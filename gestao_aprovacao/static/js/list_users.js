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
                if (e.target.closest('[data-list-users-delete-open]')) return;
                if (e.target.closest('#list-users-delete-modal')) return;
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

        initDeleteModal(root);
    }

    function initDeleteModal(root) {
        var modal = document.getElementById('list-users-delete-modal');
        if (!modal) return;

        var form = document.getElementById('list-users-delete-form');
        var elName = document.getElementById('list-users-delete-name');
        var elUser = document.getElementById('list-users-delete-username');
        var elEmail = document.getElementById('list-users-delete-email');
        var elGroups = document.getElementById('list-users-delete-groups');
        var elBlocked = document.getElementById('list-users-delete-blocked');
        var elBlockedList = document.getElementById('list-users-delete-blocked-list');
        var elWarning = document.getElementById('list-users-delete-warning');
        var elSubmit = document.getElementById('list-users-delete-submit');
        var pageCfg = window.LIST_USERS_PAGE || {};

        function displayValue(val, fallback) {
            var s = (val || '').trim();
            return s || fallback || '—';
        }

        function setBloqueios(raw) {
            var items = [];
            if (raw) {
                items = String(raw)
                    .split('|')
                    .map(function (s) {
                        return s.trim();
                    })
                    .filter(Boolean);
            }
            elBlockedList.innerHTML = '';
            var seen = {};
            items.forEach(function (text) {
                if (seen[text]) return;
                seen[text] = true;
                var li = document.createElement('li');
                li.textContent = text;
                elBlockedList.appendChild(li);
            });
            var blocked = items.length > 0;
            elBlocked.hidden = !blocked;
            elWarning.hidden = blocked;
            elSubmit.disabled = blocked;
        }

        function openFromTrigger(btn) {
            if (!btn || !form) return;
            closeOpenPopover();
            closeOpenMenu();
            form.action = btn.getAttribute('data-delete-url') || '';
            elName.textContent = displayValue(btn.getAttribute('data-full-name'), btn.getAttribute('data-username'));
            elUser.textContent = displayValue(btn.getAttribute('data-username'), '—');
            elEmail.textContent = displayValue(btn.getAttribute('data-email'), '—');
            elGroups.textContent = displayValue(btn.getAttribute('data-groups'), 'Sem grupo');
            setBloqueios(btn.getAttribute('data-bloqueios'));
            modal.hidden = false;
            document.body.style.overflow = 'hidden';
            elSubmit.focus();
        }

        function closeModal() {
            modal.hidden = true;
            document.body.style.overflow = '';
        }

        /* Abrir exclusão: menu pode estar em document.body */
        document.addEventListener('click', function (e) {
            var openBtn = e.target.closest('[data-list-users-delete-open]');
            if (!openBtn) return;
            e.preventDefault();
            closeOpenMenu();
            closeOpenPopover();
            openFromTrigger(openBtn);
        });

        /* Fechar: botões ficam dentro do painel — listener no próprio modal */
        modal.addEventListener('click', function (e) {
            if (e.target === modal) {
                closeModal();
                return;
            }
            if (e.target.closest('[data-list-users-delete-close]')) {
                e.preventDefault();
                closeModal();
            }
        });

        document.addEventListener('keydown', function (e) {
            if (e.key === 'Escape' && !modal.hidden) {
                closeModal();
            }
        });

        function stripOpenDeleteFromUrl() {
            try {
                var u = new URL(window.location.href);
                if (!u.searchParams.has('open_delete')) return;
                u.searchParams.delete('open_delete');
                var qs = u.searchParams.toString();
                window.history.replaceState({}, '', u.pathname + (qs ? '?' + qs : ''));
            } catch (err) {
                /* ignore */
            }
        }

        function openByUserId(userId) {
            var btn = root.querySelector('[data-list-users-delete-open][data-user-id="' + userId + '"]');
            if (btn) {
                openFromTrigger(btn);
                stripOpenDeleteFromUrl();
                return;
            }
            var previewBase = root.querySelector('[data-list-users-delete-open]');
            if (!previewBase) return;
            var sampleUrl = previewBase.getAttribute('data-delete-url') || '';
            var deleteUrl = sampleUrl.replace(/(\/usuarios\/)\d+(\/)/, '$1' + userId + '$2');
            var previewUrl = deleteUrl + (pageCfg.previewSuffix || '?preview=1');
            fetch(previewUrl, {
                headers: { Accept: 'application/json' },
                credentials: 'same-origin',
            })
                .then(function (r) {
                    return r.json();
                })
                .then(function (data) {
                    if (!data || !data.ok) return;
                    var fake = document.createElement('button');
                    fake.setAttribute('data-delete-url', deleteUrl);
                    fake.setAttribute('data-username', data.username || '');
                    fake.setAttribute('data-full-name', data.full_name || '');
                    fake.setAttribute('data-email', data.email || '');
                    fake.setAttribute('data-groups', (data.groups || []).join(', '));
                    fake.setAttribute('data-bloqueios', (data.bloqueios || []).join('|'));
                    openFromTrigger(fake);
                    stripOpenDeleteFromUrl();
                })
                .catch(function () {
                    stripOpenDeleteFromUrl();
                });
        }

        if (pageCfg.openDeleteUserId) {
            openByUserId(String(pageCfg.openDeleteUserId));
        }
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
