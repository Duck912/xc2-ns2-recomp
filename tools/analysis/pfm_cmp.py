# pfm_cmp.py -- compare two F12 .pfm (linear HDR, tonemap not applied)
#   python pfm_cmp.py a.pfm b.pfm [label]
import sys, struct
import numpy as np

def read_pfm(path):
    with open(path, 'rb') as f:
        hdr = f.readline().strip()
        if hdr not in (b'PF', b'Pf'):
            raise ValueError('not a pfm: %r' % hdr)
        w, h = [int(x) for x in f.readline().split()]
        scale = float(f.readline().strip())
        ch = 3 if hdr == b'PF' else 1
        dt = np.dtype('<f4') if scale < 0 else np.dtype('>f4')
        a = np.frombuffer(f.read(w * h * ch * 4), dtype=dt).reshape(h, w, ch).astype(np.float64)
    return np.flipud(a)          # pfm rows are bottom-up

def rgb(a):
    a = np.clip(a, 0.0, None)
    return a

def lum(a):
    return 0.2126 * a[:, :, 0] + 0.7152 * a[:, :, 1] + 0.0722 * a[:, :, 2]

A = read_pfm(sys.argv[1]); B = read_pfm(sys.argv[2])
label = sys.argv[3] if len(sys.argv) > 3 else ''
ha, wa = A.shape[:2]
if A.shape != B.shape:
    print('shape differs', A.shape, B.shape); sys.exit(1)
la, lb = lum(A), lum(B)
d = la - lb
print('%s  %dx%d' % (label, wa, ha))
print('  lum  A mean %.4f med %.4f p95 %.3f max %.3f' % (la.mean(), np.median(la), np.percentile(la, 95), la.max()))
print('  lum  B mean %.4f med %.4f p95 %.3f max %.3f' % (lb.mean(), np.median(lb), np.percentile(lb, 95), lb.max()))
print('  mean|d| %.4f   mean d %+.4f   p95|d| %.4f   max|d| %.3f' % (np.abs(d).mean(), d.mean(), np.percentile(np.abs(d), 95), np.abs(d).max()))
for t in (0.02, 0.05, 0.10):
    print('  |d| > %.2f : %.1f%% of pixels' % (t, 100.0 * np.mean(np.abs(d) > t)))
# same for the rgb channels (what a colour shift would show)
dr = A - B
print('  per channel mean|d|  r %.4f g %.4f b %.4f' % tuple(np.abs(dr[:, :, i]).mean() for i in range(3)))

m = np.abs(d) > 0.02
if m.sum() > 0:
    ys, xs = np.where(m)
    print('  where |d|>0.02: x %d..%d  y %d..%d  (%.1f%% of the frame)' % (xs.min(), xs.max(), ys.min(), ys.max(), 100.0 * m.mean()))
    print('  sign inside that mask: mean %+.4f  median %+.4f  std %.4f' % (d[m].mean(), np.median(d[m]), d[m].std()))

# 16x48 ascii map of the difference (median per cell)
h, w = d.shape
print('  diff map (cell median, # < -0.10, + = -0.02..-0.10, - = +0.02..+0.10, * = > +0.10, . = |d| <= 0.02)')
for r in range(16):
    s = ''
    for c in range(48):
        v = np.median(d[r * h // 16:(r + 1) * h // 16, c * w // 48:(c + 1) * w // 48])
        s += '#' if v < -0.10 else ('+' if v < -0.02 else ('*' if v > 0.10 else ('-' if v > 0.02 else '.')))
    print('    |' + s + '|')
