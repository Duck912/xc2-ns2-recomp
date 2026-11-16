#!/usr/bin/env python3
r"""Per-draw history of the 640x360 light list, from trace_snap_rt / trace_snap_tex snapshots.

    python tools\analysis\snap_list.py --dir xc2/build/boot [--rect 287,344,137,205] [--draws 690-760]

\\"[nvn] trace_snap_rt = 50\\" + \\"[nvn] trace_snap_tex = 43\\" make the runtime copy the list (RG32UI: word0 = four
light-index bytes, word1 = four 0xff slot flags) and the pass's D24S8 (depth + stencil) after every draw that
renders into the list, and write snap_d<draw>_t<id>_<format>.png plus a .png.bin with the raw texels.  The .bin
is the only readable form for an integer target: the PNG keeps 8 of 32 bits per channel.

For every snapshot this prints, over the black rectangle and over the left and right bands beside it:
  t50  fill   = texels whose word0 is not 0 (a light index was written)
       full   = texels whose word1 is 0xffffffff (all four slots taken)
       idx    = the distinct bytes of word0 (the light indices in the slot numbering the shader uses)
  t43  st40   = texels whose stencil has bit 0x40 (the mark the OR draws test with EQUAL 64)
       depth  = the mean of the 24-bit depth
t51 (the pass's per-tile 32-bit registered-light mask, when trace_snap_tex includes 51) adds the popcount
per region, i.e. how many lights that tile has taken so far.
so "the mark wrote but no OR consumed it" (st40 high, fill 0) and "the OR ran but declined"
(st40 0, fill 0 while the band fills) are different rows.
"""
from __future__ import annotations

import argparse
import glob
import os
import re
import struct
import sys

import numpy as np

SNAP = re.compile(r"snap_d(\d+)_t(\d+)_([A-Za-z0-9_]+)\.png\.bin$")


def load(path, w, h, bpp):
    """-> (texels, width, height).  A run whose window size differs renders the list at another size (604x340 for a
    1208x680 window), so the shape is taken from the file and the regions are scaled from the 640x360 reference."""
    a = np.fromfile(path, dtype=np.uint8)
    if a.size == w * h * bpp:
        return a.reshape(h, w, bpp), w, h
    n = a.size // bpp
    for hh in range(180, 2161, 2):
        if n % hh:
            continue
        ww = n // hh
        if 320 <= ww <= 2560 and abs(ww / float(hh) - 16.0 / 9.0) < 0.06:
            return a.reshape(hh, ww, bpp), ww, hh
    raise SystemExit("%s: %d bytes is not a 16:9 texel grid of %d-byte texels" % (path, a.size, bpp))


