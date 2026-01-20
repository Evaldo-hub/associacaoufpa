const CACHE_NAME = "associacao-v3";

const STATIC_ASSETS = [
  "/static/manifest.json",
  "/static/imagem.jpg"
];

// INSTALL
self.addEventListener("install", event => {
  event.waitUntil(
    caches.open(CACHE_NAME).then(cache => cache.addAll(STATIC_ASSETS))
  );
});

// ACTIVATE
self.addEventListener("activate", event => {
  event.waitUntil(
    caches.keys().then(keys =>
      Promise.all(
        keys
          .filter(key => key !== CACHE_NAME)
          .map(key => caches.delete(key))
      )
    )
  );
});

// FETCH (NETWORK FIRST PARA ROTAS FLASK)
self.addEventListener("fetch", event => {
  // Só trata GET
  if (event.request.method !== "GET") return;

  event.respondWith(
    fetch(event.request)
      .then(response => {
        // Salva assets estáticos
        if (event.request.url.includes("/static/")) {
          const responseClone = response.clone();
          caches.open(CACHE_NAME).then(cache => {
            cache.put(event.request, responseClone);
          });
        }
        return response;
      })
      .catch(() => {
        // Fallback só para assets
        return caches.match(event.request);
      })
  );
});
