#!/usr/bin/env python3
"""Pull every NVN2 shader block that the resource files inside bf2.ard embed.

    python tools/shader-cache/ard_index.py    --ard <romfs>/bf2.ard --out files.tsv
    python tools/shader-cache/extract_embedded.py --ard <romfs>/bf2.ard --tsv files.tsv --out blocks

The retail 3.0.1 archive does not store shaders in the six .wishp containers alone: the rest are embedded
inside ordinary resource records. Layout of an embedded group, verified against the blocks the runtime
dumped:

    control sections first, contiguous, 0xd8 apart
    code areas follow at  code_base = round_up(last control + 0xd8, 0x1000)
    each block at the previous one rounded up to 0x100

A block's identity is the first 16 hex digits of the SHA-1 of its code, which is the same hash the runtime
uses to look a shader up, so the extraction can be checked against a dump: pass --known with a manifest.tsv
from a -dump run and the summary reports how many blocks the game is known to ask for.

Measured on the retail 3.0.1 archive (75,646 records): 13,059 groups, 78,793 blocks, 12,126 distinct,
85 seconds. Of those, 12,104 are real shaders and 22 are misaligned garbage that the game never requests.

Why it is here: the earlier tool (census.py) only understands the 3.0.0 record layout. On a 3.0.1 archive
it finds almost nothing and reports zero rows as success, which reads as "this game has no shaders".
"""
import argparse
import collections
import hashlib
import os
import struct
import sys
import time
import zlib

CONTROL_MAGIC = b"\x34\x12\x76\x98"
CONTROL_SIZE = 0xd8
CONTROL_ID = 201
NDSR_MAGIC = b"NDSR"   # ndsr.pck: an opcode stream, code before the control table
HEADER = 0x30

STAGE = {0: "vertex", 1: "fragment", 2: "geometry", 3: "tess_control", 4: "tess_eval", 5: "compute"}

MANIFEST_COLUMNS = ("id\tstage\tcode_off\tcode_size\tctrl_off\tctrl_size\tprogram_start\tprogram_bytes"
                    "\tconst_off\tconst_size\tcode_sha1_16\tcode_file\tctrl_file\n")


def load_index(path):
    recs = []
    with open(path, encoding="utf-8") as f:
        f.readline()
        for line in f:
            p = line.rstrip("\n").split("\t")
            if len(p) >= 5:
                recs.append((int(p[0]), p[1], int(p[2]), int(p[3])))
    return recs


def load_known(path):
    """Hashes the runtime has dumped, if a dump manifest is available. Optional: it only feeds a statistic."""
    known = set()
    if not path or not os.path.exists(path):
        return known
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f.read().splitlines()[1:]:
            p = line.split("\t")
            if len(p) > 12:
                known.add(p[10])
    return known


