import os

import re, os, json
HERE = os.path.dirname(os.path.abspath(__file__))
refl = json.load(open(os.path.join(HERE, 'froxel.reflect.json'), encoding='utf-8'))
setof = {}
for t in refl['textures']: setof[t['binding']] = t['set']
for u in refl['ubos']: setof[u['binding']] = u['set']
text = open(os.path.join(HERE, 'froxel.frag'), encoding='utf-8').read()
text = re.sub(r'layout\(binding = (\d+)', lambda m: 'layout(set = %d, binding = %s' % (setof[int(m.group(1))], m.group(1)), text)
def sub1(old, new):
    global text
    assert text.count(old) == 1, ('anchor', old[:70], text.count(old))
    text = text.replace(old, new)
sub1('    bool _248 = _192;\n', '    bool _248 = true;\n')
sub1('    float _170 = _95;\n', '    float _170 = 0.0;\n')
open(os.path.join(HERE, 'froxel_fixC.frag'), 'w', encoding='utf-8').write(text)
print('ok')
