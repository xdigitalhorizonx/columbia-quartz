# Homepage scene — how the imagery was made

The hero moves from a top-down plan view of a Calacatta LX Gold island to a counter-height
profile of its mitred edge. It uses two 4K photographs and no video: on scroll, the plan photo
tilts away and pushes in, as if the camera were craning down, and then a short dissolve lands on
the elevation photo. Neither image is ever redrawn, so the veining and the lemon leaves cannot
change while you scroll.

## Sources

| Piece | Model (Replicate) | Notes |
|---|---|---|
| Plan still, 5504×3072 | `google/nano-banana-pro`, 4K, 16:9 | Real LX Gold slab photo (`assets/img/slab-lx-gold.jpg`) passed as the stone reference |
| Elevation still, 5504×3072 | `google/nano-banana-pro`, 4K, 16:9 | The plan still passed as the reference, so it is the same scene from counter height |

Masters (4K PNGs and the exact prompt JSON) are on Brandon's PC in
`C:\dev\columbia-quartz-source\`, not in git.

### Why there is no video

An earlier version scrubbed a Kling image-to-video clip between the two stills. An image-to-video
model redraws every frame, so the veining and the leaves visibly drifted during the move. A tilt
of the real photo plus a dissolve keeps every pixel of both photographs fixed.

## Rebuild the stills

```bash
python tools/scene/export_stills.py <source> assets/scene   # needs Pillow
```

This writes `plan-*.webp` and `elevation-*.webp`: 1600/2560/3840 wide, plus portrait crops at
1200/1800/2400 tall (a third of the master's width, centred by `FOCAL` in the script). Stills
use WebP quality 90–93. At quality 80, WebP smooths away about half of the stone's fine grain,
which reads as blur on large and high-density screens.

The motion lives in `assets/js/home.js` (`TILT`, `SWAP`, `LAND`); it starts with the first scroll. If the portrait crop changes,
update `TALL_CROP` there too, so the edge callouts stay on the stone. When you replace a still
under the same name, bump its `?v=` in `index.html`, because `/assets/` is cached for 7 days.
