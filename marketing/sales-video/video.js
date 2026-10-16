// PaperDrop sales video. Everything is a pure function of time so any frame can be
// rendered deterministically: window.seek(t) draws the frame at t seconds.
const FPS = 30, BEAT = 0.5, DURATION = 62;
const CUES = []; // sound effects, read by scripts/make_audio.py
const cue = (t, type, extra = {}) => CUES.push({ t: +t.toFixed(3), type, ...extra });

const $ = s => document.querySelector(s);
const $$ = s => [...document.querySelectorAll(s)];
const clamp = (v, a = 0, b = 1) => Math.min(b, Math.max(a, v));
const prog = (t, a, b) => clamp((t - a) / (b - a));
const lerp = (a, b, p) => a + (b - a) * p;
const E = {
  outBack: p => { const c1 = 2.2, c3 = c1 + 1; return 1 + c3 * Math.pow(p - 1, 3) + c1 * Math.pow(p - 1, 2); },
  outCubic: p => 1 - Math.pow(1 - p, 3),
  inCubic: p => p * p * p,
  inOutCubic: p => p < .5 ? 4 * p * p * p : 1 - Math.pow(-2 * p + 2, 3) / 2,
  outElastic: p => p === 0 ? 0 : p === 1 ? 1 : Math.pow(2, -10 * p) * Math.sin((p * 10 - .75) * (2 * Math.PI / 3)) + 1,
};
const steps = (p, n) => Math.floor(p * n) / n;
// Stop-motion "boil": a jitter that only changes 8 times a second, like the website's float-stepped.
const boil = (t, seed = 0, amp = 1) => Math.sin((Math.floor(t * 8) + seed * 13.7) * 12.9898) * amp;

function tf(el, { x = 0, y = 0, s = 1, sx = 1, sy = 1, r = 0, o = 1 } = {}) {
  el.style.transform = `translate(${x}px,${y}px) rotate(${r}deg) scale(${s * sx},${s * sy})`;
  el.style.opacity = o;
}
// Pop: scale from 0 with overshoot, plus a tiny boil afterwards.
function pop(el, t, t0, { d = .34, from = 0, r = 0, seed = 0, x = 0, y = 0, amp = 1 } = {}) {
  const p = prog(t, t0, t0 + d);
  const s = p <= 0 ? from : lerp(from, 1, E.outBack(p));
  tf(el, { s, x, y, r: r + (p >= 1 ? boil(t, seed, amp) : 0), o: p <= 0 && from === 0 ? 0 : 1 });
}
// Slide in from an offset with overshoot.
function slide(el, t, t0, { d = .4, dx = 0, dy = 0, r = 0, seed = 0, amp = .8 } = {}) {
  const p = E.outBack(prog(t, t0, t0 + d));
  tf(el, { x: dx * (1 - p), y: dy * (1 - p), r: r + boil(t, seed, amp), o: t < t0 ? 0 : 1 });
}
const show = (el, on) => { el.style.display = on ? '' : 'none'; };

// ---- Icons ---------------------------------------------------------------
for (const el of $$('[data-icon]')) {
  const stroke = el.dataset.stroke || '#3D405B';
  el.innerHTML = `<svg viewBox="0 0 24 24" fill="none" stroke="${stroke}" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round">${ICONS[el.dataset.icon]}</svg>`;
}

