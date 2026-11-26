#!/usr/bin/env python3
r"""Print the uniform blocks and storage buffers a traced draw had, as floats.

    python tools\analysis\ubodump.py --log xc2/build/boot/play.log --draw 700 [--full]
    python tools\analysis\ubodump.py --log xc2/build/boot/play.log --vs 5dffe004 --limit 4 --words 16

The slot numbers are the trace's, i.e. the NVN uniform buffer index (nvn_shaders.cpp's
derive_meaning: index = Maxwell bank - 3, so "vs ubo0" is bank 3 = a shader's _vp_c3, and
"vs ubo4" is bank 7 = _vp_c7).  --raw also prints the block's other trace lines (indices, bounds,
stencil state, pass begin), which is what makes a draw's state readable next to its constants.
"""
from __future__ import annotations

import argparse
import re
import struct
import sys

RE_DRAW = re.compile(r"nvn\.trace: draw #(\d+) vs (\S+) fs (\S+) gs (\S+) mode (\S+) idx (\S+) \| rt (\S+)")
RE_BLK = re.compile(r"nvn\.trace:\s+(vs|fs) (ubo|ssbo)(\d+) ([0-9a-f]+)/(\d+)[^:]*:\s*(.*)$")


def f32(h):
    return struct.unpack("<f", struct.pack("<I", int(h, 16)))[0]


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--log", default="xc2/build/boot/play.log")
    ap.add_argument("--draw", type=int)
    ap.add_argument("--vs")
    ap.add_argument("--fs")
    ap.add_argument("--limit", type=int, default=1)
    ap.add_argument("--words", type=int, default=32, help="floats to print per block")
    ap.add_argument("--full", action="store_true", help="also print the fragment stage's blocks")
    ap.add_argument("--raw", action="store_true", help="print the draw's other trace lines too")
    a = ap.parse_args(argv)

    shown = 0
    want = False
    with open(a.log, encoding="utf-8", errors="replace") as f:
        for line in f:
            m = RE_DRAW.search(line)
            if m:
                if want:
                    shown += 1
                    if shown >= a.limit:
                        break
                want = ((a.draw is None or a.draw == int(m.group(1)))
                        and (a.vs is None or m.group(2).startswith(a.vs))
                        and (a.fs is None or m.group(3).startswith(a.fs)))
                if want:
                    print("=" * 110)
                    print(line.rstrip("\n"))
                continue
            if not want:
                continue
            b = RE_BLK.search(line)
            if not b:
                if a.raw and "nvn.trace:" in line:
                    print("  " + line.split("nvn.trace:", 1)[1].rstrip())
                continue
            stage, kind, idx, addr, size, blob = b.groups()
            if stage == "fs" and not a.full:
                continue
            words = [f32(w) for w in blob.split()]
            if kind == "ssbo":
                print("  -- %s ssbo%s %s/%s (%d floats): %s" % (stage, idx, addr, size, len(words),
                      " ".join("%08x" % w for w in [struct.unpack("<I", struct.pack("<f", v))[0] for v in words[:8]])))
                continue
            print("  -- %s ubo%s  addr %s  size %s  (%d floats)" % (stage, idx, addr, size, len(words)))
            for i in range(0, min(len(words), a.words), 4):
                print("    [%4d] %s" % (i, " ".join("%13.6f" % v for v in words[i:i + 4])))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
