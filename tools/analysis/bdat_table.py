# SPDX-License-Identifier: GPL-3.0-or-later
"""Read a BDAT v2 table: list its columns, or print one row.

    python tools/analysis/bdat_table.py --file work/bdat/common.bdat.pkg7 --table 0x22580 --columns
    python tools/analysis/bdat_table.py --file ... --table 0x22580 --row 526 --column ArtsDrWpnType
    python tools/analysis/bdat_table.py --file ... --table 0x22580 --row 526 --raw

Layout (from the lifted main: Bdat::getVal / getIdTop / getIdCount / getMember / bdatRefresh):
    +0x00 'BDAT'   +0x04 u16 version  +0x06 u16 descriptor-area end  +0x08 u16 row size
    +0x0a u16 bucket offset           +0x0c u16 bucket count         +0x0e u16 row data offset
    +0x10 u16 row count               +0x12 u16 first row id        +0x18 u32 table size
    bucket[i] = u16 at +bucketOff+2i -> member entry offset (0 = empty)
    member entry: u16 valueDescOff, u16 nextEntryOff, u16 nameOff
    value descriptor: u8 tag(=1), u8 type, u16 value offset inside the row
    name: NUL-terminated ASCII at table+nameOff
    hash for the bucket index: h = 7*h + c over min(strlen, 8) chars, idx = h % bucketCount
"""
import argparse
import struct
import sys

TYPE_SIZE = {1: 4, 2: 1, 3: 2, 4: 1, 5: 1, 6: 2, 7: 1, 8: 1}


def u16(d, o):
    return struct.unpack_from('<H', d, o)[0]


def u32(d, o):
    return struct.unpack_from('<I', d, o)[0]


class Table:
    def __init__(self, d, base):
        self.d = d
        self.base = base
        assert d[base:base + 4] == b'BDAT', 'no BDAT at 0x%x' % base
        self.version = u16(d, base + 4)
        self.row_size = u16(d, base + 8)
        self.bucket_off = u16(d, base + 0x0a)
        self.bucket_n = u16(d, base + 0x0c)
        self.row_off = u16(d, base + 0x0e)
        self.count = u16(d, base + 0x10)
        self.top = u16(d, base + 0x12)
        self.size = u32(d, base + 0x18)

    def columns(self):
        out = {}
        for i in range(self.bucket_n):
            e = u16(self.d, self.base + self.bucket_off + 2 * i)
            seen = 0
            while e and seen < 64:
                seen += 1
                p = self.base + e
                desc, nxt, name_off = u16(self.d, p), u16(self.d, p + 2), u16(self.d, p + 4)
                end = self.d.find(b'\0', self.base + name_off, self.base + name_off + 96)
                name = self.d[self.base + name_off:end].decode('ascii', 'replace')
                tag = self.d[self.base + desc]
                typ = self.d[self.base + desc + 1]
                val_off = u16(self.d, self.base + desc + 2)
                out[name] = (typ, val_off, tag)
                e = nxt
        return out

    def row_ptr(self, row_id):
        idx = row_id - self.top
        if idx < 0 or idx >= self.count:
            raise SystemExit('row %d outside [%d, %d)' % (row_id, self.top, self.top + self.count))
        return self.base + self.row_off + self.row_size * idx

    def value(self, row_id, col):
        typ, val_off, tag = self.columns()[col]
        p = self.row_ptr(row_id) + val_off
        n = TYPE_SIZE.get(typ, 1)
        raw = self.d[p:p + n]
        return int.from_bytes(raw, 'little'), typ, val_off


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--file', required=True)
    ap.add_argument('--table', type=lambda s: int(s, 0), required=True)
    ap.add_argument('--columns', action='store_true')
    ap.add_argument('--row', type=int, default=None)
    ap.add_argument('--column', default=None)
    ap.add_argument('--raw', action='store_true')
    a = ap.parse_args(argv)
    d = open(a.file, 'rb').read()
    t = Table(d, a.table)
    print('BDAT v%d at 0x%x: rows %d..%d (%d), row size %d, row data +0x%x, size %d, %d buckets'
          % (t.version, t.base, t.top, t.top + t.count - 1, t.count, t.row_size, t.row_off, t.size, t.bucket_n))
    cols = t.columns()
    if a.columns:
        print('%d column(s):' % len(cols))
        for name, (typ, off, tag) in sorted(cols.items(), key=lambda kv: kv[1][1]):
            print('  +0x%-4x type %d  %s' % (off, typ, name))
    if a.row is not None:
        p = t.row_ptr(a.row)
        if a.raw or not a.column:
            print('row %d at 0x%x:' % (a.row, p))
            for k in range(0, t.row_size, 16):
                print('  %04x: %s' % (k, d[p + k:p + k + 16].hex(' ')))
        if a.column:
            v, typ, off = t.value(a.row, a.column)
            print('row %d  %s = %d (0x%x)  type %d at row+0x%x' % (a.row, a.column, v, v, typ, off))
    return 0


if __name__ == '__main__':
    sys.exit(main())
