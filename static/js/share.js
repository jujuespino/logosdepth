/* ===================================================
   LogosDepth — Share links
   A link to one verse (?v=John%203:16) or one starter pack (?pack=faith). No accounts: opening the link
   just offers that verse or pack on the home screen. Pure functions so they can be unit-tested in Node.
   =================================================== */
/* global module */

const Share = (() => {
  const REF = /^[1-3]? ?[A-Za-z][A-Za-z' ]*? \d{1,3}:\d{1,3}(-\d{1,3})?$/;
  const PACK = /^[a-z0-9-]{1,40}$/;

  const verseUrl = (origin, ref) => `${origin}/?v=${encodeURIComponent(ref)}`;
  const packUrl = (origin, id) => `${origin}/?pack=${encodeURIComponent(id)}`;

  // What a link asks for, or null. Anything that is not a plain Bible reference or pack id is ignored.
  function parse(search) {
    const params = new URLSearchParams(search);
    const v = (params.get('v') || '').replace(/[–—]/g, '-').replace(/\s+/g, ' ').trim();
    if (v && v.length <= 40 && REF.test(v)) return { kind: 'verse', ref: v };
    const pack = (params.get('pack') || '').trim().toLowerCase();
    if (PACK.test(pack)) return { kind: 'pack', id: pack };
    return null;
  }

  return { verseUrl, packUrl, parse };
})();

if (typeof module !== 'undefined' && module.exports) module.exports = Share;
