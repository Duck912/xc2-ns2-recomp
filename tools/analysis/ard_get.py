# SPDX-License-Identifier: GPL-3.0-or-later
"""Fetch records out of a bf2.ard using an existing listing (no full-archive scan).

    python tools/analysis/ard_get.py --ard <bf2.ard> --tsv <listing.tsv> --name common.bdat --out <dir>
    python tools/analysis/ard_get.py --ard <bf2.ard> --tsv <listing.tsv> --list 'bdat$'

The listing is what work/oracle/ard_reader.py --list writes (offset/name/unc/comp/checksum).
Record layout (xbc1): +0x00 magic, +0x08 unc, +0x0c comp, +0x14 name[28], +0x30 zlib stream.
Every inflate is length-checked against +0x08; a mismatch is a hard error.
"""
import argparse
import csv
import os
import re
import struct
import sys
import zlib

HDR = 0x30


def load(tsv, pat=None):
    rows = []
    rx = re.compile(pat) if pat else None
    with open(tsv, encoding='utf-8') as f:
        r = csv.reader(f, delimiter='\t')
        next(r)
        for row in r:
            if len(row) < 5:
                continue
            name = row[1]
            if rx and not rx.search(name):
                continue
            rows.append((int(row[0]), name, int(row[2]), int(row[3]), row[4]))
    return rows


def fetch(f, off, name, unc, comp):
    f.seek(off)
    hdr = f.read(HDR)
    if hdr[:4] != b'xbc1':
        raise SystemExit('%s: no xbc1 magic at 0x%x (got %r)' % (name, off, hdr[:4]))
    hunc, hcomp = struct.unpack_from('<II', hdr, 8)
    if hunc != unc or hcomp != comp:
        raise SystemExit('%s: listing (%d,%d) != header (%d,%d)' % (name, unc, comp, hunc, hcomp))
    blob = f.read(comp)
    if len(blob) != comp:
        raise SystemExit('%s: short read' % name)
    out = zlib.decompress(blob)
    if len(out) != unc:
        raise SystemExit('%s: inflate %d != %d' % (name, len(out), unc))
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--ard', required=True)
    ap.add_argument('--tsv', required=True)
    ap.add_argument('--name')
    ap.add_argument('--list')
    ap.add_argument('--out', default=None)
    ap.add_argument('--tag', default='', help='suffix for the written file (e.g. .pkg7)')
    a = ap.parse_args(argv)
    rows = load(a.tsv, a.list)
    if a.list:
        for off, name, unc, comp, ck in rows:
            print('0x%x\t%d\t%d\t%s\t%s' % (off, unc, comp, ck, name))
        print('-- %d record(s)' % len(rows))
        return 0
    if not a.name:
        raise SystemExit('need --name or --list')
    hits = [r for r in rows if r[1] == a.name]
    if not hits:
        raise SystemExit('not in listing: %s' % a.name)
    os.makedirs(a.out or '.', exist_ok=True)
    with open(a.ard, 'rb') as f:
        for k, (off, name, unc, comp, ck) in enumerate(hits):
            blob = fetch(f, off, name, unc, comp)
            dst = os.path.join(a.out or '.', '%s%s%s' % (name, a.tag, '' if len(hits) == 1 else '.%d' % k))
            open(dst, 'wb').write(blob)
            print('0x%x %s -> %s (%d bytes, %r)' % (off, name, dst, len(blob), blob[:4]))
    return 0


if __name__ == '__main__':
    sys.exit(main())