// ---- Printer helper --------------------------------------------------------
// Paper feeds out in 24 hard steps (stop-motion thermal feed) between t0 and t1.
const printers = {};
function printer(id) {
  if (!printers[id]) {
    const root = $('#' + id);
    printers[id] = { root, wrap: root.querySelector('.wrap'), paper: root.querySelector('.paper'), eyes: [...root.querySelectorAll('.eyes i')], lamp: root.querySelector('.lamp'), body: root.querySelector('.body') };
  }
  return printers[id];
}
function runPrinter(id, t, { appear = 0, t0, t1, seed = 0 }) {
  const P = printer(id);
  pop(P.root, t, appear, { d: .4, seed, amp: .8 });
  const full = P.paper.offsetHeight;
  const p = prog(t, t0, t1);
  P.wrap.style.height = (steps(p, 24) * full) + 'px';
  // Body shudders while printing, eyes blink now and then.
  const printing = t > t0 && t < t1;
  P.body.style.transform = printing ? `translate(${boil(t * 3, seed, 3)}px, ${Math.abs(boil(t * 3, seed + 1, 3))}px)` : '';
  const blink = ((t + seed) % 2.3) < .1;
  P.eyes.forEach(e => e.style.transform = `scaleY(${blink ? .15 : 1})`);
  P.lamp.style.background = printing ? (Math.floor(t * 8) % 2 ? '#E07A5F' : '#F2CC8F') : '#81B29A';
}

// ---- Scenes ---------------------------------------------------------------
const scenes = [];
function scene(id, start, end, update) { scenes.push({ el: $('#' + id), start, end, update }); }

// 1 · HOOK 0–4
{
  const words = $$('#hook-title .w');
  const squig = $('#hook-squiggle path');
  cue(0.15, 'pop'); cue(0.6, 'print', { d: 1.5 });
  [1.0, 1.5, 2.0].forEach(t => cue(t, 'pop'));
  cue(2.9, 'ding');
  scene('s-hook', 0, 4, t => {
    runPrinter('hook-printer', t, { appear: .1, t0: .6, t1: 2.1 });
    pop($('#hook-tag'), t, .3, { r: -3, seed: 1 });
    words.forEach((w, i) => pop(w, t, 1.0 + i * .5, { d: .3, seed: i + 2, amp: .6 }));
    squig.style.strokeDasharray = 1; squig.style.strokeDashoffset = 1 - E.outCubic(prog(t, 2.25, 2.7));
    slide($('#hook-sub'), t, 2.9, { dy: 60, seed: 4, amp: .3 });
  });
}

// 2 · KICKER 4–8
{
  const w = $$('#kick-l1 .w');
  cue(4.0, 'whoosh');
  [4.5, 4.75, 5.0, 5.25, 5.5].forEach(t => cue(t, 'pop'));
  cue(6.0, 'sparkle'); cue(6.0, 'hit');
  scene('s-kick', 4, 8, (t) => {
    slide($('#kick-logo'), t, 0, { dy: -500, d: .5, seed: 1, amp: 1 });
    w.forEach((el, i) => pop(el, t, .5 + i * .25, { d: .25, seed: i, amp: 1.2 }));
    const l2 = $('#kick-l2'); const p = prog(t, 2.0, 2.4);
    tf(l2, { s: t < 2 ? 0 : lerp(2.4, 1, E.outBack(p)), r: -3 + boil(t, 9, 1.6), o: t < 2 ? 0 : 1 });
    ['#kick-sp1', '#kick-sp2', '#kick-sp3'].forEach((s, i) => {
      const el = $(s); const q = prog(t, 2.1 + i * .15, 2.5 + i * .15);
      tf(el, { s: E.outBack(q) * (1 + .12 * Math.sin(t * 9 + i)), r: t * 90 * (i % 2 ? -1 : 1), o: q > 0 ? 1 : 0 });
    });
  });
}

