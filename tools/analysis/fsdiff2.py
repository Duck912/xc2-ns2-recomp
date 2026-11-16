import re
UP = r'.\xc2\build\boot\tt_live_prev9.log'
DN = r'.\xc2\build\boot\tt_live.log'
def draws(path):
    lines = open(path, errors='replace').readlines()
    starts = [i for i, l in enumerate(lines) if 'nvn.trace' in l and re.search(r'draw #1 vs', l)]
    if not starts: return []
    s = starts[-1]
    out = []
    for l in lines[s:]:
        if 'nvn.trace' not in l: continue
        m = re.search(r'draw #(\d+) vs (\S+) fs (\S+) gs', l)
        if m: out.append((m.group(2)[:8], m.group(3)[:8]))
    return out
up = draws(UP); dn = draws(DN)
print('up draws', len(up), 'down draws', len(dn))
fu = {}; fd = {}
for vs, fs in up: fu[fs] = fu.get(fs, 0) + 1
for vs, fs in dn: fd[fs] = fd.get(fs, 0) + 1
print('fs counts that differ (plate vs sea):')
for k in sorted(set(fu) | set(fd), key=lambda k: -abs(fu.get(k,0)-fd.get(k,0))):
    if fu.get(k,0) != fd.get(k,0):
        print('  fs %-9s  plate %3d   sea %3d' % (k, fu.get(k,0), fd.get(k,0)))
