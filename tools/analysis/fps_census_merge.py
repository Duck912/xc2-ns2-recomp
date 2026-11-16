# Run from the repo root (the repository root): every path below is relative to it.
import csv

rows = {}
for path, tag in ((r'work\fps_census\report.csv', 'idle'), (r'work\fps_census\report2.csv', 'menu')):
    with open(path, encoding='ascii') as f:
        for r in csv.DictReader(f):
            if r['class'] != 'frame-locked' or r['per_update'] != '1':
                continue
            prev = rows.get(r['site'])
            if prev is None:
                r = dict(r)
                r['scene'] = tag
                r['seen'] = 1
                rows[r['site']] = r
            else:
                prev['scene'] = '+'.join(sorted(set(prev['scene'].split('+') + [tag])))
                prev['seen'] += 1
                if int(r['visits60']) > int(prev['visits60']):
                    scene, seen = prev['scene'], prev['seen']
                    prev.update(r)
                    prev['scene'], prev['seen'] = scene, seen

out = sorted(rows.values(), key=lambda r: -int(r['visits60']))
fmt = '{:<10} {:<10} {:<10} {:<12} {:>8} {:>5} {:>7} {:>6} {:>10} {:>10} {:>6} {:>10} {:>10}  {}'
hdr = fmt.format('site', 'func', 'kind', 'field', 'visits', 'objs', 'consec%', 'vpu', 'mean30', 'mean60', 'ratio',
                 'min60', 'max60', 'scene')
lines = ['# Frame-locked counter sites of XC2 (one visit moves the field the same amount at 30 Hz and at 60 fps:',
         '# at 60 fps the counter runs twice as fast as the game it counts). Union of two scenes:',
         '#   idle = standing at the First Low Orbit Station save point (work\\fps_census\\report.csv)',
         '#   menu = the same plus the in-game menu, tab switches, a walk and a camera turn (report2.csv)',
         '# frame-locked and per-update (>= 30 repeat visits, half or more in consecutive updates), sorted by visits.',
         '# objs = distinct fields the site touched; consec% = share of visits that landed in the next update;',
         '# vpu = visits per update at 60 fps / at 30 (about 1 = runs once a frame; about 0.5 = a clock of its own).',
         hdr]
for r in out:
    rep = max(1, int(r['consec60']) + int(r['same60']) + int(r['later60']))
    cq = float(r['consec60']) / rep
    lines.append(fmt.format(r['site'], r['func'], r['kind'], r['field'], r['visits60'], r['fields60'],
                            '%.1f' % (100.0 * cq), r['vpu'], r['mean30'], r['mean60'], r['ratio'],
                            r['min60'], r['max60'], r['scene']))
open(r'work\fps_census\frame-locked.txt', 'w', encoding='ascii', newline='\n').write('\n'.join(lines) + '\n')
cols = ['site', 'func', 'kind', 'field', 'visits60', 'fields60', 'consec60', 'same60', 'later60', 'vpu', 'cq',
        'mean30', 'mean60', 'ratio', 'min60', 'max60', 'seen', 'scene']
with open(r'work\fps_census\frame-locked.csv', 'w', encoding='ascii', newline='\n') as f:
    w = csv.writer(f, lineterminator='\n')
    w.writerow(cols)
    for r in out:
        rep = max(1, int(r['consec60']) + int(r['same60']) + int(r['later60']))
        r = dict(r)
        r['cq'] = '%.3f' % (float(r['consec60']) / rep)
        w.writerow([r[c] for c in cols])
print('%d sites' % len(out))

