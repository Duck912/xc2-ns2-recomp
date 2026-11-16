# Run from the repo root (the repository root): every path below is relative to it.
import csv, sys
new = {r['site']: r for r in csv.DictReader(open(sys.argv[1], encoding='ascii'))}
old = {r['site']: r for r in csv.DictReader(open(r'work\fps_census\report.csv', encoding='ascii'))}
sites = [l.split('#')[0].split()[0] for l in open(r'xc2\scripts\fps_counters.txt', encoding='ascii') if l.strip() and not l.startswith('#')]
ci = [s for s in sites if 'int' in open(r'xc2\scripts\fps_counters.txt', encoding='ascii').read().split(s)[0].split('\n')[-1]]
bad = 0
for s in sites:
    n = new.get(s)
    if not n:
        print(s, 'MISSING'); continue
    if 'int' in n['kind']:
        good = abs(float(n['mean60']) - 0.5) < 0.06
    else:
        good = abs(float(n['mean60']) - 0.01667) < 0.002
    if not good: bad += 1
    print('%-10s %-12s %-10s %-10s %-10s %-12s -> %-10s %s' % (s, n['kind'], n['field'], n['mean30'], n['mean60'],
          n['ratio'], n['class'], 'OK' if good else 'CHECK'))
print('not matching the expected signature: %d of %d' % (bad, len(sites)))

