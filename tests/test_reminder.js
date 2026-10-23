// Unit tests for static/js/reminder.js. Run: node tests/test_reminder.js
const assert = require('assert');
const Rm = require('../static/js/reminder.js');

let passed = 0;
function test(name, fn) {
  try { fn(); passed++; console.log('PASS', name); }
  catch (e) { console.log('FAIL', name, '\n    ', e.message); process.exitCode = 1; }
}
const now = new Date(2026, 9, 22, 21, 30, 0); // 22 Oct 2026, local

test('valid calendar structure with CRLF line endings', () => {
  const ics = Rm.makeIcs({ time: '08:15', url: 'https://example.org/', now });
  assert.ok(ics.startsWith('BEGIN:VCALENDAR\r\n') && ics.endsWith('END:VCALENDAR\r\n'));
  assert.ok(!/[^\r]\n/.test(ics), 'every newline is CRLF');
  for (const tag of ['BEGIN:VEVENT', 'END:VEVENT', 'BEGIN:VALARM', 'END:VALARM', 'VERSION:2.0']) assert.ok(ics.includes(tag), tag);
});
test('daily recurrence starting tomorrow at the chosen local time', () => {
  const ics = Rm.makeIcs({ time: '08:15', now });
  assert.ok(ics.includes('RRULE:FREQ=DAILY'));
  assert.ok(ics.includes('DTSTART:20261023T081500'), ics);
  assert.ok(!/DTSTART:[^\r]*Z/.test(ics), 'floating local time, not UTC');
});
test('start date rolls over month and year ends', () => {
  assert.ok(Rm.makeIcs({ time: '07:00', now: new Date(2026, 11, 31, 12, 0) }).includes('DTSTART:20270101T070000'));
  assert.ok(Rm.makeIcs({ time: '07:00', now: new Date(2026, 9, 31, 12, 0) }).includes('DTSTART:20261101T070000'));
});
test('text is escaped and long lines are folded under 75 octets', () => {
  const ics = Rm.makeIcs({ time: '08:00', url: 'https://example.org/' + 'a'.repeat(120), now });
  assert.ok(ics.replace(/\r\n /g, '').includes("type today's verses from memory. It only takes a few minutes.\\n"), 'apostrophes and periods stay as-is; newline becomes \\n');
  for (const line of ics.split('\r\n')) assert.ok(new TextEncoder().encode(line).length <= 75, line.length + ': ' + line);
  const unfolded = ics.replace(/\r\n /g, '');
  assert.ok(unfolded.includes('URL:https://example.org/' + 'a'.repeat(120)));
});
test('commas and semicolons in descriptions are escaped', () => {
  const ics = Rm.makeIcs({ time: '08:00', now });
  assert.ok(ics.includes('Review your Bible verses (LogosDepth)'));
  assert.ok(ics.replace(/\r\n /g, '').includes('DESCRIPTION:Open LogosDepth'));
});
test('escapeText escapes backslash, comma, semicolon and newline (RFC 5545)', () => {
  assert.strictEqual(Rm.escapeText('a,b;c\\d\ne'), 'a\\,b\\;c\\\\d\\ne');
});
test('rejects invalid times', () => {
  for (const t of ['', '8:00', '24:00', '12:60', 'noon', null]) assert.throws(() => Rm.makeIcs({ time: t, now }), /Time must/);
  assert.strictEqual(Rm.validTime('23:59'), true);
});

console.log(`\n${passed} passed`);
