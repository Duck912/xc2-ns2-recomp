import os
import re, os, json
HERE = os.path.dirname(os.path.abspath(__file__))
refl = json.load(open(os.path.join(HERE, 'comp.reflect.json'), encoding='utf-8'))
setof = {}
for t in refl['textures']: setof[t['binding']] = t['set']
for u in refl['ubos']: setof[u['binding']] = u['set']
base = open(os.path.join(HERE, 'comp.frag'), encoding='utf-8').read()
text = re.sub(r"layout\(binding = (\d+)", lambda m: "layout(set = %d, binding = %s" % (setof[int(m.group(1))], m.group(1)), base)
open(os.path.join(HERE, "comp_setbase.frag"), "w", encoding="utf-8").write(text)
old = "    gl_FragDepth = intBitsToFloat(_188);\n"
assert text.count(old) == 1
probe = text.replace(old, "    gl_FragDepth = 1.0;   // probe: never occlude anything drawn later\n")
open(os.path.join(HERE, "comp_depthoff.frag"), "w", encoding="utf-8").write(probe)
print("ok")