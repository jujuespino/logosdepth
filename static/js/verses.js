/* ===================================================
   LogosDepth — Scripture memorization (verses)
   Learn:  Read -> Fill In -> Order -> Recall -> Type It
   Review: type each due verse from memory, spaced over days and weeks
   Grading and scheduling live in recall.js.
   =================================================== */

const VERSE_SRS_KEY    = 'ld_verse_srs';
const VERSE_XP_KEY     = 'ld_verse_xp';
const VERSE_STREAK_KEY = 'ld_verse_streak';
const XP_PER_LEVEL     = 100;

const VERSE_STEPS = [
  { id: 'read',  label: 'Read' },
  { id: 'fill1', label: 'Fill In', pct: 0.25 },
  { id: 'order', label: 'Order' },
  { id: 'fill2', label: 'Recall',  pct: 0.7 },
  { id: 'type',  label: 'Type It' },
];

const CHEERS  = ['Nice!', 'Great job!', 'You\'re getting it!', 'Well done!', 'Keep it up!'];
const NUDGES  = ['Not quite — try another one!', 'Almost! Look at the sentence again.', 'Close! Give it another go.'];

let verseList = [];
let vs = null; // current session: learning one verse, or a review queue

// ─── Storage (always optional) ───────────────────────
function vLoad(key, fallback) {
  try { const v = JSON.parse(localStorage.getItem(key)); return v ?? fallback; } catch { return fallback; }
}
function vSave(key, val) {
  try { localStorage.setItem(key, JSON.stringify(val)); } catch {}
}

const getCards  = () => vLoad(VERSE_SRS_KEY, {});
const saveCards = cards => vSave(VERSE_SRS_KEY, cards);
const el = id => document.getElementById(id);

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

// ─── XP / streak ─────────────────────────────────────
const getXp    = () => vLoad(VERSE_XP_KEY, 0);
const levelOf  = xp => Math.floor(xp / XP_PER_LEVEL) + 1;

function bumpDailyStreak() {
  const today = Recall.dateKey();
  const s = vLoad(VERSE_STREAK_KEY, { last: '', count: 0 });
  if (s.last === today) return s;
  const next = { last: today, count: s.last === Recall.addDays(today, -1) ? s.count + 1 : 1 };
  vSave(VERSE_STREAK_KEY, next);
  return next;
}

function currentStreak() {
  const s = vLoad(VERSE_STREAK_KEY, { last: '', count: 0 });
  const today = Recall.dateKey();
  return (s.last === today || s.last === Recall.addDays(today, -1)) ? s.count : 0;
}

// ─── Load + picker ───────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  loadVerses();
  el('vsInput').addEventListener('keydown', e => {
    if ((e.ctrlKey || e.metaKey) && e.key === 'Enter' && vs && vs.typed && !e.target.disabled) {
      e.preventDefault();
      checkTyped();
    }
  });
});

async function loadVerses() {
  try {
    const res = await fetch('/api/verses');
    verseList = await res.json();
    renderPicker();
  } catch {
    el('verseGrid').textContent = 'Could not load verses. Is the server running?';
  }
}

function renderPicker() {
  const cards = getCards();
  const today = Recall.dateKey();
  const xp    = getXp();
  const into  = xp % XP_PER_LEVEL;

  el('vLevel').textContent    = `Level ${levelOf(xp)}`;
  el('vXpLabel').textContent  = `${into} / ${XP_PER_LEVEL} XP`;
  el('vXpFill').style.width   = `${into}%`;
  el('vStreak').textContent   = currentStreak();
  el('vMastered').textContent =
    `${verseList.filter(v => Recall.isMastered(cards[v.ref])).length}/${verseList.length}`;

  renderReviewCard(cards, today);

  const todayIdx = verseList.length ? Math.floor(Date.now() / 864e5) % verseList.length : -1;
  const grid = el('verseGrid');
  grid.innerHTML = '';

  verseList.forEach((v, i) => {
    const card = cards[v.ref];
    const days = Math.min(Recall.recallDays(card), Recall.MASTERY_DAYS);

    const btn = document.createElement('button');
    btn.className = 'verse-card';

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
    const stars = document.createElement('span');
    stars.className = 'verse-stars';
    stars.textContent = '★'.repeat(days) + '☆'.repeat(Recall.MASTERY_DAYS - days);
    stars.setAttribute('aria-label',
      `Recalled on ${days} of ${Recall.MASTERY_DAYS} days needed for mastery`);
    const status = document.createElement('span');
    status.className = 'verse-status';
    if (!card) {
      status.textContent = 'New';
    } else if (Recall.isDue(card, today)) {
      status.textContent = 'Due today';
      status.classList.add('due');
    } else {
      status.textContent = (Recall.isMastered(card) ? 'Mastered · ' : '') +
        `review ${Recall.describeDue(card, today)}`;
    }
    foot.append(stars, status);

    btn.append(top, preview);
    if (i === todayIdx) {
      const tag = document.createElement('div');
      tag.className = 'verse-today';
      tag.textContent = '✦ Today\'s pick';
      btn.append(tag);
    }
    btn.append(foot);
    btn.onclick = () => startVerse(v.ref);
    grid.appendChild(btn);
  });
}

