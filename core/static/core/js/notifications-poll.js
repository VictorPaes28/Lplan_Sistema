(function () {
  // document.currentScript é null em muitos browsers para <script defer src="..."> — quebra o poll inteiro.
  var pollScript =
    document.querySelector('script[src*="notifications-poll"][data-poll-url]') ||
    document.currentScript;
  var pollUrl = pollScript && pollScript.getAttribute('data-poll-url');
  if (!pollUrl) return;

  var sinceId = 0;
  var started = false;
  var POLL_MS = 38000;
  var FIRST_POLL_MS = 12000;
  /** Máximo de toasts visíveis em pilha (bootstrap + poll). */
  var MAX_STACK = 8;
  var TOAST_MS = 6000;
  /** IDs de notificação já exibidos como toast nesta sessão (evita repetir a cada F5). */
  var SESSION_BOOTSTRAP_SHOWN_IDS = 'lplan-nt-bootstrap-shown-ids';

  function updateBellBadge(count) {
    var link = document.querySelector('.notif-bell-link');
    if (!link) return;
    var badge = link.querySelector('.notif-count-badge');
    if (count > 0) {
      var text = count > 99 ? '99+' : String(count);
      if (!badge) {
        badge = document.createElement('span');
        badge.className = 'notif-count-badge';
        link.appendChild(badge);
      }
      badge.textContent = text;
      badge.setAttribute('aria-label', count + ' notificações não lidas');
      link.setAttribute('aria-label', 'Notificações. ' + count + ' não lidas');
    } else {
      if (badge) badge.remove();
      link.setAttribute('aria-label', 'Notificações');
    }
  }

  function ensureStack() {
    var stack = document.getElementById('lplan-nt-stack');
    if (!stack) {
      stack = document.createElement('div');
      stack.id = 'lplan-nt-stack';
      stack.className = 'lplan-nt-stack';
      stack.setAttribute('role', 'region');
      stack.setAttribute('aria-label', 'Novas notificações');
      document.body.appendChild(stack);
    }
    return stack;
  }

  function escapeHtml(s) {
    var d = document.createElement('div');
    d.textContent = s == null ? '' : String(s);
    return d.innerHTML;
  }

  function truncateMsg(s, maxLen) {
    var t = s == null ? '' : String(s);
    if (t.length <= maxLen) return t;
    return t.slice(0, maxLen).trim() + '…';
  }

  function iconClassForType(t) {
    var ty = (t || 'system').toLowerCase();
    if (
      ty === 'rdo_pendente' ||
      ty === 'pedido_criado' ||
      ty === 'restricao_criada' ||
      ty.indexOf('trackhub') === 0
    ) {
      return 'lplan-nt-toast-icon--blue';
    }
    if (
      ty === 'rdo_aprovado' ||
      ty === 'pedido_aprovado' ||
      ty === 'trackhub_etapa_concluida'
    ) {
      return 'lplan-nt-toast-icon--green';
    }
    if (ty === 'rdo_reprovado' || ty === 'pedido_reprovado') {
      return 'lplan-nt-toast-icon--red';
    }
    if (ty === 'restricao_prazo' || ty === 'trackhub_prazo') {
      return 'lplan-nt-toast-icon--amber';
    }
    return 'lplan-nt-toast-icon--slate';
  }

  function iconGlyphForType(t) {
    var ty = (t || 'system').toLowerCase();
    if (
      ty === 'rdo_aprovado' ||
      ty === 'pedido_aprovado' ||
      ty === 'trackhub_etapa_concluida'
    ) {
      return 'fa-check';
    }
    if (ty === 'rdo_reprovado' || ty === 'pedido_reprovado') {
      return 'fa-times';
    }
    if (ty === 'pedido_comentario') {
      return 'fa-comment';
    }
    return 'fa-bell';
  }

  function trimStack(stack) {
    var nodes = stack.querySelectorAll('.lplan-nt-toast:not(.lplan-nt-toast-out)');
    for (var i = 0; i < nodes.length - MAX_STACK; i++) {
      removeToast(nodes[i]);
    }
  }

  function removeToast(el) {
    if (!el || el.classList.contains('lplan-nt-toast-out')) return;
    el.classList.add('lplan-nt-toast-out');
    el.addEventListener(
      'animationend',
      function () {
        el.remove();
      },
      { once: true }
    );
  }

  function showToast(item) {
    var stack = ensureStack();
    trimStack(stack);

    var el = document.createElement('div');
    el.className = 'lplan-nt-toast';
    el.setAttribute('role', 'status');
    el.dataset.type = item.type || 'system';

    var title = escapeHtml(item.title || 'Notificação');
    var rawMsg = item.message || '';
    var msg = escapeHtml(truncateMsg(rawMsg, 100));
    var related =
      (item.related_url && String(item.related_url).trim()) ||
      (item.diary_url && String(item.diary_url).trim()) ||
      '';
    var listUrl = item.list_url || '/notifications/';
    var openUrl = item.open_url && String(item.open_url).trim();
    var actionUrl = openUrl || related || listUrl;
    var iconWrapClass = 'lplan-nt-toast-icon ' + iconClassForType(item.type);
    var ig = iconGlyphForType(item.type);

    el.innerHTML =
      '<span class="' +
      iconWrapClass +
      '" aria-hidden="true"><i class="fas ' +
      ig +
      '"></i></span>' +
      '<div class="lplan-nt-toast-body">' +
      '<p class="lplan-nt-toast-title"><strong>' +
      title +
      '</strong></p>' +
      (msg
        ? '<p class="lplan-nt-toast-msg">' + msg + '</p>'
        : '') +
      '<div class="lplan-nt-toast-actions">' +
      '<a class="lplan-nt-toast-link" href="' +
      escapeHtml(actionUrl) +
      '">Ver</a>' +
      '</div></div>' +
      '<button type="button" class="lplan-nt-toast-close" aria-label="Fechar"><i class="fas fa-times" aria-hidden="true"></i></button>' +
      '<div class="lplan-nt-toast-progress" aria-hidden="true"><span class="lplan-nt-toast-progress-bar"></span></div>';

    stack.appendChild(el);

    var closeBtn = el.querySelector('.lplan-nt-toast-close');
    var bar = el.querySelector('.lplan-nt-toast-progress-bar');
    if (bar) {
      bar.style.animationDuration = TOAST_MS / 1000 + 's';
    }
    var t = window.setTimeout(function () {
      removeToast(el);
    }, TOAST_MS);
    if (closeBtn) {
      closeBtn.addEventListener('click', function () {
        window.clearTimeout(t);
        removeToast(el);
      });
    }
  }

  function parseBootstrapShownMap() {
    try {
      if (!window.sessionStorage) return {};
      var raw = sessionStorage.getItem(SESSION_BOOTSTRAP_SHOWN_IDS);
      if (!raw) return {};
      var arr = JSON.parse(raw);
      if (!Array.isArray(arr)) return {};
      var m = {};
      for (var i = 0; i < arr.length; i++) m[String(arr[i])] = true;
      return m;
    } catch (e) {
      return {};
    }
  }

  function rememberBootstrapShownIds(ids) {
    if (!ids || !ids.length) return;
    try {
      if (!window.sessionStorage) return;
      var m = parseBootstrapShownMap();
      for (var i = 0; i < ids.length; i++) {
        var id = ids[i];
        if (id != null) m[String(id)] = true;
      }
      var out = [];
      for (var k in m) out.push(parseInt(k, 10));
      sessionStorage.setItem(SESSION_BOOTSTRAP_SHOWN_IDS, JSON.stringify(out));
    } catch (e) {}
  }

  function showUnreadReminder(count) {
    if (!count || count <= 0) return;
    var key = 'lplan-nt-unread-reminder-shown';
    try {
      if (window.sessionStorage && sessionStorage.getItem(key) === '1') return;
    } catch (e) {}
    showToast({
      title: 'Você tem notificações pendentes',
      message:
        count +
        ' notificação(ões) não lida(s). Clique em Ver para abrir o centro.',
      type: 'system',
      diary_url: null,
      related_url: '',
      list_url: '/notifications/',
    });
    try {
      if (window.sessionStorage) sessionStorage.setItem(key, '1');
    } catch (e) {}
  }

  function fetchJson(url) {
    return fetch(url, {
      credentials: 'same-origin',
      headers: { 'X-Requested-With': 'XMLHttpRequest' },
    }).then(function (r) {
      if (!r.ok) throw new Error('poll ' + r.status);
      return r.json();
    });
  }

  function bootstrap() {
    return fetchJson(pollUrl + '?bootstrap=1')
      .then(function (data) {
        sinceId = data.max_id || 0;
        var unread = typeof data.unread_count === 'number' ? data.unread_count : 0;
        updateBellBadge(unread);
        var items = data.items || [];
        var shownMap = parseBootstrapShownMap();
        var fresh = [];
        for (var j = 0; j < items.length; j++) {
          var row = items[j];
          var rid = row && row.id != null ? String(row.id) : '';
          if (rid && !shownMap[rid]) fresh.push(row);
        }
        if (fresh.length > 0) {
          var newIds = [];
          for (var k = 0; k < fresh.length; k++) {
            (function (idx) {
              window.setTimeout(function () {
                showToast(fresh[idx]);
              }, idx * 320);
            })(k);
            if (fresh[k].id != null) newIds.push(fresh[k].id);
          }
          rememberBootstrapShownIds(newIds);
        } else if (items.length === 0 && unread > 0) {
          showUnreadReminder(unread);
        }
        started = true;
      })
      .catch(function () {
        started = true;
      });
  }

  function poll() {
    if (!started) return;
    fetchJson(pollUrl + '?since_id=' + encodeURIComponent(String(sinceId)))
      .then(function (data) {
        updateBellBadge(typeof data.unread_count === 'number' ? data.unread_count : 0);
        if (data.max_id != null) sinceId = data.max_id;
        var items = data.items || [];
        var limit = Math.min(items.length, MAX_STACK);
        for (var i = 0; i < limit; i++) {
          (function (idx) {
            window.setTimeout(function () {
              showToast(items[idx]);
            }, idx * 320);
          })(i);
        }
      })
      .catch(function () {});
  }

  function go() {
    bootstrap().then(function () {
      window.setInterval(poll, POLL_MS);
      window.setTimeout(poll, FIRST_POLL_MS);
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', go);
  } else {
    go();
  }
})();
