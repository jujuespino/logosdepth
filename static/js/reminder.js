/* ===================================================
   LogosDepth — Daily review reminder as a calendar file (.ics)
   Works in any calendar app on any platform, with no server or notification permission.
   Pure functions so they can be unit-tested in Node.
   =================================================== */
/* global module */

const Reminder = (() => {
  const pad = n => String(n).padStart(2, '0');

  // RFC 5545 text escaping
  const esc = s => s.replace(/\\/g, '\\\\').replace(/\n/g, '\\n').replace(/,/g, '\\,').replace(/;/g, '\\;');

  // Lines longer than 75 octets are folded with CRLF + space.
  function fold(line) {
    const out = [];
    let rest = line;
    while (byteLength(rest) > 75) {
      let cut = 75;
      while (byteLength(rest.slice(0, cut)) > 75) cut--;
      out.push(rest.slice(0, cut));
      rest = ' ' + rest.slice(cut);
    }
    out.push(rest);
    return out.join('\r\n');
  }
  function byteLength(s) { return new TextEncoder().encode(s).length; }

  function validTime(t) {
    const m = /^(\d{2}):(\d{2})$/.exec(t || '');
    return !!m && +m[1] < 24 && +m[2] < 60;
  }

  // time: 'HH:MM' local time. now: Date. Event repeats daily starting tomorrow at that local time.
  function makeIcs({ time = '08:00', url = '', now = new Date() } = {}) {
    if (!validTime(time)) throw new Error('Time must look like 08:30');
    const [hh, mm] = time.split(':');
    const start = new Date(now.getFullYear(), now.getMonth(), now.getDate() + 1);
    const day = `${start.getFullYear()}${pad(start.getMonth() + 1)}${pad(start.getDate())}`;
    const stamp = `${now.getUTCFullYear()}${pad(now.getUTCMonth() + 1)}${pad(now.getUTCDate())}` +
                  `T${pad(now.getUTCHours())}${pad(now.getUTCMinutes())}${pad(now.getUTCSeconds())}Z`;
    const desc = 'Open LogosDepth and type today\'s verses from memory. It only takes a few minutes.' +
                 (url ? `\n${url}` : '');
    const lines = [
      'BEGIN:VCALENDAR',
      'VERSION:2.0',
      'PRODID:-//LogosDepth//Daily review//EN',
      'CALSCALE:GREGORIAN',
      'METHOD:PUBLISH',
      'BEGIN:VEVENT',
      'UID:logosdepth-daily-review@logosdepth',
      `DTSTAMP:${stamp}`,
      `DTSTART:${day}T${hh}${mm}00`,   // floating local time: follows the user's time zone
      'DURATION:PT10M',
      'RRULE:FREQ=DAILY',
      `SUMMARY:${esc('Review your Bible verses (LogosDepth)')}`,
      `DESCRIPTION:${esc(desc)}`,
      ...(url ? [`URL:${url}`] : []),
      'BEGIN:VALARM',
      'ACTION:DISPLAY',
      `DESCRIPTION:${esc('Time to review your verses')}`,
      'TRIGGER:PT0S',
      'END:VALARM',
      'END:VEVENT',
      'END:VCALENDAR',
    ];
    return lines.map(fold).join('\r\n') + '\r\n';
  }

  // ─── When to ask ───────────────────────────────────
  // After the first verse is learned we offer the reminder once. If the learner says "Not now" we ask again
  // every ASK_EVERY_DAYS days (never on the same day), until they add it or choose "Don't ask again".
  const ASK_EVERY_DAYS = 2;
  const DAY = /^\d{4}-\d{2}-\d{2}$/;

  function daysBetween(a, b) {
    const t = d => Date.UTC(+d.slice(0, 4), +d.slice(5, 7) - 1, +d.slice(8, 10));
    return Math.round((t(b) - t(a)) / 864e5);
  }

  function cleanState(raw) {
    const r = raw && typeof raw === 'object' ? raw : {};
    return {
      status: r.status === 'accepted' || r.status === 'never' ? r.status : 'none',
      last: typeof r.last === 'string' && DAY.test(r.last) ? r.last : '',
    };
  }

  function shouldAsk(raw, today, hasLearned) {
    const st = cleanState(raw);
    if (!hasLearned || st.status !== 'none') return false;
    return !st.last || daysBetween(st.last, today) >= ASK_EVERY_DAYS;
  }

  const declined = (raw, today) => ({ ...cleanState(raw), last: today });
  const accepted = raw => ({ ...cleanState(raw), status: 'accepted' });
  const never = raw => ({ ...cleanState(raw), status: 'never' });

  return { makeIcs, validTime, escapeText: esc, ASK_EVERY_DAYS, shouldAsk, declined, accepted, never, cleanState };
})();

if (typeof module !== 'undefined' && module.exports) module.exports = Reminder;
