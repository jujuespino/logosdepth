/* ===================================================
   LogosDepth — Settings, backup/restore, reminders, onboarding, PWA
   =================================================== */
/* global Recall, Progress, Reminder, Sync, Analytics, vLoad, vSave, getCards, getSettings, saveSettings, verseList, packList,
   renderPicker, startVerse, showView, learnNext, sharedLink, sharedGo */

const ONBOARD_KEY = 'ld_onboarded';
const BASE_TITLE  = document.title;
const $ = id => document.getElementById(id);

// ─── Opt-in usage events and feedback (only when the server has beta tools on) ───
const tracker = Analytics.makeTracker({ store: localStorage, fetch: (...a) => window.fetch(...a), nav: navigator });
function track(name, value) { tracker.track(name, value); }
let betaEnabled = false;

// ─── Storage health ──────────────────────────────────
function showStorageBanner() { $('storageBanner').classList.remove('hidden'); }

// ─── Due-count badge and tab title ───────────────────
function updateDueBadge() {
  const n = Recall.dueRefs(getCards(), Recall.dateKey()).length;
  const badge = $('dueBadge');
  badge.textContent = n;
  badge.classList.toggle('hidden', n === 0);
  document.title = n ? `(${n}) ${BASE_TITLE}` : BASE_TITLE;
}

// ─── Backup / restore ────────────────────────────────
function say(id, text, kind) {
  const el = $(id);
  el.textContent = text || '';
  el.className = 'settings-msg' + (kind ? ` ${kind}` : '');
}

function exportProgress() {
  try {
    const data = Progress.exportData(localStorage);
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = `logosdepth-progress-${Recall.dateKey()}.json`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(a.href), 1000);
    track('backup_downloaded');
    const n = Object.keys(data.data.srs).length;
    say('backupMsg', `Backup downloaded (${n} verse${n === 1 ? '' : 's'}, ${data.data.xp} XP).`, 'good');
  } catch {
    say('backupMsg', 'Could not create the backup in this browser.', 'bad');
  }
}

let pendingImport = null;

function chooseImportFile(input) {
  const file = input.files && input.files[0];
  input.value = ''; // allow choosing the same file again later
  cancelImport();
  if (!file) return;
  if (file.size > 2 * 1024 * 1024) { say('backupMsg', 'That file is too large to be a LogosDepth backup.', 'bad'); return; }
  const reader = new FileReader();
  reader.onerror = () => say('backupMsg', 'Could not read that file.', 'bad');
  reader.onload = () => {
    const v = Progress.validate(String(reader.result));
    if (!v.ok) { say('backupMsg', v.error, 'bad'); return; }
    pendingImport = String(reader.result);
    const n = Object.keys(v.data.srs).length;
    $('importSummary').textContent =
      `This backup has ${n} verse${n === 1 ? '' : 's'} and ${v.data.xp} XP` +
      (v.dropped ? ` (${v.dropped} unreadable entr${v.dropped === 1 ? 'y was' : 'ies were'} skipped)` : '') +
      '. Merging keeps everything from both; replacing overwrites what is on this device.';
    $('importChoice').classList.remove('hidden');
    say('backupMsg', '');
  };
  reader.readAsText(file);
}

function cancelImport() {
  pendingImport = null;
  $('importChoice').classList.add('hidden');
}

function applyImport(mode) {
  if (!pendingImport) return;
  const r = Progress.importData(localStorage, pendingImport, mode);
  cancelImport();
  if (!r.ok) { say('backupMsg', r.error, 'bad'); return; }
  say('backupMsg', `${mode === 'replace' ? 'Restored' : 'Merged'}: you now have ${r.cards} verse${r.cards === 1 ? '' : 's'} and ${r.xp} XP.`, 'good');
  afterProgressChange();
  scheduleSync();
}

function afterProgressChange() {
  if (verseList.length) renderPicker();
  updateDueBadge();
}

