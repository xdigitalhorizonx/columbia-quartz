"""Export the chosen Inspirations masters to web sizes.

    python tools/inspirations/export.py <masters-dir>

<masters-dir> holds one PNG per look, named <look-id>.png (2K masters from the generator).
Writes assets/img/inspirations/<look-id>-<width>.webp at 800/1400/2000 px wide (capped at the master's width).
"""
import os, sys
from PIL import Image, ImageFilter

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
OUT = os.path.join(ROOT, "assets", "img", "inspirations")
WIDTHS = (800, 1400, 2000)


def export(src_dir):
    os.makedirs(OUT, exist_ok=True)
    total = 0
    for name in sorted(os.listdir(src_dir)):
        if not name.endswith(".png"):
            continue
        look = name[:-4]
        im = Image.open(os.path.join(src_dir, name)).convert("RGB")
        for w in sorted({min(w, im.width) for w in WIDTHS}):
            h = round(im.height * w / im.width)
            out = im.resize((w, h), Image.LANCZOS)
            out = out.filter(ImageFilter.UnsharpMask(radius=0.6, percent=35, threshold=2))
            path = os.path.join(OUT, f"{look}-{w}.webp")
            out.save(path, "WEBP", quality=80, method=6)
            total += os.path.getsize(path)
        print(look, im.size)
    print(f"{total / 1e6:.1f} MB written to {OUT}")


if __name__ == "__main__":
    export(sys.argv[1])
