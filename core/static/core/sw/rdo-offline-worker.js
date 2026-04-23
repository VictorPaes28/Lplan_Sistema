/* global self, caches, fetch */
/**
 * Service Worker dedicado ao formulário RDO: cache de estáticos e da última página do formulário.
 * Escopo ampliado via header Service-Worker-Allowed na view Django.
 * URLs de estáticos (com hash em produção) vêm da página via postMessage CACHE_URLS.
 */
var CACHE_NAME = 'lplan-rdo-offline-v2';
var STATIC_URLS = []; // preenchido via postMessage

self.addEventListener('message', function (event) {
  if (event.data && event.data.type === 'CACHE_URLS') {
    STATIC_URLS = event.data.urls || [];
    caches.open(CACHE_NAME).then(function (cache) {
      if (!STATIC_URLS.length) return Promise.resolve();
      return cache.addAll(STATIC_URLS).catch(function () {
        return Promise.resolve();
      });
    });
  }
});

self.addEventListener('install', function (event) {
  event.waitUntil(self.skipWaiting());
});

self.addEventListener('activate', function (event) {
  event.waitUntil(self.clients.claim());
});

self.addEventListener('fetch', function (event) {
  var req = event.request;
  if (req.method !== 'GET') return;

  var url = req.url;
  if (url.indexOf('/static/') !== -1) {
    event.respondWith(
      caches.match(req).then(function (cached) {
        return (
          cached ||
          fetch(req).then(function (res) {
            if (res && res.ok) {
              var copy = res.clone();
              caches.open(CACHE_NAME).then(function (cache) {
                cache.put(req, copy);
              });
            }
            return res;
          })
        );
      })
    );
    return;
  }

  var path = '';
  try {
    path = new URL(url).pathname;
  } catch (e) {
    return;
  }
  var isDiaryFormPage = /\/diaries\/(new\/|\d+\/edit\/)/.test(path);
  if (isDiaryFormPage) {
    event.respondWith(
      fetch(req)
        .then(function (res) {
          if (res && res.ok) {
            var copy = res.clone();
            caches.open(CACHE_NAME).then(function (cache) {
              cache.put(req, copy);
            });
          }
          return res;
        })
        .catch(function () {
          return caches.match(req);
        })
    );
  }
});
