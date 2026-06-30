// SupplyMap - JavaScript principal
// Versão: deve bater com window.__LPLAN_SUPPLYMAP_VER__ no base_mapa
var __LPLAN_JS_VER__ = '20';

var _csrfReadyPromise = null;
var FIELD_SPINNER_DELAY_MS = 250;
var _fieldSpinnerTimers = new WeakMap();
var _fieldSavedTimers = new WeakMap();

document.addEventListener('DOMContentLoaded', function() {
    console.warn('[LPLAN] SupplyMap v' + __LPLAN_JS_VER__ + ' carregado. Se não aparecer "v11" em produção, o JS está em cache ou collectstatic não foi executado.');
    _csrfReadyPromise = getCsrfTokenAsync().then(function(t) { return t || getCsrfToken(); });
    // Diagnóstico CSRF no F12 (Console): filtrar por [LPLAN]
    try {
        var w = typeof window.__LPLAN_CSRF_TOKEN__ === 'string' && window.__LPLAN_CSRF_TOKEN__ ? 'sim' : 'não';
        var wEmpty = (typeof window.__LPLAN_CSRF_TOKEN__ === 'string' && window.__LPLAN_CSRF_TOKEN__ === '');
        var b = document.body && document.body.getAttribute('data-csrf-token') ? 'sim' : 'não';
        var m = document.querySelector('meta[name="csrf-token"]');
        var mVal = m && m.getAttribute('content') ? 'sim' : 'não';
        var u = typeof window.__LPLAN_CSRF_TOKEN_URL__ === 'string' && window.__LPLAN_CSRF_TOKEN_URL__ ? window.__LPLAN_CSRF_TOKEN_URL__ : '(não definido)';
        var origin = typeof window.location !== 'undefined' ? window.location.origin : '(não disponível)';
        var tokenUrlAbs = (u && u.indexOf('http') !== 0 && origin !== '(não disponível)') ? (origin.replace(/\/$/, '') + (u.indexOf('/') === 0 ? u : '/' + u)) : u;
        console.warn('[LPLAN] Diagnóstico ao carregar: token em window=', w, wEmpty ? '(string vazia!)' : '', 'body=', b, 'meta=', mVal, '| URL API=', u, '| origin=', origin, '| fetch usará:', tokenUrlAbs);
    } catch (e) {}

    var inits = [
        { name: 'initInlineEdit', fn: initInlineEdit },
        { name: 'initModals', fn: initModals },
        { name: 'initFiltros', fn: initFiltros },
        { name: 'initFiltroChips', fn: initFiltroChips },
        { name: 'initKpiFilters', fn: initKpiFilters },
        { name: 'initColumnToggle', fn: initColumnToggle },
        { name: 'initGridKeyboardNav', fn: initGridKeyboardNav },
        { name: 'initTooltips', fn: initTooltips },
        { name: 'initCategoriaToggle', fn: initCategoriaToggle },
        { name: 'initCriarItem', fn: initCriarItem },
        { name: 'initDeleteItem', fn: initDeleteItem },
        { name: 'initDuplicateItem', fn: initDuplicateItem },
        { name: 'initMapaTableLoading', fn: initMapaTableLoading },
        { name: 'initMapaNavigationLoading', fn: initMapaNavigationLoading }
    ];
    inits.forEach(function(init) {
        try {
            init.fn();
        } catch (err) {
            console.error('[LPLAN] Erro em ' + init.name + ':', err && err.message ? err.message : err);
        }
    });
});

// Edição inline (HTMX ou fetch simples)
function initInlineEdit() {
    const table = document.querySelector('.tabela-mapa');
    if (!table) return;

    table.querySelectorAll('.input-inline[data-field="prioridade"]').forEach(function(input) {
        updatePrioridadeClass(input, input.value);
    });

    table.addEventListener('focusin', function(e) {
        const input = e.target.closest('.input-inline[data-update-url]');
        if (input) {
            input.setAttribute('data-initial-value', input.value || '');
            input.classList.remove('field-error');
            clearFieldErrorMessage(input);
        }
    });

    table.addEventListener('change', function(e) {
        const input = e.target.closest('.input-inline[data-update-url]');
        if (input && input.tagName === 'SELECT') {
            handleInlineFieldSave(input);
        }
    });

    table.addEventListener('blur', function(e) {
        const input = e.target.closest('.input-inline[data-update-url]');
        if (input && input.tagName !== 'SELECT') {
            handleInlineFieldSave(input);
        }
    }, true);
}

function handleInlineFieldSave(input) {
    const url = input.getAttribute('data-update-url');
    const field = input.getAttribute('data-field');
    const value = input.value;
    const itemId = input.getAttribute('data-item-id');

    if (!url || !field || !itemId) return;

    const initial = input.getAttribute('data-initial-value') || '';
    if (String(value).trim() === String(initial).trim()) {
        return;
    }

    if (field === 'prioridade') {
        updatePrioridadeClass(input, value);
    }

    if (typeof validateMapaFieldBeforeSave === 'function') {
        var validationErr = validateMapaFieldBeforeSave(input);
        if (validationErr) {
            setFieldError(input, validationErr);
            return;
        }
    }

    updateItemField(itemId, field, value, url, input);
}

// Atualizar classe visual do select de prioridade
function updatePrioridadeClass(selectElement, value) {
    // Remover todas as classes de prioridade
    selectElement.classList.remove('prioridade-urgente', 'prioridade-alta', 'prioridade-media', 'prioridade-baixa');
    
    // Adicionar nova classe baseada no valor
    const classMap = {
        'URGENTE': 'prioridade-urgente',
        'ALTA': 'prioridade-alta',
        'MEDIA': 'prioridade-media',
        'BAIXA': 'prioridade-baixa'
    };
    
    if (classMap[value]) {
        selectElement.classList.add(classMap[value]);
    }
}

function ensureCsrfToken() {
    if (_csrfReadyPromise) {
        return _csrfReadyPromise.then(function(t) { return t || getCsrfToken(); });
    }
    return getCsrfTokenAsync().then(function(t) { return t || getCsrfToken(); });
}

function getFieldCell(inputEl) {
    if (!inputEl) return null;
    var td = inputEl.closest('td');
    if (td && !td.classList.contains('field-cell-wrap')) {
        td.classList.add('field-cell-wrap');
    }
    return td;
}

function clearFieldErrorMessage(inputEl) {
    if (!inputEl) return;
    var td = inputEl.closest('td');
    if (td) {
        var err = td.querySelector('.mapa-field-error');
        if (err) err.remove();
    }
    inputEl.removeAttribute('aria-invalid');
    inputEl.removeAttribute('aria-describedby');
}

