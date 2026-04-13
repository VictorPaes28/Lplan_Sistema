/**
 * Tema claro / escuro em todo o layout base (localStorage: lplan_theme).
 * Migra chave antiga lplan_ao_bi_theme. Dispara evento lplan-theme-change.
 */
(function () {
  "use strict";

  var KEY = "lplan_theme";
  var OLD_KEY = "lplan_ao_bi_theme";

  function getTheme() {
    return document.documentElement.getAttribute("data-theme") === "dark"
      ? "dark"
      : "light";
  }

  function migrateLegacy() {
    try {
      if (!localStorage.getItem(KEY)) {
        var o = localStorage.getItem(OLD_KEY);
        if (o === "dark" || o === "light") {
          localStorage.setItem(KEY, o);
        }
      }
    } catch (e) {}
  }

  function applyTheme(theme) {
    var t = theme === "dark" ? "dark" : "light";
    document.documentElement.setAttribute("data-theme", t);
    try {
      localStorage.setItem(KEY, t);
    } catch (e) {}
    document.body.classList.remove("lplan-bi-theme-dark");
    document.dispatchEvent(
      new CustomEvent("lplan-theme-change", { detail: { theme: t } })
    );
    updateThemeUi();
  }

  function updateThemeUi() {
    var dark = getTheme() === "dark";
    var btnLight = document.getElementById("lplan-theme-light");
    var btnDark = document.getElementById("lplan-theme-dark");
    if (btnLight) {
      btnLight.setAttribute("aria-pressed", !dark ? "true" : "false");
      btnLight.classList.toggle("lplan-theme-seg--active", !dark);
    }
    if (btnDark) {
      btnDark.setAttribute("aria-pressed", dark ? "true" : "false");
      btnDark.classList.toggle("lplan-theme-seg--active", dark);
    }
  }

  function init() {
    migrateLegacy();
    var stored = null;
    try {
      stored = localStorage.getItem(KEY);
    } catch (e) {}
    if (stored === "dark" || stored === "light") {
      document.documentElement.setAttribute("data-theme", stored);
    } else if (!document.documentElement.getAttribute("data-theme")) {
      document.documentElement.setAttribute("data-theme", "light");
    }
    updateThemeUi();

    var btnLight = document.getElementById("lplan-theme-light");
    var btnDark = document.getElementById("lplan-theme-dark");
    if (btnLight) {
      btnLight.addEventListener("click", function () {
        applyTheme("light");
      });
    }
    if (btnDark) {
      btnDark.addEventListener("click", function () {
        applyTheme("dark");
      });
    }
  }

  window.LPLAN_THEME_KEY = KEY;
  window.LPLAN_getTheme = getTheme;
  window.LPLAN_setTheme = applyTheme;
  window.LPLAN_toggleTheme = function () {
    applyTheme(getTheme() === "dark" ? "light" : "dark");
  };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
