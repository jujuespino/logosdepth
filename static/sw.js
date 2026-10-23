/* LogosDepth service worker.
   __VERSION__ and __PRECACHE__ are filled in by the server (see /sw.js in app.py), so every deploy
   gets a fresh cache and old caches are removed on activate.

   Strategies:
   - App shell and static assets: precached on install, cache-first (they are versioned by the cache name).
   - Pages ("/"): network-first, falling back to the cached shell when offline.
   - /api/ GET requests: network-first (fresh data when online), falling back to the last good response.
   Progress is stored in localStorage by the page itself, so it is never touched here. */

const VERSION = '__VERSION__';
const CACHE = `logosdepth-${VERSION}`;
const PRECACHE = __PRECACHE__;
const API_PREFIX = '/api/';

self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE)
      .then(cache => cache.addAll(PRECACHE))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys()
      .then(keys => Promise.all(keys.filter(k => k.startsWith('logosdepth-') && k !== CACHE).map(k => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

async function networkFirst(request, fallbackUrl) {
  const cache = await caches.open(CACHE);
  try {
    const fresh = await fetch(request);
    if (fresh.ok) cache.put(request, fresh.clone());
    return fresh;
  } catch (err) {
    const cached = (await cache.match(request)) || (fallbackUrl && (await cache.match(fallbackUrl)));
    if (cached) return cached;
    throw err;
  }
}

async function cacheFirst(request) {
  const cache = await caches.open(CACHE);
  const cached = await cache.match(request);
  if (cached) return cached;
  const fresh = await fetch(request);
  if (fresh.ok) cache.put(request, fresh.clone());
  return fresh;
}

self.addEventListener('fetch', event => {
  const { request } = event;
  if (request.method !== 'GET') return;
  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return;

  if (url.pathname.startsWith(API_PREFIX)) {
    event.respondWith(networkFirst(request));
  } else if (request.mode === 'navigate') {
    // The app lives at "/". The public pages are separate documents and must not be answered with the app shell.
    if (url.pathname === '/') event.respondWith(networkFirst(new Request('/'), '/'));
    else if (url.pathname === '/about' || url.pathname === '/privacy') event.respondWith(networkFirst(request));
  } else if (url.pathname.startsWith('/static/') || url.pathname === '/manifest.webmanifest') {
    event.respondWith(cacheFirst(request));
  }
});
