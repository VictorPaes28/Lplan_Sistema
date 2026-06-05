/**
 * Inicialização do formulário de pedido (criação/edição e modal via fetch).
 * @param {ParentNode} scope - ancestral do `#workorder-create-form`; use document na página inteira.
 * @param {{ skipSubmitLock?: boolean }} opts - modal via AJAX não usa o travamento «Salvando…» síncrono.
 */
(function (global) {
    function fieldValorMed(scope) {
        return scope.querySelector('#id_valor_medicao');
    }

    function syncValorMed(scope) {
        var tipo = scope.querySelector('#id_tipo_solicitacao');
        var box = scope.querySelector('#valor-medicao-group');
        var el = fieldValorMed(scope);
        if (!tipo || !box) return;
        var isMed = tipo.value === 'medicao';
        box.style.display = isMed ? 'block' : 'none';
        if (el) {
            el.required = isMed;
            el.setAttribute('aria-required', isMed ? 'true' : 'false');
            if (!isMed) el.setCustomValidity('');
        }
        var mark = scope.querySelector('#valor-medicao-required-mark');
        if (mark) mark.style.display = isMed ? 'inline' : 'none';
    }

    function bindValorMedicao(scope) {
        var tipo = scope.querySelector('#id_tipo_solicitacao');
        if (tipo) {
            tipo.addEventListener('change', function () {
                syncValorMed(scope);
            });
            syncValorMed(scope);
        }
        var woForm = scope.querySelector('#workorder-create-form');
        if (woForm && tipo) {
            woForm.addEventListener('submit', function (ev) {
                if (tipo.value !== 'medicao') return;
                var el = fieldValorMed(scope);
                if (!el) return;
                var raw = (el.value || '').trim().replace(',', '.');
                var n = parseFloat(raw);
                if (!raw || isNaN(n) || n <= 0) {
                    el.setCustomValidity('Informe o valor de medição (maior que zero).');
                    ev.preventDefault();
                    ev.stopImmediatePropagation();
                    el.reportValidity();
                } else {
                    el.setCustomValidity('');
                }
            });
        }
        var elVm = fieldValorMed(scope);
        if (elVm) {
            elVm.addEventListener('input', function () {
                elVm.setCustomValidity('');
            });
        }
    }

    function bindSubmitLock(scope) {
        var form = scope.querySelector('#workorder-create-form');
        var btn = scope.querySelector('#workorder-submit-btn');
        if (!form || !btn) return;
        var defaultLabel = btn.getAttribute('data-default-label') || btn.textContent;
        var submitted = false;
        form.addEventListener('submit', function (e) {
            if (submitted) {
                e.preventDefault();
                return false;
            }
            submitted = true;
            btn.disabled = true;
            btn.textContent = 'Salvando…';
            btn.style.opacity = '0.7';
            btn.style.cursor = 'not-allowed';
        });
        global.addEventListener('pageshow', function (e) {
            if (!e.persisted) return;
            submitted = false;
            btn.disabled = false;
            btn.textContent = defaultLabel;
            btn.style.opacity = '';
            btn.style.cursor = '';
        });
    }

    function bindAnexosFileQueue(scope) {
        if (!global.LplanAnexosFileQueue) return;
        if (!scope.querySelector('#anexos')) return;
        global.LplanAnexosFileQueue(scope);
    }

    /**
     * @param {ParentNode} scope
     * @param {{ skipSubmitLock?: boolean }} [opts]
     */
    global.LplanWorkorderFormInit = function (scope, opts) {
        if (!scope || !scope.querySelector) return;
        bindValorMedicao(scope);
        bindAnexosFileQueue(scope);
        if (!opts || !opts.skipSubmitLock) bindSubmitLock(scope);
    };
})(typeof window !== 'undefined' ? window : this);
