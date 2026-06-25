/**
 * BI da Obra — UX: drawer KPI, sparklines, situação, barra de prioridades.
 */
(function () {
  "use strict";

  function esc(s) {
    if (s == null) return "";
    return String(s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function priClass(p) {
    var u = String(p || "").toUpperCase();
    if (u.indexOf("URG") >= 0) return "pri-urgente";
    if (u.indexOf("ALT") >= 0) return "pri-alta";
    if (u.indexOf("MED") >= 0) return "pri-media";
    return "pri-rotina";
  }

  function renderSparkline(values, color) {
    if (!values || !values.length) return "";
    var max = Math.max.apply(null, values.map(Number));
    var min = Math.min.apply(null, values.map(Number));
    var range = max - min || 1;
    var w = 80;
    var h = 22;
    var pts = values.map(function (v, i) {
      var x = (i / Math.max(1, values.length - 1)) * w;
      var y = h - ((Number(v) - min) / range) * (h - 4) - 2;
      return x.toFixed(1) + "," + y.toFixed(1);
    });
    return (
      '<svg class="hkpi-spark" viewBox="0 0 ' +
      w +
      " " +
      h +
      '" preserveAspectRatio="none" aria-hidden="true">' +
      '<polyline fill="none" stroke="' +
      esc(color || "var(--bi-accent)") +
      '" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" points="' +
      pts.join(" ") +
      '"/></svg>'
    );
  }

  function initSparklines() {
    var data = window.__AO_SPARKLINES__ || {};
    var colors = {
      avanco: "var(--bi-accent)",
      restricoes: "var(--bi-red)",
      aprovacao: "var(--bi-yellow)",
      rdos: "var(--bi-blue)",
    };
    document.querySelectorAll("[data-spark]").forEach(function (el) {
      var key = el.getAttribute("data-spark");
      var series = data[key];
      if (!series || !series.length) return;
      el.insertAdjacentHTML("beforeend", renderSparkline(series, colors[key]));
    });
  }

  function initPriorityBar() {
    var bar = document.getElementById("bi-priority-bar");
    if (!bar) return;
    var acoes = window.__AO_ACOES_PRIORITARIAS__ || [];
    if (!acoes.length) {
      bar.style.display = "none";
      return;
    }
    var html = '<div class="bi-priority-bar-title">Ações prioritárias hoje</div><div class="bi-priority-list">';
    acoes.forEach(function (a) {
      var href = a.url || a.ancora || "#";
      html +=
        '<a href="' +
        esc(href) +
        '" class="bi-priority-chip ' +
        priClass(a.prioridade) +
        '" data-priority-modulo="' +
        esc(a.modulo || "") +
        '"><span class="pri-dot"></span>' +
        esc(a.texto || a.acao || "") +
        "</a>";
    });
    html += "</div>";
    bar.innerHTML = html;
  }

  window.biMergePriorityActions = function (extra) {
    if (!extra || !extra.length) return;
    var bar = document.getElementById("bi-priority-bar");
    if (!bar) return;
    var list = bar.querySelector(".bi-priority-list");
    if (!list) {
      initPriorityBar();
      list = bar.querySelector(".bi-priority-list");
    }
    if (!list) return;
    var existing = {};
    list.querySelectorAll("[data-priority-modulo]").forEach(function (el) {
      existing[el.getAttribute("data-priority-modulo")] = true;
    });
    extra.forEach(function (a) {
      if (a.modulo && existing[a.modulo]) return;
      if (a.modulo) existing[a.modulo] = true;
      var chip = document.createElement("a");
      chip.href = a.url || a.ancora || "#";
      chip.className = "bi-priority-chip " + priClass(a.prioridade);
      if (a.modulo) chip.setAttribute("data-priority-modulo", a.modulo);
      chip.innerHTML = '<span class="pri-dot"></span>' + esc(a.texto || a.acao || "");
      list.appendChild(chip);
    });
    bar.style.display = "";
  };

  function initSituacao() {
    var badge = document.getElementById("bi-sit-badge");
    var pop = document.getElementById("bi-sit-popover");
    if (!badge || !pop) return;
    var sit = window.__AO_SITUACAO__ || {};
    var motivos = sit.motivos || [];
    var ul = pop.querySelector("ul");
    if (ul) {
      if (motivos.length) {
        ul.innerHTML = motivos.map(function (m) {
          return "<li>" + esc(m) + "</li>";
        }).join("");
      } else {
        ul.innerHTML = "<li>Obra dentro do previsto no recorte atual.</li>";
      }
    }

    badge.addEventListener("click", function (e) {
      e.preventDefault();
      e.stopPropagation();
      var open = pop.classList.contains("is-open");
      if (open && (sit.nivel === "risco" || sit.nivel === "atencao")) {
        pop.classList.remove("is-open");
        var target = document.getElementById("bloco-1c");
        if (target) target.scrollIntoView({ behavior: "smooth", block: "start" });
      } else {
        pop.classList.toggle("is-open");
      }
    });

    document.addEventListener("click", function (e) {
      if (!pop.contains(e.target) && !badge.contains(e.target)) {
        pop.classList.remove("is-open");
      }
    });
  }

  var drawerData = {};

  function openDrawer(kpiKey) {
    var backdrop = document.getElementById("bi-drawer-backdrop");
    var body = document.getElementById("bi-drawer-body");
    var title = document.getElementById("bi-drawer-title");
    if (!backdrop || !body) return;
    var d = drawerData[kpiKey] || window.__AO_HERO_DRAWER__ && window.__AO_HERO_DRAWER__[kpiKey];
    if (!d) return;

    if (title) title.textContent = d.titulo || "Detalhe";
    var actions = (d.acoes || [])
      .map(function (a) {
        return (
          '<a href="' +
          esc(a.url) +
          '" class="bi-drawer-btn">' +
          esc(a.label) +
          "<span>›</span></a>"
        );
      })
      .join("");
    body.innerHTML =
      '<div class="bi-drawer-kpi">' +
      esc(d.valor) +
      '</div><div class="bi-drawer-sub">' +
      esc(d.subtitulo || "") +
      "</div>" +
      (d.detalhes
        ? '<div style="font-size:12px;color:var(--bi-text2);line-height:1.5">' +
          esc(d.detalhes) +
          "</div>"
        : "") +
      (actions ? '<div class="bi-drawer-actions">' + actions + "</div>" : "");

    backdrop.classList.add("is-open");
    backdrop.setAttribute("aria-hidden", "false");
    document.body.style.overflow = "hidden";
  }

  function closeDrawer() {
    var backdrop = document.getElementById("bi-drawer-backdrop");
    if (!backdrop) return;
    backdrop.classList.remove("is-open");
    backdrop.setAttribute("aria-hidden", "true");
    document.body.style.overflow = "";
  }

  function initDrawer() {
    drawerData = window.__AO_HERO_DRAWER__ || {};
    var backdrop = document.getElementById("bi-drawer-backdrop");
    if (backdrop) {
      backdrop.addEventListener("click", function (e) {
        if (e.target === backdrop) closeDrawer();
      });
      var closeBtn = document.getElementById("bi-drawer-close");
      if (closeBtn) closeBtn.addEventListener("click", closeDrawer);
    }
    var body = document.getElementById("bi-drawer-body");
    if (body) {
      body.addEventListener("click", function (e) {
        var btn = e.target.closest(".bi-drawer-btn");
        if (!btn) return;
        var href = btn.getAttribute("href");
        if (href && href.charAt(0) === "#") {
          e.preventDefault();
          closeDrawer();
          var target = document.querySelector(href);
          if (target) target.scrollIntoView({ behavior: "smooth", block: "start" });
        }
      });
    }
    document.querySelectorAll("[data-kpi-drawer]").forEach(function (el) {
      el.addEventListener("click", function (e) {
        var key = el.getAttribute("data-kpi-drawer");
        if (!key) return;
        if (el.getAttribute("href") && el.getAttribute("href").charAt(0) === "#") {
          e.preventDefault();
        }
        openDrawer(key);
      });
    });
    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape") closeDrawer();
    });
  }

  function init() {
    initSparklines();
    initPriorityBar();
    initSituacao();
    initDrawer();
    document.querySelectorAll(".analise-loading-skeleton").forEach(function (el) {
      el.classList.add("analise-loading-skeleton--shimmer");
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
