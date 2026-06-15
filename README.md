# Columbia Quartz — Homepage

Premium quartz surfaces marketing homepage. Self-contained static site:
plain `index.html` plus local image, font, and script assets in `assets/`.

## Tech

- React 18 + ReactDOM (loaded locally from `assets/`)
- Babel Standalone (in-browser JSX transform) for a small edit-mode "tweaks" overlay
- Cormorant Garamond + companion web fonts (`.woff2`), bundled locally
- A fixed 1672×812 design canvas that scales to the viewport width

No build step is required — every dependency is committed under `assets/`.

## Run locally

```bash
python -m http.server 5050
# then open http://localhost:5050
```

## Deploy

Deployed as a static site on Vercel (no framework, no build command —
the repository root is served as-is).
