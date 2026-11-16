import os
HERE = os.path.dirname(os.path.abspath(__file__))
base = open(os.path.join(HERE, 'froxel_fixC.frag'), encoding='utf-8').read()
text = base
def sub1(old, new):
    global text
    assert text.count(old) == 1, (old[:70], text.count(old))
    text = text.replace(old, new)

# 1) light term: use the Y component of the sun direction (0.996) instead of Z (-0.089)
sub1('    float _178 = fma(_1277, fp_c1_1._m0[0].z, -_172);\n',
     '    float _178 = fma(_1277, fp_c1_1._m0[0].y, -_172);\n')
# 2) density: keep it below saturation so (1 - _944) can vary
sub1('        float _948 = clamp(_3230, 0.0, 1.0);\n',
     '        float _948 = clamp(_3230, 0.0, 1.0) * 0.30;\n')
sub1('            precise float _3185 = fma(_876, _942, fp_c4_1._m0[2].w) * fp_c4_1._m0[2].z;\n',
     '            precise float _3185 = fma(_876, _942, fp_c4_1._m0[2].w) * fp_c4_1._m0[2].z * 0.30;\n')
open(os.path.join(HERE, 'froxel_p14.frag'), 'w', encoding='utf-8').write(text)
print('ok')