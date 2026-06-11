(function () {

  'use strict';

  var root = document.getElementById('mapa-geo-app');

  if (!root) return;



  var canEdit = root.dataset.canEdit === '1';

  var apiFeatures = root.dataset.apiFeatures;

  var apiTimeline = root.dataset.apiTimeline;

  var apiFeatureDetailTpl = root.dataset.apiFeatureDetail || '';

  var apiActivities = root.dataset.apiActivities || '';

  var apiSync = root.dataset.apiSync || '';

  var centerLat = parseFloat(root.dataset.centerLat);

  var centerLng = parseFloat(root.dataset.centerLng);

  var defaultZoom = parseInt(root.dataset.zoom, 10) || 10;

  var focusDiary = root.dataset.focusDiary || '';

  var focusFeature = root.dataset.focusFeature || '';

  var expectedProjectId = root.dataset.projectId || '';



  var slider = document.getElementById('mg-timeline');

  var timelineWrap = document.getElementById('mg-timeline-wrap');

  var dateLabel = document.getElementById('mg-current-date');

  var timelinePrev = document.getElementById('mg-timeline-prev');

  var timelineNext = document.getElementById('mg-timeline-next');

  var timelineStart = document.getElementById('mg-timeline-start');

  var timelineEnd = document.getElementById('mg-timeline-end');

  var sliderShell = document.querySelector('.mapa-geo-slider-shell');

  var countEl = document.getElementById('mg-feature-count');

  var kpiProgress = document.getElementById('mg-kpi-progress');

  var searchInput = document.getElementById('mg-search');

  var filterLines = document.getElementById('mg-filter-lines');

  var filterPoints = document.getElementById('mg-filter-points');

  var filterPolygons = document.getElementById('mg-filter-polygons');

  var filterGps = document.getElementById('mg-filter-gps');

  var fitBoundsBtn = document.getElementById('mg-fit-bounds');

  var toggleEditBtn = document.getElementById('mg-toggle-edit');

  var togglePanelBtn = document.getElementById('mg-toggle-panel');

  var panelReopenBtn = document.getElementById('mg-panel-reopen');

  var filtersToggle = document.getElementById('mg-filters-toggle');

  var filtersBody = document.getElementById('mg-filters-body');

  var emptyHint = document.getElementById('mg-empty-hint');

  var exportWrap = document.getElementById('mg-export-wrap');

  var exportToggle = document.getElementById('mg-export-toggle');

  var exportMenu = document.getElementById('mg-export-menu');

  var moreToggle = document.getElementById('mg-more-toggle');

  var moreMenu = document.getElementById('mg-more-menu');

  var syncBtn = document.getElementById('mg-sync-diario');

  var drawTools = document.getElementById('mg-draw-tools');

  var workspace = document.getElementById('mg-workspace');

  var sidePanel = document.getElementById('mg-side-panel');

  var featureList = document.getElementById('mg-feature-list');

  var listCount = document.getElementById('mg-list-count');

  var drawer = document.getElementById('mg-drawer');

  var drawerBackdrop = document.getElementById('mg-drawer-backdrop');

  var helpOverlay = document.getElementById('mg-help-overlay');

  var helpToggle = document.getElementById('mg-help-toggle');

  var helpClose = document.getElementById('mg-help-close');

  var featureForm = document.getElementById('mg-feature-form');

  var saveAndNextBtn = document.getElementById('mg-save-and-next');

  var toastHost = document.getElementById('mg-toast-host');



  var map = null;

  var lineLayer = null;

  var polygonLayer = null;

  var clusterGroup = null;

  var editableLayer = null;

  var editMode = false;

  var currentTool = 'pan';

  var timelineDates = [];

  var currentGeo = null;

  var layerIndex = {};

  var diaryLayerIndex = {};

  var pendingLayer = null;

  var lastBounds = [];

  var focusHandled = false;

  var selectedFeatureId = null;

  var panelOpen = true;

  var drawerOpen = false;

  var lastDrawTool = 'line';



  var SNAP_DISTANCE = 15;

  var kindLabels = {

    segment: 'Trecho',

    point: 'Ponto',

    obstacle: 'Obstáculo',

    vistoria: 'Vistoria',

    caixa: 'Caixa',

    area: 'Área',

    other: 'Outro',

  };



  function getCsrf() {

    var meta = document.querySelector('meta[name="csrf-token"]');

    if (meta && meta.content) return meta.content;

    if (typeof window.__LPLAN_CSRF_TOKEN__ === 'string') return window.__LPLAN_CSRF_TOKEN__;

    return '';

  }



  function apiDetailUrl(id) {

    return apiFeatureDetailTpl.replace('/0/', '/' + id + '/');

  }



  function showToast(message, type) {

    type = type || 'info';

    var host = toastHost || document.getElementById('messages-container');

    if (!host) {

      host = document.createElement('div');

      host.id = 'mg-toast-host';

      host.className = 'mapa-geo-toast-host';

      document.body.appendChild(host);

    }

    var icons = {

      success: 'fa-check-circle',

      error: 'fa-exclamation-circle',

      warning: 'fa-exclamation-triangle',

      info: 'fa-info-circle',

    };

    var toast = document.createElement('div');

    toast.className = 'toast-msg toast-' + type;

    toast.style.pointerEvents = 'auto';

    toast.innerHTML =

      '<div class="toast-icon"><i class="fas ' + (icons[type] || icons.info) + '"></i></div>' +

      '<div class="toast-body"><p>' + escapeHtml(message) + '</p></div>' +

      '<button type="button" class="toast-close" aria-label="Fechar"><i class="fas fa-times"></i></button>' +

      '<div class="toast-timer"></div>';

    toast.querySelector('.toast-close').addEventListener('click', function () {

      toast.classList.add('toast-exit');

      setTimeout(function () { toast.remove(); }, 300);

    });

    host.appendChild(toast);

    setTimeout(function () {

      if (!toast.parentNode) return;

      toast.classList.add('toast-exit');

      setTimeout(function () { toast.remove(); }, 300);

    }, 5000);

  }



  function progressColor(pct) {

    if (pct >= 76) return '#22c55e';

    if (pct >= 51) return '#eab308';

    if (pct >= 26) return '#f97316';

    return '#ef4444';

  }



  function statusLabel(status) {

    var labels = {

      planned: 'Planejado',

      in_progress: 'Em andamento',

      completed: 'Concluído',

      blocked: 'Bloqueado',

      vistoria: 'Vistoria',

    };

    return labels[status] || status;

  }



  function escapeHtml(str) {

    return String(str)

      .replace(/&/g, '&amp;')

      .replace(/</g, '&lt;')

      .replace(/>/g, '&gt;')

      .replace(/"/g, '&quot;');

  }



  function formatDateBr(iso) {

    if (!iso) return 'Hoje';

    var p = iso.split('-');

    if (p.length !== 3) return iso;

    return p[2] + '/' + p[1] + '/' + p[0];

  }



  function layerToGeoJSON(layer) {

    return layer.toGeoJSON().geometry;

  }



  function defaultKindForGeometry(layer) {

    if (!layer || !layer.toGeoJSON) return 'other';

    var gtype = layer.toGeoJSON().geometry.type;

    if (gtype === 'LineString') return 'segment';

    if (gtype === 'Polygon') return 'area';

    if (gtype === 'Point') return 'point';

    return 'other';

  }



  function matchesSearch(props) {

    if (!searchInput || !searchInput.value.trim()) return true;

    var q = searchInput.value.trim().toLowerCase();

    var hay = [

      props.name,

      props.folder,

      props.description,

      props.activity_code,

      props.activity_name,

    ].filter(Boolean).join(' ').toLowerCase();

    return hay.indexOf(q) >= 0;

  }



  var filterFolder = document.getElementById('mg-filter-folder');

  function passesFilters(props, gtype) {

    if (!matchesSearch(props)) return false;

    if (filterFolder && filterFolder.value && (props.folder || '') !== filterFolder.value) return false;

    if (gtype === 'LineString' && filterLines && !filterLines.checked) return false;

    if (gtype === 'Point' && filterPoints && !filterPoints.checked) return false;

    if (gtype === 'Polygon' && filterPolygons && !filterPolygons.checked) return false;

    if (gtype === 'Point' && (props.diary_id || props.is_diary_gps) && filterGps && !filterGps.checked) {

      return false;

    }

    return true;

  }



  function popupHtml(props, editable) {

    var pct = props.progress_pct || 0;

    var color = progressColor(pct);

    var editBtn = editable

      ? '<button type="button" class="mg-btn mg-btn--xs mg-btn--secondary mg-popup-edit" data-id="' + props.id + '"><i class="fas fa-pen"></i><span>Editar</span></button>'

      : '';

    var eap = props.activity_code

      ? '<div class="meta"><strong>EAP:</strong> ' + escapeHtml(props.activity_code + ' — ' + (props.activity_name || '')) + '</div>'

      : '';

    var gps = '';

    if (props.is_diary_gps || props.diary_id) {

      var diaryLabel = props.diary_report ? ('RDO #' + props.diary_report) : 'RDO';

      if (props.diary_date) diaryLabel += ' · ' + formatDateBr(props.diary_date);

      gps = '<div class="meta mg-popup-gps"><strong>GPS do diário</strong> — ' + escapeHtml(diaryLabel);

      if (props.diary_detail_path) {

        gps += ' <a href="' + escapeHtml(props.diary_detail_path) + '" class="mg-popup-link">Abrir RDO</a>';

      }

      gps += '</div>';

    }

    var lastDiary = '';

    if (props.last_diary_path && props.last_diary_report) {

      lastDiary = '<div class="meta"><strong>Último RDO:</strong> #' + escapeHtml(String(props.last_diary_report));

      if (props.last_diary_date) lastDiary += ' · ' + formatDateBr(props.last_diary_date);

      lastDiary += ' <a href="' + escapeHtml(props.last_diary_path) + '" class="mg-popup-link">Abrir</a></div>';

    }

    var eapLink = '';

    if (props.activity_detail_path && props.activity_code) {

      eapLink = ' <a href="' + escapeHtml(props.activity_detail_path) + '" class="mg-popup-link">Ver EAP</a>';

    }

    var photo = '';

    if (props.diary_photo_url) {

      photo = '<div class="mg-popup-photo"><img src="' + escapeHtml(props.diary_photo_url) + '" alt="Foto do RDO" loading="lazy" /></div>';

    }

    var alerts = '';

    if (props.alert_blocked) alerts += '<span class="mg-popup-badge mg-popup-badge--danger">Bloqueado</span> ';

    if (props.alert_no_eap) alerts += '<span class="mg-popup-badge mg-popup-badge--warn">Sem EAP</span> ';

    if (props.alert_stale) alerts += '<span class="mg-popup-badge mg-popup-badge--muted">Parado</span> ';

    if (props.compare && props.compare.change_type === 'changed') {

      alerts += '<span class="mg-popup-badge mg-popup-badge--info">Δ ' + Number(props.compare.delta_progress).toFixed(1) + '%</span>';

    }

    return (

      '<div class="mg-popup">' +

      '<h4>' + escapeHtml(props.name || 'Sem nome') + '</h4>' +

      (props.folder ? '<div class="meta">' + escapeHtml(props.folder) + '</div>' : '') +

      (alerts ? '<div class="mg-popup-badges">' + alerts + '</div>' : '') +

      eap + eapLink + gps + lastDiary + photo +

      '<div class="meta">' + statusLabel(props.status) + ' · ' + Number(pct).toFixed(1) + '%</div>' +

      (props.description ? '<div class="meta">' + escapeHtml(String(props.description).slice(0, 200)) + '</div>' : '') +

      '<div class="progress-bar-wrap"><div class="progress-bar-fill" style="width:' + pct + '%;background:' + color + '"></div></div>' +

      editBtn +

      '</div>'

    );

  }



  function styleForProps(props) {

    if (props.is_diary_gps || props.diary_id) {

      return {

        radius: 9,

        color: '#1e40af',

        fillColor: '#3b82f6',

        fillOpacity: 0.95,

        weight: 2,

      };

    }

    var pct = props.progress_pct || 0;

    var color = progressColor(pct);

    var compare = props.compare;

    if (compare && compare.change_type) {

      if (compare.change_type === 'added') {

        color = '#16a34a';

      } else if (compare.change_type === 'changed') {

        color = '#ea580c';

      } else if (compare.change_type === 'same') {

        color = '#94a3b8';

      }

    }

    var gtype = props.geometry_type;

    var dash = compare && compare.change_type === 'added' ? '8 6' : null;

    var weightBoost = compare && compare.change_type === 'changed' ? 2 : 0;

    if (gtype === 'LineString') {

      var line = { color: color, weight: 4 + weightBoost, opacity: compare ? 0.95 : 0.85 };

      if (dash) line.dashArray = dash;

      return line;

    }

    if (gtype === 'Polygon') {

      var poly = {

        color: color,

        fillColor: color,

        fillOpacity: compare && compare.change_type === 'same' ? 0.12 : 0.25,

        weight: 2 + weightBoost,

      };

      if (dash) poly.dashArray = dash;

      return poly;

    }

    return {

      radius: compare && compare.change_type === 'changed' ? 9 : 7,

      color: compare && compare.change_type === 'added' ? '#15803d' : '#1e293b',

      fillColor: color,

      fillOpacity: compare && compare.change_type === 'same' ? 0.45 : 0.9,

      weight: 1 + (compare && compare.change_type === 'changed' ? 1 : 0),

    };

  }



  function highlightLayer(id, on) {

    var layer = layerIndex[id];

    if (!layer) return;

    var props = layer.featureProps;

    if (on) {

      if (layer.setStyle) {

        var base = props ? styleForProps(props) : {};

        layer.setStyle(Object.assign({}, base, { weight: (base.weight || 2) + 3, opacity: 1 }));

      }

      if (layer.bringToFront) layer.bringToFront();

    } else if (props && layer.setStyle) {

      layer.setStyle(styleForProps(props));

    }

  }



  function updateListSelection() {

    if (!featureList) return;

    featureList.querySelectorAll('.mapa-geo-list-row').forEach(function (row) {

      var btn = row.querySelector('.mapa-geo-list-item');

      row.classList.toggle('is-selected', btn && btn.dataset.id === String(selectedFeatureId));

    });

  }



  function focusFeatureOnMap(id) {

    var layer = layerIndex[id];

    if (!layer || !map) return;

    selectedFeatureId = id;

    updateListSelection();

    if (layer.getLatLng) {

      map.flyTo(layer.getLatLng(), Math.max(map.getZoom(), 16), { duration: 0.6 });

      layer.openPopup();

    } else if (layer.getBounds) {

      map.flyTo(layer.getBounds().getCenter(), Math.max(map.getZoom(), 14), { duration: 0.6 });

      layer.openPopup();

    }

  }



  function listIconForGtype(gtype, props) {

    if (props && (props.is_diary_gps || props.diary_id)) return 'fa-location-dot';

    if (gtype === 'LineString') return 'fa-route';

    if (gtype === 'Polygon') return 'fa-draw-polygon';

    return 'fa-map-pin';

  }



  function renderFeatureList() {

    if (!featureList) return;

    var items = [];

    (currentGeo && currentGeo.features ? currentGeo.features : []).forEach(function (feat) {

      var props = feat.properties || {};

      var gtype = props.geometry_type || (feat.geometry && feat.geometry.type);

      if (!passesFilters(props, gtype)) return;

      items.push({ props: props, gtype: gtype });

    });

    items.sort(function (a, b) {

      return String(a.props.name || '').localeCompare(String(b.props.name || ''), 'pt-BR');

    });

    if (listCount) listCount.textContent = String(items.length);

    if (!items.length) {

      featureList.innerHTML = '<p class="mapa-geo-side-empty">Nenhum elemento visível.</p>';

      return;

    }

    featureList.innerHTML = items.map(function (item) {

      var p = item.props;

      var pct = Number(p.progress_pct || 0).toFixed(0);

      var kind = kindLabels[p.kind] || listIconForGtype(item.gtype, p);

      var name = p.name || 'Sem nome';

      var meta = [p.folder, pct + '%'].filter(Boolean).join(' · ');

      var diaryPath = p.diary_detail_path || p.last_diary_path || '';

      var eapPath = p.activity_detail_path || '';

      var links = '';

      if (diaryPath) {

        links += '<a href="' + escapeHtml(diaryPath) + '" class="mapa-geo-list-link" title="Abrir RDO" onclick="event.stopPropagation()"><i class="fas fa-book-open"></i></a>';

      }

      if (eapPath) {

        links += '<a href="' + escapeHtml(eapPath) + '" class="mapa-geo-list-link" title="Ver EAP" onclick="event.stopPropagation()"><i class="fas fa-sitemap"></i></a>';

      }

      return (

        '<div class="mapa-geo-list-row' + (String(p.id) === String(selectedFeatureId) ? ' is-selected' : '') + '">' +

        '<button type="button" class="mapa-geo-list-item" data-id="' + p.id + '" data-gtype="' + item.gtype + '">' +

        '<span class="mapa-geo-list-icon"><i class="fas ' + listIconForGtype(item.gtype, p) + '"></i></span>' +

        '<span class="mapa-geo-list-body">' +

        '<span class="mapa-geo-list-kind">' + escapeHtml(kindLabels[p.kind] || item.gtype) + '</span>' +

        '<strong class="mapa-geo-list-name">' + escapeHtml(name) + '</strong>' +

        (meta ? '<span class="mapa-geo-list-meta">' + escapeHtml(meta) + '</span>' : '') +

        '</span></button>' +

        (links ? '<span class="mapa-geo-list-actions">' + links + '</span>' : '') +

        '</div>'

      );

    }).join('');

    featureList.querySelectorAll('.mapa-geo-list-item').forEach(function (btn) {

      btn.addEventListener('mouseenter', function () { highlightLayer(btn.dataset.id, true); });

      btn.addEventListener('mouseleave', function () { highlightLayer(btn.dataset.id, false); });

      btn.addEventListener('click', function () {

        focusFeatureOnMap(btn.dataset.id);

        if (canEdit && editMode) openDrawer(btn.dataset.id);

      });

    });

  }



  function bindLayer(layer, props) {

    layer.featureId = props.id;

    layer.featureProps = props;

    layerIndex[props.id] = layer;

    if (props.diary_id) diaryLayerIndex[props.diary_id] = layer;

    layer.bindPopup(popupHtml(props, canEdit && editMode));

    layer.on('popupopen', function () {

      var btn = document.querySelector('.mg-popup-edit[data-id="' + props.id + '"]');

      if (btn) {

        btn.onclick = function () {

          map.closePopup();

          openDrawer(props.id);

        };

      }

    });

    if (canEdit && editMode) {

      layer.on('click', function (e) {

        if (L.DomEvent) L.DomEvent.stopPropagation(e);

        openDrawer(props.id);

      });

    }

  }



  function initMap() {

    var center = [-14.235, -51.925];

    if (!isNaN(centerLat) && !isNaN(centerLng)) center = [centerLat, centerLng];

    map = L.map('mg-map', { zoomControl: true }).setView(center, defaultZoom);

    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {

      maxZoom: 19,

      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',

    }).addTo(map);

    lineLayer = L.layerGroup().addTo(map);

    polygonLayer = L.layerGroup().addTo(map);

    clusterGroup = L.markerClusterGroup({ maxClusterRadius: 45, showCoverageOnHover: false });

    map.addLayer(clusterGroup);

    editableLayer = new L.FeatureGroup();

    if (canEdit && map.pm) {

      map.pm.setLang('pt_br');

      map.pm.setGlobalOptions({

        snappable: true,

        snapDistance: SNAP_DISTANCE,

        snapMiddle: true,

        tooltips: true,

        allowSelfIntersection: false,

        finishOn: 'dblclick',

      });

    }

  }



  function clearLayers() {

    lineLayer.clearLayers();

    polygonLayer.clearLayers();

    clusterGroup.clearLayers();

    editableLayer.clearLayers();

    layerIndex = {};

    diaryLayerIndex = {};

  }



  function collectBounds(layer, bounds) {

    if (layer.getLatLng) {

      var ll = layer.getLatLng();

      bounds.push([ll.lat, ll.lng]);

    } else if (layer.getBounds) {

      var b = layer.getBounds();

      bounds.push(b.getSouthWest(), b.getNorthEast());

    } else if (layer.getLatLngs) {

      var flat = layer.getLatLngs();

      if (Array.isArray(flat[0])) {

        flat.forEach(function (ring) {

          if (Array.isArray(ring[0])) ring.forEach(function (p) { bounds.push(p); });

          else bounds.push(ring);

        });

      }

    }

  }



  function addFeatureToMap(feat) {

    var props = feat.properties || {};

    var gtype = props.geometry_type || (feat.geometry && feat.geometry.type);

    var coords = feat.geometry && feat.geometry.coordinates;

    if (!coords || !passesFilters(props, gtype)) return null;

    var style = styleForProps(props);

    var layer;

    if (gtype === 'LineString') {

      var latlngs = coords.map(function (c) { return [c[1], c[0]]; });

      layer = L.polyline(latlngs, style);

      if (editMode) editableLayer.addLayer(layer);

      else lineLayer.addLayer(layer);

    } else if (gtype === 'Polygon') {

      var rings = coords.map(function (ring) {

        return ring.map(function (c) { return [c[1], c[0]]; });

      });

      layer = L.polygon(rings, style);

      if (editMode) editableLayer.addLayer(layer);

      else polygonLayer.addLayer(layer);

    } else if (gtype === 'Point') {

      layer = L.circleMarker([coords[1], coords[0]], style);

      if (editMode) editableLayer.addLayer(layer);

      else clusterGroup.addLayer(layer);

    }

    if (layer) bindLayer(layer, props);

    return layer;

  }



  function fitMapToBounds(bounds, options) {

    if (!map || !bounds.length) return;

    map.fitBounds(bounds, Object.assign({ padding: [30, 30], maxZoom: 14 }, options || {}));

  }



  function focusOnTarget() {

    if (focusHandled || !map) return;

    var layer = null;

    if (focusFeature && layerIndex[focusFeature]) {

      layer = layerIndex[focusFeature];

      selectedFeatureId = focusFeature;

    } else if (focusDiary && diaryLayerIndex[focusDiary]) {

      layer = diaryLayerIndex[focusDiary];

    }

    if (!layer) return;

    focusHandled = true;

    if (layer.getLatLng) {

      map.setView(layer.getLatLng(), Math.max(map.getZoom(), 15));

      layer.openPopup();

    } else if (layer.getBounds) {

      map.fitBounds(layer.getBounds(), { padding: [40, 40], maxZoom: 16 });

      layer.openPopup();

    }

    updateListSelection();

  }



  function updateKpis(meta, visibleCount) {

    if (countEl && meta.feature_count != null) countEl.textContent = meta.feature_count;

    if (kpiProgress && meta.overall_progress_pct != null) {

      kpiProgress.textContent = Number(meta.overall_progress_pct).toFixed(1) + '%';

    }

    var featureTotal = meta.feature_count != null ? meta.feature_count : visibleCount;

    if (emptyHint) emptyHint.style.display = featureTotal ? 'none' : '';

    if (exportWrap) exportWrap.hidden = !featureTotal;

    if (toggleEditBtn && !editMode) {

      var emphasize = !featureTotal;

      toggleEditBtn.classList.toggle('mg-btn--primary', emphasize);

      toggleEditBtn.classList.toggle('mg-btn--secondary', !emphasize);

    }

  }



  function renderGeojson(data, options) {

    options = options || {};

    if (!map) return;

    currentGeo = data;

    clearLayers();

    var bounds = [];

    (data.features || []).forEach(function (feat) {

      var layer = addFeatureToMap(feat);

      if (layer) collectBounds(layer, bounds);

    });

    lastBounds = bounds;

    if (bounds.length && options.fit !== false) fitMapToBounds(bounds);

    updateKpis(data.meta || {}, bounds.length);

    applyGeomanToEditableLayers();

    renderFeatureList();

    focusOnTarget();

  }



  function updateTimelineUi() {

    if (!slider) return;

    var max = parseInt(slider.max, 10) || 0;

    var val = parseInt(slider.value, 10) || 0;

    var pct = max > 0 ? (val / max) * 100 : 100;

    if (sliderShell) sliderShell.style.setProperty('--slider-pct', pct + '%');

    if (timelinePrev) timelinePrev.disabled = slider.disabled || val <= 0;

    if (timelineNext) timelineNext.disabled = slider.disabled || val >= max;

    if (timelineDates.length) {

      if (timelineStart) timelineStart.textContent = formatDateBr(timelineDates[0]);

      if (timelineEnd) timelineEnd.textContent = formatDateBr(timelineDates[timelineDates.length - 1]);

      if (dateLabel) dateLabel.textContent = formatDateBr(timelineDates[val] || timelineDates[timelineDates.length - 1]);

    } else {

      if (timelineStart) timelineStart.textContent = '—';

      if (timelineEnd) timelineEnd.textContent = '—';

      if (dateLabel) dateLabel.textContent = 'Hoje';

    }

  }



  function setTimelineIndex(idx) {

    if (!slider || editMode) return;

    var max = parseInt(slider.max, 10) || 0;

    idx = Math.max(0, Math.min(max, idx));

    slider.value = String(idx);

    updateTimelineUi();

    loadFeatures(timelineDates[idx] || null);

  }



  function currentDateParam() {

    if (editMode || !timelineDates.length) return null;

    var idx = slider ? parseInt(slider.value, 10) : timelineDates.length - 1;

    return timelineDates[idx] || null;

  }



  function loadFeatures(dateIso) {

    var url = apiFeatures;

    if (dateIso) url += '?date=' + encodeURIComponent(dateIso);

    return fetch(url, { credentials: 'same-origin', headers: { Accept: 'application/json' } })

      .then(function (r) {

        if (!r.ok) throw new Error('Falha ao carregar mapa');

        return r.json();

      })

      .then(function (data) {

        var meta = data.meta || {};

        if (expectedProjectId && meta.project_id && String(meta.project_id) !== String(expectedProjectId)) {

          showToast('Os elementos carregados não correspondem à obra exibida. Troque de obra.', 'error');

        }

        if (meta.project_code || meta.project_name) {

          var obraTitle = document.getElementById('mg-obra-title');

          if (obraTitle) {

            obraTitle.textContent = (meta.project_code || '') + (meta.project_name ? ' — ' + meta.project_name : '');

          }

        }

        renderGeojson(data, { fit: !editMode && !focusHandled });

        return data;

      });

  }



  function loadTimeline() {

    return fetch(apiTimeline, { credentials: 'same-origin' })

      .then(function (r) { return r.json(); })

      .then(function (data) {

        timelineDates = data.dates || [];

        if (!slider) return loadFeatures(null);

        if (timelineDates.length <= 1) {

          slider.disabled = true;

          slider.max = 0;

          slider.value = 0;

          updateTimelineUi();

          return loadFeatures(timelineDates[0] || null);

        }

        slider.disabled = false;

        slider.min = 0;

        slider.max = timelineDates.length - 1;

        slider.value = timelineDates.length - 1;

        updateTimelineUi();

        return loadFeatures(timelineDates[slider.value]);

      });

  }



  function applyGeomanToEditableLayers() {

    if (!editMode || !map || !editableLayer || !map.pm) return;

    if (!map.hasLayer(editableLayer)) map.addLayer(editableLayer);

    editableLayer.eachLayer(function (layer) {

      if (layer.pm && !layer.pm.enabled()) {

        layer.pm.enable({ allowRemoval: false });

      }

    });

  }



  function updateDrawToolUi() {

    if (!drawTools) return;

    drawTools.querySelectorAll('.mapa-geo-tool-btn').forEach(function (btn) {

      btn.classList.toggle('is-active', btn.dataset.tool === currentTool);

    });

  }



  function setActiveTool(tool) {

    if (!canEdit || !map || !map.pm) return;

    currentTool = tool;

    updateDrawToolUi();

    map.pm.disableDraw();

    map.pm.disableGlobalEditMode();

    map.pm.disableGlobalRemovalMode();

    var snapOpts = { snappable: true, snapDistance: SNAP_DISTANCE, tooltips: true };

    if (tool === 'line') {

      lastDrawTool = 'line';

      map.pm.enableDraw('Line', snapOpts);

    } else if (tool === 'marker') {

      lastDrawTool = 'marker';

      map.pm.enableDraw('Marker', snapOpts);

    } else if (tool === 'polygon') {

      lastDrawTool = 'polygon';

      map.pm.enableDraw('Polygon', snapOpts);

    } else if (tool === 'edit') {

      applyGeomanToEditableLayers();

      map.pm.enableGlobalEditMode({ snappable: true, snapDistance: SNAP_DISTANCE });

    } else if (tool === 'delete') {

      map.pm.enableGlobalRemovalMode();

    }

  }



  function setupGeoman() {

    if (!canEdit || !map || !map.pm) return;

    if (!editMode) {

      map.pm.disableDraw();

      map.pm.disableGlobalEditMode();

      map.pm.disableGlobalRemovalMode();

      if (editableLayer && map.hasLayer(editableLayer)) map.removeLayer(editableLayer);

      if (drawTools) drawTools.hidden = true;

      return;

    }

    if (drawTools) drawTools.hidden = false;

    applyGeomanToEditableLayers();

    setActiveTool(currentTool || 'pan');

  }



  function setEditMode(on) {

    editMode = !!on;

    if (toggleEditBtn) {

      toggleEditBtn.classList.toggle('mg-btn--primary', editMode);

      toggleEditBtn.classList.toggle('mg-btn--secondary', !editMode);

      toggleEditBtn.classList.toggle('is-active', editMode);

      toggleEditBtn.innerHTML = editMode

        ? '<i class="fas fa-eye"></i><span>Modo visualização</span>'

        : '<i class="fas fa-pen"></i><span>Editar mapa</span>';

    }

    if (workspace) workspace.classList.toggle('is-editing', editMode);

    if (timelineWrap) timelineWrap.style.opacity = editMode ? '0.45' : '1';

    if (slider) slider.disabled = editMode || timelineDates.length <= 1;

    updateTimelineUi();

    if (!editMode) {

      closeDrawer(true);

      currentTool = 'pan';

    } else {

      currentTool = 'pan';

      if (saveAndNextBtn) saveAndNextBtn.hidden = false;

    }

    setupGeoman();

    loadFeatures(editMode ? null : currentDateParam());

  }



  function apiRequest(url, method, body) {

    var headers = { Accept: 'application/json', 'X-CSRFToken': getCsrf() };

    if (body) headers['Content-Type'] = 'application/json';

    return fetch(url, {

      method: method,

      credentials: 'same-origin',

      headers: headers,

      body: body ? JSON.stringify(body) : undefined,

    }).then(function (r) {

      return r.json().then(function (data) {

        if (!r.ok) throw new Error(data.error || 'Erro na operação');

        return data;

      });

    });

  }



  var activitiesCache = null;



  function renderActivityOptions(selectedId, filterText) {

    var sel = document.getElementById('mg-f-activity');

    if (!sel) return;

    var q = (filterText || '').trim().toLowerCase();

    sel.innerHTML = '<option value="">— Sem vínculo (progresso manual) —</option>';

    (activitiesCache || []).forEach(function (a) {

      if (q && a.label.toLowerCase().indexOf(q) < 0) return;

      var opt = document.createElement('option');

      opt.value = a.id;

      opt.textContent = a.label + ' (' + Number(a.progress_pct).toFixed(1) + '%)';

      sel.appendChild(opt);

    });

    if (selectedId) sel.value = String(selectedId);

    updateActivityHint();

  }



  function loadActivitiesSelect(selectedId) {

    if (!apiActivities) return Promise.resolve();

    return fetch(apiActivities + '?leaves=1', { credentials: 'same-origin' })

      .then(function (r) { return r.json(); })

      .then(function (data) {

        activitiesCache = data.activities || [];

        var searchEl = document.getElementById('mg-f-activity-search');

        renderActivityOptions(selectedId, searchEl ? searchEl.value : '');

      });

  }



  function updateActivityHint() {

    var sel = document.getElementById('mg-f-activity');

    var hint = document.getElementById('mg-activity-hint');

    var prog = document.getElementById('mg-f-progress');

    if (!sel || !hint) return;

    var id = sel.value;

    if (!id) {

      hint.textContent = 'Sem EAP: use progresso manual ou deixe proporcional ao avanço da obra.';

      if (prog) prog.disabled = false;

      return;

    }

    var act = (activitiesCache || []).find(function (a) { return String(a.id) === String(id); });

    if (act) {

      hint.textContent = 'Progresso sincronizado com a EAP do Lplan (' + Number(act.progress_pct).toFixed(1) + '%).';

      if (prog) {

        prog.value = act.progress_pct;

        prog.disabled = true;

      }

    }

  }



  function openDrawer(featureId, layer) {

    if (!drawer) return;

    pendingLayer = layer || null;

    drawerOpen = true;

    var props = layer && layer.featureProps ? layer.featureProps : null;



    function fillForm(p) {

      var defaultKind = p.kind || (layer ? defaultKindForGeometry(layer) : 'other');

      document.getElementById('mg-f-id').value = p.id || '';

      document.getElementById('mg-f-name').value = p.name || '';

      document.getElementById('mg-f-folder').value = p.folder || '';

      document.getElementById('mg-f-description').value = p.description || '';

      document.getElementById('mg-f-kind').value = defaultKind;

      document.getElementById('mg-f-status').value = p.status || 'planned';

      document.getElementById('mg-f-progress').value = p.progress_pct != null ? p.progress_pct : 0;

      document.getElementById('mg-drawer-title').textContent = p.id ? 'Editar elemento' : 'Novo elemento';

      document.getElementById('mg-f-delete').style.display = p.id ? '' : 'none';

      if (saveAndNextBtn) saveAndNextBtn.hidden = !!p.id;

      var searchEl = document.getElementById('mg-f-activity-search');

      if (searchEl) searchEl.value = '';

      loadActivitiesSelect(p.activity_id || '').then(function () {

        drawer.classList.add('is-open');

        drawer.setAttribute('aria-hidden', 'false');

        if (drawerBackdrop) {

          drawerBackdrop.hidden = false;

          requestAnimationFrame(function () { drawerBackdrop.classList.add('is-visible'); });

        }

      });

    }



    if (props) {

      fillForm(props);

      return;

    }

    if (featureId) {

      fetch(apiDetailUrl(featureId), { credentials: 'same-origin' })

        .then(function (r) { return r.json(); })

        .then(function (feat) { fillForm(feat.properties || {}); });

      return;

    }

    fillForm({

      name: '',

      folder: '',

      description: '',

      kind: defaultKindForGeometry(layer),

      status: 'planned',

      progress_pct: 0,

    });

  }



  function closeDrawer(skipLayerCleanup) {

    if (!drawer) return;

    if (!skipLayerCleanup && pendingLayer && !pendingLayer.featureId && editableLayer) {

      editableLayer.removeLayer(pendingLayer);

    }

    drawer.classList.remove('is-open');

    drawer.setAttribute('aria-hidden', 'true');

    if (drawerBackdrop) {

      drawerBackdrop.classList.remove('is-visible');

      drawerBackdrop.hidden = true;

    }

    drawerOpen = false;

    pendingLayer = null;

  }



  function saveFeatureFromForm(e, andDrawNext) {

    if (e) e.preventDefault();

    var id = document.getElementById('mg-f-id').value;

    var activitySel = document.getElementById('mg-f-activity');

    var payload = {

      name: document.getElementById('mg-f-name').value,

      folder: document.getElementById('mg-f-folder').value,

      description: document.getElementById('mg-f-description').value,

      kind: document.getElementById('mg-f-kind').value,

      status: document.getElementById('mg-f-status').value,

      progress_pct: parseFloat(document.getElementById('mg-f-progress').value) || 0,

      activity_id: activitySel && activitySel.value ? activitySel.value : null,

    };

    if (pendingLayer) payload.geometry = layerToGeoJSON(pendingLayer);

    var promise = id

      ? apiRequest(apiDetailUrl(id), 'PATCH', payload)

      : (payload.geometry

        ? apiRequest(apiFeatures, 'POST', payload)

        : Promise.reject(new Error('Geometria não encontrada.')));

    promise

      .then(function () {

        var wasNew = !id;

        closeDrawer(true);

        showToast(wasNew ? 'Elemento criado no mapa.' : 'Elemento atualizado.', 'success');

        return loadFeatures(editMode ? null : currentDateParam());

      })

      .then(function () {

        setupGeoman();

        if (andDrawNext) setActiveTool(lastDrawTool);

      })

      .catch(function (err) { showToast(err.message, 'error'); });

  }



  function deleteFeature() {

    var id = document.getElementById('mg-f-id').value;

    if (!id || !confirm('Excluir este elemento do mapa?')) return;

    apiRequest(apiDetailUrl(id), 'DELETE')

      .then(function () {

        closeDrawer(true);

        showToast('Elemento removido do mapa.', 'success');

        return loadFeatures(editMode ? null : currentDateParam());

      })

      .then(setupGeoman)

      .catch(function (err) { showToast(err.message, 'error'); });

  }



  function syncFromDiario() {

    if (!apiSync) return;

    if (syncBtn) {

      syncBtn.disabled = true;

      syncBtn.textContent = 'Sincronizando…';

    }

    apiRequest(apiSync, 'POST')

      .then(function (data) {

        if (data.summary) {

          if (kpiProgress) kpiProgress.textContent = Number(data.summary.overall_progress_pct).toFixed(1) + '%';

          var gpsEl = document.getElementById('mg-kpi-gps');

          if (gpsEl) gpsEl.textContent = data.summary.gps_markers;

        }

        return loadTimeline();

      })

      .then(function () {

        showToast('Progresso atualizado com base nos diários da obra.', 'success');

      })

      .catch(function (err) { showToast(err.message, 'error'); })

      .finally(function () {

        if (syncBtn) {

          syncBtn.disabled = false;

          syncBtn.textContent = 'Atualizar progresso dos diários';

        }

      });

  }



  function onGeomanCreate(e) {

    var layer = e.layer;

    editableLayer.addLayer(layer);

    pendingLayer = layer;

    openDrawer(null, layer);

  }



  function onGeomanUpdate(e) {

    var layer = e.layer;

    if (!layer.featureId) return;

    apiRequest(apiDetailUrl(layer.featureId), 'PATCH', {

      geometry: layerToGeoJSON(layer),

    })

      .then(function () { showToast('Geometria atualizada.', 'success'); })

      .catch(function (err) { showToast(err.message, 'error'); });

  }



  function onGeomanRemove(e) {

    var layer = e.layer;

    if (!layer.featureId) {

      if (editableLayer) editableLayer.removeLayer(layer);

      return;

    }

    apiRequest(apiDetailUrl(layer.featureId), 'DELETE')

      .then(function () {

        showToast('Elemento removido.', 'success');

        return loadFeatures(editMode ? null : currentDateParam());

      })

      .then(setupGeoman)

      .catch(function (err) { showToast(err.message, 'error'); });

  }



  function toggleSidePanel() {

    panelOpen = !panelOpen;

    if (workspace) workspace.classList.toggle('panel-collapsed', !panelOpen);

    if (togglePanelBtn) {

      togglePanelBtn.setAttribute('aria-expanded', panelOpen ? 'true' : 'false');

      togglePanelBtn.dataset.tooltip = panelOpen ? 'Recolher lista' : 'Expandir lista';

    }

    if (panelReopenBtn) panelReopenBtn.hidden = panelOpen;

  }



  function bindUi() {

    if (slider) {

      slider.addEventListener('input', function () {

        if (editMode) return;

        updateTimelineUi();

        loadFeatures(timelineDates[parseInt(slider.value, 10)]);

      });

    }

    if (timelinePrev) {

      timelinePrev.addEventListener('click', function () {

        setTimelineIndex(parseInt(slider.value, 10) - 1);

      });

    }

    if (timelineNext) {

      timelineNext.addEventListener('click', function () {

        setTimelineIndex(parseInt(slider.value, 10) + 1);

      });

    }

    [filterLines, filterPoints, filterPolygons, filterGps].forEach(function (el) {

      if (!el) return;

      el.addEventListener('change', function () {

        if (currentGeo) renderGeojson(currentGeo, { fit: false });

      });

    });

    if (searchInput) {

      searchInput.addEventListener('input', function () {

        if (currentGeo) renderGeojson(currentGeo, { fit: false });

      });

    }

    if (fitBoundsBtn) {

      fitBoundsBtn.addEventListener('click', function () {

        fitMapToBounds(lastBounds);

      });

    }

    if (togglePanelBtn) togglePanelBtn.addEventListener('click', toggleSidePanel);

    if (panelReopenBtn) panelReopenBtn.addEventListener('click', toggleSidePanel);

    if (filtersToggle && filtersBody) {

      filtersToggle.addEventListener('click', function () {

        var willOpen = filtersBody.hidden;

        filtersBody.hidden = !willOpen;

        filtersToggle.classList.toggle('is-open', willOpen);

        filtersToggle.setAttribute('aria-expanded', willOpen ? 'true' : 'false');

      });

    }

    function setHelpOpen(open) {

      if (!helpOverlay) return;

      helpOverlay.hidden = !open;

    }

    if (helpToggle) {

      helpToggle.addEventListener('click', function () { setHelpOpen(helpOverlay.hidden); });

    }

    if (helpClose) helpClose.addEventListener('click', function () { setHelpOpen(false); });

    if (helpOverlay) {

      helpOverlay.addEventListener('click', function (e) {

        if (e.target === helpOverlay) setHelpOpen(false);

      });

    }

    document.addEventListener('keydown', function (e) {

      if (e.key === '?' && !e.ctrlKey && !e.metaKey && !e.altKey) {

        var tagHelp = (e.target && e.target.tagName) || '';

        if (tagHelp === 'INPUT' || tagHelp === 'TEXTAREA' || tagHelp === 'SELECT') return;

        e.preventDefault();

        if (helpOverlay) setHelpOpen(helpOverlay.hidden);

        return;

      }

      if (e.key === 'Escape' && helpOverlay && !helpOverlay.hidden) {

        setHelpOpen(false);

      }

    });

    if (toggleEditBtn) toggleEditBtn.addEventListener('click', function () { setEditMode(!editMode); });

    if (syncBtn) syncBtn.addEventListener('click', syncFromDiario);



    if (drawTools) {

      drawTools.querySelectorAll('.mapa-geo-tool-btn').forEach(function (btn) {

        btn.addEventListener('click', function () {

          setActiveTool(btn.dataset.tool);

        });

      });

    }



    var dropdownMenus = [exportMenu, moreMenu].filter(Boolean);

    function closeAllDropdowns() {
      dropdownMenus.forEach(function (menu) { menu.hidden = true; });
      [exportToggle, moreToggle].forEach(function (btn) {
        if (btn) btn.classList.remove('is-open');
      });
    }

    function bindDropdownMenu(toggle, menu) {
      if (!toggle || !menu) return;
      toggle.addEventListener('click', function (e) {
        e.stopPropagation();
        var willOpen = menu.hidden;
        closeAllDropdowns();
        menu.hidden = !willOpen;
        toggle.classList.toggle('is-open', willOpen);
      });
      menu.addEventListener('click', function (e) {
        if (e.target.closest('a, button')) closeAllDropdowns();
      });
    }

    document.addEventListener('click', function (e) {
      if (!e.target.closest('.mapa-geo-export-wrap, .mapa-geo-more-wrap')) {
        closeAllDropdowns();
      }
    });

    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape') closeAllDropdowns();
    });

    bindDropdownMenu(exportToggle, exportMenu);
    bindDropdownMenu(moreToggle, moreMenu);



    if (featureForm) {

      featureForm.addEventListener('submit', function (e) { saveFeatureFromForm(e, false); });

      document.getElementById('mg-drawer-cancel').addEventListener('click', function () { closeDrawer(false); });

      document.getElementById('mg-drawer-close').addEventListener('click', function () { closeDrawer(false); });

      document.getElementById('mg-f-delete').addEventListener('click', deleteFeature);

      if (saveAndNextBtn) {

        saveAndNextBtn.addEventListener('click', function (e) { saveFeatureFromForm(e, true); });

      }

      var actSel = document.getElementById('mg-f-activity');

      if (actSel) actSel.addEventListener('change', updateActivityHint);

      var actSearch = document.getElementById('mg-f-activity-search');

      if (actSearch) {

        actSearch.addEventListener('input', function () {

          renderActivityOptions(actSel ? actSel.value : '', actSearch.value);

        });

      }

    }

    if (drawerBackdrop) {

      drawerBackdrop.addEventListener('click', function () { closeDrawer(false); });

    }



    if (canEdit && map && map.pm) {

      map.on('pm:create', onGeomanCreate);

      map.on('pm:update', onGeomanUpdate);

      map.on('pm:remove', onGeomanRemove);

    }



    document.addEventListener('keydown', function (e) {

      if (!editMode) return;

      var tag = (e.target && e.target.tagName) || '';

      if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return;

      if (e.key === 'Escape') {

        if (drawerOpen) closeDrawer(false);

        else setActiveTool('pan');

      }

      if (e.key === 'l' || e.key === 'L') setActiveTool('line');

      if (e.key === 'p' || e.key === 'P') setActiveTool('marker');

      if (e.key === 'a' || e.key === 'A') setActiveTool('polygon');

      if (e.key === 'e' || e.key === 'E') setActiveTool('edit');

      if (e.key === 'Delete') setActiveTool('delete');

    });

  }



  document.addEventListener('DOMContentLoaded', function () {

    initMap();

    bindUi();

    loadTimeline().catch(function (err) {

      console.error('[mapa_geo]', err);

      showToast('Não foi possível carregar o mapa.', 'error');

    });

  });

  window.MapaGeo = {

    getMap: function () { return map; },

    getTimelineDates: function () { return timelineDates.slice(); },

    getCurrentDate: currentDateParam,

    loadFeatures: loadFeatures,

    renderGeojson: renderGeojson,

    showToast: showToast,

    setEditMode: setEditMode,

    passesFilters: passesFilters,

    styleForProps: styleForProps,

    popupHtml: popupHtml,

    bindLayer: bindLayer,

    addFeatureToMap: addFeatureToMap,

  };

})();