function renderReviewCard(cards, today) {
  const known = verseList.filter(v => cards[v.ref]);
  const due   = Recall.dueRefs(cards, today).filter(r => verseList.some(v => v.ref === r));
  const btn   = el('vReviewBtn');

  if (due.length) {
    el('vReviewTitle').textContent = `Today's review: ${due.length} verse${due.length === 1 ? '' : 's'} due`;
    el('vReviewSub').textContent   = 'Type each one from memory. Short, spaced-out practice is what makes it stick.';
    btn.classList.remove('hidden');
  } else if (known.length) {
    const next = known.map(v => cards[v.ref]).sort((a, b) => a.due.localeCompare(b.due))[0];
    el('vReviewTitle').textContent = 'You\'re all caught up';
    el('vReviewSub').textContent   = `Next review ${Recall.describeDue(next, today)}.`;
    btn.classList.add('hidden');
  } else {
    el('vReviewTitle').textContent = 'Spaced reviews';
    el('vReviewSub').textContent   = 'Learn a verse below and its reviews will be scheduled for you.';
    btn.classList.add('hidden');
  }
}

// ─── Session plumbing ────────────────────────────────
function showVersePanel(name) {
  ['vPicker', 'vSession', 'vResult'].forEach(id =>
    el(id).classList.toggle('hidden', id !== name));
}

function stopSpeech() { try { speechSynthesis.cancel(); } catch {} }

function startVerse(ref) {
  const verse = verseList.find(v => v.ref === ref);
  if (!verse) return;
  vs = { mode: 'learn', verse, tokens: tokenize(verse.text), step: 0,
         mistakes: 0, hints: 0, xp: 0, first: null, typed: null,
         newlyMastered: false, levelBefore: levelOf(getXp()) };
  showVersePanel('vSession');
  renderStep();
  window.scrollTo({ top: 0 });
}

function startReview() {
  const refs = Recall.dueRefs(getCards(), Recall.dateKey())
    .filter(r => verseList.some(v => v.ref === r));
  if (!refs.length) { exitVerse(); return; }
  vs = { mode: 'review', queue: shuffle(refs), qi: 0, results: [], requeued: new Set(),
         xp: 0, typed: null, levelBefore: levelOf(getXp()) };
  showVersePanel('vSession');
  reviewNext();
}

function exitVerse() {
  stopSpeech();
  vs = null;
  renderPicker();
  showVersePanel('vPicker');
}

function retryVerse() { if (vs && vs.mode === 'learn') startVerse(vs.verse.ref); }

function nextVerse() {
  const cards = getCards();
  const idx = verseList.findIndex(v => v.ref === vs.verse.ref);
  const order = verseList.slice(idx + 1).concat(verseList.slice(0, idx + 1));
  const next = order.find(v => !cards[v.ref])
    || order.find(v => !Recall.isMastered(cards[v.ref]))
    || order[0];
  startVerse(next.ref);
}

function renderSteps() {
  const wrap = el('vsSteps');
  wrap.innerHTML = '';
  if (vs.mode === 'review') {
    const el1 = document.createElement('span');
    el1.className = 'vs-step current';
    el1.textContent = `Review ${vs.qi} of ${vs.queue.length}`;
    wrap.appendChild(el1);
    return;
  }
  VERSE_STEPS.forEach((s, i) => {
    const s1 = document.createElement('span');
    s1.className = 'vs-step' + (i < vs.step ? ' done' : i === vs.step ? ' current' : '');
    s1.textContent = `${i + 1}. ${s.label}`;
    wrap.appendChild(s1);
  });
}

