/* ===================================================
   LogosDepth — Scripture memorization (verses)
   Steps: Read -> Fill In -> Order -> Recall
   =================================================== */

const VERSE_PROGRESS_KEY = 'ld_verse_progress';
const VERSE_XP_KEY       = 'ld_verse_xp';
const VERSE_STREAK_KEY   = 'ld_verse_streak';
const XP_PER_LEVEL       = 100;

const VERSE_STEPS = [
  { id: 'read',  label: 'Read' },
  { id: 'fill1', label: 'Fill In', pct: 0.25 },
  { id: 'order', label: 'Order' },
  { id: 'fill2', label: 'Recall',  pct: 0.7 },
];

const CHEERS  = ['Nice!', 'Great job!', 'You\'re getting it!', 'Well done!', 'Keep it up!'];
const NUDGES  = ['Not quite — try another one!', 'Almost! Look at the sentence again.', 'Close! Give it another go.'];

let verseList = [];
let vs = null; // current practice session

// ─── Storage (always optional) ───────────────────────
function vLoad(key, fallback) {
  try { const v = JSON.parse(localStorage.getItem(key)); return v ?? fallback; } catch { return fallback; }
}
function vSave(key, val) {
  try { localStorage.setItem(key, JSON.stringify(val)); } catch {}
}

// ─── Text helpers ────────────────────────────────────
const TOKEN_RE = /^([^\p{L}\p{N}]*)(.*?)([^\p{L}\p{N}]*)$/u;

function tokenize(text) {
  return text.split(/\s+/).filter(Boolean).map(raw => {
    const m = raw.match(TOKEN_RE);
    return { raw, pre: m[1], core: m[2], post: m[3], key: m[2].toLowerCase() };
  });
}

function normUnit(s) {
  return s.toLowerCase().replace(/[^\p{L}\p{N}]/gu, '');
}

function shuffle(arr) {
  const a = arr.slice();
  for (let i = a.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [a[i], a[j]] = [a[j], a[i]];
  }
  return a;
}

function pick(arr) { return arr[Math.floor(Math.random() * arr.length)]; }

// Longer words are blanked first; they carry more meaning than "the" or "of".
function pickBlanks(tokens, pct) {
  const long = [], short = [];
  tokens.forEach((t, i) => (t.core.length >= 4 ? long : short).push(i));
  const want = Math.min(tokens.length, Math.max(2, Math.round(tokens.length * pct)));
  return shuffle(long).concat(shuffle(short)).slice(0, want).sort((a, b) => a - b);
}

// Short verses are ordered word by word; long ones phrase by phrase.
function makeUnits(tokens) {
  const raws = tokens.map(t => t.raw);
  if (raws.length <= 14) return raws;

  const chunks = [];
  let cur = [];
  raws.forEach(w => {
    cur.push(w);
    if (/[,;:.?!]$/.test(w)) { chunks.push(cur); cur = []; }
  });
  if (cur.length) chunks.push(cur);

  const split = c => {
    if (c.length <= 8) return [c];
    const mid = Math.ceil(c.length / 2);
    return [...split(c.slice(0, mid)), ...split(c.slice(mid))];
  };
  return chunks.flatMap(split).map(c => c.join(' '));
}

function difficultyOf(text) {
  const n = text.split(/\s+/).length;
  return n <= 10 ? 'Starter' : n <= 20 ? 'Steady' : 'Challenge';
}

// ─── Progress / XP / streak ──────────────────────────
function getXp() { return vLoad(VERSE_XP_KEY, 0); }

function bumpDailyStreak() {
  const today     = new Date().toLocaleDateString('en-CA');
  const yesterday = new Date(Date.now() - 864e5).toLocaleDateString('en-CA');
  const s = vLoad(VERSE_STREAK_KEY, { last: '', count: 0 });
  if (s.last === today) return s;
  const next = { last: today, count: s.last === yesterday ? s.count + 1 : 1 };
  vSave(VERSE_STREAK_KEY, next);
  return next;
}

function currentStreak() {
  const s = vLoad(VERSE_STREAK_KEY, { last: '', count: 0 });
  const today     = new Date().toLocaleDateString('en-CA');
  const yesterday = new Date(Date.now() - 864e5).toLocaleDateString('en-CA');
  return (s.last === today || s.last === yesterday) ? s.count : 0;
}

// ─── Load + picker ───────────────────────────────────
document.addEventListener('DOMContentLoaded', loadVerses);

async function loadVerses() {
  try {
    const res = await fetch('/api/verses');
    verseList = await res.json();
    renderPicker();
  } catch {
    document.getElementById('verseGrid').textContent = 'Could not load verses. Is the server running?';
  }
}

