// Unit tests for static/js/analytics.js. Run: node tests/test_analytics.js
const assert = require('assert');
const A = require('../static/js/analytics.js');

let passed = 0;
const queue = [];
function test(name, fn) { queue.push([name, fn]); }

const store = () => { const m = new Map(); return { getItem: k => (m.has(k) ? m.get(k) : null), setItem: (k, v) => m.set(k, String(v)), removeItem: k => m.delete(k) }; };
const fakeCrypto = { getRandomValues: a => { for (let i = 0; i < a.length; i++) a[i] = (i * 37 + 11) & 255; return a; } };
const timers = () => { const t = { fns: [], set: fn => { t.fns.push(fn); return t.fns.length; }, clear: id => { t.fns[id - 1] = null; } }; return t; };

test('off by default: tracking sends nothing', async () => {
  const sent = []; const t = timers();
  const tr = A.makeTracker({ store: store(), fetch: async (u, o) => sent.push(o), timers: t });
  tr.track('app_open');
  await tr.flush();
  assert.strictEqual(sent.length, 0);
  assert.strictEqual(t.fns.length, 0, 'nothing is even queued');
});

test('opting in creates a random 32-hex id and sends batched events', async () => {
  const s = store(); const sent = []; const t = timers();
  const id = A.setOn(s, true, { cryptoObj: fakeCrypto });
  assert.match(id, /^[0-9a-f]{32}$/);
  const tr = A.makeTracker({ store: s, fetch: async (u, o) => sent.push([u, JSON.parse(o.body), o.headers]), timers: t });
  tr.track('verse_started'); tr.track('typed_attempt', 'perfect'); tr.track('review_finished', 3);
  await tr.flush();
  assert.strictEqual(sent.length, 1, 'one batched request');
  assert.deepStrictEqual(sent[0][1].events, [{ name: 'verse_started' }, { name: 'typed_attempt', p: 'perfect' }, { name: 'review_finished', p: 3 }]);
  assert.strictEqual(sent[0][1].installId, id);
  assert.strictEqual(sent[0][2]['X-LD-CSRF'], '1');
});

test('values that could carry personal text are dropped', () => {
  assert.strictEqual(A.cleanValue('John 3:16 is my verse'), undefined);
  assert.strictEqual(A.cleanValue('me@example.com'), undefined);
  assert.strictEqual(A.cleanValue(-1), undefined);
  assert.strictEqual(A.cleanValue(1.5), undefined);
  assert.strictEqual(A.cleanValue({ a: 1 }), undefined);
  assert.strictEqual(A.cleanValue('x'.repeat(41)), undefined);
  assert.strictEqual(A.cleanValue('start'), 'start');
});

test('opting out removes the id and stops all sending', async () => {
  const s = store(); const sent = []; const t = timers();
  A.setOn(s, true, { cryptoObj: fakeCrypto });
  const tr = A.makeTracker({ store: s, fetch: async (u, o) => sent.push(o), timers: t });
  tr.track('app_open');
  A.setOn(s, false);
  await tr.flush();
  assert.strictEqual(A.getId(s), null);
  assert.strictEqual(sent.length, 0, 'queued events are discarded, not sent');
  tr.track('app_open');
  assert.strictEqual(A.isOn(s), false);
});

test('erase() asks the server to delete this install id', async () => {
  const s = store(); const sent = [];
  const id = A.setOn(s, true, { cryptoObj: fakeCrypto });
  const tr = A.makeTracker({ store: s, fetch: async (u, o) => sent.push([u, o.method, JSON.parse(o.body)]) });
  await tr.erase();
  assert.deepStrictEqual(sent, [['/api/events', 'DELETE', { installId: id }]]);
});

test('Do Not Track / Global Privacy Control are respected', async () => {
  const s = store(); const sent = [];
  assert.strictEqual(A.setOn(s, true, { cryptoObj: fakeCrypto, nav: { doNotTrack: '1' } }), null);
  assert.strictEqual(A.getId(s), null);
  A.setOn(s, true, { cryptoObj: fakeCrypto });
  const nav = { globalPrivacyControl: true };
  assert.strictEqual(A.isOn(s, nav), false);
  const tr = A.makeTracker({ store: s, nav, fetch: async (u, o) => sent.push(o) });
  tr.track('app_open');
  await tr.flush();
  assert.strictEqual(sent.length, 0);
});

test('a network failure is swallowed and nothing is stored for retry', async () => {
  const s = store();
  A.setOn(s, true, { cryptoObj: fakeCrypto });
  const tr = A.makeTracker({ store: s, fetch: async () => { throw new TypeError('offline'); } });
  tr.track('app_open');
  await tr.flush();
  assert.strictEqual(s.getItem('ld_verse_srs'), null);
});

test('the id is stable across calls and survives a reload', () => {
  const s = store();
  const a = A.setOn(s, true, { cryptoObj: fakeCrypto });
  const b = A.setOn(s, true, { cryptoObj: { getRandomValues: x => x.fill(9) } });
  assert.strictEqual(a, b);
});

test('more than 20 queued events are split across requests', async () => {
  const s = store(); const sent = [];
  A.setOn(s, true, { cryptoObj: fakeCrypto });
  const tr = A.makeTracker({ store: s, fetch: async (u, o) => sent.push(JSON.parse(o.body).events.length) });
  for (let i = 0; i < 45; i++) tr.track('app_open');
  await tr.flush();
  assert.deepStrictEqual(sent, [20, 20, 5]);
});

(async () => {
  for (const [name, fn] of queue) {
    try { await fn(); passed++; console.log('PASS', name); }
    catch (e) { console.log('FAIL', name, '\n    ', e.message); process.exitCode = 1; }
  }
  console.log(`\n${passed} passed`);
})();
