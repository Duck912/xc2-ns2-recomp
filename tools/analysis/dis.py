# SPDX-License-Identifier: GPL-3.0-or-later
"""Disassemble a range of a guest module with llvm-objdump.

    python tools/analysis/dis.py 2a870c 2a8a70            # main, module-relative hex
    python tools/analysis/dis.py 0x2a870c 0x2a8a70 --mod sdk
    python tools/analysis/dis.py 2a870c --len 0x364

Input: work/nso/<mod>.text.bin (the decompressed .text; see tools/analysis/nso_seg.py to make it).
The range is wrapped in a minimal ELF (one .text section at address 0) so llvm-objdump -d prints
module-relative addresses, and every `bl`/`b` target is annotated with its symbol when the module's
.dynsym has one (work/nso/<mod>.sym.tsv, written by tools/analysis/symat.py --dump).
"""
import argparse
import os
import struct
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
NSO = os.path.join(ROOT, 'work', 'nso')
LLVM = [r'C:\Program Files\LLVM\bin\llvm-objdump.exe']  # or whatever 'where llvm-objdump' finds


def objdump():
    for p in LLVM:
        if os.path.exists(p):
            return p
    raise SystemExit('llvm-objdump not found (set LLVM_BIN)')


def make_elf(text):
    """Minimal ELF64 (AArch64) with one executable .text at vaddr 0."""
    off = 0x40
    shstr = b'\0.text\0.shstrtab\0'
    shstr_off = off + len(text)
    shstr_off = (shstr_off + 7) & ~7
    shoff = (shstr_off + len(shstr) + 7) & ~7
    eh = b'\x7fELF\x02\x01\x01' + bytes(9) + struct.pack(
        '<HHIQQQIHHHHHH', 1, 183, 1, 0, 0, shoff, 0, 0x40, 0x40, 2, 0x40, 3, 2)
    body = bytearray(eh)
    body += bytes(off - len(body))
    body += text
    body += bytes(shstr_off - len(body))
    body += shstr
    body += bytes(shoff - len(body))
    body += bytes(64)                                                    # SHN_UNDEF
    body += struct.pack('<IIQQQQIIQQ', 1, 1, 6, 0, off, len(text), 0, 0, 16, 0)     # .text
    body += struct.pack('<IIQQQQIIQQ', 7, 3, 0, 0, shstr_off, len(shstr), 0, 0, 1, 0)  # .shstrtab
    return bytes(body)


def load_syms(mod):
    p = os.path.join(NSO, mod + '.sym.tsv')
    if not os.path.exists(p):
        return []
    rows = []
    for line in open(p, encoding='utf-8'):
        a, s, n = line.rstrip('\n').split('\t', 2)
        rows.append((int(a, 16), int(s, 16), n))
    rows.sort()
    return rows


def annotate(line, syms, starts):
    import bisect
    out = []
    for tok in line.split(' '):
        t = tok.strip()
        if t.startswith('0x') and len(t) > 4:
            try:
                a = int(t, 16)
            except ValueError:
                out.append(tok)
                continue
            i = bisect.bisect_right(starts, a) - 1
            if i >= 0 and a - syms[i][0] < syms[i][1] + 0x40000 and syms[i][2]:
                out.append('%s<%s+0x%x>' % (t, syms[i][2], a - syms[i][0]))
                continue
        out.append(tok)
    return ' '.join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('start')
    ap.add_argument('stop', nargs='?')
    ap.add_argument('--mod', default='main')
    ap.add_argument('--len', default=None)
    ap.add_argument('--raw', action='store_true', help='no symbol annotation')
    a = ap.parse_args()
    start = int(a.start, 16)
    stop = int(a.stop, 16) if a.stop else (start + int(a.len, 16) if a.len else start + 0x100)
    p = os.path.join(NSO, a.mod + '.text.bin')
    if not os.path.exists(p):
        raise SystemExit('missing %s (decompress the module first)' % p)
    text = open(p, 'rb').read()
    stop = min(stop, len(text))
    start &= ~3
    elf = make_elf(text)
    tmp = os.path.join(ROOT, 'work', '_tmp', 'dis_%s.elf' % a.mod)
    os.makedirs(os.path.dirname(tmp), exist_ok=True)
    open(tmp, 'wb').write(elf)
    r = subprocess.run([objdump(), '-d', '--no-show-raw-insn', '--triple=aarch64',
                        '--start-address=0x%x' % start, '--stop-address=0x%x' % stop, tmp],
                       capture_output=True, text=True)
    lines = [l for l in r.stdout.splitlines() if l.strip() and not l.startswith('dis_') and not l.endswith(':')]
    if a.raw:
        print('\n'.join(lines))
        return 0
    syms = load_syms(a.mod)
    starts = [s[0] for s in syms]
    import bisect
    # header: which function are we in?
    i = bisect.bisect_right(starts, start) - 1
    if i >= 0:
        print('; %06x in %s +0x%x (size 0x%x)' % (start, syms[i][2] or '?', start - syms[i][0], syms[i][1]))
    for l in lines:
        print(annotate(l, syms, starts))
    return 0


if __name__ == '__main__':
    sys.exit(main())
