/* ===================================================
   LogosDepth — Cross-device sync (optional accounts)
   The client does the merging (Progress.mergeData); the server stores one document per user and
   rejects stale writes with 409. Everything here takes `fetch` and `store` as arguments so the
   algorithm can be unit-tested in Node.
   =================================================== */
/* global Progress, module, require */

const Sync = (() => {
  const P = () => (typeof Progress !== 'undefined' ? Progress : require('./progress.js'));
  const HEADERS = { 'Content-Type': 'application/json', 'X-LD-CSRF': '1' };
  const MAX_ATTEMPTS = 4;
  const VERSION_KEY = 'ld_sync_version';

  async function call(fetchFn, method, url, body) {
    const res = await fetchFn(url, {
      method,
      headers: HEADERS,
      credentials: 'same-origin',
      body: body === undefined ? undefined : JSON.stringify(body),
    });
    let json = null;
    try { json = await res.json(); } catch { /* non-JSON error page */ }
    return { status: res.status, ok: res.ok, json };
  }

  function localData(store) {
    return P().exportData(store).data;
  }

  // Merge what the server has into local storage, upload the result, repeat if another device wrote first.
  // Returns { ok, cards, xp, version } or { ok: false, reason: 'signed-out' | 'offline' | 'error', error }.
  async function syncOnce({ fetch: fetchFn, store }) {
    try {
      for (let attempt = 0; attempt < MAX_ATTEMPTS; attempt++) {
        const got = await call(fetchFn, 'GET', '/api/sync');
        if (got.status === 401) return { ok: false, reason: 'signed-out' };
        if (!got.ok || !got.json) return { ok: false, reason: 'error', error: 'The server could not be reached.' };

        const remote = P().validate(got.json.progress);
        if (!remote.ok) return { ok: false, reason: 'error', error: 'The saved copy could not be read.' };
        const merged = P().mergeData(localData(store), remote.data);
        store.setItem(P().KEYS.srs, JSON.stringify(merged.srs));
        store.setItem(P().KEYS.xp, JSON.stringify(merged.xp));
        store.setItem(P().KEYS.streak, JSON.stringify(merged.streak));
        store.setItem(P().KEYS.settings, JSON.stringify(merged.settings));

        const put = await call(fetchFn, 'PUT', '/api/sync', {
          baseVersion: got.json.version,
          progress: P().exportData(store),
        });
        if (put.status === 401) return { ok: false, reason: 'signed-out' };
        if (put.ok) {
          try { store.setItem(VERSION_KEY, String(put.json.version)); } catch { /* optional */ }
          return { ok: true, cards: Object.keys(merged.srs).length, xp: merged.xp, version: put.json.version };
        }
        if (put.status !== 409) return { ok: false, reason: 'error', error: (put.json && put.json.error) || 'Sync failed.' };
        // 409: someone else saved between our GET and PUT; loop to merge their copy and try again.
      }
      return { ok: false, reason: 'error', error: 'Your other device is saving at the same time. Try again in a moment.' };
    } catch {
      return { ok: false, reason: 'offline' };
    }
  }

  // Coalesces rapid saves into one sync. `run` is called at most once per `delay` ms.
  function makeDebouncer(run, delay, timers = { set: (fn, ms) => setTimeout(fn, ms), clear: id => clearTimeout(id) }) {
    let t = null;
    return () => {
      if (t) timers.clear(t);
      t = timers.set(() => { t = null; run(); }, delay);
    };
  }

  return { syncOnce, makeDebouncer, VERSION_KEY };
})();

if (typeof module !== 'undefined' && module.exports) module.exports = Sync;
