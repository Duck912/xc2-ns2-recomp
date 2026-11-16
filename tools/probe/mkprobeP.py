import os
import re, os
HERE = os.path.dirname(os.path.abspath(__file__))
base = open(os.path.join(HERE, 'froxel_fixC.frag'), encoding='utf-8').read()

def variant(name, subs):
    text = base
    for old, new in subs:
        assert text.count(old) == 1, (name, old[:60], text.count(old))
        text = text.replace(old, new)
    open(os.path.join(HERE, name), 'w', encoding='utf-8').write(text)
    print('wrote', name)

DECL = '    bool _880 = false;\n'
DECL_NEW = ('    float dbg_a = 0.0, dbg_b = 0.0, dbg_c = 0.0;\n'
            '    bool dbg_first = true;\n'
            '    bool _880 = false;\n')
ANCHOR = '        float _948 = clamp(_3230, 0.0, 1.0);\n'
assert base.count(ANCHOR) == 1

variant('froxel_p1.frag', [
    (DECL, DECL_NEW),
    (ANCHOR, ANCHOR + '        if (dbg_first) { dbg_a = _946; dbg_b = _948; dbg_c = _872; dbg_first = false; }\n'),
    ('    _54.x = _3632;\n', '    _54.x = dbg_a;\n'),
    ('    _54.y = _3651;\n', '    _54.y = dbg_b;\n'),
    ('    _54.z = _3670;\n', '    _54.z = dbg_c;\n'),
])

variant('froxel_p2.frag', [
    ('    _54.x = _3632;\n', '    _54.x = _1042;\n'),
    ('    _54.y = _3651;\n', '    _54.y = _1044;\n'),
    ('    _54.z = _3670;\n', '    _54.z = _1046;\n'),
    ('    _54.w = _998;\n', '    _54.w = 1.0;\n'),
])