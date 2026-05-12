/**
 * Listagem de usuários: popovers (obras/permissões) e menu de ações (⋯).
 */
(function () {
    'use strict';

    var openPopover = null;
    var openMenu = null;

    function clearFloatingStyles(panel) {
        panel.style.position = '';
        panel.style.left = '';
        panel.style.top = '';
        panel.style.right = '';
        panel.style.maxWidth = '';
        panel.style.zIndex = '';
        panel.style.visibility = '';
    }

    /**
     * `position: fixed` dentro de <td> / tabela não segue o viewport de forma confiável.
     * O `.main-content-wrapper` também pode ter animação com `transform`, criando novo
     * contexto de posicionamento. Anexamos o painel ao <body> só enquanto estiver aberto.
     */
    function portalPanelToBody(panel) {
        if (!panel.parentNode || panel.parentNode === document.body) {
            return;
        }
        if (!panel._listUsersPh) {
            panel._listUsersPh = document.createComment('list-users-panel-anchor');
            panel.parentNode.insertBefore(panel._listUsersPh, panel);
        }
        document.body.appendChild(panel);
    }

    function restorePanelToTable(panel) {
        var ph = panel._listUsersPh;
        clearFloatingStyles(panel);
        if (ph && ph.parentNode) {
            ph.parentNode.insertBefore(panel, ph);
        }
    }

    function closeOpenPopover() {
        if (!openPopover) return;
        openPopover.panel.hidden = true;
        restorePanelToTable(openPopover.panel);
        openPopover.btn.setAttribute('aria-expanded', 'false');
        openPopover = null;
    }

    function closeOpenMenu() {
        if (!openMenu) return;
        openMenu.panel.hidden = true;
        restorePanelToTable(openMenu.panel);
        openMenu.btn.setAttribute('aria-expanded', 'false');
        openMenu = null;
    }

    function positionAnchored(panel, trigger) {
        portalPanelToBody(panel);

        var gutter = 6;
        var maxW = 320;

        panel.style.position = 'fixed';
        panel.style.zIndex = '10060';
        panel.style.maxWidth = maxW + 'px';
        panel.hidden = false;

        var measureAndPlace = function () {
            var rr = trigger.getBoundingClientRect();
            var pw = panel.offsetWidth || maxW;
            var left = rr.left;
            if (left + pw + gutter > window.innerWidth) {
                left = Math.max(gutter, window.innerWidth - pw - gutter);
            }
            var top = rr.bottom + gutter;
            var ph = panel.offsetHeight;
            if (top + ph + gutter > window.innerHeight && rr.top > ph + gutter) {
                top = Math.max(gutter, rr.top - ph - gutter);
            }
            panel.style.left = left + 'px';
            panel.style.top = top + 'px';
        };

        requestAnimationFrame(function () {
            requestAnimationFrame(measureAndPlace);
        });
    }

    function init() {
        var root = document.querySelector('.list-users');
        if (!root) return;

        root.addEventListener('click', function (e) {
            var popBtn = e.target.closest('[data-list-users-popover-toggle]');
            if (popBtn) {
                var panelId = popBtn.getAttribute('aria-controls');
                var panel = panelId ? document.getElementById(panelId) : null;
                if (!panel) return;
                var wasOpen = !panel.hidden;
                closeOpenMenu();
                closeOpenPopover();
                if (wasOpen) {
                    if (!panel.hidden || panel.parentNode === document.body) {
                        panel.hidden = true;
                        restorePanelToTable(panel);
                    }
                    popBtn.setAttribute('aria-expanded', 'false');
                    if (openPopover && openPopover.panel === panel) {
                        openPopover = null;
                    }
                    return;
                }
                popBtn.setAttribute('aria-expanded', 'true');
                positionAnchored(panel, popBtn);
                openPopover = { btn: popBtn, panel: panel };
                return;
            }

            var menuBtn = e.target.closest('[data-list-users-menu-toggle]');
            if (menuBtn) {
                var mId = menuBtn.getAttribute('aria-controls');
                var mPanel = mId ? document.getElementById(mId) : null;
                if (!mPanel) return;
                var menuWasOpen = !mPanel.hidden;
                closeOpenPopover();
                closeOpenMenu();
                if (menuWasOpen) {
                    if (!mPanel.hidden || mPanel.parentNode === document.body) {
                        mPanel.hidden = true;
                        restorePanelToTable(mPanel);
                    }
                    menuBtn.setAttribute('aria-expanded', 'false');
                    if (openMenu && openMenu.panel === mPanel) {
                        openMenu = null;
                    }
                    return;
                }
                menuBtn.setAttribute('aria-expanded', 'true');
                positionAnchored(mPanel, menuBtn);
                openMenu = { btn: menuBtn, panel: mPanel };
            }
        });

        document.addEventListener(
            'click',
            function (e) {
                if (e.target.closest('[data-list-users-popover-toggle]')) return;
                if (e.target.closest('.list-users-popover-panel')) return;
                if (e.target.closest('[data-list-users-menu-toggle]')) return;
                if (e.target.closest('.list-users-action-menu-panel')) return;
                closeOpenPopover();
                closeOpenMenu();
            },
            true
        );

        document.addEventListener('keydown', function (e) {
            if (e.key === 'Escape') {
                closeOpenPopover();
                closeOpenMenu();
            }
        });

        window.addEventListener('resize', function () {
            closeOpenPopover();
            closeOpenMenu();
        });
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
