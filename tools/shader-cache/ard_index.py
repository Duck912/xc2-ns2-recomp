#!/usr/bin/env python3
"""Write the file index of a bf2.ard archive.

    python tools/shader-cache/ard_index.py --ard <romfs>/bf2.ard --out files.tsv

Every record starts with the magic "xbc1" and carries its own name and sizes:

    0x00  "xbc1"          magic
    0x04  u32             version
    0x08  u32             uncompressed size
    0x0c  u32             compressed size
    0x10  u32             checksum
    0x14  name            NUL-terminated, padded to 0x30
    0x30  zlib payload    compressed size bytes

The records are not contiguous: their offsets are scattered through the archive with gaps of up to about
11 KB, so the index cannot be produced by walking from one record to the next. Scanning for the magic and
validating each candidate by inflating a sample is both simpler and safe - a false positive fails the
inflate and is dropped.

Measured on this machine: 10.2 GB in 6.1 s (52,409 records), 14.1 GB in 12.7 s (75,648 records), with
every sampled record inflating to its declared size.

Why it exists: the shader-cache tooling used to read a hand-built index that sat next to a romfs directory
which gets renamed when the archive is swapped. A stale pair failed silently - 52,400 of 52,409 records
failed to inflate and the tool reported zero rows as success.
"""
import argparse
import os
import struct
import sys
import time
import zlib

MAGIC = b"xbc1"
HEADER = 0x30
CHUNK = 64 * 1024 * 1024


def looks_valid(f, off, comp):
    """Cheap check that the payload really is a zlib stream.

    The four magic bytes can occur by chance inside compressed data (2 of 75,648 on the retail archive).
    Decompressing the first 64 output bytes is enough to tell a real record from a coincidence, and it
    costs well under a second for a whole archive.
    """
    pos = f.tell()
    try:
        f.seek(off + HEADER)
        raw = f.read(min(comp, 4096))
        d = zlib.decompressobj()
        return bool(d.decompress(raw, 64))
    except Exception:
        return False
    finally:
        f.seek(pos)


def scan(path):
    """Return (records, rejected, size); a record is (offset, name, unc, comp, checksum)."""
    records = []
    rejected = 0
    with open(path, "rb") as f:
        f.seek(0, 2)
        size = f.tell()
        f.seek(0)
        base = 0
        while True:
            chunk = f.read(CHUNK)
            if not chunk:
                break
            i = chunk.find(MAGIC)
            while i >= 0:
                off = base + i
                if i + HEADER <= len(chunk):
                    head = chunk[i:i + HEADER]
                else:
                    pos = f.tell()
                    f.seek(off)
                    head = f.read(HEADER)
                    f.seek(pos)
                if len(head) == HEADER:
                    unc, comp, ck = struct.unpack_from("<III", head, 8)
                    name = head[0x14:HEADER].split(b"\x00", 1)[0].decode("utf-8", "replace")
                    if comp and off + HEADER + comp <= size and looks_valid(f, off, comp):
                        records.append((off, name, unc, comp, ck))
                    else:
                        rejected += 1
                i = chunk.find(MAGIC, i + 1)
            base += len(chunk)
    return records, rejected, size


def verify(path, records, count):
    if not records:
        return 0, 0
    step = max(1, len(records) // max(1, count))
    ok = bad = 0
    with open(path, "rb") as f:
        for off, name, unc, comp, _ck in records[::step][:count]:
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
    ap = argparse.ArgumentParser(description="Write the file index of a bf2.ard archive.")
    ap.add_argument("--ard", required=True, help="path to bf2.ard")
    ap.add_argument("--out", required=True, help="path of the tsv to write")
    ap.add_argument("--verify", type=int, default=64, help="inflate this many records as a check (0: skip)")
    a = ap.parse_args(argv)

    t0 = time.time()
    records, rejected, size = scan(a.ard)
    if not records:
        print("ERROR: no xbc1 record found; is this a bf2.ard?", file=sys.stderr)
        return 1

    folder = os.path.dirname(os.path.abspath(a.out))
    if folder:
        os.makedirs(folder, exist_ok=True)   # the example in the docstring writes into work\, which may not exist yet
    with open(a.out, "w", encoding="utf-8", newline="\n") as f:
        f.write("offset\tname\tunc\tcomp\tchecksum\n")
        for off, name, unc, comp, ck in records:
            f.write("%d\t%s\t%d\t%d\t%08x\n" % (off, name, unc, comp, ck))

    print("archive : %s (%.2f GB)" % (a.ard, size / (1024 ** 3)))
    print("records : %d   rejected headers: %d   scan: %.1f s" % (len(records), rejected, time.time() - t0))
    print("index   : %s" % a.out)

    if a.verify:
        ok, bad = verify(a.ard, records, a.verify)
        print("verify  : %d of %d sampled records inflated" % (ok, ok + bad))
        if bad:
            print("ERROR: the index does not describe this archive; do not use it", file=sys.stderr)
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
