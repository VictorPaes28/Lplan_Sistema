/**
 * No mobile, substitui <select> do modal criar pendência por lista
 * com a mesma largura do campo (o popup nativo ignora CSS).
 */
(function (global) {
  'use strict';

  var MQ = '(max-width: 768px)';

  function isMobile() {
    return global.matchMedia && global.matchMedia(MQ).matches;
  }

  function shouldEnhance(select) {
    if (!select || select.tagName !== 'SELECT') return false;
    if (select.multiple) return false;
    if (select.closest('.th-resp-picker-wrap')) return false;
    if (select.closest('.th-ms-wrap')) return false;
    if (select.hasAttribute('data-th-ms-skip')) return false;
    var form = document.getElementById('th-cal-criar-form');
    if (form && !form.contains(select)) return false;
    return true;
  }

  function getLabel(select) {
    var opt = select.options[select.selectedIndex];
    if (!opt) return 'Selecione…';
    var t = (opt.textContent || '').trim();
    if (!select.value && (opt.disabled || !opt.value)) return t || 'Selecione…';
    return t || 'Selecione…';
  }

  function buildPanelOptions(panel, select, wrap) {
    panel.innerHTML = '';
    Array.prototype.forEach.call(select.options, function (opt) {
      var li = document.createElement('li');
      var btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'th-ms-opt';
      btn.setAttribute('role', 'option');
      btn.setAttribute('data-value', opt.value);
      btn.textContent = (opt.textContent || '').trim();
      if (opt.disabled) btn.disabled = true;
      btn.addEventListener('click', function (e) {
        e.preventDefault();
        e.stopPropagation();
        if (btn.disabled) return;
        select.value = opt.value;
        try {
          select.dispatchEvent(new Event('change', { bubbles: true }));
        } catch (err) {
          var ev = document.createEvent('HTMLEvents');
          ev.initEvent('change', true, false);
          select.dispatchEvent(ev);
        }
        syncTrigger(wrap, select);
        closeAll();
      });
      li.appendChild(btn);
      panel.appendChild(li);
    });
  }

  function syncTrigger(wrap, select) {
    var label = wrap.querySelector('.th-ms-label');
    if (label) label.textContent = getLabel(select);
    wrap.querySelectorAll('.th-ms-opt').forEach(function (btn) {
      var v = btn.getAttribute('data-value');
      if (v === null) v = '';
      btn.classList.toggle('th-ms-opt--selected', v === select.value);
      btn.setAttribute('aria-selected', v === select.value ? 'true' : 'false');
    });
  }

  function closeAll(except) {
    document.querySelectorAll('#th-cal-criar-form .th-ms-wrap.th-ms-wrap--open').forEach(function (w) {
      if (except && w === except) return;
      w.classList.remove('th-ms-wrap--open');
      var p = w.querySelector('.th-ms-panel');
      var t = w.querySelector('.th-ms-trigger');
      if (p) p.hidden = true;
      if (t) t.setAttribute('aria-expanded', 'false');
    });
  }

  function unenhance(select) {
    var wrap = select && select._thMsWrap;
    if (!wrap || !wrap.parentNode) return;
    var parent = wrap.parentNode;
    parent.insertBefore(select, wrap);
    wrap.remove();
    select.classList.remove('th-ms-native');
    select.removeAttribute('aria-hidden');
    select.style.cssText = '';
    delete select._thMsWrap;
  }

  function enhance(select) {
    if (!isMobile() || !shouldEnhance(select)) return null;
    if (select._thMsWrap) return select._thMsWrap;

    var parent = select.parentNode;
    if (!parent) return null;

    var wrap = document.createElement('div');
    wrap.className = 'th-ms-wrap';

    var trigger = document.createElement('button');
    trigger.type = 'button';
    trigger.className = 'th-ms-trigger';
    trigger.setAttribute('aria-haspopup', 'listbox');
    trigger.setAttribute('aria-expanded', 'false');
    trigger.innerHTML =
      '<span class="th-ms-label"></span>' +
      '<span class="th-ms-chevron" aria-hidden="true">▾</span>';

    var panel = document.createElement('ul');
    panel.className = 'th-ms-panel';
    panel.hidden = true;
    panel.setAttribute('role', 'listbox');

    parent.insertBefore(wrap, select);
    wrap.appendChild(select);
    wrap.appendChild(trigger);
    wrap.appendChild(panel);

    select.classList.add('th-ms-native');
    select.setAttribute('aria-hidden', 'true');
    select.tabIndex = -1;

    buildPanelOptions(panel, select, wrap);
    syncTrigger(wrap, select);

    select._thMsWrap = wrap;
    wrap._thMsSelect = select;

    trigger.addEventListener('click', function (e) {
      e.preventDefault();
      e.stopPropagation();
      var open = wrap.classList.contains('th-ms-wrap--open');
      closeAll();
      if (!open) {
        wrap.classList.add('th-ms-wrap--open');
        panel.hidden = false;
        trigger.setAttribute('aria-expanded', 'true');
      }
    });

    select.addEventListener('change', function () {
      syncTrigger(wrap, select);
    });

    return wrap;
  }

  function rebuild(select) {
    if (!select) return;
    if (!isMobile()) {
      unenhance(select);
      return;
    }
    if (!select._thMsWrap) {
      enhance(select);
      return;
    }
    var wrap = select._thMsWrap;
    var panel = wrap.querySelector('.th-ms-panel');
    if (panel) buildPanelOptions(panel, select, wrap);
    syncTrigger(wrap, select);
  }

  function enhanceAll(root) {
    if (!isMobile()) return;
    root = root || document.getElementById('th-cal-criar-form');
    if (!root) return;
    root.querySelectorAll('select').forEach(function (sel) {
      if (shouldEnhance(sel) && !sel._thMsWrap) enhance(sel);
      else if (sel._thMsWrap) syncTrigger(sel._thMsWrap, sel);
    });
  }

  function syncAll(root) {
    root = root || document.getElementById('th-cal-criar-form');
    if (!root) return;
    root.querySelectorAll('.th-ms-wrap').forEach(function (wrap) {
      var sel = wrap._thMsSelect || wrap.querySelector('select.th-ms-native');
      if (sel) syncTrigger(wrap, sel);
    });
  }

  function unenhanceAll(root) {
    root = root || document.getElementById('th-cal-criar-form');
    if (!root) return;
    root.querySelectorAll('select.th-ms-native').forEach(unenhance);
  }

  document.addEventListener('click', function (e) {
    if (!isMobile()) return;
    if (e.target.closest && e.target.closest('#th-cal-criar-form .th-ms-wrap')) return;
    closeAll();
  });

  if (global.matchMedia) {
    var mq = global.matchMedia(MQ);
    var onMq = function () {
      var form = document.getElementById('th-cal-criar-form');
      if (!form) return;
      if (isMobile()) enhanceAll(form);
      else unenhanceAll(form);
    };
    if (mq.addEventListener) mq.addEventListener('change', onMq);
    else if (mq.addListener) mq.addListener(onMq);
  }

  global.ThModalSelect = {
    enhance: enhance,
    enhanceAll: enhanceAll,
    rebuild: rebuild,
    syncAll: syncAll,
    unenhanceAll: unenhanceAll,
    isMobile: isMobile,
    closeAll: closeAll,
  };
})(window);
