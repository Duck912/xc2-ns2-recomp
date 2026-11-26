# SPDX-License-Identifier: GPL-3.0-or-later
"""Split an NSO into work/nso/<mod>.{text,rodata,data}.bin, without lz4.

    python tools/analysis/nso_seg.py main sdk subsdk0 rtld

The DSH python ships no lz4 module, so the LZ4 block format is decoded here directly (~40 lines),
which keeps the tooling free of a pip install.
"""
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
EXEFS = os.path.join(ROOT, 'xc2', 'game', 'xc2ns2')
NSO = os.path.join(ROOT, 'work', 'nso')


def lz4_block(src, usize):
    """Decode one raw LZ4 block (no frame header)."""
    dst = bytearray()
    i = 0
    n = len(src)
    while i < n:
        tok = src[i]
        i += 1
        lit = tok >> 4
        if lit == 15:
            while True:
                b = src[i]
                i += 1
                lit += b
                if b != 255:
                    break
        dst += src[i:i + lit]
        i += lit
        if i >= n:
            break
        off = src[i] | (src[i + 1] << 8)
        i += 2
        if off == 0:
            raise ValueError('bad LZ4 offset 0 at %d' % i)
        ml = tok & 15
        if ml == 15:
            while True:
                b = src[i]
                i += 1
                ml += b
                if b != 255:
                    break
        ml += 4
        start = len(dst) - off
        if start < 0:
            raise ValueError('LZ4 back-reference before start')
        for k in range(ml):
            dst.append(dst[start + k])
    if len(dst) != usize:
        raise ValueError('LZ4 size mismatch: %d != %d' % (len(dst), usize))
    return bytes(dst)


def main(argv):
    os.makedirs(NSO, exist_ok=True)
    for mod in argv or ['main']:
        d = open(os.path.join(EXEFS, mod), 'rb').read()
        flags = struct.unpack_from('<I', d, 12)[0]
        for i, (ho, cso, name) in enumerate(((0x10, 0x60, 'text'), (0x20, 0x64, 'rodata'), (0x30, 0x68, 'data'))):
            foff, moff, size = struct.unpack_from('<III', d, ho)
            csz = struct.unpack_from('<I', d, cso)[0]
            raw = d[foff:foff + csz]
            if flags & (1 << i):
                raw = lz4_block(raw, size)
            out = os.path.join(NSO, '%s.%s.bin' % (mod, name))
            open(out, 'wb').write(raw)
            print('%s %-6s vaddr=0x%-8x size=0x%-8x -> %s' % (mod, name, moff, size, out))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
