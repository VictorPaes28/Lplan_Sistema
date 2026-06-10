/**
 * Inicialização do formulário de pedido (criação/edição e modal via fetch).
 * @param {ParentNode} scope - ancestral do `#workorder-create-form`; use document na página inteira.
 * @param {{ skipSubmitLock?: boolean }} opts - modal via AJAX não usa o travamento «Salvando…» síncrono.
 */
(function (global) {
    function fieldObra(scope) {
        return scope.querySelector('#id_obra');
    }

    function fieldFront(scope) {
        return scope.querySelector('#id_front');
    }

    function parseFrontMap(obraEl) {
        if (!obraEl) return {};
        var raw = obraEl.getAttribute('data-front-map') || '{}';
        try {
            var parsed = JSON.parse(raw);
            return parsed && typeof parsed === 'object' ? parsed : {};
        } catch (_) {
            return {};
        }
    }

    function bindFrontByObra(scope) {
        var obraEl = fieldObra(scope);
        var frontEl = fieldFront(scope);
        if (!obraEl || !frontEl) return;

        var group = scope.querySelector('#front-field-group');
        var reqMark = scope.querySelector('#front-required-mark');
        var frontMap = parseFrontMap(obraEl);
        var allowEmptyForAdmin = obraEl.getAttribute('data-front-admin-allow-empty') === '1';
        var emptyLabelDefault = obraEl.getAttribute('data-front-empty-label') || 'Selecione a frente';

        function renderFrontOptions() {
            var obraId = String(obraEl.value || '').trim();
            var fronts = frontMap[obraId] || [];
            var previousValue = String(frontEl.value || '').trim();
            var previousText = '';
            if (frontEl.selectedIndex >= 0) {
                previousText = (frontEl.options[frontEl.selectedIndex] || {}).text || '';
            }

            frontEl.innerHTML = '';

            if (!obraId || !fronts.length) {
                frontEl.required = false;
                if (reqMark) reqMark.style.display = 'none';
                if (group) group.style.display = 'none';
                return;
            }

            if (group) group.style.display = '';

            var emptyOption = document.createElement('option');
            emptyOption.value = '';
            emptyOption.textContent = allowEmptyForAdmin ? 'Sem frente (obra toda)' : emptyLabelDefault;
            frontEl.appendChild(emptyOption);

            fronts.forEach(function (item) {
                var opt = document.createElement('option');
                opt.value = String(item.id);
                opt.textContent = item.name || ('Frente #' + String(item.id));
                frontEl.appendChild(opt);
            });

            var values = Array.prototype.map.call(frontEl.options, function (opt) { return opt.value; });
            if (previousValue && values.indexOf(previousValue) === -1) {
                var legacyOpt = document.createElement('option');
                legacyOpt.value = previousValue;
                legacyOpt.textContent = previousText || ('Frente #' + previousValue);
                frontEl.appendChild(legacyOpt);
            }
            if (previousValue) {
                frontEl.value = previousValue;
            }

            var shouldRequire = !allowEmptyForAdmin;
            frontEl.required = shouldRequire;
            frontEl.setAttribute('aria-required', shouldRequire ? 'true' : 'false');
            if (reqMark) reqMark.style.display = shouldRequire ? 'inline' : 'none';

            if (!allowEmptyForAdmin && fronts.length === 1) {
                frontEl.value = String(fronts[0].id);
            }
        }

        obraEl.addEventListener('change', function () {
            if (!allowEmptyForAdmin) {
                frontEl.value = '';
            }
            renderFrontOptions();
        });
        renderFrontOptions();
    }

    function fieldValorMed(scope) {
        return scope.querySelector('#id_valor_medicao');
    }

    function fieldValorEstimado(scope) {
        return scope.querySelector('#id_valor_estimado');
    }

    function parseMoneyInput(rawValue) {
        var raw = String(rawValue || '').trim();
        if (!raw) return null;

        raw = raw.replace(/\s+/g, '').replace(/^R\$\s?/, '');
        if (raw.indexOf(',') !== -1) {
            raw = raw.replace(/\./g, '').replace(',', '.');
        } else if ((raw.match(/\./g) || []).length > 1) {
            raw = raw.replace(/\./g, '');
        }

        var num = Number(raw);
        return Number.isFinite(num) ? num : null;
    }

    function formatMoneyPtBr(value) {
        return value.toLocaleString('pt-BR', {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2
        });
    }

    function normalizeMoneyField(el) {
        if (!el) return true;
        var raw = (el.value || '').trim();
        if (!raw) {
            el.value = '';
            return true;
        }
        var parsed = parseMoneyInput(raw);
        if (parsed === null) return false;
        el.value = parsed.toFixed(2);
        return true;
    }

    function bindMoneyFieldDisplay(el) {
        if (!el) return;
        var initialParsed = parseMoneyInput(el.value);
        if (initialParsed !== null) {
            el.value = formatMoneyPtBr(initialParsed);
        }
        el.addEventListener('focus', function () {
            var parsed = parseMoneyInput(el.value);
            if (parsed === null) return;
            el.value = parsed.toString().replace('.', ',');
        });
        el.addEventListener('blur', function () {
            var raw = (el.value || '').trim();
            if (!raw) return;
            var parsed = parseMoneyInput(raw);
            if (parsed === null) return;
            el.value = formatMoneyPtBr(parsed);
        });
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
                var valorEstimado = fieldValorEstimado(scope);
                if (valorEstimado && !normalizeMoneyField(valorEstimado)) {
                    valorEstimado.setCustomValidity('Informe um valor estimado válido.');
                    ev.preventDefault();
                    ev.stopImmediatePropagation();
                    valorEstimado.reportValidity();
                    return;
                }
                if (tipo.value !== 'medicao') return;
                var el = fieldValorMed(scope);
                if (!el) return;
                var n = parseMoneyInput(el.value);
                if (n === null || n <= 0) {
                    el.setCustomValidity('Informe o valor de medição (maior que zero).');
                    ev.preventDefault();
                    ev.stopImmediatePropagation();
                    el.reportValidity();
                } else {
                    el.setCustomValidity('');
                    el.value = n.toFixed(2);
                }
            });
        }
        var elVm = fieldValorMed(scope);
        if (elVm) {
            elVm.addEventListener('input', function () {
                elVm.setCustomValidity('');
            });
            bindMoneyFieldDisplay(elVm);
        }
        var elVe = fieldValorEstimado(scope);
        if (elVe) {
            elVe.addEventListener('input', function () {
                elVe.setCustomValidity('');
            });
            bindMoneyFieldDisplay(elVe);
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
        bindFrontByObra(scope);
        bindValorMedicao(scope);
        bindAnexosFileQueue(scope);
        if (!opts || !opts.skipSubmitLock) bindSubmitLock(scope);
    };
})(typeof window !== 'undefined' ? window : this);
