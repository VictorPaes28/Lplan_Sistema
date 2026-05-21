/**
 * TrackHub Fila — filtros dropdown th-cf-* (adaptado do calendário).
 * Navega via URLSearchParams, preservando o parâmetro q e demais filtros.
 */
(function () {
  'use strict';

  /* ── Dados de responsáveis ────────────────────────────────────── */
  var responsaveisData = [];
  var respDataEl = document.getElementById('th-fila-resp-data');
  if (respDataEl && respDataEl.textContent) {
    try { responsaveisData = JSON.parse(respDataEl.textContent); } catch (e) {}
  }

  var respListPopulated = false;
  var activeWrap = null;

  /* ── Helpers ─────────────────────────────────────────────────── */
  function avatarColor(name) {
    var colors = ['#3498db', '#2980b9', '#5dade2', '#577590', '#7f8c8d', '#34495e'];
    var hash = 0;
    for (var i = 0; i < (name || '').length; i++) hash = (name || '').charCodeAt(i) + ((hash << 5) - hash);
    return colors[Math.abs(hash) % colors.length];
  }

  function calcIniciais(nome) {
    var parts = (nome || '').trim().split(/\s+/).filter(Boolean);
    if (!parts.length) return '?';
    if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
    return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
  }

  function buildNavigationUrl(filterName, filterValue) {
    var params = new URLSearchParams(window.location.search);
    params.delete('page');
    // Atualiza cada filtro a partir do data-current atual dos wraps
    document.querySelectorAll('#th-fila-cf-filters .th-cf-wrap').forEach(function (w) {
      var name = w.getAttribute('data-filter') || '';
      if (!name || name === filterName) return;
      var val = w.getAttribute('data-current') || '';
      if (val) params.set(name, val); else params.delete(name);
    });
    if (filterValue) params.set(filterName, filterValue);
    else params.delete(filterName);
    return '?' + params.toString();
  }

  /* ── Open / close ─────────────────────────────────────────────── */
  function closeAllFilters() {
    document.querySelectorAll('#th-fila-cf-filters .th-cf-wrap').forEach(function (w) {
      var fp = w.querySelector('.th-cf-panel');
      if (fp) fp.hidden = true;
      var fb = w.querySelector('.th-cf-btn');
      if (fb) fb.setAttribute('aria-expanded', 'false');
    });
    activeWrap = null;
  }

  function openFilter(wrap) {
    var wasActive = activeWrap === wrap;
    closeAllFilters();
    if (wasActive) return;

    var filterPanel = wrap.querySelector('.th-cf-panel');
    var filterBtn   = wrap.querySelector('.th-cf-btn');
    if (!filterPanel) return;

    if (wrap.getAttribute('data-filter') === 'responsavel' && !respListPopulated) {
      populateRespList();
    }

    filterPanel.hidden = false;
    if (filterBtn) filterBtn.setAttribute('aria-expanded', 'true');
    activeWrap = wrap;

    var searchEl = filterPanel.querySelector('.th-cf-search');
    if (searchEl) {
      searchEl.value = '';
      filterList(wrap);
      setTimeout(function () { searchEl.focus(); }, 0);
    }
  }

  function filterList(wrap) {
    var searchEl = wrap.querySelector('.th-cf-search');
    var q = searchEl ? searchEl.value.trim().toLowerCase() : '';
    wrap.querySelectorAll('.th-cf-item').forEach(function (li) {
      li.style.display = (!q || (li.textContent || '').toLowerCase().indexOf(q) !== -1) ? '' : 'none';
    });
  }

  /* ── Responsável lazy-list ────────────────────────────────────── */
  function populateRespList() {
    var ul = document.getElementById('th-fila-resp-list');
    if (!ul) return;
    var wrap = ul.closest('.th-cf-wrap');
    var current = wrap ? (wrap.getAttribute('data-current') || '') : '';
    ul.innerHTML = '';

    var allLi = document.createElement('li');
    allLi.className = 'th-cf-item' + (!current ? ' th-cf-item--selected' : '');
    allLi.setAttribute('data-value', '');
    allLi.setAttribute('role', 'option');
    allLi.textContent = 'Todos os responsáveis';
    ul.appendChild(allLi);

    responsaveisData.forEach(function (u) {
      var li = document.createElement('li');
      li.className = 'th-cf-item' + (String(u.id) === current ? ' th-cf-item--selected' : '');
      li.setAttribute('data-value', String(u.id));
      li.setAttribute('role', 'option');

      var av = document.createElement('span');
      av.className = 'th-cf-avatar';
      av.textContent = u.iniciais || calcIniciais(u.nome);
      av.style.background = avatarColor(u.nome);
      li.appendChild(av);

      var nm = document.createElement('span');
      nm.textContent = u.nome || '';
      li.appendChild(nm);

      ul.appendChild(li);
    });
    respListPopulated = true;
  }

  // Colorir avatar no trigger quando filtro responsável já está ativo
  document.querySelectorAll('#th-fila-cf-filters .th-cf-btn .th-cf-avatar[data-nome]').forEach(function (av) {
    var nome = av.getAttribute('data-nome') || '';
    if (nome) av.style.background = avatarColor(nome);
  });

  /* ── Event listeners ──────────────────────────────────────────── */
  document.addEventListener('click', function (e) {
    var cfBtn = e.target.closest && e.target.closest('#th-fila-cf-filters .th-cf-btn');
    if (cfBtn) {
      var wrap = cfBtn.closest('.th-cf-wrap');
      if (wrap) openFilter(wrap);
      return;
    }

    var cfItem = e.target.closest && e.target.closest('#th-fila-cf-filters .th-cf-item');
    if (cfItem) {
      var itemWrap = cfItem.closest('.th-cf-wrap');
      if (itemWrap) {
        var val        = cfItem.getAttribute('data-value') || '';
        var filterName = itemWrap.getAttribute('data-filter') || '';
        itemWrap.setAttribute('data-current', val);
        closeAllFilters();
        window.location.href = buildNavigationUrl(filterName, val);
      }
      return;
    }

    if (activeWrap && !(e.target.closest && e.target.closest('#th-fila-cf-filters .th-cf-wrap'))) {
      closeAllFilters();
    }
  });

  document.addEventListener('input', function (e) {
    if (e.target && e.target.classList && e.target.classList.contains('th-cf-search')) {
      var wrap = e.target.closest('#th-fila-cf-filters .th-cf-wrap');
      if (wrap) filterList(wrap);
    }
  });

  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape' && activeWrap) closeAllFilters();
  });

  window.addEventListener('resize', function () { closeAllFilters(); });

})();