function clearFieldTimers(inputEl) {
    var spinnerTimer = _fieldSpinnerTimers.get(inputEl);
    if (spinnerTimer) {
        clearTimeout(spinnerTimer);
        _fieldSpinnerTimers.delete(inputEl);
    }
    var savedTimer = _fieldSavedTimers.get(inputEl);
    if (savedTimer) {
        clearTimeout(savedTimer);
        _fieldSavedTimers.delete(inputEl);
    }
}

function setFieldSaving(inputEl, saving) {
    if (!inputEl) return;
    var td = getFieldCell(inputEl);
    if (saving) {
        inputEl.classList.remove('field-saved', 'field-error');
        clearFieldErrorMessage(inputEl);
        if (td) td.classList.remove('field-cell-saved');
        clearFieldTimers(inputEl);
        inputEl.classList.add('field-saving');
        if (td) td.classList.add('field-cell-saving');
        var t = setTimeout(function() {
            if (inputEl.classList.contains('field-saving') && td) {
                td.classList.add('field-cell-spinner');
            }
        }, FIELD_SPINNER_DELAY_MS);
        _fieldSpinnerTimers.set(inputEl, t);
    } else {
        inputEl.classList.remove('field-saving');
        if (td) {
            td.classList.remove('field-cell-saving', 'field-cell-spinner');
        }
        clearFieldTimers(inputEl);
    }
}

function setFieldSaved(inputEl) {
    if (!inputEl) return;
    inputEl.classList.remove('field-saving', 'field-error');
    clearFieldErrorMessage(inputEl);
    var td = getFieldCell(inputEl);
    if (td) {
        td.classList.remove('field-cell-saving', 'field-cell-spinner');
    }
    clearFieldTimers(inputEl);
    inputEl.classList.add('field-saved');
    if (td) td.classList.add('field-cell-saved');
    var t = setTimeout(function() {
        inputEl.classList.remove('field-saved');
        if (td) td.classList.remove('field-cell-saved');
    }, 1800);
    _fieldSavedTimers.set(inputEl, t);
}

function setFieldError(inputEl, message) {
    if (!inputEl) return;
    setFieldSaving(inputEl, false);
    inputEl.classList.remove('field-saved');
    var td = getFieldCell(inputEl);
    if (td) td.classList.remove('field-cell-saved');
    inputEl.classList.add('field-error');
    if (!td) return;
    var errId = 'mapa-err-' + (inputEl.getAttribute('data-item-id') || 'x') + '-' + (inputEl.getAttribute('data-field') || 'f');
    var err = td.querySelector('.mapa-field-error');
    if (!err) {
        err = document.createElement('div');
        err.className = 'mapa-field-error';
        err.id = errId;
        td.appendChild(err);
    }
    err.textContent = message || 'Não foi possível salvar.';
    inputEl.setAttribute('aria-invalid', 'true');
    inputEl.setAttribute('aria-describedby', errId);
    announceMapaStatus(message || 'Erro ao salvar campo.');
}

function announceMapaStatus(msg) {
    var el = document.getElementById('mapa-table-status');
    if (!el || !msg) return;
    el.textContent = '';
    setTimeout(function() { el.textContent = msg; }, 20);
}

function showMapaTableLoading(message) {
    var shell = document.getElementById('mapa-table-shell');
    if (!shell) return;
    shell.classList.add('mapa-table-navigating');
    shell.setAttribute('aria-busy', 'true');
    var prog = document.getElementById('mapa-filter-progress');
    if (prog) {
        prog.hidden = false;
        prog.removeAttribute('aria-hidden');
    }
    if (message) announceMapaStatus(message);
}

function revealMapaTable() {
    var shell = document.getElementById('mapa-table-shell');
    if (!shell) return;
    shell.classList.remove('mapa-table-loading-init', 'mapa-table-navigating');
    shell.setAttribute('aria-busy', 'false');
    var prog = document.getElementById('mapa-filter-progress');
    if (prog) {
        prog.hidden = true;
        prog.setAttribute('aria-hidden', 'true');
    }
}

function initMapaTableLoading() {
    if (!document.querySelector('.page-mapa-suprimentos')) return;
    requestAnimationFrame(function() {
        requestAnimationFrame(function() {
            revealMapaTable();
            var count = document.querySelectorAll('.tabela-mapa tbody tr.linha-item-mapa').length;
            if (count) {
                announceMapaStatus('Mapa carregado com ' + count + ' itens.');
            }
        });
    });
}

function initMapaNavigationLoading() {
    if (!document.querySelector('.page-mapa-suprimentos')) return;
    var form = document.getElementById('filtro-form');
    if (form) {
        form.addEventListener('submit', function() {
            showMapaTableLoading('Atualizando mapa…');
        });
    }
    document.querySelectorAll('.mapa-paginacao a.page-link').forEach(function(a) {
        a.addEventListener('click', function() {
            showMapaTableLoading('Carregando página…');
        });
    });
}

function markInputSaved(inputEl, value) {
    if (!inputEl) return;
    var v = value != null ? String(value) : (inputEl.value || '');
    inputEl.setAttribute('data-initial-value', v);
}

function syncObraQueryParam(obraId) {
    if (!obraId) return;
    try {
        var params = new URLSearchParams(window.location.search);
        if (params.get('obra') === String(obraId)) return;
        params.set('obra', obraId);
        var qs = params.toString();
        var next = window.location.pathname + (qs ? '?' + qs : '');
        history.replaceState(null, '', next);
    } catch (e) { /* ignore */ }
}

function escapeHtml(text) {
    return String(text || '')
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;');
}

var MAPA_STATUS_ROW_CLASSES = [
    'status-branco', 'status-vermelho', 'status-amarelo', 'status-laranja',
    'status-verde', 'status-atrasado', 'status-azul'
];
var MAPA_BADGE_CLASSES = [
    'badge-branco', 'badge-vermelho', 'badge-amarelo', 'badge-laranja',
    'badge-verde', 'badge-atrasado', 'badge-azul'
];

function statusIconHtml(statusEtapa, isAtrasado) {
    if (isAtrasado) return '<i class="bi bi-clock-history"></i>';
    var s = String(statusEtapa || '');
    if (s.indexOf('ENTREGUE') >= 0) return '<i class="bi bi-check-circle"></i>';
    if (s.indexOf('PARCIAL') >= 0 || s.indexOf('AGUARDANDO ENTREGA') >= 0) {
        return '<i class="bi bi-hourglass-split"></i>';
    }
    if (s.indexOf('LEVANTAMENTO') >= 0) return '<i class="bi bi-file-earmark-text"></i>';
    if (s.indexOf('SOLICITACAO') >= 0 || s.indexOf('COMPRA') >= 0) return '<i class="bi bi-cart-plus"></i>';
    return '';
}

