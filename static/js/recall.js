/* ===================================================
   LogosDepth — Recall grading and spaced-review scheduling
   Pure functions (no DOM) so they can be unit-tested in Node.
   =================================================== */
/* global module */

const Recall = (() => {
  // Days until the next review after each successful, unaided recall.
  // Real spacing matters; the exact pattern is a design choice (expanding vs.
  // equal spacing showed no clear difference in Latimier et al. 2021).
  const INTERVAL_DAYS = [1, 3, 7, 14, 30, 60, 120];

  // A verse counts as mastered after unaided recall on this many different days.
  const MASTERY_DAYS = 3;

  const NON_WORD = /[^\p{L}\p{N}]/gu;
  const TOKEN_RE = /^([^\p{L}\p{N}]*)(.*?)([^\p{L}\p{N}]*)$/u;

  // ─── Words and grading ─────────────────────────────
  function normWord(w) {
    return w.toLowerCase().replace(NON_WORD, '');
  }

  // Dashes and hyphens separate words, so "self-control" and "self control" are equivalent.
  function splitWords(text) {
    return text.replace(/[\u2010-\u2015-]+/g, ' ').split(/\s+/).filter(Boolean)
      .map(raw => ({ raw, key: normWord(raw) }))
      .filter(w => w.key);
  }

  function editDistance(a, b) {
    const A = Array.from(a), B = Array.from(b);
    let prev = Array.from({ length: B.length + 1 }, (_, j) => j);
    for (let i = 1; i <= A.length; i++) {
      const cur = [i];
      for (let j = 1; j <= B.length; j++) {
        cur[j] = Math.min(
          prev[j] + 1,
          cur[j - 1] + 1,
          prev[j - 1] + (A[i - 1] === B[j - 1] ? 0 : 1)
        );
      }
      prev = cur;
    }
    return prev[B.length];
  }

  // Spelling leniency is a usability choice, not an evidence-based one. Short
  // words must match exactly because KJV pronouns differ by a letter (thee/the,
  // thy/thine, ye/you).
  function typoLimit(len) {
    return len >= 10 ? 2 : len >= 6 ? 1 : 0;
  }

  function isTypo(typedKey, targetKey) {
    const d = editDistance(typedKey, targetKey);
    return d > 0 && d <= typoLimit(Array.from(targetKey).length);
  }

  // Align typed words to target words. Strict on wording and order, lenient on
  // case, punctuation and (for longer words) small spelling slips.
  function gradeRecall(typedText, targetText) {
    const T = splitWords(targetText);
    const U = splitWords(typedText);
    const n = T.length, m = U.length;

    // Costs are scaled by 10 to keep the arithmetic exact.
    const MATCH = 0, TYPO = 1, EDIT = 10;
    const pair = (t, u) => t.key === u.key ? MATCH : isTypo(u.key, t.key) ? TYPO : EDIT;

    const dp = Array.from({ length: n + 1 }, () => new Array(m + 1).fill(0));
    for (let i = 1; i <= n; i++) dp[i][0] = i * EDIT;
    for (let j = 1; j <= m; j++) dp[0][j] = j * EDIT;
    for (let i = 1; i <= n; i++) {
      for (let j = 1; j <= m; j++) {
        dp[i][j] = Math.min(
          dp[i - 1][j - 1] + pair(T[i - 1], U[j - 1]),
          dp[i - 1][j] + EDIT,
          dp[i][j - 1] + EDIT
        );
      }
    }

    const ops = [];
    let i = n, j = m;
    while (i > 0 || j > 0) {
      if (i > 0 && j > 0 && dp[i][j] === dp[i - 1][j - 1] + pair(T[i - 1], U[j - 1])) {
        const c = pair(T[i - 1], U[j - 1]);
        ops.push({
          kind: c === MATCH ? 'ok' : c === TYPO ? 'typo' : 'wrong',
          target: T[i - 1].raw, typed: U[j - 1].raw,
        });
        i--; j--;
      } else if (i > 0 && dp[i][j] === dp[i - 1][j] + EDIT) {
        ops.push({ kind: 'missing', target: T[i - 1].raw });
        i--;
      } else {
        ops.push({ kind: 'extra', typed: U[j - 1].raw });
        j--;
      }
    }
    ops.reverse();

    const correct = ops.filter(o => o.kind === 'ok' || o.kind === 'typo').length;
    return {
      passed: n > 0 && ops.every(o => o.kind === 'ok' || o.kind === 'typo'),
      total: n,
      correct,
      accuracy: n ? correct / n : 0,
      ops,
    };
  }

  // Split a verse into short phrases for phrase-by-phrase study: break at punctuation, split anything
  // longer than 8 words in half, and fold fragments of under 3 words into a neighbor.
  function makePhrases(text) {
    const words = text.split(/\s+/).filter(Boolean);
    let chunks = [], cur = [];
    words.forEach(w => {
      cur.push(w);
      if (/[,;:.?!)]["'\u2019\u201D]?$/.test(w)) { chunks.push(cur); cur = []; }
    });
    if (cur.length) chunks.push(cur);

    const split = c => {
      if (c.length <= 8) return [c];
      const mid = Math.ceil(c.length / 2);
      return [...split(c.slice(0, mid)), ...split(c.slice(mid))];
    };
    chunks = chunks.flatMap(split);

    const merged = [];
    chunks.forEach(c => {
      if (c.length < 3 && merged.length) merged[merged.length - 1] = merged[merged.length - 1].concat(c);
      else merged.push(c);
    });
    if (merged.length > 1 && merged[0].length < 3) {
      merged[1] = merged[0].concat(merged[1]);
      merged.shift();
    }
    // Folding fragments together can make a long phrase again; cap at 10 words.
    return merged.flatMap(c => (c.length > 10 ? split(c) : [c])).map(c => c.join(' '));
  }

  // First-letter cue, e.g. "For God so loved" -> "F__ G__ s_ l____".
  function makeHint(text) {
    return text.split(/\s+/).filter(Boolean).map(raw => {
      const m = raw.match(TOKEN_RE);
      const core = Array.from(m[2]);
      if (!core.length) return raw;
      return m[1] + core[0] + '_'.repeat(core.length - 1) + m[3];
    }).join(' ');
  }

  // ─── Dates (local calendar days) ───────────────────
  const pad = n => String(n).padStart(2, '0');

  function dateKey(d = new Date()) {
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
  }

  function addDays(key, n) {
    const [y, m, d] = key.split('-').map(Number);
    return dateKey(new Date(y, m - 1, d + n));
  }

  function daysBetween(fromKey, toKey) {
    const [y1, m1, d1] = fromKey.split('-').map(Number);
    const [y2, m2, d2] = toKey.split('-').map(Number);
    return Math.round((Date.UTC(y2, m2 - 1, d2) - Date.UTC(y1, m1 - 1, d1)) / 864e5);
  }

  // ─── Scheduling ────────────────────────────────────
  // card = { stage, due, days: [dateKeys of unaided recall], lapses, lastDate }
  // stage is the index into INTERVAL_DAYS used for the next review (-1 = none yet).
  //
  // Only the first graded attempt of a calendar day counts, so same-day retries
  // (after seeing the answer) never advance the schedule.
  function recordAttempt(card, result, today) {
    const c = card
      ? { ...card, days: [...card.days] }
      : { stage: -1, due: today, days: [], lapses: 0, lastDate: null };

    if (c.lastDate === today) return { card: c, counted: false };
    c.lastDate = today;

    if (result.passed && !result.hinted) {
      if (!c.days.includes(today)) c.days.push(today);
      c.stage = Math.min(c.stage + 1, INTERVAL_DAYS.length - 1);
    } else if (result.passed && result.hinted) {
      // Recalled with a cue: scaffolded practice, not evidence of unaided recall.
      c.stage = Math.max(0, c.stage - 1);
    } else {
      c.lapses += 1;
      c.stage = 0;
    }
    c.due = addDays(today, INTERVAL_DAYS[c.stage]);
    return { card: c, counted: true };
  }

  // Merge two copies of the same verse's card (e.g. from two devices, or an imported backup).
  // The copy with the later activity decides stage and due date; recall days are unioned so no
  // earned recall day is ever lost, and lapses keep the higher count.
  function mergeCards(a, b) {
    if (!a) return b ? { ...b, days: [...b.days] } : null;
    if (!b) return { ...a, days: [...a.days] };
    const [base] = (a.lastDate || '') >= (b.lastDate || '') ? [a, b] : [b, a];
    const days = [...new Set([...a.days, ...b.days])].sort();
    return { ...base, days, lapses: Math.max(a.lapses || 0, b.lapses || 0) };
  }

  const isDue = (card, today) => !!card && card.due <= today;
  const isMastered = card => !!card && card.days.length >= MASTERY_DAYS;
  const recallDays = card => (card ? card.days.length : 0);

  function dueRefs(cards, today) {
    return Object.keys(cards)
      .filter(ref => isDue(cards[ref], today))
      .sort((a, b) => cards[a].due.localeCompare(cards[b].due));
  }

  function describeDue(card, today) {
    const d = daysBetween(today, card.due);
    if (d <= 0) return 'today';
    if (d === 1) return 'tomorrow';
    return `in ${d} days`;
  }

  // XP follows successful recall, not time spent: unaided and later recall earns
  // more; hinted passes earn little; misses and same-day repeats earn nothing.
  function xpForAttempt({ passed, hinted, review, stageBefore, counted }) {
    if (!counted || !passed) return 0;
    if (hinted) return 5;
    return review ? 20 + 5 * Math.max(0, stageBefore) : 25;
  }

  return {
    INTERVAL_DAYS, MASTERY_DAYS,
    normWord, splitWords, editDistance, gradeRecall, makeHint, makePhrases,
    dateKey, addDays, daysBetween,
    recordAttempt, mergeCards, isDue, isMastered, recallDays, dueRefs, describeDue, xpForAttempt,
  };
})();

if (typeof module !== 'undefined' && module.exports) module.exports = Recall;
