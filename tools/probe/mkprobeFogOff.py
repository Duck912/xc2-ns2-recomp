import os
HERE = os.path.dirname(os.path.abspath(__file__))
base = open(os.path.join(HERE, 'froxel_fixC.frag'), encoding='utf-8').read()
text = base
old = "    _54.w = _998;\n"
assert text.count(old) == 1
text = text.replace(old, "    _54 = vec4(0.0, 0.0, 0.0, 0.0);   // fog fully off: draw nothing\n")
open(os.path.join(HERE, "froxel_fogoff.frag"), "w", encoding="utf-8").write(text)
print("ok")