function renderPicker() {
  const progress = vLoad(VERSE_PROGRESS_KEY, {});
  const xp       = getXp();
  const level    = Math.floor(xp / XP_PER_LEVEL) + 1;
  const into     = xp % XP_PER_LEVEL;

  document.getElementById('vLevel').textContent    = `Level ${level}`;
  document.getElementById('vXpLabel').textContent  = `${into} / ${XP_PER_LEVEL} XP`;
  document.getElementById('vXpFill').style.width   = `${into}%`;
  document.getElementById('vStreak').textContent   = currentStreak();
  document.getElementById('vMastered').textContent =
    `${verseList.filter(v => (progress[v.ref] || 0) >= 3).length}/${verseList.length}`;

  const todayIdx = verseList.length ? Math.floor(Date.now() / 864e5) % verseList.length : -1;
  const grid = document.getElementById('verseGrid');
  grid.innerHTML = '';

  verseList.forEach((v, i) => {
    const stars = progress[v.ref] || 0;
    const card = document.createElement('button');
    card.className = 'verse-card';

    const top = document.createElement('div');
    top.className = 'verse-card-top';
    const ref = document.createElement('span');
    ref.className = 'verse-card-ref';
    ref.textContent = v.ref;
    const diff = document.createElement('span');
    diff.className = `verse-diff verse-diff-${difficultyOf(v.text).toLowerCase()}`;
    diff.textContent = difficultyOf(v.text);
    top.append(ref, diff);

    const preview = document.createElement('div');
    preview.className = 'verse-card-preview';
    preview.textContent = v.text.split(/\s+/).slice(0, 7).join(' ') + '…';

    const foot = document.createElement('div');
    foot.className = 'verse-card-foot';
    const starEl = document.createElement('span');
    starEl.className = 'verse-stars';
    starEl.textContent = '★'.repeat(stars) + '☆'.repeat(3 - stars);
    starEl.setAttribute('aria-label', `${stars} of 3 stars`);
    foot.append(starEl);
    if (i === todayIdx) {
      const tag = document.createElement('span');
      tag.className = 'verse-today';
      tag.textContent = '✦ Today\'s pick';
      foot.append(tag);
    }

    card.append(top, preview, foot);
    card.onclick = () => startVerse(v.ref);
    grid.appendChild(card);
  });
}

// ─── Session ─────────────────────────────────────────
function showVersePanel(name) {
  ['vPicker', 'vSession', 'vResult'].forEach(id =>
    document.getElementById(id).classList.toggle('hidden', id !== name));
}

function startVerse(ref) {
  const verse = verseList.find(v => v.ref === ref);
  if (!verse) return;
  vs = { verse, tokens: tokenize(verse.text), step: 0, mistakes: 0, hints: 0 };
  showVersePanel('vSession');
  document.getElementById('vsRef').textContent = verse.ref;
  renderStep();
  window.scrollTo({ top: 0 });
}

function exitVerse() {
  vs = null;
  renderPicker();
  showVersePanel('vPicker');
}

function retryVerse() { if (vs) startVerse(vs.verse.ref); }

function nextVerse() {
  const progress = vLoad(VERSE_PROGRESS_KEY, {});
  const idx = verseList.findIndex(v => v.ref === vs.verse.ref);
  const order = verseList.slice(idx + 1).concat(verseList.slice(0, idx + 1));
  const next = order.find(v => (progress[v.ref] || 0) < 3) || order[0];
  startVerse(next.ref);
}

function renderSteps() {
  const wrap = document.getElementById('vsSteps');
  wrap.innerHTML = '';
  VERSE_STEPS.forEach((s, i) => {
    const el = document.createElement('span');
    el.className = 'vs-step' + (i < vs.step ? ' done' : i === vs.step ? ' current' : '');
    el.textContent = `${i + 1}. ${s.label}`;
    wrap.appendChild(el);
  });
}

function setMsg(text, kind) {
  const el = document.getElementById('vsMsg');
  el.textContent = text || '';
  el.className = 'vs-msg' + (kind ? ` ${kind}` : '');
}

function addButton(parent, label, cls, onClick) {
  const b = document.createElement('button');
  b.className = cls;
  b.textContent = label;
  b.onclick = onClick;
  parent.appendChild(b);
  return b;
}

function renderStep() {
  renderSteps();
  setMsg('');
  document.getElementById('vsBank').innerHTML = '';
  document.getElementById('vsActions').innerHTML = '';
  document.getElementById('vsText').className = 'vs-text';

  const step = VERSE_STEPS[vs.step];
  if (step.id === 'read')  renderRead();
  else if (step.id === 'order') renderOrder();
  else renderFill(step.pct);
}

function advanceStep() {
  vs.step++;
  if (vs.step >= VERSE_STEPS.length) finishVerse();
  else renderStep();
}