function setMsg(text, kind) {
  const m = el('vsMsg');
  m.textContent = text || '';
  m.className = 'vs-msg' + (kind ? ` ${kind}` : '');
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
  el('vsRef').textContent = vs.verse.ref;
  renderSteps();
  setMsg('');
  el('vsBank').innerHTML = '';
  el('vsActions').innerHTML = '';
  el('vsText').className = 'vs-text';
  el('vsText').textContent = '';
  el('vsInput').classList.add('hidden');
  el('vsHint').classList.add('hidden');

  if (vs.mode === 'review') { renderTyped(); return; }

  const step = VERSE_STEPS[vs.step];
  if (step.id === 'read')       renderRead();
  else if (step.id === 'order') renderOrder();
  else if (step.id === 'type')  renderTyped();
  else                          renderFill(step.pct);
}

function advanceStep() {
  vs.step++;
  renderStep();
}

// Shown after each guided step is complete.
function stepDone() {
  setMsg(pick(CHEERS) + ' Step complete ✓', 'good');
  const actions = el('vsActions');
  actions.innerHTML = '';
  el('vsBank').innerHTML = '';
  addButton(actions, 'Next step →', 'gs-start-btn', advanceStep);
}

function shake(node) {
  node.classList.remove('shake');
  void node.offsetWidth; // restart the animation
  node.classList.add('shake');
}

// ── Step: Read ──
function renderRead() {
  el('vsInstruction').textContent =
    'Read the verse slowly, and say it aloud if you can. When you feel ready, we\'ll play with it.';
  const text = el('vsText');
  text.className = 'vs-text vs-text-read';
  text.textContent = vs.verse.text;

  const actions = el('vsActions');
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
    stopSpeech();
    advanceStep();
  });
}

// ── Step: Fill in the blanks ──
function renderFill(pct) {
  el('vsInstruction').textContent =
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

  addButton(el('vsActions'), '💡 Hint', 'gd-back-btn', fillHint);
}

