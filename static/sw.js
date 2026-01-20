const CACHE_NAME = "associacao-v2";

const URLS_TO_CACHE = [
  "/",
  "/login",
  "/static/manifest.json",
  "/static/imagem.jpg"
];

// INSTALAÇÃO
self.addEventListener("install", event => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then(cache => {
        return cache.addAll(URLS_TO_CACHE);
      })
      .catch(err => {
        console.error("❌ Erro ao cachear arquivos:", err);
      })
  );
});

// ATIVAÇÃO (remove caches antigos)
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

// FETCH
self.addEventListener("fetch", event => {
  event.respondWith(
    caches.match(event.request)
      .then(response => response || fetch(event.request))
      .catch(() => caches.match("/login"))
  );
});