// Shown after each interactive step is complete.
function stepDone() {
  setMsg(pick(CHEERS) + ' Step complete ✓', 'good');
  const actions = document.getElementById('vsActions');
  actions.innerHTML = '';
  document.getElementById('vsBank').innerHTML = '';
  const last = vs.step === VERSE_STEPS.length - 1;
  addButton(actions, last ? 'Finish ✦' : 'Next step →', 'gs-start-btn', advanceStep);
}

function shake(el) {
  el.classList.remove('shake');
  void el.offsetWidth; // restart the animation
  el.classList.add('shake');
}

// ── Step: Read ──
function renderRead() {
  document.getElementById('vsInstruction').textContent =
    'Read the verse slowly, out loud if you can. When you feel ready, we\'ll play with it.';
  const text = document.getElementById('vsText');
  text.className = 'vs-text vs-text-read';
  text.textContent = vs.verse.text;

  const actions = document.getElementById('vsActions');
  if ('speechSynthesis' in window) {
    addButton(actions, '🔊 Listen', 'gd-back-btn', () => {
      try {
        speechSynthesis.cancel();
        const u = new SpeechSynthesisUtterance(vs.verse.text);
        u.rate = 0.85;
        speechSynthesis.speak(u);
      } catch {}
    });
  }
  addButton(actions, 'I\'ve read it →', 'gs-start-btn', () => {
    try { speechSynthesis.cancel(); } catch {}
    advanceStep();
  });
}

// ── Step: Fill in the blanks ──
function renderFill(pct) {
  document.getElementById('vsInstruction').textContent =
    'Tap the word that belongs in the highlighted blank.';
  const blanks = pickBlanks(vs.tokens, pct);
  vs.fill = {
    blanks: new Set(blanks),
    order: blanks,
    filled: new Set(),
    active: blanks[0],
    bank: shuffle(blanks.map(i => ({ key: vs.tokens[i].key, text: vs.tokens[i].core }))),
  };
  drawFill();

  addButton(document.getElementById('vsActions'), '💡 Hint', 'gd-back-btn', fillHint);
}

function drawFill() {
  const f = vs.fill;
  const text = document.getElementById('vsText');
  text.innerHTML = '';

  vs.tokens.forEach((t, i) => {
    const part = document.createElement('span');
    part.className = 'vs-word';
    if (f.blanks.has(i)) {
      part.append(t.pre);
      const slot = document.createElement('button');
      const filled = f.filled.has(i);
      slot.className = 'vslot' + (filled ? ' filled' : '') + (i === f.active ? ' active' : '');
      slot.style.minWidth = `${Math.max(2.2, t.core.length * 0.62)}em`;
      slot.textContent = filled ? t.core : '';
      slot.setAttribute('aria-label', filled ? t.core : 'blank');
      if (!filled) slot.onclick = () => { f.active = i; drawFill(); };
      part.append(slot, t.post);
    } else {
      part.textContent = t.raw;
    }
    text.append(part, ' ');
  });

  const bank = document.getElementById('vsBank');
  bank.innerHTML = '';
  f.bank.forEach(chip => {
    const b = document.createElement('button');
    b.className = 'vchip';
    b.textContent = chip.text;
    b.onclick = () => pickFillChip(chip, b);
    bank.appendChild(b);
  });
}

function fillActive(chip) {
  const f = vs.fill;
  f.filled.add(f.active);
  f.bank.splice(f.bank.indexOf(chip), 1);
  f.active = f.order.find(i => !f.filled.has(i));
  if (f.active === undefined) {
    drawFill();
    stepDone();
    return;
  }
  setMsg(pick(CHEERS), 'good');
  drawFill();
}

function pickFillChip(chip, el) {
  const f = vs.fill;
  if (chip.key === vs.tokens[f.active].key) {
    fillActive(chip);
  } else {
    vs.mistakes++;
    shake(el);
    setMsg(pick(NUDGES), 'bad');
  }
}

function fillHint() {
  const f = vs.fill;
  if (f.active === undefined) return;
  const chip = f.bank.find(c => c.key === vs.tokens[f.active].key);
  if (!chip) return;
  vs.hints++;
  fillActive(chip);
}

// ── Step: Put it in order ──
function renderOrder() {
  const units = makeUnits(vs.tokens);
  const phrases = units.length !== vs.tokens.length;
  document.getElementById('vsInstruction').textContent = phrases
    ? 'Tap the phrases in the right order to rebuild the verse.'
    : 'Tap the words in the right order to rebuild the verse.';

  let bank = shuffle(units.map(u => ({ text: u, key: normUnit(u) })));
  for (let tries = 0; tries < 5 && bank.every((c, i) => c.text === units[i]); tries++) {
    bank = shuffle(bank);
  }
  vs.order = { units, pos: 0, bank };
  drawOrder();

  addButton(document.getElementById('vsActions'), '💡 Hint', 'gd-back-btn', orderHint);
}

