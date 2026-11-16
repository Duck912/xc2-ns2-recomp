#!/usr/bin/env python3
"""Read the [nvn] replay_stats lines of a play log and show where the replay's time goes.

[driven by]  [nvn] replay_stats = N in nxrt.ini: one "nvn.rstats" line every N presents.
             nvn_replay.cpp / rs_report() prints it; the phases are the RsZone marks of begin_draw().

What this adds over reading the raw line: the per-draw microseconds become milliseconds per frame
(draws x us / 1000), so the phases can be compared with the "replay X ms/frame" total and with the
60 fps budget of HANDOVER 52.4 (<= 10 ms to allow 60, <= 9 ms for a clean 59 with present_ahead = 0).

Usage:
  python tools/analysis/replay_stats.py                 # the newest work/logs/play-*.log
  python tools/analysis/replay_stats.py <log> [<log>...]
  python tools/analysis/replay_stats.py <log> --all     # keep the warm-up lines (default: drop the first 3)
"""
import os
import re
import sys
import statistics as st

REPLAY = re.compile(r"replay ([\d.]+) ms/frame = draw setup ([\d.]+) \+ call ([\d.]+) \+ out ([\d.]+) \+ dispatch ([\d.]+) \+ rest ([\d.]+)")
COUNTS = re.compile(r"([\d.]+) draws/frame \(([\d.]+) desc, ([\d.]+) pipe, ([\d.]+) ubo-only, ([\d.]+) layouts, ([\d.]+) keys\), ([\d.]+) dispatches")
DRAWUS = re.compile(r"per draw us: head ([\d.]+) prep ([\d.]+) fb ([\d.]+) pass ([\d.]+) pipe ([\d.]+) dyn ([\d.]+) sets ([\d.]+) \(alloc\+update ([\d.]+)\) vb ([\d.]+) call ([\d.]+) out ([\d.]+)")
SETS = re.compile(r"sets/frame ([\d.]+) \(([\d.]+)% cached, ([\d.]+) writes\)")
BINDS = re.compile(r"binds/frame ([\d.]+) \(([\d.]+)% same\)")
STAMP = re.compile(r"^\[\s*([\d.]+) [A-Z] ")

PHASES = ["head", "prep", "fb", "pass", "pipe", "dyn", "sets", "vb"]
FRAME = ["setup", "call", "out", "dispatch", "rest"]


def newest_log():
    root = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "work", "logs")
    cand = [os.path.join(root, f) for f in os.listdir(root) if f.startswith("play-") and f.endswith(".log")]
    if not cand:
        sys.exit("no work/logs/play-*.log found")
    return max(cand, key=os.path.getmtime)


def parse(path):
    rows = []
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            if "nvn.rstats" not in line:
                continue
            m = REPLAY.search(line)
            if not m:
                continue
            r = {"t": 0.0}
            s = STAMP.match(line)
            if s:
                r["t"] = float(s.group(1))
            (r["replay"], r["setup"], r["call"], r["out"], r["dispatch"], r["rest"]) = [float(x) for x in m.groups()]
            c = COUNTS.search(line)
            if c:
                (r["draws"], r["desc"], r["dpipe"], r["ubo"], r["layouts"], r["keys"], r["disp_n"]) = [float(x) for x in c.groups()]
            d = DRAWUS.search(line)
            if d:
                g = [float(x) for x in d.groups()]   # head prep fb pass pipe dyn sets (alloc) vb call out
                r["us"] = dict(zip(PHASES[:7], g[0:7]))
                r["us"]["vb"] = g[8]
                r["us"]["alloc"] = g[7]
                r["us"]["call"] = g[9]
                r["us"]["out"] = g[10]
            se = SETS.search(line)
            if se:
                r["sets_n"], r["sets_hit"], r["sets_w"] = [float(x) for x in se.groups()]
            b = BINDS.search(line)
            if b:
                r["binds_n"], r["binds_same"] = [float(x) for x in b.groups()]
            rows.append(r)
    return rows


def med(vals):
    return st.median(vals) if vals else float("nan")


def report(path, skip_warmup=True):
    rows = parse(path)
    print("\n=== %s" % path)
    if not rows:
        print("  no nvn.rstats line: is [nvn] replay_stats set in xc2\\build\\boot\\nxrt.ini?")
        return
    body = rows[3:] if (skip_warmup and len(rows) > 4) else rows
    print("  %d rstats lines (%d in the median)" % (len(rows), len(body)))

    head = "  %6s %8s %8s %8s %8s %8s %8s | %7s %7s %7s %7s %7s" % (
        "t(s)", "replay", "setup", "call", "out", "disp", "rest", "draws", "keys", "pipe#", "sets", "binds")
    print(head)
    for r in body:
        print("  %6.1f %8.2f %8.2f %8.2f %8.2f %8.2f %8.2f | %7.0f %7.0f %7.0f %7.0f %7.0f" % (
            r["t"], r["replay"], r["setup"], r["call"], r["out"], r["dispatch"], r["rest"],
            r.get("draws", 0), r.get("keys", 0), r.get("dpipe", 0), r.get("sets_n", 0), r.get("binds_n", 0)))

    meds = {k: med([r[k] for r in body if k in r]) for k in FRAME + ["replay", "draws", "keys", "sets_n", "binds_n", "sets_hit", "binds_same"]}
    print("\n  median: replay %.2f ms/frame  (setup %.2f + call %.2f + out %.2f + dispatch %.2f + rest %.2f)" % (
        meds["replay"], meds["setup"], meds["call"], meds["out"], meds["dispatch"], meds["rest"]))
    print("          %.0f draws/frame, %.0f keys/frame, %.0f sets/frame (%.1f%% cached), %.0f binds/frame (%.1f%% same)" % (
        meds["draws"], meds["keys"], meds["sets_n"], meds["sets_hit"], meds["binds_n"], meds["binds_same"]))

    if body and "us" in body[-1]:
        d = meds["draws"]
        print("\n  where the setup time goes (us/draw -> ms/frame at %.0f draws):" % d)
        tot = 0.0
        for k in PHASES:
            us = med([r["us"][k] for r in body if "us" in r])
            ms = us * d / 1000.0
            tot += ms
            print("    %-6s %5.2f us/draw  %6.2f ms/frame  %4.1f%%" % (k, us, ms, 100.0 * ms / meds["setup"] if meds["setup"] else 0))
        print("    %-6s %5s          %6.2f ms/frame (the phases above, added up)" % ("sum", "", tot))
        print("    %-6s %5s          %6.2f ms/frame (the rstats 'setup' column)" % ("rstats", "", meds["setup"]))

    print("\n  60 fps budget (HANDOVER 52.4): replay <= 10 ms allows 60 fps, <= 9 ms for a clean 59 with present_ahead = 0")
    print("  the median replay is %.2f ms -> %s" % (meds["replay"], "inside the 9 ms target" if meds["replay"] <= 9 else
          ("inside the 10 ms gate" if meds["replay"] <= 10 else "%.1f ms to cut" % (meds["replay"] - 9))))


def main(argv):
    args = [a for a in argv[1:] if not a.startswith("--")]
    paths = args or [newest_log()]
    for p in paths:
        report(p, skip_warmup="--all" not in argv)


if __name__ == "__main__":
    main(sys.argv)
