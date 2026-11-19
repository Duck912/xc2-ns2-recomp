# Run from the repo root (the repository root): every path below is relative to it.
import csv, os, re, sys
root = r'xc2\build\lift-census\main'
active = set()
for l in open(r'xc2\build\fps_counters.txt', encoding='ascii'):
    if l.strip() and not l.startswith('#'):
        active.add(l.split()[0])
rows = [r for r in csv.DictReader(open(r'work\fps_census\frame-locked.csv', encoding='ascii'))]
rest = [r for r in rows if r['site'] not in active]
print('%d frame-locked, %d converted, %d to read' % (len(rows), len(active), len(rest)))
want = {r['site']: r for r in rest}
pat = re.compile(r'fps_census\(0x([0-9a-f]+)ULL')
found = {}
for name in sorted(os.listdir(root)):
    if not name.endswith('.cpp'):
        continue
    with open(os.path.join(root, name), encoding='latin-1') as f:
        lines = f.read().split('\n')
    for i, line in enumerate(lines):
        m = pat.search(line)
        if m and m.group(1) in want and m.group(1) not in found:
            found[m.group(1)] = (name, i, lines)
def classify(r, after):
    txt = '\n'.join(after)
    tags = []
    if re.search(r'\* \(int64_t\)\(int32_t\)', txt) or re.search(r'\) << \d', txt) or re.search(r'\* c->x\[\d+\]\)', txt):
        tags.append('INDEX')
    if re.search(r'while|umulh|udiv|sdiv', txt):
        tags.append('ARITH')
    if re.search(r'wr(8|16|32|64)\(a, 0U?\)', txt) or re.search(r'a, 0U\);', txt):
        tags.append('RESET0')
    if re.search(r'c->x\[0\] = \(uint64_t\)\(0ULL \| c->x\[\d+\]\)', txt):
        tags.append('CALLARG')
    if 'fps_ci' in txt or 'fps_fs' in txt or 'fps_cf' in txt:
        tags.append('CONVERTED')
    return tags
out = []
buckets = {}
for s, r in sorted(want.items(), key=lambda kv: -int(kv[1]['visits60'])):
    h = found.get(s)
    tags = []
    if h:
        name, i, lines = h
        tags = classify(r, lines[i + 1:i + 8])
    buckets.setdefault(','.join(tags) or '-', 0)
    buckets[','.join(tags) or '-'] += 1
    out.append('%-10s %-10s %-12s objs=%-5s cq=%-5s mean=%s/%s tags=%s' % (s, r['kind'], r['field'], r['fields60'], r['cq'], r['mean30'], r['mean60'], ','.join(tags) or '-'))
    if h:
        name, i, lines = h
        for k in range(max(0, i - 3), min(len(lines), i + 4)):
            out.append('    %s %s' % ('->' if k == i else '  ', lines[k].strip()[:170]))
        out.append('')
open(r'work\fps_census\remaining-context.txt', 'w', encoding='utf-8', newline='\n').write('\n'.join(out) + '\n')
print('tags:', dict(sorted(buckets.items(), key=lambda kv: -kv[1])))
