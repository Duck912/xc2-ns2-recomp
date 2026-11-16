# SPDX-License-Identifier: GPL-3.0-or-later
r"""The frame-counter census report: what one visit adds to a counter site at 30 Hz and at 60 fps.

    python fps_census.py --at30 work\fps_census\census-30.txt --at60 work\fps_census\census-60.txt ^
        --sites xc2\build\fps_sites.txt --out work\fps_census\report.txt --csv work\fps_census\report.csv [--all]

A census file (xc2_boot.cpp fps_census) starts with "updates <n>" and has one line per site:
    <site hex> <visits> <fields> <consec> <same> <later> <off> <upds> <mean |d|> <min d> <max d>
The site list is nxrecomp/fps.py's (store func load op kind field value).

A frame-locked counter adds as much per visit at 60 fps as at 30 Hz (ratio = mean30 / mean60 ~ 1): the game counts it
once a frame whatever the frame rate, so it runs twice as fast at 60 fps. A time-scaled one (x += step) adds half as much
when the frames are shorter (ratio ~ 2): it keeps real time already. vpu = (visits60 / updates60) / (visits30 / updates30)
tells whether the site runs once a frame (~1) or on a clock of its own (~0.5: a loader or audio thread the frame rate does
not speed up). A "per-update" site repeats in 30 or more updates, half or more of them consecutive.

Ported from Bayonetta 3 recomp (Witch Time) tools/wtbuild/src/fps_census.rs, GPL-3.0-or-later. --selftest runs that file's
own test data and checks the exact lines it expects.
"""
import argparse
import sys


# ----------------------------------------------------------------------------------------------------------- the files
def fmt_g(v, prec=4):
    """Rust's {:.*} style short form: 1, 0.5, 1e-05, 1.235e+05 (Python's %g already matches)."""
    return '%.*g' % (prec, v)


class Site:
    __slots__ = ('visits', 'fields', 'consec', 'same', 'later', 'off', 'upds', 'mean', 'lo', 'hi')


def read_census(path):
    """-> (clock updates, [(site, Site)] in file order; a repeated site keeps its first place and takes the last values)."""
    with open(path, encoding='latin-1') as f:
        lines = f.read().split('\n')
    head = lines[0].split() if lines else []
    if len(head) < 2:
        raise ValueError('%s: no "updates <n>" line' % path)
    try:
        updates = int(head[1])
    except ValueError:
        raise ValueError('%s: the first line is not "updates <n>": %r' % (path, lines[0]))
    out, at = [], {}
    for ln, line in enumerate(lines[1:], 2):
        a = line.split()
        if len(a) < 11:
            continue
        try:
            n = [int(a[i]) for i in (1, 2, 3, 4, 5, 6)]
            f3 = [float(a[i]) for i in (8, 9, 10)]
        except ValueError:
            raise ValueError('%s:%d: %r is not a number' % (path, ln, line))
        s = Site()
        s.visits, s.fields, s.consec, s.same, s.later, s.off = n
        s.upds = int(a[7])
        s.mean, s.lo, s.hi = f3
        if a[0] in at:
            out[at[a[0]]][1] = s
        else:
            at[a[0]] = len(out)
            out.append([a[0], s])
    return updates, out


def read_sites(path):
    """fps_sites.txt -> {store hex: (func, kind, field)}."""
    out = {}
    with open(path, encoding='latin-1') as f:
        for line in f:
            t = line.split('#', 1)[0].split()
            if len(t) == 7:
                out[t[0]] = (t[1], t[4], t[5])
    return out


