(function () {
    'use strict';

    var storageKey = 'laborCatalogScroll';

    function getScrollEl() {
        return document.scrollingElement || document.documentElement;
    }

    function saveScrollPosition() {
        try {
            var scrollEl = getScrollEl();
            sessionStorage.setItem(storageKey, String(scrollEl.scrollTop || window.scrollY));
        } catch (err) {}
    }

    function restoreScrollPosition() {
        var scrollEl = getScrollEl();
        try {
            var saved = sessionStorage.getItem(storageKey);
            if (saved !== null) {
                sessionStorage.removeItem(storageKey);
                var y = parseInt(saved, 10);
                if (!isNaN(y)) {
                    scrollEl.scrollTop = y;
                    return;
                }
            }
        } catch (err) {}

        var hash = window.location.hash;
        if (!hash) return;
        var target = document.querySelector(hash);
        if (target) {
            target.scrollIntoView({ behavior: 'auto', block: 'nearest' });
        }
    }

    function showToast(message, type) {
        var host = document.getElementById('labor-catalog-toast-host');
        if (!host) {
            host = document.createElement('div');
            host.id = 'labor-catalog-toast-host';
            host.className = 'labor-catalog-toast-host';
            host.setAttribute('aria-live', 'polite');
            document.body.appendChild(host);
        }
        var el = document.createElement('div');
        el.className = 'labor-catalog-toast labor-catalog-toast--' + (type || 'success');
        el.textContent = message;
        host.appendChild(el);
        window.setTimeout(function () {
            el.classList.add('is-leaving');
            window.setTimeout(function () {
                el.remove();
            }, 280);
        }, 2600);
    }

    function updateItemToggleUI(itemId, isActive) {
        var row = document.getElementById('labor-item-' + itemId);
        if (!row) return;
        row.classList.toggle('is-inactive', !isActive);
        var badge = row.querySelector('.labor-item-actions .badge-muted');
        if (badge) {
            badge.className = 'badge-muted ' + (isActive ? 'badge-on' : 'badge-off');
            badge.textContent = isActive ? 'Visível' : 'Oculto';
        }
        var form = row.querySelector('form input[name="action"][value="toggle_item"]');
        form = form ? form.closest('form') : null;
        var btn = form ? form.querySelector('button[type="submit"]') : null;
        if (btn) {
            btn.className = 'btn-soft ' + (isActive ? 'btn-soft--hide' : 'btn-soft--show');
            btn.textContent = isActive ? 'Ocultar' : 'Mostrar';
        }
    }

    function updateCategoryToggleUI(catId, isActive) {
        var block = document.getElementById('labor-cat-' + catId);
        if (!block) return;
        block.classList.toggle('is-inactive', !isActive);
        var badge = block.querySelector('.cat-block-meta .badge-muted');
        if (badge) {
            badge.className = 'badge-muted ' + (isActive ? 'badge-on' : 'badge-off');
            badge.textContent = isActive ? 'Visível no RDO' : 'Categoria oculta';
        }
        var form = block.querySelector('form input[name="action"][value="toggle_category"]');
        form = form ? form.closest('form') : null;
        var btn = form ? form.querySelector('button[type="submit"]') : null;
        if (btn) {
            btn.className = 'btn-soft ' + (isActive ? 'btn-soft--hide' : 'btn-soft--show');
            btn.textContent = isActive ? 'Ocultar categoria' : 'Mostrar categoria';
        }
    }

    function updateActiveKpi(delta) {
        var v = document.querySelector('.labor-kpi .v');
        if (!v) return;
        var n = parseInt(v.textContent, 10);
        if (isNaN(n)) return;
        v.textContent = String(Math.max(0, n + delta));
    }

    function getFormAction(form) {
        var action = form.getAttribute('action');
        if (action) return action;
        return window.location.href;
    }

    async function handleToggleSubmit(form) {
        var actionInput = form.querySelector('input[name="action"]');
        var action = actionInput ? actionInput.value : '';
        if (action !== 'toggle_item' && action !== 'toggle_category') return false;

        var btn = form.querySelector('button[type="submit"]');
        if (btn) btn.disabled = true;

        try {
            var fd = new FormData(form);
            fd.set('ajax', '1');
            var resp = await fetch(getFormAction(form), {
                method: 'POST',
                body: fd,
                headers: {
                    'X-Requested-With': 'XMLHttpRequest',
                    Accept: 'application/json',
                },
                credentials: 'same-origin',
            });
            var data = {};
            try {
                data = await resp.json();
            } catch (parseErr) {
                data = {};
            }
            if (!resp.ok || !data.success) {
                throw new Error((data && (data.error || data.message)) || 'Não foi possível atualizar.');
            }
            if (data.kind === 'item') {
                updateItemToggleUI(data.id, data.is_active);
                updateActiveKpi(data.is_active ? 1 : -1);
            } else if (data.kind === 'category') {
                updateCategoryToggleUI(data.id, data.is_active);
            }
            if (data.message) showToast(data.message, 'success');
            return true;
        } catch (err) {
            showToast(err.message || 'Erro ao atualizar.', 'error');
            return true;
        } finally {
            if (btn) btn.disabled = false;
        }
    }

    function isCatalogNavigationLink(link) {
        var href = link.getAttribute('href') || '';
        if (!href || href.charAt(0) === '#') return false;
        return href.indexOf('mao-de-obra-rdo') !== -1;
    }

    function initLaborCatalogNavigation() {
        document.addEventListener(
            'submit',
            function (e) {
                var form = e.target;
                if (!form || form.tagName !== 'FORM') return;
                if ((form.method || 'get').toLowerCase() !== 'post') return;

                var actionInput = form.querySelector('input[name="action"]');
                var action = actionInput ? actionInput.value : '';
                if (action === 'toggle_item' || action === 'toggle_category') {
                    e.preventDefault();
                    handleToggleSubmit(form);
                    return;
                }
                saveScrollPosition();
            },
            true
        );

        document.addEventListener(
            'click',
            function (e) {
                var link = e.target.closest('.labor-catalog-detail a[href], .labor-catalog-scroll a[href]');
                if (!link || !isCatalogNavigationLink(link)) return;
                saveScrollPosition();
            },
            true
        );

        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', restoreScrollPosition);
        } else {
            restoreScrollPosition();
        }
    }

    window.closeEmbeddedLaborCatalog = window.closeEmbeddedLaborCatalog || function () {
        try {
            window.parent.postMessage({ type: 'labor-catalog-close' }, '*');
        } catch (err) {}
    };

    initLaborCatalogNavigation();
})();
