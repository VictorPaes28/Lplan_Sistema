(function () {
  var script = document.currentScript;
  var pollUrl = script && script.getAttribute('data-poll-url');
  if (!pollUrl) return;

  var sinceId = 0;
  var started = false;
  var POLL_MS = 38000;
  var FIRST_POLL_MS = 12000;

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
    var el = document.createElement('div');
    el.className = 'lplan-nt-toast';
    el.setAttribute('role', 'status');
    el.dataset.type = item.type || 'system';

    var title = escapeHtml(item.title || 'Notificação');
    var msg = escapeHtml(item.message || '');
    var primaryLabel = item.diary_url ? 'Abrir relatório' : 'Ver centro';
    var primaryHref = item.diary_url || item.list_url || '#';

    el.innerHTML =
      '<span class="lplan-nt-toast-icon" aria-hidden="true"><i class="fas fa-bell"></i></span>' +
      '<div class="lplan-nt-toast-body">' +
      '<p class="lplan-nt-toast-title">' +
      title +
      '</p>' +
      (msg ? '<p class="lplan-nt-toast-msg">' + msg + '</p>' : '') +
      '<div class="lplan-nt-toast-actions">' +
      '<a class="lplan-nt-toast-link" href="' +
      escapeHtml(primaryHref) +
      '">' +
      escapeHtml(primaryLabel) +
      '</a>' +
      '</div></div>' +
      '<button type="button" class="lplan-nt-toast-close" aria-label="Fechar"><i class="fas fa-times" aria-hidden="true"></i></button>';

    stack.appendChild(el);

    var closeBtn = el.querySelector('.lplan-nt-toast-close');
    var t = window.setTimeout(function () {
      removeToast(el);
    }, 8200);
    if (closeBtn) {
      closeBtn.addEventListener('click', function () {
        window.clearTimeout(t);
        removeToast(el);
      });
    }
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
        updateBellBadge(typeof data.unread_count === 'number' ? data.unread_count : 0);
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
        items.forEach(function (item, i) {
          window.setTimeout(function () {
            showToast(item);
          }, i * 320);
        });
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
