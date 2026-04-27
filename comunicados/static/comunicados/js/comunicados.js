/**
 * Comunicados administrativos — modal global (usuário autenticado).
 */
(function () {
  'use strict';

  var API_PENDENTES = '/comunicados/api/pendentes/';
  var API_REGISTRAR = '/comunicados/api/registrar/';

  function getCookie(name) {
    var cookieValue = null;
    if (document.cookie && document.cookie !== '') {
      var cookies = document.cookie.split(';');
      for (var i = 0; i < cookies.length; i++) {
        var cookie = cookies[i].trim();
        if (cookie.substring(0, name.length + 1) === name + '=') {
          cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
          break;
        }
      }
    }
    return cookieValue;
  }

  function getCsrfToken() {
    var meta = document.querySelector('meta[name="csrf-token"]');
    if (meta && meta.getAttribute('content')) {
      return meta.getAttribute('content');
    }
    var inp = document.querySelector('[name="csrfmiddlewaretoken"]');
    if (inp && inp.value) {
      return inp.value;
    }
    if (typeof window.__LPLAN_CSRF_TOKEN__ === 'string' && window.__LPLAN_CSRF_TOKEN__) {
      return window.__LPLAN_CSRF_TOKEN__;
    }
    return getCookie('csrftoken');
  }

  var root = document.getElementById('comunicados-root');
  if (!root) {
    return;
  }

  var elOverlay = document.getElementById('comunicados-overlay');
  var elDialog = document.getElementById('comunicados-dialog');
  var elHeader = document.getElementById('comunicados-header');
  var elTitulo = document.getElementById('comunicados-titulo');
  var elSubtitulo = document.getElementById('comunicados-subtitulo');
  var elClose = document.getElementById('comunicados-close');
  var elBody = document.getElementById('comunicados-body');
  var elActions = document.getElementById('comunicados-actions');
  var elNuncaWrap = document.getElementById('comunicados-nunca-wrap');
  var elNunca = document.getElementById('comunicados-nunca');

  var elIntercept = document.getElementById('comunicados-intercept');
  var elInterceptMsg = document.getElementById('comunicados-intercept-msg');
  var elInterceptPrimary = document.getElementById('comunicados-intercept-primary');
  var elInterceptSecondary = document.getElementById('comunicados-intercept-secondary');
  var elInterceptBackdrop = document.getElementById('comunicados-intercept-backdrop');

  var currentComunicado = null;
  var interceptOpen = false;
  var interceptPrimaryHandler = null;

  /** TEXTO / IMAGEM / IMAGEM_LINK: pede confirmação de leitura ao fechar (diálogo). */
  function interceptLeituraTiposSimples(c) {
    if (!c || !c.exige_confirmacao) {
      return false;
    }
    var t = c.tipo_conteudo || 'TEXTO';
    return t === 'TEXTO' || t === 'IMAGEM' || t === 'IMAGEM_LINK';
  }

  /** FORMULÁRIO com resposta obrigatória: não fechar até enviar. */
  function bloqueiaFecharAteResposta(c) {
    if (!c || !c.exige_resposta) {
      return false;
    }
    var t = c.tipo_conteudo || 'TEXTO';
    return t === 'FORMULARIO';
  }

  function closeInterceptUi() {
    interceptOpen = false;
    interceptPrimaryHandler = null;
    root.classList.remove('comunicados-root--intercept');
    if (elIntercept) {
      elIntercept.setAttribute('hidden', '');
      elIntercept.classList.remove('comunicados-intercept--open');
      elIntercept.setAttribute('aria-hidden', 'true');
    }
  }

  function openIntercept(message, primaryLabel, onPrimary) {
    if (!elIntercept || !elInterceptMsg || !elInterceptPrimary) {
      if (onPrimary) {
        onPrimary();
      }
      return;
    }
    interceptOpen = true;
    interceptPrimaryHandler = onPrimary;
    elInterceptMsg.textContent = message;
    elInterceptPrimary.textContent = primaryLabel;
    elIntercept.removeAttribute('hidden');
    elIntercept.classList.add('comunicados-intercept--open');
    elIntercept.setAttribute('aria-hidden', 'false');
    root.classList.add('comunicados-root--intercept');
    try {
      elInterceptPrimary.focus();
    } catch (e0) {}
  }

  function tentarFecharComOpcaoLeitura(acao, resposta) {
    var c = currentComunicado;
    if (!c) {
      return;
    }
    if (interceptLeituraTiposSimples(c)) {
      var acaoLeitura = acao;
      var respostaLeitura = resposta;
      openIntercept('Tem certeza que já leu?', 'Sim, já li', function () {
        if (!currentComunicado) {
          return;
        }
        if (acaoLeitura === 'fechou') {
          fecharModalERegistrar('confirmou', respostaLeitura);
        } else {
          fecharModalERegistrar(acaoLeitura, respostaLeitura);
        }
      });
      return;
    }
    fecharModalERegistrar(acao, resposta);
  }

  function tipoConteudoSemEnvio(t) {
    return t === 'TEXTO' || t === 'IMAGEM' || t === 'IMAGEM_LINK';
  }

  function canDismissOverlay(c) {
    if (!c) {
      return false;
    }
    var t = c.tipo_conteudo || 'TEXTO';
    if (!tipoConteudoSemEnvio(t) && !c.pode_fechar) {
      return false;
    }
    if (bloqueiaFecharAteResposta(c)) {
      return false;
    }
    return true;
  }

  function setDestaqueClasses(c) {
    var d = c.destaque_visual || 'PADRAO';
    elDialog.className = 'comunicados-destaque-' + d;
    /* O CSS usa .comunicados-header--padrao (minúsculas); o valor do modelo é PADRAO. */
    var hdrMap = {
      PADRAO: 'padrao',
      INFO: 'INFO',
      ALERTA: 'ALERTA',
      CRITICO: 'CRITICO',
      SUCESSO: 'SUCESSO',
    };
    var h = hdrMap[d] || 'padrao';
    elHeader.className = 'comunicados-header-bar comunicados-header--' + h;
  }

  function clearNode(node) {
    while (node.firstChild) {
      node.removeChild(node.firstChild);
    }
  }

  function appendTextBlock(container, text) {
    if (!text) {
      return;
    }
    var p = document.createElement('p');
    p.style.whiteSpace = 'pre-wrap';
    p.style.margin = '0 0 0.75rem';
    p.textContent = text;
    container.appendChild(p);
  }

  function buildBody(c) {
    clearNode(elBody);
    var tipo = c.tipo_conteudo || 'TEXTO';

    if (tipo === 'TEXTO') {
      appendTextBlock(elBody, c.texto_principal || '');
      return;
    }

    if (tipo === 'IMAGEM' || tipo === 'IMAGEM_LINK') {
      if (c.titulo_visivel) {
        var h = document.createElement('p');
        h.style.fontWeight = '600';
        h.style.margin = '0 0 0.5rem';
        h.textContent = c.titulo_visivel;
        elBody.appendChild(h);
      }
      if (c.texto_principal) {
        appendTextBlock(elBody, c.texto_principal);
      }
      var urlsImg = Array.isArray(c.imagens_urls) && c.imagens_urls.length
        ? c.imagens_urls
        : c.imagem_url
          ? [c.imagem_url]
          : [];
      urlsImg.forEach(function (src) {
        if (!src) {
          return;
        }
        var wrap = document.createElement('div');
        wrap.className = 'comunicados-img-wrap';
        if (tipo === 'IMAGEM_LINK' && c.link_destino) {
          var a = document.createElement('a');
          a.href = c.link_destino;
          a.target = '_blank';
          a.rel = 'noopener noreferrer';
          a.className = 'comunicados-img-link';
          var img = document.createElement('img');
          img.src = src;
          img.alt = c.titulo_visivel || 'Imagem do comunicado';
          a.appendChild(img);
          wrap.appendChild(a);
        } else {
          var img2 = document.createElement('img');
          img2.src = src;
          img2.alt = c.titulo_visivel || 'Imagem do comunicado';
          wrap.appendChild(img2);
        }
        elBody.appendChild(wrap);
      });
      return;
    }

    if (tipo === 'FORMULARIO') {
      appendTextBlock(elBody, c.texto_principal || '');
      var field = document.createElement('div');
      field.className = 'comunicados-field';
      var lab = document.createElement('label');
      lab.className = 'comunicados-label';
      lab.setAttribute('for', 'comunicados-resposta-field');
      lab.textContent = 'Sua resposta';
      var ta = document.createElement('textarea');
      ta.id = 'comunicados-resposta-field';
      ta.className = 'comunicados-textarea';
      ta.rows = 5;
      ta.setAttribute('autocomplete', 'off');
      field.appendChild(lab);
      field.appendChild(ta);
      elBody.appendChild(field);
      return;
    }

  }

  function buildFooterActions(c) {
    clearNode(elActions);
    var tipo = c.tipo_conteudo || 'TEXTO';
    var dismiss = canDismissOverlay(c);

    if (tipo === 'FORMULARIO') {
      var btnEnviar = document.createElement('button');
      btnEnviar.type = 'button';
      btnEnviar.className = 'comunicados-btn comunicados-btn--primary';
      btnEnviar.id = 'comunicados-btn-enviar';
      btnEnviar.textContent = 'Enviar';
      btnEnviar.disabled = c.exige_resposta === true;
      elActions.appendChild(btnEnviar);
      if (dismiss) {
        var btnF = document.createElement('button');
        btnF.type = 'button';
        btnF.className = 'comunicados-btn comunicados-btn--secondary';
        btnF.id = 'comunicados-btn-fechar-form';
        btnF.textContent = 'Fechar';
        elActions.appendChild(btnF);
      }
      return;
    }

    /* TEXTO, IMAGEM, IMAGEM_LINK */
    if (c.texto_botao && c.link_destino) {
      var a = document.createElement('a');
      a.className = 'comunicados-btn comunicados-btn--primary';
      a.href = c.link_destino;
      if (tipo === 'IMAGEM_LINK' || tipo === 'TEXTO') {
        a.target = '_blank';
        a.rel = 'noopener noreferrer';
      }
      a.textContent = c.texto_botao;
      elActions.appendChild(a);
    }
    if (dismiss) {
      var btnFechar = document.createElement('button');
      btnFechar.type = 'button';
      btnFechar.className = 'comunicados-btn comunicados-btn--secondary';
      btnFechar.id = 'comunicados-btn-fechar-simples';
      btnFechar.textContent = 'Fechar';
      elActions.appendChild(btnFechar);
    }
  }

  /** Sincroniza estado de botões que dependem de campos no body (um listener fixo; conteúdo do body muda a cada abertura). */
  function syncFormularioControles() {
    var c = currentComunicado;
    if (!c || c.tipo_conteudo !== 'FORMULARIO') {
      return;
    }
    var ta = document.getElementById('comunicados-resposta-field');
    var btnEnviar = document.getElementById('comunicados-btn-enviar');
    if (!btnEnviar || !c.exige_resposta) {
      return;
    }
    var ok = ta && ta.value.trim().length > 0;
    btnEnviar.disabled = !ok;
  }

  function afterExibirControles(c) {
    if (c.tipo_conteudo === 'FORMULARIO' && c.exige_resposta) {
      syncFormularioControles();
    }
  }

  function setModalOpen(open) {
    root.classList.toggle('comunicados--open', open);
    root.setAttribute('aria-hidden', open ? 'false' : 'true');
    if (open) {
      document.body.style.overflow = 'hidden';
    } else {
      document.body.style.overflow = '';
    }
  }

  function hideModal() {
    closeInterceptUi();
    currentComunicado = null;
    setModalOpen(false);
    clearNode(elBody);
    clearNode(elActions);
  }

  function onOverlayOrEscapeClose() {
    if (currentComunicado && canDismissOverlay(currentComunicado)) {
      tentarFecharComOpcaoLeitura('fechou');
    }
  }

  function exibirModal(comunicado) {
    if (!comunicado || !comunicado.id) {
      hideModal();
      return;
    }
    currentComunicado = comunicado;
    setDestaqueClasses(comunicado);

    elTitulo.textContent = comunicado.titulo_visivel || 'Comunicado';
    if (comunicado.subtitulo) {
      elSubtitulo.style.display = '';
      elSubtitulo.textContent = comunicado.subtitulo;
    } else {
      elSubtitulo.style.display = 'none';
      elSubtitulo.textContent = '';
    }

    if (canDismissOverlay(comunicado)) {
      elClose.style.display = '';
    } else {
      elClose.style.display = 'none';
    }

    buildBody(comunicado);
    buildFooterActions(comunicado);
    afterExibirControles(comunicado);

    if (comunicado.permitir_nao_mostrar_novamente) {
      elNuncaWrap.style.display = '';
    } else {
      elNuncaWrap.style.display = 'none';
    }

    setModalOpen(true);
    registrarVisualizou();
  }

  function jsonHeaders() {
    return {
      Accept: 'application/json',
      'Content-Type': 'application/json',
      'X-Requested-With': 'XMLHttpRequest',
      'X-CSRFToken': getCsrfToken() || '',
    };
  }

  /** Só ao abrir: não fecha o modal; falha não bloqueia UI. */
  function registrarVisualizou() {
    var cid = currentComunicado ? currentComunicado.id : null;
    if (!cid) {
      return;
    }
    var payload = { comunicado_id: cid, acao: 'visualizou' };
    fetch(API_REGISTRAR, {
      method: 'POST',
      credentials: 'same-origin',
      headers: jsonHeaders(),
      body: JSON.stringify(payload),
    })
      .then(function (r) {
        return r.text().then(function (text) {
          var data = {};
          if (text) {
            try {
              data = JSON.parse(text);
            } catch (parseErr) {}
          }
          return { ok: r.ok, status: r.status, data: data };
        });
      })
      .then(function (result) {
        if (!result.ok) {
          console.warn('[comunicados] registrar visualizou falhou', result.status, result.data);
        }
      })
      .catch(function (e) {
        console.warn('[comunicados] registrar visualizou erro', e);
      });
  }

  /**
   * Fecha o modal de imediato e envia o registo em segundo plano.
   * O fechamento não depende do POST (evita ficar preso por erro de rede/500).
   */
  function fecharModalERegistrar(acao, resposta) {
    var c = currentComunicado;
    if (!c) {
      return;
    }
    var cid = c.id;
    hideModal();
    postRegistroAposFechar(acao, resposta, cid);
  }

  function postRegistroAposFechar(acao, resposta, comunicadoId) {
    if (!comunicadoId) {
      return;
    }
    var payload = { comunicado_id: comunicadoId, acao: acao };
    if (acao === 'respondeu' && resposta) {
      payload.resposta = resposta;
    }

    fetch(API_REGISTRAR, {
      method: 'POST',
      credentials: 'same-origin',
      headers: jsonHeaders(),
      body: JSON.stringify(payload),
    })
      .then(function (r) {
        return r.text().then(function (text) {
          var data = {};
          if (text) {
            try {
              data = JSON.parse(text);
            } catch (parseErr) {}
          }
          return { ok: r.ok, status: r.status, data: data };
        });
      })
      .then(function (result) {
        if (!result.ok) {
          console.warn('[comunicados] registrar falhou (modal já fechado)', result.status, result.data);
        }
        if (result.ok && result.data && result.data.proximo_pendente) {
          fetchPendentesEProximo();
        }
      })
      .catch(function (e) {
        console.warn('[comunicados] registrar erro (modal já fechado)', e);
      });
  }

  function fetchPendentesEProximo() {
    fetch(API_PENDENTES, {
      method: 'GET',
      credentials: 'same-origin',
      headers: {
        Accept: 'application/json',
        'X-Requested-With': 'XMLHttpRequest',
      },
    })
      .then(function (r) {
        return r.json();
      })
      .then(function (data) {
        if (data.tem_pendente && data.comunicado) {
          exibirModal(data.comunicado);
        } else {
          hideModal();
        }
      })
      .catch(function (e) {
        console.warn('[comunicados] pendentes após ação', e);
        hideModal();
      });
  }

  function iniciar() {
    fetch(API_PENDENTES, {
      method: 'GET',
      credentials: 'same-origin',
      headers: {
        Accept: 'application/json',
        'X-Requested-With': 'XMLHttpRequest',
      },
    })
      .then(function (r) {
        return r.json();
      })
      .then(function (data) {
        if (data.tem_pendente && data.comunicado) {
          exibirModal(data.comunicado);
        }
      })
      .catch(function (e) {
        console.warn('[comunicados] pendentes', e);
      });
  }

  /** Um único listener no root: elementos estáveis no template; botões do rodapé são filhos de #comunicados-actions (sempre o mesmo nó). */
  root.addEventListener('click', function (e) {
    if (!root.classList.contains('comunicados--open')) {
      return;
    }
    var t = e.target;

    if (t.closest && t.closest('#comunicados-close')) {
      if (currentComunicado && canDismissOverlay(currentComunicado)) {
        e.preventDefault();
        tentarFecharComOpcaoLeitura('fechou');
      }
      return;
    }

    if (elOverlay && t === elOverlay) {
      onOverlayOrEscapeClose();
      return;
    }

    if (t.closest && t.closest('#comunicados-nunca')) {
      e.preventDefault();
      tentarFecharComOpcaoLeitura('nao_mostrar_novamente');
      return;
    }

    var btn = t.closest ? t.closest('button') : null;
    if (btn && elActions && elActions.contains(btn)) {
      var bid = btn.id;
      if (bid === 'comunicados-btn-fechar-simples' || bid === 'comunicados-btn-fechar-form') {
        e.preventDefault();
        tentarFecharComOpcaoLeitura('fechou');
        return;
      }
      if (bid === 'comunicados-btn-enviar') {
        e.preventDefault();
        var ta = document.getElementById('comunicados-resposta-field');
        var txt = ta ? ta.value.trim() : '';
        if (!txt) {
          return;
        }
        fecharModalERegistrar('respondeu', txt);
        return;
      }
    }
  });

  elBody.addEventListener('input', function (e) {
    if (e.target && e.target.id === 'comunicados-resposta-field') {
      syncFormularioControles();
    }
  });

  document.addEventListener('keydown', function (e) {
    if (e.key !== 'Escape') {
      return;
    }
    if (interceptOpen) {
      e.preventDefault();
      closeInterceptUi();
      return;
    }
    if (!root.classList.contains('comunicados--open')) {
      return;
    }
    if (currentComunicado && canDismissOverlay(currentComunicado)) {
      e.preventDefault();
      tentarFecharComOpcaoLeitura('fechou');
    } else {
      e.preventDefault();
    }
  });

  if (elInterceptPrimary) {
    elInterceptPrimary.addEventListener('click', function (e) {
      e.preventDefault();
      e.stopPropagation();
      if (!interceptOpen) {
        return;
      }
      var fn = interceptPrimaryHandler;
      closeInterceptUi();
      if (fn) {
        fn();
      }
    });
  }
  function interceptVoltar(ev) {
    if (ev) {
      ev.preventDefault();
      ev.stopPropagation();
    }
    closeInterceptUi();
  }
  if (elInterceptSecondary) {
    elInterceptSecondary.addEventListener('click', interceptVoltar);
  }
  if (elInterceptBackdrop) {
    elInterceptBackdrop.addEventListener('click', interceptVoltar);
  }

  function boot() {
    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', iniciar);
    } else {
      iniciar();
    }
  }
  boot();

  /** Sincroniza com o servidor quando o navegador restaura a página a partir da cache (botão Voltar). */
  window.addEventListener('pageshow', function (ev) {
    if (!ev.persisted) {
      return;
    }
    fetchPendentesEProximo();
  });
})();
