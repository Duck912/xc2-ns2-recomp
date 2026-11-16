import re
log = r".\xc2\build\boot\tt_hot.log"
lines = open(log, "r", encoding="utf-8", errors="replace").read().splitlines()
want = {"2649526f56d9b5b6":"froxel", "cc3eac68e6dd44ce":"comp", "57bdd1a067bf74f4":"cards"}
rows = []
for l in lines:
    m = re.search(r"draw #(\d+) vs ([0-9a-f]+) fs ([0-9a-f]+) gs (\S+) mode (\d+) idx (\d+) \| (.*)$", l)
    if not m:
        continue
    h = m.group(3)
    if h not in want:
        continue
    rest = m.group(7)
    rt = re.search(r"rt ([^|]+)", rest)
    rows.append((int(m.group(1)), want[h], (rt.group(1).strip() if rt else "")[:110]))
print("hits:", len(rows))
for r in rows:
    print("  #%-4d %-7s %s" % r)