def region_stats(mask):
    return mask


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default="xc2/build/boot")
    ap.add_argument("--list-size", default="640x360")
    ap.add_argument("--rect", default="287,344,137,205", help="x0,x1,y0,y1 of the black rectangle")
    ap.add_argument("--band", type=int, default=57, help="width of the comparison bands left and right of the rect")
    ap.add_argument("--draws", default="", help="only this range, e.g. 690-760")
    ap.add_argument("--deltas", action="store_true", help="per draw, over the whole list: how many texels the mask registered and how many the colour changed")
    a = ap.parse_args(argv)

    w, h = (int(v) for v in a.list_size.lower().split("x"))
    x0, x1, y0, y1 = (int(v) for v in a.rect.split(","))
    bw = a.band
    regions = [
        ("rect", x0, x1, y0, y1),
        ("left", max(0, x0 - bw), x0, y0, y1),
        ("right", x1, min(w, x1 + bw), y0, y1),
    ]
    lo, hi = (int(v) for v in a.draws.split("-")) if a.draws else (0, 1 << 30)

    t50 = {}
    t43 = {}
    t51 = {}
    for p in glob.glob(os.path.join(a.dir, "snap_d*_*.png.bin")):
        m = SNAP.search(os.path.basename(p))
        if not m:
            continue
        n, tid, fmt = int(m.group(1)), int(m.group(2)), m.group(3)
        if not (lo <= n <= hi):
            continue
        if fmt == "RG32UI" and tid == 50:
            t50[n] = p
        elif fmt == "R32UI" and tid == 51:
            t51[n] = p
        elif fmt == "DEPTH24_STENCIL8" and tid == 43:
            t43[n] = p
    if not t50 and not t43:
        print("no snapshots in %s (needs [nvn] trace_snap_rt = 50 / trace_snap_tex = 43, and F11 in the game)" % a.dir)
        return 1
    if a.deltas:
        prev = None
        print("draw | mask registered | colour word0 changed | colour word1 changed")
        for n in sorted(set(t50) | set(t51)):
            if n not in t50 or n not in t51:
                continue
            img, iw, ih = load(t50[n], w, h, 8)
            w0 = img[:, :, 0:4].copy().view(np.uint32).reshape(ih, iw)
            w1 = img[:, :, 4:8].copy().view(np.uint32).reshape(ih, iw)
            mk, _, _ = load(t51[n], w, h, 4)
            mk = mk.view(np.uint32).reshape(ih, iw)
            if prev is not None:
                p0, p1, pm = prev
                reg = int(((mk != 0) & (pm == 0)).sum())
                c0 = int((w0 != p0).sum())
                c1 = int((w1 != p1).sum())
                if reg or c0 or c1:
                    print("%4d | %15d | %20d | %20d" % (n, reg, c0, c1))
            prev = (w0, w1, mk)
        return 0
    print("t50 snapshots %d, t51 snapshots %d, t43 snapshots %d; regions: %s" % (len(t50), len(t51), len(t43), ", ".join("%s %d..%d x %d..%d" % r for r in regions)))
    print()
    print("draw | region | t50 fill  full  idx bytes        | t43 st40  depth")
    for n in sorted(set(t50) | set(t43) | set(t51)):
        pools = {}
        if n in t50:
            img, iw, ih = load(t50[n], w, h, 8)
            w0 = img[:, :, 0:4].copy().view(np.uint32).reshape(ih, iw)
            w1 = img[:, :, 4:8].copy().view(np.uint32).reshape(ih, iw)
            pools["t50"] = (w0, w1, iw, ih)
        if n in t43:
            img, iw43, ih43 = load(t43[n], w, h, 4)
            depth = (img[:, :, 0].astype(np.uint32) | (img[:, :, 1].astype(np.uint32) << 8) |
                     (img[:, :, 2].astype(np.uint32) << 16)).astype(np.float64) / 16777215.0
            pools["t43"] = (img[:, :, 3], depth, iw43, ih43)
        if n in t51:
            img, iw5, ih5 = load(t51[n], w, h, 4)
            pools["t51"] = (img[:, :, 0:4].copy().view(np.uint32).reshape(ih5, iw5), iw5, ih5)
        for name, rx0, rx1, ry0, ry1 in regions:
            fill = full = "     -      -"
            idxs = ""
            st = dep = "    -"
            mask = ""
            if "t50" in pools:
                w0, w1, iw, ih = pools["t50"]
                X0, X1 = int(rx0 * iw / float(w)), int(rx1 * iw / float(w))
                Y0, Y1 = int(ry0 * ih / float(h)), int(ry1 * ih / float(h))
                s0 = w0[Y0:Y1, X0:X1]
                s1 = w1[Y0:Y1, X0:X1]
                fill = "%5.1f%%" % (100.0 * (s0 != 0).mean())
                full = "%5.1f%%" % (100.0 * (s1 == 0xFFFFFFFF).mean())
                vals, cnts = np.unique(s0.view(np.uint8).reshape(-1), return_counts=True)
                got = [(int(v), int(c)) for v, c in zip(vals, cnts) if v != 0]
                idxs = " ".join("%d:%d" % (v, c) for v, c in sorted(got, key=lambda x: -x[1])[:5])
            if "t51" in pools:
                mki, iw5, ih5 = pools["t51"]
                mk = mki[int(ry0 * ih5 / float(h)):int(ry1 * ih5 / float(h)), int(rx0 * iw5 / float(w)):int(rx1 * iw5 / float(w))]
                uniq, cnts = np.unique(mk, return_counts=True)
                hist = {}
                for v, c in zip(uniq, cnts):
                    hist[bin(int(v)).count("1")] = hist.get(bin(int(v)).count("1"), 0) + int(c)
                mask = "pop " + " ".join("%d:%d%%" % (k, round(100.0 * v / mk.size)) for k, v in sorted(hist.items()))
            if "t43" in pools:
                sbyte, depth, iw4, ih4 = pools["t43"]
                sb = sbyte[int(ry0 * ih4 / float(h)):int(ry1 * ih4 / float(h)), int(rx0 * iw4 / float(w)):int(rx1 * iw4 / float(w))]
                dp = depth[int(ry0 * ih4 / float(h)):int(ry1 * ih4 / float(h)), int(rx0 * iw4 / float(w)):int(rx1 * iw4 / float(w))]
                st = "%5.1f%%" % (100.0 * ((sb & 0x40) != 0).mean())
                dep = "%.3f" % float(dp.mean())
            print("%4d | %-6s | %s   %s  %-18s | %s  %s | %s" % (n, name, fill, full, idxs[:18], st, dep, mask))
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))