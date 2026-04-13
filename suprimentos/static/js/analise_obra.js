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

  /** JSON do BI pode trazer números como string; Chart.js não desenha barras com NaN. */
  function chartNum(v) {
    if (v == null || v === "") return 0;
    if (typeof v === "number") return isFinite(v) ? v : 0;
    var s = String(v).trim().replace(",", ".");
    var n = parseFloat(s, 10);
    return isFinite(n) ? n : 0;
  }

  /** % médio no payload do controle (snake_case ou camelCase). */
  function pctMedioControleRow(r) {
    if (!r || typeof r !== "object") return 0;
    var v = r.percentual_medio;
    if (v == null || v === "") v = r.percentualMedio;
    return chartNum(v);
  }

  function truncateLabel(str, maxLen) {
    var s = String(str || "");
    if (s.length <= maxLen) return s;
    return s.slice(0, Math.max(0, maxLen - 1)) + "…";
  }

  /**
   * Barras horizontais com valor 0 têm largura 0 px — parecem "vazias".
   * Desenha um traço à esquerda quando a largura da barra é ~0 e % ≤ 0,01.
   */
  function pluginBlocosZeroHint(fillStyle) {
    return {
      id: "aoBlocosZeroHint",
      afterDatasetsDraw: function (chart) {
        var ds0 = chart.data.datasets[0];
        if (!ds0 || !ds0.data || !ds0.data.length) return;
        var meta = chart.getDatasetMeta(0);
        if (!meta || !meta.data || !meta.data.length) return;
        var xScale = chart.scales.x;
        if (!xScale) return;
        var ctx = chart.ctx;
        ctx.save();
        var i;
        for (i = 0; i < meta.data.length; i++) {
          var val = chartNum(ds0.data[i]);
          if (val > 0.01) continue;
          var el = meta.data[i];
          if (!el) continue;
          var props = typeof el.getProps === "function" ? el.getProps(["x", "y", "base", "width", "height"], true) : el;
          var x = props.x != null ? props.x : el.x;
          var y = props.y != null ? props.y : el.y;
          var base = props.base != null ? props.base : el.base;
          var w = Math.abs((x || 0) - (base || 0));
          if (w > 3) continue;
          var barH = Math.abs(props.height != null ? props.height : el.height || 14);
          var h = Math.min(Math.max(barH * 0.75, 8), 20);
          var x0 = xScale.getPixelForValue(0);
          ctx.fillStyle = fillStyle;
          ctx.fillRect(x0, y - h / 2, 5, h);
        }
        ctx.restore();
      },
    };
  }

  function getObraIdNav() {
    var wid = window.__AO_OBRA_ID__;
    if (wid != null && wid !== "") return String(wid);
    var p = readPayload();
    if (p && p.meta && p.meta.obra_id != null) return String(p.meta.obra_id);
    return "";
  }

  function diaryDetailUrl(pk) {
    return "/diaries/" + encodeURIComponent(pk) + "/";
  }

  function mapaControleEixoUrl(setor, bloco) {
    var obra = getObraIdNav();
    if (!obra || bloco == null || String(bloco) === "") return null;
    var base = window.__AO_MAPA_CONTROLE_URL__;
    if (!base) return null;
    var sep = base.indexOf("?") >= 0 ? "&" : "?";
    var q = "obra=" + encodeURIComponent(obra) + "&bloco=" + encodeURIComponent(bloco);
    var s = setor != null ? String(setor).trim() : "";
    if (s) {
      q += "&setor=" + encodeURIComponent(s);
    }
    return base + sep + q;
  }

  function dashboardLocalUrl(localId) {
    var obra = getObraIdNav();
    if (!obra || !localId) return null;
    var base = window.__AO_DASHBOARD_SC_URL__;
    if (!base) return null;
    var sep = base.indexOf("?") >= 0 ? "&" : "?";
    return base + sep + "obra=" + encodeURIComponent(obra) + "&local=" + encodeURIComponent(localId);
  }

  function resolveLocalIdFromNome(payload, nome) {
    var locais = (((payload.filtros || {}).opcoes || {}).suprimentos || {}).locais || [];
    var n = (nome || "").trim().toLowerCase();
    var i;
    for (i = 0; i < locais.length; i++) {
      var L = locais[i];
      if (String(L.nome || "")
        .trim()
        .toLowerCase() === n) {
        return String(L.id);
      }
    }
    return null;
  }

  function applyTagFilterAnalise(tagId) {
    var qp = new URLSearchParams(window.location.search);
    qp.set("tag_ocorrencia_id", String(tagId));
    window.location.href = window.location.pathname + "?" + qp.toString();
  }

  function initBiNavigationClicks() {
    document.body.addEventListener("click", function (ev) {
      if (ev.target.closest("a[href]") || ev.target.closest("button") || ev.target.closest("summary")) {
        return;
      }
      var trD = ev.target.closest("tr.ao-bi-diary-row");
      if (trD && trD.getAttribute("data-diary-id")) {
        window.location.href = diaryDetailUrl(trD.getAttribute("data-diary-id"));
        return;
      }
      var trB = ev.target.closest("tr.ao-bi-bloco-row");
      if (trB) {
        var bloco = trB.getAttribute("data-bloco");
        if (bloco) {
          var st = trB.getAttribute("data-setor");
          var url = mapaControleEixoUrl(st, bloco);
          if (url) window.location.href = url;
        }
      }
    });
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

  var MESES_PT = [
    "janeiro",
    "fevereiro",
    "março",
    "abril",
    "maio",
    "junho",
    "julho",
    "agosto",
    "setembro",
    "outubro",
    "novembro",
    "dezembro",
  ];

  /** Parse YYYY-MM-DD como data local (sem deslocamento UTC). */
  function parseISODateLocal(iso) {
    if (!iso || typeof iso !== "string") return null;
    var p = iso.slice(0, 10).split("-");
    if (p.length !== 3) return null;
    var y = parseInt(p[0], 10);
    var m = parseInt(p[1], 10) - 1;
    var d = parseInt(p[2], 10);
    if (!y || m < 0 || m > 11 || d < 1 || d > 31) return null;
    return new Date(y, m, d);
  }

  /**
   * Eixo legível em pt-BR: se todo o recorte é um mês, mostra só o dia no eixo
   * e o mês/ano no subtítulo; senão dd/mm ou dd/mm/aa conforme o intervalo.
   */
  function buildOcorrenciasTimelineLabels(series) {
    if (!series.length) {
      return { labels: [], subtitle: "", tooltipTitle: null };
    }
    var dates = series.map(function (r) {
      return parseISODateLocal(r.data);
    });
    if (dates.some(function (d) {
      return !d;
    })) {
      return {
        labels: series.map(function (r) {
          return r.data;
        }),
        subtitle: "",
        tooltipTitle: null,
      };
    }
    var y0 = dates[0].getFullYear();
    var m0 = dates[0].getMonth();
    var sameYear = dates.every(function (dt) {
      return dt.getFullYear() === y0;
    });
    var sameMonth = dates.every(function (dt) {
      return dt.getMonth() === m0 && dt.getFullYear() === y0;
    });

    var labels = series.map(function (r, idx) {
      var dt = dates[idx];
      var dd = String(dt.getDate()).padStart(2, "0");
      var mm = String(dt.getMonth() + 1).padStart(2, "0");
      var yy = dt.getFullYear();
      if (sameMonth) {
        return String(dt.getDate());
      }
      if (sameYear) {
        return dd + "/" + mm;
      }
      return dd + "/" + mm + "/" + String(yy).slice(-2);
    });

    var subtitle = "";
    if (sameMonth && sameYear) {
      subtitle = MESES_PT[m0].charAt(0).toUpperCase() + MESES_PT[m0].slice(1) + " de " + y0;
    } else if (sameYear) {
      subtitle = "Ano " + y0 + " · cada ponto é dia/mês";
    } else {
      subtitle = "Datas completas no eixo";
    }

    function tooltipTitle(tooltipItems) {
      if (!tooltipItems || !tooltipItems.length) return "";
      var i = tooltipItems[0].dataIndex;
      var raw = series[i] && series[i].data;
      var dt = parseISODateLocal(raw);
      if (!dt) return raw || "";
      var mes = MESES_PT[dt.getMonth()];
      return dt.getDate() + " de " + mes + " de " + dt.getFullYear();
    }

    return { labels: labels, subtitle: subtitle, tooltipTitle: tooltipTitle };
  }

  function renderOcorrenciasPorDia(payload) {
    var canvas = document.getElementById("chart-ocorrencias-dia");
    if (!canvas || typeof Chart === "undefined") return;
    var series = (((payload || {}).diario || {}).ocorrencias_por_dia) || [];
    var axis = buildOcorrenciasTimelineLabels(series);
    var labels = axis.labels;
    var data = series.map(function (r) {
      return chartNum(r.total);
    });
    var maxValue = data.length ? Math.max.apply(null, data) : 0;
    var yMax = Math.max(2, maxValue + 1);
    var pal = chartPalette();
    var fillRgb = isDarkTheme() ? "56, 189, 248" : "2, 132, 199";
    var plugins = {
      legend: { labels: { color: pal.text } },
    };
    if (axis.subtitle) {
      plugins.subtitle = {
        display: true,
        text: axis.subtitle,
        color: pal.text,
        font: { size: 11, weight: "500" },
        padding: { bottom: 8, top: 0 },
      };
    }
    if (axis.tooltipTitle) {
      plugins.tooltip = {
        callbacks: {
          title: axis.tooltipTitle,
          footer: function (tooltipItems) {
            if (!tooltipItems || !tooltipItems.length) return "";
            var i = tooltipItems[0].dataIndex;
            var row = series[i];
            if (row && row.relatorio_id) {
              return "Abrir o RDO deste dia";
            }
            if (row && row.data && window.__AO_REPORTS_URL__) {
              return "Ver relatórios desta data";
            }
            return "";
          },
        },
      };
    }
    new Chart(canvas, {
      type: "line",
      data: {
        labels: labels,
        datasets: [
          {
            label: "Ocorrências",
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
        plugins: plugins,
        onClick: function (_evt, elements) {
          if (!elements || !elements.length) return;
          var idx = elements[0].index;
          var row = series[idx];
          if (!row) return;
          var rid = row.relatorio_id;
          var d = (row.data || "").slice(0, 10);
          if (rid) {
            window.location.href = "/diaries/" + encodeURIComponent(rid) + "/";
            return;
          }
          var base = window.__AO_REPORTS_URL__;
          if (base && d) {
            var u = base.indexOf("?") >= 0 ? base + "&" : base + "?";
            window.location.href =
              u +
              "date_start=" +
              encodeURIComponent(d) +
              "&date_end=" +
              encodeURIComponent(d);
          }
        },
        onHover: function (evt, els) {
          var t = evt.native && evt.native.target;
          if (t) t.style.cursor = els && els.length ? "pointer" : "default";
        },
        scales: {
          x: {
            ticks: {
              color: pal.text,
              maxRotation: labels.length > 12 ? 35 : 0,
              minRotation: labels.length > 12 ? 35 : 0,
              autoSkip: true,
              maxTicksLimit: labels.length > 20 ? 12 : 16,
            },
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

  function syncProgChartExpandButton() {
    var btn = document.getElementById("aoProgChartExpand");
    if (!btn) return;
    var payload = readPayload();
    if (!payload) return;
    var controle = payload.controle || {};
    var resumo = controle.blocos_mais_atrasados || [];
    var completo =
      controle.progressao_eixos_completo && controle.progressao_eixos_completo.length
        ? controle.progressao_eixos_completo
        : resumo;
    var hasMoreData = completo.length > resumo.length;
    var modo = typeof window.__aoProgChartModo === "string" ? window.__aoProgChartModo : "resumo";
    if (hasMoreData) {
      if (modo === "completo") {
        btn.textContent = "Voltar ao resumo";
        btn.setAttribute("aria-expanded", "true");
      } else {
        btn.textContent = "Ver todos os eixos (" + completo.length + ")";
        btn.setAttribute("aria-expanded", "false");
      }
      return;
    }
    if (resumo.length > 6) {
      var heightOpen = !!window.__aoProgChartHeightOpen;
      btn.textContent = heightOpen ? "Recolher gráfico" : "Expandir gráfico";
      btn.setAttribute("aria-expanded", heightOpen ? "true" : "false");
    }
  }

  function renderBlocosCriticos(payload) {
    var canvas = document.getElementById("chart-blocos-controle");
    if (!canvas || typeof Chart === "undefined") return;
    if (typeof Chart !== "undefined" && Chart.getChart) {
      var prev = Chart.getChart(canvas);
      if (prev) prev.destroy();
    }
    var controle = (payload || {}).controle || {};
    var resumo = controle.blocos_mais_atrasados || [];
    var completo =
      controle.progressao_eixos_completo && controle.progressao_eixos_completo.length
        ? controle.progressao_eixos_completo
        : resumo;
    var hasMoreData = completo.length > resumo.length;
    var modo = typeof window.__aoProgChartModo === "string" ? window.__aoProgChartModo : "resumo";
    var rows = hasMoreData && modo === "completo" ? completo : resumo;
    var chartWrap = canvas.closest(".ao-chart-box");
    var heightOpen = !!window.__aoProgChartHeightOpen;
    var useLimited = rows.length > 6 && !heightOpen;
    if (chartWrap) {
      if (useLimited) {
        chartWrap.classList.add("ao-chart-prog--limited");
      } else {
        chartWrap.classList.remove("ao-chart-prog--limited");
      }
      if (!useLimited && rows.length > 6) {
        chartWrap.style.minHeight = progChartFullHeightPx(rows.length) + "px";
      } else {
        chartWrap.style.minHeight = "";
      }
    }
    var fullLabels = rows.map(function (r) {
      return r.rotulo || r.bloco || "-";
    });
    var labels = fullLabels.map(function (s) {
      return truncateLabel(s, 34);
    });
    var data = rows.map(pctMedioControleRow);
    var maxV = data.length ? Math.max.apply(null, data) : 0;
    var pal = chartPalette();
    var dark = isDarkTheme();
    var bg = dark ? "rgba(74, 222, 128, 0.88)" : "rgba(22, 163, 74, 0.55)";
    var border = dark ? "#bbf7d0" : "#15803d";
    var zeroHintFill = dark ? "rgba(74, 222, 128, 0.55)" : "rgba(22, 163, 74, 0.65)";
    var pluginsOpts = {
      legend: { labels: { color: pal.text } },
      tooltip: {
        callbacks: {
          title: function (items) {
            var i = items && items[0] ? items[0].dataIndex : 0;
            return fullLabels[i] != null ? String(fullLabels[i]) : "";
          },
          label: function (ctx) {
            var v = chartNum(ctx.raw);
            return "% médio: " + v + "%";
          },
          footer: function () {
            return "Abrir este eixo no mapa";
          },
        },
      },
    };
    if (rows.length && maxV < 0.05) {
      pluginsOpts.subtitle = {
        display: true,
        text:
          maxV <= 0
            ? "0%: a barra quase não aparece — veja a tabela ou o mapa."
            : "Valor baixo: a barra pode parecer fina — veja o % no tooltip ou na tabela.",
        color: pal.text,
        font: { size: 11 },
        padding: { bottom: 6, top: 0 },
      };
    }
    new Chart(canvas, {
      type: "bar",
      data: {
        labels: labels,
        datasets: [
          {
            label: "% médio",
            data: data,
            backgroundColor: bg,
            borderColor: border,
            borderWidth: dark ? 1 : 1,
          },
        ],
      },
      options: {
        indexAxis: "y",
        responsive: true,
        maintainAspectRatio: false,
        layout: {
          padding: { left: 4, right: 8, top: 4, bottom: 4 },
        },
        elements: {
          bar: {
            borderSkipped: false,
            borderWidth: dark ? 1 : 1,
            minBarLength: 6,
          },
        },
        plugins: pluginsOpts,
        onClick: function (_evt, elements) {
          if (!elements || !elements.length) return;
          var idx = elements[0].index;
          var row = rows[idx];
          if (!row) return;
          var url = mapaControleEixoUrl(row.setor, row.bloco);
          if (url) window.location.href = url;
        },
        onHover: function (evt, els) {
          var t = evt.native && evt.native.target;
          if (t) t.style.cursor = els && els.length ? "pointer" : "default";
        },
        scales: {
          x: {
            type: "linear",
            min: 0,
            max: 100,
            ticks: { color: pal.text },
            grid: { color: pal.grid },
          },
          y: {
            type: "category",
            ticks: {
              color: pal.text,
              autoSkip: false,
              maxWidth: 220,
            },
            grid: { display: false },
          },
        },
      },
      plugins: [pluginBlocosZeroHint(zeroHintFill)],
    });
    syncProgChartExpandButton();
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
      return chartNum(x[1]);
    });
    var pal = chartPalette();
    var dark = isDarkTheme();
    var bg = dark ? "rgba(251, 191, 36, 0.85)" : "rgba(217, 119, 6, 0.5)";
    var border = dark ? "#fde68a" : "#b45309";
    new Chart(canvas, {
      type: "bar",
      data: {
        labels: labels,
        datasets: [
          {
            label: "Pendências por local",
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
        elements: {
          bar: {
            borderSkipped: false,
          },
        },
        plugins: {
          legend: { labels: { color: pal.text } },
          tooltip: {
            callbacks: {
              footer: function () {
                return "Abrir o dashboard deste local";
              },
            },
          },
        },
        onClick: function (_evt, elements) {
          if (!elements || !elements.length) return;
          var idx = elements[0].index;
          var nome = labels[idx];
          var lid = resolveLocalIdFromNome(payload, nome);
          var url = lid ? dashboardLocalUrl(lid) : null;
          if (url) window.location.href = url;
        },
        onHover: function (evt, els) {
          var t = evt.native && evt.native.target;
          if (t) t.style.cursor = els && els.length ? "pointer" : "default";
        },
        scales: {
          x: {
            type: "linear",
            beginAtZero: true,
            ticks: { color: pal.text, precision: 0 },
            grid: { color: pal.grid },
          },
          y: {
            type: "category",
            ticks: { color: pal.text },
            grid: { display: false },
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
      return chartNum(t.total);
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
          tooltip: {
            callbacks: {
              footer: function () {
                return "Filtrar por esta tag";
              },
            },
          },
        },
        onClick: function (_evt, elements) {
          if (!elements || !elements.length) return;
          var idx = elements[0].index;
          var tag = tags[idx];
          if (tag && tag.id != null) applyTagFilterAnalise(tag.id);
        },
        onHover: function (evt, els) {
          var t = evt.native && evt.native.target;
          if (t) t.style.cursor = els && els.length ? "pointer" : "default";
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
    window.__aoProgChartModo = "resumo";
    window.__aoProgChartHeightOpen = false;
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
      '<p class="small ao-drill-muted mb-2">Bloco ' +
      escapeHtml((data.chave || {}).bloco) +
      " · Piso " +
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
      '<div class="ao-drill-kpi-grid"><div class="ao-drill-kpi"><small>% médio aqui</small><strong>' +
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
      '<h6 class="mt-3 mb-2">Atividades mais atrasadas</h6>' +
      '<div class="ao-table-wrap my-2"><table class="ao-table"><thead><tr><th>Atividade</th><th>Apto</th><th>Status</th><th>%</th></tr></thead><tbody>' +
      (travadas || '<tr><td colspan="4" class="ao-empty">Nenhuma atividade crítica</td></tr>') +
      "</tbody></table></div>" +
      '<h6 class="mt-3 mb-2">Material pendente</h6>' +
      '<ul class="ao-drill-list">' +
      (materiais || '<li class="ao-drill-muted">Nada crítico aqui.</li>') +
      "</ul>" +
      '<p class="small mt-3"><span class="ao-badge-origem controle">Mapa</span> Primeiras linhas (12)</p>' +
      '<div class="ao-table-wrap my-2"><table class="ao-table"><thead><tr><th>Atividade</th><th>Apto</th><th>Status</th><th>%</th></tr></thead><tbody>' +
      (lines || '<tr><td colspan="4" class="ao-empty">Sem itens</td></tr>') +
      "</tbody></table></div>" +
      '<p class="small"><span class="ao-badge-origem suprimentos">Suprimentos</span> ' +
      escapeHtml(s.nota || "") +
      "</p>" +
      '<pre class="small ao-drill-muted" style="white-space:pre-wrap;max-height:120px;overflow:auto">' +
      escapeHtml(JSON.stringify(s.kpis || {}, null, 0)) +
      "</pre>";
  }

  function openDrilldown(bloco, pavimento, setor) {
    var base = window.__ANALISE_DRILL_URL__;
    if (!base) return;
    var qp = new URLSearchParams(window.location.search);
    qp.set("bloco", bloco);
    qp.set("pavimento", pavimento || "");
    if (setor != null && String(setor).trim() !== "") {
      qp.set("setor", String(setor).trim());
    } else {
      qp.delete("setor");
    }
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

  function progChartFullHeightPx(rowCount) {
    var n = rowCount || 1;
    return Math.min(580, Math.max(220, 32 * n + 56));
  }

  function initProgressaoChartExpand() {
    var btn = document.getElementById("aoProgChartExpand");
    if (!btn) return;
    btn.addEventListener("click", function () {
      var payload = readPayload();
      if (!payload) return;
      var controle = payload.controle || {};
      var resumo = controle.blocos_mais_atrasados || [];
      var completo =
        controle.progressao_eixos_completo && controle.progressao_eixos_completo.length
          ? controle.progressao_eixos_completo
          : resumo;
      var hasMoreData = completo.length > resumo.length;
      if (hasMoreData) {
        var modo = typeof window.__aoProgChartModo === "string" ? window.__aoProgChartModo : "resumo";
        window.__aoProgChartModo = modo === "resumo" ? "completo" : "resumo";
        window.__aoProgChartHeightOpen = false;
        renderBlocosCriticos(payload);
        return;
      }
      window.__aoProgChartHeightOpen = !window.__aoProgChartHeightOpen;
      renderBlocosCriticos(payload);
    });
  }

  function initProgressaoTabelaExpand() {
    var btn = document.getElementById("aoProgTabelaExpand");
    if (!btn) return;
    btn.addEventListener("click", function () {
      var rows = document.querySelectorAll(".ao-prog-tabela-extra");
      var expanded = btn.getAttribute("aria-expanded") === "true";
      rows.forEach(function (row) {
        row.classList.toggle("d-none", expanded);
      });
      btn.setAttribute("aria-expanded", expanded ? "false" : "true");
      btn.textContent = expanded ? "Ver mais eixos" : "Ver menos eixos";
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
    initProgressaoChartExpand();
    initProgressaoTabelaExpand();
    initOccurrenceCollapseButton();
    initBiNavigationClicks();

    document.querySelectorAll(".ao-heat-row").forEach(function (row) {
      row.addEventListener("click", function (ev) {
        if (ev.target.closest(".ao-drill-btn")) return;
        var b = row.getAttribute("data-bloco");
        var p = row.getAttribute("data-pavimento");
        var st = row.getAttribute("data-setor");
        if (b) openDrilldown(b, p || "", st);
      });
    });
    document.querySelectorAll(".ao-drill-btn").forEach(function (btn) {
      btn.addEventListener("click", function (ev) {
        ev.stopPropagation();
        var row = btn.closest(".ao-heat-row");
        if (!row) return;
        openDrilldown(
          row.getAttribute("data-bloco"),
          row.getAttribute("data-pavimento") || "",
          row.getAttribute("data-setor")
        );
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
