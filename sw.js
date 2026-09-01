const CACHE = 'min-arbetsdag-v3';

self.addEventListener('install', event => {
  self.skipWaiting();

  event.waitUntil(
    caches.open(CACHE).then(cache =>
      cache.addAll([
        './',
        './index.html',
        './manifest.webmanifest'
      ])
    )
  );
});

self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys().then(keys =>
      Promise.all(
        keys
          .filter(key => key !== CACHE)
          .map(key => caches.delete(key))
      )
    ).then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', event => {
  if (event.request.method !== 'GET') return;

  event.respondWith(
    fetch(event.request)
      .then(response => {
        const copy = response.clone();

        if (event.request.url.startsWith(self.location.origin)) {
          caches.open(CACHE).then(cache =>
            cache.put(event.request, copy)
          );
        }

        return response;
      })
      .catch(() => caches.match(event.request))
  );
});
