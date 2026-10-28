# Inspirations page — how it was made

`inspirations/index.html` is generated from `looks.py` (copy, specs, pin positions) by `build_page.py`.
Edit the copy in `looks.py`, then rebuild:

```bash
python tools/inspirations/build_page.py
```

## The photography

Thirteen rooms, each showing one real Columbia slab. Every room was generated with
`google/nano-banana-pro` on Replicate (2K), with that slab's product photo
(`assets/img/slab-*.jpg`) passed as the stone reference, so the countertop matches the real surface.

- Model chosen by a bake-off on the same prompt: Nano Banana Pro read as a real photo; Flux 2 Max and
  Seedream 4.5 looked rendered (warm grading, plastic stone).
- Prompts (`scenes.py`) describe an interior photographer's shot, not a "render": lights off, daylight
  only, 24–35 mm at chest height, straight verticals, neutral white balance, lived-in styling.
- Two takes per room; the best was picked after zooming in on hardware, stools and text.
- Three picks had AI-garbled text (a bottle label, a range badge, book spines). Those were cleaned with
  a Nano Banana Pro edit pass on the same image.

Masters (2K PNGs, every take, and the exact job JSON) live on Brandon's PC in
`C:\dev\columbia-quartz-source\inspirations\`, not in git.

## Rebuild the images

```bash
python tools/inspirations/scenes.py jobs.json 2            # job list, 2 takes per room
python tools/inspirations/generate.py jobs.json <out-dir>   # needs REPLICATE_API_TOKEN
# copy the chosen take to <masters>/<look-id>.png, then:
python tools/inspirations/export.py <masters>
python tools/inspirations/build_page.py
```

`export.py` writes `assets/img/inspirations/<look-id>-{800,1400,2000}.webp` (about 3.6 MB for all 39 files).
If a photo changes, re-check its `pin` in `looks.py`: it marks where the quartz is, as % of width/height.

`/assets/` is cached for 7 days by URL. When `inspirations.css`/`.js` change, bump their `?v=` in the
`build_page.py` template; when the homepage bumps `home.css?v=`, match it there too.
