"""Build inspirations/index.html from looks.py and the exported images.

    python tools/inspirations/build_page.py

Image widths and heights are read from assets/img/inspirations/<id>-<w>.webp, so run export.py first.
"""
import glob, html, os, re, sys
from PIL import Image

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.dirname(__file__))
from looks import SLABS, CHAPTERS, LOOKS  # noqa: E402

IMG_DIR = os.path.join(ROOT, "assets", "img", "inspirations")
SIZES = {
    "wide": "(min-width: 1300px) 1150px, 92vw",
    "side": "(min-width: 1300px) 700px, (min-width: 1100px) 55vw, 92vw",
    "tall": "(min-width: 1300px) 480px, (min-width: 720px) 46vw, 92vw",
    "pair": "(min-width: 1300px) 560px, (min-width: 720px) 46vw, 92vw",
}
ROOM_LABEL = {"kitchens": "Kitchens", "baths": "Baths", "beyond": "Beyond the kitchen"}
ARROW = '<svg viewBox="0 0 22 9" aria-hidden="true"><path d="M0 4.5h20M16 1l4 3.5-4 3.5"/></svg>'


def strip(s):
    return re.sub(r"<[^>]+>", "", html.unescape(s))


def variants(look_id):
    out = []
    for p in glob.glob(os.path.join(IMG_DIR, f"{look_id}-*.webp")):
        w = int(re.search(r"-(\d+)\.webp$", p).group(1))
        out.append((w, Image.open(p).size))
    if not out:
        raise SystemExit(f"no exported image for {look_id}")
    return sorted(out)


def img_tag(look, sizes, eager=False):
    vs = variants(look["id"])
    srcset = ", ".join(f"/assets/img/inspirations/{look['id']}-{w}.webp {w}w" for w, _ in vs)
    mid = vs[min(1, len(vs) - 1)]
    w, h = vs[-1][1]
    load = 'fetchpriority="high"' if eager else 'loading="lazy"'
    return (f'<img src="/assets/img/inspirations/{look["id"]}-{mid[0]}.webp" srcset="{srcset}" sizes="{sizes}" '
            f'width="{w}" height="{h}" alt="{look["alt"]}" {load} decoding="async">')


def look_html(n, look, in_pair=False):
    name, no = SLABS[look["slab"]]
    layout = "pair" if in_pair else look["layout"]
    cls = "look" if in_pair else f'look look--{layout}' + (" look--flip" if look.get("flip") else "")
    x, y = look.get("pin", (50, 60))
    tag_side = " to-left" if x > 58 else ""
    swatch = f'<span class="swatch" style="--s:url(/assets/img/slab-{look["slab"]}.jpg)" aria-hidden="true"></span>'
    notes = "".join(f"<li>{t}</li>" for t in look["notes"])
    intro = (f'<p class="look-no" data-reveal><span>No. {n:02d}</span> {ROOM_LABEL[look["chapter"]]}</p>\n'
             f'      <h3 class="look-title" data-words>{look["title"]}</h3>\n'
             f'      <p class="look-text" data-reveal>{look["text"]}</p>')
    if layout == "wide":
        intro = f'<div class="look-intro">\n      {intro}\n      </div>'
    return f'''
  <article class="{cls}" id="{look["id"]}">
    <figure class="look-media" style="--ar:{look["ar"]}" data-wipe>
      {img_tag(look, SIZES[layout])}
      <button class="pin" type="button" style="--x:{x}%;--y:{y}%" aria-expanded="false" aria-controls="pin-{look["id"]}" aria-label="Show the surface in this photo" data-pin><i></i></button>
      <a class="pin-tag{tag_side}" id="pin-{look["id"]}" href="/#collections" style="--x:{x}%;--y:{y}%">{swatch}<span><b>{name}</b><small>{no}</small></span></a>
    </figure>
    <div class="look-body">
      {intro}
      <div class="look-notes" data-reveal>
        <h4>Styling notes</h4>
        <ol>{notes}</ol>
      </div>
      <dl class="look-spec" data-reveal>
        <div><dt>Surface</dt><dd><a href="/#collections">{swatch}<span><b>{name}</b> <small>{no}</small></span></a></dd></div>
        <div><dt>Edge</dt><dd>{look["edge"]}</dd></div>
        <div><dt>Pairs with</dt><dd>{look["pairs"]}</dd></div>
      </dl>
    </div>
  </article>'''


