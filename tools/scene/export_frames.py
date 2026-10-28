# Export the homepage scene: scroll frames (wide + tall crops) and the two 4K endpoint stills.
# usage: python tools/scene/export_frames.py <source-dir> assets/scene [frame-count]
#   <source-dir> holds raw/ (every clip frame as PNG, from ffmpeg) and stills/plan-master-5504.png,
#   stills/elevation-master-5504.png. See tools/scene/README.md.
# Frames are picked by camera motion, not by time: the clip's slow start and end (where the camera
# barely moves and the generated veining drifts most visibly) get few frames, the move itself gets many,
# so a linear scroll through the frames reads as one steady camera move.
import os, sys
import cv2, numpy as np
from PIL import Image, ImageFilter
SRC, OUT = sys.argv[1], sys.argv[2]
COUNT = int(sys.argv[3]) if len(sys.argv) > 3 else 72
raw = os.path.join(SRC, 'raw')
files = sorted(f for f in os.listdir(raw) if f.endswith('.png'))

# camera motion per frame: median optical-flow magnitude between neighbours, at 480 px wide
def small(f):
    im = cv2.imread(os.path.join(raw, f))
    return cv2.cvtColor(cv2.resize(im, (480, 270), interpolation=cv2.INTER_AREA), cv2.COLOR_BGR2GRAY)
motion, prev = [0.0], small(files[0])
for f in files[1:]:
    g = small(f)
    flow = cv2.calcOpticalFlowFarneback(prev, g, None, 0.5, 4, 21, 5, 7, 1.5, 0)
    motion.append(float(np.median(np.linalg.norm(flow, axis=2)))); prev = g
cum = np.cumsum(motion); cum /= cum[-1]
picks = [int(np.argmin(np.abs(cum - k / (COUNT - 1)))) for k in range(COUNT)]
picks[0], picks[-1] = 0, len(files) - 1
for k in range(1, COUNT):                       # keep picks strictly increasing
    picks[k] = max(picks[k], picks[k - 1] + 1)

# portrait crop centre (fraction of frame width) vs clip time, read off the frames by eye
KEYS = [(0.0, 0.68), (0.37, 0.70), (0.54, 0.62), (0.70, 0.50), (0.85, 0.42), (1.0, 0.38)]
def focal(t):
    for (t0, a), (t1, b) in zip(KEYS, KEYS[1:]):
        if t <= t1: return a + (b - a) * (t - t0) / (t1 - t0)
    return KEYS[-1][1]
CW = 1 / 3  # portrait crop width as a fraction of frame width (640 of 1920)
def crop_box(w, h, c):
    cw = round(w * CW); x = round(min(max(c * w - cw / 2, 0), w - cw)); return (x, 0, x + cw, h)
sharp = ImageFilter.UnsharpMask(radius=1.1, percent=45, threshold=2)
for d in ('d', 'm'): os.makedirs(os.path.join(OUT, d), exist_ok=True)
tot = {'d': 0, 'm': 0}
for i, fi in enumerate(picks):
    im = Image.open(os.path.join(raw, files[fi])).convert('RGB').filter(sharp)
    t = fi / (len(files) - 1)
    pd = os.path.join(OUT, 'd', f'{i:03d}.webp'); im.save(pd, 'WEBP', quality=88, method=6)
    pm = os.path.join(OUT, 'm', f'{i:03d}.webp'); im.crop(crop_box(*im.size, focal(t))).save(pm, 'WEBP', quality=86, method=6)
    tot['d'] += os.path.getsize(pd); tot['m'] += os.path.getsize(pm)
# endpoint stills from the 4K masters. High quality on purpose: at q80 WebP smooths away about
# half of the stone's fine grain, which reads as blur on large and high-density screens.
for name, src, t in (('plan', 'plan-master-5504.png', 0.0), ('elevation', 'elevation-master-5504.png', 1.0)):
    im = Image.open(os.path.join(SRC, 'stills', src)).convert('RGB')
    for w, q in ((3840, 90), (2560, 93), (1600, 92)):
        x = im.resize((w, round(w * im.height / im.width)), Image.LANCZOS)
        x.save(os.path.join(OUT, f'{name}-{w}.webp'), 'WEBP', quality=q, method=6)
    pc = im.crop(crop_box(*im.size, focal(t)))
    for h, q in ((2400, 90), (1800, 92), (1200, 92)):
        x = pc.resize((round(h * pc.width / pc.height), h), Image.LANCZOS)
        x.save(os.path.join(OUT, f'{name}-portrait-{h}.webp'), 'WEBP', quality=q, method=6)
print({'frames': COUNT, 'raw_picks': picks[:6] + ['...'] + picks[-4:],
       'desktop_MB': round(tot['d'] / 1e6, 2), 'mobile_MB': round(tot['m'] / 1e6, 2)})
