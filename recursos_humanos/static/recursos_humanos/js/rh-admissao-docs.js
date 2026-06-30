(function () {
  var panel = document.querySelector('.rh-admission-panel');
  if (!panel) return;

  var toastRoot = document.getElementById('rh-adm-doc-toast-root');
  if (!toastRoot) {
    toastRoot = document.createElement('div');
    toastRoot.id = 'rh-adm-doc-toast-root';
    toastRoot.className = 'rh-adm-doc-toast-root';
    toastRoot.setAttribute('aria-live', 'polite');
    document.body.appendChild(toastRoot);
  }

  function getCsrf() {
    var input = document.querySelector('input[name=csrfmiddlewaretoken]');
    return input ? input.value : '';
  }

  function escapeAttr(value) {
    return String(value || '')
      .replace(/&/g, '&amp;')
      .replace(/"/g, '&quot;')
      .replace(/</g, '&lt;');
  }

  function showToast(message, type) {
    var el = document.createElement('div');
    el.className = 'rh-adm-doc-toast rh-adm-doc-toast--' + (type || 'success');
    el.textContent = message;
    toastRoot.appendChild(el);
    window.setTimeout(function () {
      el.classList.add('is-leaving');
      window.setTimeout(function () { el.remove(); }, 220);
    }, 3200);
  }

  function findDocItem(docId) {
    return panel.querySelector('.rh-doc-item[data-doc-id="' + docId + '"]');
  }

  function setButtonLoading(btn, loading) {
    if (!btn) return;
    btn.disabled = loading;
    if (loading) {
      btn.dataset.rhOriginalHtml = btn.innerHTML;
      btn.innerHTML = '<i class="fas fa-spinner fa-spin" aria-hidden="true"></i>';
    } else if (btn.dataset.rhOriginalHtml) {
      btn.innerHTML = btn.dataset.rhOriginalHtml;
      delete btn.dataset.rhOriginalHtml;
    }
  }

  function setFormUploading(form, uploading) {
    var item = form.closest('.rh-doc-item');
    if (item) item.classList.toggle('rh-doc-item--uploading', uploading);
    var submitBtn = form.querySelector('button[type="submit"]');
    setButtonLoading(submitBtn, uploading);
  }

  function updateResumo(resumo) {
    if (!resumo) return;
    var el = document.getElementById('rh-adm-doc-resumo');
    if (el) {
      el.textContent = resumo.recebidos + '/' + resumo.total + ' recebidos';
      el.classList.toggle('ok', !!resumo.completo);
      el.classList.toggle('bad', !resumo.completo);
    }
  }

  function updateGrupos(grupos) {
    if (!grupos || !grupos.length) return;
    grupos.forEach(function (g) {
      var grupo = panel.querySelector('.rh-doc-grupo[data-grupo-id="' + g.id + '"]');
      if (!grupo) return;
      var ratio = grupo.querySelector('.rh-doc-grupo-ratio');
      if (ratio) ratio.textContent = g.recebidos + '/' + g.total;
      var fill = grupo.querySelector('.rh-progress-fill');
      if (fill) {
        var pct = g.total ? Math.round((g.recebidos / g.total) * 100) : 0;
        fill.style.width = pct + '%';
        fill.classList.remove('ok', 'bad', 'warn');
        if (g.header_state === 'done') fill.classList.add('ok');
        else if (g.header_state === 'missing') fill.classList.add('bad');
        else fill.classList.add('warn');
      }
      var header = grupo.querySelector('.rh-doc-grupo-header');
      if (header) {
        header.classList.remove('rh-doc-grupo-header--done', 'rh-doc-grupo-header--missing', 'rh-doc-grupo-header--warn');
        header.classList.add('rh-doc-grupo-header--' + g.header_state);
      }
    });
  }

  function upsertEncaminharBanner(docPayload) {
    if (!docPayload || !docPayload.pode_encaminhar_validacao) return;
    var existing = document.getElementById('rh-adm-encaminhar-banner');
    if (existing) {
      existing.hidden = false;
      return;
    }
    var anchor = panel.querySelector('.rh-doc-grupos');
    if (!anchor) return;
    var encaminharAction = anchor.getAttribute('data-encaminhar-action')
      || ('/rh/admissao/' + docPayload.colaborador_id + '/acao/');
    var wrap = document.createElement('div');
    wrap.id = 'rh-adm-encaminhar-banner';
    wrap.className = 'rh-banner rh-banner-success rh-adm-encaminhar-banner';
    wrap.innerHTML =
      '<i class="fas fa-check-circle" aria-hidden="true"></i>' +
      '<div><strong>Todos os documentos conferidos</strong>' +
      '<p class="rh-muted">Pronto para encaminhar à validação final</p></div>' +
      '<form method="post" action="' + encaminharAction + '" class="rh-adm-encaminhar-form">' +
      '<input type="hidden" name="csrfmiddlewaretoken" value="' + getCsrf() + '">' +
      '<input type="hidden" name="acao" value="avancar">' +
      '<button type="submit" class="rh-btn rh-btn-success"><i class="fas fa-arrow-right"></i> Encaminhar à validação final</button>' +
      '</form>';
    anchor.insertAdjacentElement('afterend', wrap);
  }

  function updateDateHints(body, doc) {
    if (!body) return;
    var hints = body.querySelectorAll('.rh-doc-row-hint:not(.rh-doc-row-hint--instr)');
    hints.forEach(function (h) { h.remove(); });
    if (doc.data_emissao) {
      var hint = document.createElement('span');
      hint.className = 'rh-doc-row-hint';
      hint.textContent = 'Emitido: ' + doc.data_emissao + (doc.vencimento ? ' · Vence: ' + doc.vencimento : '');
      body.appendChild(hint);
    } else if (doc.observacao) {
      var obs = document.createElement('span');
      obs.className = 'rh-doc-row-hint';
      obs.textContent = doc.observacao;
      body.appendChild(obs);
    }
  }

  function buildThumbHtml(doc) {
    if (!doc.tem_arquivo || !doc.arquivo_url) return '';
    var title = 'Visualizar ' + (doc.arquivo_nome || 'arquivo');
    var inner;
    if (doc.arquivo_is_image) {
      inner = '<img src="' + escapeAttr(doc.arquivo_url) + '" alt="' + escapeAttr(doc.arquivo_nome) + '" class="rh-doc-file-thumb">';
    } else if (doc.arquivo_is_pdf) {
      inner = '<span class="rh-doc-file-thumb rh-doc-file-thumb--pdf"><iframe src="' + escapeAttr(doc.arquivo_url) + '" title="' + escapeAttr(doc.arquivo_nome) + '" tabindex="-1"></iframe></span>';
    } else {
      inner = '<span class="rh-doc-file-thumb rh-doc-file-thumb--icon"><i class="fas ' + escapeAttr(doc.arquivo_icon || 'fa-file') + '" aria-hidden="true"></i></span>';
    }
    return '<a href="' + escapeAttr(doc.arquivo_url) + '" class="rh-doc-file-thumb-link" target="_blank" rel="noopener" title="' + escapeAttr(title) + '">' + inner + '</a>';
  }

  function getDocNextUrl(item) {
    var hidden = item && item.querySelector('input[name="next"]');
    return hidden ? hidden.value : '';
  }

  function buildActionGroupHtml(doc, nextUrl) {
    if (!doc.tem_arquivo) return '';
    var html = '<div class="rh-doc-action-group">';
    if (doc.aguardando_aprovacao && doc.approve_url) {
      html +=
        '<form method="post" action="' + escapeAttr(doc.approve_url) + '" class="rh-doc-action-form rh-doc-approve-form js-rh-doc-ajax-approve">' +
        '<input type="hidden" name="csrfmiddlewaretoken" value="' + escapeAttr(getCsrf()) + '">' +
        '<input type="hidden" name="next" value="' + escapeAttr(nextUrl) + '">' +
        '<button type="submit" class="rh-doc-action-btn rh-doc-action-btn--ok" title="Aprovar documento" aria-label="Aprovar ' + escapeAttr(doc.doc_nome || 'documento') + '">' +
        '<i class="fas fa-check" aria-hidden="true"></i></button></form>';
    }
    if (doc.aguardando_aprovacao || doc.tem_arquivo) {
      html +=
        '<button type="button" class="rh-doc-action-btn rh-doc-action-btn--reject" title="Rejeitar ou remover" aria-label="Rejeitar ' + escapeAttr(doc.doc_nome || 'documento') + '" ' +
        'data-doc-reject="' + doc.doc_id + '" data-doc-nome="' + escapeAttr(doc.doc_nome || '') + '">' +
        '<i class="fas fa-times" aria-hidden="true"></i></button>';
    }
    html += '</div>';
    return html;
  }

  function upsertRowEndAssets(item, doc, nextUrl) {
    var rowEnd = item.querySelector('.rh-doc-row-end');
    if (!rowEnd) return;
    var resolvedNext = nextUrl || getDocNextUrl(item);
    rowEnd.querySelectorAll('.rh-doc-file-thumb-link, .rh-doc-action-group, .rh-doc-upload-form').forEach(function (el) {
      el.remove();
    });
    var pill = rowEnd.querySelector('.rh-doc-pill');
    if (doc.tem_arquivo) {
      var wrap = document.createElement('div');
      wrap.innerHTML = buildThumbHtml(doc) + buildActionGroupHtml(doc, resolvedNext);
      while (wrap.firstChild) {
        if (pill) rowEnd.insertBefore(wrap.firstChild, pill);
        else rowEnd.appendChild(wrap.firstChild);
      }
    }
  }

  function applyDocReceived(doc) {
    var item = findDocItem(doc.doc_id);
    if (!item) return;
    var nextUrl = getDocNextUrl(item);
    item.dataset.docStatus = 'ok';
    item.classList.remove('rh-doc-item--with-panel', 'rh-doc-item--upload-error', 'rh-doc-item--uploading');

    var icon = item.querySelector('.rh-doc-row-icon');
    if (icon) {
      icon.className = 'rh-doc-row-icon rh-doc-row-icon--ok';
      icon.innerHTML = '<i class="fas fa-check-circle"></i>';
    }

    var name = item.querySelector('.rh-doc-row-name');
    if (name) name.classList.remove('is-muted');

    item.querySelectorAll('.rh-doc-approve-panel, .rh-doc-upload-panel, .rh-doc-upload-form').forEach(function (el) {
      el.remove();
    });

    var pill = item.querySelector('.rh-doc-pill');
    if (pill) {
      pill.className = 'rh-doc-pill rh-doc-pill--ok';
      pill.textContent = doc.status_label || 'Recebido';
    }

    upsertRowEndAssets(item, doc, nextUrl);
    updateDateHints(item.querySelector('.rh-doc-row-body'), doc);
    item.classList.add('rh-doc-item--just-approved');
    window.setTimeout(function () { item.classList.remove('rh-doc-item--just-approved'); }, 900);
  }

  function applyDocPendingApproval(doc) {
    var item = findDocItem(doc.doc_id);
    if (!item) return;
    var nextUrl = getDocNextUrl(item);
    item.dataset.docStatus = 'pending';
    item.classList.remove('rh-doc-item--uploading');

    var icon = item.querySelector('.rh-doc-row-icon');
    if (icon) {
      icon.className = 'rh-doc-row-icon rh-doc-row-icon--pending';
      icon.innerHTML = '<i class="fas fa-exclamation-circle"></i>';
    }

    var name = item.querySelector('.rh-doc-row-name');
    if (name) name.classList.remove('is-muted');

    item.querySelectorAll('.rh-doc-upload-panel, .rh-doc-upload-form, .rh-doc-approve-panel').forEach(function (el) {
      el.remove();
    });

    var pill = item.querySelector('.rh-doc-pill');
    if (pill) {
      pill.className = 'rh-doc-pill rh-doc-pill--pending';
      pill.textContent = doc.status_label || 'Aguardando aprovação';
    }

    upsertRowEndAssets(item, doc, nextUrl);
    updateDateHints(item.querySelector('.rh-doc-row-body'), doc);
  }

  function applyDocRejected(doc) {
    var item = findDocItem(doc.doc_id);
    if (!item) return;
    item.dataset.docStatus = 'missing';
    item.classList.remove('rh-doc-item--with-panel', 'rh-doc-item--uploading');

    var icon = item.querySelector('.rh-doc-row-icon');
    if (icon) {
      icon.className = 'rh-doc-row-icon rh-doc-row-icon--missing';
      icon.innerHTML = '<i class="far fa-circle"></i>';
    }

    var name = item.querySelector('.rh-doc-row-name');
    if (name) name.classList.add('is-muted');

    var rowEnd = item.querySelector('.rh-doc-row-end');
    if (rowEnd) {
      rowEnd.querySelectorAll('.rh-doc-file-thumb-link, .rh-doc-action-group, .rh-doc-reenvio-form').forEach(function (el) {
        el.remove();
      });
      var pill = rowEnd.querySelector('.rh-doc-pill');
      if (pill) {
        pill.className = 'rh-doc-pill rh-doc-pill--missing';
        pill.textContent = doc.status_label || 'Faltando';
      }
    }

    item.querySelectorAll('.rh-doc-approve-panel, .rh-doc-upload-panel, .rh-doc-upload-form').forEach(function (el) {
      el.remove();
    });

    updateDateHints(item.querySelector('.rh-doc-row-body'), doc);
  }

  function applyDocPayload(doc) {
    if (!doc) return;
    updateResumo(doc.resumo);
    updateGrupos(doc.grupos);
    if (doc.status === 'ok') {
      applyDocReceived(doc);
      upsertEncaminharBanner(doc);
    } else if (doc.status === 'pending' && doc.aguardando_aprovacao) {
      applyDocPendingApproval(doc);
    } else if (doc.status === 'missing') {
      applyDocRejected(doc);
    }
  }

  function buildUploadFormData(form) {
    var fd = new FormData(form);
    if (form.classList.contains('js-rh-doc-ajax-upload')) {
      var fileInput = form.querySelector('input[type="file"]');
      if (fileInput && fileInput.files && fileInput.files[0]) {
        fd.set('arquivo', fileInput.files[0], fileInput.files[0].name);
      }
    }
    return fd;
  }

  function postFormAjax(form, submitBtn, onStart, onEnd) {
    var action = form.getAttribute('action');
    if (!action) return Promise.reject();

    var fd = form.classList.contains('js-rh-doc-ajax-upload')
      ? buildUploadFormData(form)
      : new FormData(form);

    if (onStart) onStart();
    else setButtonLoading(submitBtn, true);

    return fetch(action, {
      method: 'POST',
      body: fd,
      credentials: 'same-origin',
      headers: {
        'X-Requested-With': 'XMLHttpRequest',
      },
    })
      .then(function (r) {
        return r.json().then(function (data) {
          return { ok: r.ok, data: data };
        });
      })
      .finally(function () {
        if (onEnd) onEnd();
        else setButtonLoading(submitBtn, false);
      });
  }

  function validateUploadForm(form) {
    var fileInput = form.querySelector('input[type="file"]');
    var dateInput = form.querySelector('input[type="date"]');
    if (form.classList.contains('rh-doc-upload-panel')) {
      if (!dateInput || !dateInput.value) {
        showToast('Informe a data de emissão do documento.', 'error');
        return false;
      }
      if (window.RhDocEmissao && !window.RhDocEmissao.valido(dateInput)) {
        showToast('Confira a data de emissão informada.', 'error');
        return false;
      }
      if (!fileInput || !fileInput.files.length) {
        showToast('Selecione um arquivo antes de enviar.', 'error');
        return false;
      }
    } else if (!fileInput || !fileInput.files.length) {
      showToast('Selecione um arquivo antes de enviar.', 'error');
      return false;
    }
    return true;
  }

  function submitUploadForm(form) {
    if (!validateUploadForm(form)) return;
    var submitBtn = form.querySelector('button[type="submit"]') || form.querySelector('.rh-btn-upload');
    postFormAjax(form, submitBtn, function () { setFormUploading(form, true); }, function () { setFormUploading(form, false); })
      .then(function (res) {
        if (res.ok && res.data.ok) {
          showToast(res.data.message, 'success');
          applyDocPayload(res.data.doc);
          return;
        }
        showToast((res.data && res.data.message) || 'Não foi possível enviar o arquivo.', 'error');
      })
      .catch(function () {
        showToast('Erro de conexão. Tente novamente.', 'error');
      });
  }

  panel.addEventListener('change', function (e) {
    var input = e.target;
    if (!input.matches('.js-rh-doc-ajax-upload input[type="file"]')) return;
    var form = input.closest('.js-rh-doc-ajax-upload');
    if (!form || form.classList.contains('rh-doc-upload-panel')) return;
    submitUploadForm(form);
  });

  panel.addEventListener('rh-doc-panel-autosubmit', function (e) {
    var form = e.target.closest('.js-rh-doc-ajax-upload.rh-doc-upload-panel');
    if (!form || !panel.contains(form)) return;
    e.preventDefault();
    submitUploadForm(form);
  });

  panel.addEventListener('submit', function (e) {
    var approveForm = e.target.closest('.js-rh-doc-ajax-approve');
    if (approveForm) {
      e.preventDefault();
      var approveDate = approveForm.querySelector('.js-rh-emissao-input');
      if (approveDate && window.RhDocEmissao && !window.RhDocEmissao.valido(approveDate)) {
        showToast('Confira a data de emissão informada.', 'error');
        return;
      }
      var approveBtn = approveForm.querySelector('button[type="submit"]');
      postFormAjax(approveForm, approveBtn)
        .then(function (res) {
          if (res.ok && res.data.ok) {
            showToast(res.data.message, 'success');
            applyDocPayload(res.data.doc);
            return;
          }
          showToast((res.data && res.data.message) || 'Não foi possível aprovar o documento.', 'error');
        })
        .catch(function () {
          showToast('Erro de conexão. Tente novamente.', 'error');
        });
      return;
    }

    var uploadForm = e.target.closest('.js-rh-doc-ajax-upload');
    if (uploadForm) {
      e.preventDefault();
      if (uploadForm.classList.contains('rh-doc-upload-panel')) return;
      submitUploadForm(uploadForm);
    }
  });

  var rejectForm = document.getElementById('rh-doc-reject-form');
  var rejectModal = document.getElementById('rh-doc-reject-modal');
  if (rejectForm) {
    rejectForm.addEventListener('submit', function (e) {
      e.preventDefault();
      var obs = document.getElementById('rh-doc-reject-observacao');
      if (obs && !obs.value.trim()) {
        obs.focus();
        return;
      }
      var btn = rejectForm.querySelector('button[type="submit"]');
      postFormAjax(rejectForm, btn)
        .then(function (res) {
          if (res.ok && res.data.ok) {
            showToast(res.data.message, 'success');
            applyDocPayload(res.data.doc);
            if (rejectModal && window.RhMotion) {
              window.RhMotion.closeRhModal(rejectModal);
            }
            if (obs) obs.value = '';
            return;
          }
          showToast((res.data && res.data.message) || 'Não foi possível rejeitar o documento.', 'error');
        })
        .catch(function () {
          showToast('Erro de conexão. Tente novamente.', 'error');
        });
    });
  }
})();