function badgeClassForStatus(statusCss) {
    var map = {
        'status-branco': 'badge-branco',
        'status-vermelho': 'badge-vermelho',
        'status-amarelo': 'badge-amarelo',
        'status-laranja': 'badge-laranja',
        'status-verde': 'badge-verde',
        'status-atrasado': 'badge-atrasado',
        'status-azul': 'badge-azul'
    };
    return map[statusCss] || 'badge-branco';
}

function formatStatusEtapaCurto(statusEtapa) {
    var s = String(statusEtapa || '').toUpperCase();
    if (!s) return '—';
    if (s.indexOf('LEVANTAMENTO') >= 0) return 'Levant.';
    if (s.indexOf('PARCIAL') >= 0) return 'Parcial';
    if (s.indexOf('ENTREGUE') >= 0) return 'Entregue';
    if (s.indexOf('AGUARDANDO ENTREGA') >= 0) return 'Aguard.';
    if (s.length > 14) return s.slice(0, 12).replace(/\s+$/, '') + '…';
    return statusEtapa;
}

function applyCardPatch(itemId, patch) {
    if (!patch) return;
    var card = document.querySelector('.supply-card[data-item-id="' + itemId + '"]');
    if (!card) return;

    var unidade = patch.unidade || '';
    var saldoRaw = patch.saldo_raw || '0';
    var saldoNum = parseFloat(String(saldoRaw).replace(',', '.')) || 0;

    if (patch.saldo_a_alocar !== undefined) {
        card.querySelectorAll('.supply-card-field').forEach(function (field) {
            var lbl = field.querySelector('.supply-card-label');
            var val = field.querySelector('.supply-card-value');
            if (!lbl || !val) return;
            if ((lbl.textContent || '').trim().toLowerCase() === 'saldo') {
                val.textContent = (patch.saldo_a_alocar || '0,00') + ' ' + unidade;
            }
        });
    }

    if (patch.percentual_pct !== undefined) {
        var fill = card.querySelector('.supply-card-progress-fill');
        var txt = card.querySelector('.supply-card-progress-text');
        if (fill) fill.style.width = patch.percentual_pct + '%';
        if (txt) txt.textContent = patch.percentual_pct + '%';
    }

    var btn = card.querySelector('.btn-alocar');
    if (btn) {
        btn.setAttribute('data-saldo', saldoRaw);
        btn.setAttribute('data-alocado', patch.alocado_raw || '0');
        if (patch.planejado_raw !== undefined) {
            btn.setAttribute('data-planejado', patch.planejado_raw);
        }
        btn.setAttribute('data-unidade', unidade);
        btn.setAttribute('title', saldoNum > 0 ? 'Alocar' : 'Revisar alocações');
        btn.innerHTML = '<i class="bi ' + (saldoNum > 0 ? 'bi-plus-lg' : 'bi-sliders') + '"></i>';
    }

    if (patch.status_etapa !== undefined) {
        card.setAttribute('data-status-etapa', patch.status_etapa);
        var cardBadge = card.querySelector('.supply-card-badge');
        if (cardBadge && patch.status_etapa) {
            cardBadge.textContent = patch.status_etapa;
        }
    }
}

function applyRowPatch(itemId, patch) {
    if (!patch) return;
    applyCardPatch(itemId, patch);
    var row = document.querySelector('tr[data-item-id="' + itemId + '"]');
    if (!row) return;

    var codInp = row.querySelector('[data-field="insumo_codigo"]');
    if (codInp && patch.insumo_codigo && patch.insumo_codigo.indexOf('SM-LEV-') !== 0) {
        codInp.value = patch.insumo_codigo;
        markInputSaved(codInp, patch.insumo_codigo);
    }

    if (patch.quantidade_planejada !== undefined || patch.quantidade_alocada !== undefined) {
        var progressCell = row.querySelector('.celula-progresso');
        var saldoCell = row.querySelector('td.input-readonly');
        var unidade = patch.unidade || '';
        var planejadoRaw = patch.planejado_raw || patch.quantidade_planejada_raw || '';
        var planejadoNum = parseFloat(String(planejadoRaw).replace(',', '.')) || 0;
        if (progressCell) {
            if (patch.progress_title) {
                progressCell.setAttribute('title', patch.progress_title);
                progressCell.setAttribute('data-bs-original-title', patch.progress_title);
            }
            var saldoRaw = patch.saldo_raw || '0';
            var alocadoRaw = patch.alocado_raw || '0';
            var saldoNum = parseFloat(String(saldoRaw).replace(',', '.')) || 0;
            var btnIcon = saldoNum > 0 ? 'bi-plus-lg' : 'bi-sliders';
            var btnTitle = saldoNum > 0
                ? ('Alocar até ' + escapeHtml(patch.saldo_a_alocar || saldoRaw) + ' ' + escapeHtml(unidade))
                : 'Ver ou ajustar alocações';
            var planejadoHtml = planejadoNum > 0
                ? '<span class="exec-planejado">' + escapeHtml(patch.quantidade_planejada || '0,00') + '</span>'
                : '<span class="exec-planejado exec-planejado--vazio" title="Informe a qtd. planejada">—</span>';
            progressCell.innerHTML =
                '<div class="exec-cell">' +
                '<span class="exec-numeros">' +
                '<strong class="exec-alocado">' + escapeHtml(patch.quantidade_alocada || '0,00') + '</strong>' +
                '<span class="exec-sep">/</span>' + planejadoHtml +
                '<span class="exec-unidade">' + escapeHtml(unidade) + '</span>' +
                '</span>' +
                '<button type="button" class="btn-alocar-ghost btn-alocar btn-alocar-inline" ' +
                'data-item-id="' + itemId + '" ' +
                'data-saldo="' + escapeHtml(saldoRaw) + '" ' +
                'data-planejado="' + escapeHtml(planejadoRaw) + '" ' +
                'data-unidade="' + escapeHtml(patch.unidade || '') + '" ' +
                'data-alocado="' + escapeHtml(alocadoRaw) + '" ' +
                'title="' + btnTitle + '">' +
                '<i class="bi ' + btnIcon + '"></i></button>' +
                '</div>';
        }
        if (saldoCell) {
            if (patch.saldo_negativo) {
                var saldoTitle = planejadoNum <= 0
                    ? 'Há alocação sem quantidade planejada.'
                    : 'Alocado maior que o planejado neste local.';
                var saldoValor = planejadoNum <= 0
                    ? '—'
                    : escapeHtml(patch.saldo_local_diferenca || '0.00');
                saldoCell.innerHTML =
                    '<span class="saldo-aviso" title="' + saldoTitle + '">' +
                    '<i class="bi bi-exclamation-circle"></i></span> ' +
                    '<span class="saldo-valor saldo-valor--alert">' + saldoValor + '</span> ' +
                    '<span class="saldo-und">' + escapeHtml(unidade) + '</span>';
            } else {
                saldoCell.innerHTML =
                    '<span class="saldo-valor">' + escapeHtml(patch.saldo_a_alocar || '0,00') + '</span> ' +
                    '<span class="saldo-und">' + escapeHtml(unidade) + '</span>';
            }
        }
    }

    if (patch.status_css) {
        updateRowStatus(itemId, patch.status_css);
    }
    if (patch.status_etapa) {
        row.setAttribute('data-status-etapa', patch.status_etapa);
        var badge = row.querySelector('.badge-status');
        if (badge) {
            MAPA_BADGE_CLASSES.forEach(function(c) { badge.classList.remove(c); });
            badge.classList.add(badgeClassForStatus(patch.status_css || ''));
            var iconHtml = statusIconHtml(patch.status_etapa, patch.is_atrasado);
            var label = formatStatusEtapaCurto(patch.status_etapa);
            badge.innerHTML = iconHtml + (iconHtml ? ' ' : '') + escapeHtml(label);
        }
    }
    if (patch.is_atrasado) {
        row.setAttribute('data-atrasado', 'true');
        row.classList.add('linha-atrasada');
    } else {
        row.removeAttribute('data-atrasado');
        row.classList.remove('linha-atrasada');
    }
}