// 3 · VOICE 8–16
{
  const typed = 'A snail delivering a love letter!';
  cue(8.6, 'beep'); cue(8.6, 'pop'); cue(9.6, 'pop'); cue(10.6, 'pop'); cue(11.9, 'pop'); cue(12.7, 'pop'); cue(12.7, 'ding');
  cue(13.0, 'print', { d: 2.0 }); cue(15.1, 'stamp');
  const bars = $$('#v-wave i');
  scene('s-voice', 8, 16, (t) => {
    pop($('#v-tag'), t, .05, { r: -2, seed: 1 });
    slide($('#v-title'), t, .15, { dx: -900, seed: 2, amp: .4 });
    pop($('#v-b1'), t, .6, { seed: 3, amp: .5 });
    bars.forEach((b, i) => b.style.height = (t > .6 && t < 1.8 ? 14 + Math.abs(Math.sin(Math.floor(t * 12) * 1.7 + i * 1.3)) * 40 : 14) + 'px');
    pop($('#v-b2'), t, 1.6, { seed: 4, amp: .5 });
    pop($('#v-b3'), t, 2.6, { seed: 5, amp: .5 });
    $('#v-typed').textContent = typed.slice(0, Math.round(prog(t, 2.7, 3.7) * typed.length)) || ' ';
    pop($('#v-b4'), t, 3.9, { seed: 6, amp: .5 });
    pop($('#v-b5'), t, 4.7, { seed: 7, amp: 1.5, d: .3 });
    runPrinter('v-printer', t, { appear: .3, t0: 5.0, t1: 7.0, seed: 1 });
    const sp = prog(t, 7.1, 7.35);
    tf($('#v-stamp'), { s: t < 7.1 ? 0 : lerp(2.2, 1, E.outCubic(sp)), r: -6 + boil(t, 3, .6), o: t < 7.1 ? 0 : 1 });
  });
}

// 4 · ANYTHING 16–20: one word per beat
{
  const slams = [0, 1, 2, 3, 4, 5].map(i => $('#slam-' + i));
  slams.forEach((_, i) => { cue(16 + i * .5, 'hit'); cue(16 + i * .5, 'scribble', { d: .4 }); });
  cue(19.0, 'whoosh');
  scene('s-any', 16, 20, (t) => {
    const i = Math.floor(t / .5);
    slams.forEach((el, k) => {
      show(el, k === i && t < 3); el.style.display = (k === i && t < 3) ? 'flex' : 'none';
      if (k !== i) return;
      const lt = t - k * .5;
      const word = el.querySelector('.word');
      tf(word, { s: lerp(1.5, 1, E.outCubic(prog(lt, 0, .18))), r: (k % 2 ? 3 : -3) + boil(t, k, 1), x: lerp(-60, 0, E.outCubic(prog(lt, 0, .2))) });
      el.querySelectorAll('.doodle [pathLength]').forEach(p => { p.style.strokeDasharray = 1; p.style.strokeDashoffset = 1 - E.outCubic(prog(lt, .02, .4)); });
      tf(el.querySelector('.doodle'), { r: boil(t, k + 3, 2), s: lerp(.7, 1, E.outBack(prog(lt, 0, .25))) });
    });
    const last = $('#slam-6'); last.style.display = t >= 3 ? 'block' : 'none';
    if (t >= 3) {
      const lt = t - 3;
      tf(last.querySelector('.h2'), { s: lerp(1.25, 1, E.outCubic(prog(lt, 0, .2))), o: 1 });
      const p = prog(lt, 0, 1);
      tf($('#any-rocket'), { x: lerp(-620, 2000, E.inOutCubic(p)), y: -Math.sin(p * Math.PI) * 120, r: lerp(-14, 10, p) + boil(t, 1, 1.5) });
    }
  });
}