function drawOrder() {
  const o = vs.order;
  const text = document.getElementById('vsText');
  text.className = 'vs-text vs-text-order';
  text.innerHTML = '';
  o.units.slice(0, o.pos).forEach(u => {
    const s = document.createElement('span');
    s.className = 'vplaced';
    s.textContent = u;
    text.append(s, ' ');
  });
  if (o.pos < o.units.length) {
    const cursor = document.createElement('span');
    cursor.className = 'vcursor';
    cursor.textContent = '…';
    text.append(cursor);
  }

  const bank = document.getElementById('vsBank');
  bank.innerHTML = '';
  o.bank.forEach(chip => {
    const b = document.createElement('button');
    b.className = 'vchip';
    b.textContent = chip.text;
    b.onclick = () => pickOrderChip(chip, b);
    bank.appendChild(b);
  });
}

function placeOrderChip(chip) {
  const o = vs.order;
  o.bank.splice(o.bank.indexOf(chip), 1);
  o.pos++;
  drawOrder();
  if (o.pos >= o.units.length) stepDone();
  else setMsg(pick(CHEERS), 'good');
}

function pickOrderChip(chip, el) {
  const o = vs.order;
  if (chip.key === normUnit(o.units[o.pos])) {
    placeOrderChip(chip);
  } else {
    vs.mistakes++;
    shake(el);
    setMsg(pick(NUDGES), 'bad');
  }
}

function orderHint() {
  const o = vs.order;
  if (o.pos >= o.units.length) return;
  const chip = o.bank.find(c => c.key === normUnit(o.units[o.pos]));
  if (!chip) return;
  vs.hints++;
  placeOrderChip(chip);
}

// ─── Finish ──────────────────────────────────────────
function finishVerse() {
  const errors = vs.mistakes + vs.hints;
  const stars  = errors <= 2 ? 3 : errors <= 6 ? 2 : 1;

  const progress = vLoad(VERSE_PROGRESS_KEY, {});
  const before   = progress[vs.verse.ref] || 0;
  const improved = stars > before;
  if (improved) {
    progress[vs.verse.ref] = stars;
    vSave(VERSE_PROGRESS_KEY, progress);
  }

  const gained = 10 + stars * 15;
  const oldLevel = Math.floor(getXp() / XP_PER_LEVEL) + 1;
  vSave(VERSE_XP_KEY, getXp() + gained);
  const newLevel = Math.floor(getXp() / XP_PER_LEVEL) + 1;
  const streak   = bumpDailyStreak();

  document.getElementById('vrStars').textContent = '★'.repeat(stars) + '☆'.repeat(3 - stars);
  document.getElementById('vrTitle').textContent =
    stars === 3 ? 'Perfect recall!' : stars === 2 ? 'Great work!' : 'Nice start!';
  document.getElementById('vrRef').textContent  = vs.verse.ref;
  document.getElementById('vrText').textContent = vs.verse.text;

  const bits = [`+${gained} XP`];
  if (newLevel > oldLevel) bits.push(`🎉 Level ${newLevel}!`);
  if (improved && before > 0) bits.push('New best!');
  if (streak.count > 1) bits.push(`🔥 ${streak.count}-day streak`);
  if (stars < 3) bits.push('Try again for 3 stars');
  document.getElementById('vrXp').textContent = bits.join('  ·  ');

  const wordsWrap = document.getElementById('vrWordsWrap');
  const wordsEl   = document.getElementById('vrWords');
  wordsEl.innerHTML = '';
  vs.verse.lexicon.forEach(entry => {
    const tag = document.createElement('span');
    tag.className = 'recent-tag';
    tag.textContent = `${entry.original} · ${entry.transliteration}`;
    tag.onclick = () => openModal(entry);
    wordsEl.appendChild(tag);
  });
  wordsWrap.classList.toggle('hidden', vs.verse.lexicon.length === 0);

  showVersePanel('vResult');
  if (stars === 3) celebrate();
}

function celebrate() {
  const host = document.getElementById('vResult');
  for (let i = 0; i < 22; i++) {
    const p = document.createElement('span');
    p.className = 'confetti';
    p.textContent = pick(['✦', '★', '✝', '❖']);
    p.style.left = `${Math.random() * 100}%`;
    p.style.animationDelay = `${Math.random() * 0.6}s`;
    p.style.animationDuration = `${1.6 + Math.random() * 1.2}s`;
    host.appendChild(p);
    setTimeout(() => p.remove(), 3500);
  }
}
