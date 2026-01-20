const CACHE_NAME = "associacao-v1";

const URLS_TO_CACHE = [
  "/",
  "/login",
  "/static/css/bootstrap.min.css",
  "/static/js/bootstrap.bundle.min.js"
];

self.addEventListener("install", event => {
  event.waitUntil(
    caches.open(CACHE_NAME).then(cache => {
      return cache.addAll(URLS_TO_CACHE);
    })
  );
});

self.addEventListener("fetch", event => {
  event.respondWith(
    caches.match(event.request).then(response => {
      return response || fetch(event.request);
    })
  );
});