// 5 · PRINT STYLES 20–26
{
  const styles = ['photo', 'vintage', 'newspaper', 'comic', 'none'];
  const names = ['Photo', 'Vintage', 'Newspaper', 'Comic', 'B&W'];
  const chips = $$('#st-chips .chip');
  const imgs = $$('.st-i'), scan = $('#st-scan'), nameEl = $('#st-name');
  const switchAt = k => 1.0 + k * .9;
  styles.forEach((_, k) => { cue(20 + switchAt(k), 'click'); cue(20 + switchAt(k) + .02, 'print', { d: .35 }); });
  scene('s-style', 20, 26, (t) => {
    slide($('#st-title'), t, .05, { dx: -900, seed: 1, amp: .3 });
    slide($('#st-sub'), t, .35, { dy: 80, seed: 2, amp: .2 });
    slide($('#st-phone'), t, .15, { dy: 900, r: 2, seed: 3, amp: .5 });
    let k = -1; styles.forEach((_, i) => { if (t >= switchAt(i)) k = i; });
    chips.forEach((c, i) => {
      c.classList.toggle('on', i === k);
      const pp = prog(t, switchAt(i), switchAt(i) + .2);
      c.style.transform = i === k ? `scale(${lerp(1.25, 1.06, E.outCubic(pp))}) rotate(${boil(t, i, 1.5)}deg)` : 'none';
    });
    // Image 0 is the original; image k+1 is style k. The new style "prints" over the previous one.
    imgs.forEach((im, i) => {
      if (i === k + 1) { const sp = steps(prog(t, switchAt(k), switchAt(k) + .4), 12); im.style.display = ''; im.style.clipPath = `inset(0 0 ${100 - sp * 100}% 0)`; im.style.zIndex = 2;
        scan.style.top = (sp * 530) + 'px'; scan.style.opacity = sp > 0 && sp < 1 ? 1 : 0; }
      else if (i === k) { im.style.display = ''; im.style.clipPath = 'none'; im.style.zIndex = 1; }
      else im.style.display = 'none';
    });
    if (k < 0) { scan.style.opacity = 0; nameEl.style.opacity = 0; return; }
    nameEl.textContent = names[k];
    tf(nameEl, { s: lerp(1.4, 1, E.outBack(prog(t, switchAt(k), switchAt(k) + .25))), r: -4 + boil(t, k, 1.4) });
  });
}

// 6 · FAMILY MAIL 26–34
{
  const paths = [0, 1, 2].map(i => $('#mp' + i));
  const envs = [0, 1, 2].map(i => $('#env' + i));
  const flights = [[.9, 1.7], [1.5, 2.3], [2.1, 2.9]];
  flights.forEach(([a]) => cue(26 + a, 'whoosh'));
  flights.forEach(([, b]) => cue(26 + b, 'pop'));
  cue(29.6, 'whoosh'); [30.0, 30.3, 30.6].forEach(t => cue(t, 'pop'));
  cue(31.0, 'print', { d: 1.8 }); cue(32.3, 'pop'); cue(32.8, 'pop');
  scene('s-mail', 26, 34, (t) => {
    const phaseB = t >= 3.6;
    show($('#mail-a'), !phaseB); show($('#mail-b'), phaseB);
    if (!phaseB) {
      slide($('#mail-title'), t, .05, { dx: -900, seed: 1, amp: .3 });
      slide($('#mail-sub'), t, .4, { dy: 80, seed: 2, amp: .2 });
      [['#h-lis', -4, .15], ['#h-ohi', 3, .3], ['#h-dus', 5, .45]].forEach(([s, r, t0], i) => pop($(s), t, t0, { r, seed: i + 3 }));
      paths.forEach((p, i) => { p.style.opacity = t > flights[i][0] - .2 ? 1 : 0; p.style.strokeDashoffset = -t * 60; });
      envs.forEach((e, i) => {
        const [a, b] = flights[i]; const p = E.inOutCubic(prog(t, a, b));
        const L = paths[i].getTotalLength(); const pt = paths[i].getPointAtLength(p * L);
        e.style.left = pt.x + 'px'; e.style.top = pt.y + 'px';
        const arrived = t > b;
        tf(e, { s: t < a ? 0 : arrived ? lerp(1.3, 0, E.inCubic(prog(t, b, b + .35))) : 1, r: boil(t, i, 6), o: t < a || t > b + .35 ? 0 : 1 });
      });
    } else {
      const lt = t - 3.6;
      slide($('#inbox'), lt, 0, { dx: -1100, seed: 1, amp: .3 });
      [0, 1, 2].forEach(i => pop($('#r' + i), lt, .4 + i * .3, { from: .6, seed: i + 2, amp: .2 }));
      const bd = $('#inbox-badge'); const bounce = Math.max(0, Math.sin((lt % 1) * Math.PI * 4)) * (lt % 1 < .5 ? 1 : 0);
      bd.style.transform = `translateY(${-bounce * 16}px) rotate(${boil(t, 5, 6)}deg)`;
      runPrinter('mail-printer', lt, { appear: .2, t0: 1.4, t1: 3.2, seed: 2 });
      slide($('#mp-0'), lt, 2.7, { dx: -1200, seed: 6, amp: .2 });
      slide($('#mp-1'), lt, 3.2, { dx: -1200, seed: 7, amp: .2 });
    }
  });
}

