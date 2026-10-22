/* ===================================================
   LogosDepth — Settings, backup/restore, reminders, onboarding, PWA
   =================================================== */
/* global Recall, Progress, Reminder, vLoad, vSave, getCards, getSettings, saveSettings, verseList, packList,
   renderPicker, startVerse, showView */

const ONBOARD_KEY = 'ld_onboarded';
const BASE_TITLE  = document.title;
const $ = id => document.getElementById(id);

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
function downloadReminder() {
  const time = $('reminderTime').value;
  if (!Reminder.validTime(time)) { say('reminderMsg', 'Please choose a time.', 'bad'); return; }
  const ics = Reminder.makeIcs({ time, url: `${location.origin}/?view=verses` });
  const blob = new Blob([ics], { type: 'text/calendar;charset=utf-8' });
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = 'logosdepth-daily-review.ics';
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(a.href), 1000);
  say('reminderMsg', `Open the downloaded file to add a daily event at ${time} to your calendar.`, 'good');
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
  $('installNote').textContent = 'Installed. You can open LogosDepth from your home screen or app list.';
});

async function installApp() {
  if (!deferredInstall) return;
  deferredInstall.prompt();
  try { await deferredInstall.userChoice; } catch { /* dismissed */ }
  deferredInstall = null;
  $('installBtn').classList.add('hidden');
}

// ─── Onboarding ──────────────────────────────────────
const ob = { step: 0, pack: 'start' };

function maybeShowOnboarding() {
  if (vLoad(ONBOARD_KEY, false)) return;
  if (Object.keys(getCards()).length) { vSave(ONBOARD_KEY, true); return; }
  showOnboarding(0);
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

function showOnboarding(step) {
  ob.step = step;
  const hasPacks = packList.length > 0;
  const total = hasPacks ? 3 : 2;
  const body = $('onboardBody'), actions = $('onboardActions'), title = $('onboardTitle');
  body.innerHTML = '';
  actions.innerHTML = '';

  const dots = $('onboardDots');
  dots.innerHTML = '';
  for (let i = 0; i < total; i++) {
    const d = document.createElement('span');
    d.className = 'onboard-dot' + (i === step ? ' active' : '');
    dots.appendChild(d);
  }

  const kind = step === 0 ? 'intro' : (hasPacks && step === 1 ? 'packs' : 'habit');

  if (kind === 'intro') {
    title.textContent = 'Welcome to LogosDepth';
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
      obButton('Next →', 'gs-start-btn', () => showOnboarding(1)),
    );
  } else if (kind === 'packs') {
    title.textContent = 'Where would you like to start?';
    const list = document.createElement('div');
    list.className = 'onboard-packs';
    packList.forEach(p => {
      const b = document.createElement('button');
      b.className = 'onboard-pack' + (ob.pack === p.id ? ' active' : '');
      b.setAttribute('aria-pressed', ob.pack === p.id ? 'true' : 'false');
      const t = document.createElement('span');
      t.className = 'onboard-pack-title';
      t.textContent = `${p.title} · ${p.count}`;
      const d = document.createElement('span');
      d.className = 'onboard-pack-desc';
      d.textContent = p.description;
      b.append(t, d);
      b.onclick = () => { ob.pack = p.id; showOnboarding(1); };
      list.appendChild(b);
    });
    body.appendChild(list);
    actions.append(
      obButton('← Back', 'gd-back-btn', () => showOnboarding(0)),
      obButton('Next →', 'gs-start-btn', () => showOnboarding(2)),
    );
  } else {
    title.textContent = 'Make it a habit';
    const p = document.createElement('p');
    p.textContent = 'Short, regular reviews work better than long, rare ones. Pick a daily time and add a reminder to your calendar (optional).';
    body.appendChild(p);
    const row = document.createElement('div');
    row.className = 'settings-row';
    const label = document.createElement('label');
    label.className = 'settings-label';
    label.htmlFor = 'obTime';
    label.textContent = 'Time';
    const time = document.createElement('input');
    time.type = 'time';
    time.id = 'obTime';
    time.value = $('reminderTime').value || '08:00';
    time.className = 'settings-input';
    const add = obButton('Add to calendar', 'gd-back-btn', () => {
      $('reminderTime').value = time.value;
      downloadReminder();
      msg.textContent = 'Reminder file downloaded. Open it to add the daily event.';
    });
    row.append(label, time, add);
    const msg = document.createElement('div');
    msg.className = 'settings-msg good';
    body.append(row, msg);
    actions.append(
      obButton('← Back', 'gd-back-btn', () => showOnboarding(hasPacks ? 1 : 0)),
      obButton('Start my first verse', 'gs-start-btn', finishOnboarding),
    );
  }

  $('onboard').classList.remove('hidden');
  $('onboardBackdrop').classList.remove('hidden');
  document.body.style.overflow = 'hidden';
  const primary = actions.querySelector('.gs-start-btn');
  if (primary) primary.focus();
}

function finishOnboarding() {
  closeOnboarding();
  if (packList.some(p => p.id === ob.pack)) saveSettings({ ...getSettings(), pack: ob.pack });
  renderPicker();
  // verseList is sorted shortest-first, so this is the gentlest verse in the chosen pack.
  const first = verseList.find(v => (v.packs || []).includes(ob.pack)) || verseList[0];
  if (first) startVerse(first.ref);
}

// ─── Startup ─────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  if (!Progress.storageAvailable(localStorage)) showStorageBanner();
  updateDueBadge();

  const view = new URLSearchParams(location.search).get('view');
  if (view && $(`view-${view}`)) showView(view, document.querySelector(`[data-view="${view}"]`));

  document.addEventListener('keydown', e => {
    if (e.key === 'Escape' && !$('onboard').classList.contains('hidden')) closeOnboarding();
  });

  if ('serviceWorker' in navigator) {
    navigator.serviceWorker.register('/sw.js').catch(() => { /* offline support is optional */ });
  }
});
