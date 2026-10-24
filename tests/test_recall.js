// Unit tests for static/js/recall.js. Run: node tests/test_recall.js
const assert = require('assert');
const fs = require('fs');
const path = require('path');
const R = require('../static/js/recall.js');

let passed = 0;
function test(name, fn) {
  try { fn(); passed++; console.log('PASS', name); }
  catch (e) { console.log('FAIL', name, '\n    ', e.message); process.exitCode = 1; }
}

const J316 = 'For God so loved the world, that he gave his only begotten Son, that whosoever believeth in him should not perish, but have everlasting life.';

// ── Grading ──
test('exact text passes', () => assert.strictEqual(R.gradeRecall(J316, J316).passed, true));
test('case and punctuation are ignored', () => {
  const typed = 'for god so loved the world that he gave his only begotten son that whosoever believeth in him should not perish but have everlasting life';
  assert.strictEqual(R.gradeRecall(typed, J316).passed, true);
});
test('extra whitespace and newlines are ignored', () => {
  assert.strictEqual(R.gradeRecall('  For God so   loved the world,\n that he gave his only begotten Son, that whosoever believeth in him should not perish, but have everlasting life.  ', J316).passed, true);
});
test('missing word fails and is reported', () => {
  const g = R.gradeRecall(J316.replace('only ', ''), J316);
  assert.strictEqual(g.passed, false);
  assert.ok(g.ops.some(o => o.kind === 'missing' && /only/i.test(o.target)));
});
test('wrong word fails', () => {
  const g = R.gradeRecall(J316.replace('loved', 'hated'), J316);
  assert.strictEqual(g.passed, false);
  assert.ok(g.ops.some(o => o.kind === 'wrong'));
});
test('extra word fails', () => {
  const g = R.gradeRecall(J316.replace('gave', 'gave freely'), J316);
  assert.strictEqual(g.passed, false);
  assert.ok(g.ops.some(o => o.kind === 'extra'));
});
test('swapped words fail', () => {
  assert.strictEqual(R.gradeRecall(J316.replace('his only', 'only his'), J316).passed, false);
});
test('small spelling slip in a long word passes as typo', () => {
  const g = R.gradeRecall(J316.replace('whosoever', 'whosoevr'), J316);
  assert.strictEqual(g.passed, true);
  assert.ok(g.ops.some(o => o.kind === 'typo'));
});
test('KJV pronouns must match exactly (thee/the, thy/thine)', () => {
  const t = 'Fear thou not; for I am with thee: be not dismayed; for I am thy God';
  assert.strictEqual(R.gradeRecall(t.replace('with thee', 'with the'), t).passed, false);
  assert.strictEqual(R.gradeRecall(t.replace('thy God', 'thine God'), t).passed, false);
});
test('empty input fails', () => assert.strictEqual(R.gradeRecall('', J316).passed, false));
test('accuracy counts correct words', () => {
  const g = R.gradeRecall('For God so loved the world', J316);
  assert.strictEqual(g.passed, false);
  assert.ok(g.accuracy > 0.2 && g.accuracy < 0.4, String(g.accuracy));
});
test('every shipped verse (KJV and WEB): exact passes, one dropped word fails, adjacent swap fails', () => {
  const verses = JSON.parse(fs.readFileSync(path.join(__dirname, '..', 'data', 'verses.json'), 'utf8'));
  assert.ok(verses.length >= 100);
  let texts = 0;
  for (const v of verses) {
    const versions = [['kjv', v.text]];
    if (v.translations && v.translations.web) versions.push(['web', v.translations.web]);
    for (const [name, text] of versions) {
      texts++;
      const label = `${v.ref} (${name})`;
      assert.strictEqual(R.gradeRecall(text, text).passed, true, label + ' exact');
      const w = R.splitWords(text).map(x => x.raw);
      const dropped = w.slice(0, 2).concat(w.slice(3)).join(' ');
      assert.strictEqual(R.gradeRecall(dropped, text).passed, false, label + ' dropped');
      // swap two adjacent, different words
      for (let i = 0; i < w.length - 1; i++) {
        if (R.normWord(w[i]) !== R.normWord(w[i + 1])) {
          const s = w.slice(); [s[i], s[i + 1]] = [s[i + 1], s[i]];
          assert.strictEqual(R.gradeRecall(s.join(' '), text).passed, false, label + ' swap@' + i);
          break;
        }
      }
    }
  }
  assert.ok(texts > 200, String(texts));
});