// 7 · KID DECK 34–39
{
  const keys = [0, 1, 2, 3, 4, 5].map(i => $('#k' + i));
  keys.forEach((_, i) => cue(34.3 + i * .12, 'tick'));
  cue(35.6, 'pop'); cue(36.2, 'pop'); cue(36.9, 'click'); cue(36.95, 'beep'); cue(37.7, 'scribble', { d: .7 }); cue(38.4, 'ding');
  scene('s-deck', 34, 39, (t) => {
    slide($('#deck-title'), t, .05, { dx: -1400, seed: 1, amp: .3 });
    slide($('#deck'), t, .1, { dy: 800, seed: 2, amp: .25 });
    keys.forEach((k, i) => { const p = prog(t, .3 + i * .12, .55 + i * .12); k.style.filter = `brightness(${lerp(.25, 1, p)})`; k.style.transform = `scale(${lerp(.85, 1, E.outBack(p))})`; });
    const b = $('#k0b'); const lb = (t * 1) % 4; const bounce = lb < .6 ? Math.abs(Math.sin(lb / .6 * Math.PI * 2)) : 0;
    b.style.transform = `translateY(${-bounce * 14}px)`;
    pop($('#c0'), t, 1.6, { r: -3, seed: 3 }); pop($('#c1'), t, 2.2, { r: 2, seed: 4 });
    // Tap on Draw & Print → red (listening) → pencil (drawing) → green check.
    const k5 = keys[5], ic = $('#k5i'), lab = $('#k5l');
    const tap = $('#tap'); const tp = prog(t, 2.9, 3.3);
    tap.style.left = (530 + 60 + 2 * (246.7 + 40) + 123) + 'px'; tap.style.top = (390 + 56 + 252 + 40 + 126) + 'px';
    tf(tap, { s: lerp(.4, 1.8, tp), o: tp > 0 && tp < 1 ? 1 - tp : 0 });
    let state = t < 2.9 ? 0 : t < 3.7 ? 1 : t < 4.4 ? 2 : 3;
    const bg = ['var(--mustard)', '#E5484D', 'var(--mustard)', 'var(--sage)'][state];
    k5.style.background = bg;
    const icon = ['Pencil', 'Mic', 'Pencil', 'Check'][state];
    if (ic.dataset.icon !== icon) { ic.dataset.icon = icon; ic.innerHTML = `<svg viewBox="0 0 24 24" fill="none" stroke="${state === 0 || state === 2 ? '#3D405B' : '#fff'}" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round">${ICONS[icon]}</svg>`; }
    lab.textContent = ['Draw & Print', 'Talk!', 'Drawing…', 'Printing!'][state];
    ic.style.transform = state === 1 ? `scale(${1 + .1 * Math.sin(t * 20)})` : state === 2 ? `translateX(${Math.sin(t * 12) * 40}px) rotate(${Math.sin(t * 24) * 12}deg)` : state === 3 ? `scale(${lerp(.4, 1, E.outBack(prog(t, 4.4, 4.7)))})` : 'none';
    if (t > 2.9) k5.style.transform = `scale(${t < 3.05 ? .9 : 1})`;
    pop($('#c2'), t, 3.0, { r: -2, seed: 5 });
  });
}