def chapter_html(ch, start):
    looks = [l for l in LOOKS if l["chapter"] == ch["id"]]
    parts, i, n = [], 0, start
    while i < len(looks):
        if looks[i]["layout"] == "pair" and i + 1 < len(looks) and looks[i + 1]["layout"] == "pair":
            parts.append('\n  <div class="look-pair">' + look_html(n, looks[i], True) + look_html(n + 1, looks[i + 1], True) + '\n  </div>')
            i += 2; n += 2
        else:
            parts.append(look_html(n, looks[i])); i += 1; n += 1
    return f'''
<!-- ============ {strip(ch["title"]).upper()} ============ -->
<section class="chapter chapter--{ch["tone"]}" id="{ch["id"]}" data-chapter data-tone="{ch["tone"]}" aria-labelledby="{ch["id"]}-title">
  <div class="wrap">
  <header class="chapter-head">
    <span class="chapter-no" aria-hidden="true" data-reveal>{ch["no"]}</span>
    <h2 id="{ch["id"]}-title" data-words>{ch["title"]}</h2>
    <p data-reveal>{ch["intro"]}</p>
  </header>{"".join(parts)}
  </div>
</section>''', n


def contents_html():
    out, n = [], 1
    for ch in CHAPTERS:
        rows = []
        for l in [l for l in LOOKS if l["chapter"] == ch["id"]]:
            peek = f'/assets/img/inspirations/{l["id"]}-{variants(l["id"])[0][0]}.webp'
            rows.append(f'<li><a href="#{l["id"]}" data-peek="{peek}"><span>{n:02d}</span><b>{strip(l["title"])}</b><small>{SLABS[l["slab"]][0].replace("Calacatta ", "")}</small></a></li>')
            n += 1
        out.append(f'<div class="contents-group" data-reveal><h2><i>{ch["no"]}</i>{strip(ch["title"])}</h2><ol>{"".join(rows)}</ol></div>')
    return "\n      ".join(out)


def build():
    chapters, n = [], 1
    for ch in CHAPTERS:
        s, n = chapter_html(ch, n)
        chapters.append(s)
    counts = {c["id"]: sum(1 for l in LOOKS if l["chapter"] == c["id"]) for c in CHAPTERS}
    chapbar = "".join(f'<a href="#{c["id"]}">{strip(c["title"])} <sup>{counts[c["id"]]:02d}</sup></a>' for c in CHAPTERS)
    surfaces = len({l["slab"] for l in LOOKS})
    rooms = len({l["id"] for l in LOOKS})
    page = TEMPLATE.format(contents=contents_html(), chapters="\n".join(chapters), chapbar=chapbar,
                           rooms=rooms, surfaces=surfaces, spaces=len(CHAPTERS))
    os.makedirs(os.path.join(ROOT, "inspirations"), exist_ok=True)
    with open(os.path.join(ROOT, "inspirations", "index.html"), "w", encoding="utf-8", newline="\n") as f:
        f.write(page)
    print("wrote inspirations/index.html,", rooms, "rooms")


TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>Inspirations — Columbia Quartz</title>
<meta name="description" content="Kitchens, baths, laundry rooms and fireplaces finished in Columbia quartz, with the surface, edge and styling notes for each look.">
<meta name="theme-color" content="#efe9e0">
<link rel="icon" type="image/png" href="/assets/img/icon-96.png">
<link rel="preload" as="font" type="font/woff2" crossorigin href="/assets/fonts/cormorant-garamond-latin-400-600.woff2">
<link rel="stylesheet" href="/assets/fonts/fonts.css">
<link rel="stylesheet" href="/assets/vendor/lenis.css">
<link rel="stylesheet" href="/assets/css/home.css?v=5">
<link rel="stylesheet" href="/assets/css/inspirations.css?v=1">
<script>
  /* Before first paint: hidden starting states exist only when motion is welcome. */
  (function (d) {{
    d.classList.add('js');
    if (!matchMedia('(prefers-reduced-motion: reduce)').matches) d.classList.add('motion');
  }})(document.documentElement);
</script>
</head>
<body class="insp">

<a class="skip" href="#kitchens">Skip to content</a>
<div class="progress" aria-hidden="true"><span></span></div>

<header class="site-head" data-head>
  <a class="brand" href="/" aria-label="Columbia Quartz, home">
    <img class="brand-logo brand-logo--light" src="/assets/img/logo-394.webp" alt="" width="197" height="147">
    <img class="brand-logo brand-logo--ink" src="/assets/img/logo-ink-394.webp" alt="" width="197" height="147">
  </a>
  <nav class="site-nav" id="site-nav" aria-label="Primary">
    <a href="/#collections">Collections</a>
    <a href="/inspirations/" aria-current="page">Inspirations</a>
    <a href="/#about">About Us</a>
    <a href="#contact">Contact</a>
    <a class="site-nav-cta" href="/#showroom">Find a Showroom</a>
  </nav>
  <a class="btn btn--line site-cta" href="/#showroom"><span>Find a Showroom</span></a>
  <button class="menu-btn" type="button" aria-expanded="false" aria-controls="site-nav" data-menu>
    <span class="menu-btn-label">Menu</span><span class="menu-btn-bars" aria-hidden="true"><i></i><i></i></span>
  </button>
