/**
 * Barra de progresso em cliques de navegação (mesma origem) e
 * animação leve após swaps HTMX.
 */
(function () {
    'use strict';

    var progressEl = null;

    function showProgress() {
        if (!progressEl) return;
        progressEl.hidden = false;
        progressEl.classList.add('is-active');
    }

    function hideProgress() {
        if (!progressEl) return;
        progressEl.classList.remove('is-active');
        window.setTimeout(function () {
            if (!progressEl.classList.contains('is-active')) {
                progressEl.hidden = true;
            }
        }, 280);
    }

    function shouldShowProgressForAnchor(anchor, event) {
        if (!anchor || anchor.tagName !== 'A') return false;
        if (event.defaultPrevented) return false;
        if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return false;
        if (typeof event.button === 'number' && event.button !== 0) return false;
        if (anchor.getAttribute('target') === '_blank') return false;
        if (anchor.hasAttribute('download')) return false;
        if (anchor.getAttribute('data-no-nav-progress') !== null) return false;
        /* HTMX trata o pedido na própria página: não há load/pageshow para esconder a barra */
        if (
            anchor.hasAttribute('hx-get') ||
            anchor.hasAttribute('hx-post') ||
            anchor.hasAttribute('hx-put') ||
            anchor.hasAttribute('hx-patch') ||
            anchor.hasAttribute('hx-delete')
        ) {
            return false;
        }

        var hrefAttr = anchor.getAttribute('href');
        if (!hrefAttr || hrefAttr === '#' || hrefAttr.indexOf('javascript:') === 0) return false;

        try {
            var u = new URL(anchor.href, window.location.href);
            if (u.origin !== window.location.origin) return false;
            /* Navegação só de âncora na mesma página: não mostra barra */
            if (
                u.pathname === window.location.pathname &&
                u.search === window.location.search &&
                u.hash !== window.location.hash
            ) {
                return false;
            }
        } catch (e) {
            return false;
        }

        return true;
    }

    function onHtmxAfterSwap(event) {
        var el = event.detail && event.detail.target;
        if (!el || !el.classList) return;
        if (el.closest && el.closest('[data-no-swap-animation]')) return;

        if (window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
            return;
        }

        el.classList.remove('lplan-swap-enter');
        void el.offsetWidth;
        el.classList.add('lplan-swap-enter');

        function onEnd(ev) {
            if (ev.animationName !== 'lplanSwapIn') return;
            el.classList.remove('lplan-swap-enter');
            el.removeEventListener('animationend', onEnd);
        }
        el.addEventListener('animationend', onEnd);
    }

    document.addEventListener('DOMContentLoaded', function () {
        progressEl = document.getElementById('lplan-nav-progress');
    });

    document.addEventListener(
        'click',
        function (e) {
            var a = e.target && e.target.closest ? e.target.closest('a[href]') : null;
            if (!shouldShowProgressForAnchor(a, e)) return;
            showProgress();
        },
        true
    );

    window.addEventListener('pageshow', function () {
        hideProgress();
    });

    window.addEventListener('load', function () {
        hideProgress();
    });

    document.body.addEventListener('htmx:afterSwap', onHtmxAfterSwap);

    /* Garante que a barra some após pedidos HTMX (ex.: ordenação na lista de relatórios). */
    document.body.addEventListener('htmx:afterRequest', function () {
        hideProgress();
    });
})();
