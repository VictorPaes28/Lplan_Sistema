(function () {
  "use strict";

  const COLOR_SEP = "\u001f";
  const BUCKET_CLASSES = ["cell-90", "cell-70", "cell-40", "cell-10", "cell-0"];

  function rowLabelFromNameCell(nameCell) {
    if (!nameCell) return "";
    const plain = nameCell.querySelector(".row-name-txt");
    if (plain) return String(plain.textContent || "").trim();
    const link = nameCell.querySelector("a.row-link");
    if (link) return String(link.textContent || "").trim();
    return String(nameCell.textContent || "").trim();
  }

  function activityLabelFromHeader(th) {
    if (!th) return "";
    const link = th.querySelector(".matrix-col-head-link");
    return String((link ? link.textContent : th.textContent) || "").trim();
  }

  function applyManualCellColor(cell, color) {
    const hex = String(color || "").trim();
    if (!hex) return;
    BUCKET_CLASSES.forEach((cls) => cell.classList.remove(cls));
    cell.classList.add("po-mapa-manual-color");
    cell.style.setProperty("background-color", hex, "important");
    cell.style.setProperty("color", "#ffffff", "important");
    const link = cell.querySelector("a.cell-link");
    if (link) {
      link.style.setProperty("background-color", hex, "important");
      link.style.setProperty("color", "#ffffff", "important");
    }
  }

  function applySavedCellColors() {
    const dataEl = document.getElementById("poMapaSavedCellColors");
    if (!dataEl) return;
    let colors = {};
    try {
      colors = JSON.parse(dataEl.textContent || "{}");
    } catch (e) {
      void e;
      return;
    }
    if (!colors || typeof colors !== "object" || !Object.keys(colors).length) return;

    const table = document.querySelector(".matrix-table");
    if (!table) return;
    const bloco = String(table.getAttribute("data-po-bloco") || "").trim();
    const pavimento = String(table.getAttribute("data-po-pavimento") || "").trim();
    const headerRow = table.querySelector("thead tr");
    const tbody = table.querySelector("tbody");
    if (!headerRow || !tbody) return;

    const colCount = headerRow.children.length;
    const totalColIdx = colCount - 1;

    tbody.querySelectorAll("tr").forEach((tr) => {
      if (
        tr.classList.contains("totals-row") ||
        tr.classList.contains("matrix-empty-row") ||
        String(tr.getAttribute("data-empty-row") || "") === "1"
      ) {
        return;
      }
      const nameCell = tr.querySelector(".row-name, .sticky-left");
      const rowLabel = rowLabelFromNameCell(nameCell);
      const cells = tr.querySelectorAll("td");
      cells.forEach((cell, cIdx) => {
        if (cIdx <= 0 || cIdx >= totalColIdx) return;
        if (!cell.classList.contains("cell-pct")) return;
        if (cell.classList.contains("po-mapa-manual-color")) return;
        const activity = activityLabelFromHeader(headerRow.children[cIdx]);
        const key = [bloco, pavimento, rowLabel, activity].join(COLOR_SEP);
        const hex = colors[key];
        if (hex) applyManualCellColor(cell, hex);
      });
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", applySavedCellColors);
  } else {
    applySavedCellColors();
  }
})();
