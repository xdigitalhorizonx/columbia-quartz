# Export the homepage scene: scroll frames (wide + tall crops) and the two 4K endpoint stills.
# usage: python tools/scene/export_frames.py <source-dir> assets/scene
#   <source-dir> holds raw/ (every clip frame as PNG, from ffmpeg) and stills/plan-master-5504.png,
#   stills/elevation-master-5504.png. See tools/scene/README.md.
import os, sys
from PIL import Image, ImageFilter
SRC, OUT = sys.argv[1], sys.argv[2]
raw = os.path.join(SRC, 'raw')
files = sorted(f for f in os.listdir(raw) if f.endswith('.png'))
picks = list(range(0, len(files), 2))
if picks[-1] != len(files) - 1: picks.append(len(files) - 1)
N = len(picks)
# portrait crop centre (fraction of frame width) vs clip time, read off the frames by eye
KEYS = [(0.0, 0.68), (0.37, 0.70), (0.54, 0.62), (0.70, 0.50), (0.85, 0.42), (1.0, 0.38)]
def focal(t):
    for (t0, a), (t1, b) in zip(KEYS, KEYS[1:]):
        if t <= t1: return a + (b - a) * (t - t0) / (t1 - t0)
    return KEYS[-1][1]
CW = 1 / 3  # portrait crop width as a fraction of frame width (640 of 1920)
def crop_box(w, h, c):
    cw = round(w * CW); x = round(min(max(c * w - cw / 2, 0), w - cw)); return (x, 0, x + cw, h)
sharp = ImageFilter.UnsharpMask(radius=1.1, percent=35, threshold=2)
for d in ('d', 'm'): os.makedirs(os.path.join(OUT, d), exist_ok=True)
tot = {'d': 0, 'm': 0}
for i, fi in enumerate(picks):
    im = Image.open(os.path.join(raw, files[fi])).convert('RGB').filter(sharp)
    t = fi / (len(files) - 1)
    pd = os.path.join(OUT, 'd', f'{i:03d}.webp'); im.save(pd, 'WEBP', quality=78, method=6)
    pm = os.path.join(OUT, 'm', f'{i:03d}.webp'); im.crop(crop_box(*im.size, focal(t))).save(pm, 'WEBP', quality=76, method=6)
    tot['d'] += os.path.getsize(pd); tot['m'] += os.path.getsize(pm)
# endpoint stills from the 4K masters
for name, src, t in (('plan', 'plan-master-5504.png', 0.0), ('elevation', 'elevation-master-5504.png', 1.0)):
    im = Image.open(os.path.join(SRC, 'stills', src)).convert('RGB')
    for w in (2560, 1600):
        x = im.resize((w, round(w * im.height / im.width)), Image.LANCZOS)
        x.save(os.path.join(OUT, f'{name}-{w}.webp'), 'WEBP', quality=80, method=6)
    pc = im.crop(crop_box(*im.size, focal(t)))
    for h in (1800, 1200):
        x = pc.resize((round(h * pc.width / pc.height), h), Image.LANCZOS)
        x.save(os.path.join(OUT, f'{name}-portrait-{h}.webp'), 'WEBP', quality=80, method=6)
print({'frames': N, 'desktop_MB': round(tot['d'] / 1e6, 2), 'mobile_MB': round(tot['m'] / 1e6, 2)})
