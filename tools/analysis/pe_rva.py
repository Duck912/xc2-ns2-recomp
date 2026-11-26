#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
r"""Resolve RVAs in a PE (x64) to the function that contains them.

    python tools\analysis\pe_rva.py <dll|exe> <rva> [<rva> ...]

For each RVA it prints the .pdata (exception directory) function that contains it -- start, end and the offset inside
it -- plus the nearest export below it. That is enough to turn a crash log line such as

    crash:   in amdvlk64.dll+0x4acf06

into "inside the function at +0x4aca0b, offset 0x4fb", which is the first step of reading the faulting instruction
(HANDOVER 95 used exactly this on amdvlk64.dll). RVAs are what the runtime prints as "module+offset"; no PDB needed.
"""

import bisect
import struct
import sys


class PE:
    def __init__(self, path):
        self.path = path
        self.data = open(path, 'rb').read()
        d = self.data
        e_lfanew = struct.unpack_from('<I', d, 0x3c)[0]
        if d[e_lfanew:e_lfanew + 4] != b'PE\0\0':
            raise SystemExit('%s: not a PE' % path)
        coff = e_lfanew + 4
        nsec, = struct.unpack_from('<H', d, coff + 2)
        optsize, = struct.unpack_from('<H', d, coff + 16)
        opt = coff + 20
        magic, = struct.unpack_from('<H', d, opt)
        self.is64 = magic == 0x20b
        self.image_base = struct.unpack_from('<Q', d, opt + 24)[0] if self.is64 else struct.unpack_from('<I', d, opt + 28)[0]
        ddir = opt + (112 if self.is64 else 96)
        ndirs, = struct.unpack_from('<I', d, ddir - 4)
        self.dirs = [struct.unpack_from('<II', d, ddir + i * 8) for i in range(min(ndirs, 16))]
        so = opt + optsize
        self.sections = []
        for i in range(nsec):
            o = so + i * 40
            name = d[o:o + 8].rstrip(b'\0').decode('latin1')
            vsize, vaddr, rawsize, rawptr = struct.unpack_from('<IIII', d, o + 8)
            self.sections.append((name, vaddr, vsize, rawptr, rawsize))

    def section_of(self, rva):
        for name, vaddr, vsize, rawptr, rawsize in self.sections:
            if vaddr <= rva < vaddr + max(vsize, rawsize):
                return name
        return '?'

    def off(self, rva):
        for name, vaddr, vsize, rawptr, rawsize in self.sections:
            if vaddr <= rva < vaddr + max(vsize, rawsize):
                o = rawptr + (rva - vaddr)
                return o if o < len(self.data) else None
        return None

    def read(self, rva, n):
        o = self.off(rva)
        return None if o is None else self.data[o:o + n]

    def functions(self):
        rva, size = self.dirs[3]                       # IMAGE_DIRECTORY_ENTRY_EXCEPTION (.pdata)
        if not rva or not size:
            return []
        o = self.off(rva)
        out = [struct.unpack_from('<III', self.data, o + i * 12) for i in range(size // 12)] if o is not None else []
        out.sort()
        return out

    def exports(self):
        rva, size = self.dirs[0]                       # IMAGE_DIRECTORY_ENTRY_EXPORT
        if not rva or not size:
            return []
        o = self.off(rva)
        if o is None:
            return []
        d = self.data
        nfun, nnam = struct.unpack_from('<II', d, o + 20)
        aof, anf, aon = struct.unpack_from('<III', d, o + 28)
        fo, no, oo = self.off(aof), self.off(anf), self.off(aon)
        if None in (fo, no, oo):
            return []
        out = []
        for i in range(nnam):
            nrva, = struct.unpack_from('<I', d, no + i * 4)
            oi, = struct.unpack_from('<H', d, oo + i * 2)
            frva, = struct.unpack_from('<I', d, fo + oi * 4)
            nm = self.read(nrva, 256)
            if nm is None:
                continue
            out.append((frva, nm.split(b'\0')[0].decode('latin1', 'backslashreplace')))
        out.sort()
        return out


def main(argv):
    if len(argv) < 3:
        print(__doc__)
        return 2
    pe = PE(argv[1])
    funcs = pe.functions()
    exports = pe.exports()
    starts = [f[0] for f in funcs]
    print('%s: image base 0x%x, %d sections, %d .pdata functions, %d exports'
          % (argv[1], pe.image_base, len(pe.sections), len(funcs), len(exports)))
    for a in argv[2:]:
        rva = int(a, 0)
        print('--- rva 0x%x (%s) ---' % (rva, pe.section_of(rva)))
        i = bisect.bisect_right(starts, rva) - 1
        if 0 <= i < len(funcs) and funcs[i][0] <= rva < funcs[i][1]:
            b, e, _unwind = funcs[i]
            print('  in function 0x%x .. 0x%x (size 0x%x), offset +0x%x' % (b, e, e - b, rva - b))
        elif 0 <= i < len(funcs) and rva - funcs[i][0] < 0x2000:
            print('  past the end of the function at 0x%x (this is a return address, i.e. the call site)' % funcs[i][0])
        else:
            print('  not inside any .pdata function')
        below = [x for x in exports if x[0] <= rva]
        above = [x for x in exports if x[0] > rva]
        if below:
            print('  nearest export below:  %s at 0x%x (+0x%x)' % (below[-1][1], below[-1][0], rva - below[-1][0]))
        if above:
            print('  next export:           %s at 0x%x' % (above[0][1], above[0][0]))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