// Atualizar campo via AJAX (sem recarregar a página — fluxo fluido como no mapa de controle)
function updateItemField(itemId, field, value, url, inputEl) {
    ensureCsrfToken().then(function(csrftoken) {
        if (!csrftoken) {
            _logCsrf('Sessão inválida: token não obtido (nem async nem retry getCsrfToken). Verifique os logs [LPLAN] acima.');
            showMessage('Sessão inválida. Recarregue a página e tente novamente.', 'error');
            return;
        }
        setFieldSaving(inputEl, true);
        fetch(url, {
            method: 'POST',
            credentials: 'include',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': csrftoken
            },
            body: JSON.stringify({
                item_id: itemId,
                field: field,
                value: value
            })
        })
        .then(function(response) {
            return response.text().then(function(text) {
                var data;
                try { data = text ? JSON.parse(text) : {}; } catch (e) { data = {}; }
                if (!response.ok) {
                    var msg = (data && data.error) ? data.error : ('Erro ' + response.status);
                    throw { status: response.status, message: msg };
                }
                return data;
            });
        })
        .then(function(data) {
            if (data.success) {
                markInputSaved(inputEl, value);
                setFieldSaved(inputEl);
                showQuietSaveToast();
                if (data.status_css) {
                    updateRowStatus(itemId, data.status_css);
                }
                if (data.row_patch) {
                    applyRowPatch(itemId, data.row_patch);
                }
                if (data.descricao_exibida !== undefined && data.descricao_exibida !== null) {
                    var rowDesc = document.querySelector('tr[data-item-id="' + itemId + '"]');
                    var descInp = rowDesc && rowDesc.querySelector('[data-field="descricao_override"]');
                    if (descInp) {
                        descInp.value = data.descricao_exibida;
                        markInputSaved(descInp, data.descricao_exibida);
                    }
                }
                syncObraQueryParam(data.obra_id);
            } else {
                var errMsg = data.error || 'Erro desconhecido';
                inputEl.value = inputEl.getAttribute('data-initial-value') || '';
                setFieldError(inputEl, errMsg);
            }
        })
        .catch(function(error) {
            _logCsrf('POST catch:', error && error.message ? error.message : error);
            var errMsg = (error && error.message) ? error.message : 'Erro ao salvar. Tente novamente.';
            inputEl.value = inputEl.getAttribute('data-initial-value') || '';
            setFieldError(inputEl, errMsg);
        })
        .finally(function() {
            setFieldSaving(inputEl, false);
        });
    });
}

// Atualizar status visual da linha
function updateRowStatus(itemId, statusCss) {
    const row = document.querySelector('tr[data-item-id="' + itemId + '"]');
    if (!row || !statusCss) return;
    MAPA_STATUS_ROW_CLASSES.forEach(function(c) { row.classList.remove(c); });
    row.classList.add(statusCss);
    const statusCell = row.querySelector('.status-cell');
    if (statusCell) {
        MAPA_STATUS_ROW_CLASSES.forEach(function(c) { statusCell.classList.remove(c); });
        statusCell.classList.add('status-cell', 'col-sticky-right', statusCss);
        const badge = statusCell.querySelector('.badge-status');
        if (badge) {
            MAPA_BADGE_CLASSES.forEach(function(c) { badge.classList.remove(c); });
            badge.classList.add(badgeClassForStatus(statusCss));
        }
    }
}

// (REMOVIDO) Não Aplica: funcionalidade descontinuada

// Modais
function initModals() {
    const modalTriggers = document.querySelectorAll('[data-modal-target]');
    
    modalTriggers.forEach(trigger => {
        trigger.addEventListener('click', function(e) {
            e.preventDefault();
            const target = this.getAttribute('data-modal-target');
            const itemId = this.getAttribute('data-item-id');
            
            if (target && itemId) {
                loadModalContent(target, itemId);
            }
        });
    });
}

