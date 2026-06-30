/* slash-radar Service Worker：殼層 cache-first（秒開）、資料 network-first（新鮮，離線退上一份快照）。 */
const C = "slash-radar-v1";
const SHELL = ["./", "index.html", "app.html", "signals.html", "calculator.html", "learning.html",
  "static/auth.js", "manifest.json", "static/icon-192.png", "static/icon-512.png"];

self.addEventListener("install", e => {
  e.waitUntil(caches.open(C).then(c => c.addAll(SHELL).catch(() => {})).then(() => self.skipWaiting()));
});
self.addEventListener("activate", e => {
  e.waitUntil(caches.keys().then(ks => Promise.all(ks.filter(k => k !== C).map(k => caches.delete(k))))
    .then(() => self.clients.claim()));
});
self.addEventListener("fetch", e => {
  if (e.request.method !== "GET") return;
  const u = new URL(e.request.url);
  const isData = u.pathname.endsWith("board.json") || u.pathname.endsWith("signals.json");
  if (isData) {
    // 去掉 ?t= cache-bust 後用穩定 key 快取，離線時可退上一份
    const key = new Request(u.origin + u.pathname);
    e.respondWith(
      fetch(e.request).then(r => { const cp = r.clone(); caches.open(C).then(c => c.put(key, cp)); return r; })
        .catch(() => caches.match(key))
    );
  } else {
    e.respondWith(caches.match(e.request).then(r => r || fetch(e.request)));
  }
});
