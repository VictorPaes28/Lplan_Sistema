(function () {
  'use strict';
  var root = document.getElementById('mapa-geo-app');
  if (!root) return;

  var apiFolders = root.dataset.apiFolders || '';
  var apiAlerts = root.dataset.apiAlerts || '';
  var apiCompare = root.dataset.apiCompare || '';
  var undoStack = [];
  var redoStack = [];
  var compareActive = false;
  var baseLayerOsm = null;
  var baseLayerSat = null;
  var currentBase = 'osm';

  function mg() {
    return window.MapaGeo || null;
  }

  function waitForMapaGeo(cb, tries) {
    tries = tries || 0;
    if (mg() && mg().getMap()) return cb();
    if (tries > 40) return;
    setTimeout(function () { waitForMapaGeo(cb, tries + 1); }, 150);
  }

  function initBaseLayers() {
    var map = mg().getMap();
    baseLayerOsm = L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      maxZoom: 19,
      attribution: '&copy; OpenStreetMap',
    });
    baseLayerSat = L.tileLayer(
      'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
      { maxZoom: 19, attribution: 'Esri, Maxar' }
    );
    map.eachLayer(function (layer) {
      if (layer instanceof L.TileLayer) map.removeLayer(layer);
    });
    baseLayerOsm.addTo(map);
    var sel = document.getElementById('mg-base-layer');
    if (sel) {
      sel.addEventListener('change', function () {
        currentBase = sel.value;
        map.removeLayer(baseLayerOsm);
        map.removeLayer(baseLayerSat);
        if (currentBase === 'satellite') baseLayerSat.addTo(map);
        else baseLayerOsm.addTo(map);
      });
    }
  }

  function loadFolders() {
    if (!apiFolders) return;
    fetch(apiFolders, { credentials: 'same-origin', headers: { Accept: 'application/json' } })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        var sel = document.getElementById('mg-filter-folder');
        if (!sel) return;
        var current = sel.value;
        sel.innerHTML = '<option value="">Todas as pastas</option>';
        (data.folders || []).forEach(function (f) {
          var opt = document.createElement('option');
          opt.value = f;
          opt.textContent = f;
          sel.appendChild(opt);
        });
        if (current) sel.value = current;
      });
  }

  function loadAlerts() {
    if (!apiAlerts) return;
    fetch(apiAlerts, { credentials: 'same-origin', headers: { Accept: 'application/json' } })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        var panel = document.getElementById('mg-alerts-panel');
        var list = document.getElementById('mg-alerts-list');
        var count = document.getElementById('mg-alerts-count');
        if (!panel || !list) return;
        var items = data.items || [];
        if (count) count.textContent = String(items.length);
        if (!items.length) {
          panel.hidden = true;
          return;
        }
        panel.hidden = false;
        list.innerHTML = items.map(function (item) {
          var cls = 'mapa-geo-alert mapa-geo-alert--' + (item.severity || 'low');
          var link = item.url
            ? '<a href="' + item.url + '" class="mg-popup-link">Ver</a>'
            : (item.feature_id
              ? '<button type="button" class="mg-btn mg-btn--xs mg-btn--secondary mg-alert-focus" data-feature="' + item.feature_id + '"><span>Ir ao mapa</span></button>'
              : '');
          return '<div class="' + cls + '"><span>' + item.message + '</span> ' + link + '</div>';
        }).join('');
        list.querySelectorAll('.mg-alert-focus').forEach(function (btn) {
          btn.addEventListener('click', function () {
            var id = btn.dataset.feature;
            var layer = null;
            if (mg().getMap && id) {
              mg().getMap().eachLayer(function (l) {
                if (String(l.featureId) === String(id)) layer = l;
              });
            }
            if (layer && layer.getBounds) mg().getMap().fitBounds(layer.getBounds(), { padding: [40, 40] });
            else if (layer && layer.getLatLng) mg().getMap().setView(layer.getLatLng(), 16);
            if (layer) layer.openPopup();
          });
        });
      });
  }

  function fillCompareDates() {
    var dates = mg().getTimelineDates();
    var a = document.getElementById('mg-compare-date-a');
    var b = document.getElementById('mg-compare-date-b');
    if (!a || !b || !dates.length) return;
    function fill(sel) {
      sel.innerHTML = '';
      dates.forEach(function (d) {
        var opt = document.createElement('option');
        opt.value = d;
        opt.textContent = d.split('-').reverse().join('/');
        sel.appendChild(opt);
      });
    }
    fill(a);
    fill(b);
    if (dates.length > 1) {
      a.value = dates[0];
      b.value = dates[dates.length - 1];
    }
  }

  function loadCompare() {
    if (!apiCompare || !compareActive) return;
    var a = document.getElementById('mg-compare-date-a');
    var b = document.getElementById('mg-compare-date-b');
    if (!a || !b || !a.value || !b.value) return;
    var url = apiCompare + '?date_a=' + encodeURIComponent(a.value) + '&date_b=' + encodeURIComponent(b.value);
    fetch(url, { credentials: 'same-origin', headers: { Accept: 'application/json' } })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        mg().renderGeojson(data, { fit: false });
        var stats = (data.meta && data.meta.stats) || {};
        var legend = document.getElementById('mg-compare-legend');
        if (legend) legend.hidden = false;
        mg().showToast(
          'Comparação: ' + (stats.changed || 0) + ' alterados, ' + (stats.added || 0) + ' novos, ' + (stats.same || 0) + ' iguais',
          'info'
        );
      })
      .catch(function () { mg().showToast('Falha ao comparar datas.', 'error'); });
  }

  function initCompare() {
    var toggle = document.getElementById('mg-compare-toggle');
    var a = document.getElementById('mg-compare-date-a');
    var b = document.getElementById('mg-compare-date-b');
    if (!toggle) return;
    toggle.addEventListener('change', function () {
      compareActive = toggle.checked;
      if (a) a.disabled = !compareActive;
      if (b) b.disabled = !compareActive;
      var legend = document.getElementById('mg-compare-legend');
      if (compareActive) {
        fillCompareDates();
        loadCompare();
      } else {
        if (legend) legend.hidden = true;
        if (mg().loadFeatures) mg().loadFeatures(mg().getCurrentDate());
      }
    });
    if (a) a.addEventListener('change', loadCompare);
    if (b) b.addEventListener('change', loadCompare);
  }

  function pushUndo(action) {
    undoStack.push(action);
    if (undoStack.length > 30) undoStack.shift();
    redoStack = [];
  }

  function initUndoRedo() {
    var map = mg().getMap();
    if (!map || !map.pm) return;
    map.on('pm:create', function (e) {
      pushUndo({ type: 'create', layer: e.layer });
    });
    map.on('pm:remove', function (e) {
      var geo = e.layer.toGeoJSON();
      if (e.layer.featureProps) geo.properties = Object.assign({}, e.layer.featureProps);
      pushUndo({ type: 'remove', layer: e.layer, geo: geo, props: e.layer.featureProps });
    });
    var undoBtn = document.getElementById('mg-undo');
    var redoBtn = document.getElementById('mg-redo');
    if (undoBtn) undoBtn.addEventListener('click', performUndo);
    if (redoBtn) redoBtn.addEventListener('click', performRedo);
    document.addEventListener('keydown', function (e) {
      if (!e.ctrlKey && !e.metaKey) return;
      if (e.key === 'z' && !e.shiftKey) { e.preventDefault(); performUndo(); }
      if (e.key === 'y' || (e.key === 'z' && e.shiftKey)) { e.preventDefault(); performRedo(); }
    });
  }

  function performUndo() {
    var action = undoStack.pop();
    if (!action) return;
    redoStack.push(action);
    if (action.type === 'create' && action.layer) {
      action.layer.remove();
    } else if (action.type === 'remove' && action.geo && mg().addFeatureToMap) {
      mg().addFeatureToMap(action.geo);
    }
    mg().showToast('Desfeito.', 'info');
  }

  function performRedo() {
    var action = redoStack.pop();
    if (!action) return;
    undoStack.push(action);
    var map = mg().getMap();
    if (action.type === 'create' && action.layer && map) {
      map.addLayer(action.layer);
    } else if (action.type === 'remove' && action.layer) {
      action.layer.remove();
    }
    mg().showToast('Refeito (visual). Salve novamente se necessário.', 'info');
  }

  function initOffline() {
    if (!('serviceWorker' in navigator)) return;
    navigator.serviceWorker.register('/static/mapa_geo/js/mapa_sw.js', { scope: '/mapa-geo/' }).catch(function () {});
  }

  function initFolderFilter() {
    var sel = document.getElementById('mg-filter-folder');
    if (!sel) return;
    sel.addEventListener('change', function () {
      if (compareActive) loadCompare();
      else if (mg().loadFeatures) mg().loadFeatures(mg().getCurrentDate());
    });
  }

  function initRelatorioLink() {
    var link = document.getElementById('mg-relatorio-link');
    if (!link) return;
    link.addEventListener('click', function () {
      var d = mg().getCurrentDate && mg().getCurrentDate();
      if (d) link.href = link.href.split('?')[0] + '?date=' + encodeURIComponent(d);
    });
  }

  document.addEventListener('DOMContentLoaded', function () {
    waitForMapaGeo(function () {
      initBaseLayers();
      loadFolders();
      loadAlerts();
      initCompare();
      initUndoRedo();
      initOffline();
      initFolderFilter();
      initRelatorioLink();
      setInterval(loadAlerts, 120000);
    });
  });
})();
