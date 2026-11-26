"""Decompile shader blocks from the dumped NVN blocks to Vulkan GLSL (spirv_harness --glsl).

  python glsl.py <hash> [<hash> ...]        writes <dump>/glsl/<hash>.glsl and prints the path
  python glsl.py --find 57bdd1a0            lists the dump dirs that hold a hash prefix

The harness turns `-o x.spv --glsl` into GLSL *text* in that file (Path.ChangeExtension is skipped
because -o names the extension explicitly), so the output is written as .glsl here.
"""
import glob
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORK = ROOT / "work"
HARNESS = ROOT / "third_party/fefw-recomp/tools/shaders/build/bin/Release/net10.0/spirv_harness.dll"
DOTNET = r"dotnet"
OUT = WORK / "shader_glsl"


def dumps():
    return sorted(WORK.glob("shader_dump*"))


def find(h):
    for d in dumps():
        c = d / ("code_%s.bin" % h)
        k = d / ("ctrl_%s.bin" % h)
        if c.exists() and k.exists():
            return c, k
    return None, None


def main():
    a = sys.argv[1:]
    if a and a[0] == "--find":
        pre = a[1]
        for d in dumps():
            for c in d.glob("code_%s*.bin" % pre):
                print(d, c.name)
        return
    OUT.mkdir(exist_ok=True)
    for h in a:
        c, k = find(h)
        if not c:
            print("!! %s: no dumped block" % h)
            continue
        out = OUT / (h + ".glsl")
        r = subprocess.run([DOTNET, str(HARNESS), str(c), str(k), "-o", str(out), "--glsl"],
                           capture_output=True, text=True)
        msg = (r.stdout + r.stderr).strip().splitlines()
        print("%s -> %s  (%s)" % (h, out if out.exists() else "FAILED", msg[-1] if msg else ""))
        for m in msg[:-1]:
            print("    " + m)


if __name__ == "__main__":
    main()