// Carregar conteúdo do modal
function loadModalContent(modalId, itemId) {
    const modal = document.getElementById(modalId);
    if (!modal) {
        console.warn('[LPLAN] Modal não encontrado: id=', modalId);
        return;
    }
    var modalBody = modal.querySelector('#modalDetalheBody') || modal.querySelector('.modal-body');
    var contentEl = modal.querySelector('#modalDetalheContent');
    if (modalBody) {
        modalBody.setAttribute('aria-busy', 'true');
    }
    if (contentEl) {
        contentEl.innerHTML = '';
    }

    var bsModal = typeof bootstrap !== 'undefined' && bootstrap.Modal ? new bootstrap.Modal(modal) : null;
    if (bsModal) bsModal.show();
    else console.warn('[LPLAN] Bootstrap.Modal não disponível');

    var base = (typeof window.__LPLAN_API_BASE__ === 'string') ? window.__LPLAN_API_BASE__ : '';
    const url = base + '/api/internal/item/' + itemId + '/detalhe/';
    fetch(url, { method: 'GET', credentials: 'include' })
        .then(function(response) {
            if (!response.ok) {
                throw new Error('Erro ' + response.status);
            }
            return response.json();
        })
        .then(function(data) {
            if (contentEl) {
                contentEl.innerHTML = (data && data.html)
                    ? data.html
                    : '<p class="text-muted mb-0">Sem detalhes disponíveis.</p>';
            }
            initAlocacaoForm(itemId);
            announceMapaStatus('Detalhes carregados.');
        })
        .catch(function(error) {
            console.error('[LPLAN] Detalhes catch:', error && error.message ? error.message : error);
            if (contentEl) {
                contentEl.innerHTML = '<p class="text-danger mb-0">Não foi possível carregar os detalhes. Tente novamente.</p>';
            }
            announceMapaStatus('Erro ao carregar detalhes.');
        })
        .finally(function() {
            if (modalBody) {
                modalBody.setAttribute('aria-busy', 'false');
            }
        });
}

// Form de alocação
function initAlocacaoForm(itemId) {
    const form = document.getElementById('form-alocacao');
    if (!form) return;
    
    form.addEventListener('submit', function(e) {
        e.preventDefault();
        
        const formData = new FormData(form);
        const url = form.getAttribute('action');
        getCsrfTokenAsync().then(function(csrftoken) {
            if (!csrftoken) {
                csrftoken = getCsrfToken();
            }
            if (!csrftoken) {
                csrftoken = getCsrfToken();
            }
            if (!csrftoken) {
                _logCsrf('Sessão inválida: token não obtido (alocação).');
                showMessage('Sessão inválida. Recarregue a página e tente novamente.', 'error');
                return;
            }
            fetch(url, {
            method: 'POST',
            credentials: 'include',
            headers: {
                'X-CSRFToken': csrftoken
            },
            body: formData
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                showMessage('Alocação realizada com sucesso!', 'success');
                var itemId = form.querySelector('[name="item_id"]') && form.querySelector('[name="item_id"]').value;
                if (itemId && data.row_patch && typeof applyRowPatch === 'function') {
                    applyRowPatch(itemId, data.row_patch);
                } else if (itemId && data.status_css && typeof updateRowStatus === 'function') {
                    updateRowStatus(itemId, data.status_css);
                }
                var modalEl = document.getElementById('modalDetalhe');
                if (modalEl && typeof bootstrap !== 'undefined') {
                    var inst = bootstrap.Modal.getInstance(modalEl);
                    if (inst) inst.hide();
                }
            } else {
                showMessage('Erro: ' + (data.error || 'Erro desconhecido'), 'error');
            }
        })
        .catch(error => {
            console.error('Error:', error);
            showMessage('Erro ao realizar alocação', 'error');
        });
        });
    });
}

// Filtros - função mantida para extensibilidade futura
function initFiltros() {
    if (typeof window.refreshMapaFragment === 'function') return;
    var form = document.getElementById('filtro-form');
    var search = document.getElementById('search');
    if (!form || !search) return;

    var debounceTimer = null;
    search.addEventListener('input', function() {
        clearTimeout(debounceTimer);
        debounceTimer = setTimeout(function() {
            var pageInput = form.querySelector('[name="page"]');
            if (pageInput) pageInput.remove();
            form.submit();
        }, 500);
    });
}

function initFiltroChips() {
    if (typeof window.refreshMapaFragment === 'function') return;
    var bar = document.getElementById('mapa-filtros-ativos');
    if (!bar) return;

    bar.addEventListener('click', function(e) {
        var chip = e.target.closest('.mapa-chip-filtro');
        if (!chip) return;
        e.preventDefault();
        var param = chip.getAttribute('data-remove-param');
        if (!param) return;
        try {
            var params = new URLSearchParams(window.location.search);
            params.delete(param);
            params.delete('page');
            var qs = params.toString();
            showMapaTableLoading('Removendo filtro…');
            window.location.href = window.location.pathname + (qs ? '?' + qs : '');
        } catch (err) {
            console.error('[LPLAN] Erro ao remover filtro:', err);
        }
    });
}

function initGridKeyboardNav() {
    var table = document.querySelector('.tabela-mapa');
    if (!table) return;

    function editableInputs() {
        return Array.prototype.slice.call(
            table.querySelectorAll('.input-inline[data-update-url]:not([disabled])')
        ).filter(function(el) {
            return !el.readOnly;
        });
    }

    table.addEventListener('keydown', function(e) {
        var el = e.target;
        if (!el || !el.matches('.input-inline[data-update-url]')) return;

        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            el.blur();
            var inputs = editableInputs();
            var idx = inputs.indexOf(el);
            if (idx >= 0 && idx < inputs.length - 1) {
                setTimeout(function() { inputs[idx + 1].focus(); }, 50);
            }
        }
    });
}

function initKpiFilters() {
    if (typeof window.refreshMapaFragment === 'function') return;
    var container = document.getElementById('kpi-container');
    var form = document.getElementById('filtro-form');
    if (!container || !form) return;

    container.querySelectorAll('.kpi-clickable').forEach(function(card) {
        card.addEventListener('click', function() {
            var status = card.getAttribute('data-kpi-status') || '';
            var statusInput = form.querySelector('[name="status"]');
            if (statusInput) {
                statusInput.value = status;
            } else {
                var hidden = document.createElement('input');
                hidden.type = 'hidden';
                hidden.name = 'status';
                hidden.value = status;
                form.appendChild(hidden);
            }
            var pageInput = form.querySelector('[name="page"]');
            if (pageInput) pageInput.remove();
            form.submit();
        });
    });
}

var MAPA_COL_STORAGE_KEY = 'lplan_mapa_colunas';

function initColumnToggle() {
    var bar = document.getElementById('mapa-colunas-toggle');
    if (!bar) return;

    var saved = {};
    try {
        saved = JSON.parse(localStorage.getItem(MAPA_COL_STORAGE_KEY) || '{}') || {};
    } catch (e) {
        saved = {};
    }

    function applyCol(colKey, visible) {
        document.querySelectorAll('.' + colKey).forEach(function(el) {
            el.classList.toggle('col-hidden', !visible);
        });
    }

    bar.querySelectorAll('input[data-col]').forEach(function(cb) {
        var colKey = cb.getAttribute('data-col');
        if (saved[colKey] === false) {
            cb.checked = false;
        }
        applyCol(colKey, cb.checked);
        cb.addEventListener('change', function() {
            applyCol(colKey, cb.checked);
            saved[colKey] = cb.checked;
            try {
                localStorage.setItem(MAPA_COL_STORAGE_KEY, JSON.stringify(saved));
            } catch (e) {}
        });
    });
}

