/**
 * BI da Obra — gráficos (Chart.js) e tema local (somente BI).
 */
(function () {
  var THEME_KEY = "lplan_ao_bi_theme";

  function getBiMain() {
    return document.querySelector("main.main-content--bi-obra");
  }

  function isDarkTheme() {
    var root = document.getElementById("ao-page-root");
    var main = getBiMain();
    return !!(
      (root && root.classList.contains("analise-obra-page--dark")) ||
      (main && main.classList.contains("bi-page-dark"))
    );
  }

  function applyThemeContainers(dark) {
    var root = document.getElementById("ao-page-root");
    var main = getBiMain();
    var body = document.body;
    if (root) {
      root.classList.toggle("analise-obra-page--dark", !!dark);
    }
    if (main) {
      main.classList.toggle("bi-page-dark", !!dark);
    }
    if (body) {
      body.classList.toggle("bi-page-dark", !!dark);
    }
  }

  function chartPalette() {
    if (isDarkTheme()) {
      return {
        grid: "rgba(148, 163, 184, 0.12)",
        text: "#94a3b8",
        line1: "#38bdf8",
        line2: "#a78bfa",
        bar: "#f59e0b",
      };
    }
    return {
      grid: "rgba(15, 23, 42, 0.08)",
      text: "#64748b",
      line1: "#0284c7",
      line2: "#7c3aed",
      bar: "#d97706",
    };
  }

  function readPayload() {
    var el = document.getElementById("analise-payload");
    if (!el || !el.textContent) return null;
    try {
      return JSON.parse(el.textContent);
    } catch (e) {
      return null;
    }
  }

  function destroyCharts() {
    var ids = [
      "chart-ocorrencias-dia",
      "chart-blocos-controle",
      "chart-suprimentos-locais",
      "chart-tags-diario",
    ];
    ids.forEach(function (id) {
      var canvas = document.getElementById(id);
      if (canvas && typeof Chart !== "undefined" && Chart.getChart) {
        var ch = Chart.getChart(canvas);
        if (ch) ch.destroy();
      }
    });
  }

  function renderOcorrenciasPorDia(payload) {
    var canvas = document.getElementById("chart-ocorrencias-dia");
    if (!canvas || typeof Chart === "undefined") return;
    var series = (((payload || {}).diario || {}).ocorrencias_por_dia) || [];
    var labels = series.map(function (r) {
      return r.data;
    });
    var data = series.map(function (r) {
      return r.total;
    });
    var maxValue = data.length ? Math.max.apply(null, data) : 0;
    var yMax = Math.max(2, maxValue + 1);
    var pal = chartPalette();
    var fillRgb = isDarkTheme() ? "56, 189, 248" : "2, 132, 199";
    new Chart(canvas, {
      type: "line",
      data: {
        labels: labels,
        datasets: [
          {
            label: "Ocorrências (Diário)",
            data: data,
            borderColor: pal.line1,
            backgroundColor: "rgba(" + fillRgb + ", 0.1)",
            fill: true,
            tension: 0.25,
            pointRadius: 3,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { labels: { color: pal.text } },
        },
        scales: {
          x: {
            ticks: { color: pal.text, maxRotation: 45 },
            grid: { color: pal.grid },
          },
          y: {
            beginAtZero: true,
            suggestedMax: yMax,
            ticks: {
              color: pal.text,
              stepSize: 1,
              precision: 0,
              callback: function (value) {
                return Number.isInteger(value) ? value : "";
              },
            },
            grid: { color: pal.grid },
          },
        },
      },
    });
  }

  function renderBlocosCriticos(payload) {
    var canvas = document.getElementById("chart-blocos-controle");
    if (!canvas || typeof Chart === "undefined") return;
    var rows = (((payload || {}).controle || {}).blocos_mais_atrasados) || [];
    var labels = rows.map(function (r) {
      return r.bloco || "-";
    });
    var data = rows.map(function (r) {
      return r.percentual_medio;
    });
    var pal = chartPalette();
    var bg = isDarkTheme() ? "rgba(34, 197, 94, 0.35)" : "rgba(22, 163, 74, 0.35)";
    var border = isDarkTheme() ? "#22c55e" : "#16a34a";
    new Chart(canvas, {
      type: "bar",
      data: {
        labels: labels,
        datasets: [
          {
            label: "% médio (Controle)",
            data: data,
            backgroundColor: bg,
            borderColor: border,
            borderWidth: 1,
          },
        ],
      },
      options: {
        indexAxis: "y",
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { labels: { color: pal.text } },
        },
        scales: {
          x: {
            min: 0,
            max: 100,
            ticks: { color: pal.text },
            grid: { color: pal.grid },
          },
          y: {
            ticks: { color: pal.text },
            grid: { color: pal.grid },
          },
        },
      },
    });
  }

  function renderSuprimentosLocais(payload) {
    var canvas = document.getElementById("chart-suprimentos-locais");
    if (!canvas || typeof Chart === "undefined") return;
    var rank = (((payload || {}).suprimentos || {}).ranking || {}).locais || [];
    var top = rank.slice(0, 8);
    var labels = top.map(function (x) {
      return x[0];
    });
    var data = top.map(function (x) {
      return x[1];
    });
    var pal = chartPalette();
    var bg = isDarkTheme() ? "rgba(245, 158, 11, 0.4)" : "rgba(217, 119, 6, 0.45)";
    var border = isDarkTheme() ? "#f59e0b" : "#d97706";
    new Chart(canvas, {
      type: "bar",
      data: {
        labels: labels,
        datasets: [
          {
            label: "Pendências por local (Suprimentos)",
            data: data,
            backgroundColor: bg,
            borderColor: border,
            borderWidth: 1,
          },
        ],
      },
      options: {
        indexAxis: "y",
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { labels: { color: pal.text } },
        },
        scales: {
          x: {
            beginAtZero: true,
            ticks: { color: pal.text, precision: 0 },
            grid: { color: pal.grid },
          },
          y: {
            ticks: { color: pal.text },
            grid: { color: pal.grid },
          },
        },
      },
    });
  }

  function renderTags(payload) {
    var canvas = document.getElementById("chart-tags-diario");
    if (!canvas || typeof Chart === "undefined") return;
    var tags = (((payload || {}).diario || {}).tags_top) || [];
    if (!tags.length) return;
    var labels = tags.map(function (t) {
      return t.nome;
    });
    var data = tags.map(function (t) {
      return t.total;
    });
    var colors = tags.map(function (t) {
      return t.cor || "#64748b";
    });
    var pal = chartPalette();
    new Chart(canvas, {
      type: "doughnut",
      data: {
        labels: labels,
        datasets: [
          {
            data: data,
            backgroundColor: colors,
            borderWidth: 0,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: {
            position: "right",
            labels: { color: pal.text, boxWidth: 12 },
          },
        },
      },
    });
  }

  function renderAllCharts(payload) {
    if (!payload) return;
    renderOcorrenciasPorDia(payload);
    renderBlocosCriticos(payload);
    renderSuprimentosLocais(payload);
    renderTags(payload);
  }

  function syncThemeUi() {
    var btn = document.getElementById("aoThemeToggle");
    var label = document.getElementById("aoThemeLabel");
    var dark = isDarkTheme();
    if (btn) {
      btn.setAttribute("aria-pressed", dark ? "true" : "false");
    }
    if (label) {
      label.textContent = dark ? "Modo claro" : "Modo escuro";
    }
  }

  function setTheme(dark) {
    applyThemeContainers(dark);
    if (dark) {
      try {
        localStorage.setItem(THEME_KEY, "dark");
      } catch (e) {}
    } else {
      try {
        localStorage.setItem(THEME_KEY, "light");
      } catch (e) {}
    }
    syncThemeUi();
    destroyCharts();
    renderAllCharts(readPayload());
  }

  function escapeHtml(s) {
    if (s == null) return "";
    var d = document.createElement("div");
    d.textContent = s;
    return d.innerHTML;
  }

  function renderDrilldown(data) {
    var body = document.getElementById("aoDrilldownBody");
    if (!body || !data) return;
    var c = data.controle || {};
    var s = data.suprimentos || {};
    var rx = data.resumo_executivo || {};
    var rs = c.resumo_status || {};
    var lines = (c.linhas_preview || c.linhas || [])
      .map(function (row) {
        return (
          "<tr><td>" +
          escapeHtml(row.atividade) +
          "</td><td>" +
          escapeHtml(row.apto) +
          "</td><td>" +
          escapeHtml(row.status_texto) +
          "</td><td>" +
          escapeHtml(row.status_percentual) +
          "</td></tr>"
        );
      })
      .join("");
    var travadas = (c.atividades_criticas || [])
      .map(function (row) {
        return (
          "<tr><td>" +
          escapeHtml(row.atividade) +
          "</td><td>" +
          escapeHtml(row.apto) +
          "</td><td>" +
          escapeHtml(row.status_texto) +
          "</td><td>" +
          escapeHtml(row.percentual) +
          "%</td></tr>"
        );
      })
      .join("");
    var materiais = (s.materiais_criticos || [])
      .map(function (row) {
        return (
          "<li><strong>" +
          escapeHtml(row.local) +
          "</strong>: " +
          escapeHtml(row.pendencias) +
          " pend.</li>"
        );
      })
      .join("");
    var prioridade = (rx.prioridade || "media").toLowerCase();
    body.innerHTML =
      '<p class="small ao-drill-muted mb-2">Recorte · bloco ' +
      escapeHtml((data.chave || {}).bloco) +
      " · pav. " +
      escapeHtml((data.chave || {}).pavimento || "—") +
      "</p>" +
      '<div class="ao-drill-priority ao-priority-' +
      escapeHtml(prioridade) +
      '"><span>Prioridade: <strong>' +
      escapeHtml((rx.prioridade || "media").toUpperCase()) +
      "</strong></span><span>Score: <strong>" +
      escapeHtml(rx.score) +
      "</strong></span></div>" +
      '<p class="small mt-2 mb-2">' +
      escapeHtml(rx.acao || "") +
      "</p>" +
      '<div class="ao-drill-kpi-grid"><div class="ao-drill-kpi"><small>% médio local</small><strong>' +
      (c.percentual_medio_local != null ? c.percentual_medio_local + "%" : "—") +
      '</strong></div><div class="ao-drill-kpi"><small>Linhas totais</small><strong>' +
      (c.total_linhas || 0) +
      '</strong></div><div class="ao-drill-kpi"><small>Concluídas</small><strong>' +
      (rs.concluidos || 0) +
      '</strong></div><div class="ao-drill-kpi"><small>Em andamento</small><strong>' +
      (rs.em_andamento || 0) +
      '</strong></div><div class="ao-drill-kpi"><small>Não iniciadas</small><strong>' +
      (rs.nao_iniciados || 0) +
      '</strong></div><div class="ao-drill-kpi"><small>Sem dado</small><strong>' +
      (rs.sem_dado || 0) +
      "</strong></div></div>" +
      '<h6 class="mt-3 mb-2">Top 5 atividades travadas</h6>' +
      '<div class="ao-table-wrap my-2"><table class="ao-table"><thead><tr><th>Atividade</th><th>Apto</th><th>Status</th><th>%</th></tr></thead><tbody>' +
      (travadas || '<tr><td colspan="4" class="ao-empty">Sem atividades críticas</td></tr>') +
      "</tbody></table></div>" +
      '<h6 class="mt-3 mb-2">Materiais críticos do local</h6>' +
      '<ul class="ao-drill-list">' +
      (materiais || '<li class="ao-drill-muted">Sem pendências críticas no recorte.</li>') +
      "</ul>" +
      '<p class="small mt-3"><span class="ao-badge-origem controle">Controle</span> Prévia de linhas do local (12 primeiras)</p>' +
      '<div class="ao-table-wrap my-2"><table class="ao-table"><thead><tr><th>Atividade</th><th>Apto</th><th>Status</th><th>%</th></tr></thead><tbody>' +
      (lines || '<tr><td colspan="4" class="ao-empty">Sem linhas</td></tr>') +
      "</tbody></table></div>" +
      '<p class="small"><span class="ao-badge-origem suprimentos">Suprimentos</span> ' +
      escapeHtml(s.nota || "") +
      "</p>" +
      '<pre class="small ao-drill-muted" style="white-space:pre-wrap;max-height:120px;overflow:auto">' +
      escapeHtml(JSON.stringify(s.kpis || {}, null, 0)) +
      "</pre>";
  }

  function openDrilldown(bloco, pavimento) {
    var base = window.__ANALISE_DRILL_URL__;
    if (!base) return;
    var qp = new URLSearchParams(window.location.search);
    qp.set("bloco", bloco);
    qp.set("pavimento", pavimento || "");
    var url = base.replace(/\/?$/, "") + "?" + qp.toString();
    fetch(url, { credentials: "same-origin", headers: { Accept: "application/json" } })
      .then(function (r) {
        return r.json();
      })
      .then(function (j) {
        if (!j.success) throw new Error(j.error || "Falha");
        renderDrilldown(j.data);
        var el = document.getElementById("aoDrilldown");
        if (el && window.bootstrap && window.bootstrap.Offcanvas) {
          window.bootstrap.Offcanvas.getOrCreateInstance(el).show();
        }
      })
      .catch(function (err) {
        var body = document.getElementById("aoDrilldownBody");
        if (body) body.innerHTML = '<p class="text-danger">' + escapeHtml(err.message) + "</p>";
        var el = document.getElementById("aoDrilldown");
        if (el && window.bootstrap && window.bootstrap.Offcanvas) {
          window.bootstrap.Offcanvas.getOrCreateInstance(el).show();
        }
      });
  }

  function initOccurrencePriorityFilter() {
    var buttons = document.querySelectorAll("[data-priority-filter]");
    if (!buttons.length) return;
    var rows = document.querySelectorAll("#aoOcorrenciasCollapse tbody tr[data-priority]");
    buttons.forEach(function (btn) {
      btn.addEventListener("click", function () {
        var target = btn.getAttribute("data-priority-filter");
        buttons.forEach(function (b) {
          b.classList.remove("active");
        });
        btn.classList.add("active");
        rows.forEach(function (row) {
          var pr = row.getAttribute("data-priority");
          row.style.display = target === "all" || pr === target ? "" : "none";
        });
      });
    });
  }

  function initOccurrenceShowMore() {
    var btn = document.getElementById("aoOccShowMore");
    if (!btn) return;
    btn.addEventListener("click", function () {
      var rows = document.querySelectorAll(".ao-occ-extra");
      var expanded = btn.getAttribute("aria-expanded") === "true";
      rows.forEach(function (row) {
        row.classList.toggle("d-none", expanded);
      });
      btn.setAttribute("aria-expanded", expanded ? "false" : "true");
      btn.textContent = expanded ? "Ver mais ocorrências (" + rows.length + ")" : "Ver menos ocorrências";
    });
  }

  function initHeatmapShowMore() {
    var btn = document.getElementById("aoHeatmapShowMore");
    if (!btn) return;
    btn.addEventListener("click", function () {
      var rows = document.querySelectorAll(".ao-heat-extra-row");
      var expanded = btn.getAttribute("aria-expanded") === "true";
      rows.forEach(function (row) {
        row.classList.toggle("d-none", expanded);
      });
      btn.setAttribute("aria-expanded", expanded ? "false" : "true");
      btn.textContent = expanded ? "Ver mais" : "Ver menos";
    });
  }

  function initActionShowMore() {
    var btn = document.getElementById("aoActionShowMore");
    if (!btn) return;
    btn.addEventListener("click", function () {
      var rows = document.querySelectorAll(".ao-action-extra");
      var expanded = btn.getAttribute("aria-expanded") === "true";
      rows.forEach(function (row) {
        row.classList.toggle("d-none", expanded);
      });
      btn.setAttribute("aria-expanded", expanded ? "false" : "true");
      btn.textContent = expanded ? "Ver mais ações (" + rows.length + ")" : "Ver menos ações";
    });
  }

  function initOccurrenceCollapseButton() {
    var btn = document.querySelector('[data-bs-target="#aoOcorrenciasCollapse"]');
    var panel = document.getElementById("aoOcorrenciasCollapse");
    if (!btn || !panel) return;
    var total = btn.textContent.match(/\((\d+)\)/);
    var countText = total ? " (" + total[1] + ")" : "";
    function syncLabel() {
      var open = panel.classList.contains("show");
      btn.setAttribute("aria-expanded", open ? "true" : "false");
      btn.textContent = (open ? "Ocultar ocorrências" : "Mostrar ocorrências") + countText;
    }
    panel.addEventListener("shown.bs.collapse", syncLabel);
    panel.addEventListener("hidden.bs.collapse", syncLabel);
    syncLabel();
  }

  document.addEventListener("DOMContentLoaded", function () {
    syncThemeUi();

    var btnTheme = document.getElementById("aoThemeToggle");
    if (btnTheme) {
      btnTheme.addEventListener("click", function () {
        setTheme(!isDarkTheme());
      });
    }

    var payload = readPayload();
    if (payload) {
      renderAllCharts(payload);
    }

    initOccurrencePriorityFilter();
    initOccurrenceShowMore();
    initHeatmapShowMore();
    initActionShowMore();
    initOccurrenceCollapseButton();

    document.querySelectorAll(".ao-heat-row").forEach(function (row) {
      row.addEventListener("click", function (ev) {
        if (ev.target.closest(".ao-drill-btn")) return;
        var b = row.getAttribute("data-bloco");
        var p = row.getAttribute("data-pavimento");
        if (b) openDrilldown(b, p || "");
      });
    });
    document.querySelectorAll(".ao-drill-btn").forEach(function (btn) {
      btn.addEventListener("click", function (ev) {
        ev.stopPropagation();
        var row = btn.closest(".ao-heat-row");
        if (!row) return;
        openDrilldown(row.getAttribute("data-bloco"), row.getAttribute("data-pavimento") || "");
      });
    });

    var btnApi = document.getElementById("btnAnaliseRefreshApi");
    if (btnApi && window.__ANALISE_API_URL__) {
      btnApi.addEventListener("click", function () {
        var qp = new URLSearchParams(window.location.search);
        qp.set("secao", "all");
        var url = window.__ANALISE_API_URL__.replace(/\/?$/, "") + "?" + qp.toString();
        btnApi.disabled = true;
        fetch(url, { credentials: "same-origin", headers: { Accept: "application/json" } })
          .then(function (r) {
            return r.json();
          })
          .then(function (j) {
            if (!j.success) throw new Error(j.error || "Falha");
            window.location.reload();
          })
          .catch(function (err) {
            alert(err.message || "Erro ao atualizar");
            btnApi.disabled = false;
          });
      });
    }
  });
})();
