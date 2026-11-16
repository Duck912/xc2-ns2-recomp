import sys
import numpy as np
def read_pfm(path):
    with open(path,'rb') as f:
        hdr=f.readline().strip(); w,h=[int(x) for x in f.readline().split()]; scale=float(f.readline().strip())
        ch=3 if hdr==b'PF' else 1
        dt=np.dtype('<f4') if scale<0 else np.dtype('>f4')
        a=np.frombuffer(f.read(w*h*ch*4),dtype=dt).reshape(h,w,ch).astype(np.float64)
    return np.flipud(a)
WINS = {'left  (x180-420,y510-570)': (180,420,510,570), 'right (x760-1000,y510-570)': (760,1000,510,570)}
for p in sys.argv[1:]:
    a=read_pfm(p)
    print('==', p)
    for name,(x0,x1,y0,y1) in WINS.items():
        w0=a[y0:y1, x0:x1]
        s='   %-30s' % name
        for i,c in enumerate('RGB'):
            v=w0[:,:,i]
            s += '  %s %.2f+-%.2f (v%.2f h%.2f)' % (c, v.mean(), v.std(), v.mean(axis=1).std(), v.mean(axis=0).std())
        print(s)