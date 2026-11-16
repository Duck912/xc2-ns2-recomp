import sys
import numpy as np
def read_pfm(path):
    with open(path,'rb') as f:
        hdr=f.readline().strip(); w,h=[int(x) for x in f.readline().split()]; scale=float(f.readline().strip())
        ch=3 if hdr==b'PF' else 1
        dt=np.dtype('<f4') if scale<0 else np.dtype('>f4')
        a=np.frombuffer(f.read(w*h*ch*4),dtype=dt).reshape(h,w,ch).astype(np.float64)
    return np.flipud(a)
p=sys.argv[1]
a=read_pfm(p)/2.78*1000.0
h,w,_=a.shape
print('== %s   (values are raw _x / 1000, decoded back: PFM/2.78*1000)' % p)
print(' rows y: R=_1018  G=_988  B=_468   (x 150..1130)')
for y in range(420,720,20):
    r=a[y,150:1130]
    print('   y=%3d  R %8.2f  G %8.2f  B %8.2f   (std %.2f %.2f %.2f)' % (y, r[:,0].mean(), r[:,1].mean(), r[:,2].mean(), r[:,0].std(), r[:,1].std(), r[:,2].std()))
print()
for name,(x0,x1,y0,y1) in {'plate left':(180,420,510,570),'plate right':(760,1000,510,570)}.items():
    v=a[y0:y1,x0:x1]
    print('   %-12s R %8.2f+-%6.2f   G %8.2f+-%6.2f   B %8.2f+-%6.2f' % (name, v[:,:,0].mean(), v[:,:,0].std(), v[:,:,1].mean(), v[:,:,1].std(), v[:,:,2].mean(), v[:,:,2].std()))