// 8 · GAMES 39–47
{
  const Q = ['I have whiskers and I say meow. What am I?', 'J’ai des moustaches et je fais miaou. Qui suis-je ?', 'Ich habe Schnurrhaare und sage miau. Wer bin ich?', 'Ho i baffi e faccio miao. Chi sono?', 'Tenho bigodes e faço miau. Quem sou eu?'];
  const starSVG = '<svg viewBox="0 0 144 144"><path d="m72 9 19 39 43 6-31 30 7 44-38-21-38 21 7-44L10 54l43-6Z" fill="#fff" stroke="#3D405B" stroke-width="8" stroke-linejoin="round"/></svg>';
  $('#g-stars').innerHTML = starSVG.repeat(5);
  const stars = $$('#g-stars svg');
  const starAt = [3.5, 3.9, 4.2, 4.5, 4.8];
  [0, 1, 2, 3].forEach(i => cue(39.25 + i * .15, 'pop'));
  cue(40.3, 'whoosh'); [0, 1, 2, 3, 4].forEach(i => cue(40.6 + i * .5, 'tick'));
  cue(42.2, 'buzz'); cue(42.5, 'click');
  starAt.forEach(a => cue(39 + a, 'sparkle'));
  cue(44.05, 'hit'); cue(44.3, 'print', { d: 1.4 }); cue(45.9, 'pop'); cue(46.2, 'pop');
  scene('s-games', 39, 47, (t) => {
    slide($('#g-title'), t, .05, { dx: -1500, seed: 1, amp: .3 });
    const tilesOn = t < 1.4;
    show($('#g-tiles'), tilesOn);
    [0, 1, 2, 3].forEach(i => pop($('#gt' + i), t, .25 + i * .15, { r: [-3, 2, -2, 3][i], seed: i + 2 }));
    const qOn = t >= 1.3 && t < 5.0;
    show($('#g-q'), qOn); show($('#g-langs'), qOn); show($('#g-stars'), t >= 1.3);
    if (qOn) {
      slide($('#g-q'), t, 1.3, { dy: 380, seed: 5, amp: .25 });
      slide($('#g-langs'), t, 1.5, { dy: 300, seed: 6, amp: .2 });
      const li = clamp(Math.floor((t - 1.6) / .5), 0, 4);
      $('#g-qtext').textContent = Q[li];
      $$('#g-langs .lang').forEach((l, i) => l.classList.toggle('on', i === li));
      // Wrong answer is gently set aside (no star lost), the right one celebrated.
      const dog = $('#ga0'), cat = $('#ga1');
      const wrong = t >= 3.2;
      dog.style.opacity = wrong ? .35 : 1;
      dog.style.transform = t > 3.2 && t < 3.5 ? `translateX(${Math.sin(t * 60) * 10}px)` : 'none';
      const right = t >= 3.5;
      cat.style.background = right ? 'var(--sage)' : 'var(--cream)';
      cat.style.transform = right ? `scale(${lerp(1.3, 1.08, E.outBack(prog(t, 3.5, 3.8)))}) rotate(${boil(t, 2, 2)}deg)` : 'none';
    }
    $('#g-stars').style.left = (t < 5.0 ? 1190 : 120) + 'px';
    $('#g-stars').style.top = (t < 5.0 ? 400 : 420) + 'px';
    stars.forEach((s, i) => {
      const on = t >= starAt[i];
      s.querySelector('path').setAttribute('fill', on ? '#F2CC8F' : '#fff');
      const p = prog(t, starAt[i], starAt[i] + .3);
      s.style.transform = `scale(${on ? lerp(1.6, 1, E.outBack(p)) : .9}) rotate(${on ? lerp(-70, 0, E.outCubic(p)) + boil(t, i, 3) : 0}deg)`;
    });
    show($('#g-five'), t >= 5.0);
    $('#g-five').style.left = '120px'; $('#g-five').style.top = '580px';
    if (t >= 5.0) tf($('#g-five'), { s: lerp(2, 1, E.outBack(prog(t, 5.0, 5.3))), r: -3 + boil(t, 3, 1.5) });
    show($('#g-prizes'), t >= 5.0); show($('#g-cap'), t >= 6.5);
    if (t >= 5.0) {
      // Prize card feeds out in hard steps, then the collection fans out behind it.
      const fp = steps(prog(t, 5.3, 6.7), 20);
      $('#gp0').style.clipPath = `inset(0 0 ${100 - fp * 100}% 0)`;
      tf($('#gp0'), { r: -4 + boil(t, 1, .8), y: lerp(-400, 0, E.outCubic(prog(t, 5.0, 5.3))) });
      tf($('#gp1'), { x: lerp(-60, 150, E.outBack(prog(t, 6.9, 7.2))), r: lerp(-4, 6, prog(t, 6.9, 7.2)) + boil(t, 2, .8), o: t > 6.9 ? 1 : 0 });
      tf($('#gp2'), { x: lerp(-120, 270, E.outBack(prog(t, 7.2, 7.5))), r: lerp(-4, 14, prog(t, 7.2, 7.5)) + boil(t, 3, .8), o: t > 7.2 ? 1 : 0 });
      slide($('#g-cap'), t, 6.5, { dy: 120, seed: 9, amp: .2 });
    }
  });
}

