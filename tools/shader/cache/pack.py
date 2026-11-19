#!/usr/bin/env python3
"""Build a spirv.preload.pack that holds every translated shader.

    python tools/shader/cache/pack.py --rows <cache>/results.tsv --cache <cache> --out pack [--install <path>]

Why a pack: the runtime otherwise reads one loose .spv per shader, which is thousands of small random reads.
A pack is one sequential file and pack_prefetch() reads it front to back, so every later lookup is a
page-cache hit. The runtime reads the pack **before** the loose files, so a stale pack shadows a freshly
installed .spv — which is why installing a shader has to rebuild this.

Entry format (matches PackHeader 32 B / PackDiskEntry 40 B in the runtime):

    hash[16]  u64 line_hash  u64 offset  u32 csize  u32 usize

line_hash is the FNV-1a 64 of that shader's results.tsv line. pack_open() drops an entry whose line_hash does
not match, so it must be computed, never zeroed.

Requires zstandard (pip install zstandard).
"""
import argparse
import json
import os
import struct
import sys

HEAD = 0x20
REC = 40
SPV_MAGIC = bytes.fromhex("03022307")

EXIT_OK = 0
EXIT_ARGS = 2
EXIT_INPUT = 3
EXIT_DEP = 4
EXIT_STEP = 5

try:
    import zstandard
except ImportError:
    print(json.dumps({"event": "error", "code": EXIT_DEP,
                      "message": "zstandard is not installed: pip install zstandard"}))
    sys.exit(EXIT_DEP)


def fnv1a64(s):
    h = 0xcbf29ce484222325
    for c in s:
        h ^= c
        h = (h * 0x100000001b3) & 0xFFFFFFFFFFFFFFFF
    return h


def read_rows(paths):
    rows = {}
    for p in paths:
        with open(p, encoding="utf-8") as f:
            for line in f:
                line = line.rstrip("\n")
                if not line or line.startswith("hash\t"):
                    continue
                h = line.split("\t", 1)[0]
                if h in rows and rows[h] != line:
                    raise SystemExit("conflicting rows for " + h)
                rows[h] = line
    return rows


def parse(blob):
    if blob[:8] != b"NXSPACK1":
        raise ValueError("bad magic")
    ver, count = struct.unpack_from("<II", blob, 8)
    idx = struct.unpack_from("<Q", blob, 0x10)[0]
    out = []
    for k in range(count):
        o = idx + k * REC
        out.append((blob[o:o + 16].split(b"\x00")[0].decode(),
                    struct.unpack_from("<Q", blob, o + 16)[0],
                    struct.unpack_from("<Q", blob, o + 24)[0],
                    struct.unpack_from("<I", blob, o + 32)[0],
                    struct.unpack_from("<I", blob, o + 36)[0]))
    return ver, count, idx, out


def main(argv):
    ap = argparse.ArgumentParser(description="Build a spirv.preload.pack.")
    ap.add_argument("--rows", nargs="+", required=True, help="one or more results.tsv files")
    ap.add_argument("--cache", required=True, help="the spirv cache folder")
    ap.add_argument("--out", required=True, help="where to write the pack")
    ap.add_argument("--install", default="", help="also copy the pack here (keeps a .bak-before-full)")
    ap.add_argument("--skip", default="", help="file of hashes to leave out")
    ap.add_argument("--level", type=int, default=19)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)

    def emit(**kw):
        if a.json:
            print(json.dumps(kw, ensure_ascii=False), flush=True)

    rows = read_rows(a.rows)
    skip = set()
    if a.skip and os.path.exists(a.skip):
        with open(a.skip, encoding="utf-8") as f:
            skip = {line.strip() for line in f if line.strip()}
    spv = {n[:-4]: os.path.join(a.cache, n) for n in os.listdir(a.cache) if n.endswith(".spv")}
    have = sorted(h for h in rows if h in spv and h not in skip)
    no_spv = [h for h in rows if h not in spv]
    emit(event="plan", rows=len(rows), cache=len(spv), skipped=len(skip), entries=len(have),
         rows_without_spv=len(no_spv))
    if not a.json:
        print("rows %d  cache %d  skipped %d  entries to pack %d" % (len(rows), len(spv), len(skip), len(have)))
        if no_spv:
            print("  WARNING: %d rows have no .spv and are left out: %s" % (len(no_spv), no_spv[:5]))
    if not have:
        emit(event="error", code=EXIT_INPUT, message="nothing to pack: no row has an .spv in " + a.cache)
        if not a.json:
            print("ERROR: nothing to pack", file=sys.stderr)
        return EXIT_INPUT

    cctx = zstandard.ZstdCompressor(level=a.level)
    frames = bytearray()
    recs = bytearray()
    total_unc = 0
    for h in have:
        with open(spv[h], "rb") as f:
            mod = f.read()
        if mod[:4] != SPV_MAGIC:
            emit(event="error", code=EXIT_INPUT, message="%s is not a SPIR-V module" % h)
            if not a.json:
                print("ERROR: %s is not a SPIR-V module" % h, file=sys.stderr)
            return EXIT_INPUT
        comp = cctx.compress(mod)
        off = HEAD + len(frames)
        frames += comp
        total_unc += len(mod)
        recs += h.encode() + struct.pack("<Q", fnv1a64(rows[h].encode())) + struct.pack("<QII", off, len(comp), len(mod))

    idx = HEAD + len(frames)
    head = bytearray(HEAD)
    head[0:8] = b"NXSPACK1"
    struct.pack_into("<II", head, 8, 1, len(have))
    struct.pack_into("<Q", head, 0x10, idx)
    blob = bytes(head) + bytes(frames) + bytes(recs)
    folder = os.path.dirname(os.path.abspath(a.out))
    if folder:
        os.makedirs(folder, exist_ok=True)
    with open(a.out, "wb") as f:
        f.write(blob)
    emit(event="wrote", path=a.out, bytes=len(blob), entries=len(have), spirv_bytes=total_unc)
    if not a.json:
        print("wrote %s: %.1f MB, %d entries, %.1f MB of SPIR-V (%.1fx)"
              % (a.out, len(blob) / 1e6, len(have), total_unc / 1e6, total_unc / max(1, len(blob))))

    # verify from scratch: every entry must decompress to the same module and keep its line_hash
    _ver, count, _idx, parsed = parse(blob)
    dctx = zstandard.ZstdDecompressor()
    bad = 0
    for h, lh, off, cs, us in parsed:
        mod = dctx.decompress(blob[off:off + cs])
        if len(mod) != us or mod[:4] != SPV_MAGIC or fnv1a64(rows[h].encode()) != lh:
            bad += 1
            continue
        with open(spv[h], "rb") as f:
            if f.read() != mod:
                bad += 1
    emit(event="verify", entries=count, failed=bad)
    if not a.json:
        print("verify: %d entries parsed, modules that fail round-trip or line_hash: %d" % (count, bad))
    if bad:
        emit(event="error", code=EXIT_STEP, message="%d entries failed verification; refusing to install" % bad)
        if not a.json:
            print("REFUSING to install", file=sys.stderr)
        return EXIT_STEP

    if a.install:
        import shutil
        bak = a.install + ".bak-before-full"
        if os.path.exists(a.install) and not os.path.exists(bak):
            shutil.copy2(a.install, bak)
            if not a.json:
                print("backup:", bak)
        shutil.copy2(a.out, a.install)
        emit(event="installed", path=a.install, bytes=os.path.getsize(a.install))
        if not a.json:
            print("installed:", a.install, os.path.getsize(a.install), "bytes")
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
