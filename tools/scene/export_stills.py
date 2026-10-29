# Export the homepage scene's two 4K photos (plan view and elevation) at the sizes the page uses.
# usage: python tools/scene/export_stills.py <source-dir> assets/scene
#   <source-dir> holds stills/plan-master-5504.png and stills/elevation-master-5504.png. See tools/scene/README.md.
# High quality on purpose: at q80, WebP smooths away about half of the stone's fine grain, which reads
# as blur on large and high-density screens.
import os, sys
from PIL import Image
SRC, OUT = sys.argv[1], sys.argv[2]
CW = 1 / 3   # portrait crop width as a fraction of the master's width
# portrait crop centre (fraction of the master's width), chosen so the bowl, vase and edge stay in frame
FOCAL = {'plan': 0.68, 'elevation': 0.38}
def crop_box(w, h, c):
    cw = round(w * CW); x = round(min(max(c * w - cw / 2, 0), w - cw)); return (x, 0, x + cw, h)
os.makedirs(OUT, exist_ok=True)
for name in ('plan', 'elevation'):
    im = Image.open(os.path.join(SRC, 'stills', f'{name}-master-5504.png')).convert('RGB')
    for w, q in ((3840, 90), (2560, 93), (1600, 92)):
        x = im.resize((w, round(w * im.height / im.width)), Image.LANCZOS)
        x.save(os.path.join(OUT, f'{name}-{w}.webp'), 'WEBP', quality=q, method=6)
    pc = im.crop(crop_box(*im.size, FOCAL[name]))
    for h, q in ((2400, 90), (1800, 92), (1200, 92)):
        x = pc.resize((round(h * pc.width / pc.height), h), Image.LANCZOS)
        x.save(os.path.join(OUT, f'{name}-portrait-{h}.webp'), 'WEBP', quality=q, method=6)
print('stills ok')
