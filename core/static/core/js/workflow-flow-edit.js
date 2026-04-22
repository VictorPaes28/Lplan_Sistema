/**
 * Editor de configuração de fluxo (alçadas + participantes) — estado em memória e renderização.
 * Ficheiro em core/static para o mesmo pipeline de estáticos que o resto do site (evita 404 em deploy).
 */
(function () {
  'use strict';

  var SK_USER = 'user';
  var SK_GROUP = 'django_group';

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
        if (p.subject_kind === SK_USER) {
          if (!p.user_id || p.user_id < 1) {
            return 'Na alçada «' + name + '», selecione o utilizador em cada linha.';
          }
        } else {
          if (!p.group_id || p.group_id < 1) {
            return 'Na alçada «' + name + '», selecione o grupo em cada linha.';
          }
        }
      }
    }
    return null;
  }

  function buildPayload(state) {
    return {
      is_active: !!state.is_active,
      steps: state.steps.map(function (st) {
        return {
          id: st.id == null ? null : st.id,
          name: (st.name || '').trim(),
          is_active: !!st.is_active,
          participants: (st.participants || []).map(function (p) {
            if (p.subject_kind === SK_USER) {
              return { subject_kind: SK_USER, user_id: p.user_id, group_id: null };
            }
            return { subject_kind: SK_GROUP, user_id: null, group_id: p.group_id };
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

    function defaultParticipant() {
      return { subject_kind: SK_USER, user_id: null, group_id: null };
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
          var row = document.createElement('div');
          row.className = 'wf-flow-part-row';

          var kindWrap = document.createElement('div');
          kindWrap.className = 'wf-flow-part-kind';
          var kindSel = document.createElement('select');
          kindSel.className = 'wf-select';
          kindSel.setAttribute('aria-label', 'Tipo de participante');
          var oU = document.createElement('option');
          oU.value = SK_USER;
          oU.textContent = 'Utilizador';
          var oG = document.createElement('option');
          oG.value = SK_GROUP;
          oG.textContent = 'Grupo Django';
          kindSel.appendChild(oU);
          kindSel.appendChild(oG);
          kindSel.value = part.subject_kind === SK_GROUP ? SK_GROUP : SK_USER;
          kindSel.addEventListener('change', function () {
            if (kindSel.value === SK_USER) {
              state.steps[si].participants[pi] = {
                subject_kind: SK_USER,
                user_id: null,
                group_id: null,
              };
            } else {
              state.steps[si].participants[pi] = {
                subject_kind: SK_GROUP,
                user_id: null,
                group_id: null,
              };
            }
            render();
          });

          kindWrap.appendChild(kindSel);

          var selWrap = document.createElement('div');
          selWrap.className = 'wf-flow-part-target';

          if (kindSel.value === SK_USER) {
            var us = document.createElement('select');
            us.className = 'wf-select';
            us.setAttribute('aria-label', 'Utilizador');
            var opt0 = document.createElement('option');
            opt0.value = '';
            opt0.textContent = 'Selecione…';
            us.appendChild(opt0);
            users.forEach(function (u) {
              var o = document.createElement('option');
              o.value = String(u.id);
              o.textContent = u.label;
              if (part.user_id === u.id) o.selected = true;
              us.appendChild(o);
            });
            us.addEventListener('change', function () {
              var v = parseInt(us.value, 10);
              state.steps[si].participants[pi].user_id = v > 0 ? v : null;
            });
            selWrap.appendChild(us);
          } else {
            var gs = document.createElement('select');
            gs.className = 'wf-select';
            gs.setAttribute('aria-label', 'Grupo');
            var g0 = document.createElement('option');
            g0.value = '';
            g0.textContent = 'Selecione…';
            gs.appendChild(g0);
            groups.forEach(function (g) {
              var o = document.createElement('option');
              o.value = String(g.id);
              o.textContent = g.label;
              if (part.group_id === g.id) o.selected = true;
              gs.appendChild(o);
            });
            gs.addEventListener('change', function () {
              var v = parseInt(gs.value, 10);
              state.steps[si].participants[pi].group_id = v > 0 ? v : null;
            });
            selWrap.appendChild(gs);
          }

          var rm = document.createElement('button');
          rm.type = 'button';
          rm.className = 'wf-flow-icon-btn wf-flow-icon-btn--danger';
          rm.title = 'Remover linha';
          rm.innerHTML = '<i class="fas fa-times" aria-hidden="true"></i>';
          rm.addEventListener('click', function () {
            if (state.steps[si].participants.length <= 1) return;
            state.steps[si].participants.splice(pi, 1);
            render();
          });

          row.appendChild(kindWrap);
          row.appendChild(selWrap);
          row.appendChild(rm);
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

