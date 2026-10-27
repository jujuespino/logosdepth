/* ===================================================
   LogosDepth — Views
   =================================================== */
/* global maybeShowOnboarding */

// Two places: Memorize and Settings.
function showView(name, btn) {
  document.body.dataset.page = name;
  document.querySelectorAll('.view').forEach(v => v.classList.add('hidden'));
  document.getElementById(`view-${name}`).classList.remove('hidden');
  document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));
  if (btn) btn.classList.add('active');
  if (name === 'verses' && typeof maybeShowOnboarding === 'function') maybeShowOnboarding();
}
