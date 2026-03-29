const CACHE_NAME = "led-matrix-v1";

// Assets to cache on install (app shell)
const SHELL_ASSETS = [
  "/",
  "/manifest.json",
  "/icons/icon-192.png",
];

// Install: cache the app shell
self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(SHELL_ASSETS))
  );
  self.skipWaiting();
});

// Activate: clean up old caches
self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE_NAME).map((k) => caches.delete(k)))
    )
  );
  self.clients.claim();
});

// Fetch: network-first for API calls, cache-first for assets
self.addEventListener("fetch", (event) => {
  const url = new URL(event.request.url);

  // API calls and image uploads — always go to network
  if (
    url.pathname.startsWith("/api/") ||
    url.pathname.startsWith("/images/") ||
    url.pathname.startsWith("/upload_image") ||
    url.pathname.startsWith("/apply_changes") ||
    url.pathname.startsWith("/set_") ||
    url.pathname.startsWith("/turn_") ||
    url.pathname.startsWith("/delete_")
  ) {
    event.respondWith(fetch(event.request));
    return;
  }

  // App shell and static assets — cache-first, fallback to network
  event.respondWith(
    caches.match(event.request).then((cached) => {
      const networkFetch = fetch(event.request)
        .then((response) => {
          // Update cache with fresh version
          if (response.ok) {
            const clone = response.clone();
            caches.open(CACHE_NAME).then((cache) => cache.put(event.request, clone));
          }
          return response;
        })
        .catch(() => cached);

      return cached || networkFetch;
    })
  );
});
