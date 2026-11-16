# SPDX-License-Identifier: GPL-3.0-or-later
"""Map the GfBdat* column registry slots to their bdat column names.

    python tools/analysis/bdat_cols.py 20d1e0 2101d0        # module-relative start/stop of a bdatRefresh()

A bdat accessor class stores, per column, `Bdat::getMember(table, "<name>")` into a static array; each
accessor function later reads one slot of that array. Walking the `adrp`/`add` + `bl Bdat::getMember` pairs
of the refresh function recovers slot -> name, which is what bdat_table.py needs to read a column by name.
"""
import argparse
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
RODATA = os.path.join(ROOT, 'work', 'nso', 'main.rodata.bin')
ROBASE = 0x9be000
PY = sys.executable


def disasm(start, stop):
    r = subprocess.run([PY, os.path.join(HERE, 'dis.py'), '%x' % start, '%x' % stop, '--raw'],
                       capture_output=True, text=True, cwd=ROOT)
    if r.returncode:
        raise SystemExit(r.stderr or r.stdout)
    return r.stdout.splitlines()


def rdstr(ro, va):
    o = va - ROBASE
    if o < 0 or o >= len(ro):
        return None
    e = ro.find(b'\0', o, o + 128)
    return ro[o:e].decode('ascii', 'replace') if e >= 0 else None


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('start')
    ap.add_argument('stop')
    ap.add_argument('--getmember', default='6b4ca0')
    a = ap.parse_args(argv)
    ro = open(RODATA, 'rb').read()
    cur = {}
    pairs = []
    for l in disasm(int(a.start, 16), int(a.stop, 16)):
        m = re.match(r'\s*([0-9a-f]+):\s+(\S+)\s+(.*)', l)
        if not m:
            continue
        op, rest = m.group(2), m.group(3)
        if op == 'adrp':
            mm = re.match(r'(x\d+), 0x([0-9a-f]+)', rest)
            if mm:
                cur[mm.group(1)] = int(mm.group(2), 16)
        elif op == 'add':
            mm = re.match(r'(x\d+), (x\d+), #0x([0-9a-f]+)', rest)
            if mm and mm.group(2) in cur:
                cur[mm.group(1)] = cur[mm.group(2)] + int(mm.group(3), 16)
        elif op == 'mov':
            mm = re.match(r'(x\d+), (x\d+)', rest)
            if mm and mm.group(2) in cur:
                cur[mm.group(1)] = cur[mm.group(2)]
        elif op == 'bl' and a.getmember in rest:
            pairs.append(cur.get('x1'))
    for i, va in enumerate(pairs):
        print('slot +0x%-3x  %-10s %s' % (i * 8, hex(va) if va else '?', rdstr(ro, va) if va else '?'))
    print('-- %d column(s)' % len(pairs))
    return 0


if __name__ == '__main__':
    sys.exit(main())
