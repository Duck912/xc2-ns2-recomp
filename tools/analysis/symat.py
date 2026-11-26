# SPDX-License-Identifier: GPL-3.0-or-later
"""Guest address -> symbol for the XC2 NS2 modules, without lz4.

    python tools/analysis/symat.py 0x71002a870c 2a8800 ...     # resolve (main-relative or absolute)
    python tools/analysis/symat.py --dump main                 # write work/nso/main.sym.tsv

Reads the module's MOD0 / .dynamic / .dynsym straight from the decompressed segment images in
work/nso/<mod>.{text,rodata,data}.bin (see nso_seg.py). The DSH python has no lz4, so this avoids
nxrecomp.nso.nso_info entirely: the segment sizes and vaddrs come from the NSO header, which is not
compressed.
"""
import argparse
import bisect
import os
import struct
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
NSO = os.path.join(ROOT, 'work', 'nso')
EXEFS = os.path.join(ROOT, 'xc2', 'game', 'xc2ns2')
BASES = {'main': 0x7100000000, 'sdk': 0x7500000000, 'subsdk0': 0x7600000000, 'rtld': 0x7700000000}
CXXFILT = [r'C:\Program Files\LLVM\bin\llvm-cxxfilt.exe']  # or whatever 'where llvm-cxxfilt' finds


def segments(mod):
    """[(vaddr, bytes)] for text/rodata/data, from work/nso/<mod>.*.bin (built by nso_seg.py)."""
    d = open(os.path.join(EXEFS, mod), 'rb').read()
    out = []
    for i, (ho, name) in enumerate(((0x10, 'text'), (0x20, 'rodata'), (0x30, 'data'))):
        foff, moff, size = struct.unpack_from('<III', d, ho)
        p = os.path.join(NSO, '%s.%s.bin' % (mod, name))
        if not os.path.exists(p):
            raise SystemExit('missing %s' % p)
        blob = open(p, 'rb').read()
        assert len(blob) == size, '%s: %d != %d' % (p, len(blob), size)
        out.append((moff, blob))
    return out


def dynsyms(mod):
    (tv, text), (rv, ro), (dv, data) = segments(mod)
    mem = bytearray(dv + len(data))
    for v, r in ((tv, text), (rv, ro), (dv, data)):
        mem[v:v + len(r)] = r
    mod0 = struct.unpack_from('<I', text, 4)[0]
    assert mem[mod0:mod0 + 4] == b'MOD0', 'no MOD0 in %s' % mod
    dyn = mod0 + struct.unpack_from('<i', mem, mod0 + 4)[0]
    tags, n = {}, 0
    while True:
        t, v = struct.unpack_from('<qQ', mem, dyn + n * 16)
        n += 1
        if t == 0:
            break
        tags.setdefault(t, v)
    symtab, strtab, strsz = tags[6], tags[5], tags[10]
    nsym = struct.unpack_from('<I', mem, tags[4] + 4)[0] if 4 in tags else (strtab - symtab) // 24
    strb = bytes(mem[strtab:strtab + strsz])
    rows = []
    for i in range(nsym):
        name_off, info_, other, shndx, value, size = struct.unpack_from('<IBBHQQ', mem, symtab + i * 24)
        if shndx == 0 or value == 0:
            continue
        if (info_ & 0xf) not in (0, 1, 2):
            continue
        end = strb.find(b'\0', name_off)
        rows.append((value, size, strb[name_off:end].decode('utf-8', 'replace')))
    rows.sort()
    return rows


def demangle(names):
    exe = next((p for p in CXXFILT if os.path.exists(p)), None)
    if not exe:
        return names
    r = subprocess.run([exe], input='\n'.join(names), capture_output=True, text=True)
    lines = r.stdout.splitlines()
    return lines if len(lines) == len(names) else names


_cache = {}


def table(mod):
    if mod not in _cache:
        rows = dynsyms(mod)
        names = demangle([r[2] for r in rows])
        tab = [(v, s, n) for (v, s, _), n in zip(rows, names)]
        _cache[mod] = (tab, [r[0] for r in tab])
    return _cache[mod]


def lookup(addr):
    for mod, base in BASES.items():
        if not (base <= addr < base + 0x40000000):
            continue
        tab, keys = table(mod)
        i = bisect.bisect_right(keys, addr - base) - 1
        if i < 0:
            return '?'
        v, s, n = tab[i]
        off = addr - base - v
        return '%s!%s+0x%x' % (mod, n[:150] or '?', off) + ('' if off < s or not s else ' (size 0x%x)' % s)
    return '?'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('addrs', nargs='*')
    ap.add_argument('--dump', default=None, help='write work/nso/<mod>.sym.tsv')
    a = ap.parse_args()
    if a.dump:
        tab, _ = table(a.dump)
        p = os.path.join(NSO, a.dump + '.sym.tsv')
        with open(p, 'w', encoding='utf-8') as f:
            for v, s, n in tab:
                f.write('%x\t%x\t%s\n' % (v, s, n.replace('\t', ' ')))
        print('wrote %s (%d symbols)' % (p, len(tab)))
        return 0
    for t in a.addrs:
        v = int(t, 16)
        if v < 0x100000000:
            v += BASES['main']
        print('%012x %s' % (v, lookup(v)))
    return 0


if __name__ == '__main__':
    sys.exit(main())
