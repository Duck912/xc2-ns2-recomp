#!/usr/bin/env python3
"""Who paints over the scene: blended draws in a traced frame, cut by the depth state they really run with.

    python tools/analysis/trace_depth.py play.log                 # every group, biggest first
    python tools/analysis/trace_depth.py play.log --quads 6       # only draws of <= 6 indices (a card is 4 or 6)
    python tools/analysis/trace_depth.py play.log --rt 13         # only draws into texture 13
    python tools/analysis/trace_depth.py play.log --depth-off     # only the draws without an effective depth test

The trace (F11 / NXRT_NVN_TRACE_FRAME) prints one "draw #N ..." block per draw; since HANDOVER 42.3 it also carries a
"depth eff test T write W func F(NAME)" line and named blend enums. An older log has neither: then the depth columns come from
the draw line ("depth t0 w0 f2", the guest's request) and the names are derived from the NVN numbers.

The point of the report: a translucent quad that ignores the scene's depth (a light card, a decal, a full-screen effect that
should not be one) is a group whose "eff" depth test is 0 while it blends. --quads narrows it to card-sized draws, because a
card is four vertices of a strip or six indices of two triangles.
"""
import argparse
import re
import sys
from collections import OrderedDict

BLEND = {1: "ZERO", 2: "ONE", 3: "SRC_COLOR", 4: "1-SRC_COLOR", 5: "SRC_ALPHA", 6: "1-SRC_ALPHA",
         7: "DST_ALPHA", 8: "1-DST_ALPHA", 9: "DST_COLOR", 10: "1-DST_COLOR", 11: "SRC_ALPHA_SAT",
         12: "SRC1_COLOR", 13: "1-SRC1_COLOR", 14: "SRC1_ALPHA", 15: "1-SRC1_ALPHA"}
EQ = {1: "ADD", 2: "SUB", 3: "REV_SUB", 4: "MIN", 5: "MAX"}
CMP = {1: "NEVER", 2: "LESS", 3: "EQUAL", 4: "LEQUAL", 5: "GREATER", 6: "NOTEQUAL", 7: "GEQUAL", 8: "ALWAYS"}

RE_DRAW = re.compile(r"nvn\.trace: draw #(\d+) vs (\S+) fs (\S+) gs (\S+) mode (\d+) idx (\d+) \|\s*rt (.*?)\s*\|\s*ds (.*?)\s*\|\s*blend (\d+) mask (\S+) depth t(\d) w(\d) f(\d+) cull (\d+) logic (\d+)")
RE_EFF = re.compile(r"nvn\.trace:\s+depth eff test (\d) write (\d) func (\d+)")
RE_CNT = re.compile(r"nvn\.trace:\s+indexed: count (\d+) type (\d+) instances (\d+)")
RE_BLEND = re.compile(r"nvn\.trace:\s+blend rt(\d+) rgb (\d+),(\d+),(\d+) a (\d+),(\d+),(\d+)")


def tex_id(desc):
    m = re.match(r"t(\d+):", desc.strip())
    return int(m.group(1)) if m else -1


def parse(path):
    draws, cur = [], None
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            m = RE_DRAW.search(line)
            if m:
                cur = {"n": int(m.group(1)), "vs": m.group(2), "fs": m.group(3), "mode": int(m.group(5)),
                       "rt": tex_id(m.group(7)), "blend_mask": int(m.group(9)),
                       "test": m.group(11) == "1", "write": m.group(12) == "1", "func": int(m.group(13)),
                       "eff": None, "count": None, "src": 0, "dst": 0, "eq": 0}
                draws.append(cur)
                continue
            if cur is None:
                continue
            m = RE_EFF.search(line)
            if m:
                cur["eff"] = (m.group(1) == "1", m.group(2) == "1", int(m.group(3)))
                continue
            m = RE_CNT.search(line)
            if m:
                cur["count"] = int(m.group(1))
                continue
            m = RE_BLEND.search(line)
            if m and m.group(1) == "0":
                cur["src"], cur["dst"], cur["eq"] = int(m.group(2)), int(m.group(3)), int(m.group(4))
    # A draw's effective state (new traces) must not be confused with the guest's.
    for d in draws:
        if d["eff"]:
            d["test"], d["write"], d["func"] = d["eff"]
    return draws


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("log")
    ap.add_argument("--rt", type=int, default=None, help="only draws into this texture id")
    ap.add_argument("--quads", type=int, default=None, metavar="N", help="only draws with at most N indices")
    ap.add_argument("--depth-off", action="store_true", help="only draws without an effective depth test")
    ap.add_argument("--top", type=int, default=40)
    args = ap.parse_args()

    draws = parse(args.log)
    if not draws:
        print("no traced draw found (is this a log with nvn.trace lines?)")
        return 1
    blended = [d for d in draws if d["blend_mask"] != 0]
    no_depth = [d for d in blended if not d["test"]]
    print(f"frame: {len(draws)} draws, {len(blended)} blended, {len(no_depth)} blended without an effective depth test")
    if args.rt is not None:
        blended = [d for d in blended if d["rt"] == args.rt]
    if args.quads is not None:
        blended = [d for d in blended if d["count"] is not None and d["count"] <= args.quads]
    if args.depth_off:
        blended = [d for d in blended if not d["test"]]

    groups = OrderedDict()
    for d in blended:
        key = (d["rt"], d["fs"], d["src"], d["dst"], d["eq"], d["test"], d["write"], d["func"], d["count"])
        groups.setdefault(key, []).append(d["n"])
    rows = sorted(groups.items(), key=lambda kv: -len(kv[1]))
    print(f"{len(rows)} groups (target, shader, blend, eff depth, count)")
    for key, nums in rows[:args.top]:
        rt, fs, src, dst, eq, test, write, func, count = key
        nums_s = " ".join(f"#{n}" for n in nums[:10]) + (" ..." if len(nums) > 10 else "")
        print(f"{len(nums):5d} x t{rt:<4d} {fs[:8]:8s} blend {str(BLEND.get(src, src))},{str(BLEND.get(dst, dst))},{str(EQ.get(eq, eq)):8s} "
              f"depth {'ON ' if test else 'OFF'} write {int(write)} {str(CMP.get(func, func)):6s} count {count if count is not None else '?':>6}  {nums_s}")   # noqa: E501
    return 0


if __name__ == "__main__":
    sys.exit(main())
