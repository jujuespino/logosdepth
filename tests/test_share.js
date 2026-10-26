// Unit tests for static/js/share.js. Run: node tests/test_share.js
const assert = require('assert');
const Share = require('../static/js/share.js');

let passed = 0;
function test(name, fn) {
  try { fn(); passed++; console.log('PASS', name); }
  catch (e) { console.log('FAIL', name, '\n    ', e.message); process.exitCode = 1; }
}

test('verse and pack links are plain, encoded URLs', () => {
  assert.strictEqual(Share.verseUrl('https://x.org', 'John 3:16'), 'https://x.org/?v=John%203%3A16');
  assert.strictEqual(Share.packUrl('https://x.org', 'comfort'), 'https://x.org/?pack=comfort');
});
test('links round-trip through parse', () => {
  for (const ref of ['John 3:16', 'Psalm 23:1-3', '1 John 4:19', 'Song of Solomon 2:4']) {
    const url = new URL(Share.verseUrl('https://x.org', ref));
    assert.deepStrictEqual(Share.parse(url.search), { kind: 'verse', ref });
  }
  assert.deepStrictEqual(Share.parse(new URL(Share.packUrl('https://x.org', 'faith-and-trust')).search), { kind: 'pack', id: 'faith-and-trust' });
});
test('parse tidies spacing and dashes', () => {
  assert.deepStrictEqual(Share.parse('?v=Psalm%20%2023:1%E2%80%933'), { kind: 'verse', ref: 'Psalm 23:1-3' });
  assert.deepStrictEqual(Share.parse('?pack=Love'), { kind: 'pack', id: 'love' });
});
test('parse ignores anything that is not a plain reference or pack id', () => {
  for (const q of ['', '?x=1', '?v=', '?v=hello', '?v=<script>alert(1)</script>', '?v=John%203:16%22%3E', `?v=${'a'.repeat(60)}%203:16`,
    '?pack=../etc', '?pack=a%20b', `?pack=${'a'.repeat(41)}`, '?pack=<b>']) {
    assert.strictEqual(Share.parse(q), null, q);
  }
});
test('a verse in the link wins over a pack', () => {
  assert.strictEqual(Share.parse('?v=John%203:16&pack=love').kind, 'verse');
});

console.log(`\n${passed} passed`);
