# Columbia Quartz — Homepage

Premium quartz surfaces marketing homepage. Static site: `index.html` plus local assets, no build step.

## The hero

Scrolling turns the camera from a top-down plan view of a Calacatta LX Gold island to a
counter-height profile of its mitred edge, using two 4K photographs (AI-generated stills) and no
video. From the first scroll the plan photo tilts away and pushes in, then a short dissolve lands on
the elevation photo, so the veining and the leaves never change.
How it was made and how to rebuild it: [`tools/scene/README.md`](tools/scene/README.md).

## Motion

The motion language follows digitalhorizon.dev: one `requestAnimationFrame` loop
(`assets/js/home.js`) drives the pinned scene, hero and finale copy, scrubbed statement, parallax, the
velocity marquee and the header. Lenis (`assets/vendor/`) smooths wheel scrolling.

- `prefers-reduced-motion`: no pinning, no Lenis, no reveals. The page renders as a static layout
  with both stills and all copy visible.
- Phones get portrait crops of both stills (`plan-portrait-*`, `elevation-portrait-*`).
- The tilt, push and dissolve are transforms, opacity and a light blur on the two photo layers,
  so they run on the compositor. Transforms are cleared at rest, so both photos render sharp.

## Inspirations page

`/inspirations/` is a lookbook of 13 rooms (kitchens, baths, laundry, pantry, fireplace), each finished
in a real Columbia slab with styling notes and a spec card. It reuses `home.css` and adds
`assets/css/inspirations.css` + `assets/js/inspirations.js`. The HTML is generated from
`tools/inspirations/looks.py`; how the photography was made: [`tools/inspirations/README.md`](tools/inspirations/README.md).

## Files

- `index.html`: markup
- `inspirations/index.html`: the Inspirations lookbook (built by `tools/inspirations/build_page.py`)
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
`vercel.json` adds a 7-day cache to `/assets/`, keyed by URL. When you replace a file under the same
name, bump its `?v=` in `index.html` (for the frame sequence, `data-rev` on the canvas), or returning
visitors keep the old file for up to a week.