// ─── Reset ───────────────────────────────────────────
function askReset() {
  $('resetChoice').classList.remove('hidden');
  $('resetBtn').classList.add('hidden');
}
function cancelReset() {
  $('resetChoice').classList.add('hidden');
  $('resetBtn').classList.remove('hidden');
}
function confirmReset() {
  Progress.resetAll(localStorage);
  cancelReset();
  say('resetMsg', 'Your progress has been erased from this device.', 'good');
  afterProgressChange();
}

// ─── Calendar reminder ───────────────────────────────
const REMIND_KEY = 'ld_reminder';
const remindState = () => Reminder.cleanState(vLoad(REMIND_KEY, null));

// Builds the .ics file and offers it for download. Returns false if the time is not valid.
function saveReminderFile(time) {
  if (!Reminder.validTime(time)) return false;
  const ics = Reminder.makeIcs({ time, url: `${location.origin}/?view=verses` });
  const blob = new Blob([ics], { type: 'text/calendar;charset=utf-8' });
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = 'logosdepth-daily-review.ics';
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(a.href), 1000);
  track('reminder_downloaded');
  vSave(REMIND_KEY, Reminder.accepted(remindState()));
  return true;
}

function downloadReminder() {
  const time = $('reminderTime').value;
  if (!saveReminderFile(time)) { say('reminderMsg', 'Please choose a time.', 'bad'); return; }
  say('reminderMsg', `Open the downloaded file to add a daily event at ${time} to your calendar.`, 'good');
  refreshReminderCards();
}

// The offer: once after the first verse is learned, then every couple of days until they add it or opt out.
function fillReminderCard(root, key) {
  root.innerHTML = '';
  const title = document.createElement('p');
  title.className = 'remind-title';
  title.textContent = 'Want a daily reminder?';
  const text = document.createElement('p');
  text.className = 'remind-text';
  text.textContent = 'Reviews work best when they are spaced out. Pick a time and add a repeating event to your calendar.';
  const row = document.createElement('div');
  row.className = 'remind-row';
  const label = document.createElement('label');
  label.className = 'settings-label';
  label.htmlFor = `${key}Time`;
  label.textContent = 'Time';
  const time = document.createElement('input');
  time.type = 'time';
  time.id = `${key}Time`;
  time.className = 'settings-input';
  time.value = $('reminderTime').value || '08:00';
  const msg = document.createElement('p');
  msg.className = 'settings-msg';
  msg.setAttribute('aria-live', 'polite');
  const add = obButton('Add to calendar', 'qf-btn qf-btn-small', () => {
    if (!saveReminderFile(time.value)) { msg.textContent = 'Please choose a time.'; msg.className = 'settings-msg bad'; return; }
    $('reminderTime').value = time.value;
    row.remove();
    text.textContent = 'Done. Open the downloaded file to add the daily event to your calendar.';
    title.textContent = 'Reminder ready';
    document.querySelectorAll('.remind-card').forEach(c => { if (c !== root) c.classList.add('hidden'); });
  });
  const later = obButton('Not now', 'qf-link', () => {
    vSave(REMIND_KEY, Reminder.declined(remindState(), Recall.dateKey()));
    refreshReminderCards();
  });
  const never = obButton('Don\'t ask again', 'qf-link', () => {
    vSave(REMIND_KEY, Reminder.never(remindState()));
    refreshReminderCards();
  });
  row.append(label, time, add, later, never);
  root.append(title, text, row, msg);
}

function refreshReminderCards() {
  const ask = Reminder.shouldAsk(remindState(), Recall.dateKey(), Object.keys(getCards()).length > 0);
  [['vRemindHome', 'remHome'], ['vrRemind', 'remResult']].forEach(([id, key]) => {
    const root = $(id);
    if (!root) return;
    if (ask) {
      if (root.classList.contains('hidden') || !root.firstChild) fillReminderCard(root, key);
      root.classList.remove('hidden');
    } else {
      root.classList.add('hidden');
    }
  });
}

// ─── Install ─────────────────────────────────────────
let deferredInstall = null;

