import sys, struct
import numpy as np

def read_pfm(path):
    with open(path,'rb') as f:
        hdr=f.readline().strip()
        w,h=[int(x) for x in f.readline().split()]
        scale=float(f.readline().strip())
        ch=3 if hdr==b'PF' else 1
        dt=np.dtype('<f4') if scale<0 else np.dtype('>f4')
        a=np.frombuffer(f.read(w*h*ch*4),dtype=dt).reshape(h,w,ch).astype(np.float64)
    return np.flipud(a)

a = read_pfm(sys.argv[1])
h,w,_ = a.shape
print('shape', a.shape)
print('column profile (band y 470..640), mean rgb per 80px column:')
for x in range(0, w, 80):
    c = a[470:640, x:x+80].reshape(-1,3)
    print('  x=%4d..%4d  R %6.3f  G %6.3f  B %6.3f   (std R %.3f G %.3f B %.3f)' % (
        x, x+80, c[:,0].mean(), c[:,1].mean(), c[:,2].mean(), c[:,0].std(), c[:,1].std(), c[:,2].std()))
print()
print('black-ish fraction per column band:')
for x in range(0, w, 80):
    c = a[470:640, x:x+80].reshape(-1,3)
    blk = np.mean((c[:,0]<0.05)&(c[:,1]<0.05)&(c[:,2]<0.05))
    print('  x=%4d..%4d  black %.1f%%' % (x, x+80, 100*blk))