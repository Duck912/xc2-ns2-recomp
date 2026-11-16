#!/usr/bin/env python3
r"""What a light-list mark draw actually covers on screen, from a trace (no game needed).

    python tools\analysis\mark_clip.py --log xc2/build/boot/play.log [--vs 5dffe004] [--rect 287,344,137,205]

Every draw whose vertex shader is the light-list one (5dffe004: a unit cube times one 64-byte
uniform block) binds that block at trace "vs ubo0": the trace's slot number is the NVN uniform
buffer index, and nvn_shaders.cpp's derive_meaning maps it as index = Maxwell bank - 3.  This script
replays the translated vertex shader with the block each draw really had, so it answers:

  * the NDC depth the draw writes (compare it with the light pass's depth attachment),
  * the screen rectangle the box covers in the 640x360 list (out-of-range numbers are the clipped
    bounding box of a box that straddles w = 0, normal for a light volume),
  * how many corners are behind the near plane (8 = the whole box is culled, which is legitimate),
  * whether the box covers --rect (default: the black rectangle, list texels 287-344 x 137-205).

Read it together with the state dump: a light-list mark writes no colour at all (channel mask 0), it
only replaces stencil 64, so "nothing appeared in the colour snapshots" says nothing about it.
"""
from __future__ import annotations

import argparse
import re
import struct
import sys

RE_DRAW = re.compile(r"nvn\.trace: draw #(\d+) vs (\S+) fs (\S+) .*?depth t(\d+) w(\d+) f(\d+) cull (\d+) logic (\d+)")
RE_UBO = re.compile(r"nvn\.trace:\s+(vs|fs) ubo(\d+) ([0-9a-f]+)/(\d+)[^:]*:\s*(.*)$")

CORNERS = [(x, y, z, 1.0) for x in (-1.0, 1.0) for y in (-1.0, 1.0) for z in (-1.0, 1.0)]
DEPTH_FUNC = {1: "NEVER", 2: "LESS", 3: "EQUAL", 4: "LEQUAL", 5: "GREATER", 6: "NOTEQUAL", 7: "GEQUAL", 8: "ALWAYS"}


def f32(h):
    return struct.unpack("<f", struct.pack("<I", int(h, 16)))[0]


def collect(path, vs_prefix):
    """-> [{"n", "fs", "m", "depth", "func", "cull"}, ...] for the draws of that vertex shader."""
    rows = []
    cur = None
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            m = RE_DRAW.search(line)
            if m:
                cur = None
                if m.group(2).startswith(vs_prefix):
                    cur = {"n": int(m.group(1)), "vs": m.group(2), "fs": m.group(3), "m": None,
                           "depth": int(m.group(4)), "func": int(m.group(6)), "cull": int(m.group(7))}
                    rows.append(cur)
                continue
            b = RE_UBO.search(line)
            if b and cur is not None and b.group(1) == "vs" and b.group(2) == "0" and cur["m"] is None:
                words = [f32(w) for w in b.group(5).split()]
                if len(words) >= 16:
                    cur["m"] = words[:16]
                    cur["addr"] = b.group(3)
    return rows


def project(m, w, h):
    """gl_Position = x*col0 + y*col1 + z*col2 + 1*col3 (what the translated shader computes)."""
    pts = []
    for c in CORNERS:
        v = [sum(m[k * 4 + i] * c[k] for k in range(4)) for i in range(4)]
        pts.append((c, v))
    behind = sum(1 for _, v in pts if v[3] <= 1e-6)
    ndc = [(v[0] / v[3], v[1] / v[3], v[2] / v[3]) for _, v in pts if v[3] > 1e-6]
    if not ndc:
        return None, behind
    xs = [p[0] for p in ndc]
    ys = [p[1] for p in ndc]
    zs = [p[2] for p in ndc]
    rect = ((min(xs) + 1) * 0.5 * w, (max(xs) + 1) * 0.5 * w,
            (1 - max(ys)) * 0.5 * h, (1 - min(ys)) * 0.5 * h)
    return (rect, (min(zs), max(zs))), behind


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--log", default="xc2/build/boot/play.log")
    ap.add_argument("--vs", default="5dffe004")
    ap.add_argument("--list", default="640x360", help="the light list's size")
    ap.add_argument("--rect", default="287,344,137,205", help="x0,x1,y0,y1 in list texels, or 'empty'")
    a = ap.parse_args(argv)
    w, h = (float(v) for v in a.list.lower().split("x"))
    rect = None if (not a.rect or a.rect == "empty") else [float(v) for v in a.rect.split(",")]
    rows = collect(a.log, a.vs)
    if not rows:
        print("no %s draws in %s (needs [nvn] trace_compact = 2)" % (a.vs, a.log))
        return 1
    print("draw  fs        depth              box on the list (x / y)                    z ndc           behind  covers rect")
    covered = behind_all = 0
    for d in rows:
        if not d["m"]:
            print("#%-4d %s  (no ubo0 dump)" % (d["n"], d["fs"][:8]))
            continue
        res, behind = project(d["m"], w, h)
        state = "t%d/w0 f%d(%s) cull %d" % (d["depth"], d["func"], DEPTH_FUNC.get(d["func"], "?"), d["cull"])
        if res is None:
            print("#%-4d %s  %-18s whole box behind the near plane (w <= 0)" % (d["n"], d["fs"][:8], state))
            behind_all += 1
            continue
        r, z = res
        hit = ""
        if rect:
            ox = max(0.0, min(r[1], rect[1]) - max(r[0], rect[0]))
            oy = max(0.0, min(r[3], rect[3]) - max(r[2], rect[2]))
            frac = ox * oy / max(1e-6, (rect[1] - rect[0]) * (rect[3] - rect[2]))
            hit = "%.2f" % frac
            covered += 1 if frac > 0 else 0
        print("#%-4d %s  %-18s x %7.0f..%-7.0f y %7.0f..%-7.0f  %5.3f..%-5.3f  %d       %s"
              % (d["n"], d["fs"][:8], state, r[0], r[1], r[2], r[3], z[0], z[1], behind, hit))
    print()
    print("%d mark draws: %d project a box, %d are entirely behind the near plane%s"
          % (len(rows), len(rows) - behind_all, behind_all,
             (", %d of the projected ones cover the rect" % covered) if rect else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
