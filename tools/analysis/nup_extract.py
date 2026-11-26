# SPDX-License-Identifier: GPL-3.0-or-later
"""List / verify / extract the packages of a .nup (Switch 2 package).

Layout (per github.com/a55uka/nup): 0x80 superblock, TOC (package 0x40, dir 0x18, file 0x50,
u32 children, string pool), absolute file extents.

    package record (0x40 B): +0x00 u32 title-id low, +0x04 u32 title-id high,
        +0x08 u32 ROOT dir (its children are `exefs/` and/or `romfs/`), +0x0c u32 control dir,
        +0x10 u32 romfs dir, +0x14 u32 version, +0x18 u8 kind (0 = base, 2 = add-on content)
    file record (0x50 B): +0x00 u32 name offset, +0x04 u32 name length (into the string pool),
        +0x08 u64 size (decompressed), +0x10 u64 file offset, +0x18 u64 stored (compressed) size,
        +0x20 32 B SHA-256 of the DECOMPRESSED content, +0x40 u8 codec (0 = stored, 1 = zstd)

NOTE: the exefs lives under the ROOT dir (+0x08), not under the romfs dir (+0x10). Reading +0x10
only is what made an earlier pass report that the nup carried no exefs at all.

    python tools\\analysis\\nup_extract.py --nup FILE --list
    python tools\\analysis\\nup_extract.py --nup FILE --files 0
    python tools\\analysis\\nup_extract.py --nup FILE --verify [--pkg 7] [--only bf2.]
    python tools\\analysis\\nup_extract.py --nup FILE --pkg 0 --part exefs --out DIR
    python tools\\analysis\\nup_extract.py --nup FILE --pkg 7 --out DIR [--only bf2.arh] [--max-gb N]

--verify checks every extent (offset + stored inside the file) and every SHA-256, so a truncated
or bit-rotted archive is caught before the game is blamed. zstandard is imported only where it is
needed, so --list and --files work on a machine without it.
"""
import argparse
import hashlib
import os
import struct
import sys
import time

CHUNK = 8 << 20


def load(path):
    f = open(path, "rb")
    sb = f.read(0x80)
    if sb[:4] != b"NUP\x01":
        sys.exit("not a .nup: %r" % sb[:4])
    toc_off, toc_size = struct.unpack_from("<QQ", sb, 0x08)
    f.seek(toc_off)
    t = f.read(toc_size)
    if t[:4] != b"TOC\x01":
        sys.exit("bad TOC")
    pkgs = struct.unpack_from("<I", t, 4)[0]
    dirs, files = struct.unpack_from("<QQ", t, 8)
    pool_at, pool_n = struct.unpack_from("<QQ", t, 0x18)
    dir_at = 0x30 + 0x40 * pkgs
    file_at = dir_at + 0x18 * dirs
    child_at = file_at + 0x50 * files
    return dict(f=f, t=t, pkgs=pkgs, dirs=dirs, files=files, pool_at=pool_at, dir_at=dir_at,
                file_at=file_at, child_at=child_at)


def name(m, rec):
    off, ln = struct.unpack_from("<II", m["t"], rec)
    return m["t"][m["pool_at"] + off: m["pool_at"] + off + ln].decode("utf-8", "replace")


def kids(m, d):
    rec = m['dir_at'] + 0x18 * d
    first, cnt = struct.unpack_from("<II", m["t"], rec + 8)
    return [struct.unpack_from("<I", m["t"], m["child_at"] + 4 * s)[0] for s in range(first, first + cnt)]


def pkg_rec(m, i):
    r = 0x30 + 0x40 * i
    lo, hi, root, ctl, rom, ver = struct.unpack_from("<IIIIII", m["t"], r)
    return dict(lo=lo, hi=hi, root=root, ctl=ctl, romfs=rom, ver=ver, kind=m["t"][r + 0x18])


def subdir(m, root, want):
    """Index of the child dir of `root` whose name is `want`, or None."""
    if root == 0xFFFFFFFF:
        return None
    for k in kids(m, root):
        if k < m['dirs'] and name(m, m['dir_at'] + 0x18 * k) == want:
            return k
    return None


def start_dir(m, i, part):
    rec = pkg_rec(m, i)
    if part == 'root':
        return rec['root']
    if part == 'exefs':
        return subdir(m, rec['root'], 'exefs')
    return subdir(m, rec['root'], 'romfs') if rec['romfs'] == 0xFFFFFFFF else rec['romfs']


def walk(m, d, prefix, out, only):
    for k in kids(m, d):
        if k < m['dirs']:
            sub = prefix + name(m, m['dir_at'] + 0x18 * k) + '/'
            if only and not (sub.startswith(only) or only.startswith(sub)):
                continue
            walk(m, k, sub, out, only)
        else:
            fr = m['file_at'] + 0x50 * (k - m['dirs'])
            p = prefix + name(m, fr)
            if only and not p.startswith(only):
                continue
            size, off, stored = struct.unpack_from("<QQQ", m["t"], fr + 8)
            codec = m["t"][fr + 0x40]
            digest = m["t"][fr + 0x20:fr + 0x40]
            out.append((p, size, off, codec, stored, digest))


def sha_region(f, off, stored):
    """SHA-256 over `stored` bytes at `off`, streamed."""
    h = hashlib.sha256()
    f.seek(off)
    left = stored
    while left:
        b = f.read(min(CHUNK, left))
        if not b:
            return None
        h.update(b)
        left -= len(b)
    return h.digest()


