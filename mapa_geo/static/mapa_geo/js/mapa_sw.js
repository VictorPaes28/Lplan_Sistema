/* Service worker básico — cache de assets estáticos do Mapa Geográfico para uso offline parcial */
var CACHE = 'mapa-geo-v1';
var ASSETS = [
  '/static/mapa_geo/css/mapa.css',
  '/static/mapa_geo/js/mapa.js',
  '/static/mapa_geo/js/mapa_extras.js',
];

self.addEventListener('install', function (event) {
  event.waitUntil(
    caches.open(CACHE).then(function (cache) {
      return cache.addAll(ASSETS);
    })
  );
  self.skipWaiting();
});

self.addEventListener('fetch', function (event) {
  var url = event.request.url;
  if (url.indexOf('/static/mapa_geo/') >= 0) {
    event.respondWith(
      caches.match(event.request).then(function (cached) {
        return cached || fetch(event.request);
      })
    );
  }
});
