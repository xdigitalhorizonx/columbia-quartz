/* Columbia Quartz homepage.
   One requestAnimationFrame loop drives everything (the digitalhorizon.dev pattern): the scrubbed
   plan-to-elevation frame sequence, story beats, veils, annotations, the scrubbed statement, parallax,
   the velocity marquee and the header. Lenis smooths wheel input and is built lazily.
   html.motion (set before first paint) gates every animated state; without it the page is static. */
(() => {
  const html = document.documentElement;
  const MOTION = html.classList.contains('motion');
  const FINE = matchMedia('(hover: hover) and (pointer: fine)').matches;
  const clamp = (v, a = 0, b = 1) => Math.min(b, Math.max(a, v));
  const smooth = (a, b, v) => { const t = clamp((v - a) / (b - a)); return t * t * (3 - 2 * t); };
  const damp = (c, t, rate, dt) => c + (t - c) * (1 - Math.exp(-rate * dt));
  const isTall = () => innerWidth / innerHeight < 0.9;
  const styleCache = new WeakMap();
  const setStyle = (el, prop, val) => {            // skip writes that would not change anything
    let c = styleCache.get(el); if (!c) styleCache.set(el, (c = {}));
    if (c[prop] === val) return; c[prop] = val; el.style[prop] = val;
  };

  /* ---------- masked words ---------- */
  function splitWords(el) {
    el.setAttribute('aria-label', el.textContent.trim().replace(/\s+/g, ' '));
    let i = 0;
    const walk = (node) => {
      [...node.childNodes].forEach((n) => {
        if (n.nodeType === 3) {
          const frag = document.createDocumentFragment();
          n.textContent.split(/(\s+)/).forEach((part) => {
            if (!part) return;
            if (/^\s+$/.test(part)) { frag.appendChild(document.createTextNode(' ')); return; }
            const w = document.createElement('span'); w.className = 'w'; w.setAttribute('aria-hidden', 'true');
            const wi = document.createElement('span'); wi.className = 'wi'; wi.textContent = part;
            wi.style.setProperty('--i', i++);
            w.appendChild(wi); frag.appendChild(w);
          });
          n.replaceWith(frag);
        } else if (n.nodeType === 1 && n.tagName !== 'BR') walk(n);
      });
    };
    walk(el);
    return [...el.querySelectorAll('.wi')];
  }

  /* ---------- reveals on enter ---------- */
  if (MOTION) {
    document.querySelectorAll('[data-words]').forEach(splitWords);
    const io = new IntersectionObserver((entries) => entries.forEach((e) => {
      if (!e.isIntersecting) return;
      e.target.classList.add('is-in'); io.unobserve(e.target);
    }), { rootMargin: '0px 0px -6% 0px' });
    document.querySelectorAll('[data-reveal], [data-words]').forEach((el) => io.observe(el));
  }

  /* ---------- Lenis, built on idle or first input ---------- */
  let lenis = null;
  function startLenis() {
    if (lenis || !MOTION || !window.Lenis) return;
    lenis = new window.Lenis({ duration: 1.15, easing: (t) => Math.min(1, 1.001 - Math.pow(2, -10 * t)) });
    if (menuOpen) lenis.stop();
  }
  if (MOTION) {
    ['wheel', 'touchstart', 'keydown', 'pointerdown'].forEach((ev) => addEventListener(ev, startLenis, { once: true, passive: true }));
    (window.requestIdleCallback || ((f) => setTimeout(f, 1200)))(startLenis, { timeout: 2000 });
  }
  const scrollToY = (y) => {
    if (lenis) lenis.scrollTo(y, { duration: 1.4 });
    else scrollTo({ top: y, behavior: MOTION ? 'smooth' : 'auto' });
  };

  /* ---------- header + menu ---------- */
  const head = document.querySelector('[data-head]');
  const menuBtn = document.querySelector('[data-menu]');
  let menuOpen = false;
  function setMenu(open) {
    menuOpen = open;
    head.classList.toggle('menu-open', open);
    menuBtn.setAttribute('aria-expanded', String(open));
    if (lenis) open ? lenis.stop() : lenis.start();
    document.body.style.overflow = open ? 'hidden' : '';
  }
  menuBtn.addEventListener('click', () => setMenu(!menuOpen));
  addEventListener('keydown', (e) => { if (e.key === 'Escape' && menuOpen) { setMenu(false); menuBtn.focus(); } });

  document.querySelectorAll('a[href^="#"]').forEach((a) => a.addEventListener('click', (e) => {
    const id = a.getAttribute('href');
    if (id === '#') return;
    const target = document.querySelector(id);
    if (!target) return;
    e.preventDefault();
    if (menuOpen) setMenu(false);
    scrollToY(target.getBoundingClientRect().top + scrollY);
    history.replaceState(null, '', id);
  }));

  /* ---------- the scene ---------- */
  const scene = document.querySelector('[data-scene]');
  const pin = scene.querySelector('.scene-pin');
  const canvas = scene.querySelector('.scene-canvas');
  const ctx = canvas.getContext('2d', { alpha: false });
  const planStill = scene.querySelector('.scene-still--plan');
  const planVeil = scene.querySelector('.plan-veil');
  const elevLayer = scene.querySelector('.scene-layer--elev');
  const beats = [...scene.querySelectorAll('[data-beat]')].map((el) => ({
    el, a: +el.dataset.in, b: +el.dataset.out,
    parts: [...el.querySelectorAll('[data-part]')], hero: el.classList.contains('beat--hero'),
  }));

  // Choreography (scene progress 0..1). The camera starts moving with the first scroll: the plan still
  // hands over to the clip at once, and the move lands on the elevation still, where the finale and the
  // edge callouts hold.
  const CAM_A = 0.02, CAM_B = 0.5;
  const PLAN_OUT = [0.01, 0.025], ELEV_IN = [0.49, 0.52];
  const SHADE_OUT = [0, 0.12], DARK_IN = [0.48, 0.58];
  const LINES_IN = [0.58, 0.66], LABELS_IN = [0.62, 0.7];
  const BEAT_IN = 0.035, BEAT_OUT = 0.03, PART_STAGGER = 0.01, PART_RISE = 16;

  // Frames arrive as encoded blobs (~7 MB for the whole wide set). Only a small window around the
  // playhead is decoded, off the main thread, into canvas-sized ImageBitmaps, so a draw is a plain blit.
  const N = +canvas.dataset.frames;
  const SRC = { wide: canvas.dataset.sizeWide.split('x').map(Number), tall: canvas.dataset.sizeTall.split('x').map(Number) };
  const WINDOW = 7, MAX_DECODES = 1;   // one decode at a time: parallel decodes hitch the main thread on the short, fast move
  const SAVE_DATA = !!(navigator.connection && navigator.connection.saveData);   // keep the two stills, skip the sequence
  let tall = isTall();
  let blobs = [], bitmaps = new Map(), decoding = new Set(), loadGen = 0, bmpGen = 0, loadingStarted = false;
  let curF = 0, lastDrawn = -1, needsDraw = true, canvasReady = false, cw = 0, ch = 0, crop = [0, 0, 1, 1];

  function frameOrder() {                    // coarse to fine, so scrubbing works before everything lands
    const order = [0, N - 1], seen = new Set(order);
    for (let s = 32; s >= 1; s >>= 1) for (let i = 0; i < N; i += s) if (!seen.has(i)) { seen.add(i); order.push(i); }
    return order;
  }
  function loadFrames() {
    loadingStarted = true;
    if (SAVE_DATA) return;
    const gen = ++loadGen, dir = tall ? canvas.dataset.framesTall : canvas.dataset.framesWide;
    blobs = new Array(N); dropBitmaps();
    const queue = frameOrder(); let active = 0;
    const pump = () => {
      while (active < 6 && queue.length) {
        const i = queue.shift(); active++;
        fetch(`${dir}${String(i).padStart(3, '0')}.webp?v=${canvas.dataset.rev}`).then((r) => (r.ok ? r.blob() : null)).then((b) => {
          if (gen === loadGen && b) blobs[i] = b;
        }).catch(() => {}).finally(() => { active--; if (gen === loadGen) pump(); });
      }
    };
    pump();
  }
  function dropBitmaps() {
    bmpGen++; bitmaps.forEach((b) => b.close()); bitmaps.clear(); decoding.clear();
    lastDrawn = -1; needsDraw = true; canvasReady = false;
  }
  function sizeCanvas() {
    const w = pin.clientWidth, h = pin.clientHeight, [iw, ih] = tall ? SRC.tall : SRC.wide;
    const s = Math.max(w / iw, h / ih);                         // CSS px per source px (cover)
    const scale = Math.min(window.devicePixelRatio || 1, 2, 1 / s); // never upsample in the backing store
    cw = Math.round(w * scale); ch = Math.round(h * scale);
    canvas.width = cw; canvas.height = ch;
    const sw = w / s, sh = h / s; crop = [(iw - sw) / 2, (ih - sh) / 2, sw, sh];
    dropBitmaps();
  }
  function decodeAround(center) {
    const g = bmpGen;
    for (let d = 0; d <= WINDOW && decoding.size < MAX_DECODES; d++) {
      for (const i of d ? [center + d, center - d] : [center]) {
        if (i < 0 || i >= N || !blobs[i] || bitmaps.has(i) || decoding.has(i) || decoding.size >= MAX_DECODES) continue;
        decoding.add(i);
        createImageBitmap(blobs[i], crop[0], crop[1], crop[2], crop[3], { resizeWidth: cw, resizeHeight: ch, resizeQuality: 'high' })
          .then((bmp) => { if (g !== bmpGen) return bmp.close(); bitmaps.set(i, bmp); needsDraw = true; })
          .catch(() => {}).finally(() => decoding.delete(i));
      }
    }
    bitmaps.forEach((b, i) => { if (Math.abs(i - center) > WINDOW + 2) { b.close(); bitmaps.delete(i); } });
  }
  function drawFrame(idx) {
    decodeAround(idx);
    let j = -1;
    for (let d = 0; d < N && j < 0; d++) { if (bitmaps.has(idx - d)) j = idx - d; else if (bitmaps.has(idx + d)) j = idx + d; }
    if (j < 0 || (j === lastDrawn && !needsDraw)) return;
    ctx.drawImage(bitmaps.get(j), 0, 0);
    lastDrawn = j; needsDraw = false; canvasReady = true;
  }

  /* annotation callouts, placed in elevation-image coordinates (fractions of the 16:9 master) */
  const notesEl = scene.querySelector('[data-notes]');
  const notesSvg = notesEl.querySelector('svg');
  const noteLabels = Object.fromEntries([...notesEl.querySelectorAll('[data-note]')].map((n) => [n.dataset.note, n]));
  const TALL_CROP = { c: 0.38, w: 1 / 3 };   // the portrait stills/frames are this crop of the master
  const NOTES = {
    wide: { thickness: { x: 0.12, y0: 0.597, y1: 0.718 }, vein: { x: 0.445, y: 0.606, ex: 0.5, ey: 0.535 } },
    tall: { thickness: { x: 0.3, y0: 0.597, y1: 0.718 }, vein: null },
  };
  let notePaths = [];
  function layoutNotes() {
    const W = pin.clientWidth, H = pin.clientHeight;
    const aspect = tall ? (5504 * TALL_CROP.w) / 3072 : 5504 / 3072;
    const dw = W / H > aspect ? W : H * aspect, dh = dw / aspect;
    const ox = (W - dw) / 2, oy = (H - dh) / 2;
    const P = (x, y) => [ox + (tall ? (x - TALL_CROP.c + TALL_CROP.w / 2) / TALL_CROP.w : x) * dw, oy + y * dh];
    const cfg = tall ? NOTES.tall : NOTES.wide;
    let svg = '';
    const t = cfg.thickness, [tx, ty0] = P(t.x, t.y0), [, ty1] = P(t.x, t.y1);
    svg += `<path d="M${tx - 6} ${ty0}H${tx + 6}M${tx} ${ty0}V${ty1}M${tx - 6} ${ty1}H${tx + 6}"/>`;
    place(noteLabels.thickness, tx + 16, (ty0 + ty1) / 2, 'left');
    if (cfg.vein) {
      const v = cfg.vein, [vx, vy] = P(v.x, v.y), [ex, ey] = P(v.ex, v.ey);
      svg += `<circle class="ring" cx="${vx}" cy="${vy}" r="9"/><circle cx="${vx}" cy="${vy}" r="2.5"/>`;
      svg += `<path d="M${vx} ${vy}L${ex} ${ey}H${ex + 18}"/>`;
      place(noteLabels.vein, ex + 22, ey, 'left');
      noteLabels.vein.hidden = false;
    } else noteLabels.vein.hidden = true;
    notesSvg.setAttribute('viewBox', `0 0 ${W} ${H}`);
    notesSvg.innerHTML = svg;
    notePaths = [...notesSvg.querySelectorAll('path, circle')].map((el) => {
      const len = el.tagName === 'path' ? el.getTotalLength() : 0;
      if (len) { el.style.strokeDasharray = len; el.style.strokeDashoffset = len; }
      return { el, len };
    });
  }
  function place(label, x, y, side) {
    const r = label.getBoundingClientRect();
    label.style.transform = `translate3d(${Math.round(side === 'left' ? x : x - r.width)}px, ${Math.round(y - r.height / 2)}px, 0)`;
  }

  let sceneP = -1;
  function updateScene(dt) {
    const r = scene.getBoundingClientRect(), vh = innerHeight;
    if (r.bottom < 0 || r.top > vh) return;
    const p = clamp(-r.top / Math.max(1, r.height - vh));
    const c = clamp((p - CAM_A) / (CAM_B - CAM_A));
    const target = smooth(0, 1, c) * (N - 1);   // frames are spaced by camera motion; ease the ends
    curF = Math.abs(target - curF) > N / 3 ? target : damp(curF, target, 16, dt);
    if (!loadingStarted && p > 0) loadFrames();
    drawFrame(Math.round(curF));

    if (p === sceneP && !needsDraw) return;
    sceneP = p;
    setStyle(planStill, 'opacity', canvasReady ? String(1 - smooth(PLAN_OUT[0], PLAN_OUT[1], p)) : '1');
    setStyle(elevLayer, 'opacity', String(smooth(ELEV_IN[0], ELEV_IN[1], p)));
    setStyle(planVeil, 'opacity', (1 - smooth(SHADE_OUT[0], SHADE_OUT[1], p)).toFixed(3));
    pin.style.setProperty('--veil', smooth(DARK_IN[0], DARK_IN[1], p).toFixed(3));

    for (const bt of beats) {
      if (bt.hero) {
        const out = smooth(0, bt.b, p);
        setStyle(bt.el, 'transform', `translate3d(0, ${(-90 * out).toFixed(1)}px, 0)`);
        setStyle(bt.el, 'opacity', String(clamp(1 - 1.15 * out)));
        bt.el.inert = out > 0.98;
        continue;
      }
      let any = 0;
      bt.parts.forEach((el, k) => {
        const vin = smooth(bt.a + k * PART_STAGGER, bt.a + k * PART_STAGGER + BEAT_IN, p);
        const vout = smooth(bt.b - BEAT_OUT, bt.b, p);
        const v = vin * (1 - vout); any = Math.max(any, v);
        setStyle(el, 'opacity', v.toFixed(3));
        setStyle(el, 'transform', `translate3d(0, ${((1 - vin) * PART_RISE - vout * PART_RISE).toFixed(1)}px, 0)`);
      });
      bt.el.inert = any < 0.02;
    }

    const ln = smooth(LINES_IN[0], LINES_IN[1], p), lb = smooth(LABELS_IN[0], LABELS_IN[1], p);
    notePaths.forEach(({ el, len }) => {
      if (len) setStyle(el, 'strokeDashoffset', String(len * (1 - ln)));
      else setStyle(el, 'opacity', String(ln));
    });
    Object.values(noteLabels).forEach((l) => setStyle(l, 'opacity', String(lb)));
  }

  /* ---------- scrubbed statement ---------- */
  const statement = document.querySelector('.statement');
  const scrubWords = MOTION ? splitWords(statement.querySelector('[data-scrub]')) : [];
  function updateStatement() {
    if (!scrubWords.length) return;
    const r = statement.getBoundingClientRect(), vh = innerHeight;
    if (r.bottom < 0 || r.top > vh) return;
    const p = clamp((vh * 0.85 - r.top) / (vh * 1.2));   // fills while the section arrives, then holds
    const n = scrubWords.length;
    scrubWords.forEach((w, i) => {
      const e = clamp((p - (i / n) * 0.6) / 0.3);
      setStyle(w, 'transform', `translate3d(0, ${((1 - e * (2 - e)) * 112).toFixed(1)}%, 0)`);
    });
  }

  /* ---------- parallax ---------- */
  const parallax = new Set();
  if (MOTION) {
    const pio = new IntersectionObserver((es) => es.forEach((e) => (e.isIntersecting ? parallax.add(e.target) : parallax.delete(e.target))), { rootMargin: '20% 0px' });
    document.querySelectorAll('[data-parallax]').forEach((img) => pio.observe(img));
  }
  function updateParallax() {
    const vh = innerHeight;
    parallax.forEach((img) => {
      const r = img.parentElement.getBoundingClientRect();
      const prog = clamp((r.top + r.height / 2 - vh / 2) / (vh / 2 + r.height / 2), -1, 1);
      setStyle(img, 'transform', `translate3d(0, ${(prog * +img.dataset.parallax * 0.55 * r.height).toFixed(1)}px, 0)`);
    });
  }

  /* ---------- velocity marquee ---------- */
  const marquee = document.querySelector('[data-marquee]');
  const track = marquee.querySelector('.marquee-track');
  const marqueeToggle = marquee.querySelector('[data-marquee-toggle]');
  let mx = 0, skew = 0, half = 0, marqueeOn = false, paused = false;
  if (MOTION) {
    track.append(...[...track.children].map((n) => n.cloneNode(true)));
    new IntersectionObserver(([e]) => { marqueeOn = e.isIntersecting; }).observe(marquee);
  }
  marqueeToggle.addEventListener('click', () => {
    paused = !paused;
    html.classList.toggle('paused', paused);
    marqueeToggle.setAttribute('aria-pressed', String(paused));
    marqueeToggle.textContent = paused ? 'Play motion' : 'Pause motion';
  });
  function updateMarquee(dt, velocity) {
    if (!MOTION || !marqueeOn) return;
    if (!half) half = track.scrollWidth / 2;
    const speed = paused ? 0 : 38 + Math.min(Math.abs(velocity) * 9, 520);
    mx -= speed * dt; if (-mx >= half) mx += half;
    skew = paused ? damp(skew, 0, 8, dt) : skew + (clamp(velocity * -0.55, -9, 9) - skew) * 0.12;
    setStyle(track, 'transform', `translate3d(${mx.toFixed(1)}px, 0, 0) skewX(${skew.toFixed(2)}deg)`);
  }

  /* ---------- magnetic buttons + lit card borders ---------- */
  if (MOTION && FINE) {
    document.querySelectorAll('[data-magnetic]').forEach((el) => {
      el.addEventListener('pointermove', (e) => {
        const r = el.getBoundingClientRect();
        el.style.transform = `translate3d(${((e.clientX - r.left - r.width / 2) * 0.32).toFixed(1)}px, ${((e.clientY - r.top - r.height / 2) * 0.32).toFixed(1)}px, 0)`;
      });
      el.addEventListener('pointerleave', () => { el.style.transform = ''; });
    });
  }
  if (FINE) {
    document.querySelectorAll('[data-spotlight]').forEach((grid) => {
      const cards = [...grid.children]; let raf = 0, ex = 0, ey = 0;
      grid.addEventListener('pointermove', (e) => {
        ex = e.clientX; ey = e.clientY;
        if (raf) return;
        raf = requestAnimationFrame(() => {
          raf = 0;
          cards.forEach((c) => { const r = c.getBoundingClientRect(); c.style.setProperty('--mx', `${ex - r.left}px`); c.style.setProperty('--my', `${ey - r.top}px`); });
        });
      });
      grid.addEventListener('pointerleave', () => cards.forEach((c) => { c.style.setProperty('--mx', '-999px'); c.style.setProperty('--my', '-999px'); }));
    });
  }

  /* ---------- header state ---------- */
  const toned = [...document.querySelectorAll('[data-tone]')];
  let lastY = scrollY;
  function updateHead() {
    const y = scrollY, pinnedUntil = scene.offsetTop + scene.offsetHeight - innerHeight;
    if (MOTION ? y < pinnedUntil + 4 : y < 8) {   // the static layout scrolls like any other section
      head.classList.remove('is-solid', 'is-paper', 'is-hidden');
      head.dataset.on = 'dark';   // the whole scene carries cream copy on shade
    } else {
      head.classList.add('is-solid');
      head.dataset.on = '';
      const probe = head.offsetHeight / 2;
      const under = toned.find((s) => { const r = s.getBoundingClientRect(); return r.top <= probe && r.bottom > probe; });
      head.classList.toggle('is-paper', !!under && under.dataset.tone === 'paper');
      if (!menuOpen && Math.abs(y - lastY) > 3) head.classList.toggle('is-hidden', y > lastY && y > pinnedUntil + 200);
    }
    lastY = y;
  }

  /* ---------- loop ---------- */
  const progressBar = document.querySelector('.progress');
  let lastT = performance.now(), lastScroll = scrollY;
  function frame(t) {
    const dt = Math.min(0.1, (t - lastT) / 1000); lastT = t;
    if (lenis) lenis.raf(t);
    const y = scrollY;
    const velocity = lenis ? lenis.velocity : (y - lastScroll) / Math.max(dt * 60, 1e-3);
    lastScroll = y;
    if (MOTION) {
      updateScene(dt);
      updateStatement();
      updateParallax();
      updateMarquee(dt, velocity);
    }
    updateHead();
    progressBar.style.setProperty('--page', clamp(y / Math.max(1, html.scrollHeight - innerHeight)).toFixed(4));
    requestAnimationFrame(frame);
  }

  function onResize() {
    const nowTall = isTall();
    if (MOTION) {
      if (nowTall !== tall) { tall = nowTall; sizeCanvas(); if (loadingStarted) loadFrames(); } else sizeCanvas(); layoutNotes(); half = 0; sceneP = -1;
    }
  }
  let rz = 0;
  addEventListener('resize', () => { clearTimeout(rz); rz = setTimeout(onResize, 120); });

  if (MOTION) {
    sizeCanvas();
    document.fonts.ready.then(layoutNotes);
    layoutNotes();
    // frames start after the hero has painted, or as soon as the visitor scrolls
    const kick = () => { if (!loadingStarted) loadFrames(); };
    if (document.readyState === 'complete') setTimeout(kick, 300); else addEventListener('load', () => setTimeout(kick, 300), { once: true });
  }
  html.classList.add('ready');
  requestAnimationFrame(frame);
})();
