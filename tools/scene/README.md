# Homepage scene — how the imagery is made

The hero is a scroll-scrubbed camera move over a Calacatta LX Gold island, from a top-down plan view to a
counter-height view of the mitred edge. It is a real 3D render (Blender 5.2, Cycles), so the veining, the
lemons and the leaves are identical in every frame and nothing drifts while the camera moves.

## What is in the scene

| Piece | Source |
|---|---|
| Countertop | Columbia's own LX Gold slab photo (`tex/slab-lx-gold-tex.png`, the site's slab image upscaled 4x). The 10 cm mitred apron is UV-unfolded from the top, so a vein that reaches the edge carries straight down the apron, as it does on a real mitred edge cut from one slab. `SLAB_OFF` places the slab's strongest vein over the front edge. |
| Lemons | Poly Haven `lemon` scan (CC0), dropped into the bowl with a rigid-body sim |
| Lemon and olive leaves | ambientCG `Leaf001` scan (CC0) for colour and veins, on modelled leaf outlines; olive leaves in opposite pairs, each pair turned about 90 degrees |
| Napkin | Cloth sim draped over the front edge; Poly Haven `rough_linen` weave (CC0), recoloured to oatmeal |
| Floor, base | Poly Haven `herringbone_parquet` and `smoked_walnut_veneer` (CC0), darkened |
| Light | Poly Haven `meadow` HDRI through steel-framed windows, plus a low warm sun from the open right side |
| Bowl, vase, tray, cups, room | Modelled in `build_scene.py` (lathed stoneware with speckle, spun brushed brass, porcelain) |

Assets are not in git (about 150 MB). They live in `C:\dev\columbia-quartz-source\3d\` on Brandon's PC:
`assets/` (each folder has the downloader's `LICENSE.txt`), `tex/`, `scene.blend` and `renders/`.
Re-download with the `cc0-assets` skill if needed.

## Rebuild

```bash
B=C:/dev/tools/blender-5.2.3-windows-x64/blender.exe
SRC=C:/dev/columbia-quartz-source/3d
"$B" -b --factory-startup --python tools/scene/build_scene.py -- --src $SRC   # ~3 min, writes $SRC/scene.blend
bash tools/scene/render_all.sh $SRC                                           # ~75 min on an RTX 3070 Ti
```

`render_all.sh` renders, then runs `export_frames.py` (needs Pillow + numpy), which writes:

- `assets/scene/d/000–119.webp`: the move, 1920×1080, for landscape screens
- `assets/scene/m/000–119.webp`: the move rendered in true 9:16 with its own framing, 720×1280, for phones
- `plan-*.webp` / `elevation-*.webp`: the first and last frame rendered again at 3840×2160 and 1440×2560,
  exported at 3840/2560/1600 wide and 2400/1800/1200 tall

Every image gets the same gentle vignette in `export_frames.py`, so a still and the frame it stands in for
match exactly and the page can swap between them with no visible seam.

## Camera

`render_move.py` holds both paths (`PATHS`). Each starts straight down from 2.6 m and cranes down to a
view 2.7 m out and 0.63 m above the top, ending with a slight lens shift (as an architectural photographer
would) so the edge sits low in frame. Focal length and aperture ease from 50 mm f/11 to 70 mm f/5.6
(tall: 58 mm to 110 mm). Frames are evenly spaced along the path; `home.js` eases the ends.

## How the page uses them

The move starts with the first scroll (`CAM_A`–`CAM_B` in `assets/js/home.js`) and lands on the
elevation still, where the finale and the edge callouts hold. The plan still is layered above the
frame canvas and fades out only once the move starts, so the first view is always the sharp 4K
render; frame 0 is the same picture, so the hand-over is invisible.

- Frame count or sizes change: update `data-frames` / `data-size-*` on the canvas in `index.html`.
- Any image changes: bump `data-rev` and every `?v=` on scene images; `/assets/` is cached for 7 days by URL.
- Callouts: `render_move.py --notes x1,x2,...` prints where points on the front edge land in the last frame
  (x, then y from the top for the top, middle and bottom of the edge). Copy them into `NOTES` in `home.js`.
- Timing: `CAM_A`/`CAM_B` in `home.js` and the finale's `data-in` in `index.html`.
