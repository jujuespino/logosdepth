/* ===================================================
   LogosDepth — Frontend Logic
   =================================================== */

const RECENT_KEY = 'ld_recent';
const MAX_RECENT = 8;

let currentLang = 'all';
let currentCategory = '';
let searchTimer = null;

// ─── Init ────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  loadStats();
  loadWordOfDay();
  loadFeatured();
  loadCategories();
  renderRecent();
});

// ─── View switching ──────────────────────────────────
function showView(name, btn) {
  document.querySelectorAll('.view').forEach(v => v.classList.add('hidden'));
  document.getElementById(`view-${name}`).classList.remove('hidden');
  document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));
  if (btn) btn.classList.add('active');

  if (name !== 'search') {
    clearSearch();
  }
}

function toggleSidebar() {
  document.getElementById('sidebar').classList.toggle('open');
}

// Close sidebar when clicking outside on mobile
document.addEventListener('click', e => {
  const sidebar = document.getElementById('sidebar');
  if (sidebar.classList.contains('open') &&
      !sidebar.contains(e.target) &&
      !e.target.closest('.menu-toggle')) {
    sidebar.classList.remove('open');
  }
});

// ─── Language filter ─────────────────────────────────
function setLang(lang, btn) {
  currentLang = lang;
  document.querySelectorAll('.lang-btn').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');

  const q = document.getElementById('searchInput').value.trim();
  if (q || currentCategory) {
    runSearch(q);
  }
}

// ─── Category filter ─────────────────────────────────
function selectCategory(cat, el) {
  if (currentCategory === cat) {
    currentCategory = '';
    document.querySelectorAll('.cat-item').forEach(i => i.classList.remove('active'));
  } else {
    currentCategory = cat;
    document.querySelectorAll('.cat-item').forEach(i => i.classList.remove('active'));
    el.classList.add('active');
  }

  showView('search', document.querySelector('[data-view="search"]'));
  const q = document.getElementById('searchInput').value.trim();
  runSearch(q);
}

// ─── Search ──────────────────────────────────────────
function onSearchInput(value) {
  const clearBtn = document.getElementById('clearBtn');
  clearBtn.style.display = value ? 'block' : 'none';

  clearTimeout(searchTimer);

  if (!value.trim() && !currentCategory) {
    showView('dashboard', document.querySelector('[data-view="dashboard"]'));
    return;
  }

  showView('search', document.querySelector('[data-view="search"]'));

  searchTimer = setTimeout(() => runSearch(value.trim()), 280);
}

function clearSearch() {
  document.getElementById('searchInput').value = '';
  document.getElementById('clearBtn').style.display = 'none';
  currentCategory = '';
  document.querySelectorAll('.cat-item').forEach(i => i.classList.remove('active'));
  showView('dashboard', document.querySelector('[data-view="dashboard"]'));
}

async function runSearch(query) {
  const grid   = document.getElementById('resultsGrid');
  const header = document.getElementById('resultsHeader');
  const noRes  = document.getElementById('noResults');
  const loading = document.getElementById('loadingState');

  grid.innerHTML = '';
  noRes.classList.add('hidden');
  loading.classList.remove('hidden');

  const params = new URLSearchParams({ q: query, lang: currentLang });
  if (currentCategory) params.set('category', currentCategory);

  try {
    const res = await fetch(`/api/search?${params}`);
    const data = await res.json();
    loading.classList.add('hidden');

    if (data.results.length === 0) {
      noRes.classList.remove('hidden');
      document.getElementById('noResultsQuery').textContent = query || currentCategory;
      header.textContent = '';
      return;
    }

    const label = currentCategory ? ` in "${currentCategory}"` : '';
    header.textContent = `${data.results.length} result${data.results.length !== 1 ? 's' : ''}${label}${query ? ` for "${query}"` : ''}`;

    data.results.forEach(entry => grid.appendChild(buildWordCard(entry)));

    if (query) saveRecent(query);
  } catch {
    loading.classList.add('hidden');
    header.textContent = 'Error fetching results. Is the server running?';
  }
}

// ─── Stats ───────────────────────────────────────────
async function loadStats() {
  try {
    const res  = await fetch('/api/categories');
    const cats = await res.json();
    const totalH = cats.reduce((s, c) => s + c.hebrew, 0);
    const totalG = cats.reduce((s, c) => s + c.greek, 0);
    document.getElementById('statHebrew').textContent  = totalH;
    document.getElementById('statGreek').textContent   = totalG;
    document.getElementById('dashTotal').textContent   = totalH + totalG;
    document.getElementById('dashHebrew').textContent  = totalH;
    document.getElementById('dashGreek').textContent   = totalG;
    document.getElementById('dashCats').textContent    = cats.length;
  } catch {}
}

// ─── Word of the Day ─────────────────────────────────
async function loadWordOfDay() {
  try {
    const res   = await fetch('/api/word-of-day');
    const entry = await res.json();

    document.getElementById('wodOriginal').textContent  = entry.original;
    document.getElementById('wodTranslit').textContent  = entry.transliteration;
    document.getElementById('wodDef').textContent       = entry.definition;
    document.getElementById('wodRef').textContent       = entry.strongs_id;

    const langEl  = document.getElementById('wodLang');
    langEl.textContent = entry.language;
    langEl.className   = `badge badge-${entry.language.toLowerCase()}`;

    document.getElementById('wodCard').onclick = () => openModal(entry);
    document.getElementById('wodCard').style.cursor = 'pointer';
  } catch {}
}