def check_pair(ard, recs, sample=24):
    """The index and the archive have to describe each other, or every offset below is nonsense."""
    if not recs:
        return 0, 0
    step = max(1, len(recs) // sample)
    ok = bad = 0
    with open(ard, "rb") as f:
        for off, name, unc, comp in recs[::step][:sample]:
            f.seek(off + HEADER)
            try:
                if len(zlib.decompress(f.read(comp))) == unc:
                    ok += 1
                else:
                    bad += 1
            except Exception:
                bad += 1
    return ok, bad


def main(argv):
    ap = argparse.ArgumentParser(description="Extract the NVN2 shader blocks embedded in bf2.ard.")
    ap.add_argument("--ard", required=True)
    ap.add_argument("--tsv", required=True, help="the record index from ard_index.py")
    ap.add_argument("--out", required=True, help="folder for the code/ctrl pairs and manifest.tsv")
    ap.add_argument("--known", default="", help="optional manifest.tsv from a -dump run, for validation")
    a = ap.parse_args(argv)

    recs = load_index(a.tsv)
    if not recs:
        print("ERROR: the index is empty: %s" % a.tsv, file=sys.stderr)
        return 1
    ok, bad = check_pair(a.ard, recs)
    if bad:
        print("ERROR: %d of %d sampled records do not inflate: the index does not describe this archive."
              % (bad, ok + bad), file=sys.stderr)
        print("       regenerate it with ard_index.py --ard %s" % a.ard, file=sys.stderr)
        return 1

    known = load_known(a.known)
    print("records: %d   known blocks: %d%s" % (len(recs), len(known), "" if known else "  (no --known: validation off)"))

    os.makedirs(a.out, exist_ok=True)
    stat = collections.Counter()
    seen = set()
    t0 = time.time()
    man = open(os.path.join(a.out, "manifest.tsv"), "w", encoding="utf-8", newline="\n")
    man.write(MANIFEST_COLUMNS)

    def emit(data, code_off, size, ctrl_off):
        """Write one block (code + its control section) and its manifest row, once per distinct hash."""
        code = data[code_off:code_off + size]
        h = hashlib.sha1(code).hexdigest()[:16]
        stat["blocks"] += 1
        if h in known:
            stat["known_hit"] += 1
        if h in seen:
            return
        seen.add(h)
        with open(os.path.join(a.out, "code_%s.bin" % h), "wb") as g:
            g.write(code)
        with open(os.path.join(a.out, "ctrl_%s.bin" % h), "wb") as g:
            g.write(data[ctrl_off:ctrl_off + CONTROL_SIZE])
        st = struct.unpack_from("<H", data, ctrl_off + 0x56)[0]
        man.write("run_%s\t%s\t0x0\t0x%x\t0x0\t0xd8\t0x%x\t0x%x\t0x%x\t0x%x\t%s\tcode_%s.bin\tctrl_%s.bin\n" % (
            h, STAGE.get(st, "unknown"), size,
            struct.unpack_from("<I", data, ctrl_off + 0x38)[0], struct.unpack_from("<I", data, ctrl_off + 0x38)[0],
            struct.unpack_from("<I", data, ctrl_off + 0x40)[0], struct.unpack_from("<I", data, ctrl_off + 0x3c)[0], h, h, h))
    with open(a.ard, "rb") as f:
        for i, (off, name, unc, comp) in enumerate(recs):
            if i and i % 10000 == 0:
                print("  %d/%d %.0fs groups=%d blocks=%d known_hit=%d"
                      % (i, len(recs), time.time() - t0, stat["groups"], stat["blocks"], stat["known_hit"]), flush=True)
            f.seek(off + HEADER)
            try:
                data = zlib.decompress(f.read(comp))
            except Exception:
                stat["inflate_fail"] += 1
                continue

            ctrls = []
            j = data.find(CONTROL_MAGIC)
            while j >= 0:
                if j + CONTROL_SIZE <= len(data) and struct.unpack_from("<I", data, j + 4)[0] == CONTROL_ID:
                    ctrls.append(j)
                j = data.find(CONTROL_MAGIC, j + 4)
            if not ctrls:
                continue

            runs, cur = [], [ctrls[0]]
            for c in ctrls[1:]:
                if c == cur[-1] + CONTROL_SIZE:
                    cur.append(c)
                else:
                    runs.append(cur)
                    cur = [c]
            runs.append(cur)

            for run in runs:
                end = run[-1] + CONTROL_SIZE
                pos = (end + 0xfff) & ~0xfff
                if pos >= len(data):
                    continue
                stat["groups"] += 1
                for c in run:
                    cs = struct.unpack_from("<I", data, c + 0x44)[0]
                    if cs == 0 or pos + cs > len(data):
                        break
                    emit(data, pos, cs, c)
                    pos += (cs + 0xff) & ~0xff

            # The "NDSR" containers (ndsr.pck) put the code BEFORE the control table and describe each program
            # with a 16-byte entry in an opcode stream:  [control][?][code][(size << 4) | flags]
            # The control section holds no pointer to its code, so the stream is the only way in.  Measured on the
            # retail archive: 40 entries, 28 distinct blocks, and all 28 of the blocks the runtime asked for were
            # found this way - they are exactly the ones the group rule above misses.
            if data[:4] == NDSR_MAGIC:
                lo, hi = ctrls[0], ctrls[-1] + CONTROL_SIZE
                stat["ndsr_records"] += 1
                for k in range(0, len(data) - 16, 4):
                    ctrl, _unused, code_off, field = struct.unpack_from("<IIII", data, k)
                    if not (lo <= ctrl < hi) or not (0 < code_off < lo):
                        continue
                    size = field >> 4
                    if size == 0 or code_off + size > len(data):
                        continue
                    stat["ndsr_blocks"] += 1
                    emit(data, code_off, size, ctrl)
    man.close()

    print("done %.0fs" % (time.time() - t0))
    print("  groups  : %d" % stat["groups"])
    print("  blocks  : %d   (inflate failures: %d)" % (stat["blocks"], stat["inflate_fail"]))
    if stat["ndsr_records"]:
        print("  ndsr    : %d record(s), %d program entries" % (stat["ndsr_records"], stat["ndsr_blocks"]))
    print("  distinct: %d   -> %s" % (len(seen), a.out))
    if known:
        print("  known   : %d of the distinct blocks are hashes the runtime has asked for" % stat["known_hit"])
    if not seen:
        print("ERROR: no embedded block found. Is this a 3.0.1 archive?", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
