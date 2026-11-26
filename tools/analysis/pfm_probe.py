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

p = sys.argv[1]
a = read_pfm(p)
h,w,_ = a.shape
print('shape', a.shape)
print('global mean', a.reshape(-1,3).mean(axis=0).round(4), 'max', a.reshape(-1,3).max(axis=0).round(3))
# row profile of the mean colour
for y in range(0,h,h//12):
    row = a[y]
    print('y=%3d  mean rgb %s  p50 %s' % (y, row.mean(axis=0).round(4), np.median(row,axis=0).round(4)))

# find the magenta band: r>1 and b>1 and g<0.3
m = (a[:,:,0]>0.8)&(a[:,:,2]>0.8)&(a[:,:,1]<0.3)
print('magenta px', int(m.sum()), 'of', h*w)
if m.sum():
    ys,xs=np.where(m); print('  bbox y %d..%d x %d..%d'%(ys.min(),ys.max(),xs.min(),xs.max()))
    v=a[m]; print('  mean', v.mean(axis=0).round(3), 'p5', np.percentile(v,5,axis=0).round(3), 'p95', np.percentile(v,95,axis=0).round(3))