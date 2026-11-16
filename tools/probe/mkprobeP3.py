import os
HERE = os.path.dirname(os.path.abspath(__file__))
base = open(os.path.join(HERE, 'froxel_fixC.frag'), encoding='utf-8').read()
text = base
def sub1(old, new):
    global text
    assert text.count(old) == 1, (old[:60], text.count(old))
    text = text.replace(old, new)

sub1('    bool _880 = false;\n',
     '    float dbg_a = 0.0, dbg_b = 0.0, dbg_c = 0.0;\n    bool dbg_first = true;\n    bool _880 = false;\n')
sub1('        float _948 = clamp(_3230, 0.0, 1.0);\n',
     '        float _948 = clamp(_3230, 0.0, 1.0);\n        if (dbg_first) { dbg_a = _946; dbg_b = _3202; dbg_c = _724; dbg_first = false; }\n')
sub1('    _54.w = _998;\n', '    _54 = vec4(dbg_a, dbg_b, dbg_c, 1.0);\n')
open(os.path.join(HERE, 'froxel_p3.frag'), 'w', encoding='utf-8').write(text)
print('ok')