import os
HERE = os.path.dirname(os.path.abspath(__file__))
base = open(os.path.join(HERE, 'froxel_fixC.frag'), encoding='utf-8').read()
text = base
def sub1(old, new):
    global text
    assert text.count(old) == 1, (old[:70], text.count(old))
    text = text.replace(old, new)

sub1('    _54.w = _998;\n',
     '    _54 = vec4(clamp(_1018 * 0.001, 0.0, 1.0), clamp(_988 * 0.001, 0.0, 1.0), clamp(_468 * 0.001, 0.0, 1.0), 1.0);\n')
open(os.path.join(HERE, 'froxel_p10.frag'), 'w', encoding='utf-8').write(text)
print('ok')