const CACHE = "icebeach-shell-v2";
const SHELL = ["/", "/index.html", "/manifest.webmanifest", "/icons/icon.svg", "/icons/icon-192.png", "/icons/icon-512.png"];

self.addEventListener("install", (event) => {
  event.waitUntil(caches.open(CACHE).then((cache) => cache.addAll(SHELL)));
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  // Старый кэш (v1) хранил прежние тёмные иконки — удаляем всё, кроме текущего.
  event.waitUntil(
    caches
      .keys()
      .then((keys) => Promise.all(keys.filter((key) => key !== CACHE).map((key) => caches.delete(key))))
      .then(() => self.clients.claim()),
  );
});

self.addEventListener("fetch", (event) => {
  if (event.request.method !== "GET") return;
  const url = new URL(event.request.url);
  if (url.pathname.startsWith("/api") || url.port === "8000") return;

  event.respondWith(
    fetch(event.request).catch(() =>
      caches.match(event.request).then((cached) => {
        if (cached) return cached;
        // index.html отдаём только вместо страниц: подмена картинки HTML-кодом
        // и давала в консоли «icon-192.png … not a valid image».
        if (event.request.mode === "navigate") return caches.match("/index.html");
        return Response.error();
      }),
    ),
  );
});
