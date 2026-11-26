"""Per-draw table from an NVN trace log (HANDOVER 18.7 step 1).

  python draw_table.py <log>                 # one row per draw
  python draw_table.py <log> --csv out.csv   # the same rows as CSV
  python draw_table.py <log> --by-count      # biggest index count first
  python draw_table.py <log> --rt t8         # only draws that render into t8
  python draw_table.py <log> --fs e17434     # only draws whose fragment shader hash starts like that
  python draw_table.py <log> --vs 8d21be     # ... vertex shader
  python draw_table.py <log> --snaps         # the `snapshot after` lines of the trace
"""
import re
import sys

DRAW = re.compile(r"draw #(\d+) vs (\S+) fs (\S+) gs (\S+) mode (\d+) idx (\d+) \| (.*?) \| blend (\d+) mask (\w+) "
                  r"depth t(\d) w(\d) f(\d+) cull (\d+) ")
IDX = re.compile(r"indexed: count (\d+) type (\d+) instances (\d+) base_vertex (-?\d+) base_instance (\d+)")
ARR = re.compile(r"vertices (\d+) instances (\d+) first (\d+)")
VIEW = re.compile(r"viewport \d+: (\S+ \S+ \S+ \S+) depth \S+\.\.\S+ scissor \d+: (\S+ \S+ \S+ \S+)")
BOUNDS = re.compile(r"bounds: a(\d+)\[([^\]]*)\]")
TEX = re.compile(r"tex set(\d+) b(\d+) (\S+) -> t(\d+):(\S+)")


def parse(path):
    draws, snaps = [], []
    cur = None
    for line in open(path, errors="replace"):
        i = line.find("nvn.trace:")
        if i < 0:
            continue
        body = line[i + len("nvn.trace:"):].rstrip("\n")
        if "snapshot after" in body:
            snaps.append(body.strip())
            continue
        m = DRAW.search(body)
        if m:
            rest = m.group(7)
            k = rest.rfind(" ds ")
            rtp, dsp = (rest[:k], rest[k + 4:]) if k >= 0 else ("", rest)
            rtp = rtp[3:].strip() if rtp.startswith("rt ") else rtp.strip()
            cur = dict(no=int(m.group(1)), vs=m.group(2), fs=m.group(3), gs=m.group(4), mode=int(m.group(5)),
                       rt=[x for x in rtp.split(" | ") if x.strip()], ds=dsp.strip(),
                       blend=int(m.group(8)), mask=m.group(9), dtest=int(m.group(10)), dwrite=int(m.group(11)),
                       dfunc=int(m.group(12)), cull=int(m.group(13)),
                       count=None, inst=None, bv=None, viewport="", scissor="", bounds={}, tex=[], ro=False)
            cur["ro"] = " (ro)" in body
            draws.append(cur)
            continue
        if cur is None:
            continue
        s = body.strip()
        if s.startswith("indexed:"):
            g = IDX.search(s)
            if g:
                cur["count"], cur["inst"], cur["bv"] = int(g.group(1)), int(g.group(3)), int(g.group(4))
        elif s.startswith("vertices "):
            g = ARR.search(s)
            if g:
                cur["count"], cur["inst"] = int(g.group(1)), int(g.group(2))
        elif s.startswith("viewport"):
            g = VIEW.search(s)
            if g:
                cur["viewport"], cur["scissor"] = g.group(1), g.group(2)
        elif s.startswith("bounds:"):
            g = BOUNDS.search(s)
            if g:
                v = []
                for part in g.group(2).split(","):
                    lo, hi = part.split("..")
                    v += [float(lo), float(hi)]
                cur["bounds"][g.group(1)] = v
        elif s.startswith("tex set"):
            g = TEX.search(s)
            if g:
                cur["tex"].append((int(g.group(4)), g.group(5)))
    return draws, snaps


def rts(d):
    return "+".join(t.split(":")[0] for t in d["rt"])


def passes(draws):
    """Consecutive runs of draws that share the same targets: a compact frame timeline."""
    out = []
    for d in draws:
        key = (rts(d), d["ds"].split(" ")[0] if d["ds"] else "-")
        if out and out[-1][0] == key:
            out[-1][2] = d["no"]
            out[-1][3] += 1
        else:
            out.append([key, d["no"], d["no"], 1])
    print("%d passes" % len(out))
    for (rt, ds), a, b, n in out:
        print("  #%-4d..#%-4d  %3d draws  rt %-30s ds %s" % (a, b, n, rt, ds))


def main():
    draws, snaps = parse(sys.argv[1])
    a = sys.argv[2:]
    if "--passes" in a:
        passes(draws)
        return
    if "--snaps" in a:
        print("\n".join(snaps))
        return
    rows = draws
    for opt, key in (("--rt", "rt"), ("--vs", "vs"), ("--fs", "fs")):
        if opt in a:
            want = a[a.index(opt) + 1].lstrip("t")
            rows = [d for d in rows if any(("t" + want) == x.split(":")[0] for x in d["rt"])] if key == "rt" \
                else [d for d in rows if d[key].startswith(want)]
    if "--by-count" in a:
        rows = sorted(rows, key=lambda d: -(d["count"] or 0))
    if "--csv" in a:
        with open(a[a.index("--csv") + 1], "w") as out:
            out.write("draw,count,inst,mode,vs,fs,rt,ds,blend,mask,dtest,dwrite,dfunc,cull,viewport,scissor,ntex,bounds\n")
            for d in rows:
                out.write("%d,%s,%s,%d,%s,%s,\"%s\",\"%s\",%d,%s,%d,%d,%d,%d,\"%s\",\"%s\",%d,\"%s\"\n" % (
                    d["no"], d["count"], d["inst"], d["mode"], d["vs"], d["fs"], rts(d), d["ds"],
                    d["blend"], d["mask"], d["dtest"], d["dwrite"], d["dfunc"], d["cull"],
                    d["viewport"], d["scissor"], len(d["tex"]),
                    " ".join("%s[%s]" % (k, ",".join("%g" % v for v in v2)) for k, v2 in d["bounds"].items())))
        print("%d rows -> %s" % (len(rows), a[a.index("--csv") + 1]))
        return
    print("%d draws" % len(rows))
    for d in rows:
        b = d["bounds"].get("0")
        bb = ("%.3g..%.3g,%.3g..%.3g,%.3g..%.3g" % (b[0], b[1], b[2], b[3], b[4], b[5])) if b else ""
        print("#%-4d c=%-6s i=%-3s m=%d %-16s %-16s rt %-22s ds %-22s b=%d mk=%s d%d%d f%-2d cu%d %-8s ntex %-2d %s%s" % (
            d["no"], d["count"], d["inst"], d["mode"], d["vs"], d["fs"], rts(d)[:22], d["ds"].split(" ")[0][:22],
            d["blend"], d["mask"], d["dtest"], d["dwrite"], d["dfunc"], d["cull"], d["viewport"], len(d["tex"]), bb,
            " (ro)" if d["ro"] else ""))


if __name__ == "__main__":
    main()
