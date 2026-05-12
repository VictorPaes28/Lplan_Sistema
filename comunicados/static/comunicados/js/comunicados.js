/**
 * Comunicados administrativos — modal global (usuário autenticado).
 */
(function () {
  'use strict';

  var API_PENDENTES = '/comunicados/api/pendentes/';
  var API_REGISTRAR = '/comunicados/api/registrar/';

  /** No painel /comunicados/ o criador costuma estar no público-alvo — não abrir o Megafone aqui. */
  function skipMegafoneNestaPagina() {
    var p = typeof location.pathname === 'string' ? location.pathname : '';
    return p.indexOf('/comunicados/') === 0;
  }

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
  var elTipoBadge = document.getElementById('comunicados-tipo-badge');
  var elTopbarDate = document.getElementById('comunicados-topbar-date');
  var elClose = document.getElementById('comunicados-close');
  var elBody = document.getElementById('comunicados-body');
  var elFooter = document.getElementById('comunicados-footer');
  var elActions = document.getElementById('comunicados-actions');
  var elNuncaWrap = document.getElementById('comunicados-nunca-wrap');
  var elNunca = document.getElementById('comunicados-nunca');
  var elLightbox = document.getElementById('comunicados-lightbox');
  var elLightboxImg = document.getElementById('comunicados-lightbox-img');
  var elLightboxClose = document.getElementById('comunicados-lightbox-close');

  var elIntercept = document.getElementById('comunicados-intercept');
  var elInterceptMsg = document.getElementById('comunicados-intercept-msg');
  var elInterceptPrimary = document.getElementById('comunicados-intercept-primary');
  var elInterceptSecondary = document.getElementById('comunicados-intercept-secondary');
  var elInterceptBackdrop = document.getElementById('comunicados-intercept-backdrop');

  var currentComunicado = null;
  var interceptOpen = false;
  var interceptPrimaryHandler = null;
  var lightboxOpen = false;

  var SVG_TEXTO =
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>';
  var SVG_IMAGEM =
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="8.5" cy="8.5" r="1.5"/><polyline points="21 15 16 10 5 21"/></svg>';
  var SVG_LINK =
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M10 13a5 5 0 007.54.54l3-3a5 5 0 00-7.07-7.07l-1.72 1.71"/><path d="M14 11a5 5 0 00-7.54-.54l-3 3a5 5 0 007.07 7.07l1.71-1.71"/></svg>';
  var SVG_FORM =
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M9 11l3 3L22 4"/><path d="M21 12v7a2 2 0 01-2 2H5a2 2 0 01-2-2V5a2 2 0 012-2h11"/></svg>';
  var SVG_LINK_BTN =
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M18 13v6a2 2 0 01-2 2H5a2 2 0 01-2-2V8a2 2 0 012-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/></svg>';

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
    var tipo = c.tipo_conteudo || 'TEXTO';
    var map = {
      TEXTO: 'tipo-texto',
      IMAGEM: 'tipo-imagem',
      IMAGEM_LINK: 'tipo-link',
      FORMULARIO: 'tipo-form',
    };
    var cls = map[tipo] || 'tipo-texto';
    elDialog.className = 'com-modal ' + cls;
  }

  function updateTipoBadge(c) {
    if (!elTipoBadge) {
      return;
    }
    var tipo = c.tipo_conteudo || 'TEXTO';
    var cfg = {
      TEXTO: { label: 'Texto', svg: SVG_TEXTO },
      IMAGEM: { label: 'Imagem', svg: SVG_IMAGEM },
      IMAGEM_LINK: { label: 'Com link', svg: SVG_LINK },
      FORMULARIO: { label: 'Formulário', svg: SVG_FORM },
    };
    var x = cfg[tipo] || cfg.TEXTO;
    elTipoBadge.innerHTML = x.svg;
    var sp = document.createElement('span');
    sp.textContent = x.label;
    elTipoBadge.appendChild(sp);
  }

  function updateTopbarDate(c) {
    if (!elTopbarDate) {
      return;
    }
    var d = c.criado_em || c.criadoEm || c.created_at;
    if (d) {
      elTopbarDate.textContent = typeof d === 'string' ? d : '';
      elTopbarDate.hidden = !elTopbarDate.textContent;
    } else {
      elTopbarDate.textContent = '';
      elTopbarDate.hidden = true;
    }
  }

  function closeLightbox() {
    if (!lightboxOpen) {
      return;
    }
    lightboxOpen = false;
    if (elLightbox) {
      elLightbox.classList.remove('com-lb-overlay--open');
      elLightbox.setAttribute('aria-hidden', 'true');
      elLightbox.setAttribute('hidden', '');
    }
    if (elLightboxImg) {
      elLightboxImg.removeAttribute('src');
    }
  }

  function openLightbox(src) {
    if (!elLightbox || !elLightboxImg || !src) {
      return;
    }
    lightboxOpen = true;
    elLightbox.removeAttribute('hidden');
    elLightboxImg.src = src;
    elLightbox.classList.add('com-lb-overlay--open');
    elLightbox.setAttribute('aria-hidden', 'false');
  }

  function clearNode(node) {
    while (node.firstChild) {
      node.removeChild(node.firstChild);
    }
  }

  function appendTituloSubtitulo(container, c) {
    var h = document.createElement('h2');
    h.id = 'comunicados-titulo';
    h.className = 'com-titulo';
    h.textContent = c.titulo_visivel || 'Comunicado';
    container.appendChild(h);
    if (c.subtitulo) {
      var s = document.createElement('div');
      s.className = 'com-subtitulo';
      s.textContent = c.subtitulo;
      container.appendChild(s);
    }
  }

  function appendMensagem(container, text) {
    if (!text) {
      return;
    }
    var d = document.createElement('div');
    d.className = 'com-mensagem';
    d.textContent = text;
    container.appendChild(d);
  }

  function appendImageGrid(container, urls, c) {
    var n = urls.length;
    if (!n) {
      return;
    }
    var altBase =
      c && c.titulo_visivel ? c.titulo_visivel : 'Imagem do comunicado';
    var grid = document.createElement('div');
    var cls = 'com-imgs n' + Math.min(n, 5);
    grid.className = cls;
    for (var i = 0; i < n; i++) {
      var src = urls[i];
      if (!src) {
        continue;
      }
      var img = document.createElement('img');
      img.className = 'com-img';
      img.src = src;
      img.alt = altBase;
      if ((n === 3 || n === 5) && i === 0) {
        img.classList.add('img-destaque');
      }
      grid.appendChild(img);
    }
    container.appendChild(grid);
  }

  function appendBodySpacer(container) {
    var sp = document.createElement('div');
    sp.className = 'com-body-spacer';
    container.appendChild(sp);
  }

  function buildBody(c) {
    clearNode(elBody);
    var tipo = c.tipo_conteudo || 'TEXTO';

    if (tipo === 'TEXTO') {
      appendTituloSubtitulo(elBody, c);
      appendMensagem(elBody, c.texto_principal || '');
      appendBodySpacer(elBody);
      return;
    }

    if (tipo === 'IMAGEM' || tipo === 'IMAGEM_LINK') {
      appendTituloSubtitulo(elBody, c);
      var urlsImg = Array.isArray(c.imagens_urls) && c.imagens_urls.length
        ? c.imagens_urls.slice(0, 5)
        : c.imagem_url
          ? [c.imagem_url]
          : [];
      appendImageGrid(elBody, urlsImg, c);
      appendMensagem(elBody, c.texto_principal || '');
      if (tipo === 'IMAGEM_LINK' && c.link_destino && c.texto_botao) {
        var wrap = document.createElement('div');
        wrap.className = 'com-link-wrap';
        var a = document.createElement('a');
        a.className = 'com-link-btn';
        a.href = c.link_destino;
        a.target = '_blank';
        a.rel = 'noopener noreferrer';
        a.innerHTML = SVG_LINK_BTN + '<span></span>';
        a.querySelector('span').textContent = c.texto_botao;
        wrap.appendChild(a);
        elBody.appendChild(wrap);
      }
      appendBodySpacer(elBody);
      return;
    }

    if (tipo === 'FORMULARIO') {
      appendTituloSubtitulo(elBody, c);
      appendMensagem(elBody, c.texto_principal || '');
      var field = document.createElement('div');
      field.className = 'com-form-section';
      var lab = document.createElement('div');
      lab.className = 'com-form-label';
      lab.textContent = 'Sua resposta';
      var ta = document.createElement('textarea');
      ta.id = 'comunicados-resposta-field';
      ta.className = 'com-textarea';
      ta.rows = 5;
      ta.setAttribute('autocomplete', 'off');
      ta.setAttribute('placeholder', 'Digite sua resposta aqui…');
      field.appendChild(lab);
      field.appendChild(ta);
      elBody.appendChild(field);
      appendBodySpacer(elBody);
      return;
    }
  }

  function podeMostrarBotaoFechar(c) {
    return c.pode_fechar !== false;
  }

  function buildFooterActions(c) {
    clearNode(elActions);
    var tipo = c.tipo_conteudo || 'TEXTO';
    var showFechar = podeMostrarBotaoFechar(c);
    var form = tipo === 'FORMULARIO';

    if (elFooter) {
      elFooter.classList.toggle('with-form', form && showFechar && c.exige_resposta === true);
    }

    if (form) {
      if (showFechar) {
        var btnF = document.createElement('button');
        btnF.type = 'button';
        btnF.className = 'comunicados-btn comunicados-btn--secondary';
        btnF.id = 'comunicados-btn-fechar-form';
        btnF.textContent = 'Fechar';
        elActions.appendChild(btnF);
      }
      if (c.exige_resposta) {
        var btnEnviar = document.createElement('button');
        btnEnviar.type = 'button';
        btnEnviar.className = 'comunicados-btn comunicados-btn--primary';
        btnEnviar.id = 'comunicados-btn-enviar';
        btnEnviar.textContent = 'Enviar resposta';
        btnEnviar.disabled = true;
        elActions.appendChild(btnEnviar);
      }
      return;
    }

    if (showFechar) {
      var btnFechar = document.createElement('button');
      btnFechar.type = 'button';
      btnFechar.className = 'comunicados-btn comunicados-btn--secondary';
      btnFechar.id = 'comunicados-btn-fechar-simples';
      btnFechar.textContent = 'Fechar';
      elActions.appendChild(btnFechar);
    }
    if (c.exige_confirmacao) {
      var btnConf = document.createElement('button');
      btnConf.type = 'button';
      btnConf.className = 'comunicados-btn comunicados-btn--primary';
      btnConf.id = 'comunicados-btn-confirmar-leitura';
      btnConf.textContent = 'Li e entendi';
      elActions.appendChild(btnConf);
    }
    if ((tipo === 'TEXTO' || tipo === 'IMAGEM') && c.texto_botao && c.link_destino) {
      var a = document.createElement('a');
      a.className = 'comunicados-btn comunicados-btn--primary';
      a.href = c.link_destino;
      a.target = '_blank';
      a.rel = 'noopener noreferrer';
      a.textContent = c.texto_botao;
      elActions.appendChild(a);
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
    closeLightbox();
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
    updateTipoBadge(comunicado);
    updateTopbarDate(comunicado);

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

  function parseRegistroErroMsg(result) {
    var d = result.data || {};
    return (
      d.erro ||
      d.error ||
      'Falha ao registar (' + result.status + '). Recarregue a página e tente novamente.'
    );
  }

  function postRegistroFetch(payload) {
    return fetch(API_REGISTRAR, {
      method: 'POST',
      credentials: 'same-origin',
      headers: jsonHeaders(),
      body: JSON.stringify(payload),
    }).then(function (r) {
      return r.text().then(function (text) {
        var data = {};
        if (text) {
          try {
            data = JSON.parse(text);
          } catch (parseErr) {}
        }
        return { ok: r.ok, status: r.status, data: data };
      });
    });
  }

  /** Só ao abrir: não fecha o modal; falha não bloqueia UI. */
  function registrarVisualizou() {
    var cid = currentComunicado ? currentComunicado.id : null;
    if (!cid) {
      return;
    }
    var payload = { comunicado_id: cid, acao: 'visualizou' };
    postRegistroFetch(payload)
      .then(function (result) {
        if (!result.ok) {
          console.warn('[comunicados] registrar visualizou falhou', result.status, result.data);
        }
      })
      .catch(function (e) {
        console.warn('[comunicados] registrar visualizou erro', e);
      });
  }

  function aguardarPostAntesDeFechar(acao) {
    return acao === 'respondeu' || acao === 'confirmou' || acao === 'nao_mostrar_novamente';
  }

  /**
   * Ações que alteram pendência de forma definitiva: só fechamos o modal após POST OK
   * (evita fechar com sucesso visual e 403 CSRF / erro de rede sem registo no servidor).
   */
  function registrarAntesFechar(acao, resposta, comunicadoId) {
    var payload = { comunicado_id: comunicadoId, acao: acao };
    if (acao === 'respondeu' && resposta) {
      payload.resposta = resposta;
    }
    var btn = document.getElementById('comunicados-btn-enviar');
    if (btn) {
      btn.disabled = true;
    }
    postRegistroFetch(payload)
      .then(function (result) {
        if (btn) {
          btn.disabled = false;
          syncFormularioControles();
        }
        if (!result.ok) {
          window.alert(parseRegistroErroMsg(result));
          return;
        }
        hideModal();
        if (result.data && result.data.proximo_pendente) {
          fetchPendentesEProximo();
        }
      })
      .catch(function (e) {
        if (btn) {
          btn.disabled = false;
          syncFormularioControles();
        }
        console.warn('[comunicados] registrar erro', e);
        window.alert('Erro de rede ao registar. Tente novamente.');
      });
  }

  /**
   * Fecha o modal e envia em segundo plano (ação "fechou" sem confirmação extra).
   * Resposta / confirmação / não mostrar: ver registrarAntesFechar.
   */
  function fecharModalERegistrar(acao, resposta) {
    var c = currentComunicado;
    if (!c) {
      return;
    }
    var cid = c.id;
    if (aguardarPostAntesDeFechar(acao)) {
      registrarAntesFechar(acao, resposta, cid);
      return;
    }
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

    postRegistroFetch(payload)
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

  function fetchPendentesHeaders() {
    return {
      Accept: 'application/json',
      'X-Requested-With': 'XMLHttpRequest',
    };
  }

  /**
   * GET /api/pendentes/ com retries curtos (útil após redirect de login: 403 ou sessão ainda a assentar).
   * @param {{ fecharSeVazio?: boolean, maxTry?: number, delayMs?: number }} opts
   */
  function fetchPendentesApi(opts) {
    opts = opts || {};
    var fecharSeVazio = !!opts.fecharSeVazio;
    var maxTry = typeof opts.maxTry === 'number' ? opts.maxTry : 3;
    var delayMs = typeof opts.delayMs === 'number' ? opts.delayMs : 400;

    function attempt(n) {
      return fetch(API_PENDENTES, {
        method: 'GET',
        credentials: 'same-origin',
        headers: fetchPendentesHeaders(),
      }).then(function (r) {
        if (
          !r.ok &&
          n < maxTry &&
          (r.status === 401 || r.status === 403 || r.status === 502 || r.status === 503 || r.status === 504)
        ) {
          return new Promise(function (resolve) {
            setTimeout(function () {
              resolve(attempt(n + 1));
            }, delayMs);
          });
        }
        if (!r.ok) {
          return Promise.reject(new Error('pendentes HTTP ' + r.status));
        }
        return r.text().then(function (text) {
          if (!text) {
            return {};
          }
          try {
            return JSON.parse(text);
          } catch (parseErr) {
            if (n < maxTry) {
              return new Promise(function (resolve) {
                setTimeout(function () {
                  resolve(attempt(n + 1));
                }, delayMs);
              });
            }
            return Promise.reject(parseErr);
          }
        });
      });
    }

    return attempt(1).then(function (data) {
      if (data && data.tem_pendente && data.comunicado) {
        exibirModal(data.comunicado);
      } else if (fecharSeVazio) {
        hideModal();
      }
    });
  }

  function fetchPendentesEProximo() {
    if (skipMegafoneNestaPagina()) {
      return;
    }
    fetchPendentesApi({ fecharSeVazio: true, maxTry: 2 }).catch(function (e) {
      console.warn('[comunicados] pendentes após ação', e);
      hideModal();
    });
  }

  var debouncePendentesTimer = null;

  /** Uma única janela após DOMContentLoaded / load / pageshow (evita rajadas e dá tempo à sessão pós-login). */
  function agendarCarregarPendentesInicial() {
    if (skipMegafoneNestaPagina()) {
      return;
    }
    clearTimeout(debouncePendentesTimer);
    debouncePendentesTimer = setTimeout(function () {
      debouncePendentesTimer = null;
      fetchPendentesApi({ fecharSeVazio: false, maxTry: 3 }).catch(function (e) {
        console.warn('[comunicados] pendentes', e);
      });
    }, 160);
  }

  /** Um único listener no root: elementos estáveis no template; botões do rodapé são filhos de #comunicados-actions (sempre o mesmo nó). */
  root.addEventListener('click', function (e) {
    if (!root.classList.contains('comunicados--open')) {
      return;
    }
    var t = e.target;

    if (lightboxOpen && elLightbox) {
      if (elLightboxClose && (t === elLightboxClose || (t.closest && t.closest('#comunicados-lightbox-close')))) {
        e.preventDefault();
        closeLightbox();
        return;
      }
      if (t === elLightbox) {
        e.preventDefault();
        closeLightbox();
        return;
      }
      if (t === elLightboxImg) {
        return;
      }
      if (elLightbox.contains(t)) {
        return;
      }
    }

    var imgLb = t.closest && t.closest('img.com-img');
    if (imgLb && elBody && elBody.contains(imgLb)) {
      e.preventDefault();
      openLightbox(imgLb.currentSrc || imgLb.src || '');
      return;
    }

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
      if (bid === 'comunicados-btn-confirmar-leitura') {
        e.preventDefault();
        fecharModalERegistrar('confirmou');
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
    if (lightboxOpen) {
      e.preventDefault();
      closeLightbox();
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
      document.addEventListener('DOMContentLoaded', agendarCarregarPendentesInicial);
    } else {
      agendarCarregarPendentesInicial();
    }
    window.addEventListener('load', agendarCarregarPendentesInicial);
  }
  boot();

  /** bfcache: reabrir; navegação normal: revalidar (HTML em cache / pós-login). */
  window.addEventListener('pageshow', function (ev) {
    if (skipMegafoneNestaPagina()) {
      return;
    }
    if (ev.persisted) {
      fetchPendentesEProximo();
      return;
    }
    agendarCarregarPendentesInicial();
  });
})();
