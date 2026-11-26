#!/usr/bin/env python3
"""Project the 640x360 light list's per-light uniform blocks onto the screen, to name the light behind a rectangle.

    python tools/analysis/light_rects.py --log xc2/build/boot/play.log [--inside 287,344,137,205]

The light list (t50) is built by one (mark stencil, logic-op OR) pair of draws per light; every such draw binds a 64-byte
uniform block with 16 floats that, read as a column-major mat4, maps the unit cube the draw rasterises onto the light's
volume. This script collects those blocks from a trace (needs [nvn] trace_compact = 2 so every draw keeps its uniform
dumps), projects the cube corners, converts to the 640x360 texel space of the list and ranks the lights by how much of them
lies inside the rectangle you are looking at.

--inside defaults to the black rectangle at First Low Orbit Station (HANDOVER 42.9: screen x 574-689 / y 275-410, i.e. texels
287-344 / 137-205). The last four columns are the block's w12..w15, the per-light values that look like colour/intensity.
"""
import argparse
import re
import struct
import sys

import numpy as np

RE_DRAW = re.compile(r"nvn\.trace: draw #(\d+) .*? fs (\S+).*?rt t50:")
RE_UBO = re.compile(r"nvn\.trace:\s+vs ubo0 [0-9a-f]+/(\d+): ([0-9a-f ]+)")


def collect(path):
    draws, cur = [], None
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            m = RE_DRAW.search(line)
            if m:
                cur = {"n": int(m.group(1)), "fs": m.group(2)[:8], "u": None}
                draws.append(cur)
                continue
            m = RE_UBO.search(line)
            if m and cur is not None and cur["u"] is None:
                cur["u"] = [struct.unpack("<f", struct.pack("<I", int(w, 16)))[0] for w in m.group(2).split()]
    return draws


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--log", default="xc2/build/boot/play.log")
    ap.add_argument("--inside", default="287,344,137,205", help="x0,x1,y0,y1 in the 640x360 list space")
    args = ap.parse_args()
    bx0, bx1, by0, by1 = (float(v) for v in args.inside.split(","))
    draws = collect(args.log)
    if not draws:
        print("no t50 draws in the log: trace with [nvn] trace_compact = 2 and press F11 in the game")
        return 1
    corners = np.array([[x, y, z, 1.0] for x in (-1, 1) for y in (-1, 1) for z in (-1, 1)])
    seen, rows = set(), []
    for d in draws:
        u = d["u"]
        if not u or len(u) < 16:
            continue
        key = tuple(round(v, 2) for v in u)
        if key in seen:
            continue
        seen.add(key)
        m = np.array(u, dtype=np.float64).reshape(4, 4)      # the block is 4 vec4s: a column-major mat4
        v = corners @ m.T
        w = v[:, 3]
        if (np.abs(w) < 1e-6).any():
            continue
        ndc = v[:, :3] / w[:, None]
        tx0, tx1 = (ndc[:, 0].min() + 1) / 2 * 640, (ndc[:, 0].max() + 1) / 2 * 640
        ty0, ty1 = (1 - ndc[:, 1].max()) / 2 * 360, (1 - ndc[:, 1].min()) / 2 * 360
        ox = max(0.0, min(tx1, bx1) - max(tx0, bx0))
        oy = max(0.0, min(ty1, by1) - max(ty0, by0))
        area = max(1e-6, (tx1 - tx0) * (ty1 - ty0))
        rows.append((ox * oy / area, ox * oy / max(1e-6, (bx1 - bx0) * (by1 - by0)), d["n"], d["fs"], tx0, tx1, ty0, ty1, u))
    rows.sort(reverse=True)
    print(f"{len(rows)} lights; rectangle x {bx0:.0f}..{bx1:.0f} y {by0:.0f}..{by1:.0f} (640x360 list space)")
    print("light-in-rect | rect-covered | draw | fs | x range | y range | w12..w15")
    for a, b, n, f, tx0, tx1, ty0, ty1, u in rows:
        neg = "  NEG" if (u[14] < 0 or u[15] < 0) else ""
        print(f"{a:5.2f} {b:5.2f} | #{n:5d} {f:8} | {tx0:7.1f}..{tx1:7.1f} {ty0:7.1f}..{ty1:7.1f} | "
              f"{u[12]:8.2f} {u[13]:8.2f} {u[14]:8.2f} {u[15]:8.2f}{neg}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
