// Unit tests for static/js/sync.js against an in-memory fake server. Run: node tests/test_sync.js
const assert = require('assert');
const S = require('../static/js/sync.js');

let passed = 0;
const queue = [];
function test(name, fn) { queue.push([name, fn]); }

function fakeStore(initial = {}) {
  const m = new Map(Object.entries(initial));
  return { getItem: k => (m.has(k) ? m.get(k) : null), setItem: (k, v) => m.set(k, String(v)), removeItem: k => m.delete(k), _m: m };
}
const card = (over = {}) => ({ stage: 1, due: '2026-11-05', days: ['2026-11-01'], lapses: 0, lastDate: '2026-11-01', ...over });
const storeWith = (srs, xp = 0) => fakeStore({
  ld_verse_srs: JSON.stringify(srs), ld_verse_xp: String(xp),
  ld_verse_streak: JSON.stringify({ last: '', count: 0 }), ld_verse_settings: '{}',
});
const doc = (srs = {}, xp = 0) => ({ app: 'logosdepth', schemaVersion: 1, data: { srs, xp, streak: { last: '', count: 0 }, settings: {} } });

// Minimal server: one document, versioned, with optional hooks to simulate another device or failures.
function fakeServer({ signedIn = true, progress = doc(), version = 0, beforePut = null } = {}) {
  const s = { progress, version, puts: 0, gets: 0 };
  s.fetch = async (url, opts) => {
    const reply = (status, json) => ({ status, ok: status >= 200 && status < 300, json: async () => json });
    if (!signedIn) return reply(401, { error: 'Not signed in.' });
    if (opts.method === 'GET') { s.gets++; return reply(200, { progress: s.progress, version: s.version }); }
    s.puts++;
    if (beforePut) { const f = beforePut; beforePut = null; f(s); }
    const body = JSON.parse(opts.body);
    if (body.baseVersion !== s.version) return reply(409, { error: 'conflict', progress: s.progress, version: s.version });
    s.progress = body.progress; s.version++;
    return reply(200, { ok: true, version: s.version });
  };
  return s;
}

test('first sync uploads local progress to an empty server', async () => {
  const srv = fakeServer();
  const store = storeWith({ 'John 3:16': card() }, 30);
  const r = await S.syncOnce({ fetch: srv.fetch, store });
  assert.deepStrictEqual([r.ok, r.cards, r.xp, r.version], [true, 1, 30, 1]);
  assert.strictEqual(srv.progress.data.xp, 30);
  assert.ok(srv.progress.data.srs['John 3:16']);
});

test('a new device pulls the server copy into empty local storage', async () => {
  const srv = fakeServer({ progress: doc({ 'Psalm 23:1': card({ stage: 3 }) }, 80), version: 4 });
  const store = fakeStore();
  const r = await S.syncOnce({ fetch: srv.fetch, store });
  assert.strictEqual(r.ok, true);
  assert.strictEqual(JSON.parse(store.getItem('ld_verse_srs'))['Psalm 23:1'].stage, 3);
  assert.strictEqual(JSON.parse(store.getItem('ld_verse_xp')), 80);
});

test('guest progress and account progress are merged, neither is lost', async () => {
  const srv = fakeServer({ progress: doc({ 'Psalm 23:1': card() }, 50), version: 2 });
  const store = storeWith({ 'John 3:16': card() }, 20);
  const r = await S.syncOnce({ fetch: srv.fetch, store });
  assert.strictEqual(r.cards, 2);
  assert.deepStrictEqual(Object.keys(srv.progress.data.srs).sort(), ['John 3:16', 'Psalm 23:1']);
  assert.strictEqual(srv.progress.data.xp, 50);
});

test('same verse on two devices: unioned recall days, later card wins', async () => {
  const remote = card({ stage: 2, days: ['2026-11-01', '2026-11-03'], lastDate: '2026-11-03', due: '2026-11-10' });
  const srv = fakeServer({ progress: doc({ v: remote }), version: 1 });
  const store = storeWith({ v: card({ days: ['2026-11-01', '2026-11-02'], lastDate: '2026-11-02' }) });
  await S.syncOnce({ fetch: srv.fetch, store });
  const merged = srv.progress.data.srs.v;
  assert.deepStrictEqual(merged.days, ['2026-11-01', '2026-11-02', '2026-11-03']);
  assert.strictEqual(merged.stage, 2);
});

