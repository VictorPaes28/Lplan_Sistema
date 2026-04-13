/**
 * Modo offline dedicado ao formulário RDO (IndexedDB + Service Worker).
 * - Guarda rascunho local (texto, JSON de atividades/ocorrências, assinaturas em base64 nos hidden).
 * - Fotos/arquivos: não são fiéis offline; ao voltar a rede o utilizador deve confirmar anexos.
 */
(function () {
  'use strict';

  var DB_NAME = 'lplan_rdo_offline';
  var DB_VER = 1;
  var STORE = 'snapshots';

  function storageId() {
    return 'rdo|' + (window.location.pathname || '/');
  }

  function openDb() {
    return new Promise(function (resolve, reject) {
      var req = indexedDB.open(DB_NAME, DB_VER);
      req.onerror = function () {
        reject(req.error);
      };
      req.onupgradeneeded = function () {
        var db = req.result;
        if (!db.objectStoreNames.contains(STORE)) {
          db.createObjectStore(STORE, { keyPath: 'id' });
        }
      };
      req.onsuccess = function () {
        resolve(req.result);
      };
    });
  }

  function saveSnapshot(record) {
    return openDb().then(function (db) {
      return new Promise(function (resolve, reject) {
        var tx = db.transaction(STORE, 'readwrite');
        tx.oncomplete = function () {
          resolve();
        };
        tx.onerror = function () {
          reject(tx.error);
        };
        record.id = storageId();
        record.savedAt = Date.now();
        tx.objectStore(STORE).put(record);
      });
    });
  }

  function loadSnapshot() {
    return openDb().then(function (db) {
      return new Promise(function (resolve, reject) {
        var tx = db.transaction(STORE, 'readonly');
        var req = tx.objectStore(STORE).get(storageId());
        req.onsuccess = function () {
          resolve(req.result || null);
        };
        req.onerror = function () {
          reject(req.error);
        };
      });
    });
  }

  function clearSnapshot() {
    return openDb().then(function (db) {
      return new Promise(function (resolve, reject) {
        var tx = db.transaction(STORE, 'readwrite');
        tx.oncomplete = function () {
          resolve();
        };
        tx.onerror = function () {
          reject(tx.error);
        };
        tx.objectStore(STORE).delete(storageId());
      });
    });
  }

  function collectFields(form) {
    var data = {};
    var filesMeta = [];
    var els = form.querySelectorAll('input, textarea, select');
    for (var i = 0; i < els.length; i++) {
      var el = els[i];
      var name = el.name;
      if (!name || el.disabled) continue;
      var tag = (el.tagName || '').toLowerCase();
      var type = (el.type || '').toLowerCase();
      if (type === 'file') {
        if (el.files && el.files.length) {
          filesMeta.push({ name: name, count: el.files.length, names: Array.prototype.map.call(el.files, function (f) { return f.name; }) });
        }
        continue;
      }
      if (type === 'checkbox' || type === 'radio') {
        if (!el.checked) continue;
        if (type === 'radio') {
          data[name] = el.value;
        } else {
          if (!data[name]) data[name] = [];
          data[name].push(el.value);
        }
        continue;
      }
      data[name] = el.value;
    }
    return { fields: data, filesMeta: filesMeta };
  }

  function applyFields(form, data) {
    var fields = data.fields || {};
    Object.keys(fields).forEach(function (name) {
      var val = fields[name];
      var els = form.querySelectorAll('[name="' + String(name).replace(/\\/g, '\\\\').replace(/"/g, '\\"') + '"]');
      if (!els.length) return;
      if (Array.isArray(val)) {
        els.forEach(function (el) {
          if (val.indexOf(el.value) !== -1) el.checked = true;
        });
        return;
      }
      var el = els[0];
      if (!el) return;
      if (el.type === 'checkbox' || el.type === 'radio') {
        el.checked = String(val) === el.value;
      } else {
        el.value = val;
      }
      try {
        el.dispatchEvent(new Event('input', { bubbles: true }));
        el.dispatchEvent(new Event('change', { bubbles: true }));
      } catch (e) {}
    });
  }

  function buildBanner() {
    var bar = document.createElement('div');
    bar.id = 'rdo-offline-banner';
    bar.setAttribute('role', 'status');
    bar.style.cssText =
      'position:fixed;bottom:0;left:0;right:0;z-index:99998;padding:10px 14px;font-size:13px;display:none;' +
      'align-items:center;justify-content:space-between;gap:10px;flex-wrap:wrap;' +
      'background:#1e293b;color:#f8fafc;box-shadow:0 -4px 20px rgba(0,0,0,.2);';
    bar.innerHTML =
      '<span id="rdo-offline-banner-text"><i class="fas fa-wifi-slash" style="margin-right:8px;"></i><strong>Sem conexão.</strong> O texto do relatório é guardado neste aparelho. Fotos e anexos só enviam com internet.</span>' +
      '<span style="display:flex;gap:8px;flex-wrap:wrap;">' +
      '<button type="button" id="rdo-offline-restore-btn" class="px-3 py-1.5 rounded-md text-xs font-semibold bg-slate-600 hover:bg-slate-500" style="display:none">Restaurar rascunho</button>' +
      '<button type="button" id="rdo-offline-clear-btn" class="px-3 py-1.5 rounded-md text-xs font-semibold bg-slate-700 hover:bg-slate-600">Limpar cópia local</button>' +
      '</span>';
    document.body.appendChild(bar);
    return bar;
  }

  function setOnlineUi(online) {
    var bar = document.getElementById('rdo-offline-banner');
    if (!bar) return;
    var text = document.getElementById('rdo-offline-banner-text');
    if (online) {
      bar.style.display = 'none';
      if (text) {
        text.innerHTML = '<i class="fas fa-wifi" style="margin-right:8px;"></i><strong>Conexão restabelecida.</strong> Pode enviar o relatório.';
      }
    } else {
      bar.style.display = 'flex';
      if (text) {
        text.innerHTML =
          '<i class="fas fa-wifi-slash" style="margin-right:8px;"></i><strong>Sem conexão.</strong> O texto é guardado automaticamente neste aparelho. <span style="opacity:.9">Fotos/anexos: adicione de novo após recuperar a rede.</span>';
      }
    }
  }

  function registerServiceWorker(swUrl) {
    if (!('serviceWorker' in navigator)) return;
    navigator.serviceWorker
      .register(swUrl, { scope: '/' })
      .catch(function () {});
  }

  function init() {
    var form = document.getElementById('diary-form');
    if (!form) return;

    var swUrl = form.getAttribute('data-rdo-sw-url');
    if (swUrl) registerServiceWorker(swUrl);

    var banner = buildBanner();
    var restoreBtn = document.getElementById('rdo-offline-restore-btn');
    var clearBtn = document.getElementById('rdo-offline-clear-btn');

    /**
     * Só persiste em IndexedDB quando está offline.
     * Com internet, NÃO chamar buildAndSetDiaryJsonPayload em background — isso altera
     * work_logs_json / TOTAL_FORMS e pode interferir no fluxo normal do formulário.
     */
    function persistOfflineOnly() {
      if (navigator.onLine) return;
      try {
        if (typeof window.buildAndSetDiaryJsonPayload === 'function') {
          window.buildAndSetDiaryJsonPayload();
        }
      } catch (e) {}
      saveSnapshot(collectFields(form)).catch(function () {});
    }

    var t = null;
    function schedulePersistOffline() {
      if (navigator.onLine) return;
      clearTimeout(t);
      t = setTimeout(persistOfflineOnly, 600);
    }

    form.addEventListener('input', schedulePersistOffline, true);
    form.addEventListener('change', schedulePersistOffline, true);

    setInterval(function () {
      if (document.hidden || navigator.onLine) return;
      persistOfflineOnly();
    }, 35000);

    loadSnapshot().then(function (snap) {
      if (!snap || !snap.fields) return;
      if (restoreBtn) {
        restoreBtn.style.display = 'inline-block';
        restoreBtn.onclick = function () {
          applyFields(form, snap);
          if (typeof window.restoreSignatureFromHidden === 'function') {
            try {
              window.restoreSignatureFromHidden(1);
              window.restoreSignatureFromHidden(2);
            } catch (e) {}
          }
          try {
            if (typeof window.buildAndSetDiaryJsonPayload === 'function') {
              window.buildAndSetDiaryJsonPayload();
            }
          } catch (e) {}
          banner.style.display = 'flex';
          if (navigator.onLine) {
            setOnlineUi(true);
            banner.style.display = 'flex';
            document.getElementById('rdo-offline-banner-text').innerHTML =
              '<i class="fas fa-check-circle" style="margin-right:8px;"></i>Rascunho local aplicado. Revise e guarde no servidor.';
          }
        };
      }
    });

    if (clearBtn) {
      clearBtn.onclick = function () {
        clearSnapshot().then(function () {
          if (restoreBtn) restoreBtn.style.display = 'none';
        });
      };
    }

    window.addEventListener('online', function () {
      setOnlineUi(true);
      setTimeout(function () {
        var b = document.getElementById('rdo-offline-banner');
        if (b) b.style.display = 'none';
      }, 4000);
    });
    window.addEventListener('offline', function () {
      setOnlineUi(false);
    });
    if (!navigator.onLine) setOnlineUi(false);

    form.addEventListener(
      'submit',
      function (e) {
        if (navigator.onLine) {
          return;
        }
        e.preventDefault();
        e.stopPropagation();
        if (typeof e.stopImmediatePropagation === 'function') {
          e.stopImmediatePropagation();
        }
        try {
          if (typeof window.buildAndSetDiaryJsonPayload === 'function') {
            window.buildAndSetDiaryJsonPayload();
          }
        } catch (err) {}
        saveSnapshot(collectFields(form))
          .then(function () {
            alert(
              'Sem conexão: não é possível enviar ao servidor agora.\n\n' +
                'O conteúdo foi guardado neste aparelho. Quando a internet voltar, abra esta página outra vez e use «Salvar rascunho» ou «Salvar diário».'
            );
          })
          .catch(function () {
            alert('Sem conexão. Tente novamente quando tiver rede.');
          });
        return false;
      },
      true
    );
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
