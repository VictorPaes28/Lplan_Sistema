(function () {
  var modal = document.getElementById('modal-prazo-decisao');
  var bodyEl = document.getElementById('modal-prazo-decisao-body');
  var subtitleEl = document.getElementById('modal-prazo-decisao-subtitle');
  var perfilLink = document.getElementById('modal-prazo-decisao-perfil');
  var jsonUrlTpl = window.RH_PRAZO_DECISAO_JSON_TMPL || '';
  var currentPk = null;

  if (!modal || !bodyEl) return;

  function esc(v) {
    if (v == null || v === '') return '';
    var d = document.createElement('div');
    d.textContent = v;
    return d.innerHTML;
  }

  function getCsrf() {
    var input = document.querySelector('[name=csrfmiddlewaretoken]');
    if (input) return input.value;
    var match = document.cookie.match(/csrftoken=([^;]+)/);
    return match ? match[1] : '';
  }

  function fecharModal() {
    if (window.RhMotion) {
      window.RhMotion.closeOverlay(modal);
    } else {
      modal.classList.remove('open');
      modal.setAttribute('aria-hidden', 'true');
      document.body.classList.remove('rh-modal-open');
    }
    currentPk = null;
  }

  function abrirModal() {
    if (window.RhMotion) {
      window.RhMotion.closeAllOverlays();
      window.RhMotion.openOverlay(modal);
      return;
    }
    document.querySelectorAll('.modal-overlay.open').forEach(function (m) {
      m.classList.remove('open');
      m.setAttribute('aria-hidden', 'true');
    });
    modal.classList.add('open');
    modal.setAttribute('aria-hidden', 'false');
    document.body.classList.add('rh-modal-open');
  }

  function iconeAcao(codigo) {
    if (codigo === 'efetivar') return 'fa-user-check';
    if (codigo === 'converter') return 'fa-exchange-alt';
    if (codigo === 'prorrogar' || codigo === 'renovar') return 'fa-calendar-plus';
    if (codigo === 'desligar' || codigo === 'encerrar') return 'fa-times-circle';
    return 'fa-check';
  }

  function btnClassAcao(acao) {
    if (acao.danger) return 'rh-btn-danger-outline';
    return 'rh-btn-primary';
  }

  var CONFIRMACOES_ACAO = {
    converter: 'Converter este contrato de prazo determinado para indeterminado? O vínculo passará a CLT sem prazo a decidir.',
    renovar: 'Confirmar a renovação do contrato com a nova data de fim informada?',
    prorrogar: 'Prorrogar para o 2º período de experiência (até o marco D90)?',
    efetivar: 'Efetivar o colaborador em CLT indeterminado após o período de experiência?',
    desligar: 'Esta ação irá encerrar o contrato e desligar o colaborador. Deseja continuar?',
    encerrar: 'Esta ação irá encerrar o contrato e desligar o colaborador. Deseja continuar?',
  };

  function confirmarAcao(codigo, form) {
    var msg = CONFIRMACOES_ACAO[codigo];
    if (!msg) return true;
    if (codigo === 'renovar' || codigo === 'prorrogar') {
      var dataInput = form.querySelector('[name=nova_data_fim]');
      if (dataInput && dataInput.required && (!dataInput || !dataInput.value)) {
        var errEl = form.querySelector('.modal-rh-prazo-form-error');
        if (errEl) {
          errEl.textContent = 'Informe a nova data de fim.';
          errEl.hidden = false;
        }
        return false;
      }
      msg = msg + '\n\nNova data de fim: ' + dataInput.value.split('-').reverse().join('/');
    }
    return window.confirm(msg);
  }

  function redirecionarParaPerfil(colaboradorId) {
    var url = new URL(window.location.href);
    url.searchParams.set('abrir_colaborador', colaboradorId);
    url.searchParams.set('abrir_colaborador_tab', 'profissional');
    window.location.href = url.pathname + url.search;
  }

  function renderCampoData(valor) {
    return ''
      + '<label class="modal-rh-prazo-field">'
      + '<span class="modal-rh-prazo-field-label">Nova data de fim <span class="rh-required">*</span></span>'
      + '<input type="date" name="nova_data_fim" class="rh-input" required'
      + (valor ? ' value="' + esc(valor) + '"' : '')
      + '>'
      + '</label>';
  }

  function renderCampoMotivo(acao) {
    return ''
      + '<label class="modal-rh-prazo-field">'
      + '<span class="modal-rh-prazo-field-label">Motivo'
      + (acao.motivo_obrigatorio ? ' <span class="rh-required">*</span>' : '')
      + '</span>'
      + '<textarea name="motivo" class="rh-input rh-textarea modal-rh-prazo-textarea" rows="3" maxlength="500"'
      + (acao.motivo_obrigatorio ? ' required minlength="10"' : '')
      + ' placeholder="Descreva o motivo (mín. 10 caracteres)..."></textarea>'
      + '</label>';
  }

  function renderAcao(acao, data) {
    var html = '<article class="modal-rh-prazo-card">';
    html += '<h4 class="modal-rh-prazo-card-title">' + esc(acao.label) + '</h4>';
    html += '<form class="modal-rh-prazo-card-form js-prazo-decisao-form" data-post-url="' + esc(data.url_post) + '">';
    html += '<input type="hidden" name="acao" value="' + esc(acao.codigo) + '">';

    if (acao.precisa_data) {
      var sugerida = (acao.codigo === 'prorrogar' && data.data_fim_sugerida) ? data.data_fim_sugerida : '';
      html += renderCampoData(sugerida);
    }

    if (acao.motivo_obrigatorio || acao.danger) {
      html += renderCampoMotivo(acao);
    }

    html += '<div class="modal-rh-prazo-card-actions">';
    html += '<button type="submit" class="rh-btn ' + btnClassAcao(acao) + '">';
    html += '<i class="fas ' + iconeAcao(acao.codigo) + '" aria-hidden="true"></i>';
    html += '<span>Confirmar</span>';
    html += '</button>';
    html += '</div>';
    html += '<p class="modal-rh-prazo-form-error rh-form-errors" hidden></p>';
    html += '</form></article>';
    return html;
  }

  function renderConteudo(data) {
    var html = '';
    if (data.guia_texto) {
      html += '<div class="rh-banner rh-banner-info modal-rh-prazo-guia" role="note">';
      html += '<i class="fas fa-compass" aria-hidden="true"></i>';
      html += '<div><strong>O que decidir agora</strong><p class="rh-muted">' + esc(data.guia_texto) + '</p></div>';
      html += '</div>';
    }
    if (data.experiencia && data.experiencia.progresso) {
      html += '<p class="modal-rh-prazo-progresso"><strong>Progresso:</strong> ' + esc(data.experiencia.progresso);
      html += ' · ' + esc(data.experiencia.periodo_label || '') + '</p>';
    }
    if (data.ultima_decisao) {
      html += '<p class="modal-rh-prazo-ultima-decisao rh-muted">';
      html += 'Última decisão: ' + esc(data.ultima_decisao.acao) + ' por ' + esc(data.ultima_decisao.por);
      html += ' em ' + esc(data.ultima_decisao.em) + '</p>';
    }
    html += '<section class="modal-rh-prazo-info" aria-label="Resumo do contrato">';
    html += '<div class="modal-rh-prazo-info-grid">';
    html += '<div class="modal-rh-prazo-info-item"><span class="rh-field-label">Tipo</span><span class="rh-field-value">' + esc(data.tipo) + '</span></div>';
    html += '<div class="modal-rh-prazo-info-item"><span class="rh-field-label">Vigência</span><span class="rh-field-value">' + esc(data.vigencia) + '</span></div>';
    html += '<div class="modal-rh-prazo-info-item"><span class="rh-field-label">Renovação</span><span class="rh-field-value">' + esc(data.renovacao) + '</span></div>';
    html += '<div class="modal-rh-prazo-info-item"><span class="rh-field-label">Situação</span><span class="rh-field-value">' + esc(data.situacao) + '</span></div>';
    html += '</div>';

    if (data.limite_legal_dias) {
      var tipoRef = (data.tipo || '').toLowerCase();
      html += '<p class="modal-rh-prazo-legal-note">';
      html += '<i class="fas fa-info-circle" aria-hidden="true"></i>';
      html += '<span>Limite legal de referência para ' + esc(tipoRef) + ': ';
      html += '<strong>' + esc(String(data.limite_legal_dias)) + ' dias</strong>';
      html += ' (desde o início do período original).</span>';
      html += '</p>';
    }
    html += '</section>';

    html += '<section class="modal-rh-prazo-acoes" aria-label="Ações disponíveis">';
    html += '<div class="modal-rh-prazo-section-head">';
    html += '<h3 class="modal-rh-prazo-section-title">Ações disponíveis</h3>';
    html += '<p class="modal-rh-prazo-section-desc">Escolha a decisão apropriada para este vínculo.</p>';
    html += '</div>';
    html += '<div class="modal-rh-prazo-cards">';
    data.acoes.forEach(function (acao) {
      html += renderAcao(acao, data);
    });
    html += '</div></section>';

    bodyEl.innerHTML = html;
    subtitleEl.textContent = data.colaborador_nome + ' — ' + data.tipo;

    bodyEl.querySelectorAll('input[type="date"][name="nova_data_fim"]').forEach(function (input) {
      input.min = data.data_fim_min;
    });

    if (perfilLink) {
      perfilLink.href = data.url_perfil;
      perfilLink.hidden = false;
    }
  }

  function carregar(pk) {
    currentPk = pk;
    bodyEl.innerHTML = '<p class="rh-muted rh-prazo-decisao-loading">Carregando...</p>';
    if (perfilLink) perfilLink.hidden = true;
    subtitleEl.textContent = '';

    return fetch(jsonUrlTpl.replace('{pk}', pk), {
      headers: { 'X-Requested-With': 'XMLHttpRequest' },
    })
      .then(function (res) {
        if (!res.ok) throw new Error('not found');
        return res.json();
      })
      .then(function (data) {
        renderConteudo(data);
      })
      .catch(function () {
        bodyEl.innerHTML = '<p class="rh-form-errors rh-prazo-decisao-error">Não foi possível carregar os dados do prazo.</p>';
      });
  }

  function abrirModalPrazoDecisao(pk) {
    if (!pk) return;
    abrirModal();
    carregar(pk);
  }

  window.abrirModalPrazoDecisao = abrirModalPrazoDecisao;

  modal.querySelectorAll('.js-prazo-decisao-close').forEach(function (btn) {
    btn.addEventListener('click', fecharModal);
  });

  modal.addEventListener('click', function (e) {
    if (e.target === modal) fecharModal();
  });

  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape' && modal.classList.contains('open')) fecharModal();
  });

  document.addEventListener('click', function (e) {
    var trigger = e.target.closest('.js-rh-prazo-decidir');
    if (!trigger) return;
    e.preventDefault();
    if (trigger.hidden) return;
    if (trigger.dataset.podeDecidir === '0') return;
    var pk = trigger.dataset.prazoPk;
    if (pk) abrirModalPrazoDecisao(pk);
  });

  bodyEl.addEventListener('submit', function (e) {
    var form = e.target.closest('.js-prazo-decisao-form');
    if (!form) return;
    e.preventDefault();

    var acao = form.querySelector('[name=acao]');
    var acaoCodigo = acao ? acao.value : '';
    var motivoInput = form.querySelector('[name=motivo]');
    var errEl = form.querySelector('.modal-rh-prazo-form-error');

    if (acaoCodigo === 'encerrar' || acaoCodigo === 'desligar') {
      var motivoVal = motivoInput ? motivoInput.value.trim() : '';
      if (!motivoVal) {
        if (errEl) {
          errEl.textContent = 'Informe o motivo do encerramento.';
          errEl.hidden = false;
        }
        return;
      }
      if (motivoVal.length < 10) {
        if (errEl) {
          errEl.textContent = 'O motivo deve ter pelo menos 10 caracteres.';
          errEl.hidden = false;
        }
        return;
      }
    }

    if (!confirmarAcao(acaoCodigo, form)) {
      return;
    }

    var btn = form.querySelector('button[type=submit]');
    if (errEl) {
      errEl.hidden = true;
      errEl.textContent = '';
    }
    if (btn) btn.disabled = true;

    fetch(form.dataset.postUrl, {
      method: 'POST',
      headers: {
        'X-Requested-With': 'XMLHttpRequest',
        'X-CSRFToken': getCsrf(),
      },
      body: new FormData(form),
    })
      .then(function (res) {
        return res.json().then(function (data) {
          return { ok: res.ok, data: data };
        });
      })
      .then(function (result) {
        if (result.ok && result.data.ok) {
          fecharModal();
          if (result.data.colaborador_id) {
            redirecionarParaPerfil(result.data.colaborador_id);
          } else {
            window.location.reload();
          }
          return;
        }
        var msg = (result.data && result.data.message) || 'Não foi possível executar a ação.';
        if (errEl) {
          errEl.textContent = msg;
          errEl.hidden = false;
        } else {
          alert(msg);
        }
      })
      .catch(function () {
        if (errEl) {
          errEl.textContent = 'Erro ao processar. Tente novamente.';
          errEl.hidden = false;
        }
      })
      .finally(function () {
        if (btn) btn.disabled = false;
      });
  });

  var urlParams = new URLSearchParams(window.location.search);
  var abrirPk = urlParams.get('abrir_prazo_decisao');
  if (abrirPk) {
    abrirModalPrazoDecisao(abrirPk);
    var cleanUrl = new URL(window.location);
    cleanUrl.searchParams.delete('abrir_prazo_decisao');
    window.history.replaceState({}, '', cleanUrl);
  }
})();
