/* ===================================================
   LogosDepth — Progress backup, import and merge
   Pure functions over a Storage-like object (getItem/setItem/removeItem) so they can be
   unit-tested in Node. The same merge rules will be used when syncing between devices.
   =================================================== */
/* global Recall, module, require */

const Progress = (() => {
  const SCHEMA_VERSION = 1;
  const APP_ID = 'logosdepth';
  const KEYS = {
    srs: 'ld_verse_srs',
    xp: 'ld_verse_xp',
    streak: 'ld_verse_streak',
    settings: 'ld_verse_settings',
  };
  const DATE = /^\d{4}-\d{2}-\d{2}$/;
  const R = () => (typeof Recall !== 'undefined' ? Recall : require('./recall.js'));

  function storageAvailable(store) {
    try {
      const k = '__ld_probe__';
      store.setItem(k, '1');
      store.removeItem(k);
      return true;
    } catch {
      return false;
    }
  }

  function read(store, key, fallback) {
    try {
      const v = JSON.parse(store.getItem(key));
      return v ?? fallback;
    } catch {
      return fallback;
    }
  }

  function exportData(store, now = new Date()) {
    return {
      app: APP_ID,
      schemaVersion: SCHEMA_VERSION,
      exportedAt: now.toISOString(),
      data: {
        srs: read(store, KEYS.srs, {}),
        xp: read(store, KEYS.xp, 0),
        streak: read(store, KEYS.streak, { last: '', count: 0 }),
        settings: read(store, KEYS.settings, {}),
      },
    };
  }

  // Upgrade an older export to the current schema. Only version 1 exists so far; add steps here
  // (v1 -> v2, ...) when the format changes so old backups keep working.
  function migrate(obj) {
    return obj;
  }

  function cleanCard(c) {
    if (!c || typeof c !== 'object') return null;
    if (!Number.isInteger(c.stage) || c.stage < -1 || c.stage > 20) return null;
    if (typeof c.due !== 'string' || !DATE.test(c.due)) return null;
    if (!Array.isArray(c.days) || !c.days.every(d => typeof d === 'string' && DATE.test(d))) return null;
    const lastDate = typeof c.lastDate === 'string' && DATE.test(c.lastDate) ? c.lastDate : null;
    const out = {
      stage: c.stage,
      due: c.due,
      days: [...new Set(c.days)].sort(),
      lapses: Number.isInteger(c.lapses) && c.lapses >= 0 ? c.lapses : 0,
      lastDate,
    };
    const slips = cleanSlips(c.slips);
    if (slips) out.slips = slips;
    return out;
  }

  // Trouble-spot words for one verse: a few short words with small counts. Anything else is dropped.
  function cleanSlips(raw) {
    if (!raw || typeof raw !== 'object' || Array.isArray(raw)) return null;
    const out = {};
    for (const [word, n] of Object.entries(raw)) {
      if (Object.keys(out).length >= 12) break;
      if (word.length > 0 && word.length <= 40 && /^[\p{L}\p{N}]+$/u.test(word) && Number.isInteger(n) && n >= 1 && n <= 9) out[word] = n;
    }
    return Object.keys(out).length ? out : null;
  }

  // Validate untrusted input (a file the user picked). Returns { ok, error, data } where data is sanitized.
  function validate(raw) {
    let obj = raw;
    if (typeof raw === 'string') {
      try { obj = JSON.parse(raw); } catch { return { ok: false, error: 'That file is not valid JSON.' }; }
    }
    if (!obj || typeof obj !== 'object' || obj.app !== APP_ID) {
      return { ok: false, error: 'That does not look like a LogosDepth backup.' };
    }
    if (!Number.isInteger(obj.schemaVersion) || obj.schemaVersion < 1) {
      return { ok: false, error: 'Unrecognized backup version.' };
    }
    if (obj.schemaVersion > SCHEMA_VERSION) {
      return { ok: false, error: 'This backup was made by a newer version of the app. Please update and try again.' };
    }
    const d = migrate(obj).data;
    if (!d || typeof d !== 'object' || !d.srs || typeof d.srs !== 'object' || Array.isArray(d.srs)) {
      return { ok: false, error: 'The backup has no progress data.' };
    }
    const srs = {};
    let dropped = 0;
    const FORBIDDEN = new Set(['__proto__', 'constructor', 'prototype']);
    for (const [key, card] of Object.entries(d.srs)) {
      const clean = key.length <= 80 && !FORBIDDEN.has(key) ? cleanCard(card) : null;
      if (clean) srs[key] = clean; else dropped++;
    }
    const xp = Number.isInteger(d.xp) && d.xp >= 0 ? d.xp : 0;
    const st = d.streak && typeof d.streak === 'object' ? d.streak : {};
    const streak = {
      last: typeof st.last === 'string' && DATE.test(st.last) ? st.last : '',
      count: Number.isInteger(st.count) && st.count >= 0 ? st.count : 0,
    };
    const set = d.settings && typeof d.settings === 'object' ? d.settings : {};
    const settings = {};
    if (set.translation === 'kjv' || set.translation === 'web') settings.translation = set.translation;
    if (typeof set.pack === 'string' && set.pack.length <= 40) settings.pack = set.pack;
    return { ok: true, dropped, data: { srs, xp, streak, settings } };
  }

  function mergeStreaks(a, b) {
    if (!a.last) return b;
    if (!b.last) return a;
    if (a.last !== b.last) return a.last > b.last ? a : b;
    return a.count >= b.count ? a : b;
  }

  // Combine local progress with incoming progress without losing anything earned on either side.
  // XP cannot be summed (the two copies may share history), so the larger value wins.
  function mergeData(local, incoming) {
    const srs = {};
    for (const key of new Set([...Object.keys(local.srs), ...Object.keys(incoming.srs)])) {
      srs[key] = R().mergeCards(local.srs[key], incoming.srs[key]);
    }
    return {
      srs,
      xp: Math.max(local.xp, incoming.xp),
      streak: mergeStreaks(local.streak, incoming.streak),
      settings: { ...incoming.settings, ...local.settings },
    };
  }

  function writeAll(store, data) {
    store.setItem(KEYS.srs, JSON.stringify(data.srs));
    store.setItem(KEYS.xp, JSON.stringify(data.xp));
    store.setItem(KEYS.streak, JSON.stringify(data.streak));
    store.setItem(KEYS.settings, JSON.stringify(data.settings));
  }

  // mode: 'merge' (default) keeps everything from both; 'replace' overwrites local progress.
  function importData(store, raw, mode = 'merge') {
    const v = validate(raw);
    if (!v.ok) return v;
    const local = exportData(store).data;
    const next = mode === 'replace' ? v.data : mergeData(local, v.data);
    writeAll(store, next);
    return { ok: true, dropped: v.dropped, cards: Object.keys(next.srs).length, xp: next.xp };
  }

  function resetAll(store) {
    Object.values(KEYS).forEach(k => store.removeItem(k));
  }

  return { SCHEMA_VERSION, APP_ID, KEYS, storageAvailable, exportData, validate, migrate, mergeData, importData, resetAll };
})();

if (typeof module !== 'undefined' && module.exports) module.exports = Progress;
