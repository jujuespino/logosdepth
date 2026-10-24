/* ===================================================
   LogosDepth — The whole Bible
   Browse any book and chapter, pick a verse or a short range, and learn it like any other verse.
   Passages you start are kept on this device (ld_custom_verses) so reviews work offline, and are
   re-fetched by reference when progress arrives from a backup or another device.
   =================================================== */
/* global el, vLoad, vSave, verseList, getCards, getSettings, saveSettings, parseKey, startVerse, showVersePanel,
   renderPicker, TRANSLATION_LABEL, exitVerse */

const CUSTOM_KEY = 'ld_custom_verses';
const BIBLE_MAX_VERSES = 12;
const BIBLE_MAX_WORDS = 160;
const BIBLE_REF = /^[1-3]? ?[A-Za-z][A-Za-z' ]*? \d{1,3}:\d{1,3}(-\d{1,3})?$/;

const bib = { index: null, level: 'books', book: null, chapter: null, verses: [], sel: null, busy: false };

// ─── Passages kept on this device ────────────────────
function addCustomVerse(data) {
  if (verseList.some(v => v.ref === data.ref)) return;
  verseList.push({ ...data, custom: true, packs: ['mine'] });
}

function saveCustomVerse(data) {
  const all = vLoad(CUSTOM_KEY, {});
  all[data.ref] = { ref: data.ref, text: data.text, translations: data.translations || {} };
  vSave(CUSTOM_KEY, all);
}

async function fetchPassage(ref) {
  const res = await fetch(`/api/passage?ref=${encodeURIComponent(ref)}`);
  const json = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(json.error || 'Could not load that passage.');
  return json;
}

// Called once the curated verses have loaded: restore saved passages, then fetch any that progress refers to.
async function hydrateCustomVerses() {
  const saved = vLoad(CUSTOM_KEY, {});
  Object.values(saved).forEach(addCustomVerse);
  const missing = new Set();
  Object.keys(getCards()).forEach(key => {
    const ref = parseKey(key).ref;
    if (!verseList.some(v => v.ref === ref) && BIBLE_REF.test(ref)) missing.add(ref);
  });
  await Promise.all([...missing].map(async ref => {
    try {
      const data = await fetchPassage(ref);
      saveCustomVerse(data);
      addCustomVerse(data);
    } catch { /* offline or unknown reference: its schedule stays safe and returns when the passage can load */ }
  }));
}

// ─── Browser ─────────────────────────────────────────
function bibleBodyClear() { const b = el('bibBody'); b.innerHTML = ''; return b; }

function bibleNote(text) {
  const p = document.createElement('p');
  p.className = 'qf-sub';
  p.textContent = text;
  return p;
}

async function openBible() {
  showVersePanel('vBible');
  bib.level = 'books';
  bib.sel = null;
  if (!bib.index) {
    try {
      bib.index = await (await fetch('/api/bible')).json();
    } catch {
      bibleBodyClear().appendChild(bibleNote('Could not load the Bible. Check your connection and try again.'));
      return;
    }
  }
  renderBible();
}

function bibleBack() {
  if (bib.level === 'verses') { bib.level = 'chapters'; bib.sel = null; }
  else if (bib.level === 'chapters') bib.level = 'books';
  else { exitVerse(); return; }
  renderBible();
}

function renderBibleToggle() {
  const toggle = el('bibTranslation');
  toggle.innerHTML = '';
  const settings = getSettings();
  Object.entries(TRANSLATION_LABEL).forEach(([id, label]) => {
    const b = document.createElement('button');
    b.className = 'translation-btn' + (settings.translation === id ? ' active' : '');
    b.textContent = label;
    b.setAttribute('aria-pressed', settings.translation === id ? 'true' : 'false');
    b.onclick = () => { saveSettings({ ...getSettings(), translation: id }); renderPicker(); renderBible(); };
    toggle.appendChild(b);
  });
}

function renderBible() {
  const body = bibleBodyClear();
  el('bibBar').classList.add('hidden');
  el('bibMsg').textContent = '';
  renderBibleToggle();
  document.querySelector('.bib-goto').classList.toggle('hidden', bib.level !== 'books');
  el('vListWrap').classList.toggle('hidden', bib.level !== 'books');
  if (bib.level === 'books') {
    el('bibTitle').textContent = 'The Bible';
    el('bibCrumb').textContent = '';
    [['Old Testament', 'OT'], ['New Testament', 'NT']].forEach(([label, key]) => {
      const h = document.createElement('h2');
      h.className = 'bib-heading';
      h.textContent = label;
      const grid = document.createElement('div');
      grid.className = 'bib-grid bib-books';
      bib.index.filter(b => b.testament === key).forEach(b => {
        const btn = document.createElement('button');
        btn.className = 'bib-btn';
        btn.textContent = b.name;
        btn.onclick = () => { bib.book = b; bib.level = 'chapters'; renderBible(); };
        grid.appendChild(btn);
      });
      body.append(h, grid);
    });
  } else if (bib.level === 'chapters') {
    el('bibTitle').textContent = bib.book.name;
    el('bibCrumb').textContent = `${bib.book.chapters.length} chapter${bib.book.chapters.length === 1 ? '' : 's'}`;
    const grid = document.createElement('div');
    grid.className = 'bib-grid bib-chapters';
    bib.book.chapters.forEach((n, i) => {
      const btn = document.createElement('button');
      btn.className = 'bib-btn';
      btn.textContent = String(i + 1);
      btn.setAttribute('aria-label', `${bib.book.name} chapter ${i + 1}, ${n} verses`);
      btn.onclick = () => loadChapter(i + 1);
      grid.appendChild(btn);
    });
    body.appendChild(grid);
  } else {
    renderChapterVerses();
  }
}

async function loadChapter(n) {
  bib.chapter = n;
  bib.sel = null;
  bib.level = 'verses';
  el('bibTitle').textContent = `${bib.book.name} ${n}`;
  const body = bibleBodyClear();
  body.appendChild(bibleNote('Loading…'));
  try {
    const res = await fetch(`/api/bible/${bib.book.slug}/${n}`);
    if (!res.ok) throw new Error('bad');
    bib.verses = (await res.json()).verses;
  } catch {
    bibleBodyClear().appendChild(bibleNote('Could not load this chapter. Check your connection and try again.'));
    return;
  }
  renderBible();
}

function verseShown(v) {
  return getSettings().translation === 'web' && v.web ? v.web : v.kjv;
}

function selectedInfo() {
  if (!bib.sel) return null;
  const a = Math.min(bib.sel.a, bib.sel.b), b = Math.max(bib.sel.a, bib.sel.b);
  const chosen = bib.verses.filter(v => v.n >= a && v.n <= b);
  const words = chosen.reduce((n, v) => n + v.kjv.split(/\s+/).length, 0);
  const pref = bib.book.ref_name;
  return { a, b, count: chosen.length, words, ref: `${pref} ${bib.chapter}:${a}${b > a ? `-${b}` : ''}` };
}

function renderChapterVerses() {
  const body = bibleBodyClear();
  const tr = getSettings().translation;
  el('bibTitle').textContent = `${bib.book.name} ${bib.chapter}`;
  el('bibCrumb').textContent = 'Tap a verse, or tap two to choose a range';
  const info = selectedInfo();
  const list = document.createElement('div');
  list.className = 'bib-verses';
  bib.verses.forEach(v => {
    const row = document.createElement('button');
    const on = info && v.n >= info.a && v.n <= info.b;
    row.className = 'bib-verse' + (on ? ' selected' : '');
    row.setAttribute('aria-pressed', on ? 'true' : 'false');
    const num = document.createElement('span');
    num.className = 'bib-num';
    num.textContent = String(v.n);
    const txt = document.createElement('span');
    txt.className = 'bib-text';
    txt.textContent = verseShown(v);
    row.append(num, txt);
    row.onclick = () => pickVerse(v.n);
    list.appendChild(row);
  });
  body.appendChild(list);
  if (tr === 'web' && bib.verses.some(v => !v.web)) {
    body.appendChild(bibleNote('Some verses in this chapter are shown in the KJV because the WEB numbering differs.'));
  }
  updateBibleBar();
}

function pickVerse(n) {
  const s = bib.sel;
  if (!s || s.a !== s.b || s.a === n) bib.sel = { a: n, b: n };
  else bib.sel = { a: s.a, b: n };
  renderChapterVerses();
  const row = document.querySelector('.bib-verse.selected');
  if (row) row.focus({ preventScroll: true });
}

function updateBibleBar() {
  const info = selectedInfo();
  const bar = el('bibBar');
  bar.classList.toggle('hidden', !info);
  if (!info) return;
  const tooLong = info.count > BIBLE_MAX_VERSES || info.words > BIBLE_MAX_WORDS;
  el('bibSel').textContent = `${info.ref} · ${info.words} words`;
  el('bibLearn').disabled = tooLong;
  el('bibHint').textContent = tooLong
    ? `Choose a shorter range (up to ${BIBLE_MAX_VERSES} verses and ${BIBLE_MAX_WORDS} words).`
    : info.words > 55 ? 'A longer passage works, but a short one is an easier start.' : '';
}

async function learnPassage(ref, msgEl) {
  if (bib.busy) return;
  bib.busy = true;
  msgEl.textContent = 'Loading…';
  try {
    const data = await fetchPassage(ref);
    saveCustomVerse(data);
    addCustomVerse(data);
    msgEl.textContent = '';
    startVerse(data.ref, getSettings().translation);
  } catch (e) {
    msgEl.textContent = e.message === 'Failed to fetch' ? 'You appear to be offline. Try again when you are connected.' : e.message;
  } finally {
    bib.busy = false;
  }
}

function bibleLearn() {
  const info = selectedInfo();
  if (info) learnPassage(info.ref, el('bibHint'));
}

function bibleGoto() {
  const ref = el('bibGoto').value.trim().replace(/\s+/g, ' ').replace(/[–—]/g, '-');
  if (!ref) { el('bibMsg').textContent = 'Type a reference, for example John 3:16 or Psalm 23:1-3.'; return; }
  learnPassage(ref, el('bibMsg'));
}

document.addEventListener('DOMContentLoaded', () => {
  el('bibGoto').addEventListener('keydown', e => { if (e.key === 'Enter') { e.preventDefault(); bibleGoto(); } });
});
