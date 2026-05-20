/**
 * Popover "Mais N" — lista todas as pendências do dia (estilo Google Agenda).
 */
(function () {
  'use strict';

  var root = document.getElementById('th-cal-day-popover');
  if (!root) return;

  var panel = root.querySelector('.th-cal-day-popover-panel');
  var elWeekday = document.getElementById('th-cal-day-popover-weekday');
  var elDayNum = document.getElementById('th-cal-day-popover-num');
  var elList = document.getElementById('th-cal-day-popover-list');
  var btnClose = root.querySelector('.th-cal-day-popover-close');
  var dataEl = document.getElementById('th-cal-day-data');
  var urlPattern = (dataEl && dataEl.dataset.urlPattern) || '';

  var dayData = {};
  if (dataEl && dataEl.textContent) {
    try {
      dayData = JSON.parse(dataEl.textContent);
    } catch (e) {
      dayData = {};
    }
  }

  function pendenciaUrl(id) {
    return urlPattern.replace('{id}', String(id));
  }

  function closePopover() {
    root.hidden = true;
    root.setAttribute('aria-hidden', 'true');
  }

  function positionPanel(anchor) {
    if (!panel || !anchor) return;
    var rect = anchor.getBoundingClientRect();
    var pw = panel.offsetWidth || 220;
    var ph = panel.offsetHeight || 200;
    var left = rect.left + rect.width / 2 - pw / 2;
    var top = rect.bottom + 6;
    if (left + pw > window.innerWidth - 8) left = window.innerWidth - pw - 8;
    if (left < 8) left = 8;
    if (top + ph > window.innerHeight - 8) {
      top = rect.top - ph - 6;
    }
    if (top < 8) top = 8;
    panel.style.left = left + 'px';
    panel.style.top = top + 'px';
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
      if (item.status === 'concluida') a.classList.add('th-cal-pop-item--concluida');
      else if (item.status === 'cancelada') a.classList.add('th-cal-pop-item--cancelada');
      a.title = item.titulo || '';
      if (item.continues_before) a.classList.add('th-cal-pop-item--cont-left');
      if (item.continues_after) a.classList.add('th-cal-pop-item--cont-right');

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
    var pack = dayData[iso];
    if (!pack) return;
    if (elWeekday) elWeekday.textContent = pack.weekday || '';
    if (elDayNum) elDayNum.textContent = String(pack.day != null ? pack.day : '');
    renderList(pack.pendencias || []);
    root.hidden = false;
    root.setAttribute('aria-hidden', 'false');
    positionPanel(anchor);
    requestAnimationFrame(function () {
      positionPanel(anchor);
    });
  }

  document.addEventListener('click', function (e) {
    var btn = e.target.closest('.th-cal-more');
    if (btn) {
      e.preventDefault();
      e.stopPropagation();
      var iso = btn.getAttribute('data-day-iso');
      if (iso) openPopover(iso, btn);
      return;
    }
    if (root.hidden) return;
    if (e.target === root || e.target.closest('.th-cal-day-popover-close')) {
      closePopover();
    }
  });

  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape' && !root.hidden) closePopover();
  });

  if (btnClose) btnClose.addEventListener('click', closePopover);

  window.addEventListener('resize', function () {
    if (!root.hidden) closePopover();
  });
})();
