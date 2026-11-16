"""Query an NVN trace log: per-draw targets, shaders, sampled textures, uniforms.

  python trace_query.py <log> --list                one line per draw (rt, ds, vs, fs, #tex)
  python trace_query.py <log> --draw 320            everything the trace printed for one draw
  python trace_query.py <log> --texfmt BPTC         draws that sample a texture format
  python trace_query.py <log> --rt t13             draws that render into t13
  python trace_query.py <log> --group              draws grouped by (rt set, vs, fs)
"""
import re
import sys
import collections

DRAW = re.compile(r"draw #(\d+) vs (\S+) fs (\S+) gs (\S+) mode (\d+) idx (\d+)(.*)$")
TEX = re.compile(r"\s+(tex|image) set(\d+) b(\d+) (\S+) -> (.*)$")
TEXD = re.compile(r"t(\d+):(\S+) (\d+)x(\d+)x(\d+)")
UBO = re.compile(r"\s+(vs|fs) ubo(\d+) ([0-9a-f]+)/(\d+)(.*)$")
RTM = re.compile(r"\s+rt(\d+) t(\d+) mem (\S+)")


def parse(path):
    draws = []
    cur = None
    for line in open(path, errors="replace"):
        i = line.find("nvn.trace:")
        if i < 0:
            continue
        body = line[i + len("nvn.trace:"):].rstrip("\n")
        m = DRAW.search(body)
        if m:
            cur = dict(no=int(m.group(1)), vs=m.group(2), fs=m.group(3), gs=m.group(4), mode=int(m.group(5)),
                       idx=int(m.group(6)), rest=m.group(7), tex=[], texel=[], ubo={}, lines=[])
            seg = body.split("|")
            cur["rt"] = [s.strip() for s in seg[1].split("+")] if len(seg) > 1 else []
            cur["rawrt"] = seg[1].strip() if len(seg) > 1 else ""
            cur["rawds"] = seg[2].strip() if len(seg) > 2 else ""
            draws.append(cur)
            continue
        if cur is None:
            continue
        cur["lines"].append(body.strip())
        t = TEX.search(body)
        if t:
            d = TEXD.search(t.group(5))
            ent = (int(t.group(3)), t.group(4), (int(d.group(1)), d.group(2), d.group(3), d.group(4)) if d else None, t.group(5))
            (cur["texel"] if t.group(1) == "texel" else cur["tex"]).append(ent)
            continue
        u = UBO.search(body)
        if u:
            cur["ubo"]["%s%d" % (u.group(1), int(u.group(2)))] = (u.group(3), int(u.group(4)), u.group(5).strip())
            continue
        r = RTM.search(body)
        if r:
            cur.setdefault("rtmem", []).append((int(r.group(2)), r.group(3)))
    return draws


def texids(d):
    return [t[2][0] for t in d["tex"] if t[2]]


def main():
    ds = parse(sys.argv[1])
    a = sys.argv[2:]
    print("%d draws" % len(ds))
    if "--group" in a:
        g = collections.Counter()
        first = {}
        for d in ds:
            k = (d["rawrt"].replace(" | ", "+"), d["rawds"].split(" L1")[0], d["vs"], d["fs"])
            g[k] += 1
            first.setdefault(k, d["no"])
        for (rt, dsv, vs, fs), n in g.most_common():
            print("%3d  first #%-4d rt %-46s | ds %-30s | vs %s fs %s" % (n, first[(rt, dsv, vs, fs)], rt[:46], dsv[:30], vs, fs))
        return
    if "--draw" in a:
        want = int(a[a.index("--draw") + 1])
        for d in ds:
            if d["no"] == want:
                print("#%d vs %s fs %s mode %d idx %d" % (d["no"], d["vs"], d["fs"], d["mode"], d["idx"]))
                print("  rt: %s" % d["rawrt"])
                print("  ds: %s" % d["rawds"])
                for ln in d["lines"]:
                    print("  " + ln[:400])
        return
    if "--rt" in a:
        want = a[a.index("--rt") + 1]
        want = want[1:] if want[:1] == "t" else want
        for d in ds:
            if any(("t" + want) in x for x in d["rt"]) or ("t" + want) in d["rawrt"]:
                print("#%-4d rt %-44s ds %-26s vs %s fs %s mode %d idx %d tex %s" % (
                    d["no"], d["rawrt"][:44], d["rawds"][:26], d["vs"], d["fs"], d["mode"], d["idx"],
                    ",".join("%d:%s" % (t[2][0], t[2][1]) for t in d["tex"] if t[2])))
        return
    if "--texfmt" in a:
        want = a[a.index("--texfmt") + 1].upper()
        for d in ds:
            hit = [t for t in d["tex"] if t[2] and want in t[2][1].upper()]
            if hit:
                print("#%-4d rt %-40s vs %s fs %s mode %d idx %d | %s" % (
                    d["no"], d["rawrt"][:40], d["vs"], d["fs"], d["mode"], d["idx"],
                    ",".join("%d:%s" % (t[2][0], t[2][1]) for t in hit)))
        return
    # default: one line per draw
    for d in ds:
        print("#%-4d rt %-44s ds %-26s vs %s fs %s mode %d idx %d ntex %d" % (
            d["no"], d["rawrt"][:44], d["rawds"][:26], d["vs"], d["fs"], d["mode"], d["idx"], len(d["tex"])))


if __name__ == "__main__":
    main()
