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

def stats(a, y0,y1,x0,x1, label):
    r=a[y0:y1,x0:x1].reshape(-1,3)
    print('%-22s n=%6d  R %.3f+-%.3f [p5 %.3f p95 %.3f]  G %.3f+-%.3f [%.3f %.3f]  B %.3f+-%.3f [%.3f %.3f]' % (
        label, len(r),
        r[:,0].mean(), r[:,0].std(), np.percentile(r[:,0],5), np.percentile(r[:,0],95),
        r[:,1].mean(), r[:,1].std(), np.percentile(r[:,1],5), np.percentile(r[:,1],95),
        r[:,2].mean(), r[:,2].std(), np.percentile(r[:,2],5), np.percentile(r[:,2],95)))

for p in sys.argv[1:]:
    a = read_pfm(p)
    h,w,_ = a.shape
    print('=====', p, a.shape)
    print(' rows: y   meanR meanG meanB   (x 150..1130)')
    for y in range(360, 720, 30):
        row = a[y,150:1130]
        print('   y=%3d  %.3f %.3f %.3f   stdR %.3f stdG %.3f stdB %.3f' % (y, row[:,0].mean(), row[:,1].mean(), row[:,2].mean(), row[:,0].std(), row[:,1].std(), row[:,2].std()))
    stats(a, 470, 640, 150, 1130, 'plate band')
    stats(a, 100, 300, 150, 1130, 'sky')
    stats(a, 660, 719, 150, 1130, 'deck')