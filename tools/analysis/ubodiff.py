import re
LOG = r'.\xc2\build\boot\tt_live.log'
lines = open(LOG, errors='replace').readlines()
starts = [i for i, l in enumerate(lines) if 'nvn.trace' in l and re.search(r'draw #1 vs', l)]
def block(a, b):
    recs = {}; cur = None
    for l in lines[a:b]:
        if 'nvn.trace' not in l: continue
        m = re.search(r'draw #(\d+) vs (\S+) fs (\S+) gs (\S+) mode (\d+) idx (\d+)', l)
        if m:
            cur = dict(n=int(m.group(1)), vs=m.group(2)[:8], fs=m.group(3)[:8]); recs[cur['n']] = cur; continue
        mm = re.search(r'indexed: count (\d+)', l)
        if mm and cur: cur['c'] = int(mm.group(1)); continue
        mm = re.search(r'(vs|fs) ubo0 [0-9a-f]+/\d+:(.*)$', l)
        if mm and cur and mm.group(1) == 'vs': cur['ubo'] = [int(w,16) for w in mm.group(2).split()]; continue
    return recs
bl = []
for k, s in enumerate(starts):
    e = starts[k+1] if k+1 < len(starts) else len(lines)
    bl.append(block(s, e))
print('traces:', [len(b) for b in bl])
bad, good = bl[0], bl[1]
def sig(r): return (r['vs'], r.get('c'))
gb = {}
for n, r in good.items(): gb.setdefault(sig(r), []).append(r)
rows = []
for n, r in bad.items():
    k = sig(r)
    if k not in gb or not gb[k]: continue
    g = gb[k].pop(0)
    ub, ug = r.get('ubo'), g.get('ubo')
    if not ub or not ug or len(ub) != len(ug): continue
    diffs = [(i, a, b) for i, (a, b) in enumerate(zip(ub, ug)) if a != b]
    rows.append((len(diffs), r['n'], g['n'], r['vs'][:8], r['fs'][:8], diffs[:4]))
rows.sort(reverse=True)
print('draws whose vertex-stage ubo0 differs most (same vs+count signature):')
for d, nb, ng, vs, fs, sample in rows[:12]:
    print('  bad #%-4d good #%-4d vs %s fs %s  %d words differ, e.g. %s' % (nb, ng, vs, fs, d, sample))
