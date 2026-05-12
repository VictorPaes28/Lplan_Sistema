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

  function closePopover() {
    if (activePop) {
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

  function buildSections(data, obraId) {
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
      for (var i = 0; i < data.length; i += 1) {
        if (String(data[i].obra_id) === String(obraId)) {
          sections.push({
            label: data[i].obra_nome || 'Obra',
            pessoas: data[i].pessoas || [],
          });
          break;
        }
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

  function syncSelectOptions(selectEl, data, obraId) {
    if (!selectEl) return;
    var current = (selectEl.value || '').trim();
    selectEl.innerHTML = '';
    var placeholder = document.createElement('option');
    placeholder.value = '';
    placeholder.textContent = 'Selecione...';
    selectEl.appendChild(placeholder);

    var sections = buildSections(data, obraId);
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
    var hasCurrent = Array.from(selectEl.options).some(function (o) {
      return o.value === current;
    });
    if (hasCurrent) selectEl.value = current;
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

  function openPopover(trigger, selectEl, getDataFn, getObraIdFn, zIndex) {
    var data = getDataFn() || [];
    var obraId = getObraIdFn ? getObraIdFn() : '';
    var sections = buildSections(data, obraId);

    var parts = [];
    parts.push('<div class="imp-resp-popover-search">');
    parts.push('<i class="fas fa-search" aria-hidden="true"></i>');
    parts.push(
      '<input type="text" placeholder="Busque ou insira o e-mail..." class="imp-resp-search-input" autocomplete="off">'
    );
    parts.push('</div><div class="imp-resp-popover-body">');

    sections.forEach(function (sec) {
      if (!(sec.pessoas && sec.pessoas.length)) return;
      parts.push('<div class="th-resp-section">');
      parts.push('<div class="imp-resp-section-label">' + escapeHtml(sec.label) + '</div>');
      sec.pessoas.forEach(function (u) {
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
      parts.push('</div>');
    });

    parts.push('</div>');

    var pop = document.createElement('div');
    pop.className = 'imp-resp-popover th-resp-popover-trackhub';
    pop.innerHTML = parts.join('');
    pop.style.position = 'fixed';
    pop.style.zIndex = String(zIndex != null ? zIndex : Z_FORM);
    pop._thTrigger = trigger;

    var rect = trigger.getBoundingClientRect();
    var top = rect.bottom + 4;
    var left = rect.left;
    var vw = global.innerWidth || 800;
    var w = 280;
    if (left + w > vw - 8) left = Math.max(8, vw - w - 8);
    pop.style.top = top + 'px';
    pop.style.left = left + 'px';

    document.body.appendChild(pop);
    activePop = pop;

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
          sec.querySelectorAll('.imp-resp-user-row').forEach(function (row) {
            var nomeEl = row.querySelector('.imp-resp-user-nome');
            var t = nomeEl ? nomeEl.textContent.toLowerCase() : '';
            var show = !q || t.indexOf(q) !== -1;
            row.style.display = show ? '' : 'none';
            if (show) any = true;
          });
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

    if (selectEl.dataset.thRespPickerAttached === '1') {
      selectEl._thRespGetData = getDataFn;
      selectEl._thRespGetObraId = getObraIdFn;
      if (selectEl._thRespRefresh) selectEl._thRespRefresh();
      return;
    }

    selectEl.dataset.thRespPickerAttached = '1';
    selectEl._thRespGetData = getDataFn;
    selectEl._thRespGetObraId = getObraIdFn;

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
      syncSelectOptions(selectEl, d, oid);
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
        return [
          {
            obra_nome: global.thDetalheObraNome || 'Obra',
            pessoas: global.thUsuarios || [],
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
