import numpy as np, os
b = r'.\xc2\build\boot'
def dec(path, w=1280, h=720):
    a = np.frombuffer(open(path,'rb').read(), dtype=np.uint32).reshape(h, w)
    out = []
    for shift, bits, mbits in ((0,11,6),(11,11,6),(22,10,5)):
        v = (a >> shift) & ((1<<bits)-1)
        e = ((v >> mbits) & 0x1F).astype(np.float64); m = (v & ((1<<mbits)-1)).astype(np.float64)
        out.append(np.where(e == 0, (m/(1<<mbits))*2.0**-14, (1.0 + m/(1<<mbits))*np.power(2.0, e-15.0)).astype(np.float32))
    return np.stack(out, axis=2)
on = dec(os.path.join(b,'ABon_t13.bin')); off = dec(os.path.join(b,'ABoff_t13.bin'))
def l(x): return 0.2126*x[:,:,0] + 0.7152*x[:,:,1] + 0.0722*x[:,:,2]
lo, lf = l(on), l(off)
print('fog on : lum mean %.4f  med %.4f  p95 %.3f' % (lo.mean(), np.median(lo), np.percentile(lo,95)))
print('fog off: lum mean %.4f  med %.4f  p95 %.3f' % (lf.mean(), np.median(lf), np.percentile(lf,95)))
d = lo - lf
print('lum(on) - lum(off): mean %+.4f  med %+.4f  p5 %+.4f  p95 %+.4f' % (d.mean(), np.median(d), np.percentile(d,5), np.percentile(d,95)))
print('  darker with fog (< -0.02): %.1f%% of pixels   brighter (> +0.02): %.1f%%   |d|<=0.02: %.1f%%' % (100*np.mean(d < -0.02), 100*np.mean(d > 0.02), 100*np.mean(np.abs(d) <= 0.02)))
def amap(v, label, scale=1.0, lo_=None, hi_=None):
    print('  ' + label)
    hh, ww = v.shape
    for r in range(16):
        s = ''
        for c in range(48):
            val = np.median(v[r*hh//16:(r+1)*hh//16, c*ww//48:(c+1)*ww//48]) * scale
            s += '#' if val < -0.10 else ('+' if val < -0.02 else ('-' if val > 0.02 else '.'))
        print('    |'+s+'|')
amap(d, 'where the fog makes the picture DARKER (# = < -0.10, + = -0.02..-0.10)')
