/* ===================================================
   LogosDepth — Opt-in anonymous usage events (beta)
   Nothing is sent unless the learner turns this on in Settings (or ticks the box in the intro).
   Events are a name from a fixed list plus at most one short value, tied to a random id that
   only lives in this browser. Turning it off deletes the id and asks the server to erase its rows.
   =================================================== */
/* global module */

const Analytics = (() => {
  const KEY = 'ld_analytics';
  const HEX = '0123456789abcdef';

  function randomId(cryptoObj) {
    const bytes = new Uint8Array(16);
    (cryptoObj || crypto).getRandomValues(bytes);
    return Array.from(bytes, b => HEX[b >> 4] + HEX[b & 15]).join('');
  }

  // Browsers can send a privacy signal; if it is on, we never collect and never ask.
  function blockedBySignal(nav) {
    return !!nav && (nav.doNotTrack === '1' || nav.globalPrivacyControl === true);
  }

  function getId(store) {
    try {
      const v = JSON.parse(store.getItem(KEY));
      return v && typeof v.id === 'string' && /^[0-9a-f]{32}$/.test(v.id) ? v.id : null;
    } catch { return null; }
  }

  function isOn(store, nav) {
    return !blockedBySignal(nav) && getId(store) !== null;
  }

  // Returns the install id (when turned on) so a caller can send the first event.
  function setOn(store, on, { cryptoObj, nav } = {}) {
    if (on && !blockedBySignal(nav)) {
      const id = getId(store) || randomId(cryptoObj);
      store.setItem(KEY, JSON.stringify({ id }));
      return id;
    }
    store.removeItem(KEY);
    return null;
  }

  function cleanValue(v) {
    if (typeof v === 'number' && Number.isInteger(v) && v >= 0 && v <= 100000) return v;
    if (typeof v === 'string' && /^[a-z0-9_.:-]{1,40}$/.test(v)) return v;
    return undefined;
  }

  // Queue events in memory and send them in small batches; failures are dropped, never retried or stored.
  function makeTracker({ store, fetch: fetchFn, nav, delay = 5000, timers = { set: (fn, ms) => setTimeout(fn, ms), clear: id => clearTimeout(id) } }) {
    let queue = [];
    let timer = null;

    async function flush() {
      if (timer) { timers.clear(timer); timer = null; }
      const id = getId(store);
      if (!queue.length || !id || blockedBySignal(nav)) { queue = []; return; }
      const events = queue.splice(0, 20);
      try {
        await fetchFn('/api/events', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', 'X-LD-CSRF': '1' },
          body: JSON.stringify({ installId: id, events }),
          keepalive: true,
        });
      } catch { /* analytics must never get in the way */ }
      if (queue.length) await flush();
    }

    function track(name, value) {
      if (!isOn(store, nav)) return;
      const e = { name };
      const p = cleanValue(value);
      if (p !== undefined) e.p = p;
      queue.push(e);
      if (!timer) timer = timers.set(flush, delay);
    }

    async function erase() {
      const id = getId(store);
      queue = [];
      if (!id) return;
      try {
        await fetchFn('/api/events', {
          method: 'DELETE',
          headers: { 'Content-Type': 'application/json', 'X-LD-CSRF': '1' },
          body: JSON.stringify({ installId: id }),
        });
      } catch { /* the id is removed locally either way */ }
    }

    return { track, flush, erase };
  }

  return { KEY, randomId, blockedBySignal, getId, isOn, setOn, makeTracker, cleanValue };
})();

if (typeof module !== 'undefined' && module.exports) module.exports = Analytics;
