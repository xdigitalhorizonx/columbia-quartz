# Export the rendered camera move and its hold stills to the homepage's WebP sets.
# usage: python tools/scene/export_frames.py <renders-dir> assets/scene     (needs Pillow + numpy)
#   <renders-dir>/wide/NNN.png    the move, 16:9 (1920x1080)        -> assets/scene/d/NNN.webp
#   <renders-dir>/tall/NNN.png    the move, 9:16 (720x1280)         -> assets/scene/m/NNN.webp
#   <renders-dir>/stills/{wide,tall}/000, 119, 191, 287.png  the four holds at 4K
#       -> {plan,elevation,sink,kitchen}-{3840,2560,1600}.webp and -portrait-{2400,1800,1200}.webp
# Every image gets the same gentle lens vignette, so a still and the frame it stands in for match exactly.
import os, sys
import numpy as np
from PIL import Image

SRC, OUT = sys.argv[1], sys.argv[2]

def vignette(im, amount=0.16):
    a = np.asarray(im).astype(np.float32) / 255.0
    h, w = a.shape[:2]
    y, x = np.mgrid[0:h, 0:w].astype(np.float32)
    d = np.hypot((x - w / 2) / (w / 2), (y - h / 2) / (h / 2)) / np.sqrt(2)   # 0 centre .. 1 corner
    lin = np.where(a <= 0.04045, a / 12.92, ((a + 0.055) / 1.055) ** 2.4)     # darken in linear light
    lin *= (1 - amount * d ** 2.4)[..., None]
    a = np.where(lin <= 0.0031308, lin * 12.92, 1.055 * lin ** (1 / 2.4) - 0.055)
    return Image.fromarray((np.clip(a, 0, 1) * 255 + 0.5).astype(np.uint8))

def load(path):
    return vignette(Image.open(path).convert('RGB'))

tot = {}
for kind, d, q in (('wide', 'd', 84), ('tall', 'm', 82)):
    src = os.path.join(SRC, kind)
    files = sorted(f for f in os.listdir(src) if f.endswith('.png'))
    os.makedirs(os.path.join(OUT, d), exist_ok=True)
    for old in os.listdir(os.path.join(OUT, d)):
        if old.endswith('.webp'): os.remove(os.path.join(OUT, d, old))
    tot[d] = 0
    for i, f in enumerate(files):
        p = os.path.join(OUT, d, f'{i:03d}.webp')
        load(os.path.join(src, f)).save(p, 'WEBP', quality=q, method=6)
        tot[d] += os.path.getsize(p)
    tot[d + '_frames'] = len(files)

# hold stills. High quality on purpose: at q80 WebP smooths away the stone's fine grain,
# which reads as blur on large and high-density screens.
for kind, sizes in (('wide', ((3840, 90), (2560, 92), (1600, 92))), ('tall', ((2400, 90), (1800, 92), (1200, 92)))):
    for name, f in (('plan', '000.png'), ('elevation', '119.png'), ('sink', '191.png'), ('kitchen', '287.png')):
        im = load(os.path.join(SRC, 'stills', kind, f))
        for size, q in sizes:
            if kind == 'wide':
                x = im.resize((size, round(size * im.height / im.width)), Image.LANCZOS)
                x.save(os.path.join(OUT, f'{name}-{size}.webp'), 'WEBP', quality=q, method=6)
            else:
                x = im.resize((round(size * im.width / im.height), size), Image.LANCZOS)
                x.save(os.path.join(OUT, f'{name}-portrait-{size}.webp'), 'WEBP', quality=q, method=6)
print({k: (round(v / 1e6, 2) if not k.endswith('frames') else v) for k, v in tot.items()})
