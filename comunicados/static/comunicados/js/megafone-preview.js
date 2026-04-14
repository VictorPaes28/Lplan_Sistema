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
  /** URL blob da imagem escolhida no file input — libertar ao fechar para não vazar memória. */
  var lastBlobPreviewUrl = null;

  function revokeBlobPreviewUrl() {
    if (lastBlobPreviewUrl) {
      try {
        URL.revokeObjectURL(lastBlobPreviewUrl);
      } catch (e) {
        /* noop */
      }
      lastBlobPreviewUrl = null;
    }
  }

  function val(id) {
    var e = document.getElementById(id);
    return e ? String(e.value || '').trim() : '';
  }

  function chk(id) {
    var e = document.getElementById(id);
    return !!(e && e.checked);
  }

  function collectPayload() {
    var tipo = val('id_tipo_conteudo') || 'TEXTO';
    var imgInput = document.getElementById('id_imagem');
    var imagemUrl = '';
    if (imgInput && imgInput.files && imgInput.files[0]) {
      try {
        revokeBlobPreviewUrl();
        imagemUrl = URL.createObjectURL(imgInput.files[0]);
        lastBlobPreviewUrl = imagemUrl;
      } catch (e) {
        imagemUrl = '';
      }
    } else if (typeof window.__MEGAFONE_PREVIEW_IMG_URL__ === 'string' && window.__MEGAFONE_PREVIEW_IMG_URL__) {
      revokeBlobPreviewUrl();
      imagemUrl = window.__MEGAFONE_PREVIEW_IMG_URL__;
    }
    return {
      tipo_conteudo: tipo,
      titulo_visivel: val('id_titulo_visivel'),
      subtitulo: val('id_subtitulo'),
      texto_principal: document.getElementById('id_texto_principal')
        ? document.getElementById('id_texto_principal').value
        : '',
      imagem_url: imagemUrl,
      link_destino: val('id_link_destino'),
      texto_botao: val('id_texto_botao'),
      destaque_visual: val('id_destaque_visual') || 'PADRAO',
      pode_fechar: chk('id_pode_fechar'),
      exige_confirmacao: chk('id_exige_confirmacao'),
      exige_resposta: chk('id_exige_resposta'),
      bloquear_ate_acao: chk('id_bloquear_ate_acao'),
      permitir_nao_mostrar_novamente: chk('id_permitir_nao_mostrar_novamente'),
    };
  }

  function bloqueiaFecharAteAcao(c) {
    if (!c.bloquear_ate_acao) {
      return false;
    }
    var t = c.tipo_conteudo || 'TEXTO';
    return t === 'CONFIRMACAO' || t === 'FORMULARIO';
  }

  function canDismissOverlay(c) {
    if (!c.pode_fechar) {
      return false;
    }
    if (bloqueiaFecharAteAcao(c)) {
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
      if (c.imagem_url) {
        var wrap = document.createElement('div');
        wrap.className = 'comunicados-img-wrap';
        if (tipo === 'IMAGEM_LINK' && c.link_destino) {
          var a = document.createElement('a');
          a.href = c.link_destino;
          a.target = '_blank';
          a.rel = 'noopener noreferrer';
          a.className = 'comunicados-img-link';
          var img = document.createElement('img');
          img.src = c.imagem_url;
          img.alt = c.titulo_visivel || 'Imagem do comunicado';
          a.appendChild(img);
          wrap.appendChild(a);
        } else {
          var img2 = document.createElement('img');
          img2.src = c.imagem_url;
          img2.alt = c.titulo_visivel || 'Imagem do comunicado';
          wrap.appendChild(img2);
        }
        elBody.appendChild(wrap);
      } else if (tipo === 'IMAGEM' || tipo === 'IMAGEM_LINK') {
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

    if (tipo === 'CONFIRMACAO') {
      appendTextBlock(elBody, c.texto_principal || '');
      var row = document.createElement('div');
      row.className = 'comunicados-check-row';
      var cb = document.createElement('input');
      cb.type = 'checkbox';
      cb.id = 'megafone-prev-checkbox-ciencia';
      cb.disabled = true;
      var lb = document.createElement('label');
      lb.setAttribute('for', 'megafone-prev-checkbox-ciencia');
      lb.style.cursor = 'default';
      lb.style.fontSize = '0.875rem';
      lb.textContent = 'Li e estou ciente';
      row.appendChild(cb);
      row.appendChild(lb);
      elBody.appendChild(row);
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
      btnEnviar.disabled = true;
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

    if (tipo === 'CONFIRMACAO') {
      var btnConf = document.createElement('button');
      btnConf.type = 'button';
      btnConf.className = 'comunicados-btn comunicados-btn--primary';
      btnConf.textContent = 'Confirmar';
      btnConf.disabled = true;
      elActions.appendChild(btnConf);
      if (dismiss) {
        var btnF2 = document.createElement('button');
        btnF2.type = 'button';
        btnF2.className = 'comunicados-btn comunicados-btn--secondary';
        btnF2.textContent = 'Fechar';
        elActions.appendChild(btnF2);
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
    revokeBlobPreviewUrl();
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
