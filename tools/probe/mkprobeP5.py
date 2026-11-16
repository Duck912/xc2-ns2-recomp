import os
HERE = os.path.dirname(os.path.abspath(__file__))
base = open(os.path.join(HERE, 'froxel_fixC.frag'), encoding='utf-8').read()
text = base
def sub1(old, new):
    global text
    assert text.count(old) == 1, (old[:70], text.count(old))
    text = text.replace(old, new)

sub1('        float _948 = clamp(_3230, 0.0, 1.0);\n',
     '        float dbg_dirx = _49.x * inversesqrt(fma(_49.z, _49.z, fma(_49.y, _49.y, _49.x * _49.x)));\n'
     '        float dbg_k = (dbg_dirx > 0.15) ? 1.0 : ((dbg_dirx < -0.15) ? 0.10 : 0.30);\n'
     '        float _948 = clamp(_3230, 0.0, 1.0) * dbg_k;\n')
open(os.path.join(HERE, 'froxel_p5.frag'), 'w', encoding='utf-8').write(text)
print('ok')