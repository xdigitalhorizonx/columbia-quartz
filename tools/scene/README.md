# Homepage scene — how the imagery is made

The hero is one scroll-scrubbed camera move through one kitchen, in three legs: from a top-down plan view of
a Calacatta LX Gold island down to its mitred edge, across the aisle to the sink run in Calacatta LX Noir,
then back to show the whole kitchen. It is a real 3D render (Blender 5.2, Cycles), so the veining, the lemons
and the leaves are identical in every frame and nothing drifts while the camera moves.

## What is in the scene

| Piece | Source |
|---|---|
| Island top | Columbia's own LX Gold slab photo (`tex/slab-lx-gold-tex.png`, the site's slab image upscaled 4x). The 10 cm mitred apron is UV-unfolded from the top, so a vein that reaches the edge carries straight down the apron, as it does on a real mitred edge cut from one slab. `SLAB_OFF` places the slab's strongest vein over the front edge. |
| Sink run top and backsplash | Columbia's LX Noir slab photo (`tex/slab-lx-noir-x4.png`, upscaled 4x with Real-ESRGAN). Counter, sink cut-out, backsplash and ledge are unfolded from one slab, so the black veins fold up the backsplash; past 3.2 m the slab mirrors, as a bookmatched second slab does. |
| Lemons | Poly Haven `lemon` scan (CC0), dropped into the bowl with a rigid-body sim |
| Lemon and olive leaves | ambientCG `Leaf001` scan (CC0) for colour and veins, on modelled leaf outlines; olive leaves in opposite pairs, each pair turned about 90 degrees |
| Napkin | Cloth sim draped over the front edge; Poly Haven `rough_linen` weave and height map (CC0), recoloured to oatmeal, with slubs |
| Wear on the props | ambientCG `Fingerprints002`, `SurfaceImperfections003`, `Scratches005` (CC0) on the brass, porcelain, glass and stone; `Metal009` brushing on the steel sink |
| Cutting board, crock | Poly Haven `wooden_cutting_board`, `ceramic_pot` (CC0) |
| Floor, walnut | Poly Haven `herringbone_parquet` and `smoked_walnut_veneer` (CC0), darkened |
| Light | Poly Haven `meadow` HDRI through steel-framed windows and a glass wall, plus a low warm sun (0.8 degrees wide, like the real sun) |
| Bowl, vase, tray, cups, faucet, sink, room | Modelled in `build_scene.py`: thrown stoneware with throwing rings, iron specks, pinholes and an unglazed foot; spun and brushed brass; porcelain with an unglazed foot ring |

Every prop is seated on the surface below it after its wobble and subdivision (`seat()`), because even a
half-millimetre gap lets light under it and kills the contact shadow.

Assets are not in git (about 240 MB with the slab textures). They live in `C:\dev\columbia-quartz-source\3d\` on Brandon's PC:
`assets/` (each folder has the downloader's `LICENSE.txt`), `tex/`, `scene.blend` and `renders/`.
Re-download with the `cc0-assets` skill if needed.

## Rebuild

```bash
B=C:/dev/tools/blender-5.2.3-windows-x64/blender.exe
SRC=C:/dev/columbia-quartz-source/3d
"$B" -b --factory-startup --python tools/scene/build_scene.py -- --src $SRC   # ~4 min, writes $SRC/scene.blend
bash tools/scene/render_all.sh $SRC                                           # ~2 hours on an RTX 3070 Ti
```

`render_all.sh` renders, then runs `export_frames.py` (needs Pillow + numpy), which writes:

- `assets/scene/d/000–287.webp`: the move, 1920×1080, for landscape screens
- `assets/scene/m/000–287.webp`: the move rendered in true 9:16 with its own framing, 720×1280, for phones
- `{plan,elevation,sink,kitchen}-*.webp`: the four stops rendered again at 3840×2160 and 1440×2560,
  exported at 3840/2560/1600 wide and 2400/1800/1200 tall

Every image gets the same gentle vignette in `export_frames.py`, so a still and the frame it stands in for
match exactly and the page can swap between them with no visible seam.

## Camera

`render_move.py` holds the whole move. Frames 0–119 are leg 1 (`PATHS`): straight down from 2.6 m, craning
down to a view 2.7 m out and 0.63 m above the top, with a slight lens shift (as an architectural
photographer would) so the edge sits low in frame; focal length and aperture ease from 50 mm f/11 to
70 mm f/5.6 (tall: 58 mm to 100 mm). Frames 120–191 glide to the sink view and 192–287 pull back to the
kitchen view (`SHOTS`: position, aim, lens, shift). Wide ends on a three-quarter view of the whole room;
tall pulls straight back from the sink to look down the island at the sink wall, which suits a 9:16 frame.
The ceiling is hidden from the camera only in leg 1, while the camera is above it.

Frames are evenly spaced along each leg; `home.js` eases each leg's ends.

## How the page uses them

`LEGS` in `assets/js/home.js` maps scroll progress to frames: leg 1 starts with the first scroll, and each
leg lands on a stop where its 4K still swaps in (`data-hold` on the layers in `index.html`). The plan still
is layered above the frame canvas and fades out only once the move starts, so the first view is always the
sharp 4K render; each stop's frame is the same picture as its still, so the hand-overs are invisible.

- Frame count or sizes change: update `data-frames` / `data-size-*` on the canvas in `index.html`.
- Any image changes: bump `data-rev` and every `?v=` on scene images; `/assets/` is cached for 7 days by URL.
- Callouts and name tags: `render_move.py --notes x1,x2,...` prints where points on the island's front edge
  land in its stop frame, and where each name tag's spot (`TAGS`) lands at each stop. `render_all.sh` writes
  these lines to `renders/render.log`; copy them into `NOTES` in `home.js`.
- Timing: `LEGS` and the in/out ranges next to it in `home.js`, the finale's `data-in`/`data-out` and the
  `data-hold` ranges in `index.html`.
