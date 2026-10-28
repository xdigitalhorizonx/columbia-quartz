# Columbia Quartz — Homepage

Premium quartz surfaces marketing homepage. Static site: `index.html` plus local assets, no build step.

## The hero

Scrolling turns the camera from a top-down plan view of a Calacatta LX Gold island to a
counter-height profile of its mitred edge. The imagery is photographic (AI-generated stills and
an image-to-video camera move, cut into 122 WebP frames), drawn to a canvas as you scroll.
How it was made and how to rebuild it: [`tools/scene/README.md`](tools/scene/README.md).

## Motion

The motion language follows digitalhorizon.dev: one `requestAnimationFrame` loop
(`assets/js/home.js`) drives the pinned scene, story beats, scrubbed statement, parallax, the
velocity marquee and the header. Lenis (`assets/vendor/`) smooths wheel scrolling.

- `prefers-reduced-motion`: no pinning, no Lenis, no reveals. The page renders as a static layout
  with both stills and all copy visible.
- Data Saver: the frame sequence is skipped and the scene cross-fades between the two stills.
- Phones use a separate portrait frame set (2.9 MB) instead of the 16:9 set (7.3 MB).
- Frames load after the page's `load` event, coarse to fine, so scrubbing works before every frame has arrived.

## Files

- `index.html`: markup
- `assets/css/home.css`, `assets/js/home.js`: styles and motion
- `assets/scene/`: frame sequence and endpoint stills
- `assets/img/`: logo, slab swatches, room photography
- `assets/fonts/`: self-hosted Cormorant Garamond and Mulish (`SOURCES.txt` has the licences)
- `assets/vendor/`: Lenis 1.3.26 (MIT)

## Run locally

```bash
python -m http.server 5050
# then open http://localhost:5050
```

## Deploy

Static site on Vercel (no framework, no build command; the repository root is served as-is).
`vercel.json` adds a 7-day cache to `/assets/`.