// 9 · RELIABILITY 47–52
{
  [0, 1, 2, 3, 4, 5].forEach(i => cue(47.5 + i * .5, 'stamp'));
  cue(48.6, 'print', { d: 1.6 });
  scene('s-rel', 47, 52, (t) => {
    slide($('#rel-title'), t, .05, { dx: -1300, seed: 1, amp: .3 });
    [0, 1, 2, 3, 4, 5].forEach(i => {
      const el = $('#ck' + i); const t0 = .5 + i * .5; const p = prog(t, t0, t0 + .22);
      tf(el, { x: lerp(-80, 0, E.outCubic(p)), s: t < t0 ? 1 : lerp(1.15, 1, E.outBack(p)), o: t < t0 ? 0 : 1, r: boil(t, i, .25) });
      el.querySelector('.ci').style.transform = `scale(${lerp(0, 1, E.outBack(p))})`;
    });
    runPrinter('rel-printer', t, { appear: .3, t0: 1.6, t1: 3.2, seed: 3 });
  });
}

// 10 · NO INK 52–55
{
  cue(52.0, 'hit'); cue(53.0, 'hit'); cue(54.3, 'riser', { d: .7 });
  scene('s-ink', 52, 55, (t) => {
    tf($('#ink-1'), { s: t < 0 ? 0 : lerp(2.2, 1, E.outCubic(prog(t, 0, .2))), r: boil(t, 1, 1.2) });
    tf($('#ink-2'), { s: t < 1 ? 0 : lerp(2.6, 1, E.outBack(prog(t, 1, 1.3))), r: -5 + boil(t, 2, 2), o: t < 1 ? 0 : 1 });
  });
}

// 11 · CTA 55–62
{
  const scraps = [
    ['Love you!', 120, 90, -8], ['Good luck today!', 1460, 70, 6], ['Bonjour Mamie!', 1500, 930, -5], ['Dinner at 7', 150, 900, 7],
    ['5 stars!', 1660, 380, -10], ['Miss you xx', 1200, 960, 3],
  ];
  $('#cta-scraps').innerHTML = scraps.map(([s, x, y, r], i) => `<div class="scrap" id="sc${i}" style="left:${x}px;top:${y}px">${s}</div>`).join('');
  cue(55.0, 'hit'); cue(55.2, 'pop'); cue(55.6, 'pop'); cue(56.1, 'pop'); cue(56.7, 'click'); cue(57.0, 'ding');
  scraps.forEach((_, i) => cue(55.3 + i * .18, 'tick'));
  scene('s-cta', 55, 62, (t) => {
    const m = $('#cta-mascot'); const p = prog(t, .1, .5);
    const hop = Math.abs(Math.sin(Math.max(0, t - .5) * Math.PI * 2)) * 30 * Math.exp(-Math.max(0, t - .5) * .4);
    tf(m, { y: lerp(-900, 0, E.outBack(p)) - hop, sy: 1 - .06 * (hop < 3 && t > .5 ? 1 : 0), r: boil(t, 1, 2.2) });
    pop($('#cta-logo'), t, .2, { seed: 2, amp: .5 });
    slide($('#cta-h'), t, .6, { dy: 160, seed: 3, amp: .5 });
    pop($('#cta-btn'), t, 1.1, { seed: 4, amp: .5, r: -1 });
    const press = t > 1.7 && t < 1.9;
    $('#cta-btn .cta').style.transform = press ? 'translate(8px,8px)' : 'none';
    $('#cta-btn .cta').style.boxShadow = press ? '4px 4px 0 var(--coral)' : '12px 12px 0 var(--coral)';
    slide($('#cta-url'), t, 2.0, { dy: 200, seed: 5, amp: .3 });
    scraps.forEach(([, , , r], i) => pop($('#sc' + i), t, .3 + i * .18, { r, seed: i + 7, amp: 1.5 }));
  });
}

