// Unit tests for static/js/progress.js and Recall.mergeCards. Run: node tests/test_progress.js
const assert = require('assert');
const R = require('../static/js/recall.js');
const P = require('../static/js/progress.js');

let passed = 0;
function test(name, fn) {
  try { fn(); passed++; console.log('PASS', name); }
  catch (e) { console.log('FAIL', name, '\n    ', e.message); process.exitCode = 1; }
}

function fakeStore(initial = {}, { failWrites = false } = {}) {
  const m = new Map(Object.entries(initial));
  return {
    getItem: k => (m.has(k) ? m.get(k) : null),
    setItem: (k, v) => { if (failWrites) throw new Error('quota'); m.set(k, String(v)); },
    removeItem: k => m.delete(k),
    _m: m,
  };
}
const card = (over = {}) => ({ stage: 1, due: '2026-11-05', days: ['2026-11-01', '2026-11-02'], lapses: 0, lastDate: '2026-11-02', ...over });
const seeded = () => fakeStore({
  ld_verse_srs: JSON.stringify({ 'John 3:16': card() }),
  ld_verse_xp: '45', ld_verse_streak: JSON.stringify({ last: '2026-11-02', count: 2 }),
  ld_verse_settings: JSON.stringify({ translation: 'web', pack: 'faith' }),
});

// ── mergeCards ──
test('mergeCards: later activity decides stage/due, recall days are unioned', () => {
  const a = card({ stage: 1, due: '2026-11-05', days: ['2026-11-01', '2026-11-02'], lastDate: '2026-11-02' });
  const b = card({ stage: 2, due: '2026-11-12', days: ['2026-11-01', '2026-11-05'], lastDate: '2026-11-05', lapses: 1 });
  const m = R.mergeCards(a, b);
  assert.deepStrictEqual([m.stage, m.due, m.lastDate, m.lapses], [2, '2026-11-12', '2026-11-05', 1]);
  assert.deepStrictEqual(m.days, ['2026-11-01', '2026-11-02', '2026-11-05']);
  assert.deepStrictEqual(R.mergeCards(b, a), m, 'merge is symmetric');
});
test('mergeCards: handles missing sides and does not alias inputs', () => {
  const a = card();
  assert.strictEqual(R.mergeCards(null, null), null);
  const m = R.mergeCards(a, null);
  m.days.push('x');
  assert.strictEqual(a.days.length, 2);
  assert.deepStrictEqual(R.mergeCards(null, a).days, a.days);
});

// ── export ──
test('export captures all progress with schema version', () => {
  const e = P.exportData(seeded(), new Date('2026-11-03T10:00:00Z'));
  assert.deepStrictEqual([e.app, e.schemaVersion, e.exportedAt], ['logosdepth', 1, '2026-11-03T10:00:00.000Z']);
  assert.strictEqual(e.data.xp, 45);
  assert.deepStrictEqual(Object.keys(e.data.srs), ['John 3:16']);
  assert.strictEqual(e.data.settings.translation, 'web');
});
test('export of empty storage uses safe defaults', () => {
  const e = P.exportData(fakeStore());
  assert.deepStrictEqual([e.data.srs, e.data.xp, e.data.streak], [{}, 0, { last: '', count: 0 }]);
});
test('export survives corrupted stored JSON', () => {
  const e = P.exportData(fakeStore({ ld_verse_srs: '{not json', ld_verse_xp: 'abc' }));
  assert.deepStrictEqual([e.data.srs, e.data.xp], [{}, 0]);
});

// ── round trip ──
test('replace import restores exactly what was exported', () => {
  const src = seeded();
  const json = JSON.stringify(P.exportData(src));
  const dst = fakeStore();
  const r = P.importData(dst, json, 'replace');
  assert.strictEqual(r.ok, true);
  assert.deepStrictEqual(P.exportData(dst).data, P.exportData(src).data);
});
test('merge import keeps local-only and incoming-only cards and unions days', () => {
  const dst = fakeStore({
    ld_verse_srs: JSON.stringify({ 'Psalm 23:1': card({ days: ['2026-11-03'], lastDate: '2026-11-03' }), 'John 3:16': card() }),
    ld_verse_xp: '20',
  });
  const incoming = JSON.stringify(P.exportData(seeded()));
  const r = P.importData(dst, incoming); // default merge
  assert.strictEqual(r.ok, true);
  const out = P.exportData(dst).data;
  assert.deepStrictEqual(Object.keys(out.srs).sort(), ['John 3:16', 'Psalm 23:1']);
  assert.strictEqual(out.xp, 45, 'larger XP wins');
  assert.strictEqual(out.streak.count, 2);
});
test('merge import never lowers progress (importing an older backup is safe)', () => {
  const newer = fakeStore({
    ld_verse_srs: JSON.stringify({ 'John 3:16': card({ stage: 3, due: '2026-11-20', days: ['2026-11-01', '2026-11-02', '2026-11-09'], lastDate: '2026-11-09' }) }),
    ld_verse_xp: '120',
  });
  P.importData(newer, JSON.stringify(P.exportData(seeded())));
  const c = P.exportData(newer).data.srs['John 3:16'];
  assert.deepStrictEqual([c.stage, c.due, c.days.length], [3, '2026-11-20', 3]);
  assert.strictEqual(P.exportData(newer).data.xp, 120);
});

