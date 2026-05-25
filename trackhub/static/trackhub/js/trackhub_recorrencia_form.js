/**
 * Campo "Repetir" — usa id_recorrencia_regra + id_recorrencia_parametros_json (JSON).
 * Parâmetros: { dias_semana: [0,4], dias_mes: [1,15], datas_ano: [{m:5,d:14}, ...] }
 */
(function () {
  'use strict';

  var IDS = { regra: 'id_recorrencia_regra', params: 'id_recorrencia_parametros_json' };
  var DOW_SHORT = ['Seg', 'Ter', 'Qua', 'Qui', 'Sex', 'Sáb', 'Dom'];
  var DOW_LONG = [
    'Segunda-feira',
    'Terça-feira',
    'Quarta-feira',
    'Quinta-feira',
    'Sexta-feira',
    'Sábado',
    'Domingo',
  ];
  var MESES_PT = [
    'Janeiro',
    'Fevereiro',
    'Março',
    'Abril',
    'Maio',
    'Junho',
    'Julho',
    'Agosto',
    'Setembro',
    'Outubro',
    'Novembro',
    'Dezembro',
  ];
  var MESES_CURTO = ['', 'jan', 'fev', 'mar', 'abr', 'mai', 'jun', 'jul', 'ago', 'set', 'out', 'nov', 'dez'];
  var REGRAS_DIAS_MES = ['monthly', 'bimonthly', 'quarterly', 'semiannual'];
  var INTERVALO_MESES_LABEL = {
    monthly: 1,
    bimonthly: 2,
    quarterly: 3,
    semiannual: 6,
  };

  function isRegraDiasMes(rule) {
    return REGRAS_DIAS_MES.indexOf(rule) >= 0;
  }

  function labelDiasMesSecao(rule) {
    var n = INTERVALO_MESES_LABEL[rule] || 1;
    if (n === 1) return 'Dias do mês';
    return 'A cada ' + n + ' meses — dias do mês';
  }

  function $(id) {
    return document.getElementById(id);
  }

  function elRegra() {
    return $(IDS.regra);
  }

  function elParams() {
    return $(IDS.params);
  }

  function getRegra() {
    var el = elRegra();
    return el ? (el.value || '').trim() : 'none';
  }

  function setRegra(v) {
    var el = elRegra();
    if (el) el.value = v || 'none';
  }

  function getParametros() {
    var raw = (elParams() && elParams().value) || '{}';
    try {
      var o = JSON.parse(raw);
      return typeof o === 'object' && o && !Array.isArray(o) ? o : {};
    } catch (e) {
      return {};
    }
  }

  function setParametros(obj) {
    var el = elParams();
    if (el) el.value = JSON.stringify(obj || {});
  }

  function jsParaPythonWeekday(dt) {
    return (dt.getDay() + 6) % 7;
  }

  function readPrazoDate() {
    var root = $('th-rec-root');
    var form = root && root.closest('form');
    var prazoInp = form
      ? form.querySelector('input[name="prazo"]')
      : document.querySelector('input[name="prazo"]');
    if (!prazoInp || !prazoInp.value) return null;
    var p = prazoInp.value.split('-');
    if (p.length !== 3) return null;
    var y = parseInt(p[0], 10);
    var m = parseInt(p[1], 10);
    var d = parseInt(p[2], 10);
    if (isNaN(y) || isNaN(m) || isNaN(d)) return null;
    return new Date(y, m - 1, d);
  }

  function syncFromPrazoSubset(regra) {
    var dt = readPrazoDate();
    if (!dt) return null;
    var py = jsParaPythonWeekday(dt);
    var d = dt.getDate();
    var m = dt.getMonth() + 1;
    if (regra === 'weekly') return { dias_semana: [py] };
    if (isRegraDiasMes(regra)) return { dias_mes: [d] };
    if (regra === 'yearly') return { datas_ano: [{ m: m, d: d }] };
    return {};
  }

  /** Quando não há prazo preenchido: semanal/anual/mensal alinham ao calendário de hoje (dia da semana / dia do mês / data). */
  function defaultParamsWhenNoPrazo(rule) {
    var now = new Date();
    var py = jsParaPythonWeekday(now);
    if (rule === 'weekly') return { dias_semana: [py] };
    if (isRegraDiasMes(rule)) return { dias_mes: [now.getDate()] };
    if (rule === 'yearly') return { datas_ano: [{ m: now.getMonth() + 1, d: now.getDate() }] };
    return {};
  }

  function labelForState() {
    var rule = getRegra() || 'none';
    var pm = getParametros();
    if (rule === 'none' || !rule) return 'Não se repete';
    if (rule === 'daily') return 'Diariamente';
    if (rule === 'weekdays') return 'Dias da semana (segunda a sexta)';
    if (rule === 'weekly') {
      var ds = Array.isArray(pm.dias_semana) ? pm.dias_semana.map(Number).filter(function (x) { return !isNaN(x); }) : [];
      if (!ds.length) return 'Semanal';
      if (ds.length === 1) return 'Semanal — ' + DOW_LONG[ds[0]];
      return 'Semanal — ' + ds.map(function (i) { return DOW_SHORT[i]; }).join(', ');
    }
    if (rule === 'monthly') {
      var dm = Array.isArray(pm.dias_mes) ? pm.dias_mes.map(Number).filter(function (x) { return !isNaN(x); }) : [];
      if (!dm.length) return 'Mensal';
      dm.sort(function (a, b) { return a - b; });
      if (dm.length === 1) return 'Todo mês no dia ' + dm[0];
      return 'Todo mês nos dias ' + dm.join(', ');
    }
    if (rule === 'bimonthly') {
      var dmB = Array.isArray(pm.dias_mes) ? pm.dias_mes.map(Number).filter(function (x) { return !isNaN(x); }) : [];
      if (!dmB.length) return 'Bimestral';
      dmB.sort(function (a, b) { return a - b; });
      if (dmB.length === 1) return 'Bimestral — dia ' + dmB[0];
      return 'Bimestral — dias ' + dmB.join(', ');
    }
    if (rule === 'quarterly') {
      var dmQ = Array.isArray(pm.dias_mes) ? pm.dias_mes.map(Number).filter(function (x) { return !isNaN(x); }) : [];
      if (!dmQ.length) return 'Trimestral';
      dmQ.sort(function (a, b) { return a - b; });
      if (dmQ.length === 1) return 'Trimestral — dia ' + dmQ[0];
      return 'Trimestral — dias ' + dmQ.join(', ');
    }
    if (rule === 'semiannual') {
      var dmS = Array.isArray(pm.dias_mes) ? pm.dias_mes.map(Number).filter(function (x) { return !isNaN(x); }) : [];
      if (!dmS.length) return 'Semestral';
      dmS.sort(function (a, b) { return a - b; });
      if (dmS.length === 1) return 'Semestral — dia ' + dmS[0];
      return 'Semestral — dias ' + dmS.join(', ');
    }
    if (rule === 'yearly') {
      var da = Array.isArray(pm.datas_ano) ? pm.datas_ano : [];
      if (!da.length) return 'Anual';
      var partes = da.map(function (it) {
        var mm = parseInt(it.m, 10);
        var dd = parseInt(it.d, 10);
        return dd + '/' + (MESES_CURTO[mm] || mm);
      });
      if (partes.length === 1) {
        var it0 = da[0];
        return 'Todo ano em ' + it0.d + ' de ' + (MESES_PT[parseInt(it0.m, 10) - 1] || it0.m);
      }
      return 'Todo ano em ' + partes.join(', ');
    }
    return 'Não se repete';
  }

  function updateTriggerText() {
    var t = $('th-rec-trigger-text');
    if (!t) return;
    var root = $('th-rec-root');
    if (root && root.getAttribute('data-rec-draft') === '1') return;
    t.textContent = labelForState();
  }

  function setDraftMode(on) {
    var root = $('th-rec-root');
    var t = $('th-rec-trigger-text');
    if (!root || !t) return;
    if (on) {
      root.setAttribute('data-rec-draft', '1');
      t.textContent = 'Personalizar — clique em Aplicar para confirmar';
    } else {
      root.removeAttribute('data-rec-draft');
      updateTriggerText();
    }
  }

  function hideCustom() {
    var c = $('th-rec-custom');
    if (c) c.hidden = true;
  }

  function closeMenu() {
    var m = $('th-rec-menu');
    var tr = $('th-rec-trigger');
    if (m) m.hidden = true;
    if (tr) tr.setAttribute('aria-expanded', 'false');
  }

  function openMenu() {
    var m = $('th-rec-menu');
    var tr = $('th-rec-trigger');
    if (m) m.hidden = false;
    if (tr) tr.setAttribute('aria-expanded', 'true');
  }

  function buildWeekdayChips(container) {
    if (!container || container.children.length) return;
    for (var i = 0; i < 7; i++) {
      var b = document.createElement('button');
      b.type = 'button';
      b.className = 'th-rec-chip';
      b.setAttribute('data-wd', String(i));
      b.setAttribute('aria-pressed', 'false');
      b.textContent = DOW_SHORT[i];
      b.addEventListener('click', function (ev) {
        ev.preventDefault();
        this.classList.toggle('is-on');
        this.setAttribute('aria-pressed', this.classList.contains('is-on') ? 'true' : 'false');
      });
      container.appendChild(b);
    }
  }

  function buildMonthChips(container) {
    if (!container || container.children.length) return;
    for (var d = 1; d <= 31; d++) {
      var b = document.createElement('button');
      b.type = 'button';
      b.className = 'th-rec-chip th-rec-chip-sm';
      b.setAttribute('data-dom', String(d));
      b.setAttribute('aria-pressed', 'false');
      b.textContent = String(d);
      b.addEventListener('click', function (ev) {
        ev.preventDefault();
        this.classList.toggle('is-on');
        this.setAttribute('aria-pressed', this.classList.contains('is-on') ? 'true' : 'false');
      });
      container.appendChild(b);
    }
  }

  function syncWeekChipsFromPm(pm) {
    var row = $('th-rec-chips-wd');
    if (!row) return;
    var sel = Array.isArray(pm.dias_semana) ? pm.dias_semana.map(String) : [];
    row.querySelectorAll('.th-rec-chip').forEach(function (btn) {
      var on = sel.indexOf(btn.getAttribute('data-wd')) >= 0;
      btn.classList.toggle('is-on', on);
      btn.setAttribute('aria-pressed', on ? 'true' : 'false');
    });
  }

  function syncDomChipsFromPm(pm) {
    var row = $('th-rec-chips-dom');
    if (!row) return;
    var sel = Array.isArray(pm.dias_mes) ? pm.dias_mes.map(String) : [];
    row.querySelectorAll('.th-rec-chip').forEach(function (btn) {
      var on = sel.indexOf(btn.getAttribute('data-dom')) >= 0;
      btn.classList.toggle('is-on', on);
      btn.setAttribute('aria-pressed', on ? 'true' : 'false');
    });
  }

  function createAnoRow(mInit, dInit) {
    var wrap = document.createElement('div');
    wrap.className = 'th-rec-ano-row';
    var sel = document.createElement('select');
    sel.className = 'th-filter-select th-rec-ano-m';
    for (var mi = 1; mi <= 12; mi++) {
      var o = document.createElement('option');
      o.value = String(mi);
      o.textContent = MESES_PT[mi - 1];
      if (mi === (mInit || 1)) o.selected = true;
      sel.appendChild(o);
    }
    var inp = document.createElement('input');
    inp.type = 'number';
    inp.className = 'th-filter-select th-rec-ano-d';
    inp.min = 1;
    inp.max = 31;
    inp.value = String(dInit != null ? dInit : 1);
    var rm = document.createElement('button');
    rm.type = 'button';
    rm.className = 'th-rec-ano-remove';
    rm.setAttribute('aria-label', 'Remover data');
    rm.textContent = '\u00d7';
    rm.addEventListener('click', function (ev) {
      ev.preventDefault();
      ev.stopPropagation();
      var rows = document.querySelectorAll('#th-rec-ano-rows .th-rec-ano-row');
      if (rows.length <= 1) return;
      wrap.remove();
    });
    wrap.appendChild(inp);
    wrap.appendChild(sel);
    wrap.appendChild(rm);
    return wrap;
  }

  function ensureAnoRowsFromPm(pm) {
    var host = $('th-rec-ano-rows');
    if (!host) return;
    host.innerHTML = '';
    var da = Array.isArray(pm.datas_ano) && pm.datas_ano.length ? pm.datas_ano : [{ m: 1, d: 1 }];
    da.forEach(function (it) {
      host.appendChild(createAnoRow(parseInt(it.m, 10) || 1, parseInt(it.d, 10) || 1));
    });
  }

  function collectWeekDays() {
    var row = $('th-rec-chips-wd');
    if (!row) return [];
    var out = [];
    row.querySelectorAll('.th-rec-chip.is-on').forEach(function (btn) {
      out.push(parseInt(btn.getAttribute('data-wd'), 10));
    });
    return out.sort(function (a, b) { return a - b; });
  }

  function collectDomDays() {
    var row = $('th-rec-chips-dom');
    if (!row) return [];
    var out = [];
    row.querySelectorAll('.th-rec-chip.is-on').forEach(function (btn) {
      out.push(parseInt(btn.getAttribute('data-dom'), 10));
    });
    return out.sort(function (a, b) { return a - b; });
  }

  function collectAnoDatas() {
    var out = [];
    document.querySelectorAll('#th-rec-ano-rows .th-rec-ano-row').forEach(function (row) {
      var sel = row.querySelector('select.th-rec-ano-m');
      var inp = row.querySelector('input.th-rec-ano-d');
      if (!sel || !inp) return;
      var m = parseInt(sel.value, 10);
      var d = parseInt(inp.value, 10) || 1;
      out.push({ m: Math.max(1, Math.min(12, m)), d: Math.max(1, Math.min(31, d)) });
    });
    return out;
  }

  function refreshModeSections() {
    var mode = $('th-rec-custom-mode');
    var m = mode ? mode.value : 'weekly';
    var sw = $('th-rec-sec-weekly');
    var sm = $('th-rec-sec-monthly');
    var sy = $('th-rec-sec-yearly');
    var smLabel = $('th-rec-sec-monthly-label');
    if (sw) sw.hidden = m !== 'weekly';
    if (sm) sm.hidden = !isRegraDiasMes(m);
    if (sy) sy.hidden = m !== 'yearly';
    if (smLabel && isRegraDiasMes(m)) smLabel.textContent = labelDiasMesSecao(m);
  }

  function syncDomChipsForMode(mode) {
    var pm = getParametros();
    if (!Array.isArray(pm.dias_mes) || !pm.dias_mes.length) {
      pm = syncFromPrazoSubset(mode) || defaultParamsWhenNoPrazo(mode);
    }
    syncDomChipsFromPm(pm);
  }

  function applyMenuRule(rule) {
    hideCustom();
    setRegra(rule);
    var pm = {};
    if (rule === 'weekly') {
      pm = syncFromPrazoSubset('weekly') || defaultParamsWhenNoPrazo('weekly');
    } else if (isRegraDiasMes(rule)) {
      pm = syncFromPrazoSubset(rule) || defaultParamsWhenNoPrazo(rule);
    } else if (rule === 'yearly') {
      pm = syncFromPrazoSubset('yearly') || defaultParamsWhenNoPrazo('yearly');
    } else {
      pm = {};
    }
    setParametros(pm);
    setDraftMode(false);
    updateTriggerText();
    closeMenu();
  }

  function init() {
    var root = $('th-rec-root');
    if (!root || !elRegra() || !elParams()) return;
    if (root.getAttribute('data-th-rec-init') === '1') return;
    root.setAttribute('data-th-rec-init', '1');

    var trigger = $('th-rec-trigger');
    var menu = $('th-rec-menu');
    var custom = $('th-rec-custom');
    var modeEl = $('th-rec-custom-mode');

    buildWeekdayChips($('th-rec-chips-wd'));
    buildMonthChips($('th-rec-chips-dom'));

    syncWeekChipsFromPm(getParametros());
    syncDomChipsFromPm(getParametros());
    updateTriggerText();

    if (trigger) {
      trigger.addEventListener('click', function (e) {
        e.preventDefault();
        e.stopPropagation();
        if (!menu) return;
        if (menu.hidden) openMenu();
        else closeMenu();
      });
    }

    if (menu) {
      menu.addEventListener('click', function (e) {
        var btn = e.target.closest('.th-recorrencia-opt');
        if (!btn) return;
        e.preventDefault();
        e.stopPropagation();

        if (btn.getAttribute('data-action') === 'custom') {
          closeMenu();
          if (modeEl) {
            var r = getRegra();
            if (r === 'weekly' || r === 'yearly' || isRegraDiasMes(r)) {
              modeEl.value = r;
            } else {
              modeEl.value = 'weekly';
            }
          }
          refreshModeSections();
          var pm0 = getParametros();
          if (modeEl && modeEl.value === 'weekly') syncWeekChipsFromPm(pm0);
          if (modeEl && isRegraDiasMes(modeEl.value)) syncDomChipsForMode(modeEl.value);
          if (modeEl && modeEl.value === 'yearly') ensureAnoRowsFromPm(pm0);
          if (custom) custom.hidden = false;
          setDraftMode(true);
          return;
        }

        var rule = btn.getAttribute('data-rule');
        if (!rule) return;
        applyMenuRule(rule);
      });
    }

    document.addEventListener('click', function (ev) {
      if (root.contains(ev.target)) return;
      closeMenu();
      hideCustom();
      setDraftMode(false);
    });

    if (modeEl) {
      modeEl.addEventListener('change', function () {
        refreshModeSections();
        var m = modeEl.value;
        if (m === 'yearly' && $('th-rec-ano-rows') && !$('th-rec-ano-rows').children.length) {
          ensureAnoRowsFromPm({ datas_ano: [{ m: 1, d: 1 }] });
        }
        if (isRegraDiasMes(m)) syncDomChipsForMode(m);
      });
    }

    var btnAddAno = $('th-rec-ano-add');
    if (btnAddAno) {
      btnAddAno.addEventListener('click', function (e) {
        e.preventDefault();
        e.stopPropagation();
        var host = $('th-rec-ano-rows');
        if (host) host.appendChild(createAnoRow(1, 1));
      });
    }

    var btnCancel = $('th-rec-custom-cancel');
    if (btnCancel) {
      btnCancel.addEventListener('click', function (e) {
        e.preventDefault();
        e.stopPropagation();
        hideCustom();
        setDraftMode(false);
      });
    }

    var btnApply = $('th-rec-custom-apply');
    if (btnApply) {
      btnApply.addEventListener('click', function (e) {
        e.preventDefault();
        e.stopPropagation();
        var mode = modeEl ? modeEl.value : 'weekly';
        var pm = {};
        if (mode === 'weekly') {
          setRegra('weekly');
          pm.dias_semana = collectWeekDays();
          if (!pm.dias_semana.length) return;
        } else if (isRegraDiasMes(mode)) {
          setRegra(mode);
          pm.dias_mes = collectDomDays();
          if (!pm.dias_mes.length) return;
        } else {
          setRegra('yearly');
          pm.datas_ano = collectAnoDatas();
          if (!pm.datas_ano.length) return;
        }
        setParametros(pm);
        hideCustom();
        setDraftMode(false);
      });
    }

    /* Não sincronizar prazo → parâmetros de recorrência ao mudar a data:
     * o prazo (entrega) é independente do dia da repetição (ex.: toda quinta, prazo na segunda). */
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
