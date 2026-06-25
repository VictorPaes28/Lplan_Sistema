/**
 * Mapa de Suprimentos — AJAX, undo, atalhos e UX operacional
 */
(function () {
    'use strict';

    var cfg = window.__MAPA_ENG_CFG__ || {};
    var searchDebounce = null;

    function apiBase() {
        return (typeof window.__LPLAN_API_BASE__ === 'string') ? window.__LPLAN_API_BASE__ : '';
    }

    function buildMapaQuery(extra) {
        var form = document.getElementById('filtro-form');
        var params = new URLSearchParams(window.location.search);
        if (form) {
            ['obra', 'categoria', 'local', 'prioridade', 'status', 'pendencia', 'ordenar', 'por_pagina', 'search', 'quick', 'page'].forEach(function (name) {
                var el = form.querySelector('[name="' + name + '"]');
                if (!el) return;
                if (el.value) params.set(name, el.value);
                else params.delete(name);
            });
        }
        if (extra) {
            Object.keys(extra).forEach(function (k) {
                if (extra[k] === null || extra[k] === undefined || extra[k] === '') params.delete(k);
                else params.set(k, String(extra[k]));
            });
        }
        params.delete('scroll_item');
        return params;
    }

    function updateKpis(kpis) {
        if (!kpis) return;
        var map = {
            '': kpis.total,
            'ATRASADO': kpis.atrasados,
            'LEVANTAMENTO': kpis.levantamento,
            'PARCIAL': kpis.parciais,
            'ENTREGUE': kpis.entregues
        };
        document.querySelectorAll('#kpi-container .kpi-clickable').forEach(function (card) {
            var st = card.getAttribute('data-kpi-status') || '';
            var val = card.querySelector('.kpi-valor');
            if (val && map[st] !== undefined) val.textContent = map[st];
        });
    }

    function updateFiltrosAtivos(html) {
        var host = document.getElementById('mapa-filtros-ativos-host');
        if (!host) return;
        host.innerHTML = html || '';
    }

    function syncQuickFilterChips(quickValue) {
        var q = quickValue;
        if (q === undefined || q === null) {
            q = buildMapaQuery().get('quick') || '';
        }
        var hidden = document.getElementById('filtro-quick');
        if (hidden) hidden.value = q;
        document.querySelectorAll('[data-quick-filter]').forEach(function (btn) {
            var active = btn.getAttribute('data-quick-filter') === q;
            btn.classList.toggle('is-active', active);
        });
    }

    function bindPaginationLinks() {
        document.querySelectorAll('.mapa-paginacao a.page-link, .mapa-paginacao a.btn-outline-secondary').forEach(function (a) {
            if (a.dataset.ajaxBound) return;
            a.dataset.ajaxBound = '1';
            a.addEventListener('click', function (e) {
                e.preventDefault();
                try {
                    var u = new URL(a.href, window.location.origin);
                    var page = u.searchParams.get('page');
                    window.refreshMapaFragment({ page: page }, { loadingMessage: 'Carregando página…' });
                } catch (err) {
                    window.location.href = a.href;
                }
            });
        });
    }

    function openNovoLevantamentoPanel() {
        var btn = document.getElementById('btnNovoLevantamento');
        var body = document.getElementById('novoLevantamentoBody');
        if (!btn || !body || typeof bootstrap === 'undefined') return;
        var inst = bootstrap.Collapse.getOrCreateInstance(body, { toggle: false });
        inst.show();
        btn.focus();
    }

    function initEmptyLevantamentoButtons() {
        ['btnEmptyNovoLevantamento', 'btnEmptyNovoLevantamentoMobile'].forEach(function (id) {
            var el = document.getElementById(id);
            if (!el || el.dataset.bound) return;
            el.dataset.bound = '1';
            el.addEventListener('click', function (e) {
                e.preventDefault();
                openNovoLevantamentoPanel();
            });
        });
    }

    function rebindMapaDom() {
        document.querySelectorAll('.input-inline').forEach(function (el) {
            el.classList.add('ghost-input');
        });
        document.querySelectorAll('[data-field="prioridade"]').forEach(function (sel) {
            if (typeof updatePrioridadeClass === 'function') updatePrioridadeClass(sel, sel.value);
        });
        document.querySelectorAll('[data-field], [data-update-url]').forEach(function (campo) {
            if (typeof atualizarEstadoCampo === 'function') atualizarEstadoCampo(campo);
        });
        if (typeof initTooltips === 'function') initTooltips();
        if (typeof initColumnToggle === 'function') initColumnToggle();
        if (typeof initCategoriaToggle === 'function') initCategoriaToggle();
        updateExportLink();
        syncQuickFilterChips();
        bindPaginationLinks();
        initEmptyLevantamentoButtons();
    }

    function updateExportLink() {
        var link = document.getElementById('mapa-export-excel');
        if (!link || !cfg.exportBase) return;
        var params = buildMapaQuery();
        var hidden = [];
        try {
            var saved = JSON.parse(localStorage.getItem('lplan_mapa_colunas') || '{}') || {};
            Object.keys(saved).forEach(function (k) {
                if (saved[k] === false) hidden.push(k);
            });
        } catch (e) { /* ignore */ }
        if (hidden.indexOf('col-prioridade') === -1) {
            var pri = document.querySelector('.tabela-mapa .col-opt.col-obs');
            /* prioridade não está no toggle atual — ok */
        }
        if (hidden.length) params.set('hidden_cols', hidden.join(','));
        link.href = cfg.exportBase + '?' + params.toString();
    }

    window.scrollToItemFlash = function (itemId) {
        if (!itemId) return;
        var alvo = document.querySelector('tr[data-item-id="' + itemId + '"]')
            || document.querySelector('.supply-card[data-item-id="' + itemId + '"]');
        if (!alvo) return;
        setTimeout(function () {
            alvo.scrollIntoView({ behavior: 'smooth', block: 'center' });
            alvo.classList.add('scroll-highlight');
            setTimeout(function () { alvo.classList.remove('scroll-highlight'); }, 2800);
        }, 150);
    };

    window.removeItemFromDom = function (itemId) {
        var row = document.querySelector('tr[data-item-id="' + itemId + '"]');
        var card = document.querySelector('.supply-card[data-item-id="' + itemId + '"]');
        if (row) row.remove();
        if (card) card.remove();
    };

    window.refreshMapaFragment = function (extra, options) {
        options = options || {};
        if (!cfg.fragmentUrl) return Promise.reject(new Error('Fragment URL não configurada'));
        var params = buildMapaQuery(extra);
        if (typeof showMapaTableLoading === 'function') {
            showMapaTableLoading(options.loadingMessage || 'Atualizando mapa…');
        }
        return fetch(apiBase() + cfg.fragmentUrl + '?' + params.toString(), {
            method: 'GET',
            credentials: 'include',
            headers: { 'Accept': 'application/json', 'X-Requested-With': 'XMLHttpRequest' }
        })
            .then(function (r) { return r.json(); })
            .then(function (data) {
                if (!data.success) throw new Error(data.error || 'Erro ao atualizar mapa');
                var tbody = document.querySelector('.tabela-mapa tbody');
                if (tbody) tbody.innerHTML = data.tbody_html;
                var cards = document.querySelector('.supply-cards');
                if (cards) cards.innerHTML = data.mobile_cards_html;
                updateKpis(data.kpis);
                updateFiltrosAtivos(data.filtros_ativos_html);
                syncQuickFilterChips(params.get('quick') || '');
                if (options.pushState !== false) {
                    history.replaceState(null, '', window.location.pathname + '?' + params.toString());
                }
                if (typeof revealMapaTable === 'function') revealMapaTable();
                rebindMapaDom();
                if (options.scrollItemId) window.scrollToItemFlash(options.scrollItemId);
                if (typeof announceMapaStatus === 'function') {
                    announceMapaStatus('Mapa atualizado.');
                }
                return data;
            })
            .catch(function (err) {
                if (typeof revealMapaTable === 'function') revealMapaTable();
                if (typeof showMessage === 'function') {
                    showMessage(err.message || 'Erro ao atualizar mapa.', 'error');
                }
                throw err;
            });
    };

    window.showUndoDeleteToast = function (snapshot, message) {
        if (!snapshot || !cfg.restoreUrl) {
            if (typeof showMessage === 'function') showMessage(message || 'Item excluído.', 'success');
            return;
        }
        var existing = document.querySelector('.mapa-toast-fixo');
        if (existing) existing.remove();
        var id = 'mapa-undo-' + Date.now();
        var div = document.createElement('div');
        div.id = id;
        div.className = 'alert alert-warning alert-dismissible fade show mapa-toast-fixo mapa-toast-undo';
        div.setAttribute('role', 'alert');
        div.innerHTML =
            '<span>' + (message || 'Item excluído.') + '</span> ' +
            '<button type="button" class="btn btn-sm btn-dark ms-2" data-undo-btn>Desfazer</button>' +
            '<button type="button" class="btn-close ms-2" data-bs-dismiss="alert" aria-label="Fechar"></button>';
        document.body.appendChild(div);
        var undone = false;
        var timer = setTimeout(function () {
            var el = document.getElementById(id);
            if (el) el.remove();
        }, 7000);
        div.querySelector('[data-undo-btn]').addEventListener('click', function () {
            if (undone) return;
            undone = true;
            clearTimeout(timer);
            ensureCsrfToken().then(function (token) {
                if (!token) {
                    showMessage('Sessão inválida.', 'error');
                    return;
                }
                fetch(apiBase() + cfg.restoreUrl, {
                    method: 'POST',
                    credentials: 'include',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': token
                    },
                    body: JSON.stringify({ undo_snapshot: snapshot })
                })
                    .then(function (r) { return r.json(); })
                    .then(function (data) {
                        div.remove();
                        if (data.success) {
                            window.refreshMapaFragment({}, { scrollItemId: data.item_id, loadingMessage: 'Restaurando item…' })
                                .then(function () {
                                    showMessage(data.message || 'Item restaurado.', 'success');
                                });
                        } else {
                            showMessage(data.error || 'Erro ao restaurar.', 'error');
                        }
                    })
                    .catch(function () {
                        showMessage('Erro ao restaurar item.', 'error');
                    });
            });
        });
    };

    function validateFieldBeforeSave(input) {
        if (!input) return null;
        var field = input.getAttribute('data-field');
        var value = (input.value || '').trim();
        if (field === 'quantidade_planejada') {
            var row = input.closest('tr[data-item-id]');
            var alocado = row ? parseFloat(String(row.getAttribute('data-alocado') || '0').replace(',', '.')) : 0;
            if (!alocado && row) {
                var exec = row.querySelector('.exec-alocado');
                if (exec) alocado = parseFloat(String(exec.textContent || '0').replace(/\./g, '').replace(',', '.')) || 0;
            }
            var plan = parseFloat(String(value).replace(',', '.')) || 0;
            if (plan > 0 && alocado > 0 && plan < alocado) {
                return 'Planejado não pode ser menor que o já alocado (' + alocado + ').';
            }
            if (plan <= 0) return 'Informe quantidade planejada maior que zero.';
        }
        if (field === 'prazo_necessidade' && value) {
            var d = new Date(value + 'T12:00:00');
            if (isNaN(d.getTime())) return 'Data de prazo inválida.';
        }
        return null;
    }

    window.validateMapaFieldBeforeSave = validateFieldBeforeSave;

    function initAjaxFilters() {
        var form = document.getElementById('filtro-form');
        var search = document.getElementById('search');
        if (!form) return;

        form.addEventListener('submit', function (e) {
            e.preventDefault();
            window.refreshMapaFragment({}, { loadingMessage: 'Aplicando filtros…' });
        });

        if (search) {
            search.addEventListener('input', function () {
                clearTimeout(searchDebounce);
                searchDebounce = setTimeout(function () {
                    window.refreshMapaFragment({ page: null }, { loadingMessage: 'Buscando…' });
                }, 450);
            });
        }

        bindPaginationLinks();
    }

    function initQuickFilters() {
        document.querySelectorAll('[data-quick-filter]').forEach(function (btn) {
            btn.addEventListener('click', function () {
                var q = btn.getAttribute('data-quick-filter');
                var current = buildMapaQuery().get('quick');
                var next = (current === q) ? null : q;
                var hidden = document.getElementById('filtro-quick');
                if (hidden) hidden.value = next || '';
                syncQuickFilterChips(next || '');
                window.refreshMapaFragment({ quick: next, page: null }, { loadingMessage: 'Filtrando…' });
            });
        });
    }

    function initFiltroChipsAjax() {
        document.addEventListener('click', function (e) {
            var chip = e.target.closest('.mapa-chip-filtro');
            if (!chip) return;
            e.preventDefault();
            var param = chip.getAttribute('data-remove-param');
            if (!param) return;
            var extra = {};
            extra[param] = null;
            extra.page = null;
            window.refreshMapaFragment(extra, { loadingMessage: 'Atualizando…' });
        });
    }

    function initKpiAjax() {
        var container = document.getElementById('kpi-container');
        var form = document.getElementById('filtro-form');
        if (!container || !form) return;
        container.querySelectorAll('.kpi-clickable').forEach(function (card) {
            card.addEventListener('click', function () {
                var status = card.getAttribute('data-kpi-status') || '';
                var statusInput = form.querySelector('[name="status"]');
                if (statusInput) statusInput.value = status;
                else {
                    var hidden = document.createElement('input');
                    hidden.type = 'hidden';
                    hidden.name = 'status';
                    hidden.value = status;
                    form.appendChild(hidden);
                }
                window.refreshMapaFragment({ page: null, status: status }, { loadingMessage: 'Filtrando…' });
            });
        });
    }

    function initKeyboardShortcuts() {
        document.addEventListener('keydown', function (e) {
            var input = e.target.closest('.input-inline[data-update-url]');
            if (e.key === 'Escape' && input) {
                var initial = input.getAttribute('data-initial-value') || '';
                input.value = initial;
                input.blur();
                input.classList.remove('field-error', 'field-saving');
                if (typeof clearFieldErrorMessage === 'function') clearFieldErrorMessage(input);
                e.preventDefault();
                return;
            }
            if (e.key === '?' && !e.target.matches('input, textarea, select')) {
                var modal = document.getElementById('modalMapaAtalhos');
                if (modal && typeof bootstrap !== 'undefined') {
                    bootstrap.Modal.getOrCreateInstance(modal).show();
                    e.preventDefault();
                }
            }
        });
    }

    function initObraFocusEmpty() {
        if (document.querySelector('.mapa-empty-obra')) {
            var sel = document.getElementById('obra') || document.querySelector('[name="obra"]');
            if (sel) setTimeout(function () { sel.focus(); }, 300);
        }
    }

    function initScrollItemOnLoad() {
        var scrollId = new URLSearchParams(window.location.search).get('scroll_item');
        if (!scrollId && cfg.scrollItem) scrollId = String(cfg.scrollItem);
        if (scrollId) window.scrollToItemFlash(scrollId);
        try {
            var params = new URLSearchParams(window.location.search);
            if (params.has('scroll_item')) {
                params.delete('scroll_item');
                history.replaceState(null, '', window.location.pathname + (params.toString() ? '?' + params.toString() : ''));
            }
        } catch (e) { /* ignore */ }
    }

    document.addEventListener('DOMContentLoaded', function () {
        if (!document.querySelector('.page-mapa-suprimentos')) return;
        initAjaxFilters();
        initQuickFilters();
        initFiltroChipsAjax();
        initKpiAjax();
        initKeyboardShortcuts();
        initObraFocusEmpty();
        initScrollItemOnLoad();
        initEmptyLevantamentoButtons();
        updateExportLink();
    });
})();
