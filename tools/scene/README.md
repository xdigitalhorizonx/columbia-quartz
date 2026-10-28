# Homepage scene — how the imagery was made

The hero is a scroll-scrubbed camera move over a Calacatta LX Gold island, from a top-down
plan view to a counter-height edge profile. It is photographic, not 3D: two 4K stills and one
image-to-video clip, cut into frames.

## Sources

| Piece | Model (Replicate) | Notes |
|---|---|---|
| Plan still, 5504×3072 | `google/nano-banana-pro`, 4K, 16:9 | Real LX Gold slab photo (`assets/img/slab-lx-gold.jpg`) passed as the stone reference |
| Elevation still, 5504×3072 | `google/nano-banana-pro`, 4K, 16:9 | The plan still passed as the reference, so it is the same scene from counter height |
| Camera move, 10 s, 1920×1080, 24 fps | `kwaivgi/kling-v2.5-turbo-pro` | `start_image` = plan still, `end_image` = elevation still |

The clip's first and last frames match the stills to a mean pixel difference of about 3/255,
which is why the page can cross-fade between the 4K stills and the sequence with no visible seam.

Masters (4K PNGs, the clip, and the exact prompt JSON) are on Brandon's PC in
`C:\dev\columbia-quartz-source\`, not in git.

## Rebuild the frames

```bash
ffmpeg -i <source>/clips/plan-to-elevation-kling25-10s.mp4 -fps_mode passthrough <source>/raw/f%03d.png
python tools/scene/export_frames.py <source> assets/scene 72   # needs Pillow + opencv-python
```

This writes:

- `assets/scene/d/000–071.webp`: 72 clip frames, 1920×1080, for landscape screens (about 7.6 MB)
- `assets/scene/m/000–071.webp`: a 640×1080 portrait crop that follows the objects (`KEYS` in the script), for phones (about 2.7 MB)
- `plan-*.webp` / `elevation-*.webp`: the endpoint stills at 1600/2560/3840 wide plus portrait crops at 1200/1800/2400 tall

Frames are picked by camera motion (optical flow), not evenly in time. The clip starts and ends slowly,
and those stretches are where the generated veining and leaves drift most; spacing frames by motion
skips them, so scrolling through the frames reads as one steady move.

The stills are exported at WebP quality 90–93 on purpose. At quality 80, WebP smooths away about half
of the stone's fine grain, which reads as blur on large and high-density screens.

## Why the move is short

An image-to-video model redraws the veining and the lemon leaves on every frame, so they drift during
the move. The page therefore holds on the two 4K stills for most of the scroll (hero and beats 1–2 on
the plan view, beat 3 and the finale on the elevation) and plays the clip only during a short, quick
camera move (`CAM_A`–`CAM_B` in `assets/js/home.js`).

If the frame count or sizes change, update `data-frames` / `data-size-*` on the canvas in
`index.html`. If the portrait crop path changes, update `TALL_CROP` in `assets/js/home.js`.
