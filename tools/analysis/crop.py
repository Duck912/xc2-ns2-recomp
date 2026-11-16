import sys, os, numpy as np
from PIL import Image
D=sys.argv[1]; OUT=sys.argv[2]
im=Image.open(os.path.join(D,'shots_manual','shot_0001.png')).convert('RGB')
w,h=im.size
crop=im.crop((0, 400, 1280, 620)).resize((1280, 440), Image.NEAREST)
crop.save(os.path.join(OUT,'crop_band.png'))
# also a luminance-stretched version (linear-ish contrast on the low band)
a=np.asarray(im.crop((0,400,1280,620))).astype(np.float64)/255.0
L=0.2126*a[:,:,0]+0.7152*a[:,:,1]+0.0722*a[:,:,2]
lo,hi=np.percentile(L,2),np.percentile(L,98)
st=np.clip((L-lo)/(hi-lo),0,1)
Image.fromarray((st*255).astype(np.uint8)).resize((1280,440), Image.NEAREST).save(os.path.join(OUT,'crop_band_stretch.png'))
print('crop saved; band lum p2 %.3f p50 %.3f p98 %.3f'%(lo,np.median(L),hi))