window.addEventListener('beforeinstallprompt', e => {
  e.preventDefault();
  deferredInstall = e;
  $('installBtn').classList.remove('hidden');
});
window.addEventListener('appinstalled', () => {
  deferredInstall = null;
  $('installBtn').classList.add('hidden');
  track('app_installed');
  $('installNote').textContent = 'Installed. You can open LogosDepth from your home screen or app list.';
});

async function installApp() {
  if (!deferredInstall) return;
  deferredInstall.prompt();
  try { await deferredInstall.userChoice; } catch { /* dismissed */ }
  deferredInstall = null;
  $('installBtn').classList.add('hidden');
}

// ─── Onboarding (one welcome screen) ─────────────────
function maybeShowOnboarding() {
  if (vLoad(ONBOARD_KEY, false)) return;
  if (Object.keys(getCards()).length) { vSave(ONBOARD_KEY, true); return; }
  showOnboarding();
}

function closeOnboarding() {
  vSave(ONBOARD_KEY, true);
  $('onboard').classList.add('hidden');
  $('onboardBackdrop').classList.add('hidden');
  document.body.style.overflow = '';
}

function obButton(label, cls, onClick) {
  const b = document.createElement('button');
  b.className = cls;
  b.textContent = label;
  b.onclick = onClick;
  return b;
}

// The optional usage-sharing box (beta servers only). The server answers after the intro may already be showing,
// so this is also called when that answer arrives.
function addShareBox() {
  const body = $('onboardBody');
  if (!betaEnabled || $('obShare') || $('onboard').classList.contains('hidden')) return;
  if (Analytics.blockedBySignal(navigator) || Analytics.isOn(localStorage, navigator)) return;
  const share = document.createElement('label');
  share.className = 'check-row';
  const box = document.createElement('input');
  box.type = 'checkbox';
  box.id = 'obShare';
  share.append(box, ' Share anonymous usage to help improve the app (optional; no text you type is sent)');
  body.appendChild(share);
}

function showOnboarding() {
  const body = $('onboardBody'), actions = $('onboardActions');
  body.innerHTML = '';
  actions.innerHTML = '';
  $('onboardDots').innerHTML = '';
  $('onboardTitle').textContent = 'Welcome to LogosDepth';

  const ol = document.createElement('ol');
  ol.className = 'onboard-list';
  [
    ['Learn a verse in short steps.', 'Read it, practice it phrase by phrase, then fill in the blanks.'],
    ['Type it from memory.', 'Trying to recall is what makes it stick, even when it feels hard.'],
    ['We bring it back on a schedule.', 'A quick review tomorrow, then days and weeks later. Recall it on three different days and it\'s mastered.'],
  ].forEach(([head, rest]) => {
    const li = document.createElement('li');
    const strong = document.createElement('strong');
    strong.textContent = head;
    li.append(strong, ' ', rest);
    ol.appendChild(li);
  });
  body.appendChild(ol);
  const note = document.createElement('p');
  note.className = 'settings-note';
  note.textContent = 'A few minutes a day is enough to get going.';
  body.appendChild(note);
  actions.append(
    obButton('Skip intro', 'gd-back-btn', closeOnboarding),
    obButton('Start my first verse', 'gs-start-btn', finishOnboarding),
  );

  $('onboard').classList.remove('hidden');
  $('onboardBackdrop').classList.remove('hidden');
  document.body.style.overflow = 'hidden';
  addShareBox();
  actions.querySelector('.gs-start-btn').focus();
}

function finishOnboarding() {
  const share = $('obShare');
  if (share && share.checked) {
    Analytics.setOn(localStorage, true, { nav: navigator });
    renderBetaCards();
  }
  track('onboarding_done');
  closeOnboarding();
  renderPicker();
  if (sharedLink) sharedGo(); // they came from a shared link: start that
  else learnNext(); // the gentlest verse in the starter pack
}

// ─── Accounts and sync (only when the server has them switched on) ───
const CSRF = { 'Content-Type': 'application/json', 'X-LD-CSRF': '1' };
let syncState = { enabled: false, signedIn: false };
let syncing = false;
const syncDebounced = Sync.makeDebouncer(() => { if (syncState.signedIn) runSync(true); }, 4000);

