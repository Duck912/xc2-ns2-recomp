#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
r"""Census of play sessions from the runtime logs.

    python tools\analysis\session_census.py [log dir] [--per-session]

Reads every play-*.log / ns1-*.log in work\logs (default: <repo>\work\logs) and answers the question that a crash
report cannot: *which configuration were the crashing sessions running, and how long did the others survive?* It
classifies each session by the upscaler actually in use (the first "context made: FSR x.y.z" / "first evaluation,
taau" line), measures the duration from the log timestamps, and groups the amdvlk crash signature
("amdvlk64.dll+0x4acf06").

HANDOVER 95 used this to show the amdvlk crash is tied to FSR 4.1.2: 3 crashes in 19.7 minutes of FSR 4.1.2 against 0
in 236 minutes of FSR 3.1.6 / TAAU.
"""

import argparse
import glob
import os
import re
import sys

CRASH = 'amdvlk64.dll+0x4acf06'


def classify(path):
    txt = open(path, 'r', encoding='utf-8', errors='replace').read()
    stamps = re.findall(r'^\[\s*([0-9]+\.[0-9]+)', txt, re.M)
    dur = max((float(v) for v in stamps[-5:]), default=0.0)
    if 'context made: FSR 4.1.2' in txt:
        group = 'fsr4'
    elif 'context made: FSR 3.1.6' in txt:
        group = 'fsr3.1'
    elif 'first evaluation, taau' in txt or 'upscaler -> taau' in txt:
        group = 'taau'
    else:
        group = 'other'
    win = re.search(r'platform: window (\d+x\d+)', txt)
    peak = re.findall(r'memory: footprint [0-9.]+ GB \(peak ([0-9.]+) GB', txt)
    return dict(log=os.path.basename(path), dur=dur, group=group, crash=CRASH in txt,
                window=win.group(1) if win else '', peak=peak[-1] if peak else '')


def main(argv=None):
    ap = argparse.ArgumentParser(description='per-upscaler session and crash census')
    ap.add_argument('dir', nargs='?', default='')
    ap.add_argument('--per-session', action='store_true')
    ap.add_argument('--pattern', default='play-*.log')
    a = ap.parse_args(argv)
    root = a.dir or os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'work', 'logs')
    files = sorted(glob.glob(os.path.join(root, a.pattern)))
    if not files:
        print('no %s in %s' % (a.pattern, root))
        return 2
    rows = [classify(f) for f in files]
    if a.per_session:
        print('%-40s %8s %-8s %-6s %-11s %6s' % ('log', 'dur_s', 'upscaler', 'crash', 'window', 'peak'))
        for r in rows:
            print('%-40s %8.1f %-8s %-6s %-11s %6s'
                  % (r['log'], r['dur'], r['group'], 'CRASH' if r['crash'] else '-', r['window'], r['peak']))
        print()
    agg = {}
    for r in rows:
        a_ = agg.setdefault(r['group'], [0, 0.0, 0])
        a_[0] += 1
        a_[1] += r['dur']
        a_[2] += 1 if r['crash'] else 0
    print('%-10s %5s %10s %8s %14s' % ('upscaler', 'n', 'minutes', 'crashes', 'min/crash'))
    for k in sorted(agg):
        n, d, c = agg[k]
        print('%-10s %5d %10.1f %8d %14s' % (k, n, d / 60.0, c, ('%.1f' % (d / 60.0 / c)) if c else '-'))
    print('\nsessions: %d, amdvlk64.dll+0x4acf06 crashes: %d' % (len(rows), sum(r['crash'] for r in rows)))
    return 0


if __name__ == '__main__':
    sys.exit(main())
