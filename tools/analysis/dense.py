import re
LOG = r'.\xc2\build\boot\tt_live.log'
lines = open(LOG, errors='replace').readlines()
def nums(s): return [float(x) for x in re.findall(r'-?\d+\.?\d*(?:e[-+]?\d+)?', s)]
rows = []
for l in lines:
    if 'snapshot after draw' not in l: continue
    m = re.search(r'snapshot after draw (\d+): (t\d+):', l)
    if not m: continue
    mm = re.search(r'min (.*?) max (.*?) mean (.*)$', l.split('->',1)[-1])
    if not mm: continue
    mn, mx, me = nums(mm.group(1)), nums(mm.group(2)), nums(mm.group(3))
    if len(mn) >= 3:
        rows.append((int(m.group(1)), m.group(2), mn[0], mx[0], me[0]))
seen = {}
for n, t, mn, mx, me in rows:
    seen.setdefault((n, t), (mn, mx, me))
print('t13 across the early draws:')
for (n, t), (mn, mx, me) in sorted(seen.items()):
    if t != 't13': continue
    print('  #%-4d  min %8.4f  max %8.4f  mean %8.4f' % (n, mn, mx, me))
print()
print('all targets at a few early points:')
for (n, t), (mn, mx, me) in sorted(seen.items()):
    if n in (2, 20, 60, 100, 118) :
        print('  #%-4d %-6s min %8.4f max %8.4f mean %8.4f' % (n, t, mn, mx, me))