# ----------------------------------------------------------------------------------------------------------- the report
def report(at30, at60, site_list, every=False, max_off=100.0, min_visits=0):
    """-> (lines, rows): the report lines and every row's fields, for the CSV."""
    u30, s30 = read_census(at30)
    u60, s60 = read_census(at60)
    m30 = dict(s30)
    info = read_sites(site_list)
    classes = [('frame-locked', 0), ('own clock', 0), ('scaled', 0), ('other', 0)]
    rows = []
    for site, h in s60:
        b = m30.get(site)
        if b is None:
            continue
        if b.mean == 0.0 or h.mean == 0.0:
            continue
        ratio = b.mean / h.mean
        rep = h.consec + h.same + h.later
        cq = h.consec / float(rep if rep > 0 else 1)
        # visits per clock update, 60 over 30: about 1 for code that runs every frame, about 0.5 for code on a thread of
        # its own clock (the guest's 60 Hz vsync, audio), which the frame rate does not speed up
        vpu = (h.visits / float(u60 if u60 > 0 else 1)) / max(b.visits / float(u30 if u30 > 0 else 1), 1e-12)
        if 0.8 <= ratio <= 1.25:
            cls = 'frame-locked'
        elif ratio >= 1.5:
            cls = 'scaled'
        else:
            cls = 'other'
        if cls == 'frame-locked' and vpu < 0.75:
            cls = 'own clock'
        per_update = rep >= 30 and cq >= 0.5
        if per_update:
            for i, c in enumerate(classes):
                if c[0] == cls:
                    classes[i] = (c[0], c[1] + 1)
        func, kind, field = info.get(site, ('?', '?', '?'))
        rows.append({'site': site, 'func': func, 'kind': kind, 'field': field, 'cls': cls, 'per_update': per_update,
                     'visits30': b.visits, 'visits60': h.visits, 'fields': h.fields, 'consec': h.consec, 'same': h.same,
                     'later': h.later, 'off': h.off, 'upds': h.upds, 'cq': cq, 'vpu': vpu,
                     'mean30': b.mean, 'mean60': h.mean, 'ratio': ratio, 'lo': h.lo, 'hi': h.hi})
    rows.sort(key=lambda r: -r['visits60'])
    both = sum(1 for s, _ in s60 if s in m30)
    out = ['# clock updates: %d at 30, %d above; sites seen in both: %d' % (u30, u60, both)]
    for r in rows:
        if not (every or (r['cls'] == 'frame-locked' and r['per_update'])):
            continue
        # the listing filters (the class counts above are over every site): off-thread spin loops (off ~ 100 %) are not
        # counters of the frame, and a site seen a handful of times carries no mean worth reading
        if 100.0 * r['off'] / float(r['visits60'] if r['visits60'] > 0 else 1) > max_off or r['visits60'] < min_visits:
            continue
        out.append('{} {} {:<9} {:<14} | {:>8} {:>5} {:>5.1f} {:>5.1f} {:>4.2f} | {:>10} {:>10} {:>5.2f} | {}, {}'.format(
            r['site'], r['func'], r['kind'], r['field'], r['visits60'], r['fields'], 100.0 * r['cq'],
            100.0 * r['off'] / float(r['visits60'] if r['visits60'] > 0 else 1), r['vpu'],
            fmt_g(r['mean30']), fmt_g(r['mean60']), r['ratio'], fmt_g(r['lo']), fmt_g(r['hi'])))
    out.append('# per-update sites (30+ repeat visits, half or more in consecutive updates): ' +
               ', '.join('%s %d' % c for c in classes))
    return out, rows


CSV_COLUMNS = ['site', 'func', 'kind', 'field', 'class', 'per_update', 'visits30', 'visits60', 'vpu', 'cq',
               'consec60', 'same60', 'later60', 'fields60', 'upds60', 'off60',
               'mean30', 'mean60', 'ratio', 'min60', 'max60']


def write_csv(path, rows):
    with open(path, 'w', encoding='ascii', newline='\n') as f:
        f.write(','.join(CSV_COLUMNS) + '\n')
        for r in rows:
            f.write(','.join([
                r['site'], r['func'], r['kind'], r['field'], r['cls'], '1' if r['per_update'] else '0',
                str(r['visits30']), str(r['visits60']), fmt_g(r['vpu']), fmt_g(r['cq']),
                str(r['consec']), str(r['same']), str(r['later']), str(r['fields']), str(r['upds']), str(r['off']),
                fmt_g(r['mean30']), fmt_g(r['mean60']), fmt_g(r['ratio']), fmt_g(r['lo']), fmt_g(r['hi'])]) + '\n')