test('dashes and hyphens separate words', () => {
  const web = 'But now faith, hope, and love remain\u2014these three. And self-control.';
  assert.strictEqual(R.gradeRecall('But now faith hope and love remain these three And self control', web).passed, true);
  assert.strictEqual(R.gradeRecall('But now faith, hope, and love remain\u2014these three. And self-control.', web).passed, true);
  assert.strictEqual(R.gradeRecall('But now faith hope and love remain three And self control', web).passed, false);
});
test('curly and straight apostrophes are equivalent', () => {
  assert.strictEqual(R.gradeRecall("For God didn't give us a spirit of fear", 'For God didn\u2019t give us a spirit of fear').passed, true);
});

// ── Hint ──
test('hint keeps first letters, length and punctuation', () => {
  assert.strictEqual(R.makeHint('For God so loved'), 'F__ G__ s_ l____');
  assert.strictEqual(R.makeHint('The LORD is my shepherd; I'), 'T__ L___ i_ m_ s_______; I');
});

// ── Phrases ──
test('makePhrases breaks at punctuation', () => {
  assert.deepStrictEqual(R.makePhrases('The LORD is my shepherd; I shall not want.'),
    ['The LORD is my shepherd;', 'I shall not want.']);
});
test('makePhrases splits long unpunctuated runs in half', () => {
  const p = R.makePhrases('In the beginning God created the heaven and the earth.');
  assert.strictEqual(p.length, 2);
  assert.strictEqual(p.join(' '), 'In the beginning God created the heaven and the earth.');
});
test('makePhrases folds tiny fragments into a neighbor', () => {
  const p = R.makePhrases('Rejoice evermore. Pray without ceasing. In every thing give thanks: for this is the will of God.');
  assert.ok(p.every(x => x.split(' ').length >= 3), JSON.stringify(p));
});
test('makePhrases keeps short verses whole and never loses words', () => {
  assert.deepStrictEqual(R.makePhrases('Jesus wept.'), ['Jesus wept.']);
  const verses = JSON.parse(fs.readFileSync(path.join(__dirname, '..', 'data', 'verses.json'), 'utf8'));
  for (const v of verses) {
    for (const text of [v.text, v.translations && v.translations.web].filter(Boolean)) {
      const p = R.makePhrases(text);
      assert.strictEqual(p.join(' '), text.split(/\s+/).filter(Boolean).join(' '), v.ref);
      assert.ok(p.length >= 1 && p.every(x => x.split(' ').length <= 12), v.ref + ' ' + JSON.stringify(p));
      if (text.split(/\s+/).length > 10) assert.ok(p.length >= 2, v.ref);
    }
  }
});

// ── Dates ──
test('addDays crosses month and year boundaries', () => {
  assert.strictEqual(R.addDays('2026-10-31', 1), '2026-11-01');
  assert.strictEqual(R.addDays('2026-12-31', 1), '2027-01-01');
  assert.strictEqual(R.addDays('2026-03-01', -1), '2026-02-28');
});
test('daysBetween is exact across DST changes', () => {
  assert.strictEqual(R.daysBetween('2026-03-07', '2026-03-09'), 2);
  assert.strictEqual(R.daysBetween('2026-10-31', '2026-11-02'), 2);
});

// ── Scheduling ──
const day = n => R.addDays('2026-01-01', n);