function scheduleSync() { if (syncState.signedIn) syncDebounced(); }

async function api(method, url, body) {
  const res = await fetch(url, { method, headers: CSRF, credentials: 'same-origin', body: body === undefined ? undefined : JSON.stringify(body) });
  let json = null;
  try { json = await res.json(); } catch { /* not JSON */ }
  return { ok: res.ok, status: res.status, json };
}

function renderSyncCard() {
  $('syncCard').classList.toggle('hidden', !syncState.enabled);
  $('syncSignedOut').classList.toggle('hidden', syncState.signedIn);
  $('syncSignedIn').classList.toggle('hidden', !syncState.signedIn);
  if (syncState.signedIn) $('syncWho').textContent = syncState.email;
}

async function refreshAuth() {
  try {
    const cfg = await (await fetch('/api/config')).json();
    syncState.enabled = !!cfg.accounts;
    betaEnabled = !!cfg.beta;
    if (syncState.enabled) {
      const me = await (await fetch('/api/auth/me', { credentials: 'same-origin' })).json();
      syncState.signedIn = !!me.signedIn;
      syncState.email = me.email;
    }
  } catch { syncState.enabled = false; betaEnabled = false; }
  renderSyncCard();
  renderBetaCards();
  if (!$('onboard').classList.contains('hidden')) addShareBox();
}

async function runSync(quiet) {
  if (syncing) return;
  syncing = true;
  const btn = $('syncNowBtn');
  if (btn) btn.disabled = true;
  if (!quiet) say('syncMsg', 'Syncing…');
  const r = await Sync.syncOnce({ fetch: window.fetch.bind(window), store: localStorage });
  syncing = false;
  if (btn) btn.disabled = false;
  if (r.ok) {
    afterProgressChange();
    say('syncMsg', `Synced: ${r.cards} verse${r.cards === 1 ? '' : 's'}, ${r.xp} XP.`, 'good');
  } else if (r.reason === 'signed-out') {
    syncState.signedIn = false;
    renderSyncCard();
    say('syncMsg', 'You have been signed out. Sign in again to keep syncing.', 'bad');
  } else if (r.reason === 'offline') {
    if (!quiet) say('syncMsg', 'You appear to be offline. Your progress is safe on this device and will sync later.', 'bad');
  } else {
    say('syncMsg', r.error || 'Sync failed.', 'bad');
  }
}

function syncNow() { runSync(false); }

async function requestSignIn() {
  const email = $('syncEmail').value.trim();
  if (!email) { say('syncMsg', 'Please enter your email address.', 'bad'); return; }
  $('syncRequestBtn').disabled = true;
  say('syncMsg', 'Sending…');
  try {
    const r = await api('POST', '/api/auth/request', { email });
    say('syncMsg', r.ok ? `If that address is valid, a sign-in link is on its way to ${email}. It works once and expires in 15 minutes.` : (r.json && r.json.error) || 'Could not send the link.', r.ok ? 'good' : 'bad');
  } catch {
    say('syncMsg', 'You appear to be offline.', 'bad');
  }
  $('syncRequestBtn').disabled = false;
}

async function completeSignIn(token) {
  history.replaceState(null, '', location.pathname + (location.hash || ''));
  const r = await api('POST', '/api/auth/verify', { token });
  showView('settings', document.querySelector('[data-view="settings"]'));
  if (!r.ok) { say('syncMsg', (r.json && r.json.error) || 'Sign-in failed.', 'bad'); return; }
  syncState.signedIn = true;
  syncState.email = r.json.email;
  track('signed_in');
  renderSyncCard();
  await runSync(false);
}

async function signOut() {
  await api('POST', '/api/auth/logout');
  syncState.signedIn = false;
  renderSyncCard();
  say('syncMsg', 'Signed out. Your progress stays on this device.', 'good');
}

async function signOutEverywhere() {
  await api('POST', '/api/auth/logout-all');
  syncState.signedIn = false;
  renderSyncCard();
  say('syncMsg', 'Signed out on every device. Your progress stays on each device.', 'good');
}