function initDuplicateItem() {
    document.addEventListener('click', function(e) {
        var btn = e.target.closest('[data-action="duplicate-item"]');
        if (!btn) return;
        e.preventDefault();
        e.stopPropagation();

        var url = btn.getAttribute('data-duplicate-url');
        if (!url) return;
        if (!window.confirm('Duplicar este item?\n\nSerá criada uma cópia sem alocações.')) return;

        getCsrfTokenAsync().then(function(csrftoken) {
            if (!csrftoken) csrftoken = getCsrfToken();
            if (!csrftoken) {
                showMessage('Sessão inválida. Recarregue a página.', 'error');
                return;
            }
            fetch(url, {
                method: 'POST',
                credentials: 'include',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrftoken
                },
                body: '{}'
            })
            .then(function(r) { return r.json().then(function(d) { return { ok: r.ok, data: d }; }); })
            .then(function(res) {
                if (res.ok && res.data.success) {
                    showMessage(res.data.message || 'Item duplicado.', 'success');
                    if (typeof refreshMapaFragment === 'function') {
                        refreshMapaFragment({}, { scrollItemId: res.data.item_id, loadingMessage: 'Atualizando mapa…' });
                    } else if (res.data.redirect_url) {
                        window.location.href = res.data.redirect_url;
                    } else {
                        window.location.reload();
                    }
                } else {
                    showMessage(res.data.error || 'Erro ao duplicar.', 'error');
                }
            })
            .catch(function() {
                showMessage('Erro ao duplicar item.', 'error');
            });
        });
    });
}

// Utilitários
function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}

/** Log no F12 (Console) para diagnosticar CSRF/sessão. Prefixo [LPLAN] para filtrar. */
function _logCsrf(msg, detail) {
    try {
        if (detail !== undefined) {
            console.warn('[LPLAN]', msg, detail);
        } else {
            console.warn('[LPLAN]', msg);
        }
    } catch (e) {}
}

/** Obtém o token CSRF: variável injetada pelo servidor (base_mapa), data-csrf-token no body, meta tag, cookie, input hidden. */
function getCsrfToken() {
    if (typeof window.__LPLAN_CSRF_TOKEN__ === 'string' && window.__LPLAN_CSRF_TOKEN__) {
        _logCsrf('CSRF token: obtido de window.__LPLAN_CSRF_TOKEN__');
        return window.__LPLAN_CSRF_TOKEN__;
    }
    if (document.body) {
        var bodyToken = document.body.getAttribute('data-csrf-token');
        if (bodyToken) {
            _logCsrf('CSRF token: obtido de body[data-csrf-token]');
            return bodyToken;
        }
    }
    const meta = document.querySelector('meta[name="csrf-token"]');
    if (meta) {
        var metaToken = meta.getAttribute('content');
        if (metaToken) {
            _logCsrf('CSRF token: obtido de meta[name=csrf-token]');
            return metaToken;
        }
    }
    var cookieToken = getCookie('csrftoken');
    if (cookieToken) {
        _logCsrf('CSRF token: obtido de cookie csrftoken');
        return cookieToken;
    }
    const input = document.querySelector('input[name="csrfmiddlewaretoken"]');
    if (input && input.value) {
        _logCsrf('CSRF token: obtido de input csrfmiddlewaretoken');
        return input.value;
    }
    _logCsrf('CSRF token: nenhuma fonte disponível (window, body, meta, cookie, input vazios)');
    return null;
}

/**
 * Obtém o token CSRF; se não estiver na página, busca em /api/csrf-token/ e atualiza a meta tag.
 * Usa window.__LPLAN_CSRF_TOKEN_URL__ se definido (injetado pelo base_mapa.html).
 * Em produção usa URL absoluta (origin + path) para evitar falhas quando o path base difere.
 */
function getCsrfTokenAsync() {
    const sync = getCsrfToken();
    if (sync) return Promise.resolve(sync);
    var url = (typeof window.__LPLAN_CSRF_TOKEN_URL__ === 'string' && window.__LPLAN_CSRF_TOKEN_URL__)
        ? window.__LPLAN_CSRF_TOKEN_URL__
        : (document.body && document.body.getAttribute('data-csrf-token-url')) || '/api/csrf-token/';
    if (url.indexOf('http') !== 0 && typeof window.location !== 'undefined' && window.location.origin) {
        url = window.location.origin.replace(/\/$/, '') + (url.indexOf('/') === 0 ? url : '/' + url);
        _logCsrf('CSRF token: usando URL absoluta para fetch', url);
    } else {
        _logCsrf('CSRF token: não encontrado na página; buscando em GET', url);
    }
    return fetch(url, { method: 'GET', credentials: 'include' })
        .then(function(r) {
            _logCsrf('CSRF GET resposta:', { status: r.status, ok: r.ok, url: r.url, contentType: r.headers.get('Content-Type') });
            if (!r.ok) {
                _logCsrf('CSRF GET: status não OK (pode ser redirect para login ou 403). Status=', r.status);
                r.text().then(function(body) {
                    _logCsrf('CSRF GET body (primeiros 400 chars):', body ? body.substring(0, 400) : '(vazio)');
                }).catch(function() {});
                return null;
            }
            var ct = r.headers.get('Content-Type') || '';
            if (ct.indexOf('application/json') === -1) {
                _logCsrf('CSRF GET: resposta não é JSON (provavelmente HTML/redirect). Content-Type=', ct);
                r.text().then(function(body) {
                    _logCsrf('CSRF GET body (primeiros 400 chars):', body ? body.substring(0, 400) : '(vazio)');
                }).catch(function() {});
                return null;
            }
            return r.json();
        })
        .then(function(data) {
            if (!data) return null;
            var t = (data && data.csrfToken) ? data.csrfToken : null;
            if (t) {
                window.__LPLAN_CSRF_TOKEN__ = t;
                if (document.body) document.body.setAttribute('data-csrf-token', t);
                var meta = document.querySelector('meta[name="csrf-token"]');
                if (!meta) {
                    meta = document.createElement('meta');
                    meta.setAttribute('name', 'csrf-token');
                    document.head.appendChild(meta);
                }
                meta.setAttribute('content', t);
                _logCsrf('CSRF token: recebido da API e salvo na página');
                return t;
            }
            _logCsrf('CSRF GET: JSON sem csrfToken', data);
            return null;
        })
        .catch(function(err) {
            _logCsrf('CSRF GET: erro no fetch', err && err.message ? err.message : err);
            return null;
        });
}

