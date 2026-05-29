/**
 * Editor de configuração de fluxo (alçadas + participantes) — estado em memória e renderização.
 * Ficheiro em core/static para o mesmo pipeline de estáticos que o resto do site (evita 404 em deploy).
 */
(function () {
  'use strict';

  var SK_USER = 'user';
  var SK_GROUP = 'django_group';
  var MODE_INTERNAL_USER = 'internal_user';
  var MODE_GROUP = 'group';
  var MODE_EXTERNAL_USER = 'external_user';
  var MODE_EXTERNAL_VARIABLE = 'external_variable';

  function slugify(txt) {
    return (txt || '')
      .toString()
      .trim()
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, '_')
      .replace(/^_+|_+$/g, '');
  }

  function variableDefaults(si, pi, p) {
    var keyBase = slugify(p.variable_key || '');
    if (!keyBase) keyBase = 'terceirizado_alcada_' + (si + 1) + '_' + (pi + 1);
    return {
      variable_key: keyBase,
      variable_label: (p.variable_label || '').trim() || 'Terceirizado responsável',
      required_on_create: true,
      variable_subject_kind: SK_USER,
    };
  }

  function parseJsonScript(id) {
    var node = document.getElementById(id);
    if (!node || !node.textContent) {
      return null;
    }
    try {
      return JSON.parse(node.textContent);
    } catch (e) {
      console.error('wf-flow-editor: JSON inválido em #' + id, e);
      return null;
    }
  }

  function cloneState(obj) {
    return JSON.parse(JSON.stringify(obj));
  }

  function showErr(msg) {
    var el = document.getElementById('wf-flow-editor-err');
    if (el) {
      el.textContent = msg;
      el.hidden = false;
      el.setAttribute('aria-live', 'assertive');
      try {
        el.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
      } catch (e) {}
    } else {
      window.alert(msg);
    }
  }

  function hideErr() {
    var el = document.getElementById('wf-flow-editor-err');
    if (el) {
      el.textContent = '';
      el.hidden = true;
    }
  }

  function validate(state) {
    var internalIds = (state.__internal_user_ids || {});
    var externalIds = (state.__external_user_ids || {});
    var groupIds = (state.__group_ids || {});

    if (!state.steps || state.steps.length === 0) {
      return 'Defina pelo menos uma alçada.';
    }
    for (var i = 0; i < state.steps.length; i++) {
      var st = state.steps[i];
      var name = (st.name || '').trim();
      if (!name) {
        return 'Informe o nome da alçada ' + (i + 1) + '.';
      }
      var parts = st.participants || [];
      if (parts.length === 0) {
        return 'A alçada «' + name + '» precisa de pelo menos um aprovador.';
      }
      for (var j = 0; j < parts.length; j++) {
        var p = parts[j];
        var mode = (p.participant_mode || '').trim() || MODE_INTERNAL_USER;

        if (mode === MODE_EXTERNAL_VARIABLE) {
          continue;
        }
        if (mode === MODE_GROUP) {
          var gid = Number(p.group_id || 0);
          if (!gid || !groupIds[gid]) {
            return 'Na alçada «' + name + '», selecione um grupo válido em cada linha do tipo Grupo.';
          }
          continue;
        }

        var uid = Number(p.user_id || 0);
        if (!uid) {
          if (mode === MODE_EXTERNAL_USER) {
            return 'Na alçada «' + name + '», selecione o terceirizado cadastrado em cada linha do tipo Terceirizado externo.';
          }
          return 'Na alçada «' + name + '», selecione o usuário interno em cada linha do tipo Usuário interno.';
        }
        if (mode === MODE_EXTERNAL_USER && !externalIds[uid]) {
          return 'Na alçada «' + name + '», o usuário selecionado não pertence à lista de terceirizados aprovados.';
        }
        if (mode === MODE_INTERNAL_USER && !internalIds[uid]) {
          return 'Na alçada «' + name + '», o usuário selecionado não pertence à lista de aprovadores internos.';
        }
      }
    }
    return null;
  }

  function buildPayload(state) {
    return {
      is_active: !!state.is_active,
      steps: state.steps.map(function (st, si) {
        return {
          id: st.id == null ? null : st.id,
          name: (st.name || '').trim(),
          is_active: !!st.is_active,
          participants: (st.participants || []).map(function (p, pi) {
            var mode = (p.participant_mode || '').trim() || MODE_INTERNAL_USER;
            var varMeta = variableDefaults(si, pi, p);
            if (mode === MODE_EXTERNAL_VARIABLE) {
              return {
                subject_kind: SK_USER,
                user_id: null,
                group_id: null,
                is_variable: true,
                variable_key: varMeta.variable_key,
                variable_label: varMeta.variable_label,
                required_on_create: true,
                variable_subject_kind: SK_USER,
              };
            }
            if (mode === MODE_GROUP) {
              return {
                subject_kind: SK_GROUP,
                user_id: null,
                group_id: Number(p.group_id || 0) || null,
                is_variable: false,
                variable_key: '',
                variable_label: '',
                required_on_create: false,
                variable_subject_kind: SK_GROUP,
              };
            }
            return {
              subject_kind: SK_USER,
              user_id: Number(p.user_id || 0) || null,
              group_id: null,
              is_variable: false,
              variable_key: '',
              variable_label: '',
              required_on_create: false,
              variable_subject_kind: SK_USER,
            };
          }),
        };
      }),
    };
  }

  function init() {
    var root = document.getElementById('wf-flow-editor-root');
    var form = document.getElementById('wf-flow-form');
    var payloadField = document.getElementById('wf-config-payload');
    if (!root || !form || !payloadField) {
      return;
    }

    hideErr();

    var locked = root.getAttribute('data-locked') === 'true';
    var externalSignupUrl = (root.getAttribute('data-external-signup-url') || '').trim();
    var externalSignupListUrl = (root.getAttribute('data-external-signup-list-url') || '').trim();
    var flowProjectId = Number(root.getAttribute('data-flow-project-id') || 0) || null;
    var flowProjectCode = (root.getAttribute('data-flow-project-code') || '').trim();
    var flowProjectName = (root.getAttribute('data-flow-project-name') || '').trim();
    var flowCategoryName = (root.getAttribute('data-flow-category-name') || '').trim();
    var initial = parseJsonScript('wf-flow-initial');
    var users = parseJsonScript('wf-flow-users') || [];
    var groups = parseJsonScript('wf-flow-groups') || [];

    if (!initial) {
      root.innerHTML =
        '<p class="wf-help" style="color:#b91c1c;">Não foi possível carregar os dados do fluxo. Recarregue a página.</p>';
      showErr('Não foi possível carregar os dados do fluxo. Recarregue a página.');
      return;
    }

    var state = cloneState(initial);
    var allUsers = Array.isArray(users) ? users.slice() : [];
    var internalUsers = allUsers.filter(function (u) { return (u.scope || '') === 'internal'; });
    var externalUsers = allUsers.filter(function (u) { return (u.scope || '') === 'external'; });
    var internalUserIds = {};
    var externalUserIds = {};
    var userById = {};
    var groupById = {};
    var groupIds = {};

    allUsers.forEach(function (u) {
      var id = Number(u.id || 0);
      if (!id) return;
      userById[id] = u;
    });
    internalUsers.forEach(function (u) {
      var id = Number(u.id || 0);
      if (!id) return;
      internalUserIds[id] = true;
    });
    externalUsers.forEach(function (u) {
      var id = Number(u.id || 0);
      if (!id) return;
      externalUserIds[id] = true;
    });
    (Array.isArray(groups) ? groups : []).forEach(function (g) {
      var id = Number(g.id || 0);
      if (!id) return;
      groupById[id] = g;
      groupIds[id] = true;
    });

    state.__internal_user_ids = internalUserIds;
    state.__external_user_ids = externalUserIds;
    state.__group_ids = groupIds;

    function inferMode(part) {
      if (part && part.is_variable && part.subject_kind === SK_USER) return MODE_EXTERNAL_VARIABLE;
      if (part && part.subject_kind === SK_GROUP) return MODE_GROUP;
      var uid = Number((part && part.user_id) || 0);
      if (uid && externalUserIds[uid]) return MODE_EXTERNAL_USER;
      return MODE_INTERNAL_USER;
    }

    function csrfToken() {
      var tokenField = form.querySelector('input[name="csrfmiddlewaretoken"]');
      return tokenField ? (tokenField.value || '').trim() : '';
    }

    function requestExternalPreSignup(data) {
      if (!externalSignupUrl) {
        return Promise.reject(new Error('URL de pré-cadastro externo não configurada.'));
      }
      return fetch(externalSignupUrl, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': csrfToken(),
          'X-Requested-With': 'XMLHttpRequest',
        },
        body: JSON.stringify(data || {}),
      }).then(function (resp) {
        return resp
          .json()
          .catch(function () { return {}; })
          .then(function (payload) {
            if (!resp.ok || !payload.ok) {
              throw new Error(payload.message || 'Falha ao enviar solicitação de pré-cadastro.');
            }
            return payload;
          });
      });
    }

    function formatBrazilPhone(value) {
      var digits = String(value || '').replace(/\D/g, '');
      if (digits.indexOf('55') === 0) digits = digits.slice(2);
      digits = digits.slice(0, 11);
      var ddd = digits.slice(0, 2);
      var rest = digits.slice(2);
      var out = '+55';
      if (ddd.length > 0) out += ' (' + ddd;
      if (ddd.length === 2) out += ')';
      if (rest.length > 0) {
        out += ' ';
        var block1Len = rest.length > 8 ? 5 : 4;
        var b1 = rest.slice(0, block1Len);
        var b2 = rest.slice(block1Len, block1Len + 4);
        out += b1;
        if (b2) out += '-' + b2;
      }
      return out;
    }

    function formatCnpjMasked(value) {
      var raw = String(value || '').toUpperCase().replace(/[^A-Z0-9]/g, '').slice(0, 14);
      var p1 = raw.slice(0, 2);
      var p2 = raw.slice(2, 5);
      var p3 = raw.slice(5, 8);
      var p4 = raw.slice(8, 12);
      var p5 = raw.slice(12, 14);
      var out = p1;
      if (p2) out += '.' + p2;
      if (p3) out += '.' + p3;
      if (p4) out += '/' + p4;
      if (p5) out += '-' + p5;
      return out;
    }

    function defaultParticipant() {
      return {
        subject_kind: SK_USER,
        user_id: null,
        group_id: null,
        is_variable: false,
        participant_mode: MODE_INTERNAL_USER,
        variable_key: '',
        variable_label: '',
        required_on_create: false,
        variable_subject_kind: SK_USER,
      };
    }

    function defaultStep() {
      return {
        id: null,
        name: 'Nova alçada',
        is_active: true,
        participants: [defaultParticipant()],
      };
    }

    function render() {
      hideErr();
      root.innerHTML = '';

      var wrap = document.createElement('div');
      wrap.className = 'wf-flow-editor';

      if (locked) {
        var lock = document.createElement('div');
        lock.className = 'wf-flow-lock';
        lock.setAttribute('role', 'status');
        lock.innerHTML =
          '<i class="fas fa-lock" aria-hidden="true"></i> ' +
          '<span><strong>Fluxo em uso.</strong> Não é possível adicionar, remover ou reordenar alçadas. ' +
          'Pode alterar nomes, situação ativa e participantes.</span>';
        wrap.appendChild(lock);
      }

      var flowRow = document.createElement('div');
      flowRow.className = 'wf-flow-flowbar';
      var flowToggle = document.createElement('label');
      flowToggle.className = 'wf-flow-toggle';
      var cb = document.createElement('input');
      cb.type = 'checkbox';
      cb.checked = !!state.is_active;
      cb.addEventListener('change', function () {
        state.is_active = cb.checked;
      });
      var span = document.createElement('span');
      span.textContent = 'Fluxo ativo (aceita novos processos conforme regras do sistema)';
      flowToggle.appendChild(cb);
      flowToggle.appendChild(span);
      flowRow.appendChild(flowToggle);
      wrap.appendChild(flowRow);

      var stepsWrap = document.createElement('div');
      stepsWrap.className = 'wf-flow-steps';

      state.steps.forEach(function (step, si) {
        var card = document.createElement('section');
        card.className = 'wf-flow-card';
        card.setAttribute('data-step-index', String(si));

        var head = document.createElement('header');
        head.className = 'wf-flow-card__head';

        var badge = document.createElement('span');
        badge.className = 'wf-flow-card__badge';
        badge.textContent = 'Alçada ' + (si + 1);

        var tools = document.createElement('div');
        tools.className = 'wf-flow-card__tools';

        if (!locked) {
          var btnUp = document.createElement('button');
          btnUp.type = 'button';
          btnUp.className = 'wf-flow-icon-btn';
          btnUp.title = 'Mover para cima';
          btnUp.innerHTML = '<i class="fas fa-arrow-up" aria-hidden="true"></i>';
          btnUp.disabled = si === 0;
          btnUp.addEventListener('click', function () {
            if (si === 0) return;
            var t = state.steps[si - 1];
            state.steps[si - 1] = state.steps[si];
            state.steps[si] = t;
            render();
          });

          var btnDown = document.createElement('button');
          btnDown.type = 'button';
          btnDown.className = 'wf-flow-icon-btn';
          btnDown.title = 'Mover para baixo';
          btnDown.innerHTML = '<i class="fas fa-arrow-down" aria-hidden="true"></i>';
          btnDown.disabled = si === state.steps.length - 1;
          btnDown.addEventListener('click', function () {
            if (si >= state.steps.length - 1) return;
            var t = state.steps[si + 1];
            state.steps[si + 1] = state.steps[si];
            state.steps[si] = t;
            render();
          });

          var btnRm = document.createElement('button');
          btnRm.type = 'button';
          btnRm.className = 'wf-flow-icon-btn wf-flow-icon-btn--danger';
          btnRm.title = 'Remover alçada';
          btnRm.innerHTML = '<i class="fas fa-trash-alt" aria-hidden="true"></i>';
          btnRm.disabled = state.steps.length <= 1;
          btnRm.addEventListener('click', function () {
            if (state.steps.length <= 1) return;
            state.steps.splice(si, 1);
            render();
          });

          tools.appendChild(btnUp);
          tools.appendChild(btnDown);
          tools.appendChild(btnRm);
        }

        head.appendChild(badge);
        head.appendChild(tools);
        card.appendChild(head);

        var body = document.createElement('div');
        body.className = 'wf-flow-card__body';

        var grid = document.createElement('div');
        grid.className = 'wf-flow-fields';

        var fName = document.createElement('div');
        fName.className = 'wf-field';
        var ln = document.createElement('label');
        ln.setAttribute('for', 'wf-step-name-' + si);
        ln.textContent = 'Nome da alçada';
        var inp = document.createElement('input');
        inp.id = 'wf-step-name-' + si;
        inp.type = 'text';
        inp.className = 'wf-input';
        inp.value = step.name || '';
        inp.maxLength = 200;
        inp.addEventListener('input', function () {
          state.steps[si].name = inp.value;
        });
        fName.appendChild(ln);
        fName.appendChild(inp);

        var fAct = document.createElement('div');
        fAct.className = 'wf-field';
        var labAct = document.createElement('label');
        labAct.className = 'wf-flow-toggle';
        var cbAct = document.createElement('input');
        cbAct.type = 'checkbox';
        cbAct.checked = !!step.is_active;
        cbAct.addEventListener('change', function () {
          state.steps[si].is_active = cbAct.checked;
        });
        var spAct = document.createElement('span');
        spAct.textContent = 'Alçada ativa';
        labAct.appendChild(cbAct);
        labAct.appendChild(spAct);
        fAct.appendChild(labAct);

        grid.appendChild(fName);
        grid.appendChild(fAct);
        body.appendChild(grid);

        var pHead = document.createElement('div');
        pHead.className = 'wf-flow-part-head';
        var pTitle = document.createElement('h3');
        pTitle.className = 'wf-flow-part-title';
        pTitle.textContent = 'Aprovadores nesta alçada';
        pHead.appendChild(pTitle);
        body.appendChild(pHead);

        var pList = document.createElement('div');
        pList.className = 'wf-flow-part-list';

        (step.participants || []).forEach(function (part, pi) {
          if (!part.participant_mode) part.participant_mode = inferMode(part);
          var mode = part.participant_mode;
          if (mode === MODE_EXTERNAL_VARIABLE) {
            part.subject_kind = SK_USER;
            part.user_id = null;
            part.group_id = null;
            part.is_variable = true;
          } else if (mode === MODE_GROUP) {
            part.subject_kind = SK_GROUP;
            part.user_id = null;
            part.is_variable = false;
          } else if (mode === MODE_EXTERNAL_USER) {
            part.subject_kind = SK_USER;
            part.group_id = null;
            part.is_variable = false;
            if (part.user_id && !externalUserIds[Number(part.user_id || 0)]) part.user_id = null;
          } else {
            part.subject_kind = SK_USER;
            part.group_id = null;
            part.is_variable = false;
            if (part.user_id && !internalUserIds[Number(part.user_id || 0)]) part.user_id = null;
          }

          var row = document.createElement('div');
          row.className = 'wf-flow-part-row';
          row.setAttribute('data-participant-index', String(pi));

          var kindWrap = document.createElement('div');
          kindWrap.className = 'wf-flow-part-field wf-flow-part-field--kind';
          var modeLbl = document.createElement('label');
          modeLbl.className = 'wf-flow-part-mode-label';
          modeLbl.textContent = 'Tipo nesta alçada';
          kindWrap.appendChild(modeLbl);

          var selWrap = document.createElement('div');
          selWrap.className = 'wf-flow-part-field wf-flow-part-field--approver';
          var approverLbl = document.createElement('label');
          approverLbl.className = 'wf-flow-part-mode-label';
          approverLbl.textContent = mode === MODE_GROUP ? 'Grupo aprovador' : 'Participante';
          selWrap.appendChild(approverLbl);

          function buildUserCombobox(opts) {
            var chooser = document.createElement('div');
            chooser.className = 'wf-user-combobox';

            var trigger = document.createElement('button');
            trigger.type = 'button';
            trigger.className = 'wf-user-combobox__trigger';
            trigger.setAttribute('aria-haspopup', 'listbox');
            trigger.setAttribute('aria-expanded', 'false');
            trigger.innerHTML =
              '<span class="wf-user-combobox__value"></span>' +
              '<i class="fas fa-chevron-down wf-user-combobox__icon" aria-hidden="true"></i>';

            var valueEl = trigger.querySelector('.wf-user-combobox__value');
            var panel = document.createElement('div');
            panel.className = 'wf-user-combobox__panel';
            panel.hidden = true;

            var userSearch = document.createElement('input');
            userSearch.type = 'search';
            userSearch.className = 'wf-user-combobox__search';
            userSearch.placeholder = opts.searchPlaceholder || 'Pesquisar usuário...';
            userSearch.autocomplete = 'off';

            var list = document.createElement('ul');
            list.className = 'wf-user-combobox__list';
            list.setAttribute('role', 'listbox');
            list.setAttribute('aria-label', opts.listAriaLabel || 'Opções disponíveis');

            panel.appendChild(userSearch);
            panel.appendChild(list);
            chooser.appendChild(trigger);
            chooser.appendChild(panel);
            selWrap.appendChild(chooser);

            var detachOutside = null;
            var detachEsc = null;

            function selectedUserLabel() {
              var id = Number(state.steps[si].participants[pi].user_id || 0);
              if (!id) return opts.placeholder || 'Selecionar';
              var hit = userById[id];
              return hit ? hit.label : (opts.placeholder || 'Selecionar');
            }

            function syncTriggerValue() {
              valueEl.textContent = selectedUserLabel();
            }

            function closePanel() {
              panel.hidden = true;
              chooser.classList.remove('is-open');
              row.classList.remove('is-open');
              card.classList.remove('has-open-combobox');
              trigger.setAttribute('aria-expanded', 'false');
              userSearch.value = '';
              if (detachOutside) { detachOutside(); detachOutside = null; }
              if (detachEsc) { detachEsc(); detachEsc = null; }
            }

            function renderList(query) {
              var q = (query || '').trim().toLowerCase();
              var selectedId = Number(state.steps[si].participants[pi].user_id || 0);
              var filtered = opts.items.filter(function (u) {
                var hay = ((u.label || '') + ' ' + (u.secondary || '') + ' ' + (u.badge || '')).toLowerCase();
                return !q || hay.indexOf(q) >= 0;
              });
              list.innerHTML = '';
              if (!filtered.length) {
                var empty = document.createElement('li');
                empty.className = 'wf-user-combobox__empty';
                empty.textContent = 'Nenhum usuário encontrado';
                list.appendChild(empty);
                return;
              }
              filtered.forEach(function (u) {
                var li = document.createElement('li');
                li.className = 'wf-user-combobox__item';
                if (Number(u.id) === selectedId) li.classList.add('is-selected');
                var top = document.createElement('span');
                top.className = 'wf-user-combobox__item-name';
                top.textContent = u.label || '';
                li.appendChild(top);
                var meta = document.createElement('span');
                meta.className = 'wf-user-combobox__item-meta';
                meta.textContent = [u.secondary || '', u.badge || ''].filter(Boolean).join(' · ');
                li.appendChild(meta);
                li.addEventListener('click', function () {
                  state.steps[si].participants[pi].subject_kind = SK_USER;
                  state.steps[si].participants[pi].user_id = Number(u.id);
                  state.steps[si].participants[pi].group_id = null;
                  syncTriggerValue();
                  closePanel();
                });
                list.appendChild(li);
              });
            }

            function openPanel() {
              panel.hidden = false;
              chooser.classList.add('is-open');
              row.classList.add('is-open');
              card.classList.add('has-open-combobox');
              trigger.setAttribute('aria-expanded', 'true');
              renderList('');
              window.setTimeout(function () { userSearch.focus(); }, 0);

              var onOutside = function (evt) {
                if (!chooser.contains(evt.target)) closePanel();
              };
              document.addEventListener('mousedown', onOutside);
              detachOutside = function () { document.removeEventListener('mousedown', onOutside); };

              var onEsc = function (evt) {
                if (evt.key === 'Escape') closePanel();
              };
              document.addEventListener('keydown', onEsc);
              detachEsc = function () { document.removeEventListener('keydown', onEsc); };
            }

            trigger.addEventListener('click', function () {
              if (panel.hidden) openPanel();
              else closePanel();
            });
            userSearch.addEventListener('input', function () {
              renderList(userSearch.value || '');
            });

            syncTriggerValue();
            return chooser;
          }

          if (mode === MODE_INTERNAL_USER) {
            selWrap.appendChild(
              buildUserCombobox({
                items: internalUsers,
                placeholder: 'Selecionar usuário interno',
                searchPlaceholder: 'Pesquisar usuário...',
                listAriaLabel: 'Usuários internos disponíveis',
              })
            );
          } else if (mode === MODE_EXTERNAL_USER) {
            selWrap.appendChild(
              buildUserCombobox({
                items: externalUsers,
                placeholder: 'Selecionar terceirizado cadastrado',
                searchPlaceholder: 'Pesquisar terceirizado...',
                listAriaLabel: 'Terceirizados disponíveis',
              })
            );
            var helperActions = document.createElement('div');
            helperActions.className = 'wf-flow-part-inline-actions';
            var requestNewBtn = document.createElement('button');
            requestNewBtn.type = 'button';
            requestNewBtn.className = 'wf-flow-link-btn';
            requestNewBtn.textContent = 'Solicitar novo terceirizado';
            var requestPanel = document.createElement('div');
            requestPanel.className = 'wf-flow-external-request';
            requestPanel.hidden = true;

            var requestTitle = document.createElement('p');
            requestTitle.className = 'wf-flow-external-request__title';
            requestTitle.textContent = 'Pré-cadastro de novo terceirizado';
            requestPanel.appendChild(requestTitle);

            var requestGrid = document.createElement('div');
            requestGrid.className = 'wf-flow-external-request__grid';

            function field(label, type) {
              var w = document.createElement('label');
              w.className = 'wf-flow-external-request__field';
              var s = document.createElement('span');
              s.textContent = label;
              var i = document.createElement('input');
              i.type = type || 'text';
              i.className = 'wf-input';
              w.appendChild(s);
              w.appendChild(i);
              requestGrid.appendChild(w);
              return i;
            }

            var fullNameInput = field('Nome *', 'text');
            var companyInput = field('Empresa', 'text');
            var emailInput = field('E-mail *', 'email');
            var phoneInput = field('Telefone/WhatsApp', 'text');
            var cnpjInput = field('CNPJ (opcional)', 'text');
            var noteInput = field('Observação (opcional)', 'text');
            phoneInput.placeholder = '+55 (11) 99999-9999';
            cnpjInput.placeholder = '00.000.000/0000-00';
            phoneInput.addEventListener('focus', function () {
              if (!(phoneInput.value || '').trim()) phoneInput.value = '+55 ';
            });
            phoneInput.addEventListener('input', function () {
              phoneInput.value = formatBrazilPhone(phoneInput.value || '');
            });
            cnpjInput.addEventListener('input', function () {
              cnpjInput.value = formatCnpjMasked(cnpjInput.value || '');
            });
            requestPanel.appendChild(requestGrid);

            var requestMsg = document.createElement('p');
            requestMsg.className = 'wf-flow-external-request__msg';
            requestMsg.hidden = true;
            requestPanel.appendChild(requestMsg);

            var requestActions = document.createElement('div');
            requestActions.className = 'wf-flow-external-request__actions';
            var submitRequestBtn = document.createElement('button');
            submitRequestBtn.type = 'button';
            submitRequestBtn.className = 'wf-btn-table';
            submitRequestBtn.textContent = 'Enviar solicitação';
            var markVariableBtn = document.createElement('button');
            markVariableBtn.type = 'button';
            markVariableBtn.className = 'wf-btn-table wf-btn-table--ghost';
            markVariableBtn.textContent = 'Marcar como a definir no pedido';
            requestActions.appendChild(submitRequestBtn);
            requestActions.appendChild(markVariableBtn);
            requestPanel.appendChild(requestActions);

            function showRequestMsg(text, isError) {
              requestMsg.hidden = false;
              requestMsg.textContent = text || '';
              requestMsg.classList.toggle('is-error', !!isError);
              requestMsg.classList.toggle('is-success', !isError);
            }

            submitRequestBtn.addEventListener('click', function () {
              var fullName = (fullNameInput.value || '').trim();
              var email = (emailInput.value || '').trim().toLowerCase();
              if (!fullName) {
                showRequestMsg('Informe o nome do terceirizado.', true);
                return;
              }
              if (!email) {
                showRequestMsg('Informe o e-mail do terceirizado.', true);
                return;
              }
              submitRequestBtn.disabled = true;
              submitRequestBtn.textContent = 'Enviando...';
              requestExternalPreSignup({
                full_name: fullName,
                company_name: (companyInput.value || '').trim(),
                email: email,
                phone_whatsapp: (phoneInput.value || '').trim(),
                cnpj: (cnpjInput.value || '').trim(),
                note: (noteInput.value || '').trim(),
                flow_context: (step.name || ('Alçada ' + (si + 1))) + ' · participante ' + (pi + 1),
                project_id: flowProjectId,
                project_code: flowProjectCode,
                project_name: flowProjectName,
                category_name: flowCategoryName,
              })
                .then(function (resp) {
                  var item = state.steps[si].participants[pi];
                  item.participant_mode = MODE_EXTERNAL_VARIABLE;
                  item.subject_kind = SK_USER;
                  item.user_id = null;
                  item.group_id = null;
                  item.is_variable = true;
                  var meta = variableDefaults(si, pi, item);
                  item.variable_key = meta.variable_key;
                  item.variable_label = meta.variable_label;
                  item.required_on_create = true;
                  item.variable_subject_kind = SK_USER;
                  item.external_prefill_request = {
                    request_id: resp.request_id || null,
                    full_name: fullName,
                    email: email,
                    already_pending: !!resp.already_pending,
                    message: resp.message || '',
                    project_code: flowProjectCode,
                    project_name: flowProjectName,
                  };
                  render();
                })
                .catch(function (err) {
                  showRequestMsg((err && err.message) || 'Falha ao enviar solicitação.', true);
                  submitRequestBtn.disabled = false;
                  submitRequestBtn.textContent = 'Enviar solicitação';
                });
            });

            markVariableBtn.addEventListener('click', function () {
              var item = state.steps[si].participants[pi];
              item.participant_mode = MODE_EXTERNAL_VARIABLE;
              item.subject_kind = SK_USER;
              item.user_id = null;
              item.group_id = null;
              item.is_variable = true;
              var meta = variableDefaults(si, pi, item);
              item.variable_key = meta.variable_key;
              item.variable_label = meta.variable_label;
              item.required_on_create = true;
              item.variable_subject_kind = SK_USER;
              render();
            });

            requestNewBtn.addEventListener('click', function () {
              requestPanel.hidden = !requestPanel.hidden;
              if (!requestPanel.hidden) fullNameInput.focus();
            });
            helperActions.appendChild(requestNewBtn);
            helperActions.appendChild(requestPanel);
            selWrap.appendChild(helperActions);
          } else if (mode === MODE_GROUP) {
            var groupSel = document.createElement('select');
            groupSel.className = 'wf-select';
            var groupPlaceholder = document.createElement('option');
            groupPlaceholder.value = '';
            groupPlaceholder.textContent = 'Selecionar grupo';
            groupSel.appendChild(groupPlaceholder);
            (Array.isArray(groups) ? groups : []).forEach(function (g) {
              var opt = document.createElement('option');
              opt.value = String(g.id);
              opt.textContent = g.label || ('Grupo #' + g.id);
              groupSel.appendChild(opt);
            });
            groupSel.value = String(part.group_id || '');
            groupSel.addEventListener('change', function () {
              var item = state.steps[si].participants[pi];
              item.group_id = groupSel.value ? Number(groupSel.value) : null;
            });
            selWrap.appendChild(groupSel);
          } else {
            var variableMsg = document.createElement('p');
            variableMsg.className = 'wf-help';
            variableMsg.textContent =
              'Este participante será informado no momento da criação do pedido de assinatura.';
            selWrap.appendChild(variableMsg);

            var prefillInfo = state.steps[si].participants[pi].external_prefill_request;
            if (prefillInfo && (prefillInfo.email || prefillInfo.request_id)) {
              var sentBox = document.createElement('div');
              sentBox.className = 'wf-flow-external-sent';
              var sentTitle = document.createElement('p');
              sentTitle.className = 'wf-flow-external-sent__title';
              sentTitle.textContent = prefillInfo.already_pending
                ? 'Solicitação já estava pendente'
                : 'Solicitação de cadastro enviada';
              sentBox.appendChild(sentTitle);

              var sentDesc = document.createElement('p');
              sentDesc.className = 'wf-flow-external-sent__desc';
              var parts = [];
              if (prefillInfo.request_id) parts.push('ID #' + prefillInfo.request_id);
              if (prefillInfo.full_name) parts.push(prefillInfo.full_name);
              if (prefillInfo.email) parts.push(prefillInfo.email);
              sentDesc.textContent = parts.join(' · ');
              sentBox.appendChild(sentDesc);

              if (prefillInfo.project_code || prefillInfo.project_name) {
                var sentProject = document.createElement('p');
                sentProject.className = 'wf-flow-external-sent__desc';
                sentProject.textContent =
                  'Obra pré-marcada: ' +
                  [prefillInfo.project_code || '', prefillInfo.project_name || ''].filter(Boolean).join(' - ');
                sentBox.appendChild(sentProject);
              }

              if (externalSignupListUrl) {
                var sentLink = document.createElement('a');
                sentLink.className = 'wf-flow-external-sent__link';
                sentLink.href = externalSignupListUrl;
                sentLink.textContent = 'Abrir fila de solicitações externas';
                sentBox.appendChild(sentLink);
              }
              selWrap.appendChild(sentBox);
            }

            var backToFixed = document.createElement('button');
            backToFixed.type = 'button';
            backToFixed.className = 'wf-flow-link-btn';
            backToFixed.textContent = 'Selecionar terceirizado cadastrado';
            backToFixed.addEventListener('click', function () {
              var item = state.steps[si].participants[pi];
              item.participant_mode = MODE_EXTERNAL_USER;
              item.subject_kind = SK_USER;
              item.is_variable = false;
              item.user_id = null;
              item.group_id = null;
              render();
            });
            selWrap.appendChild(backToFixed);
          }

          var modeSel = document.createElement('select');
          modeSel.className = 'wf-select';
          var modeInternal = document.createElement('option');
          modeInternal.value = MODE_INTERNAL_USER;
          modeInternal.textContent = 'Usuário interno';
          var modeGroup = document.createElement('option');
          modeGroup.value = MODE_GROUP;
          modeGroup.textContent = 'Grupo';
          var modeExternalFixed = document.createElement('option');
          modeExternalFixed.value = MODE_EXTERNAL_USER;
          modeExternalFixed.textContent = 'Terceirizado externo';
          var modeExternalVariable = document.createElement('option');
          modeExternalVariable.value = MODE_EXTERNAL_VARIABLE;
          modeExternalVariable.textContent = 'Terceirizado a definir no pedido';
          modeSel.appendChild(modeInternal);
          modeSel.appendChild(modeGroup);
          modeSel.appendChild(modeExternalFixed);
          modeSel.appendChild(modeExternalVariable);
          modeSel.value = mode;
          modeSel.addEventListener('change', function () {
            var item = state.steps[si].participants[pi];
            item.participant_mode = modeSel.value;
            if (item.participant_mode === MODE_EXTERNAL_VARIABLE) {
              item.subject_kind = SK_USER;
              item.user_id = null;
              item.group_id = null;
              item.is_variable = true;
              var meta = variableDefaults(si, pi, item);
              item.variable_key = meta.variable_key;
              item.variable_label = meta.variable_label;
              item.required_on_create = true;
              item.variable_subject_kind = SK_USER;
            } else if (item.participant_mode === MODE_GROUP) {
              item.subject_kind = SK_GROUP;
              item.user_id = null;
              item.is_variable = false;
              item.variable_key = '';
              item.variable_label = '';
              item.required_on_create = false;
              item.variable_subject_kind = SK_GROUP;
            } else if (item.participant_mode === MODE_EXTERNAL_USER) {
              item.subject_kind = SK_USER;
              item.group_id = null;
              item.is_variable = false;
              item.user_id = null;
              item.variable_key = '';
              item.variable_label = '';
              item.required_on_create = false;
              item.variable_subject_kind = SK_USER;
            } else {
              item.subject_kind = SK_USER;
              item.group_id = null;
              item.is_variable = false;
              item.user_id = null;
              item.variable_key = '';
              item.variable_label = '';
              item.required_on_create = false;
              item.variable_subject_kind = SK_USER;
            }
            render();
          });
          kindWrap.appendChild(modeSel);

          if (mode === MODE_EXTERNAL_VARIABLE) {
            var metaInfo = document.createElement('p');
            metaInfo.className = 'wf-help';
            metaInfo.textContent =
              'Quem cria o pedido deverá escolher um terceirizado existente ou solicitar novo cadastro para aprovação.';
            kindWrap.appendChild(metaInfo);
          }

          var rm = document.createElement('button');
          rm.type = 'button';
          rm.className = 'wf-flow-remove-btn';
          rm.title = 'Remover aprovador';
          rm.innerHTML = '<i class="fas fa-times" aria-hidden="true"></i><span>Remover</span>';
          rm.addEventListener('click', function () {
            if (state.steps[si].participants.length <= 1) return;
            state.steps[si].participants.splice(pi, 1);
            render();
          });

          var actionWrap = document.createElement('div');
          actionWrap.className = 'wf-flow-part-field wf-flow-part-field--remove';
          actionWrap.appendChild(rm);

          row.appendChild(kindWrap);
          row.appendChild(selWrap);
          row.appendChild(actionWrap);
          pList.appendChild(row);
        });

        body.appendChild(pList);

        var addP = document.createElement('button');
        addP.type = 'button';
        addP.className = 'wf-flow-add-line';
        addP.innerHTML = '<i class="fas fa-plus" aria-hidden="true"></i> Adicionar aprovador';
        addP.addEventListener('click', function () {
          state.steps[si].participants.push(defaultParticipant());
          render();
        });
        body.appendChild(addP);

        card.appendChild(body);
        stepsWrap.appendChild(card);
      });

      wrap.appendChild(stepsWrap);

      if (!locked) {
        var addStep = document.createElement('button');
        addStep.type = 'button';
        addStep.className = 'wf-flow-add-step';
        addStep.innerHTML = '<i class="fas fa-layer-group" aria-hidden="true"></i> Adicionar alçada';
        addStep.addEventListener('click', function () {
          state.steps.push(defaultStep());
          render();
        });
        wrap.appendChild(addStep);
      }

      root.appendChild(wrap);
    }

    render();

    form.addEventListener('submit', function (e) {
      var err = validate(state);
      if (err) {
        e.preventDefault();
        showErr(err);
        return;
      }
      hideErr();
      payloadField.value = JSON.stringify(buildPayload(state));
    });
  }

  /* Executado após os <script type="application/json"> do fluxo — DOM acima deste ficheiro já existe. */
  init();
})();

