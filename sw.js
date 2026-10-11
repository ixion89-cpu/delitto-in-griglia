const CACHE = 'delitto-v4';
const ASSETS = ['./', './index.html', './style.css', './app.js', './puzzles.js', './puzzles.json', './manifest.json',
  './icons/icon-192.png', './icons/icon-512.png', './icons/apple-touch-icon.png',
  './assets/bg/hangar.webp',
  './assets/cast/livia.webp', './assets/cast/vasquez.webp', './assets/cast/brenner.webp', './assets/cast/okafor.webp',
  './assets/cast/nadia.webp', './assets/cast/halvorsen.webp', './assets/cast/mei.webp',
  './assets/faces/vasquez.webp', './assets/faces/brenner.webp', './assets/faces/okafor.webp',
  './assets/faces/nadia.webp', './assets/faces/halvorsen.webp', './assets/faces/mei.webp',
  './assets/expr/livia-neutral.webp', './assets/expr/livia-surprised.webp', './assets/expr/livia-angry.webp', './assets/expr/livia-worried.webp',
  './assets/expr/vasquez-neutral.webp', './assets/expr/vasquez-surprised.webp', './assets/expr/vasquez-angry.webp', './assets/expr/vasquez-worried.webp'];
self.addEventListener('install', e => {
  e.waitUntil(caches.open(CACHE).then(c => c.addAll(ASSETS)).then(() => self.skipWaiting()));
});
self.addEventListener('activate', e => {
  e.waitUntil(caches.keys().then(ks => Promise.all(ks.filter(k => k !== CACHE).map(k => caches.delete(k)))).then(() => self.clients.claim()));
});
self.addEventListener('fetch', e => {
  if (e.request.method !== 'GET') return;
  e.respondWith(caches.match(e.request, {ignoreSearch: true}).then(r => r || fetch(e.request).then(resp => {
    const copy = resp.clone();
    if (resp.ok && new URL(e.request.url).origin === location.origin) caches.open(CACHE).then(c => c.put(e.request, copy));
    return resp;
  }).catch(() => caches.match('./index.html'))));
});
