(function () {
  var hub = document.querySelector('.rh-docs-hub');
  if (!hub) return;

  var modal = document.getElementById('rh-docs-modal');
  var dialog = modal ? modal.querySelector('.rh-docs-modal') : null;
  var modalAcao = document.getElementById('rh-docs-modal-acao');
  var modalTipoId = document.getElementById('rh-docs-modal-tipo-id');
  var cargoContext = document.getElementById('rh-docs-cargo-context');
  var previewUrl = hub.getAttribute('data-preview-url');

  var SCOPE_COPY = {
    todos: {
      hint: 'Entra em toda admissão, independente do cargo.',
      createSubtitle: 'Documento universal — vale para qualquer admissão.',
      readonly: 'Para todos os colaboradores',
    },
    por_cargo: {
      hintCriar: 'Marque um ou mais cargos abaixo. Também é possível ajustar depois na aba Por cargo.',
      hintEditar: 'O escopo não pode ser alterado. Vincule ou desvincule cargos na aba Por cargo.',
      createSubtitle: 'Documento extra — selecione os cargos que devem enviar este item.',
      readonly: 'Por cargo específico',
    },
  };

  function inferCategoria(nome) {
    var n = (nome || '').toLowerCase();
    if (n.indexOf('aso') >= 0 || n.indexOf('saúde') >= 0 || n.indexOf('saude') >= 0) return 'saude';
    if (n.indexOf('nr-') >= 0 || n.indexOf('nr ') === 0) return 'treinamentos';
    if (n.indexOf('comprovante') >= 0 || n.indexOf('fgts') >= 0 || n.indexOf('banc') >= 0) return 'comprovantes';
    if (/rg|cpf|título|titulo|certidão|certidao|pis|ctps|filhos|escolaridade/.test(n)) return 'pessoais';
    return 'outros';
  }

  function getScopeRadios() {
    return Array.prototype.slice.call(document.querySelectorAll('.js-docs-scope-radio'));
  }

  function getCargoPickers() {
    return Array.prototype.slice.call(document.querySelectorAll('.js-docs-cargo-pick'));
  }

  function setCargoPicks(ids, disabled) {
    var idSet = {};
    (ids || []).forEach(function (id) { idSet[String(id)] = true; });
    getCargoPickers().forEach(function (cb) {
      cb.checked = !!idSet[cb.value];
      cb.disabled = !!disabled;
    });
  }

  function setScope(aplica, mode, options) {
    options = options || {};
    var hidden = document.getElementById('id_aplica_a_modal');
    var scopeValue = aplica === 'por_cargo' ? 'por_cargo' : 'todos';
    if (hidden) hidden.value = scopeValue;

    var hint = document.getElementById('rh-docs-modal-scope-hint');
    var scopeOptions = document.getElementById('rh-docs-scope-options');
    var scopeReadonly = document.getElementById('rh-docs-modal-scope-readonly');
    var cargosPanel = document.getElementById('rh-docs-modal-cargos');
    var copy = SCOPE_COPY[scopeValue];
    var isEdit = mode === 'editar';

    getScopeRadios().forEach(function (radio) {
      radio.checked = radio.value === scopeValue;
      radio.disabled = isEdit;
    });

    if (scopeOptions) scopeOptions.hidden = isEdit;
    if (scopeReadonly) {
      scopeReadonly.hidden = !isEdit;
      scopeReadonly.textContent = copy.readonly;
    }

    if (hint) {
      hint.textContent = isEdit
        ? copy.hintEditar
        : (scopeValue === 'por_cargo' ? copy.hintCriar : copy.hint);
    }

    if (cargosPanel) {
      cargosPanel.hidden = scopeValue !== 'por_cargo';
    }

    if (scopeValue === 'por_cargo') {
      var picks = options.cargoIds || [];
      if (!picks.length && options.cargoContext) {
        picks = [options.cargoContext];
      }
      setCargoPicks(picks, isEdit);
    } else {
      setCargoPicks([], false);
    }

    return copy;
  }

  function openModal(mode, data) {
    if (!modal) return;
    modal.hidden = false;
    modal.setAttribute('aria-hidden', 'false');
    modal.classList.add('is-open');
    document.body.classList.add('rh-modal-open');
    if (modalAcao) modalAcao.value = mode === 'editar' ? 'editar' : 'criar';
    if (modalTipoId) modalTipoId.value = data && data.pk ? data.pk : '';

    var aplica = (data && data.aplica) || 'todos';
    var cargoIds = [];
    if (data && data.cargoIds) {
      cargoIds = String(data.cargoIds).split(',').filter(Boolean);
    }
    var scopeCopy = setScope(aplica, mode, {
      cargoContext: data && data.cargoContext,
      cargoIds: cargoIds,
    });

    var title = document.getElementById('rh-docs-modal-title');
    var subtitle = document.getElementById('rh-docs-modal-subtitle');
    if (title) title.textContent = mode === 'editar' ? 'Editar documento' : 'Novo documento';
    if (subtitle) {
      subtitle.textContent = mode === 'editar'
        ? 'Alterações valem para novas admissões e sincronizam as em andamento.'
        : (aplica === 'por_cargo' ? scopeCopy.createSubtitle : scopeCopy.hint);
    }

    var nome = document.getElementById('id_nome_modal');
    var categoria = document.getElementById('id_categoria_modal');
    var instrucoes = document.getElementById('id_instrucoes_modal');
    var temVal = document.getElementById('id_tem_validade_modal');
    var dias = document.getElementById('id_dias_validade_modal');
    var obr = document.getElementById('id_obrigatorio_modal');
    var ativo = document.getElementById('id_ativo_modal');
    if (nome) nome.value = (data && data.nome) || '';
    if (categoria) {
      categoria.value = (data && data.categoria) || (mode === 'criar' && nome && nome.value ? inferCategoria(nome.value) : 'outros');
    }
    if (instrucoes) instrucoes.value = (data && data.instrucoes) || '';
    if (temVal) temVal.checked = data ? data.temValidade === '1' : false;
    if (dias) dias.value = (data && data.dias) || 365;
    if (obr) obr.checked = data ? data.obrigatorio !== '0' : true;
    if (ativo) ativo.checked = data ? data.ativo !== '0' : true;
    if (cargoContext) cargoContext.value = (data && data.cargoContext) || '';
    syncValidade();
    if (nome) nome.focus();
  }

  function closeModal() {
    if (!modal) return;
    modal.classList.remove('is-open');
    modal.hidden = true;
    modal.setAttribute('aria-hidden', 'true');
    document.body.classList.remove('rh-modal-open');
    if (cargoContext) cargoContext.value = '';
    setCargoPicks([], false);
  }

  function syncValidade() {
    var tem = document.getElementById('id_tem_validade_modal');
    var panel = document.getElementById('rh-docs-validade-panel');
    var dias = document.getElementById('id_dias_validade_modal');
    var on = tem && tem.checked;
    if (panel) panel.hidden = !on;
    if (dias) dias.disabled = !on;
  }

  function onScopeRadioChange() {
    var selected = getScopeRadios().find(function (radio) { return radio.checked; });
    if (!selected) return;
    var acao = document.getElementById('rh-docs-modal-acao');
    var mode = acao && acao.value === 'editar' ? 'editar' : 'criar';
    var copy = setScope(selected.value, mode, {
      cargoContext: cargoContext ? cargoContext.value : '',
    });
    var subtitle = document.getElementById('rh-docs-modal-subtitle');
    if (subtitle && mode === 'criar') {
      subtitle.textContent = selected.value === 'por_cargo' ? copy.createSubtitle : copy.hint;
    }
  }

  document.getElementById('rh-docs-open-modal')?.addEventListener('click', function () {
    openModal('criar', {
      aplica: this.getAttribute('data-scope') || 'todos',
      cargoContext: this.getAttribute('data-cargo') || '',
    });
  });

  getScopeRadios().forEach(function (radio) {
    radio.addEventListener('change', onScopeRadioChange);
  });

  document.querySelectorAll('.js-docs-novo-cargo').forEach(function (btn) {
    btn.addEventListener('click', function () {
      openModal('criar', {
        aplica: 'por_cargo',
        cargoContext: btn.getAttribute('data-cargo'),
      });
    });
  });

  document.querySelectorAll('.js-docs-edit').forEach(function (btn) {
    btn.addEventListener('click', function () {
      openModal('editar', {
        pk: btn.getAttribute('data-pk'),
        nome: btn.getAttribute('data-nome'),
        aplica: btn.getAttribute('data-aplica'),
        categoria: btn.getAttribute('data-categoria'),
        instrucoes: btn.getAttribute('data-instrucoes') || '',
        temValidade: btn.getAttribute('data-tem-validade') || '0',
        dias: btn.getAttribute('data-dias') || '365',
        obrigatorio: btn.getAttribute('data-obrigatorio') || '1',
        ativo: btn.getAttribute('data-ativo') || '1',
        cargoIds: btn.getAttribute('data-cargo-ids') || '',
      });
    });
  });

  document.querySelectorAll('.js-docs-preset-dias').forEach(function (btn) {
    btn.addEventListener('click', function () {
      var dias = document.getElementById('id_dias_validade_modal');
      if (dias) dias.value = btn.getAttribute('data-dias');
    });
  });

  document.getElementById('id_nome_modal')?.addEventListener('blur', function () {
    var cat = document.getElementById('id_categoria_modal');
    var acao = document.getElementById('rh-docs-modal-acao');
    if (cat && acao && acao.value === 'criar' && cat.value === 'outros' && this.value.trim()) {
      cat.value = inferCategoria(this.value);
    }
  });

  ['rh-docs-modal-close', 'rh-docs-modal-cancel'].forEach(function (id) {
    document.getElementById(id)?.addEventListener('click', closeModal);
  });

  modal?.addEventListener('click', function (e) {
    if (e.target === modal) closeModal();
  });

  dialog?.addEventListener('click', function (e) {
    e.stopPropagation();
  });

  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape' && modal && !modal.hidden) closeModal();
  });

  document.getElementById('id_tem_validade_modal')?.addEventListener('change', syncValidade);

  function loadPreview() {
    if (!previewUrl) return;
    var cargoInput = document.querySelector('input[name="cargo_id"]');
    var cargoId = cargoInput ? cargoInput.value : '';
    if (!cargoId) return;

    fetch(previewUrl + '?cargo=' + encodeURIComponent(cargoId), {
      headers: { 'X-Requested-With': 'XMLHttpRequest' },
    })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        var totalEl = document.getElementById('rh-preview-total');
        var obrEl = document.getElementById('rh-preview-obr');
        var listEl = document.getElementById('rh-docs-preview-list');
        var ctxEl = document.getElementById('rh-docs-preview-context');
        if (totalEl) totalEl.textContent = data.total;
        if (obrEl) obrEl.textContent = data.obrigatorios;
        if (ctxEl && data.cargo_nome) ctxEl.textContent = data.cargo_nome;
        if (listEl) {
          listEl.innerHTML = '';
          (data.itens || []).forEach(function (item) {
            var li = document.createElement('li');
            li.className = 'rh-docs-preview__item rh-docs-preview__item--' + item.origem.toLowerCase();
            li.innerHTML =
              '<span class="rh-docs-preview__item-name">' + item.nome + '</span>' +
              '<span class="rh-docs-preview__item-tag">' + item.origem + '</span>';
            listEl.appendChild(li);
          });
        }
      })
      .catch(function () {});
  }

  document.querySelectorAll('.js-docs-cargo-check').forEach(function (cb) {
    cb.addEventListener('change', loadPreview);
  });

  if (document.getElementById('rh-docs-preview')) {
    loadPreview();
  }
})();
