"""Scan a [nvn] trace_dump_tex folder for black / suspicious textures.

  python texdump_scan.py <dir> [--black 0.999] [--min-bytes 1024]

Every dumped texture has t<id>.bin (level 0 as the GPU sees it, linear) and t<id>.txt (format, size, transcoded, error).
A texture whose bytes are all zero renders black wherever the game samples it - the first thing to check when one
material comes out black while its neighbours are fine (HANDOVER 21). Prints the black ones by size, then a summary of
the formats in the folder.
"""
import collections
import os
import sys


def main():
    d = sys.argv[1]
    black_thr = 0.999
    min_bytes = 1024
    if "--black" in sys.argv:
        black_thr = float(sys.argv[sys.argv.index("--black") + 1])
    if "--min-bytes" in sys.argv:
        min_bytes = int(sys.argv[sys.argv.index("--min-bytes") + 1])
    rows = []
    formats = collections.Counter()
    total = 0
    for name in sorted(os.listdir(d)):
        if not name.endswith(".bin"):
            continue
        stem = os.path.join(d, name[:-4])
        try:
            data = open(stem + ".bin", "rb").read()
        except OSError:
            continue
        total += 1
        meta = ""
        try:
            meta = open(stem + ".txt", encoding="utf-8", errors="replace").readline().strip()
        except OSError:
            pass
        if len(data) < min_bytes:
            continue
        zeros = data.count(0) / float(len(data))
        fmt = ""
        size = ""
        parts = meta.split()
        for i, p in enumerate(parts):
            if p == "format" and i + 1 < len(parts):
                fmt = parts[i + 1]
            if p == "level" and i + 1 < len(parts):
                size = " ".join(parts[i + 1:i + 4])
        formats[fmt] += 1
        if zeros >= black_thr:
            rows.append((len(data), name[:-4], zeros, fmt, size, meta))
    rows.sort(reverse=True)
    print("%d textures dumped, %d of them all zero bytes (>= %.3f)" % (total, len(rows), black_thr))
    for n, tid, z, fmt, size, meta in rows[:40]:
        print("  %-12s %9d B  zeros %.4f  format %-6s %s" % (tid, n, z, fmt, size))
    print("formats seen:", dict(formats.most_common(12)))


if __name__ == "__main__":
    main()