test('first unaided pass: due next day, 1 recall day', () => {
  const { card, counted } = R.recordAttempt(null, { passed: true, hinted: false }, day(0));
  assert.strictEqual(counted, true);
  assert.deepStrictEqual([card.stage, card.due, card.days.length], [0, day(1), 1]);
});
test('successive unaided passes follow the interval ladder', () => {
  let card = null, today = 0;
  const expectedGaps = [1, 3, 7, 14, 30, 60, 120, 120];
  expectedGaps.forEach(gap => {
    ({ card } = R.recordAttempt(card, { passed: true, hinted: false }, day(today)));
    assert.strictEqual(card.due, day(today + gap), `after day ${today}`);
    today += gap;
  });
});
test('miss resets to stage 0, due tomorrow, no recall day', () => {
  let { card } = R.recordAttempt(null, { passed: true, hinted: false }, day(0));
  ({ card } = R.recordAttempt(card, { passed: true, hinted: false }, day(1)));
  ({ card } = R.recordAttempt(card, { passed: false, hinted: false }, day(4)));
  assert.deepStrictEqual([card.stage, card.due, card.lapses, card.days.length], [0, day(5), 1, 2]);
});
test('hinted pass steps back a stage and does not add a recall day', () => {
  let { card } = R.recordAttempt(null, { passed: true, hinted: false }, day(0));
  ({ card } = R.recordAttempt(card, { passed: true, hinted: false }, day(1)));
  ({ card } = R.recordAttempt(card, { passed: true, hinted: true }, day(4)));
  assert.deepStrictEqual([card.stage, card.days.length], [0, 2]);
  assert.strictEqual(card.due, day(5));
});
test('second attempt on the same day does not count', () => {
  let { card } = R.recordAttempt(null, { passed: false, hinted: false }, day(0));
  const r = R.recordAttempt(card, { passed: true, hinted: false }, day(0));
  assert.strictEqual(r.counted, false);
  assert.deepStrictEqual([r.card.stage, r.card.days.length], [0, 0]);
});
test('mastery needs unaided recall on 3 different days', () => {
  let { card } = R.recordAttempt(null, { passed: true, hinted: false }, day(0));
  assert.strictEqual(R.isMastered(card), false);
  ({ card } = R.recordAttempt(card, { passed: true, hinted: false }, day(1)));
  assert.strictEqual(R.isMastered(card), false);
  ({ card } = R.recordAttempt(card, { passed: true, hinted: false }, day(4)));
  assert.strictEqual(R.isMastered(card), true);
});
test('recordAttempt does not mutate the input card', () => {
  const { card: c1 } = R.recordAttempt(null, { passed: true, hinted: false }, day(0));
  const snapshot = JSON.stringify(c1);
  R.recordAttempt(c1, { passed: true, hinted: false }, day(1));
  assert.strictEqual(JSON.stringify(c1), snapshot);
});
test('dueRefs: only due cards, most overdue first', () => {
  const cards = {
    A: { due: day(5), days: [] }, B: { due: day(2), days: [] }, C: { due: day(9), days: [] },
  };
  assert.deepStrictEqual(R.dueRefs(cards, day(6)), ['B', 'A']);
  assert.deepStrictEqual(R.dueRefs(cards, day(1)), []);
});
test('describeDue wording', () => {
  assert.strictEqual(R.describeDue({ due: day(3) }, day(3)), 'today');
  assert.strictEqual(R.describeDue({ due: day(4) }, day(3)), 'tomorrow');
  assert.strictEqual(R.describeDue({ due: day(10) }, day(3)), 'in 7 days');
});
test('XP rewards unaided/later recall; none for misses, retries or hints-only beyond 5', () => {
  const base = { passed: true, hinted: false, counted: true };
  assert.strictEqual(R.xpForAttempt({ ...base, review: false, stageBefore: -1 }), 25);
  assert.strictEqual(R.xpForAttempt({ ...base, review: true, stageBefore: 0 }), 20);
  assert.strictEqual(R.xpForAttempt({ ...base, review: true, stageBefore: 4 }), 40);
  assert.strictEqual(R.xpForAttempt({ ...base, hinted: true, review: true, stageBefore: 4 }), 5);
  assert.strictEqual(R.xpForAttempt({ ...base, passed: false, review: true, stageBefore: 4 }), 0);
  assert.strictEqual(R.xpForAttempt({ ...base, counted: false, review: true, stageBefore: 4 }), 0);
});

console.log(`\n${passed} passed`);