// ---- Transitions: torn-paper wipes at section changes --------------------
const WIPES = [[8, '#3D405B'], [20, '#E07A5F'], [26, '#F2CC8F'], [34, '#3D405B'], [39, '#FAF9F6'], [47, '#E07A5F'], [55, '#3D405B']];
WIPES.forEach(([b]) => cue(b - .25, 'whoosh'));
{
  // Jagged leading/trailing edges, fixed once so they don't flicker.
  let d = 'M120 0 ', y = 0, k = 0;
  while (y < 1120) { y += 40; d += `L${120 + (k++ % 2 ? -40 : 30) + ((k * 37) % 25)} ${y} `; }
  d += 'L2280 1120 '; y = 1120; k = 0;
  while (y > 0) { y -= 40; d += `L${2280 + (k++ % 2 ? 40 : -30) - ((k * 53) % 25)} ${y} `; }
  $('#wipe-path').setAttribute('d', d + 'Z');
}
function wipe(t) {
  const w = $('#wipe');
  for (const [b, color] of WIPES) {
    const p = prog(t, b - .3, b + .3);
    if (p > 0 && p < 1) {
      w.style.display = 'block';
      $('#wipe-path').setAttribute('fill', color);
      w.style.transform = `translateX(${lerp(1920, -2400, E.inOutCubic(p))}px)`;
      return;
    }
  }
  w.style.display = 'none';
}

// ---- Frame -----------------------------------------------------------------
function seek(t) {
  for (const s of scenes) {
    const on = t >= s.start && t < s.end;
    s.el.style.display = on ? 'block' : 'none';
    if (on) s.update(t - s.start, t);
  }
  wipe(t);
  // Beat bump: the whole picture breathes on every kick (not during the quiet "No ink" break).
  const quiet = t >= 52 && t < 55;
  const ph = t % BEAT;
  const bump = quiet || t < 2 ? 0 : .012 * Math.exp(-ph * 12);
  $('#cam').style.transform = `scale(${1 + bump})`;
  // White flash on big hits.
  const hits = [6.0, 52.0, 53.0, 55.0];
  let f = 0; for (const h of hits) if (t >= h) f = Math.max(f, .55 * Math.exp(-(t - h) * 14));
  $('#flash').style.opacity = f;
  // Fade to the end card's last frame.
  $('#stage').style.filter = t > DURATION - .6 ? `brightness(${lerp(1, .0, prog(t, DURATION - .6, DURATION))})` : '';
}

window.seek = seek;
window.CUES = CUES.sort((a, b) => a.t - b.t);
window.VIDEO = { FPS, DURATION };
window.READY = document.fonts.ready.then(() => Promise.all([...document.images].map(i => i.complete ? 1 : new Promise(r => { i.onload = i.onerror = r; }))));

// Live preview when opened in a browser: ?t=12 seeks, otherwise plays in real time.
if (!navigator.webdriver) {
  const q = new URLSearchParams(location.search);
  if (q.has('t')) seek(+q.get('t'));
  else { const t0 = performance.now(); const tick = () => { seek(((performance.now() - t0) / 1000) % DURATION); requestAnimationFrame(tick); }; tick(); }
}
