/* ─────────────────────────────────────────────────────────────────────────────
   Ciel Study — motion layer (every page; the home page gets the most)
   GSAP + ScrollTrigger + SplitText, Lenis for the wheel. All four are vendored in
   vendor/ — no CDN, nothing here phones anyone.

   ⚠ THE PAGE IS COMPLETE WITHOUT THIS FILE. Every word, number and link is in the
   HTML; this only decides how it arrives. Three ways it stands down:
     · prefers-reduced-motion → the gate in <head> never adds `.motion`
     · a library fails to load → `.motion` is removed here, nothing stays hidden
     · this file is slow       → the gate removes `.motion` itself after 3 s
   ⚠ sync_site.py rewrites the numbers in `.stat b`. The count-up reads its target
   out of that text and puts the exact string back at the end — it holds no
   number of its own.
   ───────────────────────────────────────────────────────────────────────────── */
(function () {
  var root = document.documentElement;
  if (!root.classList.contains('motion')) return;
  var gsap = window.gsap, ScrollTrigger = window.ScrollTrigger;
  if (!gsap || !ScrollTrigger) { root.classList.remove('motion'); return; }
  window.__cielMotion = true;

  try {
    gsap.registerPlugin(ScrollTrigger);
    if (window.SplitText) gsap.registerPlugin(window.SplitText);
    var all = function (sel, ctx) { return gsap.utils.toArray((ctx || document).querySelectorAll(sel)); };
    var desktop = window.matchMedia('(hover: hover) and (pointer: fine)').matches;

    /* ── Smooth wheel (desktop only; a phone keeps its own native scroll) ──── */
    /* A box with its own scrollbar (the fixes log) keeps its own wheel. */
    all('.log-scroll, .table-scroll').forEach(function (el) { el.setAttribute('data-lenis-prevent', ''); });
    if (desktop && window.Lenis) {
      var lenis = new window.Lenis({ lerp: 0.12, anchors: true });
      lenis.on('scroll', ScrollTrigger.update);
      gsap.ticker.add(function (t) { lenis.raf(t * 1000); });
      gsap.ticker.lagSmoothing(0);
    }

    /* ── Reading progress, a hairline over the header ──────────────────────── */
    var bar = document.createElement('div');
    bar.className = 'scroll-bar'; bar.setAttribute('aria-hidden', 'true');
    document.body.appendChild(bar);
    gsap.fromTo(bar, { scaleX: 0 }, { scaleX: 1, ease: 'none',
      scrollTrigger: { start: 0, end: 'max', scrub: 0.3 } });

    /* ── Hero ──────────────────────────────────────────────────────────────── */
    var isHome = !!document.querySelector('.hero');
    var hero = gsap.timeline({ defaults: { ease: 'power3.out' } });
    var h1 = document.querySelector('.hero h1');
    if (!isHome) {
      /* Inner pages: the title block arrives, nothing more. */
      hero.fromTo(all('.doc > h1, .doc > .updated'), { opacity: 0, y: 16 },
        { opacity: 1, y: 0, duration: 0.7, stagger: 0.08, clearProps: 'transform' }, 0.05);
    } else if (h1 && window.SplitText) {
      gsap.set(h1, { opacity: 1 });
      window.SplitText.create(h1, { type: 'lines', mask: 'lines', autoSplit: true,
        onSplit: function (self) {
          return gsap.from(self.lines, { yPercent: 105, duration: 0.9,
            ease: 'power4.out', stagger: 0.09 });
        } });
    } else if (h1) {
      hero.fromTo(h1, { opacity: 0, y: 20 }, { opacity: 1, y: 0, duration: 0.8 }, 0);
    }
    if (isHome) {
      hero.fromTo(all('.hero .eyebrow, .hero .sub, .hero .cta-row, .hero .cta-note'),
        { opacity: 0, y: 18 }, { opacity: 1, y: 0, duration: 0.7, stagger: 0.08 }, 0.25);
      hero.fromTo(all('.hero-media'), { opacity: 0, y: 26, scale: 0.965 },
        { opacity: 1, y: 0, scale: 1, duration: 1, clearProps: 'transform' }, 0.3);
    }

    /* ── Stat strip: count up to the number the page already carries ───────── */
    all('.stat b').forEach(function (el) {
      var txt = el.textContent, m = /^([\d,]+)(.*)$/.exec(txt.trim());
      if (!m) return;
      var target = parseInt(m[1].replace(/,/g, ''), 10), tail = m[2], o = { v: 0 };
      if (!target) return;
      gsap.to(o, { v: target, duration: 1.4, ease: 'power2.out',
        scrollTrigger: { trigger: el, start: 'top 92%', once: true },
        onUpdate: function () { el.textContent = Math.round(o.v).toLocaleString('en-US') + tail; },
        onComplete: function () { el.textContent = txt; } });
    });

    /* ── Sections arrive as you reach them ─────────────────────────────────── */
    /* ⚠ Only what is BELOW the screen at load is hidden and brought in. Anything
       already visible is left alone - hiding it now would be a flash, and on a
       policy page the top of the text must simply be there. */
    var fold = window.innerHeight * 0.95;
    function reveal(sel, y, each) {
      var els = all(sel).filter(function (el) {
        var r = el.getBoundingClientRect();
        return r.height > 0 && r.top > fold;
      });
      if (!els.length) return;
      gsap.set(els, { opacity: 0, y: y });
      ScrollTrigger.batch(els, { start: 'top 90%', once: true,
        onEnter: function (b) {
          gsap.to(b, { opacity: 1, y: 0, duration: 0.65, ease: 'power2.out',
            stagger: each, overwrite: true, clearProps: 'transform' });
        } });
    }
    if (isHome) {
      reveal('main > section:not(.hero) .wrap > .eyebrow, main > section:not(.hero) .wrap > h2,' +
             'main > section:not(.hero) .wrap > .lede, .demo-copy > *, .group-grid > div > *', 18, 0.07);
      reveal('.card', 24, 0.05);
      reveal('.step, .price-tile, .note, details.faq, .cta-band', 22, 0.07);
      reveal('li.exam-row, .milestone-band .wrap > ol.milestones > li, .group-list li', 14, 0.06);
    } else {
      /* A document page: each block of the text, as one piece. A grid is left
         whole and its cards come in instead, so nothing fades twice. */
      reveal('.doc > *:not(h1):not(.updated):not(.grid):not(.plans)', 12, 0.04);
      reveal('.doc > .grid > *, .doc > .plans > *', 20, 0.05);
    }

    /* ── Desktop: a light that follows the pointer, a button that leans in ─── */
    if (desktop) {
      all('.card, .plan, .price-tile').forEach(function (c) {
        c.addEventListener('pointermove', function (e) {
          var r = c.getBoundingClientRect();
          c.style.setProperty('--mx', (e.clientX - r.left) + 'px');
          c.style.setProperty('--my', (e.clientY - r.top) + 'px');
        });
      });
      all('.hero .btn-primary, .cta-band .btn-primary, .group-band .btn-primary').forEach(function (b) {
        b.classList.add('magnet');
        var x = gsap.quickTo(b, 'x', { duration: 0.35, ease: 'power3.out' });
        var y = gsap.quickTo(b, 'y', { duration: 0.35, ease: 'power3.out' });
        b.addEventListener('pointermove', function (e) {
          var r = b.getBoundingClientRect();
          x((e.clientX - r.left - r.width / 2) * 0.22);
          y((e.clientY - r.top - r.height / 2) * 0.3);
        });
        b.addEventListener('pointerleave', function () { x(0); y(0); });
      });
    }

    /* ── The demo: one real question, played as the bot sends it ───────────── */
    var screen = document.querySelector('.phone-screen');
    if (screen) {
      var q = function (s) { return screen.querySelector(s); };
      var rows = { ask: q('[data-d="ask"]'), keys: q('[data-d="keys"]'),
                   ans: q('[data-d="ans"]'), acts: q('[data-d="acts"]'), why: q('[data-d="why"]') };
      var pick = q('.kb-pick'), whyBtn = q('.kb-why');
      var pts = all('.demo-points li');
      var again = document.querySelector('.demo-replay');
      var stick = function () { screen.scrollTop = screen.scrollHeight; };
      var open = function (el, at) {
        return demo.fromTo(el, { height: 0, opacity: 0 },
          { height: 'auto', opacity: 1, duration: 0.55, ease: 'power2.out' }, at);
      };
      var tap = function (btn, at) {
        demo.fromTo(btn.querySelector('.tap'), { scale: 0.3, opacity: 0.9 },
          { scale: 1.9, opacity: 0, duration: 0.6, ease: 'power2.out' }, at);
        demo.fromTo(btn, { scale: 1 }, { scale: 0.95, duration: 0.12, yoyo: true, repeat: 1 }, at);
        demo.fromTo(btn, { backgroundColor: 'rgba(245,197,66,0)' },
          { backgroundColor: 'rgba(245,197,66,.2)', duration: 0.2 }, at);
      };

      root.classList.add('demo-live');
      var demo = gsap.timeline({ paused: true, onUpdate: stick,
        onComplete: function () { if (again) again.hidden = false; } });
      demo.fromTo(pts, { opacity: 0.4 }, { opacity: 0.4, duration: 0.01 }, 0);
      open(rows.ask, 0.1);
      open(rows.keys, '+=0.15');
      tap(pick, '+=0.9');
      demo.to(rows.keys, { height: 0, opacity: 0, duration: 0.3, ease: 'power2.in' }, '+=0.35');
      open(rows.ans, '+=0.05');
      demo.to(pts[0], { opacity: 1, duration: 0.4 }, '<');
      demo.fromTo(all('.revise', rows.ans), { opacity: 0, x: -10 },
        { opacity: 1, x: 0, duration: 0.5 }, '+=0.5');
      demo.to(pts[2], { opacity: 1, duration: 0.4 }, '<');
      open(rows.acts, '+=0.3');
      tap(whyBtn, '+=1.1');
      open(rows.why, '+=0.4');
      demo.to(pts[1], { opacity: 1, duration: 0.4 }, '<');

      ScrollTrigger.create({ trigger: '.phone', start: 'top 85%', once: true,
        onEnter: function () { demo.play(0); } });
      if (again) again.addEventListener('click', function () {
        again.hidden = true; demo.restart();
      });
    }

    ScrollTrigger.refresh();
  } catch (e) {
    /* Whatever went wrong, the reader gets the plain page. */
    root.classList.remove('motion', 'demo-live');
    try { gsap.set('main *', { clearProps: 'opacity,transform,height' }); } catch (_) {}
  }
})();
