# SPDX-License-Identifier: GPL-3.0-or-later
"""Draws this project's app icon: an "XC2" monogram in gold on a deep indigo tile. No outside artwork is used; the
letters are set in a serif font installed with Windows (rasterised, as the font licences allow). Needs Pillow.

    python icon/make_icon.py [--font georgiab.ttf] [--out-png PATH]

Writes icon/icon.png (1024 px, the source for `npx tauri icon`) and the four files src-tauri/tauri.conf.json
lists under bundle.icon, so a package build has all of them.
"""
import argparse
import os

from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
LAUNCHER = os.path.dirname(HERE)
S = 2048
FONTS = ['georgiab.ttf', 'constanb.ttf', 'timesbd.ttf', 'arialbd.ttf']


def vertical(size, top, bottom):
    """A vertical gradient from top to bottom, drawn small and scaled up."""
    small = Image.new('RGB', (1, 64))
    px = small.load()
    for y in range(64):
        t = y / 63.0
        px[0, y] = tuple(int(round(a + (b - a) * t)) for a, b in zip(top, bottom))
    return small.resize((size, size), Image.BILINEAR)


def font(size):
    for name in FONTS:
        path = os.path.join(os.environ.get('WINDIR', r'C:\Windows'), 'Fonts', name)
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def rounded(size, radius):
    """A white rounded square, used as a mask so the tile has soft corners."""
    m = Image.new('L', (size, size), 0)
    ImageDraw.Draw(m).rounded_rectangle([0, 0, size - 1, size - 1], radius=radius, fill=255)
    return m


def draw(text):
    # sky blue, lighter at the top, like the page the launcher itself shows
    img = vertical(S, (163, 222, 250), (86, 170, 220)).convert('RGBA')
    # a soft white glow behind the letters, so the monogram reads at 32 px on the blue
    glow = Image.new('RGBA', (S, S), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    f = font(int(S * 0.46))
    box = gd.textbbox((0, 0), text, font=f)
    x = (S - (box[2] - box[0])) // 2 - box[0]
    y = (S - (box[3] - box[1])) // 2 - box[1]
    gd.text((x, y), text, font=f, fill=(255, 255, 255, 150))
    img = Image.alpha_composite(img, glow.filter(ImageFilter.GaussianBlur(S * 0.045)))
    # the letters themselves in cherry red, with a darker edge so they keep their shape when small
    d = ImageDraw.Draw(img)
    d.text((x, y), text, font=f, fill=(150, 20, 50, 120), stroke_width=int(S * 0.012), stroke_fill=(150, 20, 50, 120))
    d.text((x, y), text, font=f, fill=(208, 36, 76, 255))
    img.putalpha(rounded(S, int(S * 0.20)))
    return img


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--font', default='')
    ap.add_argument('--out-png', default=os.path.join(HERE, 'icon.png'))
    a = ap.parse_args()
    if a.font:
        FONTS.insert(0, a.font)

    big = draw('XC2')
    big.resize((1024, 1024), Image.LANCZOS).save(a.out_png)
    print('wrote', a.out_png)

    icons = os.path.join(LAUNCHER, 'src-tauri', 'icons')
    os.makedirs(icons, exist_ok=True)
    for name, px in (('32x32.png', 32), ('128x128.png', 128), ('128x128@2x.png', 256)):
        big.resize((px, px), Image.LANCZOS).save(os.path.join(icons, name))
        print('wrote', os.path.join(icons, name))
    # Windows picks the closest size out of the .ico; 16 to 256 covers the title bar and the large thumbnails
    ico = os.path.join(icons, 'icon.ico')
    big.resize((256, 256), Image.LANCZOS).save(ico, sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    print('wrote', ico)


if __name__ == '__main__':
    main()
