/* ===================================================
   LogosDepth — Event wiring
   The page has no inline event handlers (so the Content-Security-Policy can forbid inline scripts).
   Elements declare what they do with data attributes:
     data-click="fn"   calls fn() on click; with data-arg="x" calls fn("x", element)
     data-btn="sel"    optional: pass document.querySelector(sel) instead of the element as the 2nd argument
     data-input="fn"   calls fn(element.value) on input
     data-change="fn"  calls fn(element) on change
   =================================================== */

(() => {
  function parseArg(raw) {
    try { return JSON.parse(raw); } catch { return raw; }
  }

  function call(name, args) {
    const fn = window[name];
    if (typeof fn === 'function') fn(...args);
  }

  document.addEventListener('click', e => {
    const el = e.target.closest('[data-click]');
    if (!el || el.disabled) return;
    if (el.dataset.arg === undefined) { call(el.dataset.click, []); return; }
    const second = el.dataset.btn ? document.querySelector(el.dataset.btn) : el;
    call(el.dataset.click, [parseArg(el.dataset.arg), second]);
  });

  document.addEventListener('input', e => {
    const el = e.target.closest('[data-input]');
    if (el) call(el.dataset.input, [el.value]);
  });

  document.addEventListener('change', e => {
    const el = e.target.closest('[data-change]');
    if (el) call(el.dataset.change, [el]);
  });
})();