async function downloadAccountData() {
  const res = await fetch('/api/account/export', { credentials: 'same-origin' });
  if (!res.ok) { say('syncMsg', 'Could not download your account data.', 'bad'); return; }
  const blob = new Blob([await res.text()], { type: 'application/json' });
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = 'logosdepth-account.json';
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(a.href), 1000);
}

function askDeleteAccount() {
  $('deleteAccountChoice').classList.remove('hidden');
  $('deleteAccountBtn').classList.add('hidden');
}
function cancelDeleteAccount() {
  $('deleteAccountChoice').classList.add('hidden');
  $('deleteAccountBtn').classList.remove('hidden');
}
async function confirmDeleteAccount() {
  const r = await api('DELETE', '/api/account');
  cancelDeleteAccount();
  if (!r.ok) { say('syncMsg', 'Could not delete the account. Please try again.', 'bad'); return; }
  syncState.signedIn = false;
  renderSyncCard();
  say('syncMsg', 'Your account and synced progress were deleted from the server. Progress on this device was kept.', 'good');
}

function renderBetaCards() {
  $('betaCard').classList.toggle('hidden', !betaEnabled);
  $('feedbackCard').classList.toggle('hidden', !betaEnabled);
  const blocked = Analytics.blockedBySignal(navigator);
  $('analyticsToggle').checked = Analytics.isOn(localStorage, navigator);
  $('analyticsToggle').disabled = blocked;
  $('analyticsSignalNote').classList.toggle('hidden', !blocked);
}

async function toggleAnalytics() {
  if ($('analyticsToggle').checked) {
    Analytics.setOn(localStorage, true, { nav: navigator });
    track('app_open');
    tracker.flush();
    say('analyticsMsg', 'Thank you. Anonymous usage sharing is on.', 'good');
  } else {
    await tracker.erase();
    Analytics.setOn(localStorage, false);
    say('analyticsMsg', 'Usage sharing is off. Your random ID was deleted here and on the server.', 'good');
  }
  renderBetaCards();
}

async function sendFeedback() {
  const message = $('fbMessage').value.trim();
  if (message.length < 3) { say('fbMsg', 'Please write a few words first.', 'bad'); return; }
  $('fbSend').disabled = true;
  say('fbMsg', 'Sending…');
  try {
    const r = await api('POST', '/api/feedback', {
      kind: $('fbKind').value, message, contact: $('fbContact').value.trim() || undefined,
      context: `view=${document.querySelector('.view:not(.hidden)')?.id || ''}`,
    });
    if (r.ok) { $('fbMessage').value = ''; say('fbMsg', 'Thank you! Your feedback was sent.', 'good'); }
    else say('fbMsg', (r.json && r.json.error) || 'Could not send feedback.', 'bad');
  } catch {
    say('fbMsg', 'You appear to be offline. Please try again when you are back online.', 'bad');
  }
  $('fbSend').disabled = false;
}

// ─── Startup ─────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  if (!Progress.storageAvailable(localStorage)) showStorageBanner();
  updateDueBadge();

  const params = new URLSearchParams(location.search);
  const loginToken = params.get('login');
  refreshAuth().then(() => {
    if (betaEnabled) track('app_open');
    if (loginToken && syncState.enabled) completeSignIn(loginToken);
    else if (syncState.signedIn) runSync(true);
  });
  window.addEventListener('online', () => { if (syncState.signedIn) runSync(true); });
  document.addEventListener('visibilitychange', () => { if (document.visibilityState === 'hidden') tracker.flush(); });

  if (typeof maybeShowOnboarding === 'function') maybeShowOnboarding(); // Memorize is the home view

  const view = params.get('view');
  if (view && $(`view-${view}`)) showView(view, document.querySelector(`[data-view="${view}"]`));

  document.addEventListener('keydown', e => {
    if (e.key === 'Escape' && !$('onboard').classList.contains('hidden')) closeOnboarding();
  });

  if ('serviceWorker' in navigator) {
    navigator.serviceWorker.register('/sw.js').catch(() => { /* offline support is optional */ });
  }
});
