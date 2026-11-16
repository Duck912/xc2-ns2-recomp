#!/usr/bin/env python3
"""A/B of two screenshot runs of the same save (HANDOVER 43).

The [nvn] shot_frames key writes the presented picture of the same frame numbers into two directories; this
compares them frame by frame and reports where they differ, so a fix can be judged without trusting a
remembered rectangle.

    python tools/analysis/ab_diff.py --a work/ab_earlyz/off --b work/ab_earlyz/on
    python tools/analysis/ab_diff.py --a DIR --b DIR --rect 576,264,689,404     # also report that rectangle

The numbers are 8-bit luma (0.299 R + 0.587 G + 0.114 B). A run whose frames do not line up (a cutscene that
started at another frame) shows a large bbox and a high mean difference over the whole picture - re-run it.
"""
import argparse
import glob
import os
import sys

def load(path):
    from PIL import Image
    import numpy as np
    im = Image.open(path).convert("RGB")
    a = np.asarray(im, dtype=np.float32)
    return a[..., 0] * 0.299 + a[..., 1] * 0.587 + a[..., 2] * 0.114

def frames(d):
    out = {}
    for p in glob.glob(os.path.join(d, "*.png")):
        n = os.path.splitext(os.path.basename(p))[0]
        if n.isdigit():
            out[int(n)] = p
    return out

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--a", required=True)
    ap.add_argument("--b", required=True)
    ap.add_argument("--thresh", type=float, default=6.0, help="luma difference that counts as changed (0..255)")
    ap.add_argument("--rect", default="", help="x0,y0,x1,y1 to report as well")
    ap.add_argument("--only", type=int, default=0)
    args = ap.parse_args()
    fa, fb = frames(args.a), frames(args.b)
    common = sorted(set(fa) & set(fb))
    if not common:
        print("no frame numbers in both directories")
        return 1
    import numpy as np
    print(f"{len(common)} frames, {common[0]}..{common[-1]}")
    print("frame  changed%  bbox(x0,y0,x1,y1)      mean|d|   A-mean  B-mean" + ("   rectA  rectB" if args.rect else ""))
    rect = None
    if args.rect:
        rect = [int(v) for v in args.rect.split(",")]
    worst = []
    for n in common:
        if args.only and n != args.only:
            continue
        a, b = load(fa[n]), load(fb[n])
        if a.shape != b.shape:
            print(f"{n}: size differs {a.shape} vs {b.shape}")
            continue
        d = np.abs(a - b)
        m = d > args.thresh
        cnt = int(m.sum())
        pct = 100.0 * cnt / d.size
        line = f"{n:5d}  {pct:7.3f}  "
        if cnt:
            ys, xs = np.nonzero(m)
            line += f"{xs.min():4d},{ys.min():4d},{xs.max():4d},{ys.max():4d}"
        else:
            line += " " * 21
        line += f"  {d.mean():7.3f}  {a.mean():6.1f}  {b.mean():6.1f}"
        if rect:
            x0, y0, x1, y1 = rect
            ra, rb = a[y0:y1 + 1, x0:x1 + 1], b[y0:y1 + 1, x0:x1 + 1]
            line += f"  {ra.mean():6.1f} {rb.mean():6.1f}"
            worst.append((float(ra.mean()), float(rb.mean()), n))
        print(line)
    if rect and worst:
        print()
        print("rectangle %s: A mean %.2f, B mean %.2f over %d frames" % (args.rect, np.mean([w[0] for w in worst]), np.mean([w[1] for w in worst]), len(worst)))
    return 0

if __name__ == "__main__":
    sys.exit(main())
