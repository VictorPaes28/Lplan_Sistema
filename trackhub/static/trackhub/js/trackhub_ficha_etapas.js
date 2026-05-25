/**
 * Ficha completa da pendência — menu, editar/excluir etapa (AJAX) e reordenar (DnD).
 */
(function () {
  'use strict';

  var root = document.getElementById('th-ficha-etapas-root');
  if (!root) return;

  var CSRF = root.dataset.csrf || '';
  var pendenciaPk = root.dataset.pendenciaPk || '';
  var podeEditar = root.dataset.podeEditar === '1';
  var pendenciaStatus = root.dataset.pendenciaStatus || '';
  var podeReordenar =
    podeEditar && pendenciaStatus !== 'concluida' && pendenciaStatus !== 'cancelada';

  function urlPk(tpl, pk) {
    if (!tpl) return '';
    return tpl.replace(/\/0\//g, '/' + pk + '/');
  }

  var urlReordenar = root.dataset.urlReordenar || '';
  var urlEditarTpl = root.dataset.urlEditar || '';
  var urlDeletarTpl = root.dataset.urlDeletar || '';
  var urlReabrirTpl = root.dataset.urlReabrir || '';
  var list = document.getElementById('th-ficha-etapas-list');
  var editHost = document.getElementById('th-ficha-editar-etapa-host');
  var dragEtapaId = null;

  function esc(s) {
    return String(s || '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/"/g, '&quot;');
  }

  function closeMenus() {
    root.querySelectorAll('.th-etapa-menu-wrap.is-open').forEach(function (w) {
      w.classList.remove('is-open');
    });
  }

  document.addEventListener('click', function (e) {
    if (!e.target.closest('.th-etapa-menu-wrap')) closeMenus();
  });

  root.addEventListener('click', function (e) {
    var btn = e.target.closest('.th-etapa-menu-btn');
    if (!btn) return;
    e.stopPropagation();
    var wrap = btn.closest('.th-etapa-menu-wrap');
    if (!wrap) return;
    var open = wrap.classList.contains('is-open');
    closeMenus();
    if (!open) wrap.classList.add('is-open');
  });

  function getEtapaItem(pk) {
    return list && list.querySelector('.th-ficha-etapa-item[data-etapa-id="' + String(pk) + '"]');
  }

  function fecharEditarEtapa() {
    if (editHost) editHost.innerHTML = '';
  }

  window.thFichaFecharEditarEtapa = fecharEditarEtapa;

  function findResponsavelIdByNome(nome) {
    var el = document.getElementById('th-ficha-resp-blocos');
    if (!el || !nome) return '';
    var blocos;
    try {
      blocos = JSON.parse(el.textContent || '[]');
    } catch (e) {
      return '';
    }
    var alvo = String(nome).trim().toLowerCase();
    for (var b = 0; b < blocos.length; b++) {
      var pessoas = blocos[b].pessoas || [];
      for (var i = 0; i < pessoas.length; i++) {
        if (String(pessoas[i].nome || '').trim().toLowerCase() === alvo) {
          return String(pessoas[i].id);
        }
      }
    }
    return '';
  }

  window.thFichaEditarEtapa = function (pk) {
    closeMenus();
    var item = getEtapaItem(pk);
    if (!item) return;
    if (item.dataset.etapaStatus === 'concluida') {
      alert('Não é possível editar uma etapa já concluída.');
      return;
    }
    fecharEditarEtapa();
    var panelNova = document.getElementById('th-ficha-nova-etapa-panel');
    var btnNova = document.getElementById('th-ficha-btn-abrir-nova-etapa');
    if (panelNova) panelNova.hidden = true;
    if (btnNova) btnNova.style.display = '';

    var titulo = item.dataset.etapaTitulo || '';
    var respId = item.dataset.etapaResponsavel || findResponsavelIdByNome(item.dataset.etapaResponsavelNome);
    var prazo = item.dataset.etapaPrazo || '';
    var obs = item.dataset.etapaObservacao || '';
    var reqAss = item.dataset.etapaRequerAssinatura === '1';

    if (!editHost) return;

    var html =
      '<div id="th-ficha-form-editar-etapa" class="th-ficha-nova-etapa-card" data-etapa-id="' +
      esc(pk) +
      '" style="margin-top:12px;border:2px dashed #b8d4eb;background:#ebf6fd;position:relative;">' +
      '<button type="button" onclick="thFichaFecharEditarEtapa()" aria-label="Fechar" title="Fechar"' +
      ' style="position:absolute;top:10px;right:10px;width:28px;height:28px;border-radius:8px;border:1px solid #e2e8f0;background:#fff;color:#64748b;cursor:pointer;display:flex;align-items:center;justify-content:center;">' +
      '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg></button>' +
      '<div style="font-size:11px;font-weight:700;color:#2980b9;text-transform:uppercase;letter-spacing:.5px;margin-bottom:12px;padding-right:40px;">Editar etapa</div>' +
      '<div style="margin-bottom:10px;"><label style="font-size:12px;font-weight:600;color:#374151;margin-bottom:4px;display:block;">Título <span style="color:#ef4444">*</span></label>' +
      '<input type="text" name="titulo" value="' +
      esc(titulo) +
      '" class="th-filter-select" style="width:100%;box-sizing:border-box;"></div>' +
      '<div class="th-ficha-nova-etapa-grid" style="display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:12px;">' +
      '<div><label style="font-size:12px;font-weight:600;color:#374151;margin-bottom:5px;display:block;">Usuário responsável <span style="color:#ef4444">*</span></label>' +
      '<select name="responsavel_interno" class="th-filter-select" style="width:100%;box-sizing:border-box;"><option value="">Selecione…</option></select></div>' +
      '<div><label style="font-size:12px;font-weight:600;color:#374151;margin-bottom:5px;display:block;">Prazo da etapa</label>' +
      '<input type="date" name="prazo" value="' +
      esc(prazo) +
      '" class="th-filter-select" style="width:100%;box-sizing:border-box;"></div></div>' +
      '<div style="margin-bottom:12px;"><label style="font-size:12px;font-weight:600;color:#374151;margin-bottom:5px;display:block;">Observação</label>' +
      (window.ThRichText ? window.ThRichText.observacaoBlockHtml(obs) : '') +
      '</div>' +
      '<label class="th-assinatura-toggle" style="margin-bottom:12px;cursor:pointer;display:flex;align-items:flex-start;gap:8px;">' +
      '<input type="checkbox" name="requer_assinatura" value="1"' +
      (reqAss ? ' checked' : '') +
      ' style="margin-top:3px;cursor:pointer;">' +
      '<span style="font-size:12px;font-weight:600;color:#374151;">Esta etapa requer assinatura</span></label>' +
      '<button type="button" class="th-ficha-nova-etapa-submit" onclick="thFichaSalvarEditarEtapa()">Salvar alterações</button>' +
      '</div>';

    editHost.innerHTML = html;
    if (window.ThRichText) window.ThRichText.initAll(editHost);

    var sel = editHost.querySelector('select[name="responsavel_interno"]');
    if (sel && window.ThRespPicker) {
      var el = document.getElementById('th-ficha-resp-blocos');
      var blocos = [];
      try {
        blocos = JSON.parse((el && el.textContent) || '[]');
      } catch (e) {}
      function thFichaObraIdFromBlocos() {
        return blocos.length ? String(blocos[0].obra_id) : '';
      }
      function thParseTodosUsuariosFicha() {
        var todosEl = document.getElementById('th-todos-usuarios');
        if (!todosEl) return [];
        try { return JSON.parse(todosEl.textContent || '[]'); } catch (e) { return []; }
      }
      function thFichaObraNomeFromBlocos() {
        return blocos.length ? (blocos[0].obra_nome || '') : '';
      }
      window.ThRespPicker.attach(sel, function () {
        return blocos;
      }, thFichaObraIdFromBlocos, {
        zIndex: 1600,
        getOutrosFn: thParseTodosUsuariosFicha,
        getObraNomeFn: thFichaObraNomeFromBlocos,
      });
    }
    if (sel && respId) sel.value = respId;
    if (sel && sel._thRespRefresh) sel._thRespRefresh();

    editHost.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    var inp = editHost.querySelector('input[name="titulo"]');
    if (inp) inp.focus();
  };

  function thFichaObsFromForm(form) {
    if (!form) return '';
    var rt = form.querySelector('.th-richtext[data-th-richtext]');
    if (rt && window.ThRichText) {
      window.ThRichText.syncToTextarea(rt);
      var ta = form.querySelector('textarea[name="observacao"]');
      return ta ? ta.value : '';
    }
    var taOnly = form.querySelector('textarea[name="observacao"]');
    return taOnly ? taOnly.value : '';
  }

  window.thFichaSalvarEditarEtapa = function () {
    var form = document.getElementById('th-ficha-form-editar-etapa');
    if (!form) return;
    var etapaId = form.getAttribute('data-etapa-id');
    var titulo = (form.querySelector('input[name="titulo"]').value || '').trim();
    var resp = form.querySelector('select[name="responsavel_interno"]').value;
    if (!titulo || !resp) {
      alert('Preencha título e responsável.');
      return;
    }
    var data = new FormData();
    data.append('csrfmiddlewaretoken', CSRF);
    data.append('titulo', titulo);
    data.append('responsavel_interno', resp);
    data.append('prazo', form.querySelector('input[name="prazo"]').value || '');
    data.append('observacao', thFichaObsFromForm(form));
    data.append(
      'requer_assinatura',
      form.querySelector('input[name="requer_assinatura"]').checked ? '1' : ''
    );
    fetch(urlPk(urlEditarTpl, etapaId), {
      method: 'POST',
      body: data,
      credentials: 'same-origin',
      headers: { 'X-Requested-With': 'XMLHttpRequest' },
    })
      .then(function (r) {
        return r.json().then(function (d) {
          return { r: r, d: d };
        });
      })
      .then(function (x) {
        if (!x.r.ok || !x.d.success) {
          alert((x.d && x.d.error) || 'Erro ao salvar etapa.');
          return;
        }
        window.location.reload();
      })
      .catch(function () {
        alert('Erro ao salvar etapa.');
      });
  };

  window.thFichaReabrirEtapa = function (pk, titulo) {
    closeMenus();
    if (!confirm('Reabrir a etapa "' + (titulo || '') + '"? Ela voltará ao status pendente.')) return;
    var data = new FormData();
    data.append('csrfmiddlewaretoken', CSRF);
    fetch(urlPk(urlReabrirTpl, pk), {
      method: 'POST',
      body: data,
      credentials: 'same-origin',
      headers: { 'X-Requested-With': 'XMLHttpRequest' },
    })
      .then(function (r) {
        return r.json().then(function (d) {
          return { r: r, d: d };
        });
      })
      .then(function (x) {
        if (!x.r.ok || !x.d.success) {
          alert((x.d && x.d.error) || 'Erro ao reabrir etapa.');
          return;
        }
        window.location.reload();
      })
      .catch(function () {
        alert('Erro ao reabrir etapa.');
      });
  };

  window.thFichaExcluirEtapa = function (pk, titulo) {
    closeMenus();
    if (!confirm('Excluir a etapa "' + (titulo || '') + '"? Esta ação não pode ser desfeita.')) return;
    var data = new FormData();
    data.append('csrfmiddlewaretoken', CSRF);
    fetch(urlPk(urlDeletarTpl, pk), {
      method: 'POST',
      body: data,
      credentials: 'same-origin',
      headers: { 'X-Requested-With': 'XMLHttpRequest' },
    })
      .then(function (r) {
        return r.json().then(function (d) {
          return { r: r, d: d };
        });
      })
      .then(function (x) {
        if (!x.r.ok || !x.d.success) {
          alert((x.d && x.d.error) || 'Erro ao excluir etapa.');
          return;
        }
        window.location.reload();
      })
      .catch(function () {
        alert('Erro ao excluir etapa.');
      });
  };

  function getDragAfterEtapa(clientY) {
    if (!list) return null;
    var draggable = [].slice.call(list.querySelectorAll('.th-ficha-etapa-item[draggable="true"]'));
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

  function updateEtapaNumbers() {
    if (!list) return;
    var items = list.querySelectorAll('.th-ficha-etapa-item');
    items.forEach(function (item, idx) {
      var circle = item.querySelector('.th-ficha-etapa-num');
      if (circle && item.dataset.etapaStatus !== 'concluida') {
        circle.textContent = String(idx + 1);
      }
    });
  }

  function persistEtapasOrder(ordemIds) {
    fetch(urlReordenar, {
      method: 'POST',
      credentials: 'same-origin',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': CSRF,
        'X-Requested-With': 'XMLHttpRequest',
      },
      body: JSON.stringify({ ordem_ids: ordemIds }),
    })
      .then(function (r) {
        return r.json().then(function (d) {
          return { r: r, d: d };
        });
      })
      .then(function (x) {
        if (!x.r.ok || !x.d.ok) {
          alert((x.d && x.d.error) || 'Não foi possível reordenar as etapas.');
          window.location.reload();
          return;
        }
        updateEtapaNumbers();
      })
      .catch(function () {
        alert('Erro ao reordenar etapas.');
        window.location.reload();
      });
  }

  if (podeReordenar && list) {
    list.querySelectorAll('.th-ficha-etapa-item').forEach(function (item) {
      item.setAttribute('draggable', 'true');
      item.setAttribute('title', 'Arraste para alterar a ordem das etapas');
      item.addEventListener('dragstart', function (ev) {
        if (ev.target.closest && ev.target.closest('button, a, input, textarea, select, .th-etapa-menu-wrap')) {
          ev.preventDefault();
          return;
        }
        dragEtapaId = item.getAttribute('data-etapa-id');
        ev.dataTransfer.setData('text/plain', dragEtapaId);
        ev.dataTransfer.effectAllowed = 'move';
        item.classList.add('th-etapa-item--dragging');
      });
      item.addEventListener('dragend', function () {
        item.classList.remove('th-etapa-item--dragging');
        dragEtapaId = null;
      });
    });

    list.addEventListener('dragover', function (ev) {
      if (!dragEtapaId) return;
      ev.preventDefault();
      if (ev.dataTransfer) ev.dataTransfer.dropEffect = 'move';
    });

    list.addEventListener('drop', function (ev) {
      ev.preventDefault();
      var rawId = (ev.dataTransfer && ev.dataTransfer.getData('text/plain')) || dragEtapaId;
      if (!rawId) return;
      var draggedEl = list.querySelector('.th-ficha-etapa-item[data-etapa-id="' + String(rawId) + '"]');
      if (!draggedEl) return;
      var afterEl = getDragAfterEtapa(ev.clientY);
      if (afterEl === draggedEl) return;
      if (afterEl == null) {
        list.appendChild(draggedEl);
      } else {
        list.insertBefore(draggedEl, afterEl);
      }
      var ids = [].map.call(
        list.querySelectorAll('.th-ficha-etapa-item[draggable="true"]'),
        function (node) {
          return parseInt(node.getAttribute('data-etapa-id'), 10);
        }
      );
      updateEtapaNumbers();
      persistEtapasOrder(ids);
    });
  }
})();
