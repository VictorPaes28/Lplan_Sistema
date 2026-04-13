/* global self, caches, fetch */
/**
 * Service Worker dedicado ao formulário RDO: cache de estáticos e da última página do formulário.
 * Escopo ampliado via header Service-Worker-Allowed na view Django.
 */
var CACHE_NAME = 'lplan-rdo-offline-v1';
var STATIC_URLS = [
  '/static/core/css/daily_log_form.css',
  '/static/core/css/base.css',
  '/static/core/css/tailwind-utilities.css',
  '/static/core/css/mobile.css',
  '/static/core/js/theme-global.js'
];

self.addEventListener('install', function (event) {
  event.waitUntil(
    caches.open(CACHE_NAME).then(function (cache) {
      return cache.addAll(STATIC_URLS).catch(function () {
        return Promise.resolve();
      });
    })
  );
  self.skipWaiting();
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
