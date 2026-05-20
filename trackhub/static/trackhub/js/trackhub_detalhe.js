/**
 * Modal de detalhe TrackHub — edição inline (AJAX), padrão alinhado a impedimentos.
 */
(function () {
  'use strict';

  var root = document.getElementById('th-trackhub-detalhe-root');
  if (!root) return;

  var CSRF = root.dataset.csrf || '';
  var CURRENT_USER_ID = root.dataset.currentUserId || '';
  var thModalSigStates = {};
  var thModalSigKey = 'lplan_trackhub_last_signature_u' + CURRENT_USER_ID;
  var thDiarySigKey = 'lplan_diary_last_signature_inspection_v1_u' + CURRENT_USER_ID;

  function urlPk(tpl, pk) {
    if (!tpl) return '';
    return tpl.replace(/\/0\//g, '/' + pk + '/');
  }

  function detailUrl(pk) { return urlPk(root.dataset.urlDetail, pk); }
  function updateUrl(pk) { return urlPk(root.dataset.urlUpdate, pk); }
  function atividadesUrl(pk) { return urlPk(root.dataset.urlAtividades, pk); }
  function comentariosUrl(pk) { return urlPk(root.dataset.urlComentarios, pk); }
  function anexoUploadUrl(pk) { return urlPk(root.dataset.urlAnexoUpload, pk); }
  function anexoDeletarUrl(anexoPk) { return urlPk(root.dataset.urlAnexoDeletar, anexoPk); }
  function etapaConcluirUrl(etapaPk) { return urlPk(root.dataset.urlEtapaConcluir, etapaPk); }
  function etapaReabrirUrl(etapaPk) { return urlPk(root.dataset.urlEtapaReabrir, etapaPk); }
  function pendenciaConcluirUrl(pk) { return urlPk(root.dataset.urlPendenciaConcluir, pk); }
  function pendenciaDeletarUrl(pk) { return urlPk(root.dataset.urlPendenciaDeletar, pk); }
  function etapaAdicionarUrl(pk) { return urlPk(root.dataset.urlEtapaAdicionar, pk); }
  function etapaEditarUrl(etapaPk) { return urlPk(root.dataset.urlEtapaEditar, etapaPk); }
  function etapaDeletarUrl(etapaPk) { return urlPk(root.dataset.urlEtapaDeletar, etapaPk); }
  function pendenciaFichaUrl(pk) { return urlPk(root.dataset.urlPendenciaFicha, pk); }
  function etapaNotificarUrl(etapaPk) { return urlPk(root.dataset.urlEtapaNotificar, etapaPk); }
  function etapasReordenarUrl(pk) { return urlPk(root.dataset.urlEtapasReordenar, pk); }

  var dragEtapaId = null;
  /** A fila/calendário são HTML estático; após mudanças no modal, recarrega ao fechar. */
  var trackhubListPageNeedsReload = false;
  function markTrackhubListStale() {
    trackhubListPageNeedsReload = true;
  }


  var overlay = document.getElementById('th-detalhe-overlay');
  var btnClose = document.getElementById('th-detalhe-close');
  var elBreadcrumbObra = document.getElementById('th-det-breadcrumb-obra');
  var elBreadcrumbTipo = document.getElementById('th-det-breadcrumb-tipo');
  var elMetaCreated = document.getElementById('th-det-meta-created');
  var elObraLine = document.getElementById('th-det-obra-line');
  var elTitulo = document.getElementById('th-det-titulo');
  var elRecInfo = document.getElementById('th-det-recorrencia-info');
  var elDesc = document.getElementById('th-det-descricao');
  var elEtapas = document.getElementById('th-det-etapas-list');
  var elEtapasCounter = document.getElementById('th-det-etapas-counter');
  var elProgressFill = document.getElementById('th-det-progress-fill');
  var elProgressText = document.getElementById('th-det-progress-text');
  var elAnexosSec = document.getElementById('th-det-anexos-section');
  var elAnexosGrid = document.getElementById('th-det-anexos-grid');
  var elAnexosLabel = document.getElementById('th-det-anexos-label');
  var elAnexoInput = document.getElementById('th-det-anexo-input');
  var elCommentAttach = document.getElementById('th-det-comment-attach');
  var elCommentFileInput = document.getElementById('th-det-comment-file-input');
  var elCommentFilesChips = document.getElementById('th-det-comment-files');
  var elComments = document.getElementById('th-det-comments-list');
  var elActivities = document.getElementById('th-det-activities-list');
  var elCommentText = document.getElementById('th-det-comment-text');
  var elCommentSend = document.getElementById('th-det-comment-send');
  var pillStatus = document.getElementById('th-det-pill-status');
  var pillPrio = document.getElementById('th-det-pill-prioridade');
  var pillTipo = document.getElementById('th-det-pill-tipo');
  var pillPrazo = document.getElementById('th-det-pill-prazo');
  var valStatus = document.getElementById('th-det-pill-status-val');
  var valPrio = document.getElementById('th-det-pill-prioridade-val');
  var valTipo = document.getElementById('th-det-pill-tipo-val');
  var valPrazo = document.getElementById('th-det-pill-prazo-val');
  var pillResponsavel = document.getElementById('th-det-pill-responsavel');
  var valResponsavel = document.getElementById('th-det-pill-responsavel-val');
  var selResponsavel = document.getElementById('th-det-responsavel-select');

  var panelComments = document.getElementById('th-det-panel-comments');
  var panelActivities = document.getElementById('th-det-panel-activities');
  var tabs = document.querySelectorAll('.th-detalhe-tab');

  var currentPk = null;
  var currentData = null;
  var openMenuEl = null;
  var commentPendingFiles = [];

  function esc(s) {
    return String(s == null ? '' : s)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/"/g, '&quot;');
  }

  function formatPrazo(iso) {
    if (!iso) return '—';
    var p = String(iso).split('T')[0].split('-');
    if (p.length !== 3) return iso;
    return p[2] + '/' + p[1] + '/' + p[0];
  }

  function shortCommentDate(s) {
    if (!s) return '';
    var t = String(s).trim();
    var m = t.match(/^(\d{2})\/(\d{2})\/\d{4}\s+(\d{2}:\d{2})/);
    if (m) return m[1] + '/' + m[2] + ' · ' + m[3];
    return t;
  }

  function avatarStyleFromName(nome, idx) {
    var colors = ['#3498db', '#2980b9', '#5dade2', '#577590', '#7f8c8d', '#34495e'];
    return colors[(idx + (nome || '').length) % colors.length];
  }

  function prazoPillExtras(prazoIso, estaVencida, status) {
    var ex = [];
    if (status === 'concluida' || status === 'cancelada') {
      ex.push('neutral');
      return ex;
    }
    if (estaVencida) {
      ex.push('vencida');
      return ex;
    }
    if (!prazoIso) return ex;
    var raw = String(prazoIso).split('T')[0].split('-');
    if (raw.length !== 3) return ex;
    var d = new Date(parseInt(raw[0], 10), parseInt(raw[1], 10) - 1, parseInt(raw[2], 10));
    var today = new Date();
    today.setHours(0, 0, 0, 0);
    var diff = (d.getTime() - today.getTime()) / 86400000;
    if (diff >= 0 && diff <= 7) ex.push('soon');
    return ex;
  }

  function flashSaving() {
    var el = document.getElementById('th-det-saving');
    if (!el) return;
    el.classList.add('visible');
    if (window._thSaveT) clearTimeout(window._thSaveT);
    window._thSaveT = setTimeout(function () { el.classList.remove('visible'); }, 1400);
  }

  function rebuildPillClass(el, classTokens) {
    if (!el) return;
    el.className = classTokens.filter(Boolean).join(' ');
  }

  function setEditable(el, on) {
    if (!el) return;
    el.contentEditable = on ? 'true' : 'false';
    el.classList.toggle('is-readonly', !on);
  }

  function closeDropdown() {
    if (openMenuEl && openMenuEl.parentNode) openMenuEl.remove();
    openMenuEl = null;
  }

  function positionDropdown(anchor, menu) {
    var r = anchor.getBoundingClientRect();
    menu.style.position = 'fixed';
    menu.style.top = (r.bottom + 4) + 'px';
    menu.style.left = Math.min(r.left, window.innerWidth - 220) + 'px';
    menu.style.zIndex = '1400';
  }

  function showChoiceMenu(anchor, field, choices, currentVal) {
    closeDropdown();
    var menu = document.createElement('div');
    menu.className = 'th-detalhe-inline-menu';
    openMenuEl = menu;
    choices.forEach(function (opt) {
      var b = document.createElement('button');
      b.type = 'button';
      b.className = 'th-detalhe-inline-menu__opt' + (opt.value === currentVal ? ' is-active' : '');
      b.textContent = opt.label;
      b.addEventListener('click', function (e) {
        e.preventDefault();
        e.stopPropagation();
        closeDropdown();
        if (opt.value !== currentVal) salvarCampo(field, opt.value);
      });
      menu.appendChild(b);
    });
    document.body.appendChild(menu);
    positionDropdown(anchor, menu);
  }

  document.addEventListener('click', function () {
    closeDropdown();
    closeEtapaMenus();
    closeFilaCardMenus();
  });

  function preencherActionsFooter(pk) {
    var delForm = document.getElementById('th-form-deletar');
    var concForm = document.getElementById('th-form-concluir');
    if (delForm) delForm.action = pendenciaDeletarUrl(pk);
    if (concForm) concForm.action = pendenciaConcluirUrl(pk);
  }

  function closeEtapaMenus() {
    document.querySelectorAll('.th-etapa-menu-wrap.is-open').forEach(function (w) {
      w.classList.remove('is-open');
    });
  }

  function closeFilaCardMenus() {
    document.querySelectorAll('.th-card-menu-wrap.is-open').forEach(function (w) {
      w.classList.remove('is-open');
    });
    document.querySelectorAll('.th-card.th-card--menu-open').forEach(function (c) {
      c.classList.remove('th-card--menu-open');
    });
  }

  function buildEtapaMenuBtn(e, p) {
    var wrap = document.createElement('div');
    wrap.className = 'th-etapa-menu-wrap';
    var btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'th-etapa-menu-btn';
    btn.setAttribute('aria-label', 'Opções da etapa');
    btn.setAttribute('aria-haspopup', 'true');
    btn.innerHTML = '<svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor" aria-hidden="true"><circle cx="12" cy="5" r="1.5"/><circle cx="12" cy="12" r="1.5"/><circle cx="12" cy="19" r="1.5"/></svg>';
    var menu = document.createElement('div');
    menu.className = 'th-etapa-menu-dropdown';
    menu.setAttribute('role', 'menu');

    var btnEdit = document.createElement('button');
    btnEdit.type = 'button';
    btnEdit.className = 'th-etapa-menu-item';
    btnEdit.textContent = 'Editar etapa';
    btnEdit.addEventListener('click', function (ev) {
      ev.stopPropagation();
      closeEtapaMenus();
      window.abrirFormEditarEtapa(e.id);
    });
    if (e.status !== 'concluida') {
      menu.appendChild(btnEdit);
    }

    if (e.status === 'pendente') {
      var btnDel = document.createElement('button');
      btnDel.type = 'button';
      btnDel.className = 'th-etapa-menu-item th-etapa-menu-item--danger';
      btnDel.textContent = 'Excluir etapa';
      btnDel.addEventListener('click', function (ev) {
        ev.stopPropagation();
        closeEtapaMenus();
        window.excluirEtapaAjax(e.id, e.titulo);
      });
      menu.appendChild(btnDel);
    }

    if (e.status === 'concluida' && p.pode_editar && p.status !== 'cancelada') {
      var btnReab = document.createElement('button');
      btnReab.type = 'button';
      btnReab.className = 'th-etapa-menu-item';
      btnReab.textContent = 'Reabrir etapa';
      btnReab.addEventListener('click', function (ev) {
        ev.stopPropagation();
        closeEtapaMenus();
        window.reabrirEtapaAjax(e.id, e.titulo);
      });
      menu.appendChild(btnReab);
    }

    btn.addEventListener('click', function (ev) {
      ev.stopPropagation();
      var open = wrap.classList.contains('is-open');
      closeEtapaMenus();
      if (!open) wrap.classList.add('is-open');
    });
    wrap.appendChild(btn);
    wrap.appendChild(menu);
    return wrap;
  }


  function applyPendenciaPayload(p) {
    currentData = p;
    if (elBreadcrumbObra) elBreadcrumbObra.textContent = p.obra_nome || '—';
    if (elBreadcrumbTipo) elBreadcrumbTipo.textContent = p.tipo_display || '';
    if (elMetaCreated) {
      var criador = p.criado_por_nome || '—';
      var dc = p.created_at || '';
      elMetaCreated.textContent = dc ? ('Criado por ' + criador + ' em ' + dc) : '';
    }
    if (elObraLine) elObraLine.textContent = p.obra_nome || '';
    if (elTitulo) elTitulo.textContent = p.titulo || '';
    if (elRecInfo) {
      var r = p.recorrencia;
      if (r && r.proxima_execucao_display) {
        elRecInfo.hidden = false;
        elRecInfo.textContent = 'Pendência recorrente · próxima em ' + r.proxima_execucao_display;
      } else {
        elRecInfo.hidden = true;
        elRecInfo.textContent = '';
      }
    }
    if (elDesc) {
      elDesc.textContent = p.descricao || '';
      if (!p.descricao) elDesc.classList.add('is-placeholder');
      else elDesc.classList.remove('is-placeholder');
    }
    if (valStatus) valStatus.textContent = p.status_display || '';
    if (valPrio) valPrio.textContent = p.prioridade_display || '';
    if (valTipo) valTipo.textContent = p.tipo_display || '';
    if (valResponsavel) valResponsavel.textContent = p.responsavel_nome || (p.responsavel_interno_id ? '' : '—');
    if (valPrazo) valPrazo.textContent = formatPrazo(p.prazo);

    var pode = p.pode_editar;
    rebuildPillClass(pillStatus, ['th-detalhe-pill', 'th-pill', 'th-pill--status', 'status-' + (p.status || 'aberta')]);
    rebuildPillClass(pillPrio, ['th-detalhe-pill', 'th-pill', 'th-pill--prioridade', 'prio-' + (p.prioridade || 'normal')]);
    rebuildPillClass(pillTipo, ['th-detalhe-pill', 'th-pill', 'th-pill--tipo', 'tipo-' + (p.tipo || 'outro')]);
    rebuildPillClass(pillPrazo, ['th-detalhe-pill', 'th-pill', 'th-pill--prazo', 'prazo-pill'].concat(prazoPillExtras(p.prazo, p.esta_vencida, p.status)));

    setEditable(elTitulo, pode);
    setEditable(elDesc, pode);
    [pillStatus, pillPrio, pillTipo, pillResponsavel, pillPrazo].forEach(function (pill) {
      if (pill) {
        pill.disabled = !pode;
        pill.classList.toggle('is-disabled', !pode);
      }
    });

    renderEtapas(p);
    renderAnexos(p);
    renderComentarios(p.comentarios || []);
    carregarAtividades(currentPk);

    window.thDetalheAtual = p.id;
    window.thUsuarios = p.usuarios || [];
    window.thUsuariosOutros = p.usuarios_outros || [];
    window.thDetalheObraNome = p.obra_nome || '';
    window.etapasPendentesCount = typeof p.etapas_pendentes_count === 'number'
      ? p.etapas_pendentes_count
      : 0;

    // preparar select de responsável (picker) no modal
    if (selResponsavel) {
      // sincronizar valor preservado
      selResponsavel.value = p.responsavel_interno_id ? String(p.responsavel_interno_id) : '';
      // garantir attach do ThRespPicker quando necessário
      try {
        ThRespPicker.attachModalNovaEtapa(selResponsavel);
      } catch (e) {}
      // salvar quando usuário escolher no picker
      selResponsavel.onchange = function () {
        var vid = selResponsavel.value || null;
        salvarCampo('responsavel_interno', vid);
      };
    }

    preencherActionsFooter(p.id);

    var btnNova = document.querySelector('#th-det-modal-footer .btn-nova-etapa');
    if (btnNova) {
      btnNova.disabled = !pode;
      btnNova.classList.toggle('is-disabled', !pode);
    }
    var btnExcluirEl = document.querySelector('#th-form-deletar .btn-excluir');
    if (btnExcluirEl) btnExcluirEl.disabled = !pode;
    var btnConcEl = document.querySelector('#th-form-concluir .btn-concluir');
    if (btnConcEl) {
      var sealed = p.status === 'concluida' || p.status === 'cancelada';
      btnConcEl.disabled = sealed;
    }
  }

  function thModalInitCanvas(epk) {
    var canvas = document.getElementById('th-modal-canvas-' + epk);
    if (!canvas || canvas.dataset.init === '1') return;
    var ctx = canvas.getContext('2d');
    var isDrawing = false;
    var lastX = 0;
    var lastY = 0;
    var activePointerId = null;
    var state = thModalSigStates[epk] || {};
    thModalSigStates[epk] = state;
    function resizeCanvas() {
      var rect = canvas.getBoundingClientRect();
      if (!rect.width) return;
      var dpr = window.devicePixelRatio || 1;
      var preserved = '';
      if (state.hasInk) { try { preserved = canvas.toDataURL('image/png'); } catch (ex) {} }
      canvas.width = rect.width * dpr;
      canvas.height = 120 * dpr;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      ctx.strokeStyle = '#1e293b'; ctx.lineWidth = 2.2; ctx.lineCap = 'round'; ctx.lineJoin = 'round';
      if (preserved) {
        var img = new Image();
        img.onload = function() { try { ctx.drawImage(img, 0, 0, rect.width, 120); } catch (ex) {} };
        img.src = preserved;
      }
    }
    function getPoint(ev) { var r = canvas.getBoundingClientRect(); return { x: ev.clientX - r.left, y: ev.clientY - r.top }; }
    function startDraw(ev) {
      if (activePointerId !== null && activePointerId !== ev.pointerId) return;
      ev.preventDefault();
      activePointerId = ev.pointerId; isDrawing = true;
      var pt = getPoint(ev); lastX = pt.x; lastY = pt.y;
    }
    function drawMove(ev) {
      if (!isDrawing || (activePointerId !== null && ev.pointerId !== activePointerId)) return;
      ev.preventDefault();
      var pt = getPoint(ev);
      ctx.beginPath(); ctx.moveTo(lastX, lastY); ctx.lineTo(pt.x, pt.y); ctx.stroke();
      state.hasInk = true; lastX = pt.x; lastY = pt.y;
    }
    function endDraw(ev) {
      if (activePointerId !== null && ev && ev.pointerId !== activePointerId) return;
      isDrawing = false; activePointerId = null;
    }
    resizeCanvas();
    canvas.__thSigResize = resizeCanvas;
    window.addEventListener('resize', resizeCanvas);
    canvas.addEventListener('pointerdown', startDraw, { passive: false });
    canvas.addEventListener('pointermove', drawMove, { passive: false });
    canvas.addEventListener('pointerup', endDraw, { passive: false });
    canvas.addEventListener('pointercancel', endDraw, { passive: false });
    canvas.addEventListener('pointerleave', endDraw, { passive: false });
    canvas.dataset.init = '1';
  }

  function thModalLimparCanvas(epk) {
    var canvas = document.getElementById('th-modal-canvas-' + epk);
    if (!canvas) return;
    var state = thModalSigStates[epk] || {};
    state.hasInk = false;
    thModalSigStates[epk] = state;
    if (typeof canvas.__thSigResize === 'function') { canvas.__thSigResize(); }
    else { var ctx = canvas.getContext('2d'); ctx.clearRect(0, 0, canvas.width, canvas.height); }
  }

  function thModalUsarUltimaSig(epk) {
    var data = localStorage.getItem(thModalSigKey) || localStorage.getItem(thDiarySigKey);
    if (!data) { alert('Nenhuma assinatura salva encontrada.'); return; }
    var canvas = document.getElementById('th-modal-canvas-' + epk);
    if (!canvas) return;
    thModalInitCanvas(epk);
    var ctx = canvas.getContext('2d');
    var img = new Image();
    img.onload = function() {
      var r = canvas.getBoundingClientRect();
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      ctx.drawImage(img, 0, 0, r.width || canvas.width, 120);
      var state = thModalSigStates[epk] || {};
      state.hasInk = true;
      thModalSigStates[epk] = state;
    };
    img.src = data;
  }

  function thModalGetSigData(epk) {
    var state = thModalSigStates[epk] || {};
    if (!state.hasInk) return '';
    var canvas = document.getElementById('th-modal-canvas-' + epk);
    if (!canvas) return '';
    var data = canvas.toDataURL('image/png');
    if (data && CURRENT_USER_ID) { localStorage.setItem(thModalSigKey, data); }
    return data;
  }

  function removerFormulariosEtapaModal() {
    var ed = document.getElementById('th-form-editar-etapa');
    if (ed) ed.remove();
    var ne = document.getElementById('th-form-nova-etapa');
    if (ne) ne.remove();
  }

  function renderEtapas(p) {
    if (!elEtapas) return;
    removerFormulariosEtapaModal();
    elEtapas.innerHTML = '';
    var etapas = p.etapas || [];
    var total = etapas.length;
    var concl = 0;
    for (var j = 0; j < total; j++) {
      if (etapas[j].status === 'concluida') concl++;
    }
    if (elEtapasCounter) {
      elEtapasCounter.textContent = total ? (concl + ' de ' + total + ' concluídas') : '';
    }
    if (elProgressFill) {
      elProgressFill.style.width = total ? (Math.round(100 * concl / total) + '%') : '0%';
    }
    if (elProgressText) {
      var firstPend = null;
      for (var fp = 0; fp < etapas.length; fp++) {
        if (etapas[fp].status === 'pendente') { firstPend = etapas[fp]; break; }
      }
      elProgressText.textContent = total
        ? (concl + ' de ' + total + ' etapas concluídas' + (firstPend ? (' · Etapa atual: ' + firstPend.titulo) : ''))
        : 'Sem etapas definidas para esta pendência.';
    }
    if (!etapas.length) {
      elEtapas.innerHTML = '<p class="th-detalhe-muted">Sem etapas.</p>';
      return;
    }
    var firstPendenteIdx = -1;
    for (var i = 0; i < etapas.length; i++) {
      if (etapas[i].status === 'pendente') { firstPendenteIdx = i; break; }
    }
    etapas.forEach(function (e, idx) {
      var isConcl = e.status === 'concluida';
      var isAtiva = !isConcl && idx === firstPendenteIdx;
      var item = document.createElement('div');
      item.className = 'th-etapa-item' + (isConcl ? ' concluida' : (isAtiva ? ' ativa' : ''));
      item.setAttribute('data-etapa-id', String(e.id));
      var podeReordenar = p.pode_editar && p.status !== 'concluida' && p.status !== 'cancelada';
      if (podeReordenar) {
        item.setAttribute('draggable', 'true');
        item.setAttribute('title', 'Arraste para alterar a ordem das etapas');
        item.addEventListener('dragstart', function (ev) {
          if (ev.target.closest && ev.target.closest('button, a')) {
            ev.preventDefault();
            return;
          }
          dragEtapaId = String(e.id);
          ev.dataTransfer.setData('text/plain', String(e.id));
          ev.dataTransfer.effectAllowed = 'move';
          item.classList.add('th-etapa-item--dragging');
          document.addEventListener('dragover', onDocumentDragOverForEtapaReorder, true);
        });
        item.addEventListener('dragend', function () {
          item.classList.remove('th-etapa-item--dragging');
          dragEtapaId = null;
          document.removeEventListener('dragover', onDocumentDragOverForEtapaReorder, true);
        });
      }

      var row = document.createElement('div');
      row.className = 'th-etapa-row';
      var circle = document.createElement('div');
      circle.className = 'th-etapa-circle ' + (isConcl ? 'concluida' : 'pendente');
      if (isConcl) {
        circle.innerHTML = '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>';
      } else {
        var num = typeof e.numero === 'number' ? e.numero : (idx + 1);
        circle.textContent = String(num);
      }
      var tit = document.createElement('div');
      tit.className = 'th-etapa-titulo';
      tit.textContent = e.titulo || '';
      var badge = document.createElement('span');
      badge.className = 'th-etapa-badge ' + (isConcl ? 'concluida' : 'pendente');
      badge.textContent = e.status_display || '';
      row.appendChild(circle);
      row.appendChild(tit);
      row.appendChild(badge);
      if (p.pode_editar && p.status !== 'cancelada' && (p.status !== 'concluida' || e.status === 'concluida')) {
        var menuWrap = buildEtapaMenuBtn(e, p);
        menuWrap.style.flexShrink = '0';
        row.appendChild(menuWrap);
      }
      item.appendChild(row);

      var meta = document.createElement('div');
      meta.className = 'th-etapa-meta';
      var spanR = document.createElement('span');
      spanR.className = 'th-etapa-meta-item';
      spanR.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20 21v-2a4 4 0 00-4-4H8a4 4 0 00-4 4v2"/><circle cx="12" cy="7" r="4"/></svg> ';
      spanR.appendChild(document.createTextNode(e.responsavel_nome || '—'));
      meta.appendChild(spanR);
      if (e.prazo) {
        var spanP = document.createElement('span');
        spanP.className = 'th-etapa-meta-item';
        spanP.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="4" width="18" height="18" rx="2" ry="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/></svg> Prazo: ' + esc(formatPrazo(e.prazo));
        meta.appendChild(spanP);
      }
      item.appendChild(meta);

      if (e.requer_assinatura) {
        var box = document.createElement('div');
        box.className = 'th-assinatura-box';
        if (e.status === 'pendente' && e.pode_assinar) {
          var boxTitleC = document.createElement('div');
          boxTitleC.className = 'th-assinatura-title';
          boxTitleC.innerHTML = '<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M10.4 12.6a2 2 0 113 3L8 21l-4 1 1-4 5.4-5.4z"/></svg> Assinatura Manual';
          var btnsRow = document.createElement('div');
          btnsRow.className = 'th-sig-btns';
          var btnLast = document.createElement('button');
          btnLast.type = 'button';
          btnLast.className = 'th-sig-btn';
          btnLast.innerHTML = '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="1 4 1 10 7 10"/><path d="M3.51 15a9 9 0 102.13-9.36L1 10"/></svg> Usar última assinatura';
          (function(epk) { btnLast.addEventListener('click', function(ev) { ev.stopPropagation(); thModalUsarUltimaSig(epk); }); })(e.id);
          var btnClr = document.createElement('button');
          btnClr.type = 'button';
          btnClr.className = 'th-sig-btn';
          btnClr.innerHTML = '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 6h18"/><path d="M8 6V4h8v2"/><path d="M19 6l-1 14H6L5 6"/></svg> Limpar';
          (function(epk) { btnClr.addEventListener('click', function(ev) { ev.stopPropagation(); thModalLimparCanvas(epk); }); })(e.id);
          btnsRow.appendChild(btnLast);
          btnsRow.appendChild(btnClr);
          var sigCanvas = document.createElement('canvas');
          sigCanvas.id = 'th-modal-canvas-' + e.id;
          sigCanvas.height = 120;
          sigCanvas.className = 'th-sig-canvas';
          var sigHint = document.createElement('div');
          sigHint.className = 'th-sig-hint';
          sigHint.textContent = 'Desenhe sua assinatura acima ou use "Usar última" para reutilizar.';
          box.appendChild(boxTitleC);
          box.appendChild(btnsRow);
          box.appendChild(sigCanvas);
          box.appendChild(sigHint);
          item.appendChild(box);
          (function(epk, existingSig) {
            setTimeout(function() {
              thModalInitCanvas(epk);
              if (existingSig) {
                var cv = document.getElementById('th-modal-canvas-' + epk);
                if (cv) {
                  var cx = cv.getContext('2d');
                  var im = new Image();
                  im.onload = function() {
                    var r = cv.getBoundingClientRect();
                    cx.clearRect(0, 0, cv.width, cv.height);
                    cx.drawImage(im, 0, 0, r.width || cv.width, 120);
                    var st = thModalSigStates[epk] || {};
                    st.hasInk = true;
                    thModalSigStates[epk] = st;
                  };
                  im.src = existingSig;
                }
              }
            }, 0);
          })(e.id, e.tem_assinatura ? e.signature_data : '');
        } else if (e.status === 'pendente' && !e.pode_assinar && !e.tem_assinatura) {
          box.innerHTML = '<div class="th-assinatura-title"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M10.4 12.6a2 2 0 113 3L8 21l-4 1 1-4 5.4-5.4z"/></svg> Assinatura necessária</div><p class="th-assinatura-hint">Aguardando assinatura do responsável.</p>';
          item.appendChild(box);
        } else if (e.tem_assinatura && e.signature_data) {
          var boxTitleR = document.createElement('div');
          boxTitleR.className = 'th-assinatura-title';
          boxTitleR.textContent = 'Assinatura registrada';
          var sigImg = document.createElement('img');
          sigImg.src = e.signature_data;
          sigImg.alt = 'Assinatura';
          sigImg.className = 'th-assinatura-img';
          box.appendChild(boxTitleR);
          box.appendChild(sigImg);
          item.appendChild(box);
        }
      }

      if (e.observacao) {
        var obs = document.createElement('div');
        obs.className = 'th-etapa-obs';
        var obsLabel = document.createElement('div');
        obsLabel.className = 'th-etapa-obs-label';
        obsLabel.textContent = 'Observações:';
        var obsText = document.createElement('div');
        obsText.className = 'th-etapa-obs-text';
        obsText.textContent = e.observacao;
        obs.appendChild(obsLabel);
        obs.appendChild(obsText);
        item.appendChild(obs);
      }

      if (e.anexos && e.anexos.length) {
        var anexosEtapa = document.createElement('div');
        anexosEtapa.className = 'th-etapa-anexos';
        e.anexos.forEach(function(an) {
          var aLink = document.createElement('a');
          aLink.href = an.url;
          aLink.target = '_blank';
          aLink.rel = 'noopener';
          aLink.title = an.nome;
          aLink.className = 'th-etapa-anexo-item' + (an.eh_imagem ? ' imagem' : ' arquivo');
          if (an.eh_imagem) {
            var img = document.createElement('img');
            img.src = an.url;
            img.alt = an.nome;
            img.loading = 'lazy';
            aLink.appendChild(img);
          } else {
            aLink.innerHTML = '<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>';
            var nameSpan = document.createElement('span');
            nameSpan.textContent = an.nome;
            aLink.appendChild(nameSpan);
          }
          anexosEtapa.appendChild(aLink);
        });
        item.appendChild(anexosEtapa);
      }

      var actions = document.createElement('div');
      actions.className = 'th-etapa-actions';

      var btnN = document.createElement('button');
      btnN.type = 'button';
      btnN.className = 'btn-etapa-notif';
      btnN.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 16.92v3a2 2 0 01-2.18 2 19.79 19.79 0 01-8.63-3.07A19.5 19.5 0 013.07 9.81a19.79 19.79 0 01-3.07-8.68A2 2 0 012 .99h3a2 2 0 012 1.72 12.84 12.84 0 00.7 2.81 2 2 0 01-.45 2.11L6.09 8.91a16 16 0 006 6l1.27-1.27a2 2 0 012.11-.45 12.84 12.84 0 002.81.7A2 2 0 0122 16.92z"/></svg> Notificar';
      btnN.addEventListener('click', function (ev) {
        ev.stopPropagation();
        thAbrirModalNotif(e.id, e.titulo, e.responsavel_nome, e.responsavel_whatsapp, e.responsavel_email, p.titulo);
      });
      actions.appendChild(btnN);

      if (e.status === 'pendente') {
        if (e.requer_assinatura && e.pode_assinar) {
          var btnCSign = document.createElement('button');
          btnCSign.type = 'button';
          btnCSign.className = 'btn-etapa-concluir';
          btnCSign.innerHTML = '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg> Concluir etapa';
          (function(epk) {
            btnCSign.addEventListener('click', function(ev) {
              ev.stopPropagation();
              var sigData = thModalGetSigData(epk);
              if (!sigData) { alert('Assine antes de concluir.'); return; }
              concluirEtapaAjax(epk, sigData);
            });
          })(e.id);
          actions.appendChild(btnCSign);
        } else if (e.requer_assinatura && !e.pode_assinar) {
          var wait = document.createElement('span');
          wait.style.cssText = 'display:inline-flex;align-items:center;padding:7px 10px;border-radius:8px;background:#fff7ed;color:#9a3412;border:1px solid #fed7aa;font-size:11px;font-weight:600;font-family:inherit;';
          wait.textContent = 'Aguardando assinatura do responsável';
          actions.appendChild(wait);
        } else {
          var btnC = document.createElement('button');
          btnC.type = 'button';
          btnC.className = 'btn-etapa-concluir';
          btnC.innerHTML = '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg> Concluir etapa';
          btnC.addEventListener('click', function (ev) {
            ev.stopPropagation();
            concluirEtapaAjax(e.id);
          });
          actions.appendChild(btnC);
        }
      } else if (e.status === 'concluida' && p.pode_editar && p.status !== 'cancelada') {
        var btnR = document.createElement('button');
        btnR.type = 'button';
        btnR.className = 'btn-etapa-reabrir';
        btnR.innerHTML = '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="1 4 1 10 7 10"/><path d="M3.51 15a9 9 0 102.13-9.36L1 10"/></svg> Reabrir etapa';
        btnR.addEventListener('click', function (ev) {
          ev.stopPropagation();
          window.reabrirEtapaAjax(e.id, e.titulo);
        });
        actions.appendChild(btnR);
      }
      item.appendChild(actions);
      elEtapas.appendChild(item);
    });
  }

  function renderAnexos(p) {
    if (!elAnexosGrid || !elAnexosSec) return;
    var list = p.anexos || [];
    var showSec = list.length > 0 || p.pode_editar;
    elAnexosSec.hidden = !showSec;
    elAnexosGrid.innerHTML = '';
    if (elAnexosLabel) {
      elAnexosLabel.textContent = 'Arquivos (' + list.length + '/5)';
    }

    list.forEach(function (a) {
      var wrap = document.createElement('div');
      wrap.className = 'th-anexo-thumb';
      if (a.eh_imagem) {
        var img = document.createElement('img');
        img.src = a.url;
        img.alt = a.nome;
        img.onclick = function () { window.open(a.url, '_blank'); };
        wrap.appendChild(img);
      } else {
        var doc = document.createElement('div');
        doc.className = 'th-anexo-thumb-doc';
        doc.onclick = function () { window.open(a.url, '_blank'); };
        doc.innerHTML = '<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#94a3b8" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>';
        var nm = document.createElement('div');
        nm.className = 'th-anexo-thumb-name';
        nm.textContent = a.nome || 'Arquivo';
        doc.appendChild(nm);
        wrap.appendChild(doc);
      }
      if (p.pode_editar) {
        var rm = document.createElement('button');
        rm.type = 'button';
        rm.className = 'th-file-thumb-remove';
        rm.textContent = '×';
        rm.title = 'Remover';
        rm.onclick = function () { removerAnexo(a.id); };
        wrap.appendChild(rm);
      }
      elAnexosGrid.appendChild(wrap);
    });

    if (p.pode_editar && list.length < 5) {
      var add = document.createElement('div');
      add.className = 'th-anexo-add';
      add.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg><span>Adicionar</span>';
      add.addEventListener('click', function () {
        if (elAnexoInput) elAnexoInput.click();
      });
      elAnexosGrid.appendChild(add);
    }
  }

  function renderComentarios(arr) {
    if (!elComments) return;
    elComments.innerHTML = '';
    if (!arr.length) {
      elComments.innerHTML = '<p class="th-detalhe-muted">Nenhum comentário.</p>';
      return;
    }
    arr.forEach(function (c, idx) {
      var item = document.createElement('div');
      item.className = 'th-comment';
      var ini = esc(c.autor_iniciais || (c.autor_nome || '?').slice(0, 2).toUpperCase());
      var head = document.createElement('div');
      head.className = 'th-comment-header';
      head.innerHTML = '<div class="th-comment-avatar" style="background:' + avatarStyleFromName(c.autor_nome, idx) + '">' + ini + '</div>'
        + '<span class="th-comment-author">' + esc(c.autor_nome) + '</span>'
        + '<span class="th-comment-date">' + esc(shortCommentDate(c.criado_em)) + '</span>';
      var txt = document.createElement('div');
      txt.className = 'th-comment-text';
      txt.textContent = c.texto || '';
      item.appendChild(head);
      if ((c.texto || '').trim()) item.appendChild(txt);
      if (c.anexos && c.anexos.length) {
        var filesWrap = document.createElement('div');
        filesWrap.className = 'th-comment-files';
        c.anexos.forEach(function (a) {
          if (!a || !a.url) return;
          if (a.eh_imagem) {
            var img = document.createElement('img');
            img.className = 'th-comentario-img';
            img.src = a.url;
            img.alt = a.nome || 'imagem';
            img.loading = 'lazy';
            img.addEventListener('click', function () {
              window.open(a.url, '_blank');
            });
            filesWrap.appendChild(img);
          } else {
            var doc = document.createElement('a');
            doc.className = 'th-comentario-doc';
            doc.href = a.url;
            doc.target = '_blank';
            doc.rel = 'noopener';
            doc.textContent = a.nome || 'Arquivo';
            filesWrap.appendChild(doc);
          }
        });
        if (filesWrap.childNodes.length) item.appendChild(filesWrap);
      }
      elComments.appendChild(item);
    });
  }

  function renderCommentPendingFiles() {
    if (!elCommentFilesChips) return;
    elCommentFilesChips.innerHTML = '';
    if (!commentPendingFiles.length) {
      elCommentFilesChips.hidden = true;
      return;
    }
    elCommentFilesChips.hidden = false;
    commentPendingFiles.forEach(function (f, idx) {
      var chip = document.createElement('span');
      chip.className = 'th-file-chip';
      var nm = f.name || ('Arquivo ' + (idx + 1));
      chip.appendChild(document.createTextNode(nm.length > 28 ? (nm.slice(0, 27) + '…') : nm));
      var rm = document.createElement('button');
      rm.type = 'button';
      rm.setAttribute('aria-label', 'Remover arquivo');
      rm.textContent = '×';
      rm.addEventListener('click', function () {
        commentPendingFiles.splice(idx, 1);
        renderCommentPendingFiles();
        if (elCommentSend) {
          elCommentSend.disabled = !((elCommentText && (elCommentText.value || '').trim()) || commentPendingFiles.length);
        }
      });
      chip.appendChild(rm);
      elCommentFilesChips.appendChild(chip);
    });
  }

  function renderAtividades(arr) {
    if (!elActivities) return;
    elActivities.innerHTML = '';
    if (!arr.length) {
      elActivities.innerHTML = '<p class="th-detalhe-muted">Nenhuma atividade registrada.</p>';
      return;
    }
    arr.forEach(function (a) {
      var dotMap = { criacao: 'criacao', status: 'status', comentario: 'comentario', arquivo: 'arquivo', etapa: 'etapa' };
      var dotC = dotMap[a.tipo] || '';
      var item = document.createElement('div');
      item.className = 'th-activity';
      item.innerHTML = '<div class="th-activity-dot ' + dotC + '"></div><div class="th-activity-content">'
        + '<div class="th-activity-desc"><strong>' + esc(a.usuario) + '</strong> ' + esc(a.descricao) + '</div>'
        + '<div class="th-activity-meta">' + esc(a.criado_em) + '</div></div>';
      elActivities.appendChild(item);
    });
  }

  async function salvarCampo(field, value) {
    if (!currentPk) return;
    var r = await fetch(updateUrl(currentPk), {
      method: 'POST',
      credentials: 'same-origin',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': CSRF,
      },
      body: JSON.stringify({ field: field, value: value }),
    });
    var data = await r.json().catch(function () { return {}; });
    if (!r.ok || !data.ok) {
      alert((data && data.error) || 'Não foi possível salvar.');
      return;
    }
    markTrackhubListStale();
    if (data.perdeu_acesso) {
      if (typeof window.fecharDetalhe === 'function') window.fecharDetalhe();
      return;
    }
    if (data.pendencia) applyPendenciaPayload(data.pendencia);
    carregarAtividades(currentPk);
    flashSaving();
  }

  async function carregarAtividades(pk) {
    if (!pk || !elActivities) return;
    var r = await fetch(atividadesUrl(pk), { credentials: 'same-origin' });
    var d = await r.json().catch(function () { return {}; });
    if (r.ok && d.ok) renderAtividades(d.atividades || []);
  }

  async function carregarComentarios(pk) {
    if (!pk) return;
    var r = await fetch(comentariosUrl(pk), { credentials: 'same-origin' });
    var d = await r.json().catch(function () { return {}; });
    if (r.ok && d.ok) renderComentarios(d.comentarios || []);
  }

  async function enviarComentario() {
    if (!currentPk || !elCommentText) return;
    var texto = (elCommentText.value || '').trim();
    if (!texto && !commentPendingFiles.length) return;
    var fd = new FormData();
    fd.append('texto', texto);
    fd.append('csrfmiddlewaretoken', CSRF);
    commentPendingFiles.forEach(function (f) {
      fd.append('arquivos_comentario', f);
    });
    var r = await fetch(comentariosUrl(currentPk), {
      method: 'POST',
      credentials: 'same-origin',
      headers: { 'X-CSRFToken': CSRF },
      body: fd,
    });
    var d = await r.json().catch(function () { return {}; });
    if (!r.ok || !d.ok) {
      alert((d && d.error) || 'Erro ao enviar comentário.');
      return;
    }
    elCommentText.value = '';
    commentPendingFiles = [];
    if (elCommentFileInput) elCommentFileInput.value = '';
    renderCommentPendingFiles();
    if (elCommentSend) elCommentSend.disabled = true;
    carregarComentarios(currentPk);
    carregarAtividades(currentPk);
  }

  async function concluirEtapaAjax(etapaPk, signatureData) {
    var fd = new FormData();
    fd.append('csrfmiddlewaretoken', CSRF);
    if (signatureData) { fd.append('signature_etapa_' + etapaPk, signatureData); }
    var r = await fetch(etapaConcluirUrl(etapaPk), {
      method: 'POST',
      credentials: 'same-origin',
      headers: {
        'X-Requested-With': 'XMLHttpRequest',
        Accept: 'application/json',
      },
      body: fd,
    });
    var d = await r.json().catch(function () { return {}; });
    if (!r.ok || !d.ok) {
      alert((d && d.error) || 'Não foi possível concluir a etapa.');
      return;
    }
    markTrackhubListStale();
    var res = await fetch(detailUrl(currentPk), { credentials: 'same-origin' });
    var pack = await res.json().catch(function () { return {}; });
    if (res.ok && pack.ok && pack.pendencia) applyPendenciaPayload(pack.pendencia);
    carregarAtividades(currentPk);
  }

  async function reabrirEtapaAjax(etapaPk, titulo) {
    if (!confirm('Reabrir a etapa "' + (titulo || '') + '"? Ela voltará ao status pendente.')) return;
    var fd = new FormData();
    fd.append('csrfmiddlewaretoken', CSRF);
    var r = await fetch(etapaReabrirUrl(etapaPk), {
      method: 'POST',
      credentials: 'same-origin',
      headers: {
        'X-Requested-With': 'XMLHttpRequest',
        Accept: 'application/json',
      },
      body: fd,
    });
    var d = await r.json().catch(function () { return {}; });
    if (!r.ok || !d.success) {
      alert((d && d.error) || 'Não foi possível reabrir a etapa.');
      return;
    }
    markTrackhubListStale();
    if (d.pendencia) {
      applyPendenciaPayload(d.pendencia);
    } else if (currentPk) {
      var res = await fetch(detailUrl(currentPk), { credentials: 'same-origin' });
      var pack = await res.json().catch(function () { return {}; });
      if (res.ok && pack.ok && pack.pendencia) applyPendenciaPayload(pack.pendencia);
    }
    carregarAtividades(currentPk);
  }

  window.reabrirEtapaAjax = reabrirEtapaAjax;

  function getDragAfterEtapa(clientY) {
    if (!elEtapas) return null;
    var draggable = [].slice.call(elEtapas.querySelectorAll('.th-etapa-item[draggable="true"]'));
    var closest = { offset: Number.NEGATIVE_INFINITY, element: null };
    draggable.forEach(function (child) {
      var box = child.getBoundingClientRect();
      var offset = clientY - box.top - box.height / 2;
      if (offset < 0 && offset > closest.offset) {
        closest = { offset: offset, element: child };
      }
    });
    return closest.element;
  }

  /** Scroll automático ao arrastar etapas (HTML5 DnD não rola sozinho perto das bordas). */
  function onDocumentDragOverForEtapaReorder(ev) {
    if (!dragEtapaId) return;
    ev.preventDefault();
    if (ev.dataTransfer) ev.dataTransfer.dropEffect = 'move';
    autoScrollDuringEtapaDrag(ev.clientY);
  }

  function autoScrollDuringEtapaDrag(clientY) {
    var zone = 80;
    var maxStep = 32;
    var candidates = [
      document.querySelector('.th-detalhe-col-left.th-modal-left'),
      document.getElementById('th-detalhe-overlay'),
    ];
    candidates.forEach(function (el) {
      if (!el) return;
      var oy = getComputedStyle(el).overflowY;
      if (oy !== 'auto' && oy !== 'scroll' && oy !== 'overlay') return;
      if (el.scrollHeight <= el.clientHeight + 2) return;
      var r = el.getBoundingClientRect();
      if (clientY < r.top || clientY > r.bottom) return;
      var delta = 0;
      if (clientY < r.top + zone) {
        delta = -Math.ceil(maxStep * Math.min(1, (r.top + zone - clientY) / zone));
      } else if (clientY > r.bottom - zone) {
        delta = Math.ceil(maxStep * Math.min(1, (clientY - (r.bottom - zone)) / zone));
      }
      if (delta !== 0) {
        el.scrollTop = Math.max(
          0,
          Math.min(el.scrollHeight - el.clientHeight, el.scrollTop + delta)
        );
      }
    });
  }

  async function persistEtapasOrder(ordemIds) {
    if (!currentPk) return;
    var r = await fetch(etapasReordenarUrl(currentPk), {
      method: 'POST',
      credentials: 'same-origin',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': CSRF,
      },
      body: JSON.stringify({ ordem_ids: ordemIds }),
    });
    var d = await r.json().catch(function () { return {}; });
    if (!r.ok || !d.ok) {
      alert((d && d.error) || 'Não foi possível reordenar as etapas.');
      var res = await fetch(detailUrl(currentPk), { credentials: 'same-origin' });
      var pack = await res.json().catch(function () { return {}; });
      if (res.ok && pack.ok && pack.pendencia) applyPendenciaPayload(pack.pendencia);
      return;
    }
    markTrackhubListStale();
    if (d.pendencia) applyPendenciaPayload(d.pendencia);
    carregarAtividades(currentPk);
    flashSaving();
  }

  function initEtapasDnDOnce() {
    if (!elEtapas || elEtapas._thEtapasDndInit) return;
    elEtapas._thEtapasDndInit = true;
    elEtapas.addEventListener('dragover', function (ev) {
      if (!dragEtapaId) return;
      ev.preventDefault();
      ev.dataTransfer.dropEffect = 'move';
      autoScrollDuringEtapaDrag(ev.clientY);
    });
    elEtapas.addEventListener('drop', function (ev) {
      ev.preventDefault();
      var rawId = (ev.dataTransfer && ev.dataTransfer.getData('text/plain')) || dragEtapaId;
      if (!rawId || !elEtapas) return;
      var draggedEl = elEtapas.querySelector('.th-etapa-item[data-etapa-id="' + String(rawId) + '"]');
      if (!draggedEl || draggedEl.getAttribute('draggable') !== 'true') return;
      var afterEl = getDragAfterEtapa(ev.clientY);
      if (afterEl === draggedEl) return;
      var verMais = elEtapas.querySelector('.th-etapas-ver-historico');
      if (afterEl == null) {
        if (verMais) elEtapas.insertBefore(draggedEl, verMais);
        else elEtapas.appendChild(draggedEl);
      } else {
        elEtapas.insertBefore(draggedEl, afterEl);
      }
      var ids = [].map.call(elEtapas.querySelectorAll('.th-etapa-item[draggable="true"]'), function (node) {
        return parseInt(node.getAttribute('data-etapa-id'), 10);
      });
      var orig = (currentData && currentData.etapas) ? currentData.etapas.map(function (x) { return x.id; }) : [];
      var changed = ids.length !== orig.length || ids.some(function (id, i) { return id !== orig[i]; });
      if (!changed) return;
      persistEtapasOrder(ids);
    });
  }
  initEtapasDnDOnce();

  async function removerAnexo(anexoPk) {
    if (!confirm('Remover este arquivo?')) return;
    var fd = new FormData();
    fd.append('csrfmiddlewaretoken', CSRF);
    var r = await fetch(anexoDeletarUrl(anexoPk), {
      method: 'POST',
      credentials: 'same-origin',
      body: fd,
    });
    var d = await r.json().catch(function () { return {}; });
    if (!r.ok || !d.success) {
      alert((d && d.error) || 'Erro ao remover.');
      return;
    }
    var res = await fetch(detailUrl(currentPk), { credentials: 'same-origin' });
    var pack = await res.json().catch(function () { return {}; });
    if (res.ok && pack.ok && pack.pendencia) applyPendenciaPayload(pack.pendencia);
    carregarAtividades(currentPk);
  }

  function switchTab(name) {
    var isComm = name === 'comments';
    if (panelComments) {
      panelComments.hidden = !isComm;
      panelComments.classList.toggle('th-tab-panel--visible', isComm);
      panelComments.classList.toggle('th-tab-panel--hidden', !isComm);
      panelComments.style.display = isComm ? 'flex' : 'none';
    }
    if (panelActivities) {
      panelActivities.hidden = isComm;
      panelActivities.classList.toggle('th-tab-panel--visible', !isComm);
      panelActivities.classList.toggle('th-tab-panel--hidden', isComm);
      panelActivities.style.display = isComm ? 'none' : 'flex';
    }
    tabs.forEach(function (t) {
      t.classList.toggle('active', (isComm && t.dataset.tab === 'comments') || (!isComm && t.dataset.tab === 'activities'));
    });
  }

  tabs.forEach(function (t) {
    t.addEventListener('click', function () {
      switchTab(t.dataset.tab === 'comments' ? 'comments' : 'activities');
    });
  });

  function onTituloBlur() {
    if (!currentData || !currentData.pode_editar) return;
    var v = (elTitulo.innerText || '').trim();
    if (!v || v === (currentData.titulo || '')) return;
    salvarCampo('titulo', v);
  }

  function onDescBlur() {
    if (!currentData || !currentData.pode_editar) return;
    var v = elDesc.innerText || '';
    if (v === (currentData.descricao || '')) return;
    salvarCampo('descricao', v);
  }

  if (elTitulo) {
    elTitulo.addEventListener('blur', onTituloBlur);
    elTitulo.addEventListener('keydown', function (e) {
      if (e.key === 'Enter') { e.preventDefault(); elTitulo.blur(); }
    });
  }
  if (elDesc) {
    elDesc.addEventListener('blur', onDescBlur);
    elDesc.addEventListener('keydown', function (e) {
      if (e.key === 'Enter' && e.ctrlKey) { e.preventDefault(); elDesc.blur(); }
    });
  }

  function bindPill(el, field, getChoices, getVal) {
    if (!el) return;
    el.addEventListener('click', function (e) {
      e.stopPropagation();
      if (!currentData || !currentData.pode_editar) return;
      var ch = getChoices();
      var cv = getVal();
      showChoiceMenu(el, field, ch, cv);
    });
  }

  bindPill(pillStatus, 'status', function () { return currentData.status_choices || []; }, function () { return currentData.status; });
  bindPill(pillPrio, 'prioridade', function () { return currentData.prioridade_choices || []; }, function () { return currentData.prioridade; });
  bindPill(pillTipo, 'tipo', function () { return currentData.tipo_choices || []; }, function () { return currentData.tipo; });

  if (pillPrazo) {
    pillPrazo.addEventListener('click', function (e) {
      e.stopPropagation();
      if (!currentData || !currentData.pode_editar) return;
      var old = document.getElementById('th-prazo-picker-native');
      if (old) old.remove();
      var rect = pillPrazo.getBoundingClientRect();
      var inp = document.createElement('input');
      inp.type = 'date';
      inp.id = 'th-prazo-picker-native';
      inp.setAttribute('aria-hidden', 'true');
      inp.tabIndex = -1;
      inp.value = (currentData.prazo || '').split('T')[0] || '';
      inp.style.position = 'fixed';
      inp.style.left = Math.max(8, rect.left) + 'px';
      inp.style.top = Math.max(8, rect.bottom + 6) + 'px';
      inp.style.width = '1px';
      inp.style.height = '1px';
      inp.style.opacity = '0';
      inp.style.border = 'none';
      inp.style.padding = '0';
      inp.style.pointerEvents = 'none';
      inp.style.zIndex = '12000';
      document.body.appendChild(inp);
      inp.addEventListener('change', function () {
        salvarCampo('prazo', inp.value || null);
        inp.remove();
      });
      inp.addEventListener('blur', function () { setTimeout(function () { if (inp.parentNode) inp.remove(); }, 200); });
      setTimeout(function () {
        inp.style.pointerEvents = 'auto';
        try {
          if (typeof inp.showPicker === 'function') inp.showPicker();
          else inp.click();
        } catch (err) {
          inp.click();
        }
      }, 50);
    });
  }

    if (pillResponsavel && selResponsavel) {
      pillResponsavel.addEventListener('click', function (e) {
        e.stopPropagation();
        if (!currentData || !currentData.pode_editar) return;
        try {
          ThRespPicker.attachModalNovaEtapa(selResponsavel);
          ThRespPicker.open(selResponsavel, { zIndex: 12600, anchor: pillResponsavel, trigger: pillResponsavel });
        } catch (err) {}
      });
    }

  if (elCommentAttach && elCommentFileInput) {
    elCommentAttach.addEventListener('click', function () { elCommentFileInput.click(); });
  }

  if (elCommentFileInput) {
    elCommentFileInput.addEventListener('change', function () {
      var files = Array.from(elCommentFileInput.files || []);
      if (files.length) {
        files.forEach(function (f) { commentPendingFiles.push(f); });
        elCommentFileInput.value = '';
      }
      renderCommentPendingFiles();
      if (elCommentSend) {
        elCommentSend.disabled = !((elCommentText && (elCommentText.value || '').trim()) || commentPendingFiles.length);
      }
    });
  }

  if (elAnexoInput) {
    elAnexoInput.addEventListener('change', async function () {
      if (!currentPk || !elAnexoInput.files.length) return;
      var fd = new FormData();
      fd.append('csrfmiddlewaretoken', CSRF);
      for (var i = 0; i < elAnexoInput.files.length; i++) {
        fd.append('arquivos', elAnexoInput.files[i]);
      }
      var r = await fetch(anexoUploadUrl(currentPk), {
        method: 'POST',
        credentials: 'same-origin',
        body: fd,
      });
      var d = await r.json().catch(function () { return {}; });
      elAnexoInput.value = '';
      if (!r.ok || !d.success) {
        alert((d && d.error) || 'Erro no upload.');
        return;
      }
      var res = await fetch(detailUrl(currentPk), { credentials: 'same-origin' });
      var pack = await res.json().catch(function () { return {}; });
      if (res.ok && pack.ok && pack.pendencia) applyPendenciaPayload(pack.pendencia);
      carregarAtividades(currentPk);
    });
  }

  if (elCommentText && elCommentSend) {
    elCommentText.addEventListener('input', function () {
      elCommentSend.disabled = !((elCommentText.value || '').trim() || commentPendingFiles.length);
    });
    elCommentText.addEventListener('keydown', function (e) {
      if (e.key !== 'Enter' || e.shiftKey) return;
      e.preventDefault();
      if (!elCommentSend.disabled) enviarComentario();
    });
    elCommentSend.addEventListener('click', enviarComentario);
  }

  function thModalNovaEtapaChips(input) {
    var form = document.getElementById('th-form-nova-etapa');
    if (!form || !input) return;
    var chips = form.querySelector('.th-modal-nova-etapa-chips');
    if (!chips) return;
    chips.innerHTML = '';
    if (!input.files || !input.files.length) return;
    Array.from(input.files).forEach(function (f) {
      var s = document.createElement('span');
      s.style.cssText = 'display:inline-block;font-size:10.5px;padding:4px 8px;background:#e2e8f0;border-radius:6px;color:#475569;margin:2px 4px 2px 0;font-family:inherit;';
      var nm = f.name || '';
      s.textContent = nm.length > 26 ? nm.slice(0, 24) + '\u2026' : nm;
      chips.appendChild(s);
    });
  }

  window.tentarConcluir = function () {
    if (typeof window.etapasPendentesCount !== 'undefined' && window.etapasPendentesCount > 0) {
      alert(
        'Não é possível concluir esta pendência.\nAinda há ' + window.etapasPendentesCount
        + ' etapa(s) pendente(s).\nConclua todas as etapas antes.'
      );
      return;
    }
    var f = document.getElementById('th-form-concluir');
    if (f) f.submit();
  };

  window.abrirFormNovaEtapa = function () {
    if (!currentData || !currentData.pode_editar) return;
    removerFormulariosEtapaModal();
    var formExistente = document.getElementById('th-form-nova-etapa');
    if (formExistente) {
      formExistente.scrollIntoView({ behavior: 'smooth' });
      var inp = formExistente.querySelector('input[name="titulo"]');
      if (inp) inp.focus();
      return;
    }

    var etapasList = document.querySelector('.th-modal-left');
    if (!etapasList) return;

    var novaEtapaHtml = ''
      + '<div id="th-form-nova-etapa" style="position:relative;border:2px dashed #b8d4eb;border-radius:10px;padding:14px 14px 16px;margin-top:12px;background:#ebf6fd;">'
      + '  <button type="button" onclick="document.getElementById(\'th-form-nova-etapa\').remove()" aria-label="Fechar" title="Fechar"'
      + '    style="position:absolute;top:10px;right:10px;width:28px;height:28px;border-radius:8px;border:1px solid #e2e8f0;background:#fff;color:#64748b;cursor:pointer;display:flex;align-items:center;justify-content:center;font-size:14px;line-height:1;font-family:inherit;">'
      + '    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>'
      + '  </button>'
      + '  <div style="font-size:11px;font-weight:700;color:#2980b9;text-transform:uppercase;letter-spacing:.5px;margin-bottom:12px;padding-right:40px;">Nova etapa</div>'
      + '  <div style="margin-bottom:10px;">'
      + '    <label style="font-size:12px;font-weight:600;color:#374151;margin-bottom:4px;display:block;">T\u00edtulo <span style="color:#ef4444">*</span></label>'
      + '    <input type="text" name="titulo" placeholder="T\u00edtulo da etapa\u2026"'
      + '      style="width:100%;box-sizing:border-box;padding:8px 10px;border-radius:7px;border:1px solid #e2e8f0;font-size:13px;font-family:inherit;">'
      + '  </div>'
      + '  <div class="th-modal-nova-etapa-grid">'
      + '    <div>'
      + '      <label style="font-size:12px;font-weight:600;color:#374151;margin-bottom:4px;display:block;">Usu\u00e1rio respons\u00e1vel <span style="color:#ef4444">*</span></label>'
      + '      <select name="responsavel_interno" style="width:100%;box-sizing:border-box;padding:8px 10px;border-radius:7px;border:1px solid #e2e8f0;font-size:13px;font-family:inherit;">'
      + '        <option value="">Selecione...</option>'
      + '      </select>'
      + '    </div>'
      + '    <div>'
      + '      <label style="font-size:12px;font-weight:600;color:#374151;margin-bottom:4px;display:block;">Prazo da etapa</label>'
      + '      <input type="date" name="prazo" style="width:100%;box-sizing:border-box;padding:8px 10px;border-radius:7px;border:1px solid #e2e8f0;font-size:13px;font-family:inherit;">'
      + '    </div>'
      + '  </div>'
      + '  <div style="margin-bottom:10px;">'
      + '    <label style="font-size:12px;font-weight:600;color:#374151;margin-bottom:4px;display:block;">Observa\u00e7\u00e3o</label>'
      + '    <textarea name="observacao" rows="3" placeholder="Observa\u00e7\u00f5es sobre esta etapa..."'
      + '      style="width:100%;box-sizing:border-box;min-height:72px;resize:vertical;padding:8px 10px;border-radius:7px;border:1px solid #e2e8f0;font-size:13px;font-family:inherit;"></textarea>'
      + '  </div>'
      + '  <div class="th-etapa-upload-row" style="margin-bottom:10px;flex-wrap:wrap;">'
      + '    <span class="th-etapa-upload-label">Anexos:</span>'
      + '    <button type="button" class="th-etapa-upload-btn" onclick="this.nextElementSibling.nextElementSibling.click()">'
      + '      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/></svg>'
      + '      Adicionar arquivo'
      + '    </button>'
      + '    <div class="th-modal-nova-etapa-chips th-file-chips" style="display:flex;flex-wrap:wrap;align-items:center;gap:4px;min-height:0;"></div>'
      + '    <input type="file" name="anexos_etapa" id="th-nova-etapa-anexos" multiple accept="image/*,.pdf,.doc,.docx,.xls,.xlsx" style="display:none">'
      + '  </div>'
      + '  <label class="th-assinatura-toggle" id="th-modal-nova-etapa-ass-wrap" style="margin-top:0;margin-bottom:12px;cursor:pointer;">'
      + '    <input type="checkbox" id="th-nova-etapa-assinatura" name="requer_assinatura" value="1" style="cursor:pointer;">'
      + '    <span class="th-assinatura-toggle-label">'
      + '      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M10.4 12.6a2 2 0 113 3L8 21l-4 1 1-4 5.4-5.4z"/></svg>'
      + '      Esta etapa requer assinatura'
      + '    </span>'
      + '    <span style="font-size:10.5px;color:#94a3b8;">Quem concluir precisar\u00e1 assinar</span>'
      + '  </label>'
      + '  <div style="display:flex;gap:8px;flex-wrap:wrap;">'
      + '    <button type="button" onclick="salvarNovaEtapa()" style="padding:8px 16px;border-radius:8px;background:#3498db;color:#fff;border:none;font-size:12.5px;font-weight:700;cursor:pointer;font-family:inherit;">Adicionar etapa</button>'
      + '  </div>'
      + '</div>';

    etapasList.insertAdjacentHTML('beforeend', novaEtapaHtml);

    var select = document.querySelector('#th-form-nova-etapa select[name="responsavel_interno"]');
    if (select && window.ThRespPicker) {
      window.ThRespPicker.attachModalNovaEtapa(select);
    }

    var ne = document.getElementById('th-form-nova-etapa');
    var finp = document.getElementById('th-nova-etapa-anexos');
    if (finp) {
      finp.addEventListener('change', function () {
        thModalNovaEtapaChips(finp);
      });
    }
    var assWrap = document.getElementById('th-modal-nova-etapa-ass-wrap');
    var assInp = document.getElementById('th-nova-etapa-assinatura');
    if (assWrap && assInp) {
      assInp.addEventListener('change', function () {
        assWrap.classList.toggle('ativo', assInp.checked);
        var hint = assWrap.querySelector('span:last-of-type');
        var labelSpan = assWrap.querySelector('.th-assinatura-toggle-label');
        if (hint && hint !== labelSpan) {
          hint.style.color = assInp.checked ? '#2980b9' : '#94a3b8';
        }
      });
    }

    if (ne) {
      ne.scrollIntoView({ behavior: 'smooth', block: 'center' });
      var t = ne.querySelector('input[name="titulo"]');
      if (t) t.focus();
    }
  };

  window.salvarNovaEtapa = function () {
    var form = document.getElementById('th-form-nova-etapa');
    if (!form) return;
    var titulo = (form.querySelector('input[name="titulo"]').value || '').trim();
    if (!titulo) {
      alert('Informe o t\u00edtulo da etapa.');
      return;
    }

    var rid = (form.querySelector('select[name="responsavel_interno"]').value || '').trim();
    if (!rid) {
      alert('Informe o respons\u00e1vel interno da etapa.');
      return;
    }

    var pk = window.thDetalheAtual;
    if (!pk) return;

    var data = new FormData();
    data.append('titulo', titulo);
    data.append('responsavel_interno', rid);
    data.append('prazo', (form.querySelector('input[name="prazo"]').value || ''));
    var obsEl = form.querySelector('textarea[name="observacao"]');
    data.append('observacao', obsEl ? (obsEl.value || '') : '');
    data.append('requer_assinatura', form.querySelector('#th-nova-etapa-assinatura') && form.querySelector('#th-nova-etapa-assinatura').checked ? '1' : '');
    data.append('csrfmiddlewaretoken', CSRF);

    var fileInput = document.getElementById('th-nova-etapa-anexos');
    if (fileInput && fileInput.files && fileInput.files.length) {
      for (var fi = 0; fi < fileInput.files.length; fi++) {
        data.append('anexos_etapa', fileInput.files[fi]);
      }
    }

    fetch(etapaAdicionarUrl(pk), {
      method: 'POST',
      body: data,
      credentials: 'same-origin',
      headers: {
        'X-Requested-With': 'XMLHttpRequest',
      },
    })
      .then(function (r) {
        return r.json().then(function (d) {
          if (!r.ok || !d.success) {
            alert((d && d.error) || 'Erro ao adicionar etapa.');
            return;
          }
          markTrackhubListStale();
          form.remove();
          window.abrirDetalhe(pk);
        });
      })
      .catch(function () {
        alert('Erro ao adicionar etapa.');
      });
  };

  function findEtapaInCurrent(etapaId) {
    if (!currentData || !currentData.etapas) return null;
    var id = parseInt(etapaId, 10);
    for (var i = 0; i < currentData.etapas.length; i++) {
      if (currentData.etapas[i].id === id) return currentData.etapas[i];
    }
    return null;
  }

  function findResponsavelIdByNome(nome) {
    if (!currentData || !nome) return '';
    var n = String(nome).trim().toLowerCase();
    var list = (currentData.usuarios || []).concat(currentData.usuarios_outros || []);
    for (var i = 0; i < list.length; i++) {
      var u = list[i];
      if ((u.nome || '').trim().toLowerCase() === n) return String(u.id);
    }
    return '';
  }

  window.abrirFormEditarEtapa = function (etapaId) {
    if (!currentData || !currentData.pode_editar) return;
    var etapa = findEtapaInCurrent(etapaId);
    if (!etapa) return;
    if (etapa.status === 'concluida') {
      alert('Não é possível editar uma etapa já concluída.');
      return;
    }
    var existente = document.getElementById('th-form-editar-etapa');
    if (existente) existente.remove();
    var nova = document.getElementById('th-form-nova-etapa');
    if (nova) nova.remove();

    if (!elEtapas) return;

    var rid = etapa.responsavel_interno_id
      ? String(etapa.responsavel_interno_id)
      : findResponsavelIdByNome(etapa.responsavel_nome);
    var html = ''
      + '<div id="th-form-editar-etapa" data-etapa-id="' + String(etapa.id) + '" style="position:relative;border:2px dashed #b8d4eb;border-radius:10px;padding:14px 14px 16px;margin-top:12px;background:#ebf6fd;">'
      + '  <button type="button" onclick="document.getElementById(\'th-form-editar-etapa\').remove()" aria-label="Fechar" title="Fechar"'
      + '    style="position:absolute;top:10px;right:10px;width:28px;height:28px;border-radius:8px;border:1px solid #e2e8f0;background:#fff;color:#64748b;cursor:pointer;display:flex;align-items:center;justify-content:center;font-size:14px;line-height:1;font-family:inherit;">'
      + '    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>'
      + '  </button>'
      + '  <div style="font-size:11px;font-weight:700;color:#2980b9;text-transform:uppercase;letter-spacing:.5px;margin-bottom:12px;padding-right:40px;">Editar etapa</div>'
      + '  <div style="margin-bottom:10px;"><label style="font-size:12px;font-weight:600;color:#374151;margin-bottom:4px;display:block;">Título <span style="color:#ef4444">*</span></label>'
      + '  <input type="text" name="titulo" value="' + esc(etapa.titulo || '') + '" style="width:100%;box-sizing:border-box;padding:8px 10px;border-radius:7px;border:1px solid #e2e8f0;font-size:13px;font-family:inherit;"></div>'
      + '  <div class="th-modal-nova-etapa-grid"><div><label style="font-size:12px;font-weight:600;color:#374151;margin-bottom:4px;display:block;">Usuário responsável <span style="color:#ef4444">*</span></label>'
      + '  <select name="responsavel_interno" style="width:100%;box-sizing:border-box;padding:8px 10px;border-radius:7px;border:1px solid #e2e8f0;font-size:13px;font-family:inherit;"><option value="">Selecione...</option></select></div>'
      + '  <div><label style="font-size:12px;font-weight:600;color:#374151;margin-bottom:4px;display:block;">Prazo da etapa</label>'
      + '  <input type="date" name="prazo" value="' + esc(etapa.prazo || '') + '" style="width:100%;box-sizing:border-box;padding:8px 10px;border-radius:7px;border:1px solid #e2e8f0;font-size:13px;font-family:inherit;"></div></div>'
      + '  <div style="margin-bottom:10px;"><label style="font-size:12px;font-weight:600;color:#374151;margin-bottom:4px;display:block;">Observação</label>'
      + '  <textarea name="observacao" rows="3" style="width:100%;box-sizing:border-box;min-height:72px;resize:vertical;padding:8px 10px;border-radius:7px;border:1px solid #e2e8f0;font-size:13px;font-family:inherit;">' + esc(etapa.observacao || '') + '</textarea></div>'
      + '  <label class="th-assinatura-toggle th-modal-etapa-ass-wrap" style="margin-bottom:12px;cursor:pointer;display:flex;align-items:flex-start;gap:8px;">'
      + '  <input type="checkbox" name="requer_assinatura" value="1"' + (etapa.requer_assinatura ? ' checked' : '') + ' style="cursor:pointer;margin-top:3px;">'
      + '  <span style="font-size:12px;font-weight:600;color:#374151;">Esta etapa requer assinatura</span></label>'
      + '  <button type="button" onclick="salvarEditarEtapa()" style="padding:8px 16px;border-radius:8px;background:#3498db;color:#fff;border:none;font-size:12.5px;font-weight:700;cursor:pointer;font-family:inherit;">Salvar alterações</button>'
      + '</div>';
    elEtapas.insertAdjacentHTML('beforeend', html);

    var sel = document.querySelector('#th-form-editar-etapa select[name="responsavel_interno"]');
    if (sel) {
      if (rid) {
        sel.dataset.thRespPreserveId = rid;
        sel.dataset.thRespPreserveNome = etapa.responsavel_nome || '';
      } else {
        delete sel.dataset.thRespPreserveId;
        delete sel.dataset.thRespPreserveNome;
      }
      if (window.ThRespPicker) window.ThRespPicker.attachModalNovaEtapa(sel);
      if (rid) sel.value = rid;
      if (sel._thRespRefresh) sel._thRespRefresh();
    }

    var panel = document.getElementById('th-form-editar-etapa');
    if (panel) {
      panel.scrollIntoView({ behavior: 'smooth', block: 'center' });
      var t = panel.querySelector('input[name="titulo"]');
      if (t) t.focus();
    }
  };

  window.salvarEditarEtapa = function () {
    var form = document.getElementById('th-form-editar-etapa');
    if (!form) return;
    var etapaId = form.getAttribute('data-etapa-id');
    if (!etapaId) return;
    var titulo = (form.querySelector('input[name="titulo"]').value || '').trim();
    if (!titulo) { alert('Informe o título da etapa.'); return; }
    var rid = (form.querySelector('select[name="responsavel_interno"]').value || '').trim();
    if (!rid) { alert('Informe o responsável interno da etapa.'); return; }
    var data = new FormData();
    data.append('titulo', titulo);
    data.append('responsavel_interno', rid);
    data.append('prazo', (form.querySelector('input[name="prazo"]').value || ''));
    data.append('observacao', (form.querySelector('textarea[name="observacao"]').value || ''));
    data.append('requer_assinatura', form.querySelector('input[name="requer_assinatura"]').checked ? '1' : '');
    data.append('csrfmiddlewaretoken', CSRF);
    fetch(etapaEditarUrl(etapaId), {
      method: 'POST',
      body: data,
      credentials: 'same-origin',
      headers: { 'X-Requested-With': 'XMLHttpRequest' },
    })
      .then(function (r) { return r.json().then(function (d) { return { r: r, d: d }; }); })
      .then(function (x) {
        if (!x.r.ok || !x.d.success) {
          alert((x.d && x.d.error) || 'Erro ao salvar etapa.');
          return;
        }
        markTrackhubListStale();
        form.remove();
        if (x.d.pendencia) applyPendenciaPayload(x.d.pendencia);
        else if (currentPk) window.abrirDetalhe(currentPk);
      })
      .catch(function () { alert('Erro ao salvar etapa.'); });
  };

  window.excluirEtapaAjax = function (etapaId, titulo) {
    if (!confirm('Excluir a etapa "' + (titulo || '') + '"? Esta ação não pode ser desfeita.')) return;
    var data = new FormData();
    data.append('csrfmiddlewaretoken', CSRF);
    fetch(etapaDeletarUrl(etapaId), {
      method: 'POST',
      body: data,
      credentials: 'same-origin',
      headers: { 'X-Requested-With': 'XMLHttpRequest' },
    })
      .then(function (r) { return r.json().then(function (d) { return { r: r, d: d }; }); })
      .then(function (x) {
        if (!x.r.ok || !x.d.success) {
          alert((x.d && x.d.error) || 'Erro ao excluir etapa.');
          return;
        }
        markTrackhubListStale();
        var ed = document.getElementById('th-form-editar-etapa');
        if (ed) ed.remove();
        if (x.d.pendencia) applyPendenciaPayload(x.d.pendencia);
        else if (currentPk) window.abrirDetalhe(currentPk);
      })
      .catch(function () { alert('Erro ao excluir etapa.'); });
  };

  window.abrirDetalhe = async function (pk) {
    removerFormulariosEtapaModal();
    currentPk = pk;
    overlay.removeAttribute('hidden');
    overlay.setAttribute('aria-hidden', 'false');
    document.body.style.overflow = 'hidden';
    if (elBreadcrumbObra) elBreadcrumbObra.textContent = '';
    if (elBreadcrumbTipo) elBreadcrumbTipo.textContent = '';
    if (elMetaCreated) elMetaCreated.textContent = '';
    elTitulo.textContent = 'Carregando…';
    elDesc.textContent = '';
    elEtapas.innerHTML = '';
    if (elEtapasCounter) elEtapasCounter.textContent = '';
    if (elProgressFill) elProgressFill.style.width = '0%';
    if (elProgressText) elProgressText.textContent = '';
    elComments.innerHTML = '';
    elActivities.innerHTML = '';
    commentPendingFiles = [];
    if (elCommentFileInput) elCommentFileInput.value = '';
    if (elCommentText) elCommentText.value = '';
    renderCommentPendingFiles();
    if (elCommentSend) elCommentSend.disabled = true;
    switchTab('comments');
    try {
      var r = await fetch(detailUrl(pk), { credentials: 'same-origin' });
      var data = await r.json();
      if (!r.ok || !data.ok) throw new Error((data && data.error) || 'Erro ao carregar.');
      applyPendenciaPayload(data.pendencia);
    } catch (err) {
      alert(err.message || 'Erro');
      window.fecharDetalhe();
    }
  };

  window.fecharDetalhe = function () {
    closeDropdown();
    removerFormulariosEtapaModal();
    var needReload = trackhubListPageNeedsReload;
    trackhubListPageNeedsReload = false;
    overlay.setAttribute('hidden', '');
    overlay.setAttribute('aria-hidden', 'true');
    document.body.style.overflow = '';
    currentPk = null;
    currentData = null;
    window.thDetalheObraNome = '';
    window.thUsuarios = [];
    window.thUsuariosOutros = [];
    commentPendingFiles = [];
    if (elCommentFileInput) elCommentFileInput.value = '';
    renderCommentPendingFiles();
    if (needReload) {
      window.location.reload();
    }
  };

  if (btnClose) btnClose.addEventListener('click', window.fecharDetalhe);

  if (overlay) {
    overlay.addEventListener('click', function (e) {
      if (e.target === overlay) window.fecharDetalhe();
    });
  }

  /* -------- Notificar (modal existente) -------- */
  var etapaNotifPk = null;
  var canalNotif = 'wpp';

  window.fecharModal = function () {
    var mr = document.getElementById('modal-notificar');
    if (mr) mr.style.display = 'none';
  };

  window.switchModalTab = function (tab, btn) {
    canalNotif = tab;
    document.querySelectorAll('.modal-tab').forEach(function (t) {
      t.style.background = 'transparent';
      t.style.color = '#64748b';
      t.style.boxShadow = 'none';
    });
    if (btn) {
      btn.style.background = '#fff';
      btn.style.color = '#1e293b';
      btn.style.boxShadow = '0 1px 3px rgba(0,0,0,.08)';
    } else {
      var sel = document.querySelector('.modal-tab[data-tab="' + tab + '"]');
      if (sel) {
        sel.style.background = '#fff';
        sel.style.color = '#1e293b';
        sel.style.boxShadow = '0 1px 3px rgba(0,0,0,.08)';
      }
    }
    var wppEl = document.getElementById('modal-wpp');
    var emEl = document.getElementById('modal-email');
    if (wppEl) wppEl.style.display = tab === 'wpp' ? 'block' : 'none';
    if (emEl) emEl.style.display = tab === 'email' ? 'block' : 'none';
    var btnEnviar = document.getElementById('btn-modal-enviar');
    if (btnEnviar) btnEnviar.textContent = tab === 'wpp' ? 'Abrir WhatsApp' : 'Enviar e-mail';
  };

  window.enviarNotificacao = function () {
    var canal = canalNotif;
    var msg = canal === 'wpp' ? document.getElementById('modal-wpp-msg').value : document.getElementById('modal-email-msg').value;
    var contato = canal === 'wpp' ? document.getElementById('modal-wpp-numero').value : document.getElementById('modal-email-para').value;
    var nome = document.getElementById('modal-etapa-resp').textContent;
    if (canal === 'wpp' && contato) {
      var num = contato.replace(/\D/g, '');
      window.open('https://wa.me/55' + num + '?text=' + encodeURIComponent(msg), '_blank');
    }
    if (etapaNotifPk) {
      fetch(etapaNotificarUrl(etapaNotifPk), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': CSRF },
        body: JSON.stringify({
          canal: canal === 'wpp' ? 'whatsapp' : 'email',
          destinatario_nome: nome,
          destinatario_contato: contato,
          mensagem: msg,
        }),
      });
    }
    window.fecharModal();
  };

  window.thAbrirModalNotif = function (etapaPk, tituloEtapa, responsavel, wpp, email, tituloPendencia) {
    etapaNotifPk = etapaPk;
    document.getElementById('modal-etapa-titulo').textContent = tituloEtapa || 'Etapa';
    document.getElementById('modal-etapa-resp').textContent = responsavel || '—';
    document.getElementById('modal-wpp-numero').value = wpp || '';
    document.getElementById('modal-email-para').value = email || '';
    var msg = 'Olá ' + (responsavel || '') + ', pendência: ' + (tituloPendencia || '') + ' — etapa: ' + (tituloEtapa || '') + '.';
    document.getElementById('modal-wpp-msg').value = msg;
    document.getElementById('modal-email-msg').value = msg;
    var rootN = document.getElementById('modal-notificar');
    if (rootN) rootN.style.display = 'flex';
    var tabBtn = document.querySelector('.modal-tab[data-tab="wpp"]');
    window.switchModalTab('wpp', tabBtn);
  };

  var modalN = document.getElementById('modal-notificar');
  if (modalN) {
    modalN.addEventListener('click', function (e) {
      if (e.target === modalN) window.fecharModal();
    });
  }

  window.thFilaToggleCardMenu = function (btn) {
    var wrap = btn.closest('.th-card-menu-wrap');
    if (!wrap) return;
    var card = btn.closest('.th-card');
    var open = wrap.classList.contains('is-open');
    closeFilaCardMenus();
    closeEtapaMenus();
    if (!open) {
      wrap.classList.add('is-open');
      if (card) card.classList.add('th-card--menu-open');
    }
  };

  var filaListEl = document.querySelector('.th-list');
  if (filaListEl) {
    filaListEl.addEventListener('mouseenter', function (e) {
      var card = e.target.closest('.th-card');
      if (!card) return;
      if (card.classList.contains('th-card--menu-open')) return;
      if (document.querySelector('.th-card-menu-wrap.is-open')) closeFilaCardMenus();
    }, true);
  }

  window.thFilaEditarPendencia = function (pk) {
    closeFilaCardMenus();
    if (typeof window.abrirDetalhe === 'function') window.abrirDetalhe(pk);
  };

  window.thFilaExcluirPendencia = function (pk) {
    closeFilaCardMenus();
    if (!confirm('Excluir esta pendência e todos os dados associados?')) return;
    var f = document.getElementById('th-fila-del-' + pk);
    if (f) f.submit();
  };

  window.thFilaCancelarPendencia = function (pk) {
    closeFilaCardMenus();
    if (!confirm('Cancelar esta pendência? Ela ficará arquivada na fila, sem contar como pendente ativa.')) return;
    var f = document.getElementById('th-fila-cancel-' + pk);
    if (f) f.submit();
  };

  window.thFilaReativarPendencia = function (pk) {
    closeFilaCardMenus();
    if (!confirm('Reativar esta pendência? Ela voltará a contar como pendente na fila.')) return;
    var f = document.getElementById('th-fila-reativar-' + pk);
    if (f) f.submit();
  };

  function showFilaErroToast(msg) {
    var container = document.getElementById('messages-container');
    if (!container) {
      container = document.createElement('div');
      container.id = 'messages-container';
      container.style.cssText = 'position:fixed;top:1rem;right:1rem;z-index:9999;display:flex;flex-direction:column;gap:0.5rem;max-width:420px;pointer-events:none;';
      document.body.appendChild(container);
    }
    var toast = document.createElement('div');
    toast.className = 'toast-msg toast-error';
    toast.style.pointerEvents = 'auto';
    toast.innerHTML =
      '<div class="toast-icon"><i class="fas fa-exclamation-circle"></i></div>' +
      '<div class="toast-body"><p>' + esc(msg || 'Não foi possível concluir a pendência.') + '</p></div>' +
      '<button type="button" class="toast-close" onclick="this.closest(\'.toast-msg\').remove()"><i class="fas fa-times"></i></button>' +
      '<div class="toast-timer"></div>';
    container.appendChild(toast);
    setTimeout(function () {
      toast.classList.add('toast-exit');
      setTimeout(function () { toast.remove(); }, 300);
    }, 5000);
  }

  document.addEventListener('submit', function (ev) {
    var form = ev.target.closest('.th-fila-concluir-form');
    if (!form) return;
    ev.preventDefault();
    ev.stopPropagation();
    var pk = form.dataset.pk;
    var csrfInput = form.querySelector('[name=csrfmiddlewaretoken]');
    var csrf = csrfInput ? csrfInput.value : (CSRF || '');
    var fd = new FormData();
    fd.append('csrfmiddlewaretoken', csrf);
    fetch(form.action, {
      method: 'POST',
      headers: { 'Accept': 'application/json' },
      credentials: 'same-origin',
      body: fd,
    })
      .then(function (r) { return r.json(); })
      .then(function (d) {
        if (d.ok) {
          window.location.reload();
        } else {
          showFilaErroToast(d.error);
          if (pk && typeof window.abrirDetalhe === 'function') {
            window.abrirDetalhe(parseInt(pk, 10));
          }
        }
      })
      .catch(function () {
        showFilaErroToast('Erro ao concluir pendência. Tente novamente.');
      });
  });
})();
