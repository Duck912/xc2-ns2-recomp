#!/usr/bin/env python3
"""Who painted this pixel: walk a per-draw render-target history and name the draw that changed a rectangle.

    python tools/analysis/snap_who.py snap_d*.png --inside 585,660,300,360 --control 760,835,300,360
    python tools/analysis/snap_who.py snap_d*.png --inside 585,660,300,360 --control 760,835,300,360 --min 0.03

The history comes from [nvn] trace_snap_rt = <texture id> in nxrt.ini: the traced frame copies that render target after every
draw that renders into it, as snap_d<draw>_t<id>_<format>.png. Sorting the files by draw number gives the target's whole frame,
one image per draw, and the first image whose rectangle differs from the one before it is the draw that painted it.

The rectangles are in pixels of the dumped image (1280x720 for the game's scene target) and are given as x0,x1,y0,y1. --control
is a rectangle that must NOT change (a reference of the same depth, so a whole-screen effect and a local one are told apart):
the report prints the change of both, and --min is how much the measured ratio has to move to count as "this draw painted it".
"""
import argparse
import glob
import os
import re
import sys

import numpy as np
from PIL import Image

RE_NAME = re.compile(r"snap_d(\d+)_t(\d+)_")


def rect_mean(img, r):
    x0, x1, y0, y1 = r
    return img[y0:y1, x0:x1].reshape(-1, 3).mean(0)


def parse_rect(s):
    x0, x1, y0, y1 = (int(v) for v in s.split(","))
    return x0, x1 + 1, y0, y1 + 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="+")
    ap.add_argument("--inside", required=True, help="x0,x1,y0,y1 of the rectangle that the draw paints")
    ap.add_argument("--control", default=None, help="x0,x1,y0,y1 of a rectangle that must stay constant")
    ap.add_argument("--min", type=float, default=0.02, help="how much the inside/control ratio has to move (default 0.02)")
    ap.add_argument("--rt", type=int, default=None, help="only snapshots of this texture id (snap_d*_t<N>_*)")
    ap.add_argument("--top", type=int, default=12)
    args = ap.parse_args()

    inside = parse_rect(args.inside)
    control = parse_rect(args.control) if args.control else None
    files = []
    for f in args.files:
        for p in glob.glob(f):
            m = RE_NAME.search(os.path.basename(p))
            if m and (args.rt is None or int(m.group(2)) == args.rt):
                files.append((int(m.group(1)), p))
    files.sort()
    if not files:
        print("no snap_d<draw>_t<id>_*.png files given")
        return 1
    print(f"{len(files)} snapshots, draw {files[0][0]}..{files[-1][0]}")

    prev = None
    hits = []
    for draw, path in files:
        img = np.asarray(Image.open(path).convert("RGB")).astype(np.float32)
        a = rect_mean(img, inside)
        c = rect_mean(img, control) if control else np.array([1.0, 1.0, 1.0], np.float32)
        ratio = float((a / np.maximum(c, 1e-3)).mean())
        delta = 0.0 if prev is None else ratio - prev
        if prev is not None and abs(delta) >= args.min:
            hits.append((draw, ratio, delta, path))
        prev = ratio
    print(f"{len(hits)} draw(s) moved the rectangle by more than {args.min:g}")
    for draw, ratio, delta, path in hits[:args.top]:
        print(f"  draw #{draw:5d}  ratio {ratio:6.3f}  delta {delta:+.3f}  {os.path.basename(path)}")
    if not hits:
        print("  (nothing moved it: the rectangle is already there before the first snapshot, or lies in an unwritten channel)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