// ── validation of untrusted files ──
test('rejects non-JSON, wrong app, newer version, and missing data', () => {
  assert.match(P.validate('{{{').error, /valid JSON/);
  assert.match(P.validate({ app: 'other', schemaVersion: 1, data: {} }).error, /LogosDepth backup/);
  assert.match(P.validate({ app: 'logosdepth', schemaVersion: 99, data: { srs: {} } }).error, /newer version/);
  assert.match(P.validate({ app: 'logosdepth', schemaVersion: 1 }).error, /no progress/);
  assert.match(P.validate({ app: 'logosdepth', schemaVersion: 1, data: { srs: [] } }).error, /no progress/);
  assert.match(P.validate(null).error, /LogosDepth backup/);
});
test('drops malformed cards and sanitizes values instead of trusting them', () => {
  const bad = {
    app: 'logosdepth', schemaVersion: 1,
    data: {
      srs: {
        good: card(),
        badStage: card({ stage: 'x' }), badDue: card({ due: 'tomorrow' }), badDays: card({ days: ['soon'] }),
        proto: null, evil: '<script>', ['x'.repeat(200)]: card(),
      },
      xp: -5, streak: { last: 'nope', count: 'many' }, settings: { translation: 'evil', pack: 7, extra: 1 },
    },
  };
  const v = P.validate(bad);
  assert.strictEqual(v.ok, true);
  assert.deepStrictEqual(Object.keys(v.data.srs), ['good']);
  assert.strictEqual(v.dropped, 6);
  assert.deepStrictEqual([v.data.xp, v.data.streak, v.data.settings], [0, { last: '', count: 0 }, {}]);
});
test('import does not write anything when validation fails', () => {
  const s = seeded();
  const before = JSON.stringify([...s._m]);
  assert.strictEqual(P.importData(s, '{"app":"nope"}').ok, false);
  assert.strictEqual(JSON.stringify([...s._m]), before);
});
test('__proto__ keys in a backup cannot pollute objects', () => {
  const evil = '{"app":"logosdepth","schemaVersion":1,"data":{"srs":{"__proto__":{"stage":1,"due":"2026-11-05","days":[],"lapses":0},"ok":{"stage":0,"due":"2026-11-05","days":[]}}}}';
  const v = P.validate(evil);
  assert.strictEqual(v.ok, true);
  assert.strictEqual({}.stage, undefined);
  assert.deepStrictEqual(Object.keys(v.data.srs), ['ok']);
  assert.strictEqual(Object.getPrototypeOf(v.data.srs), Object.prototype, 'no foreign prototype');
  assert.strictEqual(v.dropped, 1);
});

test('trouble-spot words are kept when valid and dropped when not', () => {
  const doc = srs => ({ app: 'logosdepth', schemaVersion: 1, data: { srs } });
  const good = P.validate(doc({ a: card({ slips: { shepherd: 2, lord: 1 } }) })).data.srs.a;
  assert.deepStrictEqual(good.slips, { shepherd: 2, lord: 1 });
  const bad = P.validate(doc({ a: card({ slips: { 'x y': 1, big: 99, zero: 0, ok: 3, '<b>': 1, a: 'x' } }) })).data.srs.a;
  assert.deepStrictEqual(bad.slips, { ok: 3 });
  assert.strictEqual(P.validate(doc({ a: card({ slips: [1, 2] }) })).data.srs.a.slips, undefined);
  assert.strictEqual(P.validate(doc({ a: card() })).data.srs.a.slips, undefined, 'no empty slips field');
  const many = Object.fromEntries(Array.from({ length: 30 }, (_, i) => ['w' + i, 1]));
  assert.strictEqual(Object.keys(P.validate(doc({ a: card({ slips: many }) })).data.srs.a.slips).length, 12);
});

// ── storage availability and reset ──
test('storageAvailable detects a store that refuses writes', () => {
  assert.strictEqual(P.storageAvailable(fakeStore()), true);
  assert.strictEqual(P.storageAvailable(fakeStore({}, { failWrites: true })), false);
});
test('resetAll clears every progress key only', () => {
  const s = seeded();
  s.setItem('unrelated', 'keep');
  P.resetAll(s);
  assert.deepStrictEqual([...s._m.keys()], ['unrelated']);
});

console.log(`\n${passed} passed`);
