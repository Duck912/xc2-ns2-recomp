import numpy as np, os, glob
from PIL import Image
b = r'.\xc2\build\boot'
fs = sorted(glob.glob(os.path.join(b,'snap_d*_t13_R11G11B10F.png')), key=os.path.getmtime)
print('t13 dumps:', [os.path.basename(f) for f in fs[-4:]])
f = fs[-1]
im = Image.open(f).convert('RGB')
a = np.array(im).astype(np.float32)/255.0
lum = 0.2126*a[:,:,0] + 0.7152*a[:,:,1] + 0.0722*a[:,:,2]
print(os.path.basename(f), 'lum: min %.4f med %.4f p95 %.4f max %.4f' % (lum.min(), np.median(lum), np.percentile(lum,95), lum.max()))
# contrast stretch by percentile and save
lo, hi = np.percentile(lum, 2), np.percentile(lum, 99.5)
s = np.clip((lum-lo)/max(hi-lo,1e-6), 0, 1)
out = os.path.join(b, 't13_stretch.png')
Image.fromarray((s*255).astype(np.uint8)).save(out)
print('wrote', out, 'lo %.4f hi %.4f' % (lo, hi))
