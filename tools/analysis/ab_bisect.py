#!/usr/bin/env python3
"""Live A/B on a running game: turn groups of draws off through skip_uvdiv.txt and measure a rectangle in the runtime's own
screenshots (nxrt.ini: [nvn] shot_frames / shot_dir / skip_fs_file; see tools/run/ab.cmd).

    python tools/analysis/ab_bisect.py --shots work/_tmp/ab/stream --inside 585,660 --ring 520,575,690,745 --rows 300,360 \
        --only-blended [--group 45] [--dry] [--range 2926-3149]

The draw numbers are the traced frame's (press F11 once, then leave the game alone: the runtime compares "#A-B" against the
draws of the live frame). The report gives, per group, the rectangle's inside/ring brightness ratio - the artefact is present
when that ratio is well below 1 - and a reference patch's brightness; when the reference collapses the group carries the scene
itself and the trial says nothing about the artefact.
"""
import argparse
import glob
import os
import re
import sys
import time

import numpy as np
from PIL import Image

RE_DRAW = re.compile(r"nvn\.trace: draw #(\d+) .*? blend (\d+) mask")


def parse(path, only_blended):
    nums = []
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            m = RE_DRAW.search(line)
            if m and (not only_blended or int(m.group(2)) != 0):
                nums.append(int(m.group(1)))
    return sorted(set(nums))


def make_groups(nums, size):
    out, cur = [], [nums[0]] if nums else []
    for n in nums[1:]:
        if n - cur[-1] <= 6 and len(cur) < size:
            cur.append(n)
        else:
            out.append((cur[0], cur[-1], len(cur)))
            cur = [n]
    if cur:
        out.append((cur[0], cur[-1], len(cur)))
    return out


def newest(after, shots):
    for _ in range(40):
        c = [p for p in glob.glob(os.path.join(shots, "*.png"))
             if re.search(r"\d{6}\.png$", os.path.basename(p)) and os.path.getmtime(p) > after]
        if c:
            return max(c, key=os.path.getmtime)
        time.sleep(0.25)
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--log", default="xc2/build/boot/play.log")
    ap.add_argument("--shots", required=True)
    ap.add_argument("--skip", default="tools/run/skip_uvdiv.txt")
    ap.add_argument("--inside", type=lambda s: [int(v) for v in s.split(",")], required=True, help="x0,x1")
    ap.add_argument("--ring", type=lambda s: [int(v) for v in s.split(",")], required=True, help="left x0,x1,right x0,x1")
    ap.add_argument("--rows", type=lambda s: [int(v) for v in s.split(",")], default=[300, 360])
    ap.add_argument("--ref", type=lambda s: [int(v) for v in s.split(",")], default=[100, 260, 600, 700])
    ap.add_argument("--group", type=int, default=45)
    ap.add_argument("--only-blended", action="store_true")
    ap.add_argument("--wait", type=float, default=3.5)
    ap.add_argument("--range", default=None, help="test only this #A-B group")
    ap.add_argument("--dry", action="store_true")
    args = ap.parse_args()

    nums = parse(args.log, args.only_blended)
    if not nums:
        print("no draw lines in the log: press F11 in the game first (the numbers are the traced frame's)")
        return 1
    gs = make_groups(nums, args.group)
    print(f"{len(nums)} draws, {len(gs)} groups")
    if args.range:
        a, b = (int(v) for v in args.range.split("-"))
        gs = [g for g in gs if not (g[1] < a or g[0] > b)]
    if args.dry:
        for a, b, c in gs:
            print(f"  #{a}-{b} ({c})")
        return 0

    y0, y1 = args.rows
    rx0, rx1, ry0, ry1 = args.ref

    def measure(path):
        im = None
        for _ in range(12):                      # the game may still be writing the file
            try:
                im = np.asarray(Image.open(path).convert("RGB")).astype(np.float32)
                break
            except Exception:
                time.sleep(0.25)
        if im is None:
            return float("nan"), float("nan")
        x0, x1 = args.inside
        lx0, lx1, rx0_, rx1_ = args.ring
        ins = im[y0:y1, x0:x1].reshape(-1, 3).mean()
        ring = (im[y0:y1, lx0:lx1].reshape(-1, 3).mean() + im[y0:y1, rx0_:rx1_].reshape(-1, 3).mean()) / 2
        ref = im[ry0:ry1, rx0:rx1].reshape(-1, 3).mean()
        return float(ins / (ring + 1e-6)), float(ref)

    t0 = time.time()
    open(args.skip, "w").write("\n")
    time.sleep(args.wait)
    p = newest(t0, args.shots)
    base_ratio = base_ref = None
    if p:
        base_ratio, base_ref = measure(p)
        print(f"baseline: ratio {base_ratio:.3f} ref {base_ref:.1f} ({os.path.basename(p)})")
    for a, b, c in gs:
        t0 = time.time()
        open(args.skip, "w").write(f"#{a}-{b}\n")
        time.sleep(args.wait)
        p = newest(t0, args.shots)
        if not p:
            print(f"#{a}-{b}: no screenshot")
            continue
        ratio, ref = measure(p)
        gone = base_ratio is not None and ratio > base_ratio + 0.08
        dead = base_ref is not None and ref < base_ref * 0.5
        print(f"#{a}-{b} ({c:3d} draws): ratio {ratio:5.3f} ref {ref:6.1f}"
              f"{'   <== BLOCK GONE' if gone else ''}{'   (scene gone)' if dead else ''}")
    open(args.skip, "w").write("\n")
    print("skip file cleared")
    return 0


if __name__ == "__main__":
    sys.exit(main())