var _quietSaveToastTimer = null;
var _quietSaveCount = 0;

function showQuietSaveToast() {
    _quietSaveCount += 1;
    clearTimeout(_quietSaveToastTimer);
    _quietSaveToastTimer = setTimeout(function() {
        var n = _quietSaveCount;
        _quietSaveCount = 0;
        var msg = n > 1 ? (n + ' alterações salvas') : 'Salvo';
        showMessage(msg, 'success', { quiet: true });
    }, 700);
}

function showMessage(message, type, options) {
    options = options || {};
    var existing = document.querySelector('.mapa-toast-fixo');
    if (existing) existing.remove();

    const id = 'mapa-toast-' + Date.now();
    const alertDiv = document.createElement('div');
    alertDiv.id = id;
    var alertType = type === 'success' ? 'success' : 'danger';
    alertDiv.className = 'alert alert-' + alertType + ' alert-dismissible fade show mapa-toast-fixo'
        + (options.quiet ? ' mapa-toast-quiet' : '');
    alertDiv.setAttribute('role', 'alert');
    alertDiv.innerHTML =
        '<i class="bi bi-' + (type === 'success' ? 'check-circle-fill' : 'exclamation-circle-fill') + ' me-2"></i>' +
        '<span>' + message + '</span>' +
        '<button type="button" class="btn-close' + (type === 'success' ? '' : ' btn-close-white') + '" data-bs-dismiss="alert" aria-label="Fechar"></button>';
    document.body.appendChild(alertDiv);
    setTimeout(function() {
        const el = document.getElementById(id);
        if (el) el.remove();
    }, options.quiet ? 2200 : 4000);
}

// Inicializar tooltips Bootstrap
function initTooltips() {
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });
}

// Feedback de salvamento
function showSaveFeedback(itemId) {
    const row = document.querySelector(`tr[data-item-id="${itemId}"]`);
    if (row) {
        row.classList.add('saved-feedback');
        setTimeout(() => {
            row.classList.remove('saved-feedback');
        }, 2000);
    }
}

// Agrupamento por categoria
function initCategoriaToggle() {
    document.querySelectorAll('.toggle-categoria').forEach(toggle => {
        toggle.addEventListener('click', function(e) {
            e.stopPropagation();
            const categoria = this.getAttribute('data-categoria');
            const header = this.closest('.categoria-header');
            const categoriaSlug = categoria.toLowerCase().replace(/\s+/g, '-');
            
            header.classList.toggle('collapsed');
            
            // Esconder/mostrar linhas da categoria
            let nextRow = header.nextElementSibling;
            while (nextRow && nextRow.classList.contains(`categoria-${categoriaSlug}`)) {
                if (header.classList.contains('collapsed')) {
                    nextRow.style.display = 'none';
                } else {
                    nextRow.style.display = '';
                }
                nextRow = nextRow.nextElementSibling;
                // Parar se encontrar outro header
                if (nextRow && nextRow.classList.contains('categoria-header')) {
                    break;
                }
            }
        });
    });
}

// (REMOVIDO) Toggle NAO_APLICA: funcionalidade descontinuada

// Criar novo item
function initCriarItem() {
    const form = document.getElementById('formCriarItem');
    if (!form) return;
    
    // Carregar locais quando obra mudar
    const obraSelect = document.getElementById('criar_obra');
    if (obraSelect) {
        obraSelect.addEventListener('change', function() {
            loadLocaisCriar(this.value);
        });
        
        // Se já tem obra selecionada, carregar locais
        if (obraSelect.value) {
            loadLocaisCriar(obraSelect.value);
        }
    }
    
    // Submeter formulário
    form.addEventListener('submit', function(e) {
        e.preventDefault();
        criarItem();
    });
    
    // Inicializar modal de criar insumo
    initCriarInsumo();
}

// Excluir item (delegação para funcionar no modal e na tabela)
function initDeleteItem() {
    document.addEventListener('click', function(e) {
        const btn = e.target.closest('[data-action="delete-item"]');
        if (!btn) return;

        // Evitar clique “subir” e disparar outros handlers (ex: card mobile)
        e.preventDefault();
        e.stopPropagation();

        const itemId = btn.getAttribute('data-item-id');
        const url = btn.getAttribute('data-delete-url');
        if (!itemId || !url) return;

        const ok = window.confirm('Excluir este item?\n\nVocê terá 7 segundos para desfazer.');
        if (!ok) return;

        getCsrfTokenAsync().then(function(csrftoken) {
            if (!csrftoken) {
                csrftoken = getCsrfToken();
            }
            if (!csrftoken) {
                csrftoken = getCsrfToken();
            }
            if (!csrftoken) {
                _logCsrf('Sessão inválida: token não obtido (excluir item).');
                showMessage('Sessão inválida. Recarregue a página e tente novamente.', 'error');
                return;
            }
            fetch(url, {
            method: 'POST',
            credentials: 'include',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': csrftoken
            },
            body: JSON.stringify({ item_id: itemId })
        })
        .then(function(r) {
            return r.text().then(function(text) {
                var data = {};
                try { data = text ? JSON.parse(text) : {}; } catch (e) { data = {}; }
                if (!r.ok) {
                    var msg = (data && data.error) ? data.error : ('Erro ' + r.status + (r.status === 403 ? ': selecione a obra no topo da página e recarregue.' : ''));
                    return Promise.reject({ message: msg });
                }
                return data;
            });
        })
        .then(data => {
            if (data.success) {
                if (typeof removeItemFromDom === 'function') removeItemFromDom(itemId);
                var modal = document.getElementById('modalDetalhe');
                if (modal && typeof bootstrap !== 'undefined') {
                    var inst = bootstrap.Modal.getInstance(modal);
                    if (inst) inst.hide();
                }
                if (typeof showUndoDeleteToast === 'function' && data.undo_snapshot) {
                    showUndoDeleteToast(data.undo_snapshot, data.message || 'Item excluído.');
                } else {
                    showMessage(data.message || 'Item excluído', 'success');
                }
            } else {
                showMessage('❌ ' + (data.error || 'Erro ao excluir'), 'error');
            }
        })
        .catch(err => {
            console.error(err);
            var msg = (err && err.message) ? err.message : 'Erro ao excluir. Verifique se a obra está selecionada no topo da página e recarregue.';
            showMessage('❌ ' + msg, 'error');
        });
        });
    });
}