// ─── Featured words ──────────────────────────────────
async function loadFeatured() {
  try {
    const res   = await fetch('/api/featured');
    const words = await res.json();
    const grid  = document.getElementById('featuredGrid');
    words.forEach(w => grid.appendChild(buildWordCard(w)));
  } catch {}
}

// ─── Categories sidebar + browse ─────────────────────
async function loadCategories() {
  try {
    const res  = await fetch('/api/categories');
    const cats = await res.json();

    // Sidebar list
    const list = document.getElementById('categoryList');
    list.innerHTML = '';
    cats.forEach(cat => {
      const li = document.createElement('li');
      li.className = 'cat-item';
      li.innerHTML = `
        <span>${cat.name}</span>
        <span class="cat-count">${cat.count}</span>
      `;
      li.onclick = () => selectCategory(cat.name, li);
      list.appendChild(li);
    });

    // Browse grid
    const browseGrid = document.getElementById('browseGrid');
    browseGrid.innerHTML = '';
    cats.forEach(cat => {
      const card = document.createElement('div');
      card.className = 'browse-card';
      card.innerHTML = `
        <div class="browse-cat-name">${cat.name}</div>
        <div class="browse-cat-counts">
          <span class="h">H: ${cat.hebrew}</span>
          <span class="g">G: ${cat.greek}</span>
          <span>${cat.count} words</span>
        </div>
      `;
      card.onclick = () => {
        selectCategory(cat.name, document.querySelector(`.cat-item[data-cat="${cat.name}"]`) || card);
      };
      browseGrid.appendChild(card);
    });
  } catch {}
}

// ─── Build word card ─────────────────────────────────
function buildWordCard(entry) {
  const card = document.createElement('div');
  card.className = `word-card ${entry.language.toLowerCase()}`;
  card.innerHTML = `
    <div class="card-original">${entry.original}</div>
    <div class="card-translit">${entry.transliteration}</div>
    <div class="card-def">${entry.definition}</div>
    <div class="card-footer">
      <span class="badge badge-${entry.language.toLowerCase()}">${entry.language}</span>
      <span class="card-strongs">${entry.strongs_id}</span>
    </div>
  `;
  card.onclick = () => openModal(entry);
  return card;
}

// ─── Modal ───────────────────────────────────────────
function openModal(entry) {
  const modal   = document.getElementById('wordModal');
  const backdrop = document.getElementById('modalBackdrop');

  document.getElementById('modalLang').innerHTML =
    `<span class="badge badge-${entry.language.toLowerCase()}">${entry.language} · ${entry.category}</span>`;

  const origEl = document.getElementById('modalOriginal');
  origEl.textContent = entry.original;
  origEl.className   = `modal-original ${entry.language.toLowerCase()}`;

  document.getElementById('modalTranslit').textContent = entry.transliteration;
  document.getElementById('modalPronun').textContent   = entry.pronunciation
    ? `Pronunciation: ${entry.pronunciation}` : '';
  document.getElementById('modalStrongs').textContent  = entry.strongs_id;
  document.getElementById('modalDef').textContent      = entry.definition;
  document.getElementById('modalExtended').textContent = entry.extended_definition || '';
  document.getElementById('modalCat').textContent      = entry.category || '—';
  document.getElementById('modalKjv').textContent      = (entry.kjv_translations || []).join(', ') || '—';
  document.getElementById('modalUsage').textContent    = entry.usage_count
    ? `~${entry.usage_count.toLocaleString()}×` : '—';

  modal.classList.remove('hidden');
  backdrop.classList.remove('hidden');
  document.body.style.overflow = 'hidden';
}

function closeModal() {
  document.getElementById('wordModal').classList.add('hidden');
  document.getElementById('modalBackdrop').classList.add('hidden');
  document.body.style.overflow = '';
}

document.addEventListener('keydown', e => {
  if (e.key === 'Escape') closeModal();
  if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
    e.preventDefault();
    document.getElementById('searchInput').focus();
  }
});

// ─── Recent searches ─────────────────────────────────
function saveRecent(query) {
  let recent = getRecent().filter(r => r.toLowerCase() !== query.toLowerCase());
  recent.unshift(query);
  if (recent.length > MAX_RECENT) recent = recent.slice(0, MAX_RECENT);
  localStorage.setItem(RECENT_KEY, JSON.stringify(recent));
  renderRecent();
}

function getRecent() {
  try { return JSON.parse(localStorage.getItem(RECENT_KEY) || '[]'); } catch { return []; }
}

function renderRecent() {
  const tags    = document.getElementById('recentTags');
  const heading = document.getElementById('recentHeading');
  const recent  = getRecent();

  tags.innerHTML = '';

  if (recent.length === 0) {
    heading.style.display = 'none';
    return;
  }

  heading.style.display = 'block';
  recent.forEach(term => {
    const tag = document.createElement('span');
    tag.className = 'recent-tag';
    tag.textContent = term;
    tag.onclick = () => {
      document.getElementById('searchInput').value = term;
      onSearchInput(term);
    };
    tags.appendChild(tag);
  });
}
