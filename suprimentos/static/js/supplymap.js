// SupplyMap - JavaScript principal

document.addEventListener('DOMContentLoaded', function() {
    // Diagnóstico CSRF no F12 (Console): filtrar por [LPLAN]
    try {
        var w = typeof window.__LPLAN_CSRF_TOKEN__ === 'string' && window.__LPLAN_CSRF_TOKEN__ ? 'sim' : 'não';
        var b = document.body && document.body.getAttribute('data-csrf-token') ? 'sim' : 'não';
        var m = document.querySelector('meta[name="csrf-token"]');
        var mVal = m && m.getAttribute('content') ? 'sim' : 'não';
        var u = typeof window.__LPLAN_CSRF_TOKEN_URL__ === 'string' && window.__LPLAN_CSRF_TOKEN_URL__ ? window.__LPLAN_CSRF_TOKEN_URL__ : '(não definido)';
        console.warn('[LPLAN] Diagnóstico ao carregar: token em window=', w, 'body=', b, 'meta=', mVal, '| URL API=', u);
    } catch (e) {}

    // Inicialização
    initInlineEdit();
    initModals();
    initFiltros();
    initTooltips();
    initCategoriaToggle();
    initCriarItem();
    initDeleteItem();
});

// Edição inline (HTMX ou fetch simples)
function initInlineEdit() {
    const inputs = document.querySelectorAll('.input-inline[data-update-url]');
    
    inputs.forEach(input => {
        // Guardar valor inicial ao ganhar foco (para não enviar POST se não mudou)
        input.addEventListener('focus', function() {
            this.setAttribute('data-initial-value', this.value || '');
        });
        
        const eventType = input.tagName === 'SELECT' ? 'change' : 'blur';
        input.addEventListener(eventType, function() {
            const url = this.getAttribute('data-update-url');
            const field = this.getAttribute('data-field');
            const value = this.value;
            const itemId = this.getAttribute('data-item-id');
            
            if (!url || !field || !itemId) return;
            
            const initial = this.getAttribute('data-initial-value') || '';
            if (String(value).trim() === String(initial).trim()) {
                return; // Valor não mudou, não enviar requisição
            }
            
            if (field === 'prioridade') {
                updatePrioridadeClass(this, value);
            }
            
            updateItemField(itemId, field, value, url);
        });
        
        if (input.getAttribute('data-field') === 'prioridade') {
            updatePrioridadeClass(input, input.value);
        }
    });
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

// Atualizar campo via AJAX
// CSRF: o token vem de 1) cookie csrftoken, 2) meta name="csrf-token", 3) input name="csrfmiddlewaretoken".
// Se não houver, getCsrfTokenAsync() busca em /api/csrf-token/ e atualiza a meta.
function updateItemField(itemId, field, value, url) {
    getCsrfTokenAsync().then(function(csrftoken) {
        if (!csrftoken) {
            csrftoken = getCsrfToken();
        }
        if (!csrftoken) {
            _logCsrf('Sessão inválida: token não obtido (nem async nem retry getCsrfToken). Verifique os logs [LPLAN] acima.');
            showMessage('Sessão inválida. Recarregue a página e tente novamente.', 'error');
            return;
        }
        setRowSaving(itemId, true);
        _logCsrf('POST', url);
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
    .then(response => {
        return response.text().then(function(text) {
            var data;
            try { data = text ? JSON.parse(text) : {}; } catch (e) { data = {}; }
            if (!response.ok) {
                _logCsrf('POST falhou:', { status: response.status, url: url, error: (data && data.error) ? data.error : text ? text.substring(0, 200) : '' });
                var msg = (data && data.error) ? data.error : ('Erro ' + response.status);
                throw { status: response.status, message: msg };
            }
            return data;
        });
    })
    .then(data => {
        setRowSaving(itemId, false);
        if (data.success) {
            showSaveFeedback(itemId);
            showMessage('Salvo', 'success');
            if (data.status_css) {
                updateRowStatus(itemId, data.status_css);
            }
            // Dados do Sienge (PC, prazo, empresa, quantidade) foram preenchidos no servidor;
            // recarregar a página para exibir todas as colunas atualizadas.
            if (data.filled_from_sienge) {
                setTimeout(function() { window.location.reload(); }, 600);
            }
            if (data.debug_no_recebimento) {
                showMessage('Nenhum recebimento do Sienge para esta obra + SC + insumo. Reimporte o MAPA_CONTROLE com a obra correta ou confira em Admin > Recebimentos na Obra.', 'error');
            }
        } else {
            showMessage('Erro: ' + (data.error || 'Erro desconhecido'), 'error');
        }
    })
    .catch(error => {
        setRowSaving(itemId, false);
        _logCsrf('POST catch:', error && error.message ? error.message : error);
        showMessage((error && error.message) ? error.message : 'Erro ao salvar. Recarregue e tente novamente.', 'error');
    });
    });
}

// Atualizar status visual da linha
function updateRowStatus(itemId, statusCss) {
    const row = document.querySelector(`tr[data-item-id="${itemId}"]`);
    if (row) {
        const statusCell = row.querySelector('.status-cell');
        if (statusCell) {
            statusCell.className = 'status-cell ' + statusCss;
        }
    }
}

function setRowSaving(itemId, saving) {
    const row = document.querySelector(`tr[data-item-id="${itemId}"]`);
    if (row) {
        if (saving) row.classList.add('row-saving'); else row.classList.remove('row-saving');
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
    if (!modal) return;
    
    const url = `/api/internal/item/${itemId}/detalhe/`;
    
    fetch(url)
        .then(response => response.json())
        .then(data => {
            const modalBody = modal.querySelector('.modal-body');
            if (modalBody) {
                modalBody.innerHTML = data.html;
            }
            // Inicializar form de alocação se existir
            initAlocacaoForm(itemId);
        })
        .catch(error => {
            console.error('Error:', error);
            showMessage('Erro ao carregar detalhes', 'error');
        });
    
    // Abrir modal (Bootstrap)
    const bsModal = new bootstrap.Modal(modal);
    bsModal.show();
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
                // Recarregar modal ou atualizar tabela
                setTimeout(() => {
                    location.reload();
                }, 1000);
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
    // Auto-submit pode ser implementado aqui se necessário
    // Por enquanto, o formulário usa submit manual via botão
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
        var t = document.body.getAttribute('data-csrf-token');
        if (t) {
            _logCsrf('CSRF token: obtido de body[data-csrf-token]');
            return t;
        }
    }
    const meta = document.querySelector('meta[name="csrf-token"]');
    if (meta) {
        const t = meta.getAttribute('content');
        if (t) {
            _logCsrf('CSRF token: obtido de meta[name=csrf-token]');
            return t;
        }
    }
    const t = getCookie('csrftoken');
    if (t) {
        _logCsrf('CSRF token: obtido de cookie csrftoken');
        return t;
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
 */
function getCsrfTokenAsync() {
    const sync = getCsrfToken();
    if (sync) return Promise.resolve(sync);
    var url = (typeof window.__LPLAN_CSRF_TOKEN_URL__ === 'string' && window.__LPLAN_CSRF_TOKEN_URL__)
        ? window.__LPLAN_CSRF_TOKEN_URL__
        : (document.body && document.body.getAttribute('data-csrf-token-url')) || '/api/csrf-token/';
    _logCsrf('CSRF token: não encontrado na página; buscando em GET', url);
    return fetch(url, { method: 'GET', credentials: 'include' })
        .then(function(r) {
            _logCsrf('CSRF GET resposta:', { status: r.status, ok: r.ok, contentType: r.headers.get('Content-Type') });
            if (!r.ok) return null;
            var ct = r.headers.get('Content-Type') || '';
            if (ct.indexOf('application/json') === -1) {
                _logCsrf('CSRF GET: resposta não é JSON (provavelmente HTML/redirect)', ct);
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

function showMessage(message, type) {
    const id = 'mapa-toast-' + Date.now();
    const alertDiv = document.createElement('div');
    alertDiv.id = id;
    alertDiv.className = `alert alert-${type === 'success' ? 'success' : 'danger'} alert-dismissible fade show mapa-toast-fixo`;
    alertDiv.setAttribute('role', 'alert');
    alertDiv.innerHTML = `
        <i class="bi bi-${type === 'success' ? 'check-circle-fill' : 'exclamation-circle-fill'} me-2"></i>
        <span>${message}</span>
        <button type="button" class="btn-close ${type === 'success' ? '' : 'btn-close-white'}" data-bs-dismiss="alert" aria-label="Fechar"></button>
    `;
    document.body.appendChild(alertDiv);
    setTimeout(() => {
        const el = document.getElementById(id);
        if (el) el.remove();
    }, 4000);
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

        const ok = window.confirm('Excluir este item?\n\nEssa ação não pode ser desfeita.');
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
                showMessage(data.message || '✅ Item excluído', 'success');
                setTimeout(() => window.location.reload(), 400);
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
                // Limpar formulário
                form.reset();
                // Fechar modal
                const modalElement = document.getElementById('modalCriarItem');
                if (modalElement) {
                    const modal = bootstrap.Modal.getInstance(modalElement);
                    if (modal) modal.hide();
                }
                // Recarregar página após 1 segundo
                setTimeout(() => {
                    window.location.reload();
                }, 1000);
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
