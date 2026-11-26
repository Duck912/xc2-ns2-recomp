import sys
import numpy as np
def read_pfm(path):
    with open(path,'rb') as f:
        hdr=f.readline().strip(); w,h=[int(x) for x in f.readline().split()]; scale=float(f.readline().strip())
        ch=3 if hdr==b'PF' else 1
        dt=np.dtype('<f4') if scale<0 else np.dtype('>f4')
        a=np.frombuffer(f.read(w*h*ch*4),dtype=dt).reshape(h,w,ch).astype(np.float64)
    return np.flipud(a)

for p in sys.argv[1:]:
    a=read_pfm(p)
    w0 = a[500:560, 400:900]   # clean fog window (below horizon, above deck)
    print('==', p)
    for i,c in enumerate('RGB'):
        v = w0[:,:,i]
        print('   %s mean %.3f std %.3f min %.3f max %.3f   rowstd %.3f colstd %.3f' % (
            c, v.mean(), v.std(), v.min(), v.max(), v.mean(axis=1).std(), v.mean(axis=0).std()))
    # fraction of pixels within 2% of the window median, per channel
    for i,c in enumerate('RGB'):
        v=w0[:,:,i]; med=np.median(v)
        print('   %s |v-med| < 2%% of med: %.1f%%' % (c, 100*np.mean(np.abs(v-med) < 0.02*max(med,1e-6))))