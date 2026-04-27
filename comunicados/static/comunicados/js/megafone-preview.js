/**
 * Pré-visualização do Megafone no painel (criar/editar) — replica a lógica visual de comunicados.js.
 */
(function () {
  'use strict';

  var root = document.getElementById('megafone-prev-root');
  if (!root) {
    return;
  }

  var elOverlay = document.getElementById('megafone-prev-overlay');
  var elDialog = document.getElementById('megafone-prev-dialog');
  var elHeader = document.getElementById('megafone-prev-header');
  var elTitulo = document.getElementById('megafone-prev-titulo');
  var elSubtitulo = document.getElementById('megafone-prev-subtitulo');
  var elBody = document.getElementById('megafone-prev-body');
  var elActions = document.getElementById('megafone-prev-actions');
  var btnClose = document.getElementById('megafone-prev-close');
  var btnOpen = document.getElementById('btn-megafone-prev');
  /** URLs blob dos ficheiros escolhidos — libertar ao fechar. */
  var lastBlobPreviewUrls = [];

  function revokeBlobPreviewUrls() {
    lastBlobPreviewUrls.forEach(function (u) {
      try {
        URL.revokeObjectURL(u);
      } catch (e) {
        /* noop */
      }
    });
    lastBlobPreviewUrls = [];
  }

  function val(id) {
    var e = document.getElementById(id);
    return e ? String(e.value || '').trim() : '';
  }

  function chk(id) {
    var e = document.getElementById(id);
    return !!(e && e.checked);
  }

  function totalImagensForms(formRoot) {
    var tf = formRoot.querySelector('input[name="imagens-TOTAL_FORMS"]');
    return tf ? parseInt(tf.value, 10) || 0 : 0;
  }

  function collectPayload() {
    var tipo = val('id_tipo_conteudo') || 'TEXTO';
    var formRoot = document.getElementById('form-comunicado');
    var imagensUrls = [];
    revokeBlobPreviewUrls();
    if (formRoot) {
      var useSlots = !!document.getElementById('comunicado-imagem-slot-0');
      if (useSlots) {
        var total = totalImagensForms(formRoot);
        for (var i = 0; i < total; i++) {
          var del = formRoot.querySelector('#id_imagens-' + i + '-DELETE');
          if (del && del.checked) {
            continue;
          }
          var finp = formRoot.querySelector('#id_imagens-' + i + '-arquivo');
          if (finp && finp.files && finp.files[0]) {
            try {
              var u = URL.createObjectURL(finp.files[0]);
              lastBlobPreviewUrls.push(u);
              imagensUrls.push(u);
            } catch (e) {
              /* noop */
            }
          } else {
            var slot = document.getElementById('comunicado-imagem-slot-' + i);
            var du = slot && slot.getAttribute('data-preview-url');
            if (du) {
              imagensUrls.push(du);
            }
          }
        }
      } else {
        formRoot.querySelectorAll('input[type="file"][name^="imagens-"][name$="-arquivo"]').forEach(function (inp) {
          if (inp.files && inp.files[0]) {
            try {
              var u2 = URL.createObjectURL(inp.files[0]);
              lastBlobPreviewUrls.push(u2);
              imagensUrls.push(u2);
            } catch (e) {
              /* noop */
            }
          }
        });
      }
    }
    var imagemUrl = '';
    if (imagensUrls.length) {
      imagemUrl = imagensUrls[0];
    } else if (Array.isArray(window.__MEGAFONE_PREVIEW_IMG_URLS__) && window.__MEGAFONE_PREVIEW_IMG_URLS__.length) {
      imagensUrls = window.__MEGAFONE_PREVIEW_IMG_URLS__.slice();
      imagemUrl = imagensUrls[0];
    } else if (typeof window.__MEGAFONE_PREVIEW_IMG_URL__ === 'string' && window.__MEGAFONE_PREVIEW_IMG_URL__) {
      imagemUrl = window.__MEGAFONE_PREVIEW_IMG_URL__;
      imagensUrls = [imagemUrl];
    }
    return {
      tipo_conteudo: tipo,
      titulo_visivel: val('id_titulo_visivel'),
      subtitulo: val('id_subtitulo'),
      texto_principal: document.getElementById('id_texto_principal')
        ? document.getElementById('id_texto_principal').value
        : '',
      imagem_url: imagemUrl,
      imagens_urls: imagensUrls,
      link_destino: val('id_link_destino'),
      texto_botao: val('id_texto_botao'),
      destaque_visual: val('id_destaque_visual') || 'PADRAO',
      pode_fechar: chk('id_pode_fechar'),
      exige_confirmacao: chk('id_exige_confirmacao'),
      exige_resposta: chk('id_exige_resposta'),
      permitir_nao_mostrar_novamente: chk('id_permitir_nao_mostrar_novamente'),
    };
  }

  function bloqueiaFecharAteResposta(c) {
    if (!c.exige_resposta) {
      return false;
    }
    var t = c.tipo_conteudo || 'TEXTO';
    return t === 'FORMULARIO';
  }

  function tipoConteudoSemEnvio(t) {
    return t === 'TEXTO' || t === 'IMAGEM' || t === 'IMAGEM_LINK';
  }

  function canDismissOverlay(c) {
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
      if (urlsImg.length) {
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
      } else {
        var av = document.createElement('p');
        av.style.color = '#94a3b8';
        av.style.fontSize = '0.875rem';
        av.textContent = '(Sem imagem selecionada — obrigatório para publicar este tipo.)';
        elBody.appendChild(av);
      }
      return;
    }

    if (tipo === 'FORMULARIO') {
      appendTextBlock(elBody, c.texto_principal || '');
      var field = document.createElement('div');
      field.className = 'comunicados-field';
      var lab = document.createElement('label');
      lab.className = 'comunicados-label';
      lab.setAttribute('for', 'megafone-prev-resposta-field');
      lab.textContent = 'Sua resposta';
      var ta = document.createElement('textarea');
      ta.id = 'megafone-prev-resposta-field';
      ta.className = 'comunicados-textarea';
      ta.rows = 5;
      ta.setAttribute('autocomplete', 'off');
      ta.disabled = true;
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
      btnEnviar.textContent = 'Enviar';
      btnEnviar.disabled = c.exige_resposta === true;
      elActions.appendChild(btnEnviar);
      if (dismiss) {
        var btnF = document.createElement('button');
        btnF.type = 'button';
        btnF.className = 'comunicados-btn comunicados-btn--secondary';
        btnF.textContent = 'Fechar';
        elActions.appendChild(btnF);
      }
      return;
    }

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
      btnFechar.textContent = 'Fechar';
      elActions.appendChild(btnFechar);
    }
  }

  /** No Megafone real, o rodapé usa delegação em #comunicados-root; aqui os botões são criados de novo a cada abertura. */
  function bindFooterFecharButtons() {
    if (!elActions) {
      return;
    }
    elActions.querySelectorAll('button.comunicados-btn--secondary').forEach(function (btn) {
      if (btn.textContent.trim() === 'Fechar') {
        btn.addEventListener('click', closePreview);
      }
    });
  }

  function openPreview() {
    var c = collectPayload();
    if (!c) {
      return;
    }
    setDestaqueClasses(c);
    elTitulo.textContent = c.titulo_visivel || 'Comunicado';
    if (c.subtitulo) {
      elSubtitulo.style.display = '';
      elSubtitulo.textContent = c.subtitulo;
    } else {
      elSubtitulo.style.display = 'none';
      elSubtitulo.textContent = '';
    }
    if (canDismissOverlay(c)) {
      btnClose.style.display = '';
    } else {
      btnClose.style.display = 'none';
    }
    buildBody(c);
    buildFooterActions(c);
    bindFooterFecharButtons();
    root.classList.add('megafone-prev--open');
    root.setAttribute('aria-hidden', 'false');
    document.body.style.overflow = 'hidden';
  }

  function closePreview() {
    root.classList.remove('megafone-prev--open');
    root.setAttribute('aria-hidden', 'true');
    document.body.style.overflow = '';
    revokeBlobPreviewUrls();
  }

  if (btnOpen) {
    btnOpen.addEventListener('click', function () {
      openPreview();
    });
  }
  if (btnClose) {
    btnClose.addEventListener('click', closePreview);
  }
  if (elOverlay) {
    elOverlay.addEventListener('click', function () {
      var c = collectPayload();
      if (c && canDismissOverlay(c)) {
        closePreview();
      }
    });
  }
  document.addEventListener('keydown', function (e) {
    if (e.key !== 'Escape' || !root.classList.contains('megafone-prev--open')) {
      return;
    }
    var c = collectPayload();
    if (c && canDismissOverlay(c)) {
      e.preventDefault();
      closePreview();
    }
  });
})();
