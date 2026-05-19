(function () {
  // document.currentScript é null em muitos browsers para <script defer src="..."> — quebra o poll inteiro.
  var pollScript =
    document.querySelector('script[src*="notifications-poll"][data-poll-url]') ||
    document.currentScript;
  var pollUrl = pollScript && pollScript.getAttribute('data-poll-url');
  if (!pollUrl) return;

  var sinceId = 0;
  var started = false;
  /** Polling REST leve (~3×/min) — não depende só do reload para atualizar badge/toasts Core. */
  var POLL_MS = 20000;
  var FIRST_POLL_MS = 4000;
  /** Máximo de toasts visíveis em pilha (apenas notificações novas após abrir). */
  var MAX_STACK = 4;
  var TOAST_MS = 6000;
  /** IDs já conhecidos no carregamento — não repetir toast ao reabrir o sistema. */
  var BOOTSTRAP_SHOWN_IDS_KEY = 'lplan-nt-bootstrap-shown-ids';
  function defaultNotificationsListUrl() {
    return '/notifications/';
  }

  /** Badge do sino Core (notification unread). */
  function unreadCountForBell(data) {
    return typeof data.unread_count === 'number' ? data.unread_count : 0;
  }

  function bellLinkNodes() {
    var out = [];
    var desktop = document.querySelectorAll('.notif-bell-link');
    for (var i = 0; i < desktop.length; i++) out.push(desktop[i]);
    return out;
  }

  function updateBellBadge(count) {
    var links = bellLinkNodes();
    if (!links.length) return;
    var text = count > 99 ? '99+' : String(count);
    links.forEach(function (link) {
      var badge =
        link.querySelector('.notif-count-badge') ||
        link.querySelector('.notification-badge') ||
        link.querySelector('.mobile-menu-badge');
      if (count > 0) {
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
    });
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
      ty === 'pedido_atualizado' ||
      ty === 'restricao_criada' ||
      ty.indexOf('trackhub') === 0
    ) {
      return 'lplan-nt-toast-icon--blue';
    }
    if (ty === 'pedido_reenviado') {
      return 'lplan-nt-toast-icon--amber';
    }
    if (ty === 'pedido_exclusao_solicitada') {
      return 'lplan-nt-toast-icon--amber';
    }
    if (
      ty === 'rdo_aprovado' ||
      ty === 'pedido_aprovado' ||
      ty === 'pedido_exclusao_aprovada' ||
      ty === 'trackhub_etapa_concluida'
    ) {
      return 'lplan-nt-toast-icon--green';
    }
    if (ty === 'rdo_reprovado' || ty === 'pedido_reprovado' || ty === 'pedido_exclusao_rejeitada') {
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
      ty === 'pedido_exclusao_aprovada' ||
      ty === 'trackhub_etapa_concluida'
    ) {
      return 'fa-check';
    }
    if (ty === 'rdo_reprovado' || ty === 'pedido_reprovado' || ty === 'pedido_exclusao_rejeitada') {
      return 'fa-times';
    }
    if (ty === 'pedido_exclusao_solicitada') {
      return 'fa-trash-alt';
    }
    if (ty === 'pedido_comentario') {
      return 'fa-comment';
    }
    if (ty === 'pedido_criado') {
      return 'fa-file-alt';
    }
    if (ty === 'pedido_reenviado') {
      return 'fa-redo-alt';
    }
    if (ty === 'pedido_atualizado') {
      return 'fa-pen-to-square';
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

  function storageGet(key) {
    try {
      return window.localStorage || window.sessionStorage;
    } catch (e) {
      return null;
    }
  }

  function parseBootstrapShownMap() {
    try {
      var store = storageGet();
      if (!store) return {};
      var raw = store.getItem(BOOTSTRAP_SHOWN_IDS_KEY);
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
      var store = storageGet();
      if (!store) return;
      var m = parseBootstrapShownMap();
      for (var i = 0; i < ids.length; i++) {
        var id = ids[i];
        if (id != null) m[String(id)] = true;
      }
      var out = [];
      for (var k in m) {
        if (Object.prototype.hasOwnProperty.call(m, k)) out.push(parseInt(k, 10));
      }
      out = out.filter(function (n) {
        return !isNaN(n);
      });
      if (out.length > 500) {
        out = out.slice(-500);
      }
      store.setItem(BOOTSTRAP_SHOWN_IDS_KEY, JSON.stringify(out));
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
        var bellUnread = unreadCountForBell(data);
        updateBellBadge(bellUnread);
        var items = data.items || [];
        var allIds = [];
        for (var j = 0; j < items.length; j++) {
          if (items[j] && items[j].id != null) allIds.push(items[j].id);
        }
        rememberBootstrapShownIds(allIds);
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
        updateBellBadge(unreadCountForBell(data));
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
      document.addEventListener('visibilitychange', function () {
        if (!document.hidden && started) poll();
      });
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', go);
  } else {
    go();
  }
})();