function drawFill() {
  const f = vs.fill;
  const text = el('vsText');
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

  const bank = el('vsBank');
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

function pickFillChip(chip, node) {
  const f = vs.fill;
  if (chip.key === vs.tokens[f.active].key) {
    fillActive(chip);
  } else {
    vs.mistakes++;
    shake(node);
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
  el('vsInstruction').textContent = phrases
    ? 'Tap the phrases in the right order to rebuild the verse.'
    : 'Tap the words in the right order to rebuild the verse.';

  let bank = shuffle(units.map(u => ({ text: u, key: normUnit(u) })));
  for (let tries = 0; tries < 5 && bank.every((c, i) => c.text === units[i]); tries++) {
    bank = shuffle(bank);
  }
  vs.order = { units, pos: 0, bank };
  drawOrder();

  addButton(el('vsActions'), '💡 Hint', 'gd-back-btn', orderHint);
}

function drawOrder() {
  const o = vs.order;
  const text = el('vsText');
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

  const bank = el('vsBank');
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

function pickOrderChip(chip, node) {
  const o = vs.order;
  if (chip.key === normUnit(o.units[o.pos])) {
    placeOrderChip(chip);
  } else {
    vs.mistakes++;
    shake(node);
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

// ── Step: Type it from memory (also the whole of a review) ──
function renderTyped() {
  const review = vs.mode === 'review';
  el('vsInstruction').textContent = (review ? 'Type this verse from memory. ' : 'Last step: type the whole verse from memory. ') +
    'Capitals and punctuation don\'t matter, but the words and their order do.';

  vs.typed = { hinted: false };
  const input = el('vsInput');
  input.value = '';
  input.disabled = false;
  input.classList.remove('hidden');
  el('vsHint').classList.add('hidden');
  el('vsHint').textContent = '';
  el('vsText').className = 'vs-text';
  el('vsText').textContent = '';

  const actions = el('vsActions');
  actions.innerHTML = '';
  addButton(actions, 'Show first letters', 'gd-back-btn', showTypedHint);
  addButton(actions, 'I don\'t remember', 'gd-back-btn', giveUpTyped);
  addButton(actions, 'Check', 'gs-start-btn', checkTyped);
  setTimeout(() => input.focus(), 0);
}

function showTypedHint() {
  if (!vs.typed) return;
  vs.typed.hinted = true;
  const hint = el('vsHint');
  hint.textContent = Recall.makeHint(vs.verse.text);
  hint.classList.remove('hidden');
  setMsg('Cue used: this attempt won\'t count toward mastery, and the verse will come back sooner.');
  el('vsInput').focus();
}

function giveUpTyped() { submitAttempt(false, null); }

function checkTyped() {
  const input = el('vsInput');
  if (!input.value.trim()) {
    setMsg('Type what you remember, or tap "I don\'t remember".', 'bad');
    input.focus();
    return;
  }
  const grade = Recall.gradeRecall(input.value, vs.verse.text);
  submitAttempt(grade.passed, grade);
}

function submitAttempt(passed, grade) {
  const hinted = vs.typed.hinted;
  const ref    = vs.verse.ref;
  const today  = Recall.dateKey();
  const cards  = getCards();
  const before = cards[ref];
  const review = vs.mode === 'review';

  const { card, counted } = Recall.recordAttempt(before, { passed, hinted }, today);
  const xp = Recall.xpForAttempt({
    passed, hinted, review, stageBefore: before ? before.stage : -1, counted,
  });

  cards[ref] = card;
  saveCards(cards);
  if (xp) vSave(VERSE_XP_KEY, getXp() + xp);
  if (counted && passed) bumpDailyStreak();
  vs.xp += xp;

  if (counted) {
    if (!vs.first) vs.first = { passed, hinted };
    if (!Recall.isMastered(before) && Recall.isMastered(card)) vs.newlyMastered = true;
    if (review) vs.results.push({ ref, passed, hinted, card });
  }

  el('vsInput').disabled = true;
  drawFeedback(grade);

  const typos = grade && grade.ops.some(o => o.kind === 'typo');
  let msg, kind;
  if (passed && !hinted) {
    msg = typos ? 'Correct! Check the spelling of the underlined words.' : 'Perfect recall ✓';
    kind = 'good';
  } else if (passed) {
    msg = 'Recalled with a cue. It will come back sooner so you can try it without one.';
    kind = 'good';
  } else if (grade) {
    msg = 'Not yet. Words in red were missing or different.';
    kind = 'bad';
  } else {
    msg = 'No problem. Read it aloud once; it will come back soon.';
    kind = 'bad';
  }
  if (!counted) msg += ' (You already practiced this verse today, so this round won\'t change your schedule.)';
  setMsg(msg, kind);

  const actions = el('vsActions');
  actions.innerHTML = '';
  if (review) {
    addButton(actions, 'Next →', 'gs-start-btn', () => {
      if (!passed && counted && !vs.requeued.has(ref)) {
        vs.requeued.add(ref);
        vs.queue.push(ref); // one more try at the end of this session
      }
      reviewNext();
    });
  } else if (passed) {
    addButton(actions, 'Continue →', 'gs-start-btn', finishLearning);
  } else {
    addButton(actions, 'Try again', 'gd-back-btn', renderTyped);
    addButton(actions, 'Finish for today', 'gs-start-btn', finishLearning);
  }
}

function drawFeedback(grade) {
  const text = el('vsText');
  text.className = 'vs-text vs-text-feedback';
  text.innerHTML = '';

  if (!grade) {
    text.textContent = vs.verse.text;
    return;
  }

  grade.ops.forEach(op => {
    const span = document.createElement('span');
    if (op.kind === 'ok') {
      span.className = 'd-ok';
      span.textContent = op.target;
    } else if (op.kind === 'typo') {
      span.className = 'd-typo';
      span.textContent = op.target;
      span.title = `You typed "${op.typed}"`;
    } else if (op.kind === 'wrong') {
      span.className = 'd-miss';
      span.textContent = op.target;
      const said = document.createElement('small');
      said.className = 'd-said';
      said.textContent = ` (you: ${op.typed})`;
      span.append(said);
    } else if (op.kind === 'missing') {
      span.className = 'd-miss';
      span.textContent = op.target;
    } else {
      span.className = 'd-extra';
      span.textContent = op.typed;
    }
    text.append(span, ' ');
  });

  const hint = el('vsHint');
  hint.textContent = 'Green = correct · underlined = check spelling · red = missing or different · struck through = extra';
  hint.classList.remove('hidden');
}

// ─── Finish: learning ────────────────────────────────
function finishLearning() {
  const today = Recall.dateKey();
  const card  = getCards()[vs.verse.ref];
  const days  = Math.min(Recall.recallDays(card), Recall.MASTERY_DAYS);
  const first = vs.first;

  let title;
  if (vs.newlyMastered)                 title = 'Mastered!';
  else if (first && first.passed && !first.hinted) title = 'Recalled from memory!';
  else if (first && first.passed)       title = 'Nice. Try it without a cue next time';
  else if (first)                       title = 'Good start. You\'ll see this again tomorrow';
  else                                  title = 'Practice logged';

  el('vrStars').textContent = '●'.repeat(days) + '○'.repeat(Recall.MASTERY_DAYS - days);
  el('vrTitle').textContent = title;
  el('vrRef').textContent   = `${vs.verse.ref} · recalled on ${days} of ${Recall.MASTERY_DAYS} days`;
  el('vrText').textContent  = vs.verse.text;

  const newLevel = levelOf(getXp());
  const bits = [vs.xp ? `+${vs.xp} XP` : 'No XP this round'];
  if (newLevel > vs.levelBefore) bits.push(`🎉 Level ${newLevel}!`);
  const streak = currentStreak();
  if (streak > 1) bits.push(`🔥 ${streak}-day streak`);
  bits.push(`Next review ${Recall.describeDue(card, today)}`);
  if (!Recall.isMastered(card)) {
    const need = Recall.MASTERY_DAYS - Recall.recallDays(card);
    bits.push(`${need} more recall day${need === 1 ? '' : 's'} to master`);
  }
  el('vrXp').textContent = bits.join('  ·  ');

  const wordsEl = el('vrWords');
  wordsEl.innerHTML = '';
  vs.verse.lexicon.forEach(entry => {
    const tag = document.createElement('span');
    tag.className = 'recent-tag';
    tag.textContent = `${entry.original} · ${entry.transliteration}`;
    tag.onclick = () => openModal(entry);
    wordsEl.appendChild(tag);
  });
  el('vrWordsWrap').classList.toggle('hidden', vs.verse.lexicon.length === 0);

  const othersDue = Recall.dueRefs(getCards(), today).filter(r => r !== vs.verse.ref).length;
  el('vrReview').classList.toggle('hidden', othersDue === 0);
  el('vrNext').classList.remove('hidden');
  el('vrAgain').classList.remove('hidden');

  showVersePanel('vResult');
  if (vs.newlyMastered) celebrate();
}

// ─── Review session ──────────────────────────────────
function reviewNext() {
  if (vs.qi >= vs.queue.length) { finishReview(); return; }
  const ref = vs.queue[vs.qi++];
  vs.verse  = verseList.find(v => v.ref === ref);
  vs.tokens = tokenize(vs.verse.text);
  renderStep();
  window.scrollTo({ top: 0 });
}

function finishReview() {
  const today = Recall.dateKey();
  const total = vs.results.length;
  const clean = vs.results.filter(r => r.passed && !r.hinted).length;

  el('vrStars').textContent = total ? `${clean} / ${total}` : '–';
  el('vrTitle').textContent = 'Review complete';
  el('vrRef').textContent   = total ? 'Recalled without a cue' : 'Daily review';
  el('vrText').textContent  = vs.results.map(r => {
    const how = r.passed && !r.hinted ? '✓ recalled' : r.passed ? 'recalled with a cue' : 'missed';
    return `${r.ref} — ${how} · next ${Recall.describeDue(r.card, today)}`;
  }).join('\n');

  const newLevel = levelOf(getXp());
  const bits = [vs.xp ? `+${vs.xp} XP` : 'No XP this round'];
  if (newLevel > vs.levelBefore) bits.push(`🎉 Level ${newLevel}!`);
  const streak = currentStreak();
  if (streak > 1) bits.push(`🔥 ${streak}-day streak`);
  el('vrXp').textContent = bits.join('  ·  ');

  el('vrWordsWrap').classList.add('hidden');
  el('vrReview').classList.add('hidden');
  el('vrNext').classList.add('hidden');
  el('vrAgain').classList.add('hidden');

  showVersePanel('vResult');
  if (total && clean === total) celebrate();
}

function celebrate() {
  const host = el('vResult');
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
