/**
 * Calendário TrackHub — popover "Mais N" + filtros dropdown (single e multi-select).
 */
(function () {
  'use strict';

  /* ── Popover "Mais N" ─────────────────────────────────────────── */
  var root      = document.getElementById('th-cal-day-popover');
  var panel     = root && root.querySelector('.th-cal-day-popover-panel');
  var elWeekday = document.getElementById('th-cal-day-popover-weekday');
  var elDayNum  = document.getElementById('th-cal-day-popover-num');
  var elList    = document.getElementById('th-cal-day-popover-list');
  var btnClose  = root && root.querySelector('.th-cal-day-popover-close');
  var dataEl    = document.getElementById('th-cal-day-data');
  var urlPattern = (dataEl && dataEl.dataset.urlPattern) || '';

  var dayData = {};
  if (dataEl && dataEl.textContent) {
    try { dayData = JSON.parse(dataEl.textContent); } catch (e) { dayData = {}; }
  }

  function pendenciaUrl(id) { return urlPattern.replace('{id}', String(id)); }

  function closePopover() {
    if (!root) return;
    root.hidden = true;
    root.setAttribute('aria-hidden', 'true');
  }

  function positionPanel(anchor) {
    if (!panel || !anchor) return;
    var rect = anchor.getBoundingClientRect();
    var pw = panel.offsetWidth || 220;
    var ph = panel.offsetHeight || 200;
    var left = rect.left + rect.width / 2 - pw / 2;
    var top  = rect.bottom + 6;
    if (left + pw > window.innerWidth - 8) left = window.innerWidth - pw - 8;
    if (left < 8) left = 8;
    if (top + ph > window.innerHeight - 8) top = rect.top - ph - 6;
    if (top < 8) top = 8;
    panel.style.left = left + 'px';
    panel.style.top  = top + 'px';
  }

  function renderList(items) {
    if (!elList) return;
    elList.innerHTML = '';
    if (!items || !items.length) {
      elList.innerHTML = '<p class="th-cal-day-popover-empty">Nenhuma pendência.</p>';
      return;
    }
    items.forEach(function (item) {
      var a = document.createElement('a');
      a.href = pendenciaUrl(item.id);
      a.className = 'th-cal-pop-item ' + (item.prioridade || 'normal');
      if (item.status === 'concluida')      a.classList.add('th-cal-pop-item--concluida');
      else if (item.status === 'cancelada') a.classList.add('th-cal-pop-item--cancelada');
      a.title = item.titulo || '';
      if (item.continues_before) a.classList.add('th-cal-pop-item--cont-left');
      if (item.continues_after)  a.classList.add('th-cal-pop-item--cont-right');

      if (item.status === 'concluida') {
        var ico = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
        ico.setAttribute('viewBox', '0 0 24 24');
        ico.setAttribute('class', 'th-cal-pop-item-icon');
        ico.innerHTML = '<polyline points="20 6 9 17 4 12" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/>';
        a.appendChild(ico);
      } else if (item.status === 'cancelada') {
        var icoX = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
        icoX.setAttribute('viewBox', '0 0 24 24');
        icoX.setAttribute('class', 'th-cal-pop-item-icon');
        icoX.innerHTML = '<line x1="18" y1="6" x2="6" y2="18" fill="none" stroke="currentColor" stroke-width="2.5"/><line x1="6" y1="6" x2="18" y2="18" fill="none" stroke="currentColor" stroke-width="2.5"/>';
        a.appendChild(icoX);
      }

      var span = document.createElement('span');
      span.className = 'th-cal-pop-item-text';
      span.textContent = item.titulo || '—';
      a.appendChild(span);
      elList.appendChild(a);
    });
  }

  function openPopover(iso, anchor) {
    if (!root) return;
    var pack = dayData[iso];
    if (!pack) return;
    if (elWeekday) elWeekday.textContent = pack.weekday || '';
    if (elDayNum)  elDayNum.textContent  = String(pack.day != null ? pack.day : '');
    renderList(pack.pendencias || []);
    root.hidden = false;
    root.setAttribute('aria-hidden', 'false');
    positionPanel(anchor);
    requestAnimationFrame(function () { positionPanel(anchor); });
  }

  /* ── Filtros dropdown ─────────────────────────────────────────── */
  var responsaveisData = [];
  var respDataEl = document.getElementById('th-cal-resp-data');
  if (respDataEl && respDataEl.textContent) {
    try { responsaveisData = JSON.parse(respDataEl.textContent); } catch (e) {}
  }

  var respListPopulated = false;
  var activeWrap = null;
  var multiInitial = {};

  /* helpers */
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
    var container = document.querySelector('.th-cal-filters');
    var params = new URLSearchParams();
    if (container) {
      if (container.dataset.year)  params.set('year',  container.dataset.year);
      if (container.dataset.month) params.set('month', container.dataset.month);
    }
    document.querySelectorAll('.th-cf-wrap').forEach(function (w) {
      var name = w.getAttribute('data-filter') || '';
      var val  = (name === filterName) ? filterValue : (w.getAttribute('data-current') || '');
      if (val) params.set(name, val);
    });
    return '?' + params.toString();
  }

  /* ── Multi-select helpers ─────────────────────────────────────── */
  var PRIO_LABELS = { urgente: 'Urgente', alta: 'Alta', normal: 'Normal', baixa: 'Baixa' };
  var PRIO_ORDER  = ['urgente', 'alta', 'normal', 'baixa'];

  function getCheckedVals(wrap) {
    var checked = [];
    wrap.querySelectorAll('.th-cf-item--checked[data-value]').forEach(function (li) {
      var v = li.getAttribute('data-value');
      if (v) checked.push(v);
    });
    return checked;
  }

  function updateMultiLabel(wrap) {
    var label = wrap.querySelector('.th-cf-label');
    var btn   = wrap.querySelector('.th-cf-btn');
    if (!label) return;
    var total   = wrap.querySelectorAll('.th-cf-item[data-value]:not([data-value=""])').length;
    var checked = getCheckedVals(wrap);
    if (!checked.length || checked.length >= total) {
      label.textContent = 'Prioridade';
      if (btn) btn.classList.remove('th-cf-btn--active');
    } else {
      var names = PRIO_ORDER.filter(function (v) { return checked.indexOf(v) !== -1; })
                            .map(function (v) { return PRIO_LABELS[v] || v; });
      label.textContent = names.join(', ');
      if (btn) btn.classList.add('th-cf-btn--active');
    }
  }

  function finalizeMulti(wrap) {
    var filterName = wrap.getAttribute('data-filter');
    var total      = wrap.querySelectorAll('.th-cf-item[data-value]:not([data-value=""])').length;
    var checked    = getCheckedVals(wrap);
    var newVal     = (checked.length && checked.length < total) ? checked.join(',') : '';
    var initial    = multiInitial[filterName] !== undefined ? multiInitial[filterName] : '';
    wrap.setAttribute('data-current', newVal);
    updateMultiLabel(wrap);
    return { newVal: newVal, initial: initial, filterName: filterName };
  }

  /* ── Open / close ─────────────────────────────────────────────── */
  function closeAllFilters(skipNavigate) {
    var nav = null;
    if (activeWrap && activeWrap.getAttribute('data-multi') === 'true') {
      var result = finalizeMulti(activeWrap);
      if (!skipNavigate && result.newVal !== result.initial) {
        nav = { name: result.filterName, val: result.newVal };
      }
    }
    document.querySelectorAll('.th-cf-wrap').forEach(function (w) {
      var fp = w.querySelector('.th-cf-panel');
      if (fp) fp.hidden = true;
      var fb = w.querySelector('.th-cf-btn');
      if (fb) fb.setAttribute('aria-expanded', 'false');
    });
    activeWrap = null;
    if (nav) window.location.href = buildNavigationUrl(nav.name, nav.val);
  }

  function openFilter(wrap) {
    var wasActive = activeWrap === wrap;
    closeAllFilters(true); // close without navigating; we decide below
    if (wasActive) {
      // Button was clicked again: toggle closed. For multi, apply now.
      var fName = wrap.getAttribute('data-filter');
      if (wrap.getAttribute('data-multi') === 'true') {
        var result = finalizeMulti(wrap);
        if (result.newVal !== result.initial) {
          window.location.href = buildNavigationUrl(result.filterName, result.newVal);
        }
      }
      return;
    }

    var filterPanel = wrap.querySelector('.th-cf-panel');
    var filterBtn   = wrap.querySelector('.th-cf-btn');
    if (!filterPanel) return;

    // Responsável: lazy-populate
    if (wrap.getAttribute('data-filter') === 'responsavel' && !respListPopulated) {
      populateRespList();
    }

    // Multi: mark initial checked state
    if (wrap.getAttribute('data-multi') === 'true') {
      var fname  = wrap.getAttribute('data-filter');
      var current = wrap.getAttribute('data-current') || '';
      multiInitial[fname] = current;
      var vals = current ? current.split(',').map(function (v) { return v.trim(); }).filter(Boolean) : [];
      wrap.querySelectorAll('.th-cf-item[data-value]:not([data-value=""])').forEach(function (li) {
        li.classList.toggle('th-cf-item--checked', vals.indexOf(li.getAttribute('data-value')) !== -1);
      });
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
    var ul = document.getElementById('th-cf-resp-list');
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
  document.querySelectorAll('.th-cf-btn .th-cf-avatar[data-nome]').forEach(function (av) {
    var nome = av.getAttribute('data-nome') || '';
    if (nome) av.style.background = avatarColor(nome);
  });

  /* ── Event listeners ──────────────────────────────────────────── */
  document.addEventListener('click', function (e) {
    // Filtro — botão trigger
    var cfBtn = e.target.closest && e.target.closest('.th-cf-btn');
    if (cfBtn) {
      var wrap = cfBtn.closest('.th-cf-wrap');
      if (wrap) openFilter(wrap);
      return;
    }

    // Filtro — item selecionado
    var cfItem = e.target.closest && e.target.closest('.th-cf-item');
    if (cfItem) {
      var itemWrap = cfItem.closest('.th-cf-wrap');
      if (itemWrap) {
        if (itemWrap.getAttribute('data-multi') === 'true') {
          // Multiselect: toggle e atualiza label (sem navegar ainda)
          cfItem.classList.toggle('th-cf-item--checked');
          updateMultiLabel(itemWrap);
        } else {
          // Single: navega imediatamente
          var val        = cfItem.getAttribute('data-value') || '';
          var filterName = itemWrap.getAttribute('data-filter') || '';
          closeAllFilters(true);
          window.location.href = buildNavigationUrl(filterName, val);
        }
      }
      return;
    }

    // Clique fora: fecha (e para multi, aplica + navega se mudou)
    if (activeWrap && !(e.target.closest && e.target.closest('.th-cf-wrap'))) {
      closeAllFilters();
    }

    // Popover "Mais N"
    var moreBtn = e.target.closest && e.target.closest('.th-cal-more');
    if (moreBtn) {
      e.preventDefault();
      e.stopPropagation();
      var iso = moreBtn.getAttribute('data-day-iso');
      if (iso) openPopover(iso, moreBtn);
      return;
    }

    // Fechar popover dia
    if (root && !root.hidden) {
      if (e.target === root || (e.target.closest && e.target.closest('.th-cal-day-popover-close'))) {
        closePopover();
      }
    }
  });

  document.addEventListener('input', function (e) {
    if (e.target && e.target.classList && e.target.classList.contains('th-cf-search')) {
      var wrap = e.target.closest('.th-cf-wrap');
      if (wrap) filterList(wrap);
    }
  });

  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape') {
      if (activeWrap) { closeAllFilters(); return; }
      if (root && !root.hidden) closePopover();
    }
  });

  if (btnClose) btnClose.addEventListener('click', closePopover);

  window.addEventListener('resize', function () {
    closeAllFilters(true);
    if (root && !root.hidden) closePopover();
  });

})();
