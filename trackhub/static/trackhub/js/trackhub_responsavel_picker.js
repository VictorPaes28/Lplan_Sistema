/**
 * Seletor de responsável TrackHub — mesmo visual do popover de Restrições (impedimentos).
 */
(function (global) {
  'use strict';

  var Z_FORM = 1400;
  var Z_MODAL = 12650;
  var activePop = null;

  function escapeHtml(s) {
    var d = document.createElement('div');
    d.textContent = s == null ? '' : String(s);
    return d.innerHTML;
  }

  function avatarColor(name) {
    var colors = ['#3498db', '#2980b9', '#5dade2', '#577590', '#7f8c8d', '#34495e'];
    var hash = 0;
    var str = name || '';
    for (var i = 0; i < str.length; i += 1) {
      hash = str.charCodeAt(i) + ((hash << 5) - hash);
    }
    return colors[Math.abs(hash) % colors.length];
  }

  function userIniciais(u) {
    if (u && u.iniciais) return u.iniciais;
    var nome = (u && u.nome ? u.nome : '').trim();
    var parts = nome.split(/\s+/).filter(Boolean);
    if (!parts.length) return '?';
    if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
    return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
  }

  function getScrollParents(el) {
    var list = [];
    var node = el && el.parentElement;
    while (node) {
      var st = global.getComputedStyle(node);
      var oy = st.overflowY;
      var ox = st.overflowX;
      if (/(auto|scroll|overlay)/.test(oy + ' ' + ox)) {
        list.push(node);
      }
      node = node.parentElement;
    }
    list.push(global);
    return list;
  }

  function unbindPopoverScroll(pop) {
    if (!pop || !pop._thScrollHandler) return;
    (pop._thScrollTargets || []).forEach(function (target) {
      target.removeEventListener('scroll', pop._thScrollHandler, true);
    });
    pop._thScrollHandler = null;
    pop._thScrollTargets = null;
  }

  /** Fecha ao rolar qualquer área que não seja o próprio popover (evita “fantasma” fixo na tela). */
  function bindCloseOnScroll(pop, trigger, wrap) {
    unbindPopoverScroll(pop);
    var onScroll = function (e) {
      if (!activePop || activePop !== pop) return;
      var el = e.target;
      if (el === pop || (el && el.nodeType === 1 && pop.contains(el))) return;
      var body = pop.querySelector('.imp-resp-popover-body');
      if (body && (el === body || (el.contains && body.contains(el)))) return;
      if (wrap && el && el.contains && el.contains(wrap)) return;
      closePopover();
    };
    pop._thScrollHandler = onScroll;
    pop._thScrollTargets = getScrollParents(trigger);
    pop._thScrollTargets.forEach(function (target) {
      target.addEventListener('scroll', onScroll, true);
    });
  }

  function closePopover() {
    if (activePop) {
      unbindPopoverScroll(activePop);
      if (activePop._thWrap) {
        activePop._thWrap.classList.remove('th-resp-picker-wrap--open');
        activePop._thWrap = null;
      }
      activePop.remove();
      activePop = null;
    }
    if (document._thRespDocClose) {
      document.removeEventListener('click', document._thRespDocClose, true);
      document.removeEventListener('keydown', document._thRespKeyClose, true);
      document._thRespDocClose = null;
      document._thRespKeyClose = null;
    }
  }

  function dedupeOutros(obraPessoas, outros) {
    if (!outros || !outros.length) return [];
    var seen = {};
    (obraPessoas || []).forEach(function (p) {
      seen[String(p.id)] = true;
    });
    return outros.filter(function (p) {
      return !seen[String(p.id)];
    });
  }

  function obraSectionLabel(nome) {
    var label = nome || 'Obra';
    if (!/^1\s*[-–—]\s*/i.test(label)) label = '1 - ' + label;
    return label;
  }

  function buildSections(data, obraId, outros, obraNomeFallback) {
    data = data || [];
    var sections = [];
    if (obraId === '__single__') {
      data.forEach(function (b) {
        sections.push({
          label: b.obra_nome || 'Obra',
          pessoas: b.pessoas || [],
        });
      });
      return sections;
    }
    if (obraId) {
      var obraBlock = null;
      for (var i = 0; i < data.length; i += 1) {
        if (String(data[i].obra_id) === String(obraId)) {
          obraBlock = data[i];
          break;
        }
      }
      var pessoasObra = obraBlock ? (obraBlock.pessoas || []) : [];
      var obraNome = (obraBlock && obraBlock.obra_nome) || obraNomeFallback || 'Obra';
      sections.push({
        label: obraSectionLabel(obraNome),
        pessoas: pessoasObra,
      });
      var outrosFiltrados = dedupeOutros(pessoasObra, outros);
      if (outrosFiltrados.length) {
        sections.push({ label: '2 - Outros', pessoas: outrosFiltrados });
      }
      return sections;
    }
    data.forEach(function (b) {
      var pessoas = b.pessoas || [];
      if (!pessoas.length) return;
      sections.push({
        label: b.obra_nome || ('Obra #' + b.obra_id),
        pessoas: pessoas,
      });
    });
    return sections;
  }

  function appendSectionPopoverHtml(parts, sec) {
    parts.push('<div class="th-resp-section">');
    parts.push('<div class="imp-resp-section-label">' + escapeHtml(sec.label) + '</div>');
    var pessoas = sec.pessoas || [];
    if (pessoas.length) {
      pessoas.forEach(function (u) {
        var bg = avatarColor(u.nome);
        var ini = escapeHtml(userIniciais(u));
        var nome = escapeHtml(u.nome || '');
        var id = String(u.id);
        parts.push(
          '<div class="imp-resp-user-row" data-user-id="' +
            escapeHtml(id) +
            '">' +
            '<div class="imp-resp-avatar" style="background:' +
            bg +
            '">' +
            ini +
            '</div>' +
            '<span class="imp-resp-user-nome">' +
            nome +
            '</span>' +
            '</div>'
        );
      });
    } else {
      parts.push(
        '<p class="th-resp-section-empty">Nenhum usuário designado nesta obra.</p>'
      );
    }
    parts.push('</div>');
  }

  function syncSelectOptions(selectEl, data, obraId, outros, obraNomeFallback) {
    if (!selectEl) return;
    var current = (selectEl.value || '').trim();
    selectEl.innerHTML = '';
    var placeholder = document.createElement('option');
    placeholder.value = '';
    placeholder.textContent = 'Selecione...';
    selectEl.appendChild(placeholder);

    var sections = buildSections(data, obraId, outros, obraNomeFallback);
    var seen = {};
    sections.forEach(function (sec) {
      (sec.pessoas || []).forEach(function (p) {
        var idStr = String(p.id);
        if (seen[idStr]) return;
        seen[idStr] = true;
        var opt = document.createElement('option');
        opt.value = idStr;
        opt.textContent = p.nome || ('Usuário ' + idStr);
        selectEl.appendChild(opt);
      });
    });
    var preserveId = (selectEl.dataset.thRespPreserveId || '').trim();
    var preserveNome = (selectEl.dataset.thRespPreserveNome || '').trim();
    if (preserveId && !seen[preserveId]) {
      var extra = document.createElement('option');
      extra.value = preserveId;
      extra.textContent = preserveNome || ('Usuário ' + preserveId);
      selectEl.appendChild(extra);
      seen[preserveId] = true;
    }
    var hasCurrent = Array.from(selectEl.options).some(function (o) {
      return o.value === current;
    });
    if (hasCurrent) selectEl.value = current;
    else if (preserveId && seen[preserveId]) selectEl.value = preserveId;
  }

  function updateTrigger(trigger, selectEl) {
    if (!trigger || !selectEl) return;
    var labelEl = trigger.querySelector('.th-resp-picker-label');
    var avEl = trigger.querySelector('.th-resp-picker-avatar');
    var val = (selectEl.value || '').trim();
    if (!val) {
      if (labelEl) labelEl.textContent = 'Selecione…';
      if (avEl) avEl.style.display = 'none';
      return;
    }
    var nome = '';
    var opt = selectEl.options[selectEl.selectedIndex];
    if (opt) nome = opt.textContent || '';
    if (labelEl) labelEl.textContent = nome || 'Selecione…';
    if (avEl) {
      avEl.style.display = 'flex';
      avEl.style.background = avatarColor(nome);
      avEl.textContent = userIniciais({ nome: nome });
    }
  }

  function openPopover(trigger, selectEl, getDataFn, getObraIdFn, getOutrosFn, zIndex) {
    var data = getDataFn() || [];
    var obraId = getObraIdFn ? getObraIdFn() : '';
    var outros = getOutrosFn ? getOutrosFn() : null;
    var obraNomeFallback = selectEl._thRespGetObraNome ? selectEl._thRespGetObraNome() : '';
    var sections = buildSections(data, obraId, outros, obraNomeFallback);

    var parts = [];
    parts.push('<div class="imp-resp-popover-search">');
    parts.push('<i class="fas fa-search" aria-hidden="true"></i>');
    parts.push(
      '<input type="text" placeholder="Busque ou insira o e-mail..." class="imp-resp-search-input" autocomplete="off">'
    );
    parts.push('</div><div class="imp-resp-popover-body">');

    sections.forEach(function (sec) {
      appendSectionPopoverHtml(parts, sec);
    });

    parts.push('</div>');

    var pop = document.createElement('div');
    var wrap = trigger.closest('.th-resp-picker-wrap');
    pop.className = 'imp-resp-popover th-resp-popover-trackhub th-resp-popover--anchored';
    pop.innerHTML = parts.join('');
    pop._thTrigger = trigger;
    pop.style.zIndex = String(zIndex != null ? zIndex : Z_FORM);

    if (wrap) {
      pop._thWrap = wrap;
      wrap.classList.add('th-resp-picker-wrap--open');
      wrap.appendChild(pop);
    } else {
      document.body.appendChild(pop);
      pop.classList.remove('th-resp-popover--anchored');
      pop.style.position = 'fixed';
      var rect = trigger.getBoundingClientRect();
      pop.style.top = rect.bottom + 4 + 'px';
      pop.style.left = rect.left + 'px';
    }

    activePop = pop;
    bindCloseOnScroll(pop, trigger, wrap);

    var searchInput = pop.querySelector('.imp-resp-search-input');
    if (searchInput) {
      searchInput.addEventListener('click', function (e) {
        e.stopPropagation();
      });
      searchInput.addEventListener('keydown', function (e) {
        e.stopPropagation();
      });
      setTimeout(function () {
        try {
          searchInput.focus();
        } catch (e) {}
      }, 0);
      searchInput.addEventListener('input', function () {
        var q = (this.value || '').toLowerCase();
        pop.querySelectorAll('.th-resp-section').forEach(function (sec) {
          var any = false;
          var emptyEl = sec.querySelector('.th-resp-section-empty');
          sec.querySelectorAll('.imp-resp-user-row').forEach(function (row) {
            var nomeEl = row.querySelector('.imp-resp-user-nome');
            var t = nomeEl ? nomeEl.textContent.toLowerCase() : '';
            var show = !q || t.indexOf(q) !== -1;
            row.style.display = show ? '' : 'none';
            if (show) any = true;
          });
          if (emptyEl) {
            if (!q) {
              emptyEl.style.display = '';
              any = true;
            } else {
              emptyEl.style.display = 'none';
            }
          }
          sec.style.display = any ? '' : 'none';
        });
      });
    }

    pop.querySelectorAll('.imp-resp-user-row').forEach(function (row) {
      row.addEventListener('click', function (e) {
        e.stopPropagation();
        var id = row.getAttribute('data-user-id') || '';
        selectEl.value = id;
        try {
          selectEl.dispatchEvent(new Event('change', { bubbles: true }));
        } catch (err) {
          var ev = document.createEvent('Event');
          ev.initEvent('change', true, true);
          selectEl.dispatchEvent(ev);
        }
        updateTrigger(trigger, selectEl);
        closePopover();
      });
    });

    document._thRespDocClose = function (e) {
      if (!activePop) return;
      if (e.target === pop || pop.contains(e.target)) return;
      if (e.target === trigger || trigger.contains(e.target)) return;
      closePopover();
    };
    document._thRespKeyClose = function (e) {
      if (e.key === 'Escape') closePopover();
    };
    setTimeout(function () {
      document.addEventListener('click', document._thRespDocClose, true);
      document.addEventListener('keydown', document._thRespKeyClose, true);
    }, 0);
  }

  function attach(selectEl, getDataFn, getObraIdFn, opts) {
    if (!selectEl || !getDataFn) return;
    opts = opts || {};
    var zIndex = opts.zIndex != null ? opts.zIndex : Z_FORM;

    var getOutrosFn = opts.getOutrosFn || null;
    var getObraNomeFn = opts.getObraNomeFn || null;

    if (selectEl.dataset.thRespPickerAttached === '1') {
      selectEl._thRespGetData = getDataFn;
      selectEl._thRespGetObraId = getObraIdFn;
      selectEl._thRespGetOutros = getOutrosFn;
      selectEl._thRespGetObraNome = getObraNomeFn;
      if (selectEl._thRespRefresh) selectEl._thRespRefresh();
      return;
    }

    selectEl.dataset.thRespPickerAttached = '1';
    selectEl._thRespGetData = getDataFn;
    selectEl._thRespGetObraId = getObraIdFn;
    selectEl._thRespGetOutros = getOutrosFn;
    selectEl._thRespGetObraNome = getObraNomeFn;

    var wrap = document.createElement('div');
    wrap.className = 'th-resp-picker-wrap';
    var parent = selectEl.parentNode;
    if (!parent) return;
    parent.insertBefore(wrap, selectEl);
    wrap.appendChild(selectEl);

    selectEl.classList.add('th-resp-picker-select');
    selectEl.setAttribute('aria-hidden', 'true');
    selectEl.tabIndex = -1;

    var trigger = document.createElement('button');
    trigger.type = 'button';
    trigger.className = 'th-resp-picker-trigger';
    trigger.innerHTML =
      '<span class="th-resp-picker-avatar" style="display:none" aria-hidden="true"></span>' +
      '<span class="th-resp-picker-label">Selecione…</span>' +
      '<span class="th-resp-picker-chev" aria-hidden="true">▾</span>';

    wrap.appendChild(trigger);

    selectEl._thRespRefresh = function () {
      var d = selectEl._thRespGetData ? selectEl._thRespGetData() : [];
      var oid = selectEl._thRespGetObraId ? selectEl._thRespGetObraId() : '';
      var outros = selectEl._thRespGetOutros ? selectEl._thRespGetOutros() : null;
      var obraNomeFallback = selectEl._thRespGetObraNome ? selectEl._thRespGetObraNome() : '';
      syncSelectOptions(selectEl, d, oid, outros, obraNomeFallback);
      updateTrigger(trigger, selectEl);
    };

    trigger.addEventListener('click', function (e) {
      e.preventDefault();
      e.stopPropagation();
      if (activePop && activePop._thTrigger === trigger) {
        closePopover();
        return;
      }
      closePopover();
      openPopover(
        trigger,
        selectEl,
        function () {
          return selectEl._thRespGetData ? selectEl._thRespGetData() : [];
        },
        selectEl._thRespGetObraId,
        selectEl._thRespGetOutros,
        zIndex
      );
    });

    selectEl.addEventListener('change', function () {
      updateTrigger(trigger, selectEl);
    });

    selectEl._thRespRefresh();
  }

  function attachModalNovaEtapa(selectEl) {
    if (!selectEl) return;
    attach(
      selectEl,
      function () {
        var obraUsers = global.thUsuarios || [];
        var outros = global.thUsuariosOutros || [];
        return [
          {
            obra_nome: obraSectionLabel(global.thDetalheObraNome || 'Obra'),
            pessoas: obraUsers,
          },
          {
            obra_nome: '2 - Outros',
            pessoas: dedupeOutros(obraUsers, outros),
          },
        ];
      },
      function () {
        return '__single__';
      },
      { zIndex: Z_MODAL }
    );
  }

  global.ThRespPicker = {
    syncSelectOptions: syncSelectOptions,
    attach: attach,
    attachModalNovaEtapa: attachModalNovaEtapa,
    close: closePopover,
  };
})(window);
