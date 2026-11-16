import os
HERE = os.path.dirname(os.path.abspath(__file__))
base = open(os.path.join(HERE, 'froxel_fixC.frag'), encoding='utf-8').read()
text = base
def sub1(old, new):
    global text
    assert text.count(old) == 1, (old[:70], text.count(old))
    text = text.replace(old, new)

sub1('            float _834 = fma(_81, _810, _2786);\n',
     '            float _834 = fma(_81, _810, _2786);\n'
     '            {\n'
     '                float dxx3 = _49.x * inversesqrt(fma(_49.z, _49.z, fma(_49.y, _49.y, _49.x * _49.x)));\n'
     '                if (dxx3 > 0.0) { _834 = (_160 + _81 * _810) * fp_c4_1._m0[2].y; }\n'
     '            }\n')
open(os.path.join(HERE, 'froxel_p9.frag'), 'w', encoding='utf-8').write(text)
print('ok')