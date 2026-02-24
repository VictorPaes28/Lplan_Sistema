// SupplyMap - JavaScript principal

document.addEventListener('DOMContentLoaded', function() {
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
        // Para selects, usar 'change' em vez de 'blur'
        const eventType = input.tagName === 'SELECT' ? 'change' : 'blur';
        
        input.addEventListener(eventType, function() {
            const url = this.getAttribute('data-update-url');
            const field = this.getAttribute('data-field');
            const value = this.value;
            const itemId = this.getAttribute('data-item-id');
            
            if (!url || !field || !itemId) return;
            
            // Atualizar classe visual para campo prioridade
            if (field === 'prioridade') {
                updatePrioridadeClass(this, value);
            }
            
            updateItemField(itemId, field, value, url);
        });
        
        // Inicializar classe correta para prioridade
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
function updateItemField(itemId, field, value, url) {
    const csrftoken = getCookie('csrftoken');
    
    fetch(url, {
        method: 'POST',
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
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showSaveFeedback(itemId);
            showMessage('✓ Salvo', 'success');
            // Atualizar status visual se necessário
            if (data.status_css) {
                updateRowStatus(itemId, data.status_css);
            }
        } else {
            showMessage('Erro ao atualizar: ' + (data.error || 'Erro desconhecido'), 'error');
        }
    })
    .catch(error => {
        console.error('Error:', error);
        showMessage('Erro ao atualizar', 'error');
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
        const csrftoken = getCookie('csrftoken');
        
        fetch(url, {
            method: 'POST',
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

function showMessage(message, type) {
    // Criar toast/alert simples
    const alertDiv = document.createElement('div');
    alertDiv.className = `alert alert-${type === 'success' ? 'success' : 'danger'} alert-dismissible fade show`;
    alertDiv.setAttribute('role', 'alert');
    alertDiv.innerHTML = `
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
    `;
    
    const container = document.querySelector('.container-fluid') || document.body;
    container.insertBefore(alertDiv, container.firstChild);
    
    setTimeout(() => {
        alertDiv.remove();
    }, 3000);
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

        const csrftoken = getCookie('csrftoken');
        fetch(url, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': csrftoken
            },
            body: JSON.stringify({ item_id: itemId })
        })
        .then(r => r.json())
        .then(data => {
            if (data.success) {
                showMessage(data.message || '✅ Item excluído', 'success');
                // Recarregar para manter agrupamentos/contagens consistentes
                setTimeout(() => window.location.reload(), 400);
            } else {
                showMessage('❌ ' + (data.error || 'Erro ao excluir'), 'error');
            }
        })
        .catch(err => {
            console.error(err);
            showMessage('❌ Erro ao excluir', 'error');
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
    const csrftoken = getCookie('csrftoken');
    const submitBtn = form.querySelector('button[type="submit"]');
    
    // Desabilitar botão e mostrar loading
    if (submitBtn) {
        submitBtn.disabled = true;
        const originalText = submitBtn.innerHTML;
        submitBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Criando...';
        
        fetch(form.action, {
            method: 'POST',
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
    const formData = new FormData(form);
    const csrftoken = getCookie('csrftoken');
    const submitBtn = form.querySelector('button[type="submit"]');
    
    // Desabilitar botão e mostrar loading
    if (submitBtn) {
        submitBtn.disabled = true;
        const originalText = submitBtn.innerHTML;
        submitBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Criando...';
        
        fetch('/engenharia/mapa/criar-item/', {
            method: 'POST',
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
}
