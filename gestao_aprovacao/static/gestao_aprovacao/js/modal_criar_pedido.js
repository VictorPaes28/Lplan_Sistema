(function () {
    var urlTpl = typeof window.LPLAN_CREATE_WORKORDER_URL === 'string' ? window.LPLAN_CREATE_WORKORDER_URL : '';

    function getOverlay() {
        return document.getElementById('wc-create-overlay');
    }

    function getScroll() {
        return document.getElementById('wc-create-scroll');
    }

    function buildCreateUrl(embedQuery) {
        if (!urlTpl) return '';
        var q = embedQuery !== false ? 'embed=modal&v=' + String(Date.now()) : '';
        if (!q) return urlTpl.split('?')[0];
        return urlTpl.indexOf('?') >= 0 ? urlTpl.split('?')[0] + '&' + q : urlTpl.split('?')[0] + '?' + q;
    }

    function getCsrfToken() {
        var m = document.querySelector('meta[name="csrf-token"]');
        if (m && m.content) return String(m.content).trim();
        var h = document.querySelector('.gestao-csrf-root input[name="csrfmiddlewaretoken"]');
        if (h && h.value) return String(h.value).trim();
        var inp = document.querySelector('input[name="csrfmiddlewaretoken"]');
        return inp && inp.value ? String(inp.value).trim() : '';
    }

    function openOverlay() {
        var el = getOverlay();
        if (!el) return;
        el.classList.add('is-open');
        el.setAttribute('aria-hidden', 'false');
        document.body.classList.add('wc-create-modal-open');
        var closeBtn = document.getElementById('wc-create-close-btn');
        if (closeBtn) closeBtn.focus();
    }

    function closeOverlay() {
        var el = getOverlay();
        if (!el) return;
        el.classList.remove('is-open');
        el.classList.remove('is-busy');
        el.setAttribute('aria-hidden', 'true');
        document.body.classList.remove('wc-create-modal-open');
        var scroll = getScroll();
        if (scroll) scroll.innerHTML = '';
    }

    function setBusy(on) {
        var el = getOverlay();
        if (!el) return;
        if (on) el.classList.add('is-busy');
        else el.classList.remove('is-busy');
    }

    function mountFragment(html) {
        var scroll = getScroll();
        if (!scroll) return;
        scroll.innerHTML = html;
        var root = scroll.querySelector('.wc-modal-fragment') || scroll;
        if (typeof window.LplanWorkorderFormInit === 'function') {
            window.LplanWorkorderFormInit(root, { skipSubmitLock: true });
        }
        var form = scroll.querySelector('#workorder-create-form');
        if (form) form.addEventListener('submit', onFormSubmitAjax);
        scroll.querySelectorAll('.wc-modal-cancel').forEach(function (btn) {
            btn.addEventListener('click', function () {
                closeOverlay();
            });
        });
        var first = scroll.querySelector('select, input:not([type="hidden"])');
        if (first && typeof first.focus === 'function') first.focus();
    }

    function onFormSubmitAjax(ev) {
        var form = ev.target;
        if (!form || form.id !== 'workorder-create-form') return;
        ev.preventDefault();
        var token = getCsrfToken();
        if (!token) {
            window.alert('CSRF não disponível. Recarregue a página.');
            return;
        }
        var btn = form.querySelector('#workorder-submit-btn');
        setBusy(true);
        if (btn) {
            btn.disabled = true;
            btn.dataset._prevText = btn.textContent;
            btn.textContent = 'Salvando…';
        }
        var fd = new FormData(form);
        fetch(form.action, {
            method: 'POST',
            body: fd,
            credentials: 'same-origin',
            headers: {
                'X-CSRFToken': token,
                'X-Requested-With': 'XMLHttpRequest'
            }
        })
            .then(function (res) {
                var ct = (res.headers.get('Content-Type') || '').toLowerCase();
                if (ct.indexOf('application/json') !== -1) {
                    return res.json().then(function (j) {
                        return { type: 'json', res: res, body: j };
                    });
                }
                return res.text().then(function (t) {
                    return { type: 'html', res: res, body: t };
                });
            })
            .then(function (packed) {
                setBusy(false);
                if (btn) {
                    btn.disabled = false;
                    if (btn.dataset._prevText) btn.textContent = btn.dataset._prevText;
                }
                var res = packed.res;
                if (packed.type === 'json') {
                    var j = packed.body || {};
                    if (res.ok && j.ok === true && j.pk != null) {
                        closeOverlay();
                        var pk = parseInt(String(j.pk), 10);
                        if (typeof window.abrirModalPedido === 'function') window.abrirModalPedido(pk);
                        else window.location.href = '/gestao/pedidos/' + String(j.pk) + '/';
                        return;
                    }
                    if (j.reload || j.redirect) {
                        window.location.href =
                            typeof j.redirect === 'string'
                                ? j.redirect
                                : window.LPLAN_CREATE_WORKORDER_URL.replace(/\/criar\/?$/, '/') || '/gestao/pedidos/';
                        return;
                    }
                    window.alert(j.error || j.message || 'Não foi possível criar o pedido.');
                    return;
                }
                if (packed.type === 'html') {
                    if (res.ok || res.status === 422) mountFragment(packed.body);
                    else window.alert('Erro ao enviar (' + res.status + '). Tente novamente.');
                    return;
                }
            })
            .catch(function () {
                setBusy(false);
                if (btn) {
                    btn.disabled = false;
                    if (btn.dataset._prevText) btn.textContent = btn.dataset._prevText;
                }
                window.alert('Erro de rede. Verifique sua conexão.');
            });
    }

    function loadModalForm() {
        var fetchUrl = buildCreateUrl(true);
        if (!fetchUrl) return;
        setBusy(true);
        fetch(fetchUrl, {
            credentials: 'same-origin',
            headers: { 'X-Requested-With': 'XMLHttpRequest' }
        })
            .then(function (r) {
                if (!r.ok) {
                    var ct = (r.headers.get('Content-Type') || '').toLowerCase();
                    if (ct.indexOf('application/json') !== -1) {
                        return r.json().then(function (j) {
                            throw new Error(j.error || r.statusText);
                        });
                    }
                    throw new Error(r.statusText);
                }
                return r.text();
            })
            .then(function (html) {
                mountFragment(html);
                setBusy(false);
            })
            .catch(function (e) {
                setBusy(false);
                window.alert(e.message || 'Não foi possível abrir o formulário.');
                closeOverlay();
            });
    }

    function shouldDeferToBrowser(ev) {
        return (
            ev.metaKey ||
            ev.ctrlKey ||
            ev.shiftKey ||
            ev.altKey ||
            (typeof ev.button === 'number' && ev.button !== 0)
        );
    }

    function onDocClick(ev) {
        var a = ev.target.closest('.gc-open-create-modal,[data-open-create-modal]');
        if (!a || !(a.matches('a'))) return;
        if (shouldDeferToBrowser(ev)) return;
        var href = a.getAttribute('href') || '';
        if (!href || href === '#') {
            ev.preventDefault();
            openOverlay();
            loadModalForm();
            return;
        }
        try {
            var u = new URL(href, window.location.origin);
            var pathOk =
                urlTpl && urlTpl.trim()
                    ? u.pathname.replace(/\/$/, '') === new URL(urlTpl, window.location.origin).pathname.replace(/\/$/, '')
                    : u.pathname.indexOf('/pedidos/criar') !== -1;
            if (pathOk && !u.searchParams.get('no_modal')) {
                ev.preventDefault();
                openOverlay();
                loadModalForm();
            }
        } catch (_) {
            /* ignore */
        }
    }

    document.addEventListener(
        'click',
        function (ev) {
            try {
                onDocClick(ev);
            } catch (_) {
                /* empty */
            }
        },
        true
    );

    document.addEventListener('DOMContentLoaded', function () {
        var overlay = getOverlay();
        if (!overlay) return;
        var closeBtn = document.getElementById('wc-create-close-btn');
        if (closeBtn) closeBtn.addEventListener('click', closeOverlay);
        overlay.addEventListener('click', function (e) {
            if (e.target === overlay) closeOverlay();
        });
        document.addEventListener('keydown', function (e) {
            if (e.key !== 'Escape') return;
            if (!overlay.classList.contains('is-open')) return;
            closeOverlay();
        });
    });
})();