# ----------------------------------------------------------------------------------------------------------- the tests
AT30 = """updates 100
a1 1000 10 900 50 50 0 100 0.5 0.1 1
b2 1000 10 900 50 50 0 100 0.5 0.1 1
c3 1000 10 900 50 50 0 100 1 0.1 2
d4 1000 10 900 50 50 0 100 0.65 0.1 1
e5 10 1 5 0 0 0 10 1 1 1
f6 10 1 5 0 0 0 10 1 1 1
g7 10 1 5 0 0 0 10 1 1 1
"""
AT60 = """updates 200
a1 1 1 1 1 1 1 1 1 1 1
b2 1000 10 900 50 50 0 100 0.5 0.1 1
c3 2000 10 1800 100 100 1500 200 0.5 -1 2
d4 2000 10 1800 100 100 0 200 0.5 0.1 1
e5 20 1 10 0 0 0 20 1 1 1
g7 10 1 5 0 0 0 10 0 0 0
h8 10 1 5 0 0 0 10 1 1 1
short line
a1 2000 12 1800 100 100 500 200 0.5 1e-05 123456
"""
SITES = """# store func load op kind field value
a1 f_a 0 0 f32+reg [x19+16] s0
c3 f_c 0 0 int32+1 [x8+0] w8
"""


def selftest():
    """fps_census.rs's own test data: one site per class, a1 twice in the 60 file (first place, last values)."""
    import os
    import tempfile
    d = tempfile.mkdtemp(prefix='fps_census_')
    p30, p60, ps = (os.path.join(d, n) for n in ('at30.txt', 'at60.txt', 'sites.txt'))
    for p, t in ((p30, AT30), (p60, AT60), (ps, SITES)):
        with open(p, 'w', encoding='ascii', newline='\n') as f:
            f.write(t)
    head = '# clock updates: 100 at 30, 200 above; sites seen in both: 6'
    # the reference's own lines, the field column only shorter by the space fps.rs's parser needed ("[x19+16]", not "[x19 +16]")
    a1 = 'a1 f_a f32+reg   [x19+16]       |     2000    12  90.0  25.0 1.00 |        0.5        0.5  1.00 | 1e-05, 1.235e+05'
    tail = ('# per-update sites (30+ repeat visits, half or more in consecutive updates): '
            'frame-locked 1, own clock 1, scaled 1, other 1')
    got, _ = report(p30, p60, ps, False)
    assert got == [head, a1, tail], got
    got, _ = report(p30, p60, ps, True)
    assert got == [head, a1,
                   'c3 f_c int32+1   [x8+0]         |     2000    10  90.0  75.0 1.00 |          1        0.5  2.00 | -1, 2',
                   'd4 ? ?         ?              |     2000    10  90.0   0.0 1.00 |       0.65        0.5  1.30 | 0.1, 1',
                   'b2 ? ?         ?              |     1000    10  90.0   0.0 0.50 |        0.5        0.5  1.00 | 0.1, 1',
                   'e5 ? ?         ?              |       20     1 100.0   0.0 1.00 |          1          1  1.00 | 1, 1',
                   tail], got
    print('selftest: ok')
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description='Frame-counter census report: 30 Hz against 60 fps.')
    ap.add_argument('--at30', help='the census file of the 30 Hz run (census-30.txt)')
    ap.add_argument('--at60', help='the census file of the 60 fps run (census-60.txt)')
    ap.add_argument('--sites', help='the site list (xc2\\build\\fps_sites.txt)')
    ap.add_argument('--out', help='write the report here (report.txt)')
    ap.add_argument('--csv', help='write every site here (report.csv)')
    ap.add_argument('--all', action='store_true', help='list every site, not only the frame-locked per-update ones')
    ap.add_argument('--max-off', type=float, default=100.0,
                    help='list only sites with at most this percent of their visits on another thread (default 100: all)')
    ap.add_argument('--min-visits', type=int, default=0,
                    help='list only sites visited at least this often in the 60 fps run (default 0: all)')
    ap.add_argument('--selftest', action='store_true', help='run the ported test data and exit')
    a = ap.parse_args(argv)
    if a.selftest:
        return selftest()
    for k in ('at30', 'at60', 'sites'):
        if not getattr(a, k):
            ap.error('--%s is required' % k)
    lines, rows = report(a.at30, a.at60, a.sites, a.all, a.max_off, a.min_visits)
    text = '\n'.join(lines) + '\n'
    if a.out:
        with open(a.out, 'w', encoding='ascii', newline='\n') as f:
            f.write(text)
    else:
        sys.stdout.write(text)
    if a.csv:
        write_csv(a.csv, rows)
    print('%d rows, %d in the report' % (len(rows), len(lines) - 2), file=sys.stderr)
    return 0


if __name__ == '__main__':
    sys.exit(main())
