import re, os, glob, time
LOG = r'.\xc2\build\boot\tt_live.log'
lines = open(LOG, errors='replace').readlines()
starts = [i for i, l in enumerate(lines) if 'nvn.trace' in l and re.search(r'draw #1 vs', l)]
print('traces in this run:', len(starts))
def block(a, b):
    recs = []; cur = None
    for l in lines[a:b]:
        if 'nvn.trace' not in l: continue
        m = re.search(r'draw #(\d+) vs (\S+) fs (\S+) gs (\S+) mode (\d+) idx (\d+) \| rt (.*?) ds (.*?) \| blend (\d+)', l)
        if m:
            cur = dict(n=int(m.group(1)), vs=m.group(2)[:8], fs=m.group(3)[:8], mode=int(m.group(5)), rt=m.group(7), c=None, b=None, cull=None)
            recs.append(cur); continue
        mm = re.search(r'bounds: (.*)$', l)
        if mm and cur is not None: cur['b'] = mm.group(1); continue
        mm = re.search(r'indexed: count (\d+)', l)
        if mm and cur is not None: cur['c'] = int(mm.group(1)); continue
        mm = re.search(r'cull (\d+)', l)
        if mm and cur is not None: cur['cull'] = int(mm.group(1)); continue
    return recs
bl = []
for k, s in enumerate(starts):
    e = starts[k+1] if k+1 < len(starts) else len(lines)
    r = block(s, e); bl.append(r); print('  #%d: %d draws' % (k, len(r)))
if len(bl) >= 2:
    A, B = bl[-3] if len(bl) >= 3 else bl[0], bl[-1]
    ka = {}; kb = {}
    for r in A: ka[(r['fs'], r['c'])] = ka.get((r['fs'], r['c']), 0) + 1
    for r in B: kb[(r['fs'], r['c'])] = kb.get((r['fs'], r['c']), 0) + 1
    print()
    print('draws (fs,count) only in the FIRST of the compared frames:')
    for k in sorted(set(ka) - set(kb)): print('   fs %-9s count %-6s  x%d' % (k[0], k[1], ka[k]))
    print('draws only in the LAST:')
    for k in sorted(set(kb) - set(ka)): print('   fs %-9s count %-6s  x%d' % (k[0], k[1], kb[k]))
