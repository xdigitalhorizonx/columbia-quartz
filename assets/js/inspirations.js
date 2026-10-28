/* Columbia Quartz — Inspirations.
   Same motion language as the homepage (assets/js/home.js), minus the scene: masked word reveals,
   image wipes, Lenis, the header, plus this page's own pieces — the contents preview, the sticky
   chapter bar with scroll-spy, and the surface pins on each photo.
   html.motion (set before first paint) gates every animated state; without it the page is static. */
(() => {
  const html = document.documentElement;
  const MOTION = html.classList.contains('motion');
  const FINE = matchMedia('(hover: hover) and (pointer: fine)').matches;
  const clamp = (v, a = 0, b = 1) => Math.min(b, Math.max(a, v));

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
  }

  /* ---------- reveals on enter ---------- */
  if (MOTION) {
    document.querySelectorAll('[data-words]').forEach(splitWords);
    const io = new IntersectionObserver((entries) => entries.forEach((e) => {
      if (!e.isIntersecting) return;
      e.target.classList.add('is-in'); io.unobserve(e.target);
    }), { rootMargin: '0px 0px -8% 0px' });
    document.querySelectorAll('[data-reveal], [data-words], [data-wipe]').forEach((el) => io.observe(el));
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
  const chapbar = document.querySelector('[data-chapbar]');
  let menuOpen = false;
  function setMenu(open) {
    menuOpen = open;
    head.classList.toggle('menu-open', open);
    menuBtn.setAttribute('aria-expanded', String(open));
    if (lenis) open ? lenis.stop() : lenis.start();
    document.body.style.overflow = open ? 'hidden' : '';
  }
  menuBtn.addEventListener('click', () => setMenu(!menuOpen));

  // in-page links land below the chapter bar (and below the header when scrolling back up, where it reappears)
  document.querySelectorAll('a[href^="#"]').forEach((a) => a.addEventListener('click', (e) => {
    const id = a.getAttribute('href');
    const target = id.length > 1 && document.querySelector(id);
    if (!target) return;
    e.preventDefault();
    if (menuOpen) setMenu(false);
    const top = target.getBoundingClientRect().top + scrollY;
    const offset = chapbar.offsetHeight + (top < scrollY ? head.offsetHeight : 0) + 18;
    scrollToY(Math.max(0, top - offset));
    history.replaceState(null, '', id);
  }));

  /* ---------- contents: a cursor-following preview of each room ---------- */
  if (FINE) {
    const peek = document.createElement('div');
    peek.className = 'peek'; peek.setAttribute('aria-hidden', 'true');
    const peekImg = new Image(); peekImg.alt = ''; peek.appendChild(peekImg);
    document.body.appendChild(peek);
    const move = (e) => { peek.style.setProperty('--px', `${e.clientX + 28}px`); peek.style.setProperty('--py', `${e.clientY - 90}px`); };
    document.querySelectorAll('[data-peek]').forEach((a) => {
      a.addEventListener('pointerenter', (e) => { peekImg.src = a.dataset.peek; move(e); peek.classList.add('is-on'); });
      a.addEventListener('pointermove', move);
      a.addEventListener('pointerleave', () => peek.classList.remove('is-on'));
    });
  }

  /* ---------- surface pins ----------
     Hover previews the tag on fine pointers; a click (or tap, or Enter) pins it open until clicked again. */
  const pins = [...document.querySelectorAll('[data-pin]')];
  const setPin = (p, open, held = false) => { p.setAttribute('aria-expanded', String(open)); p.dataset.held = open && held ? '1' : ''; };
  const closePins = (except) => pins.forEach((p) => { if (p !== except) setPin(p, false); });
  pins.forEach((pin) => {
    pin.addEventListener('click', (e) => {
      e.stopPropagation();
      const open = pin.dataset.held !== '1';
      closePins(pin);
      setPin(pin, open, true);
    });
    if (FINE) {
      const media = pin.closest('.look-media');
      pin.addEventListener('pointerenter', () => { if (pin.dataset.held !== '1') { closePins(pin); setPin(pin, true); } });
      media.addEventListener('pointerleave', () => { if (pin.dataset.held !== '1') setPin(pin, false); });
    }
  });
  document.addEventListener('click', (e) => { if (!e.target.closest('.pin-tag')) closePins(); });
  addEventListener('keydown', (e) => {
    if (e.key !== 'Escape') return;
    if (menuOpen) { setMenu(false); menuBtn.focus(); }
    const open = pins.find((p) => p.getAttribute('aria-expanded') === 'true');
    if (open) { closePins(); open.focus(); }
  });

  /* ---------- parallax (closing image) ---------- */
  const parallax = MOTION ? [...document.querySelectorAll('[data-parallax]')] : [];
  function updateParallax() {
    const vh = innerHeight;
    parallax.forEach((img) => {
      const r = img.parentElement.getBoundingClientRect();
      if (r.bottom < -100 || r.top > vh + 100) return;
      const prog = clamp((r.top + r.height / 2 - vh / 2) / (vh / 2 + r.height / 2), -1, 1);
      img.style.transform = `translate3d(0, ${(prog * +img.dataset.parallax * 0.55 * r.height).toFixed(1)}px, 0)`;
    });
  }

  /* ---------- header state, chapter bar, scroll-spy ---------- */
  const toned = [...document.querySelectorAll('[data-tone]')];
  const chapters = [...document.querySelectorAll('[data-chapter]')];
  const chapLinks = new Map([...chapbar.querySelectorAll('a')].map((a) => [a.getAttribute('href').slice(1), a]));
  const toneAt = (y) => { const s = toned.find((el) => { const r = el.getBoundingClientRect(); return r.top <= y && r.bottom > y; }); return s && s.dataset.tone; };
  let lastY = scrollY, lastOn = null;
  function updateChrome() {
    const y = scrollY;
    head.classList.toggle('is-solid', y > 12);
    head.classList.toggle('is-dark', toneAt(head.offsetHeight / 2) === 'ink');
    if (!menuOpen && Math.abs(y - lastY) > 3) head.classList.toggle('is-hidden', y > lastY && y > 400);
    lastY = y;

    const barTop = chapbar.getBoundingClientRect().top;
    const stuck = barTop <= head.offsetHeight + 1;
    chapbar.classList.toggle('under-head', !head.classList.contains('is-hidden'));
    chapbar.classList.toggle('is-dark', stuck && toneAt(barTop + chapbar.offsetHeight / 2) === 'ink');

    const probe = barTop + chapbar.offsetHeight + innerHeight * 0.25;
    let on = null;
    chapters.forEach((c) => { if (c.getBoundingClientRect().top <= probe) on = c.id; });
    if (on !== lastOn) {
      chapLinks.forEach((a, id) => {
        a.classList.toggle('is-on', id === on);
        if (id === on) a.setAttribute('aria-current', 'location'); else a.removeAttribute('aria-current');
      });
      const active = chapLinks.get(on), strip = chapbar.firstElementChild;   // keep the live chapter in view on narrow bars
      if (active && strip.scrollWidth > strip.clientWidth) strip.scrollTo({ left: active.offsetLeft - 20, behavior: MOTION ? 'smooth' : 'auto' });
      lastOn = on;
    }
  }

  /* ---------- loop ---------- */
  const progressBar = document.querySelector('.progress');
  function frame(t) {
    if (lenis) lenis.raf(t);
    if (MOTION) updateParallax();
    updateChrome();
    progressBar.style.setProperty('--page', clamp(scrollY / Math.max(1, html.scrollHeight - innerHeight)).toFixed(4));
    requestAnimationFrame(frame);
  }
  html.classList.add('ready');
  requestAnimationFrame(frame);
})();
