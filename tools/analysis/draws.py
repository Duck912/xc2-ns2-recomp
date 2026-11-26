import re
LOG = r'.\xc2\build\boot\tt_live.log'
lines = open(LOG, errors='replace').readlines()
# find the last trace block
start = 0
for i, l in enumerate(lines):
    if 'nvn.trace' in l and ('---- frame' in l or 'trace: frame' in l):
        start = i
if start == 0:
    # fall back: the last line containing 'draw #1 '
    for i, l in enumerate(lines):
        if 'nvn.trace' in l and re.search(r'draw #1 vs', l): start = i
print('block starts at line', start)
draws = []
for l in lines[start:]:
    if 'nvn.trace' not in l: continue
    m = re.search(r'draw #(\d+) vs (\S+) fs (\S+) gs (\S+) mode (\d+) idx (\d+) \| rt (.*?) ds (.*?) \| blend (\d+)', l)
    if m: draws.append(dict(n=int(m.group(1)), vs=m.group(2)[:8], fs=m.group(3)[:8], gs=m.group(4), mode=int(m.group(5)), idx=m.group(6), rt=m.group(7)[:120], ds=m.group(8)[:40], blend=int(m.group(9)), vp=None, full=False))
print('draws in block:', len(draws))
# viewports follow the draw line
cur = None
for l in lines[start:]:
    if 'nvn.trace' not in l: continue
    m = re.search(r'draw #(\d+) vs', l)
    if m:
        cur = int(m.group(1)); continue
    m = re.search(r'viewport ([\d.]+),([\d.]+) ([\d.]+)x([\d.]+) \(of (\d+)\)', l)
    if m and cur is not None:
        for d in draws:
            if d['n'] == cur:
                d['vp'] = '%s,%s %sx%s' % (m.group(1), m.group(2), m.group(3), m.group(4))
                d['full'] = (m.group(3).startswith('1280') and m.group(4).startswith('720'))
                break
full = [d for d in draws if d['full']]
print('full-screen draws:', len(full))
for d in full[:40]:
    print('  #%-4d fs %-8s vs %-8s rt %s' % (d['n'], d['fs'], d['vs'], d['rt'][:80]))