// Criar novo insumo
function initCriarInsumo() {
    const modalCriarInsumo = document.getElementById('modalCriarInsumo');
    if (!modalCriarInsumo) {
        console.warn('Modal modalCriarInsumo não encontrado');
        return;
    }
    
    // Inicializar formulário quando o modal for mostrado
    modalCriarInsumo.addEventListener('shown.bs.modal', function() {
        const form = document.getElementById('formCriarInsumo');
        if (!form) {
            console.error('Formulário formCriarInsumo não encontrado');
            return;
        }
        
        // Remover listener anterior se existir
        const newForm = form.cloneNode(true);
        form.parentNode.replaceChild(newForm, form);
        
        // Adicionar listener de submit
        newForm.addEventListener('submit', function(e) {
            e.preventDefault();
            e.stopPropagation();
            criarInsumo();
        });
    });
    
    // Quando modal de criar insumo fechar, limpar formulário
    modalCriarInsumo.addEventListener('hidden.bs.modal', function() {
        const form = document.getElementById('formCriarInsumo');
        if (form) {
            form.reset();
        }
    });
    
    // Também inicializar se o formulário já existir no DOM
    const form = document.getElementById('formCriarInsumo');
    if (form) {
        form.addEventListener('submit', function(e) {
            e.preventDefault();
            e.stopPropagation();
            criarInsumo();
        });
    }
}

function criarInsumo() {
    const form = document.getElementById('formCriarInsumo');
    if (!form) {
        console.error('Formulário formCriarInsumo não encontrado');
        return;
    }
    
    const formData = new FormData(form);
    const submitBtn = form.querySelector('button[type="submit"]');
    
    getCsrfTokenAsync().then(function(csrftoken) {
        if (!csrftoken) {
            csrftoken = getCsrfToken();
        }
        if (!csrftoken) {
            _logCsrf('Sessão inválida: token não obtido (criar insumo).');
            showMessage('Sessão inválida. Recarregue a página e tente novamente.', 'error');
            return;
        }
        if (submitBtn) {
        submitBtn.disabled = true;
        const originalText = submitBtn.innerHTML;
        submitBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Criando...';

        fetch(form.action, {
            method: 'POST',
            credentials: 'include',
            headers: {
                'X-Requested-With': 'XMLHttpRequest',
                'X-CSRFToken': csrftoken
            },
            body: formData
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                showMessage('✅ ' + data.message, 'success');
                
                // Adicionar novo insumo ao select
                const selectInsumo = document.getElementById('criar_insumo');
                if (selectInsumo) {
                    const option = document.createElement('option');
                    option.value = data.insumo.id;
                    option.textContent = `${data.insumo.codigo_sienge} - ${data.insumo.descricao}`;
                    option.selected = true;
                    selectInsumo.appendChild(option);
                }
                
                // Limpar formulário
                form.reset();
                
                // Fechar modal
                const modalElement = document.getElementById('modalCriarInsumo');
                if (modalElement) {
                    const modal = bootstrap.Modal.getInstance(modalElement);
                    if (modal) modal.hide();
                }
            } else {
                // Mostrar erros de validação
                let errorMsg = '❌ Erro: ';
                if (data.errors) {
                    const errors = Object.values(data.errors).flat();
                    errorMsg += errors.join(', ');
                } else {
                    errorMsg += (data.error || 'Erro desconhecido');
                }
                showMessage(errorMsg, 'error');
                submitBtn.disabled = false;
                submitBtn.innerHTML = originalText;
            }
        })
        .catch(error => {
            console.error('Error:', error);
            showMessage('❌ Erro ao criar insumo: ' + error.message, 'error');
            submitBtn.disabled = false;
            submitBtn.innerHTML = originalText;
        });
        }
    });
}

function loadLocaisCriar(obraId) {
    const select = document.getElementById('criar_local');
    if (!select || !obraId) {
        if (select) select.innerHTML = '<option value="">-- Selecione --</option>';
        return;
    }
    
    // Mostrar loading
    select.disabled = true;
    select.innerHTML = '<option value="">Carregando locais...</option>';
    
    fetch(`/api/internal/locais/?obra=${obraId}`)
        .then(response => response.json())
        .then(data => {
            select.innerHTML = '<option value="">-- Selecione --</option>';
            if (data.locais && data.locais.length > 0) {
                data.locais.forEach(local => {
                    const option = document.createElement('option');
                    option.value = local.id;
                    option.textContent = local.nome;
                    select.appendChild(option);
                });
            } else {
                const option = document.createElement('option');
                option.value = '';
                option.textContent = 'Nenhum local cadastrado';
                select.appendChild(option);
            }
            select.disabled = false;
        })
        .catch(error => {
            console.error('Erro ao carregar locais:', error);
            select.innerHTML = '<option value="">Erro ao carregar locais</option>';
            select.disabled = false;
        });
}

function criarItem() {
    const form = document.getElementById('formCriarItem');
    if (!form) return;
    const formData = new FormData(form);
    const submitBtn = form.querySelector('button[type="submit"]');
    
    getCsrfTokenAsync().then(function(csrftoken) {
        if (!csrftoken) {
            csrftoken = getCsrfToken();
        }
        if (!csrftoken) {
            _logCsrf('Sessão inválida: token não obtido (criar insumo).');
            showMessage('Sessão inválida. Recarregue a página e tente novamente.', 'error');
            return;
        }
        if (submitBtn) {
        submitBtn.disabled = true;
        const originalText = submitBtn.innerHTML;
        submitBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Criando...';

        fetch(form.action, {
            method: 'POST',
            credentials: 'include',
            headers: {
                'X-CSRFToken': csrftoken
            },
            body: formData
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                showMessage('✅ Item criado com sucesso!', 'success');
                form.reset();
                const modalElement = document.getElementById('modalCriarItem');
                if (modalElement) {
                    const modal = bootstrap.Modal.getInstance(modalElement);
                    if (modal) modal.hide();
                }
                if (typeof refreshMapaFragment === 'function' && data.item_id) {
                    refreshMapaFragment({}, { scrollItemId: data.item_id, loadingMessage: 'Atualizando mapa…' });
                } else if (data.redirect_url) {
                    window.location.href = data.redirect_url;
                } else {
                    setTimeout(() => window.location.reload(), 800);
                }
            } else {
                showMessage('❌ Erro ao criar item: ' + (data.error || 'Erro desconhecido'), 'error');
                submitBtn.disabled = false;
                submitBtn.innerHTML = originalText;
            }
        })
        .catch(error => {
            console.error('Error:', error);
            showMessage('❌ Erro ao criar item: ' + error.message, 'error');
            submitBtn.disabled = false;
            submitBtn.innerHTML = originalText;
        });
        }
    });
}