def verify_file(f, size, off, codec, stored, digest):
    """(ok, note): extent, then the SHA-256 of the decompressed content."""
    total = os.fstat(f.fileno()).st_size
    if off + stored > total:
        return False, "extent runs past the end (%d + %d > %d)" % (off, stored, total)
    if codec == 0:
        if stored != size:
            return False, "stored %d != size %d for a stored record" % (stored, size)
        got = sha_region(f, off, stored)
        if got is None:
            return False, "short read"
        return (got == digest), ("ok" if got == digest else "sha256 %s != %s" % (got.hex()[:16], digest.hex()[:16]))
    if codec == 1:
        import zstandard
        f.seek(off)
        blob = f.read(stored)
        if len(blob) != stored:
            return False, "short read"
        try:
            data = zstandard.ZstdDecompressor().decompress(blob, max_output_size=size or 0)
        except Exception as e:
            return False, "zstd: %s" % e
        if size and len(data) != size:
            return False, "inflated %d != size %d" % (len(data), size)
        got = hashlib.sha256(data).digest()
        return (got == digest), ("ok" if got == digest else "sha256 %s != %s" % (got.hex()[:16], digest.hex()[:16]))
    return False, "unknown codec %d" % codec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--nup', required=True)
    ap.add_argument('--pkg', type=int, default=-1)
    ap.add_argument('--part', choices=['romfs', 'exefs', 'root'], default='romfs')
    ap.add_argument('--out')
    ap.add_argument('--only', default='')
    ap.add_argument('--list', action='store_true')
    ap.add_argument('--files', type=int, default=None, metavar='PKG')
    ap.add_argument('--verify', action='store_true')
    ap.add_argument('--max-gb', type=float, default=0.0)
    a = ap.parse_args()
    m = load(a.nup)
    if a.list or (a.pkg < 0 and not a.verify and a.files is None):
        print("%-4s %-5s %-14s %-14s %8s %10s %10s" % ("pkg", "kind", "title id", "dirs", "files", "GB", "version"))
        for i in range(m['pkgs']):
            r = pkg_rec(m, i)
            out = []
            if r['root'] != 0xFFFFFFFF:
                walk(m, r["root"], "", out, a.only)
            has = []
            for part in ('exefs', 'romfs'):
                if subdir(m, r['root'], part) is not None:
                    has.append(part)
            tid = "%016X" % ((r["hi"] << 32) | r["lo"])
            print("%-4d %-5d %-14s %-14s %8d %10.2f %10d" % (i, r["kind"], tid, "+".join(has) or "-", len(out),
                  sum(s for _, s, _, _, _, _ in out) / 1e9, r['ver']))
        return 0
    if a.files is not None:
        d = start_dir(m, a.files, a.part)
        if d is None:
            sys.exit("pkg %d has no %s" % (a.files, a.part))
        out = []
        walk(m, d, "", out, a.only)
        for p, s, o, c, st, dg in sorted(out, key=lambda r: -r[1]):
            print("%-70s %14d off 0x%-12x codec %d stored %d" % (p, s, o, c, st))
        print("-- %d file(s), %.2f GB" % (len(out), sum(s for _, s, _, _, _, _ in out) / 1e9))
        return 0
    if a.verify:
        targets = range(m['pkgs']) if a.pkg < 0 else [a.pkg]
        bad = 0
        for i in targets:
            r = pkg_rec(m, i)
            if r['root'] == 0xFFFFFFFF:
                continue
            out = []
            walk(m, r["root"], "", out, a.only)
            t0 = time.time()
            ok = 0
            gb = 0.0
            for p, s, o, c, st, dg in out:
                good, note = verify_file(m['f'], s, o, c, st, dg)
                gb += st / 1e9
                if good:
                    ok += 1
                else:
                    bad += 1
                    print("  FAIL pkg %d %s: %s" % (i, p, note))
            print("pkg %d (kind %d, ver %d): %d/%d ok, %.2f GB read, %.1f s"
                  % (i, r['kind'], r['ver'], ok, len(out), gb, time.time() - t0))
        return 1 if bad else 0
    d = start_dir(m, a.pkg, a.part)
    if d is None or not a.out:
        sys.exit("package %d has no %s, or no --out" % (a.pkg, a.part))
    out = []
    walk(m, d, "", out, a.only)
    total = sum(s for _, s, _, _, _, _ in out)
    print("pkg %d %s: %d files, %.2f GB -> %s" % (a.pkg, a.part, len(out), total / 1e9, a.out))
    f = m['f']
    done = 0
    t0 = time.time()
    dec = None
    for p, size, off, codec, stored, digest in out:
        dst = os.path.join(a.out, p.replace('/', os.sep))
        if os.path.exists(dst) and os.path.getsize(dst) == size:
            done += size
            continue
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        f.seek(off)
        if codec == 1:
            if dec is None:
                import zstandard
                dec = zstandard.ZstdDecompressor()
            raw = f.read(stored)
            data = dec.decompress(raw, max_output_size=size if size else 0)
            if size and len(data) != size:
                sys.exit("size mismatch at %s: %d != %d" % (p, len(data), size))
            if hashlib.sha256(data).digest() != digest:
                sys.exit("sha256 mismatch at %s" % p)
            with open(dst, 'wb') as g:
                g.write(data)
        else:
            h = hashlib.sha256()
            left = size
            with open(dst, 'wb') as g:
                while left:
                    b = f.read(min(CHUNK, left))
                    if not b:
                        sys.exit("short read at %s" % p)
                    h.update(b)
                    g.write(b)
                    left -= len(b)
            if h.digest() != digest:
                sys.exit("sha256 mismatch at %s" % p)
        done += size
        if a.max_gb and done >= a.max_gb * 1e9:
            print("  stop at %.2f GB (--max-gb)" % (done / 1e9))
            break
    print("done %.2f GB in %.1f s" % (done / 1e9, time.time() - t0))
    return 0


if __name__ == '__main__':
    sys.exit(main())
