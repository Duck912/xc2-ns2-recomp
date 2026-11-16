import os
HERE = os.path.dirname(os.path.abspath(__file__))
base = open(os.path.join(HERE, 'froxel_fixC.frag'), encoding='utf-8').read()
text = base
def sub1(old, new):
    global text
    assert text.count(old) == 1, (old[:70], text.count(old))
    text = text.replace(old, new)

sub1('        float _946 = _3213;\n',
     '        float _946 = _3213;\n'
     '        {\n'
     '            float dxx2 = _49.x * inversesqrt(fma(_49.z, _49.z, fma(_49.y, _49.y, _49.x * _49.x)));\n'
     '            if (dxx2 > 0.0) { _946 = clamp(_3202, 0.0, 1.0) * _724 * clamp(1.0 - _872, 0.0, 1.0); }\n'
     '        }\n')
open(os.path.join(HERE, 'froxel_p7.frag'), 'w', encoding='utf-8').write(text)
print('ok')