test('a write from another device mid-sync (409) is merged and retried', async () => {
  const srv = fakeServer({
    beforePut: s => { s.progress = doc({ 'Romans 8:1': card() }, 10); s.version = 1; },
  });
  const store = storeWith({ 'John 3:16': card() });
  const r = await S.syncOnce({ fetch: srv.fetch, store });
  assert.strictEqual(r.ok, true);
  assert.strictEqual(srv.puts, 2);
  assert.deepStrictEqual(Object.keys(srv.progress.data.srs).sort(), ['John 3:16', 'Romans 8:1']);
  assert.ok(JSON.parse(store.getItem('ld_verse_srs'))['Romans 8:1'], 'remote verse reached the device');
});

test('gives up with a friendly error if every attempt conflicts', async () => {
  const srv = fakeServer();
  const real = srv.fetch;
  srv.fetch = async (url, opts) => {
    if (opts.method === 'PUT') { srv.version++; }
    return real(url, opts);
  };
  const r = await S.syncOnce({ fetch: srv.fetch, store: storeWith({}) });
  assert.strictEqual(r.ok, false);
  assert.strictEqual(r.reason, 'error');
});

test('signed-out server answers 401 -> reason signed-out, local data untouched', async () => {
  const srv = fakeServer({ signedIn: false });
  const store = storeWith({ 'John 3:16': card() }, 12);
  const r = await S.syncOnce({ fetch: srv.fetch, store });
  assert.deepStrictEqual([r.ok, r.reason], [false, 'signed-out']);
  assert.strictEqual(JSON.parse(store.getItem('ld_verse_xp')), 12);
});

test('network failure -> reason offline, local data untouched', async () => {
  const store = storeWith({ 'John 3:16': card() }, 12);
  const r = await S.syncOnce({ fetch: async () => { throw new TypeError('Failed to fetch'); }, store });
  assert.deepStrictEqual([r.ok, r.reason], [false, 'offline']);
  assert.strictEqual(JSON.parse(store.getItem('ld_verse_xp')), 12);
});

test('a corrupt server document is refused rather than merged', async () => {
  const srv = fakeServer({ progress: { app: 'other' }, version: 3 });
  const store = storeWith({ 'John 3:16': card() }, 12);
  const r = await S.syncOnce({ fetch: srv.fetch, store });
  assert.strictEqual(r.ok, false);
  assert.strictEqual(JSON.parse(store.getItem('ld_verse_xp')), 12);
});

test('requests carry the CSRF header and same-origin credentials', async () => {
  const seen = [];
  const srv = fakeServer();
  await S.syncOnce({ fetch: (u, o) => { seen.push(o); return srv.fetch(u, o); }, store: storeWith({}) });
  assert.ok(seen.length >= 2);
  seen.forEach(o => { assert.strictEqual(o.headers['X-LD-CSRF'], '1'); assert.strictEqual(o.credentials, 'same-origin'); });
});

test('syncing twice in a row is idempotent', async () => {
  const srv = fakeServer();
  const store = storeWith({ 'John 3:16': card() }, 5);
  await S.syncOnce({ fetch: srv.fetch, store });
  const before = JSON.stringify(srv.progress.data);
  await S.syncOnce({ fetch: srv.fetch, store });
  assert.strictEqual(JSON.stringify(srv.progress.data), before);
});

test('debouncer coalesces bursts into one run', () => {
  const timers = []; let runs = 0;
  const fake = { set: fn => { timers.push(fn); return timers.length; }, clear: id => { timers[id - 1] = null; } };
  const d = S.makeDebouncer(() => runs++, 1000, fake);
  d(); d(); d();
  timers.forEach(fn => fn && fn());
  assert.strictEqual(runs, 1);
});

(async () => {
  for (const [name, fn] of queue) {
    try { await fn(); passed++; console.log('PASS', name); }
    catch (e) { console.log('FAIL', name, '\n    ', e.message); process.exitCode = 1; }
  }
  console.log(`\n${passed} passed`);
})();
