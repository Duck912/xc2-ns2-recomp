# SPDX-License-Identifier: GPL-3.0-or-later
"""Scan every .bdat record of an archive listing for a BDAT table header signature.

    python tools/analysis/bdat_scan.py --ard <bf2.ard> --tsv <listing.tsv> --top 526 [--count 245]

BDAT v2 header (verified against Bdat::getVal / getIdTop / getIdCount in the lifted main):
    +0x00 'BDAT'      +0x04 u16 version   +0x06 u16 header size   +0x08 u16 row size
    +0x0a u16 ?       +0x0c u16 col count +0x0e u16 row data off  +0x10 u16 row count
    +0x12 u16 id top  +0x14 u16 ?         +0x16 u16 ?             +0x18 u32 table size
A .bdat file is either a single table or a container {u32 n, u32 total, u32 offsets[n]}.
"""
import argparse
import csv
import os
import struct
import sys
import zlib

HDR = 0x30


def records(tsv, pat):
    out = []
    with open(tsv, encoding='utf-8') as f:
        r = csv.reader(f, delimiter='\t')
        next(r)
        for row in r:
            if len(row) >= 5 and row[1].endswith(pat):
                out.append((int(row[0]), row[1], int(row[2]), int(row[3])))
    return out


def fetch(f, off, unc, comp):
    f.seek(off)
    if f.read(4) != b'xbc1':
        return None
    f.seek(off + HDR)
    blob = f.read(comp)
    if len(blob) != comp:
        return None
    try:
        out = zlib.decompress(blob)
    except zlib.error:
        return None
    return out if len(out) == unc else None


def tables(d):
    """Yield (offset, name_hint) for every BDAT table inside a .bdat image."""
    if d[:4] == b'BDAT':
        yield 0
        return
    if len(d) < 8:
        return
    n, total = struct.unpack_from('<II', d, 0)
    if not (0 < n < 100000) or total != len(d) or 8 + n * 4 > len(d):
        return
    for i in range(n):
        o = struct.unpack_from('<I', d, 8 + i * 4)[0]
        if o + 0x1c <= len(d) and d[o:o + 4] == b'BDAT':
            yield o


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--ard', required=True)
    ap.add_argument('--tsv', required=True)
    ap.add_argument('--top', type=lambda s: int(s, 0), default=None)
    ap.add_argument('--count', type=lambda s: int(s, 0), default=None)
    ap.add_argument('--ext', default='.bdat')
    a = ap.parse_args(argv)
    recs = records(a.tsv, a.ext)
    print('%d %s record(s) in the listing' % (len(recs), a.ext))
    seen = 0
    tables_n = 0
    hits = []
    with open(a.ard, 'rb') as f:
        for off, name, unc, comp in recs:
            d = fetch(f, off, unc, comp)
            if d is None:
                continue
            seen += 1
            for t in tables(d):
                tables_n += 1
                top = struct.unpack_from('<H', d, t + 0x12)[0]
                cnt = struct.unpack_from('<H', d, t + 0x10)[0]
                if a.top is not None and top != a.top:
                    continue
                if a.count is not None and cnt != a.count:
                    continue
                hits.append((name, off, t, cnt, top))
    print('decoded %d image(s), %d BDAT table(s)' % (seen, tables_n))
    for name, off, t, cnt, top in hits:
        print('  %s  rec 0x%x  table +0x%x  count=%d top=%d' % (name, off, t, cnt, top))
    print('-- %d hit(s)' % len(hits))
    return 0


if __name__ == '__main__':
    sys.exit(main())
