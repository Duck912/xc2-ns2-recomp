import os
HERE = os.path.dirname(os.path.abspath(__file__))
base = open(os.path.join(HERE, 'froxel_fixC.frag'), encoding='utf-8').read()
text = base
def sub1(old, new):
    global text
    assert text.count(old) == 1, (old[:70], text.count(old))
    text = text.replace(old, new)

BLOCK = (
    '    {\n'
    '        float dxx = _1028;\n'
    '        if (dxx > 0.0) { _54 = vec4(_3632, _3651, _3670, _998); }\n'
    '        else { _54 = vec4(0.0, 0.0, 0.0, 0.0); }\n'
    '    }\n')
sub1('    _54.w = _998;\n', BLOCK)
open(os.path.join(HERE, 'froxel_p6.frag'), 'w', encoding='utf-8').write(text)
print('ok')