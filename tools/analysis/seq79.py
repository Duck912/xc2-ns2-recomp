import numpy as np, os, glob, re
from PIL import Image
b = r'.\xc2\build\boot'
files = []
for f in glob.glob(os.path.join(b,'snap_d*_t13_*.png')):
    m = re.search(r'snap_d(\d+)_t13_', f)
    if m: files.append((int(m.group(1)), f))
files.sort()
print('snapshots:', len(files))
print(' draw   region-std  region-mean(rgb)          verdict')
prev = None
for n, f in files:
    im = Image.open(f).convert('RGB')
    if im.size != (1280,720):
        print('  #%-4d size %s (skipped)' % (n, im.size)); continue
    a = np.array(im).astype(np.float32)/255.0
    box = a[520:620, 60:400]
    sd = float(box.std(axis=(0,1)).mean()); mu = box.mean(axis=(0,1))
    tag = ''
    if sd < 0.02 and mu.mean() > 0.004: tag = '  <== flat'
    print('  #%-4d  %8.4f   (%.3f %.3f %.3f)  %s' % (n, sd, mu[0], mu[1], mu[2], tag))