</header>

<main>

<!-- ============ HERO / CONTENTS ============ -->
<section class="ix-hero" data-tone="paper">
  <div class="wrap">
    <div class="ix-intro">
      <p class="eyebrow eyebrow--gold rise" style="--d:.1s">Inspirations <span class="dot" aria-hidden="true"></span> The Lookbook</p>
      <h1 class="ix-title"><span class="focus" style="--d:.05s;display:block">Rooms worth</span> <em class="focus" style="--d:.2s;display:block">borrowing from.</em></h1>
      <p class="ix-lede rise" style="--d:.45s">Kitchens, baths and the rooms in between, each finished in a Columbia surface. Every look comes with the slab, the edge and a few styling notes so you can make it your own.</p>
      <div class="ix-count rise" style="--d:.6s">
        <div><b>{rooms}</b><span>Rooms</span></div>
        <div><b>{surfaces}</b><span>Surfaces</span></div>
        <div><b>{spaces}</b><span>Chapters</span></div>
      </div>
    </div>
    <nav class="contents" aria-label="All looks">
      {contents}
    </nav>
  </div>
</section>

<div class="lookbook">
<nav class="chapbar" aria-label="Chapters" data-chapbar>
  <div class="wrap chapbar-in">
    <span class="chapbar-label">The Lookbook</span>
    {chapbar}
  </div>
</nav>
{chapters}
</div>

<!-- ============ CLOSING ============ -->
<section class="ix-close" data-tone="ink">
  <img class="ix-close-bg" src="/assets/img/showroom.jpg" alt="" loading="lazy" width="1536" height="881" data-parallax="0.1">
  <div class="ix-close-veil" aria-hidden="true"></div>
  <div class="wrap ix-close-inner">
    <p class="eyebrow eyebrow--gold" data-reveal>Found your room?</p>
    <h2 class="sec-title sec-title--xl" data-words>Bring the look. <em>We&rsquo;ll pull the slab.</em></h2>
    <p data-reveal>Show us the room you saved and a showroom specialist will bring out the full slabs, so you can see the real veining, the edge and the color in daylight before anything is cut.</p>
    <div class="ix-close-actions" data-reveal>
      <a class="btn btn--solid btn--lg" href="/#showroom"><span>Find a Showroom</span></a>
      <a class="btn btn--line btn--lg" href="/#collections"><span>Explore Collections</span></a>
    </div>
  </div>
</section>

</main>

<!-- ============ FOOTER ============ -->
<footer class="site-foot" id="contact" data-tone="ink">
  <div class="wrap">
    <div class="foot-grid">
      <div class="foot-brand">
        <img src="/assets/img/logo-394.webp" alt="Columbia Quartz" width="160" height="119" loading="lazy">
        <p>Premium engineered quartz surfaces for kitchens, baths, and the rooms in between.</p>
      </div>
      <div class="foot-col">
        <h4>Explore</h4>
        <a href="/#collections">Collections</a>
        <a href="/inspirations/">Inspirations</a>
        <a href="#">Color Visualizer</a>
        <a href="#">Care &amp; Maintenance</a>
      </div>
      <div class="foot-col">
        <h4>Company</h4>
        <a href="/#about">About Us</a>
        <a href="#">Sustainability</a>
        <a href="/#showroom">Find a Showroom</a>
        <a href="#">Contact</a>
      </div>
      <div class="foot-col foot-news">
        <h4>Stay Inspired</h4>
        <p>New collections, design ideas, and showroom events, a few times a year.</p>
        <div class="news-row">
          <input type="email" placeholder="Email address" aria-label="Email address">
          <button type="button">Join</button>
        </div>
      </div>
    </div>
    <div class="foot-bottom">
      <span>&copy; 2026 Columbia Quartz. All rights reserved.</span>
      <div class="foot-social">
        <a href="#">Instagram</a>
        <a href="#">Pinterest</a>
        <a href="#">Houzz</a>
        <a href="#">LinkedIn</a>
      </div>
    </div>
  </div>
</footer>

<script src="/assets/vendor/lenis.min.js" defer></script>
<script src="/assets/js/inspirations.js?v=1" defer></script>
</body>
</html>
"""

if __name__ == "__main__":
    build()
