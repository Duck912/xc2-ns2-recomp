import sys
import numpy as np
def read_pfm(path):
    with open(path,"rb") as f:
        hdr=f.readline().strip(); w,h=[int(x) for x in f.readline().split()]; scale=float(f.readline().strip())
        ch=3 if hdr==b"PF" else 1
        dt=np.dtype("<f4") if scale<0 else np.dtype(">f4")
        a=np.frombuffer(f.read(w*h*ch*4),dtype=dt).reshape(h,w,ch).astype(np.float64)
    return np.flipud(a)
a = read_pfm(sys.argv[1]) / 2.78
for name,(x0,x1,y0,y1) in {"plate-left":(180,420,510,570), "plate-right":(760,1000,510,570), "plate-wide":(150,1130,500,580)}.items():
    v = a[y0:y1, x0:x1]
    print("%-12s  R(raw) %.3f +- %.3f   G(wrap) %.3f +- %.3f   corr %.2f" % (
        name, v[:,:,0].mean(), v[:,:,0].std(), v[:,:,1].mean(), v[:,:,1].std(),
        np.corrcoef(v[:,:,0].ravel(), v[:,:,1].ravel())[0,1]))
print()
print("column means (y 500..580) every 80 px:   raw / wrap")
h,w,_ = a.shape
for x in range(0, w, 80):
    c = a[500:580, x:x+80]
    print("   x=%4d  raw %.3f+-%.3f   wrap %.3f+-%.3f" % (x, c[:,:,0].mean(), c[:,:,0].std(), c[:,:,1].mean(), c[:,:,1].std()))