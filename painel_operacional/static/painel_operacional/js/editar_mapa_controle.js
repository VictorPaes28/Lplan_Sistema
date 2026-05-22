(function () {
  const ctx = window.PO_MAPA_EDIT_CONTEXT || {};
  const frame = document.getElementById("poMapaEditFrame");
  const loading = document.getElementById("poMapaEditLoading");
  const btnToggle = document.getElementById("btnMapaEditToggle");
  const inpText = document.getElementById("inpMapaEditText");
  const btnApplyText = document.getElementById("btnMapaApplyText");
  const inpColor = document.getElementById("inpMapaEditColor");
  const btnApplyColor = document.getElementById("btnMapaApplyColor");
  const btnMoveColLeft = document.getElementById("btnMapaMoveColLeft");
  const btnMoveColRight = document.getElementById("btnMapaMoveColRight");
  const btnMoveRowUp = document.getElementById("btnMapaMoveRowUp");
  const btnMoveRowDown = document.getElementById("btnMapaMoveRowDown");
  const btnAddCol = document.getElementById("btnMapaAddCol");
  const btnAddRow = document.getElementById("btnMapaAddRow");
  const btnDeleteCol = document.getElementById("btnMapaDeleteCol");
  const btnDeleteRow = document.getElementById("btnMapaDeleteRow");
  const btnSaveDraft = document.getElementById("btnMapaSaveDraft");
  const btnDiscardDraft = document.getElementById("btnMapaDiscardDraft");
  const statusEl = document.getElementById("poMapaEditStatus");
  if (!frame) return;
  const contextMenuEl = document.createElement("div");
  contextMenuEl.id = "poMapaContextMenu";
  contextMenuEl.className = "po-mapa-context-menu";
  contextMenuEl.hidden = true;
  document.body.appendChild(contextMenuEl);
  let bridgedDeltaY = 0;
  let bridgeRaf = 0;
  let restoreParentScrollY = null;
  const matrixDnD = {
    active: false,
    axis: null,
    from: null,
    dropTarget: null,
    dragEl: null,
    handleEl: null,
    pointerId: null,
    onPointerMove: null,
    onPointerEnd: null,
  };

  const storageKey = `po_mapa_edit_draft_${ctx.ambienteId || "global"}`;
  const state = {
    enabled: false,
    dirty: false,
    selectedCell: null,
    selectedKey: "",
    draft: loadDraft(),
    inline: {
      cell: null,
      node: null,
      key: "",
      originalText: "",
      originalHref: null,
      originalBoxShadow: "",
    },
    context: {
      visible: false,
    },
  };

  const contextMenuStyle = document.createElement("style");
  contextMenuStyle.textContent = `
    .po-mapa-context-menu {
      position: fixed;
      min-width: 230px;
      max-width: 280px;
      z-index: 12000;
      border: 1px solid #dbeafe;
      border-radius: 12px;
      background: #ffffff;
      box-shadow: 0 18px 40px rgba(15, 23, 42, 0.2);
      padding: 8px;
      display: flex;
      flex-direction: column;
      gap: 4px;
      font-size: 0.78rem;
    }
    .po-mapa-context-menu__title {
      font-size: 0.69rem;
      font-weight: 700;
      color: #334155;
      background: #f8fafc;
      border: 1px solid #e2e8f0;
      border-radius: 8px;
      padding: 5px 8px;
      margin-bottom: 2px;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }
    .po-mapa-context-menu__item {
      width: 100%;
      border: 0;
      background: transparent;
      color: #0f172a;
      text-align: left;
      border-radius: 8px;
      padding: 7px 9px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 8px;
      cursor: pointer;
    }
    .po-mapa-context-menu__item:hover:not(:disabled) {
      background: #eff6ff;
      color: #1d4ed8;
    }
    .po-mapa-context-menu__item:disabled {
      opacity: 0.45;
      cursor: not-allowed;
    }
    .po-mapa-context-menu__item--danger { color: #b91c1c; }
    .po-mapa-context-menu__item--primary {
      background: #eff6ff;
      color: #1d4ed8;
      font-weight: 600;
    }
    .po-mapa-context-menu__sep {
      border-top: 1px solid #e2e8f0;
      margin: 3px 0;
    }
    .po-mapa-context-menu__hint {
      font-size: 0.67rem;
      color: #64748b;
    }
    .po-mapa-insert-dialog {
      position: fixed;
      inset: 0;
      z-index: 13000;
      display: flex;
      align-items: center;
      justify-content: center;
      padding: 16px;
    }
    .po-mapa-insert-dialog[hidden] {
      display: none !important;
    }
    .po-mapa-insert-dialog__backdrop {
      position: absolute;
      inset: 0;
      background: rgba(15, 23, 42, 0.45);
    }
    .po-mapa-insert-dialog__panel {
      position: relative;
      width: min(420px, 100%);
      border: 1px solid #dbeafe;
      border-radius: 14px;
      background: #fff;
      box-shadow: 0 22px 50px rgba(15, 23, 42, 0.22);
      padding: 16px 16px 14px;
      display: flex;
      flex-direction: column;
      gap: 12px;
    }
    .po-mapa-insert-dialog__title {
      margin: 0;
      font-size: 1rem;
      font-weight: 700;
      color: #0f172a;
    }
    .po-mapa-insert-dialog__scope {
      margin: 0;
      font-size: 0.78rem;
      line-height: 1.45;
      color: #475569;
      padding: 8px 10px;
      border-radius: 8px;
      background: #f8fafc;
      border: 1px solid #e2e8f0;
    }
    .po-mapa-insert-dialog__field label {
      display: block;
      margin-bottom: 5px;
      font-size: 0.75rem;
      font-weight: 600;
      color: #334155;
    }
    .po-mapa-insert-dialog__field input[type="text"] {
      width: 100%;
      border: 1px solid #cbd5e1;
      border-radius: 9px;
      padding: 8px 10px;
      font-size: 0.9rem;
    }
    .po-mapa-insert-dialog__field input[type="text"]:focus {
      outline: 2px solid #93c5fd;
      border-color: #60a5fa;
    }
    .po-mapa-insert-dialog__positions {
      display: flex;
      flex-direction: column;
      gap: 6px;
    }
    .po-mapa-insert-dialog__positions legend {
      font-size: 0.75rem;
      font-weight: 600;
      color: #334155;
      margin-bottom: 4px;
    }
    .po-mapa-insert-dialog__pos {
      display: flex;
      align-items: flex-start;
      gap: 8px;
      padding: 7px 9px;
      border: 1px solid #e2e8f0;
      border-radius: 9px;
      cursor: pointer;
      font-size: 0.8rem;
      color: #0f172a;
    }
    .po-mapa-insert-dialog__pos:hover {
      border-color: #93c5fd;
      background: #f8fbff;
    }
    .po-mapa-insert-dialog__pos.is-active {
      border-color: #2563eb;
      background: #eff6ff;
    }
    .po-mapa-insert-dialog__pos input {
      margin-top: 2px;
    }
    .po-mapa-insert-dialog__pos small {
      display: block;
      color: #64748b;
      font-size: 0.7rem;
      margin-top: 2px;
    }
    .po-mapa-insert-dialog__actions {
      display: flex;
      justify-content: flex-end;
      gap: 8px;
      margin-top: 2px;
    }
    .po-mapa-insert-dialog__actions .btn-primary {
      background: #2563eb;
      border-color: #2563eb;
    }
  `;
  document.head.appendChild(contextMenuStyle);

  const insertDialogEl = document.createElement("div");
  insertDialogEl.id = "poMapaInsertDialog";
  insertDialogEl.className = "po-mapa-insert-dialog";
  insertDialogEl.hidden = true;
  insertDialogEl.setAttribute("role", "dialog");
  insertDialogEl.setAttribute("aria-modal", "true");
  insertDialogEl.innerHTML = `
    <div class="po-mapa-insert-dialog__backdrop" data-insert-dismiss="1"></div>
    <div class="po-mapa-insert-dialog__panel">
      <h3 class="po-mapa-insert-dialog__title" data-insert-title>Novo item</h3>
      <p class="po-mapa-insert-dialog__scope" data-insert-scope></p>
      <div class="po-mapa-insert-dialog__field">
        <label data-insert-name-label>Nome</label>
        <input type="text" data-insert-name autocomplete="off" />
      </div>
      <fieldset class="po-mapa-insert-dialog__positions">
        <legend>Posição na lista</legend>
        <label class="po-mapa-insert-dialog__pos" data-insert-pos="above">
          <input type="radio" name="poMapaInsertPos" value="above" />
          <span><span data-insert-pos-above-label>Acima da linha selecionada</span></span>
        </label>
        <label class="po-mapa-insert-dialog__pos" data-insert-pos="below">
          <input type="radio" name="poMapaInsertPos" value="below" />
          <span><span data-insert-pos-below-label>Abaixo da linha selecionada</span></span>
        </label>
        <label class="po-mapa-insert-dialog__pos" data-insert-pos="end">
          <input type="radio" name="poMapaInsertPos" value="end" />
          <span>No final da lista<small>Depois de todas as linhas visíveis</small></span>
        </label>
      </fieldset>
      <div class="po-mapa-insert-dialog__actions">
        <button type="button" class="btn btn-outline-secondary btn-sm" data-insert-cancel>Cancelar</button>
        <button type="button" class="btn btn-primary btn-sm" data-insert-confirm>Adicionar</button>
      </div>
    </div>
  `;
  document.body.appendChild(insertDialogEl);

  const insertDialog = {
    open: false,
    kind: "row",
    onSubmit: null,
    els: {
      title: insertDialogEl.querySelector("[data-insert-title]"),
      scope: insertDialogEl.querySelector("[data-insert-scope]"),
      nameLabel: insertDialogEl.querySelector("[data-insert-name-label]"),
      nameInput: insertDialogEl.querySelector("[data-insert-name]"),
      posAbove: insertDialogEl.querySelector('[data-insert-pos="above"]'),
      posBelow: insertDialogEl.querySelector('[data-insert-pos="below"]'),
      posEnd: insertDialogEl.querySelector('[data-insert-pos="end"]'),
      posAboveLabel: insertDialogEl.querySelector("[data-insert-pos-above-label]"),
      posBelowLabel: insertDialogEl.querySelector("[data-insert-pos-below-label]"),
      confirm: insertDialogEl.querySelector("[data-insert-confirm]"),
      cancel: insertDialogEl.querySelector("[data-insert-cancel]"),
    },
  };

  function rowAxisHumanLabel(axisKey) {
    if (axisKey === "pavimento") return "Pavimento";
    if (axisKey === "apto") return "Unidade / apto";
    if (axisKey === "setor") return "Setor";
    return "Bloco";
  }

  function rowAxisPlaceholder(axisKey) {
    if (axisKey === "pavimento") return "Ex.: Térreo, 1º andar…";
    if (axisKey === "apto") return "Ex.: 101, 102, Sala 01…";
    if (axisKey === "setor") return "Ex.: Torre Norte…";
    return "Ex.: Bloco A, Bloco B…";
  }

  function buildRowInsertScopeHint() {
    const scope = parseCurrentScope();
    const axisKey = inferRowAxisKeyFromPage();
    const crumbs = [];
    if (scope.setor) crumbs.push(scope.setor);
    if (scope.bloco) crumbs.push(scope.bloco);
    if (scope.pavimento) crumbs.push(scope.pavimento);
    if (crumbs.length) {
      return `Dentro de ${crumbs.join(" › ")} — cadastre um novo ${rowAxisHumanLabel(axisKey).toLowerCase()} neste nível.`;
    }
    return `Lista de ${rowAxisHumanLabel(axisKey).toLowerCase()}s na raiz do mapa.`;
  }

  function selectedRowReferenceLabel() {
    const sc = selectedCoords();
    if (!sc || sc.r <= 0) return "";
    const table = tableRef();
    if (!table) return "";
    const tbody = table.querySelector("tbody");
    if (!tbody) return "";
    const rows = listMatrixTbodyRows(tbody);
    const row = rows[sc.r - 1];
    if (!row) return "";
    const nameCell = row.querySelector(".row-name, .sticky-left");
    if (!nameCell) return "";
    return rowDisplayLabelFromNameCell(nameCell) || "linha selecionada";
  }

  function selectedColumnReferenceLabel() {
    const sc = selectedCoords();
    if (!sc || sc.c <= 0) return "";
    const table = tableRef();
    if (!table) return "";
    const headerRow = table.querySelector("thead tr") || table.querySelector("tr");
    if (!headerRow) return "";
    const cell = headerRow.children[sc.c];
    if (!cell) return "";
    return String(textNodeForCell(cell).textContent || "").trim() || "coluna selecionada";
  }

  function syncInsertDialogPositionUi(kind) {
    const isColumn = kind === "column";
    const ref = isColumn ? selectedColumnReferenceLabel() : selectedRowReferenceLabel();
    const hasRef = Boolean(ref);
    const { posAbove, posBelow, posEnd, posAboveLabel, posBelowLabel } = insertDialog.els;
    const endHint = posEnd ? posEnd.querySelector("small") : null;
    if (posAbove) {
      posAbove.hidden = !hasRef;
      if (posAboveLabel) {
        if (isColumn) {
          posAboveLabel.textContent = hasRef ? `Antes de «${ref}»` : "Antes da coluna selecionada";
        } else {
          posAboveLabel.textContent = hasRef ? `Acima de «${ref}»` : "Acima da linha selecionada";
        }
      }
    }
    if (posBelow) {
      posBelow.hidden = !hasRef;
      if (posBelowLabel) {
        if (isColumn) {
          posBelowLabel.textContent = hasRef ? `Depois de «${ref}»` : "Depois da coluna selecionada";
        } else {
          posBelowLabel.textContent = hasRef ? `Abaixo de «${ref}»` : "Abaixo da linha selecionada";
        }
      }
    }
    if (posEnd) posEnd.hidden = false;
    if (endHint) {
      endHint.textContent = isColumn
        ? "Última posição antes da coluna Total"
        : "Depois de todas as linhas visíveis";
    }
    const defaultPos = hasRef ? "below" : "end";
    insertDialogEl.querySelectorAll('input[name="poMapaInsertPos"]').forEach((input) => {
      const label = input.closest(".po-mapa-insert-dialog__pos");
      input.checked = input.value === defaultPos;
      if (label) label.classList.toggle("is-active", input.checked);
    });
  }

  function hideInsertDialog() {
    insertDialog.open = false;
    insertDialog.onSubmit = null;
    insertDialogEl.hidden = true;
  }

  function showInsertDialog(config) {
    if (!config || typeof config.onSubmit !== "function") return;
    hideContextMenu();
    insertDialog.open = true;
    insertDialog.kind = config.kind === "column" ? "column" : "row";
    insertDialog.onSubmit = config.onSubmit;

    const { title, scope, nameLabel, nameInput, confirm } = insertDialog.els;
    if (title) title.textContent = insertDialog.kind === "column" ? "Nova coluna / atividade" : "Nova linha";
    if (scope) {
      scope.textContent =
        insertDialog.kind === "column"
          ? `Adiciona uma coluna de atividade no ${scopeDisplayLabel()}.`
          : buildRowInsertScopeHint();
    }
    if (nameLabel) {
      if (insertDialog.kind === "column") {
        nameLabel.textContent = "Nome da atividade";
      } else {
        nameLabel.textContent = rowAxisHumanLabel(inferRowAxisKeyFromPage());
      }
    }
    if (nameInput) {
      nameInput.value = "";
      nameInput.placeholder =
        insertDialog.kind === "column" ? "Ex.: Alvenaria, Instalações…" : rowAxisPlaceholder(inferRowAxisKeyFromPage());
    }
    if (confirm) confirm.textContent = insertDialog.kind === "column" ? "Adicionar coluna" : "Adicionar linha";
    const posLegend = insertDialogEl.querySelector(".po-mapa-insert-dialog__positions legend");
    if (posLegend) {
      posLegend.textContent = insertDialog.kind === "column" ? "Posição na grade" : "Posição na lista";
    }

    syncInsertDialogPositionUi(insertDialog.kind);
    insertDialogEl.hidden = false;
    window.setTimeout(() => {
      if (nameInput) {
        nameInput.focus();
        nameInput.select();
      }
    }, 0);
  }

  function readInsertDialogPosition() {
    const checked = insertDialogEl.querySelector('input[name="poMapaInsertPos"]:checked');
    return checked ? String(checked.value || "end") : "end";
  }

  function resolveRowInsertIndex(position) {
    const table = tableRef();
    if (!table) return 0;
    const tbody = table.querySelector("tbody");
    const bodyRows = listMatrixTbodyRows(tbody);
    let insertAt = bodyRows.length;
    const sc = selectedCoords();
    if (!sc || sc.r <= 0) return insertAt;
    const base = sc.r - 1;
    const mode = String(position || "below").trim().toLowerCase();
    if (mode === "above") return Math.max(0, base);
    if (mode === "end") return bodyRows.length;
    return Math.max(0, base + 1);
  }

  function resolveColumnInsertIndex(position) {
    const table = tableRef();
    if (!table) return 1;
    const headerRow = table.querySelector("tr");
    let insertAt = headerRow ? Math.max(1, headerRow.children.length - 1) : 1;
    const sc = selectedCoords();
    if (!sc || sc.c <= 0) return insertAt;
    const mode = String(position || "below").trim().toLowerCase();
    if (mode === "above") return sc.c;
    if (mode === "end") return Math.max(1, headerRow.children.length - 1);
    return sc.c + 1;
  }

  insertDialogEl.querySelectorAll(".po-mapa-insert-dialog__pos").forEach((label) => {
    label.addEventListener("click", () => {
      const input = label.querySelector('input[type="radio"]');
      if (!input || input.disabled) return;
      input.checked = true;
      insertDialogEl.querySelectorAll(".po-mapa-insert-dialog__pos").forEach((el) => {
        el.classList.toggle("is-active", el.querySelector('input[type="radio"]')?.checked);
      });
    });
  });

  insertDialogEl.querySelector("[data-insert-cancel]")?.addEventListener("click", () => hideInsertDialog());
  insertDialogEl.querySelector('[data-insert-dismiss="1"]')?.addEventListener("click", () => hideInsertDialog());
  insertDialogEl.querySelector("[data-insert-confirm]")?.addEventListener("click", () => {
    if (!insertDialog.open || typeof insertDialog.onSubmit !== "function") return;
    const name = String(insertDialog.els.nameInput?.value || "").trim();
    if (!name) {
      insertDialog.els.nameInput?.focus();
      updateStatus("Informe um nome para continuar.");
      return;
    }
    const position = readInsertDialogPosition();
    const submit = insertDialog.onSubmit;
    hideInsertDialog();
    submit({ name, position });
  });
  insertDialog.els.nameInput?.addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
      event.preventDefault();
      insertDialogEl.querySelector("[data-insert-confirm]")?.click();
    }
    if (event.key === "Escape") {
      event.preventDefault();
      hideInsertDialog();
    }
  });

  function hideLoading() {
    if (loading) loading.style.display = "none";
  }

  function hideContextMenu() {
    state.context.visible = false;
    contextMenuEl.hidden = true;
    contextMenuEl.innerHTML = "";
  }

  function menuSeparator() {
    const hr = document.createElement("div");
    hr.className = "po-mapa-context-menu__sep";
    return hr;
  }

  function menuItem(label, hint, options) {
    const cfg = options && typeof options === "object" ? options : {};
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = `po-mapa-context-menu__item${cfg.danger ? " po-mapa-context-menu__item--danger" : ""}${cfg.primary ? " po-mapa-context-menu__item--primary" : ""}`;
    btn.disabled = !!cfg.disabled;
    const text = document.createElement("span");
    text.textContent = label;
    const info = document.createElement("span");
    info.className = "po-mapa-context-menu__hint";
    info.textContent = hint || "";
    btn.appendChild(text);
    btn.appendChild(info);
    if (typeof cfg.onClick === "function") {
      btn.addEventListener("click", () => {
        cfg.onClick();
        hideContextMenu();
      });
    }
    return btn;
  }

  function showContextMenu(clientX, clientY) {
    const rect = frame.getBoundingClientRect();
    const x = Math.round(rect.left + Number(clientX || 0));
    const y = Math.round(rect.top + Number(clientY || 0));
    contextMenuEl.style.left = `${x}px`;
    contextMenuEl.style.top = `${y}px`;
    contextMenuEl.hidden = false;
    state.context.visible = true;

    const menuRect = contextMenuEl.getBoundingClientRect();
    let nextLeft = x;
    let nextTop = y;
    const pad = 10;
    if (nextLeft + menuRect.width > window.innerWidth - pad) {
      nextLeft = Math.max(pad, window.innerWidth - menuRect.width - pad);
    }
    if (nextTop + menuRect.height > window.innerHeight - pad) {
      nextTop = Math.max(pad, window.innerHeight - menuRect.height - pad);
    }
    contextMenuEl.style.left = `${nextLeft}px`;
    contextMenuEl.style.top = `${nextTop}px`;
  }

  function resizeFrameToContent() {
    try {
      const doc = frame.contentDocument;
      if (!doc) return;
      const body = doc.body;
      const html = doc.documentElement;
      const rawHeight = Math.max(
        Number(body && body.scrollHeight) || 0,
        Number(html && html.scrollHeight) || 0,
        600,
      );
      // Mantém o iframe em "viewport de edição" (não em página inteira),
      // para a matriz ficar próxima da barra e permitir foco no ponto de trabalho.
      const nextHeight = Math.min(rawHeight, 980);
      frame.style.height = `${nextHeight}px`;
    } catch (e) {
      void e;
    }
  }

  function scrollIframeToMatrix() {
    try {
      const doc = frame.contentDocument;
      const win = frame.contentWindow;
      if (!doc || !win) return;
      const matrixWrap = doc.querySelector(".matrix-wrap");
      if (!matrixWrap) return;
      const rect = matrixWrap.getBoundingClientRect();
      const targetTop = Math.max(0, (Number(win.scrollY || 0) + Number(rect.top || 0)) - 8);
      win.scrollTo({ top: targetTop, left: 0, behavior: "auto" });
    } catch (e) {
      void e;
    }
  }

  function loadDraft() {
    try {
      const raw = window.localStorage.getItem(storageKey);
      if (!raw) return { pages: {} };
      const data = JSON.parse(raw);
      if (data && typeof data === "object") {
        if (!data.pages || typeof data.pages !== "object") data.pages = {};
        return data;
      }
      return { pages: {} };
    } catch (e) {
      void e;
      return { pages: {} };
    }
  }

  function getCsrfToken() {
    if (ctx.csrfToken) return ctx.csrfToken;
    const match = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
    return match ? decodeURIComponent(match[1]) : "";
  }

  function sanitizeRowDisplayLabel(raw) {
    return String(raw || "")
      .replace(/[⋮⠿\u22ee]+/g, "")
      .replace(/^\s*\+\s*/, "")
      .replace(/\s+/g, " ")
      .trim();
  }

  function rowDisplayLabelFromNameCell(nameCell) {
    if (!nameCell) return "";
    const plain = nameCell.querySelector(".row-name-txt");
    if (plain) return sanitizeRowDisplayLabel(plain.textContent);
    const link = nameCell.querySelector("a.row-link");
    if (link) return sanitizeRowDisplayLabel(link.textContent);
    const wrap = nameCell.querySelector(".po-mapa-row-name-wrap");
    if (wrap) {
      const clone = wrap.cloneNode(true);
      clone.querySelectorAll(".po-mapa-row-add, .po-mapa-row-inline-add").forEach((el) => el.remove());
      return sanitizeRowDisplayLabel(clone.textContent);
    }
    return sanitizeRowDisplayLabel(textNodeForCell(nameCell).textContent);
  }

  function rowLabelForCell(cell) {
    if (!cell) return "";
    const tr = cell.closest("tr");
    if (!tr) return "";
    const nameCell = tr.querySelector(".row-name, .sticky-left");
    if (!nameCell) return "";
    return rowDisplayLabelFromNameCell(nameCell);
  }

  function isMatrixEmptyRow(tr) {
    return !!(tr && tr.classList && tr.classList.contains("matrix-empty-row"));
  }

  function isNonDataMatrixRow(tr) {
    return (
      !!(tr && tr.classList) &&
      (tr.classList.contains("totals-row") || tr.classList.contains("matrix-empty-row"))
    );
  }

  function removeMatrixEmptyRows(tbody) {
    if (!tbody) return 0;
    let removed = 0;
    tbody.querySelectorAll("tr.matrix-empty-row").forEach((tr) => {
      tbody.removeChild(tr);
      removed += 1;
    });
    return removed;
  }

  function listMatrixTbodyRows(tbody) {
    if (!tbody) return [];
    return Array.from(tbody.querySelectorAll("tr")).filter((tr) => !isNonDataMatrixRow(tr));
  }

  function shouldRowNameBeDrillLink(pageKey) {
    const ctx = getMatrixEditContext(pageKey);
    if (ctx.isAreaComum && ctx.mode === "pavimento") return false;
    return ctx.mode === "bloco" || ctx.mode === "pavimento" || ctx.mode === "apto";
  }

  function buildMatrixDrillHref(rowLabel, pageKey) {
    if (!shouldRowNameBeDrillLink(pageKey)) return null;
    try {
      const u = new URL(String(frame.contentWindow.location.href || ""), window.location.origin);
      const p = new URLSearchParams(u.search);
      const label = String(rowLabel || "").trim();
      if (!label) return null;
      const ctx = getMatrixEditContext(pageKey);
      if (ctx.mode === "bloco") {
        p.set("bloco", label);
        p.delete("pavimento");
        p.delete("apto");
      } else if (ctx.mode === "pavimento") {
        if (ctx.bloco) p.set("bloco", ctx.bloco);
        p.set("pavimento", label);
        p.delete("apto");
      } else if (ctx.mode === "apto") {
        if (ctx.bloco) p.set("bloco", ctx.bloco);
        if (ctx.pavimento) p.set("pavimento", ctx.pavimento);
        p.set("apto", label);
      }
      if (ctx.setor && !p.get("setor")) p.set("setor", ctx.setor);
      return `${u.pathname}?${p.toString()}`;
    } catch (e) {
      void e;
      return null;
    }
  }

  function populateRowNameCell(nameTd, title, pageKey) {
    const key = pageKey || currentPageKey();
    nameTd.className = "sticky-left row-name";
    nameTd.textContent = "";
    const href = buildMatrixDrillHref(title, key);
    const ctx = getMatrixEditContext(key);
    if (href) {
      const a = document.createElement("a");
      a.className = "cell-link row-link";
      a.href = href;
      a.textContent = title;
      if (ctx.mode === "bloco") {
        a.title = "Ver pavimentos deste bloco na matriz";
      } else if (ctx.mode === "pavimento" && !ctx.isAreaComum) {
        a.title = "Ver unidades (aptos) deste pavimento na matriz";
      }
      nameTd.appendChild(a);
    } else {
      const span = document.createElement("span");
      span.className = "row-name-txt";
      if (ctx.isAreaComum && ctx.mode === "pavimento") {
        span.title = "Área comum: sem camada de unidade";
      }
      span.textContent = title;
      nameTd.appendChild(span);
    }
    poMapaDebug("row-name preview", {
      pageKey: key,
      contexto: ctx,
      drill: !!href,
      href,
      html: nameTd.innerHTML,
    });
  }

  function extractLayoutMatrixFromLayout(layout) {
    const sections = layout && Array.isArray(layout.sections) ? layout.sections : [];
    for (let i = 0; i < sections.length; i += 1) {
      const data = sections[i] && sections[i].data;
      const rows = data && data.rows;
      if (Array.isArray(rows) && rows.length) {
        const header = rows[0];
        const meta = data.importMeta && typeof data.importMeta === "object" ? data.importMeta : {};
        return { rows, header, meta, axisMap: buildAxisMapFromMeta(meta, header) };
      }
    }
    return { rows: [], header: [], meta: {}, axisMap: {} };
  }

  function verifyCreateRowsInLayout(layout, structuralOps) {
    const { rows, axisMap } = extractLayoutMatrixFromLayout(layout);
    if (!rows.length) return structuralOps.filter((op) => op && op.type === "create_row");
    return structuralOps.filter((op) => {
      if (!op || op.type !== "create_row") return false;
      const context = op.context || {};
      const label = String(op.label || "").trim();
      return !layoutHasStructuralRow(rows, axisMap, context, label);
    });
  }

  function rememberCellPatch(cell, key, text) {
    const kind = patchKindForCell(cell);
    if (!kind) return;
    const page = ensurePageDraft(currentPageKey());
    const coords = cellCoordsFromKey(cell);
    if (!coords) return;
    page.cells = page.cells || {};
    page.cells[key] = {
      colIndex: coords.c,
      rowLabel: rowLabelForCell(cell),
      text: String(text || ""),
      kind,
    };
  }

  function parsePageFilters(pageKey) {
    try {
      const u = new URL(pageKey, window.location.origin);
      const filters = {};
      ["setor", "bloco", "pavimento", "apto"].forEach((k) => {
        const v = u.searchParams.get(k);
        if (v) filters[k] = v;
      });
      return filters;
    } catch (e) {
      return {};
    }
  }

  function normalizeSetorKey(setor) {
    return String(setor || "")
      .normalize("NFD")
      .replace(/[\u0300-\u036f]/g, "")
      .trim()
      .toUpperCase()
      .replace(/\s+/g, " ");
  }

  function isSetorAreaComum(setor) {
    return normalizeSetorKey(setor) === "AREA COMUM";
  }

  function parseScopeFromPageKey(pageKey) {
    try {
      const u = new URL(pageKey || currentPageKey(), window.location.origin);
      return {
        requestedMode: String(u.searchParams.get("matrix_mode") || "").trim().toLowerCase(),
        setor: String(u.searchParams.get("setor") || "").trim(),
        bloco: String(u.searchParams.get("bloco") || "").trim(),
        pavimento: String(u.searchParams.get("pavimento") || "").trim(),
        apto: String(u.searchParams.get("apto") || "").trim(),
      };
    } catch (e) {
      return { requestedMode: "", setor: "", bloco: "", pavimento: "", apto: "" };
    }
  }

  /** Espelha suprimentos.views_controle._resolve_matrix_mode (recorte + matrix_mode). */
  function resolveMatrixMode(scope) {
    const s = scope && typeof scope === "object" ? scope : parseScopeFromPageKey();
    let r = s.requestedMode;
    if (r && r !== "bloco" && r !== "pavimento" && r !== "apto") {
      r = "";
    }

    if (isSetorAreaComum(s.setor)) {
      if (r === "apto") r = "pavimento";
      if (s.bloco) return "pavimento";
      if (r === "pavimento" && !s.bloco) return "bloco";
      if (r === "pavimento") return "pavimento";
      if (r === "bloco") return "bloco";
      return "bloco";
    }

    if (r === "apto") {
      if (s.bloco && s.pavimento) return "apto";
      if (s.bloco) return "pavimento";
      return "bloco";
    }
    if (r === "pavimento") {
      if (s.bloco) return "pavimento";
      return "bloco";
    }
    if (r === "bloco") return "bloco";

    if (s.bloco && s.pavimento) return "apto";
    if (s.bloco) return "pavimento";
    if (s.setor) return "bloco";
    return "bloco";
  }

  function readMatrixModeFromIframeDom() {
    try {
      const doc = frame.contentDocument;
      const active = doc && doc.querySelector(".matrix-mode-pill.active");
      if (!active) return "";
      const href = String(active.getAttribute("href") || "");
      const m = href.match(/matrix_mode=(bloco|pavimento|apto)/i);
      return m ? String(m[1]).toLowerCase() : "";
    } catch (e) {
      return "";
    }
  }

  function buildAxisMapFromMeta(meta, header) {
    const axisMap = {};
    const cols = meta && Array.isArray(meta.axis_cols_interpreted) ? meta.axis_cols_interpreted : [];
    const headers =
      meta && Array.isArray(meta.axis_headers_interpreted) ? meta.axis_headers_interpreted : [];
    const keys = ["setor", "bloco", "pavimento", "apto"];
    cols.forEach((col, idx) => {
      if (!Number.isInteger(col)) return;
      const label = String(headers[idx] || (header[col] || "")).toUpperCase();
      if (label.includes("SETOR") || label.includes("REGIAO")) axisMap.setor = col;
      else if (label.includes("BLOCO") || label.includes("LOCAL") || label.includes("TORRE")) axisMap.bloco = col;
      else if (label.includes("PAV") || label.includes("ANDAR") || label.includes("NIVEL")) axisMap.pavimento = col;
      else if (label.includes("APTO") || label.includes("UNIDADE")) axisMap.apto = col;
    });
    if (!Object.keys(axisMap).length && header.length) {
      axisMap.bloco = 0;
    }
    return axisMap;
  }

  function rowMatchesFilters(row, axisMap, filters) {
    if (!filters || !Object.keys(filters).length) return true;
    return Object.entries(filters).every(([key, value]) => {
      const idx = axisMap[key];
      if (!Number.isInteger(idx)) return true;
      return String(row[idx] || "").trim() === String(value || "").trim();
    });
  }

  function primaryAxisIndex(axisMap) {
    if (Number.isInteger(axisMap.pavimento)) return axisMap.pavimento;
    if (Number.isInteger(axisMap.apto)) return axisMap.apto;
    if (Number.isInteger(axisMap.bloco)) return axisMap.bloco;
    if (Number.isInteger(axisMap.setor)) return axisMap.setor;
    return 0;
  }

  function inferRowAxisKeyFromPage(pageKey) {
    const scope = parseScopeFromPageKey(pageKey);
    if (!pageKey || pageKey === currentPageKey()) {
      const domMode = readMatrixModeFromIframeDom();
      if (domMode) scope.requestedMode = domMode;
    }
    return resolveMatrixMode(scope);
  }

  function applyCellTextToLayoutRows(rows, axisMap, filters, rowLabel, colIndex, text, rowAxisKey) {
    if (!Array.isArray(rows) || !rowLabel || !Number.isInteger(colIndex)) return;
    const axisKey = rowAxisKey || inferRowAxisKeyFromPage();
    const axisIdx = Number.isInteger(axisMap[axisKey]) ? axisMap[axisKey] : primaryAxisIndex(axisMap);
    for (let ri = 1; ri < rows.length; ri += 1) {
      const row = rows[ri];
      if (!Array.isArray(row)) continue;
      if (!rowMatchesFilters(row, axisMap, filters)) continue;
      if (String(row[axisIdx] || "").trim() !== String(rowLabel).trim()) continue;
      while (row.length <= colIndex) row.push("");
      row[colIndex] = text;
    }
  }

  function isManualFlatLayout(meta, axisMap) {
    const axisCols =
      meta && Array.isArray(meta.axis_cols_interpreted) ? meta.axis_cols_interpreted : [];
    return axisCols.length <= 1 || Object.keys(axisMap).length <= 1;
  }

  /** Contexto hierárquico para operações estruturais (fonte: URL, não tbody). */
  function buildStructuralRowContext(pageKey) {
    const ctx = getMatrixEditContext(pageKey);
    const filters = parsePageFilters(pageKey);
    const level = inferRowAxisKeyFromPage(pageKey);
    return {
      setor: String(filters.setor || ctx.setor || "").trim(),
      bloco: String(filters.bloco || ctx.bloco || "").trim(),
      pavimento: String(filters.pavimento || ctx.pavimento || "").trim(),
      level,
    };
  }

  function parentFiltersForStructuralLevel(context) {
    const f = {};
    if (context.setor) f.setor = context.setor;
    if (context.level === "pavimento" || context.level === "apto") {
      if (context.bloco) f.bloco = context.bloco;
    }
    if (context.level === "apto" && context.pavimento) {
      f.pavimento = context.pavimento;
    }
    return f;
  }

  function newCanonicalLayoutRow(header, axisMap, context, label) {
    const row = new Array(header.length).fill("");
    ["setor", "bloco", "pavimento", "apto"].forEach((key) => {
      const idx = axisMap[key];
      const val = context[key];
      if (Number.isInteger(idx) && val) row[idx] = val;
    });
    const levelIdx = axisMap[context.level];
    if (Number.isInteger(levelIdx)) row[levelIdx] = String(label || "").trim();
    return row;
  }

  function layoutHasStructuralRow(rows, axisMap, context, label) {
    const levelIdx = axisMap[context.level];
    if (!Number.isInteger(levelIdx)) return false;
    const want = String(label || "").trim();
    if (!want) return false;
    const parentF = parentFiltersForStructuralLevel(context);
    for (let ri = 1; ri < rows.length; ri += 1) {
      const row = rows[ri];
      if (!Array.isArray(row)) continue;
      if (Object.keys(parentF).length && !rowMatchesFilters(row, axisMap, parentF)) continue;
      if (String(row[levelIdx] || "").trim() === want) return true;
    }
    return false;
  }

  function applyCreateRowToLayout(rows, axisMap, context, label) {
    const header = rows[0];
    if (!Array.isArray(header) || !header.length) return false;
    const title = String(label || "").trim();
    if (!title || layoutHasStructuralRow(rows, axisMap, context, title)) return false;
    rows.push(newCanonicalLayoutRow(header, axisMap, context, title));
    return true;
  }

  function applyDeleteRowToLayout(rows, axisMap, context, label) {
    const levelIdx = axisMap[context.level];
    if (!Number.isInteger(levelIdx)) return;
    const want = String(label || "").trim();
    if (!want) return;
    const parentF = parentFiltersForStructuralLevel(context);
    const remove = [];
    for (let ri = 1; ri < rows.length; ri += 1) {
      const row = rows[ri];
      if (!Array.isArray(row)) continue;
      if (context.level === "bloco") {
        if (String(row[levelIdx] || "").trim() === want) remove.push(ri);
        continue;
      }
      if (Object.keys(parentF).length && !rowMatchesFilters(row, axisMap, parentF)) continue;
      if (String(row[levelIdx] || "").trim() === want) remove.push(ri);
    }
    remove.sort((a, b) => b - a).forEach((ri) => rows.splice(ri, 1));
  }

  function applyMoveRowToLayout(rows, axisMap, context, label, fromOrder, toOrder) {
    const parentF = parentFiltersForStructuralLevel(context);
    const siblingIdxs = [];
    for (let ri = 1; ri < rows.length; ri += 1) {
      const row = rows[ri];
      if (!Array.isArray(row)) continue;
      if (Object.keys(parentF).length && !rowMatchesFilters(row, axisMap, parentF)) continue;
      siblingIdxs.push(ri);
    }
    if (siblingIdxs.length < 2) return;
    const fromPos = clampIndex(Number(fromOrder), 0, siblingIdxs.length - 1);
    const toPos = clampIndex(Number(toOrder), 0, siblingIdxs.length - 1);
    if (fromPos === toPos) return;
    const fromRi = siblingIdxs[fromPos];
    const [moved] = rows.splice(fromRi, 1);
    const remaining = siblingIdxs.filter((ri) => ri !== fromRi);
    const toRi = remaining[clampIndex(toPos, 0, remaining.length - 1)];
    rows.splice(toRi, 0, moved);
  }

  function applyCreateColumnToLayout(rows, op) {
    const header = rows[0];
    if (!Array.isArray(header) || header.length < 2) return;
    const totalIdx = header.length - 1;
    const insertAt = clampIndex(Number(op.index), 1, totalIdx);
    const title = String(op.label || "Nova coluna").trim() || "Nova coluna";
    header.splice(insertAt, 0, title);
    for (let ri = 1; ri < rows.length; ri += 1) {
      if (!Array.isArray(rows[ri])) continue;
      rows[ri].splice(insertAt, 0, "");
    }
  }

  function applyDeleteColumnToLayout(rows, op) {
    const header = rows[0];
    if (!Array.isArray(header) || header.length < 3) return;
    const idx = clampIndex(Number(op.index), 1, header.length - 2);
    header.splice(idx, 1);
    for (let ri = 1; ri < rows.length; ri += 1) {
      if (!Array.isArray(rows[ri])) continue;
      if (idx < rows[ri].length) rows[ri].splice(idx, 1);
    }
  }

  function applyMoveColumnToLayout(rows, op) {
    const header = rows[0];
    if (!Array.isArray(header) || header.length < 3) return;
    const from = clampIndex(Number(op.from), 1, header.length - 2);
    const to = clampIndex(Number(op.to), 1, header.length - 2);
    if (from === to) return;
    const moveCell = (arr) => {
      if (!Array.isArray(arr) || from >= arr.length) return;
      const [cell] = arr.splice(from, 1);
      arr.splice(to, 0, cell);
    };
    moveCell(header);
    for (let ri = 1; ri < rows.length; ri += 1) moveCell(rows[ri]);
  }

  function structuralOpDedupeKey(op) {
    if (!op || op.type !== "create_row") return "";
    const c = op.context || {};
    return ["create_row", c.level, c.setor, c.bloco, c.pavimento, op.label].join("|");
  }

  function normalizeLegacyStructuralOp(op, pageKey) {
    if (!op || typeof op !== "object") return null;
    const context = buildStructuralRowContext(pageKey);
    if (op.type === "insert_row") {
      return { type: "create_row", context, label: op.label, order: op.index };
    }
    if (op.type === "create_row" && op.context) return op;
    return null;
  }

  function gatherStructuralOpsForMerge(pages, axisMap) {
    const seen = new Set();
    const list = [];
    Object.entries(pages || {}).forEach(([pageKey, draft]) => {
      if (!draft || !canPersistStructuralLayoutOps(pageKey)) return;
      const push = (op) => {
        if (!op || typeof op !== "object") return;
        const key = structuralOpDedupeKey(op);
        if (key) {
          if (seen.has(key)) return;
          seen.add(key);
        }
        list.push(op);
      };
      (draft.structuralOps || []).forEach(push);
      (draft.ops || []).forEach((op) => {
        const normalized = normalizeLegacyStructuralOp(op, pageKey);
        if (normalized) push(normalized);
      });
      if (
        !(draft.structuralOps && draft.structuralOps.length) &&
        Array.isArray(draft.structuralExport) &&
        draft.structuralExport.length
      ) {
        const context = buildStructuralRowContext(pageKey);
        const levelIdx = axisMap[context.level];
        if (Number.isInteger(levelIdx)) {
          draft.structuralExport.forEach((row) => {
            if (!Array.isArray(row)) return;
            const label = String(row[levelIdx] || "").trim();
            if (label) push({ type: "create_row", context, label });
          });
        }
      }
    });
    return list;
  }

  function applyStructuralOpsToLayoutData(data, axisMap, structuralOps) {
    if (!data || !Array.isArray(data.rows) || !data.rows.length || !structuralOps.length) return;
    const rows = data.rows;
    const creates = structuralOps.filter((o) => o.type === "create_row");
    const deletes = structuralOps.filter((o) => o.type === "delete_row");
    const moves = structuralOps.filter((o) => o.type === "move_row");
    const colCreates = structuralOps.filter((o) => o.type === "create_column");
    const colDeletes = structuralOps.filter((o) => o.type === "delete_column");
    const colMoves = structuralOps.filter((o) => o.type === "move_column");

    poMapaDebug("applyStructuralOps", {
      creates: creates.length,
      deletes: deletes.length,
      rowsAntes: rows.length,
    });

    creates.forEach((op) => {
      const context = op.context || {};
      applyCreateRowToLayout(rows, axisMap, context, op.label);
    });
    deletes.forEach((op) => {
      applyDeleteRowToLayout(rows, axisMap, op.context || {}, op.label);
    });
    moves.forEach((op) => {
      applyMoveRowToLayout(rows, axisMap, op.context || {}, op.label, op.from, op.to);
    });
    colCreates.forEach((op) => applyCreateColumnToLayout(rows, op));
    colDeletes.forEach((op) => applyDeleteColumnToLayout(rows, op));
    colMoves.forEach((op) => applyMoveColumnToLayout(rows, op));

    poMapaDebug("applyStructuralOps depois", { rowsDepois: rows.length });
  }

  function pageDraftHasStructuralOps(pageDraft) {
    if (!pageDraft) return false;
    if (Array.isArray(pageDraft.structuralOps) && pageDraft.structuralOps.length) return true;
    return !!(Array.isArray(pageDraft.ops) && pageDraft.ops.length);
  }

  function pageDraftNeedsStructuralMerge(pageDraft) {
    return pageDraftHasStructuralOps(pageDraft);
  }

  function mergeAllDraftsIntoLayout(layout) {
    const next = layout && typeof layout === "object" ? layout : { sections: [] };
    const sections = Array.isArray(next.sections) ? next.sections : [];
    const pages = state.draft.pages || {};
    sections.forEach((section) => {
      const data = section && section.data;
      if (!data || !Array.isArray(data.rows) || !data.rows.length) return;
      const header = data.rows[0];
      const meta = data.importMeta && typeof data.importMeta === "object" ? data.importMeta : {};
      const axisMap = buildAxisMapFromMeta(meta, header);
      const rowsBefore = data.rows.length;

      Object.entries(pages).forEach(([pageKey, pageDraft]) => {
        const filters = parsePageFilters(pageKey);
        const texts = (pageDraft && pageDraft.text) || {};
        const cells = (pageDraft && pageDraft.cells) || {};
        const keys = new Set([...Object.keys(texts), ...Object.keys(cells)]);
        keys.forEach((key) => {
          const patch = cells[key] || {};
          const kind =
            patch.kind || (Number(patch.colIndex) === 0 ? "structural" : "percent");
          if (kind === "percent" && !isAptoUndManualEntryLayer(pageKey)) return;
          const colIndex = Number.isInteger(patch.colIndex) ? patch.colIndex : null;
          const rowLabel = patch.rowLabel != null ? String(patch.rowLabel).trim() : "";
          const text =
            texts[key] != null ? String(texts[key]) : patch.text != null ? String(patch.text) : "";
          if (!rowLabel || colIndex == null) return;
          const rowAxisKey = inferRowAxisKeyFromPage(pageKey);
          applyCellTextToLayoutRows(data.rows, axisMap, filters, rowLabel, colIndex, text, rowAxisKey);
        });
      });

      const structuralOps = gatherStructuralOpsForMerge(pages, axisMap);
      if (structuralOps.length) {
        applyStructuralOpsToLayoutData(data, axisMap, structuralOps);
      }

      poMapaDebug("merge layout seção", {
        rowsAntes: rowsBefore,
        rowsDepois: data.rows.length,
        structuralOps: structuralOps.length,
        pages: Object.keys(pages).length,
      });
    });
    return next;
  }

  async function saveDraftToServer() {
    if (!ctx.ambienteId || !ctx.endpoints || !ctx.endpoints.saveDraft) {
      saveDraftToStorage();
      return;
    }
    if (draftHasUnpersistedStructuralLayoutOps()) {
      const proceed = window.confirm(STRUCTURAL_OPS_SAVE_WARN_MSG);
      if (!proceed) {
        updateStatus(
          "Salvamento cancelado. Abra um bloco ou pavimento para gravar linhas/colunas no servidor.",
        );
        return;
      }
    }
    finishInlineEdit({ commit: true });
    updateStatus("Salvando no servidor...");
    try {
      const detRes = await fetch(ctx.endpoints.detalhe, {
        credentials: "same-origin",
        headers: { "X-Requested-With": "XMLHttpRequest" },
      });
      const detJson = await detRes.json();
      if (!detRes.ok || !detJson.success) {
        throw new Error((detJson && detJson.error) || "Falha ao carregar rascunho do ambiente.");
      }
      const draft = detJson.draft || detJson.versao || {};
      const layoutIn = JSON.parse(JSON.stringify(draft.layout || {}));
      poMapaDebug("save servidor início", {
        pageKey: currentPageKey(),
        contexto: getMatrixEditContext(),
        rowsLayout: (layoutIn.sections && layoutIn.sections[0] && layoutIn.sections[0].data && layoutIn.sections[0].data.rows || []).length,
      });
      const pagesSnapshot = JSON.parse(JSON.stringify(state.draft.pages || {}));
      const { axisMap: axisMapIn } = extractLayoutMatrixFromLayout(layoutIn);
      const structuralOpsSnapshot = gatherStructuralOpsForMerge(pagesSnapshot, axisMapIn);

      const layout = mergeAllDraftsIntoLayout(layoutIn);
      const { rows: rowsMerged } = extractLayoutMatrixFromLayout(layout);
      const missingInPayload = verifyCreateRowsInLayout(layout, structuralOpsSnapshot);
      poMapaDebug("save servidor layout merge", {
        rowsLayout: rowsMerged.length,
        structuralOps: structuralOpsSnapshot.length,
        missingInPayload: missingInPayload.map((o) => o.label),
        structuralOpsLista: structuralOpsSnapshot,
      });
      if (missingInPayload.length) {
        throw new Error(
          "As linhas criadas não foram aplicadas ao layout antes do envio. Recarregue a página e tente novamente.",
        );
      }
      const saveRes = await fetch(ctx.endpoints.saveDraft, {
        method: "POST",
        credentials: "same-origin",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": getCsrfToken(),
          "X-Requested-With": "XMLHttpRequest",
        },
        body: JSON.stringify({
          layout,
          metadados: draft.metadados || {},
        }),
      });
      const saveJson = await saveRes.json();
      poMapaDebug("save servidor resposta", { ok: saveRes.ok, success: saveJson.success, saveJson });
      if (!saveRes.ok || !saveJson.success) {
        throw new Error((saveJson && saveJson.error) || "Falha ao salvar no servidor.");
      }

      const verifyRes = await fetch(ctx.endpoints.detalhe, {
        credentials: "same-origin",
        headers: { "X-Requested-With": "XMLHttpRequest" },
      });
      const verifyJson = await verifyRes.json();
      const savedLayout =
        verifyJson && verifyJson.success
          ? (verifyJson.draft || verifyJson.versao || {}).layout || {}
          : {};
      const missingAfterSave = verifyCreateRowsInLayout(savedLayout, structuralOpsSnapshot);
      poMapaDebug("save servidor verificação", {
        ok: verifyRes.ok,
        rowsPersistidas: extractLayoutMatrixFromLayout(savedLayout).rows.length,
        missingAfterSave: missingAfterSave.map((o) => o.label),
      });
      if (missingAfterSave.length) {
        throw new Error(
          "O servidor não confirmou as linhas criadas no layout. O rascunho local foi mantido.",
        );
      }

      const keepEditEnabled = state.enabled;
      state.dirty = false;
      state.draft = { pages: {} };
      try {
        window.localStorage.removeItem(storageKey);
      } catch (e) {
        void e;
      }
      updateStatus("Mapa salvo no servidor.");
      state.restoreEditOnNextLoad = keepEditEnabled;
      frame.contentWindow.location.reload();
    } catch (err) {
      updateStatus(err && err.message ? err.message : "Erro ao salvar no servidor.");
    }
  }

  function saveDraftToStorage() {
    try {
      window.localStorage.setItem(storageKey, JSON.stringify(state.draft));
      state.dirty = false;
      updateStatus("Rascunho salvo localmente.");
    } catch (e) {
      updateStatus("Falha ao salvar rascunho local.");
    }
  }

  function currentPageKey() {
    try {
      const u = new URL(String(frame.contentWindow.location.href || ""));
      return `${u.pathname}${u.search}`;
    } catch (e) {
      return "default";
    }
  }

  function ensurePageDraft(pageKey) {
    if (!state.draft.pages || typeof state.draft.pages !== "object") state.draft.pages = {};
    if (!state.draft.pages[pageKey]) {
      state.draft.pages[pageKey] = { text: {}, color: {}, ops: [], structuralOps: [] };
    }
    if (!Array.isArray(state.draft.pages[pageKey].ops)) state.draft.pages[pageKey].ops = [];
    if (!Array.isArray(state.draft.pages[pageKey].structuralOps)) {
      state.draft.pages[pageKey].structuralOps = [];
    }
    return state.draft.pages[pageKey];
  }

  function textNodeForCell(cell) {
    const link = cell.querySelector("a");
    if (link) return link;
    return cell;
  }

  function escapeSelectorValue(value) {
    const raw = String(value || "");
    if (typeof CSS !== "undefined" && CSS && typeof CSS.escape === "function") {
      return CSS.escape(raw);
    }
    return raw.replace(/\\/g, "\\\\").replace(/"/g, '\\"');
  }

  function resolveEventElement(rawTarget) {
    if (!rawTarget) return null;
    if (rawTarget.nodeType === Node.TEXT_NODE) {
      return rawTarget.parentElement || null;
    }
    if (rawTarget.nodeType === Node.ELEMENT_NODE) {
      return rawTarget;
    }
    return null;
  }

  function placeCaretAtEnd(node) {
    try {
      const range = document.createRange();
      range.selectNodeContents(node);
      range.collapse(false);
      const sel = frame.contentWindow.getSelection();
      if (!sel) return;
      sel.removeAllRanges();
      sel.addRange(range);
    } catch (e) {
      void e;
    }
  }

  function cellCoordsFromKey(cell) {
    if (!cell) return null;
    const key = String(cell.getAttribute("data-po-edit-key") || "");
    const m = key.match(/^r(\d+)c(\d+)$/);
    if (!m) return null;
    return { r: Number(m[1]), c: Number(m[2]) };
  }

  const EDIT_PERCENT_BLOCKED_MSG =
    "Edição de percentuais permitida apenas na camada de apartamentos/unidades. Abra um pavimento para editar as unidades.";

  const STRUCTURAL_LAYOUT_OPS_BLOCKED_MSG =
    "Não é possível alterar a estrutura de linhas/colunas nesta camada. Abra a matriz na raiz (blocos), dentro de um bloco (pavimentos) ou de um pavimento (unidades).";

  const STRUCTURAL_OPS_SAVE_WARN_MSG =
    "Há alterações estruturais de linhas/colunas em telas onde o cadastro não pode ser gravado. Elas não serão enviadas ao servidor. Deseja continuar?";

  function showBlockedPercentEditMessage() {
    updateStatus(EDIT_PERCENT_BLOCKED_MSG);
  }

  function poMapaDebug(label, payload) {
    if (!window.PO_MAPA_EDIT_DEBUG) return;
    try {
      console.log("[po-mapa-edit]", label, payload);
    } catch (e) {
      void e;
    }
  }

  /**
   * Operações de layout (inserir/mover/apagar linha ou coluna).
   * Raiz (modo bloco): novo bloco. Com bloco na URL: pavimentos. Com pavimento: aptos.
   */
  function canPersistStructuralLayoutOps(pageKey) {
    const key = pageKey || currentPageKey();
    const filters = parsePageFilters(key);
    const ctx = getMatrixEditContext(key);
    if (String(filters.bloco || "").trim() || String(filters.pavimento || "").trim()) return true;
    if (ctx.mode === "bloco") return true;
    return false;
  }

  function showStructuralLayoutOpsBlockedMessage() {
    updateStatus(STRUCTURAL_LAYOUT_OPS_BLOCKED_MSG);
  }

  function guardStructuralLayoutOp(cfg) {
    const register = !cfg || cfg.registerOp !== false;
    if (!register) return true;
    if (canPersistStructuralLayoutOps()) return true;
    showStructuralLayoutOpsBlockedMessage();
    return false;
  }

  function draftHasUnpersistedStructuralLayoutOps() {
    const pages = state.draft.pages || {};
    return Object.entries(pages).some(([pageKey, pageDraft]) => {
      if (canPersistStructuralLayoutOps(pageKey)) return false;
      return pageDraftHasStructuralOps(pageDraft);
    });
  }

  /** Contexto de camada do iframe (URL + pill ativa); espelha recorte do mapa clássico. */
  function getMatrixEditContext(pageKey) {
    const key = pageKey || currentPageKey();
    const scope = parseScopeFromPageKey(key);
    if (!pageKey || pageKey === currentPageKey()) {
      const domMode = readMatrixModeFromIframeDom();
      if (domMode) scope.requestedMode = domMode;
    }
    const filters = parsePageFilters(key);
    return {
      mode: resolveMatrixMode(scope),
      setor: scope.setor,
      bloco: filters.bloco || scope.bloco,
      pavimento: filters.pavimento || scope.pavimento,
      apto: filters.apto || scope.apto,
      isAreaComum: isSetorAreaComum(scope.setor),
    };
  }

  /** Camada APTO/UND (habitação): lançamento manual de %; demais camadas são consolidadas. */
  function isAptoUndManualEntryLayer(pageKey) {
    const ctx = getMatrixEditContext(pageKey);
    if (ctx.isAreaComum) return false;
    if (ctx.mode !== "apto") return false;
    if (!String(ctx.bloco || "").trim()) return false;
    if (!String(ctx.pavimento || "").trim()) return false;
    return true;
  }

  function isPercentEligibleCell(cell) {
    if (!cell || cell.tagName !== "TD") return false;
    if (cell.classList.contains("row-name") || cell.classList.contains("sticky-left")) return false;
    const coords = cellCoordsFromKey(cell);
    if (!coords) return false;
    return coords.c > 0;
  }

  /** TD de percentual no tbody (exclui totais, coluna Total e cabeçalho). */
  function isMatrixPercentDataCell(cell) {
    if (!isPercentEligibleCell(cell)) return false;
    if (cell.classList.contains("total-col")) return false;
    const tr = cell.closest("tr");
    if (!tr || tr.classList.contains("totals-row")) return false;
    if (!tr.closest("tbody")) return false;
    const table = cell.closest(".matrix-table");
    if (!table) return false;
    const headerRow = table.querySelector("tr");
    const coords = cellCoordsFromKey(cell);
    if (!headerRow || !coords) return false;
    if (coords.c >= headerRow.children.length - 1) return false;
    return true;
  }

  /**
   * Lançamento manual de percentual — somente camada APTO/UND (habitação).
   * Não confundir com edição estrutural do escopo (nome/ordem de linha e coluna).
   */
  function canEditPercentCell(cell, options) {
    const cfg = options && typeof options === "object" ? options : {};
    if (!state.enabled) return false;
    if (!isMatrixPercentDataCell(cell)) return false;
    if (!isAptoUndManualEntryLayer()) {
      if (!cfg.silent) showBlockedPercentEditMessage();
      return false;
    }
    return true;
  }

  /** Nome de linha/coluna e rótulos do escopo — qualquer camada, inclusive Área Comum. */
  function isMatrixStructuralCell(cell) {
    if (!cell || !state.enabled) return false;
    const table = cell.closest(".matrix-table");
    if (!table) return false;
    if (cell.tagName === "TH") {
      const thead = cell.closest("thead");
      if (!thead) return false;
      if (cell.classList.contains("sticky-left")) return false;
      return true;
    }
    if (cell.tagName === "TD") {
      if (!cell.classList.contains("row-name") && !cell.classList.contains("sticky-left")) return false;
      const tr = cell.closest("tr");
      if (!tr || tr.classList.contains("totals-row")) return false;
      return !!tr.closest("tbody");
    }
    return false;
  }

  function canEditStructuralCell(cell) {
    return state.enabled && isMatrixStructuralCell(cell);
  }

  function patchKindForCell(cell) {
    if (canEditPercentCell(cell, { silent: true })) return "percent";
    if (canEditStructuralCell(cell)) return "structural";
    return "";
  }

  function refreshToolbarEditState() {
    const cell = state.selectedCell;
    const canPercent = cell && canEditPercentCell(cell, { silent: true });
    const canStructural = cell && canEditStructuralCell(cell);
    const canText = state.enabled && (canPercent || canStructural);
    if (inpText) inpText.disabled = !canText;
    if (btnApplyText) btnApplyText.disabled = !canText;
    if (inpColor) inpColor.disabled = !(state.enabled && canPercent);
    if (btnApplyColor) btnApplyColor.disabled = !(state.enabled && canPercent);
  }

  function normalizeCellText(cell, rawValue) {
    const value = String(rawValue || "").trim();
    if (!value) return "";
    if (!isPercentEligibleCell(cell)) return value;
    if (value.includes("%")) return value;
    if (/^-?\d+(?:[.,]\d+)?$/.test(value)) {
      return `${value}%`;
    }
    return value;
  }

  function ensureEditModeIframeGuards() {
    const doc = frame.contentDocument;
    if (!doc) return;
    const styleId = "po-mapa-edit-guards-style";
    if (!doc.getElementById(styleId)) {
      const style = doc.createElement("style");
      style.id = styleId;
      style.textContent = `
        .po-map-edit-enabled .matrix-table a:not(.row-link) {
          pointer-events: none !important;
          cursor: default !important;
          text-decoration: none !important;
        }
        .po-map-edit-enabled .matrix-table a.row-link {
          pointer-events: auto !important;
          cursor: pointer !important;
          text-decoration: underline !important;
        }
        .po-map-edit-enabled .po-mapa-row-name-wrap {
          display: flex;
          align-items: center;
          gap: 6px;
          min-width: 0;
        }
        .po-map-edit-enabled .po-mapa-row-name-wrap > :not(.po-mapa-dnd-handle) {
          flex: 1 1 auto;
          min-width: 0;
        }
        .po-map-edit-enabled .po-mapa-dnd-handle {
          flex: 0 0 auto;
          display: inline-flex;
          align-items: center;
          justify-content: center;
          width: 18px;
          height: 22px;
          margin: 0;
          padding: 0;
          border: 1px solid #cbd5e1;
          border-radius: 5px;
          background: linear-gradient(180deg, #ffffff 0%, #f1f5f9 100%);
          color: #64748b;
          font-size: 0.72rem;
          line-height: 1;
          cursor: grab;
          user-select: none;
          touch-action: none;
          box-shadow: 0 1px 2px rgba(15, 23, 42, 0.06);
          overflow: hidden;
        }
        .po-map-edit-enabled .po-mapa-dnd-handle__icon {
          pointer-events: none;
          font-size: 0.72rem;
          line-height: 1;
        }
        .po-map-edit-enabled .po-mapa-dnd-handle:hover {
          color: #2563eb;
          border-color: #93c5fd;
          background: #eff6ff;
        }
        .po-map-edit-enabled .po-mapa-dnd-handle:active,
        .po-map-edit-enabled .po-mapa-dnd-handle.is-dragging {
          cursor: grabbing;
          color: #1d4ed8;
          border-color: #2563eb;
          background: #dbeafe;
        }
        .po-map-edit-enabled th.vertical .po-mapa-dnd-handle {
          display: inline-flex;
          vertical-align: middle;
          margin-right: 3px;
        }
        .po-map-edit-enabled tr.po-mapa-dnd-dragging > td,
        .po-map-edit-enabled tr.po-mapa-dnd-dragging > th {
          opacity: 0.62;
          cursor: grabbing !important;
        }
        .po-map-edit-enabled th.po-mapa-dnd-dragging {
          opacity: 0.62;
          cursor: grabbing !important;
        }
        .po-map-edit-enabled tr.po-mapa-dnd-row-slot > td,
        .po-map-edit-enabled tr.po-mapa-dnd-row-slot > th {
          box-shadow: inset 0 -3px 0 0 #2563eb;
        }
        .po-map-edit-enabled thead th.po-mapa-dnd-col-slot:not(.vertical) {
          box-shadow: inset -3px 0 0 0 #2563eb;
        }
        /* Só no cabeçalho da coluna; rotate(180deg) inverte o lado do shadow */
        .po-map-edit-enabled thead th.vertical.po-mapa-dnd-col-slot {
          box-shadow: inset 3px 0 0 0 #2563eb;
        }
      `;
      (doc.head || doc.documentElement).appendChild(style);
    }
    if (doc.body) {
      doc.body.classList.toggle("po-map-edit-enabled", state.enabled);
    }
  }

  function finishInlineEdit(options) {
    const cfg = options && typeof options === "object" ? options : {};
    const commit = cfg.commit !== false;
    const inline = state.inline;
    if (!inline || !inline.node || !inline.cell) return;
    const page = ensurePageDraft(currentPageKey());
    const nextText = normalizeCellText(inline.cell, inline.node.textContent);
    const hasChanged = nextText !== inline.originalText;
    if (commit && inline.key) {
      if (!patchKindForCell(inline.cell)) {
        inline.node.textContent = inline.originalText;
      } else {
        inline.node.textContent = nextText;
        page.text[inline.key] = nextText;
        rememberCellPatch(inline.cell, inline.key, nextText);
        if (hasChanged) markDirty();
      }
      if (inpText && state.selectedCell === inline.cell) {
        inpText.value = nextText;
      }
    } else {
      inline.node.textContent = inline.originalText;
    }
    if (inline.originalHref) {
      inline.node.setAttribute("href", inline.originalHref);
    }
    inline.node.removeAttribute("data-po-inline-edit");
    inline.node.removeAttribute("contenteditable");
    inline.node.removeAttribute("spellcheck");
    inline.cell.classList.remove("po-inline-editing");
    inline.cell.style.boxShadow = inline.originalBoxShadow || "";
    state.inline = {
      cell: null,
      node: null,
      key: "",
      originalText: "",
      originalHref: null,
      originalBoxShadow: "",
    };
    refreshMoveButtons();
  }

  function startInlineEdit(cell) {
    if (!state.enabled || !cell) return false;
    const canPercent = canEditPercentCell(cell, { silent: true });
    const canStructural = canEditStructuralCell(cell);
    if (!canPercent && !canStructural) {
      if (isMatrixPercentDataCell(cell)) showBlockedPercentEditMessage();
      return false;
    }
    setSelectedCell(cell);
    finishInlineEdit({ commit: true });
    const node = textNodeForCell(cell);
    if (!node) return false;
    let originalHref = null;
    if (node.tagName === "A") {
      originalHref = node.getAttribute("href");
      node.removeAttribute("href");
    }
    state.inline = {
      cell,
      node,
      key: String(cell.getAttribute("data-po-edit-key") || ""),
      originalText: String(node.textContent || "").trim(),
      originalHref,
      originalBoxShadow: String(cell.style.boxShadow || ""),
    };
    node.setAttribute("contenteditable", "true");
    node.setAttribute("spellcheck", "false");
    node.setAttribute("data-po-inline-edit", "1");
    cell.classList.add("po-inline-editing");
    cell.style.boxShadow = "inset 0 0 0 2px #2563eb";
    node.focus();
    placeCaretAtEnd(node);
    return true;
  }

  function setSelectedCell(cell) {
    if (state.inline.cell && state.inline.cell !== cell) {
      finishInlineEdit({ commit: true });
    }
    if (state.selectedCell && state.selectedCell !== cell) {
      state.selectedCell.style.outline = "";
      state.selectedCell.style.outlineOffset = "";
    }
    state.selectedCell = cell;
    state.selectedKey = String(cell.getAttribute("data-po-edit-key") || "");
    if (state.selectedCell) {
      state.selectedCell.style.outline = "2px solid #1d4ed8";
      state.selectedCell.style.outlineOffset = "-2px";
      const node = textNodeForCell(state.selectedCell);
      if (inpText) inpText.value = String(node.textContent || "").trim();
    }
    refreshMoveButtons();
    refreshToolbarEditState();
  }

  function applyDraftToDoc() {
    const doc = frame.contentDocument;
    if (!doc) return;
    const pageKey = currentPageKey();
    const page = ensurePageDraft(pageKey);
    poMapaDebug("applyDraftToDoc", {
      pageKey,
      ops: (page.ops || []).length,
      structuralOps: (page.structuralOps || []).length,
      editEnabled: state.enabled,
    });
    (page.ops || []).forEach((op) => {
      if (!op || typeof op !== "object") return;
      if (op.type === "move_col") applyMoveColumn(op.from, op.to, { registerOp: false, keepSelection: false });
      else if (op.type === "move_row") applyMoveRow(op.from, op.to, { registerOp: false, keepSelection: false });
      else if (op.type === "insert_col") applyInsertColumn(op.index, op.label, { registerOp: false, keepSelection: false });
      else if (op.type === "insert_row") applyInsertRow(op.index, op.label, { registerOp: false, keepSelection: false });
      else if (op.type === "delete_col") applyDeleteColumn(op.index, { registerOp: false, keepSelection: false });
      else if (op.type === "delete_row") applyDeleteRow(op.index, { registerOp: false, keepSelection: false });
    });
    mapEditableCells();
    Object.entries(page.text || {}).forEach(([key, value]) => {
      const cell = doc.querySelector(`[data-po-edit-key="${escapeSelectorValue(key)}"]`);
      if (!cell) return;
      if (!canEditPercentCell(cell, { silent: true }) && !canEditStructuralCell(cell)) return;
      textNodeForCell(cell).textContent = String(value || "");
    });
    Object.entries(page.color || {}).forEach(([key, value]) => {
      const cell = doc.querySelector(`[data-po-edit-key="${escapeSelectorValue(key)}"]`);
      if (!cell || !canEditPercentCell(cell, { silent: true })) return;
      cell.style.backgroundColor = String(value || "");
      cell.style.color = "#ffffff";
    });
  }

  function mapEditableCells() {
    const doc = frame.contentDocument;
    if (!doc) return;
    const table = doc.querySelector(".matrix-table");
    if (!table) return;
    const rows = table.querySelectorAll("tr");
    rows.forEach((tr, rIdx) => {
      const cells = tr.querySelectorAll("th,td");
      cells.forEach((cell, cIdx) => {
        cell.setAttribute("data-po-edit-key", `r${rIdx}c${cIdx}`);
      });
    });
    cleanupRowAddControls();
    enhanceMatrixDragHandles();
    bindMatrixDragReorder();
  }

  function tableRef() {
    const doc = frame.contentDocument;
    if (!doc) return null;
    return doc.querySelector(".matrix-table");
  }

  function clampIndex(idx, min, max) {
    return Math.max(min, Math.min(max, idx));
  }

  function selectedCoords() {
    if (!state.selectedCell) return null;
    const key = String(state.selectedCell.getAttribute("data-po-edit-key") || "");
    const m = key.match(/^r(\d+)c(\d+)$/);
    if (!m) return null;
    return { r: Number(m[1]), c: Number(m[2]) };
  }

  function canMoveSelectedColumn() {
    const table = tableRef();
    const sc = selectedCoords();
    if (!table || !sc) return false;
    const row = table.querySelector("tr");
    if (!row) return false;
    const colCount = row.children.length;
    // Coluna 0 (rótulo) e última (Total) permanecem fixas.
    return colCount >= 3 && sc.c > 0 && sc.c < colCount - 1;
  }

  function canMoveSelectedRow() {
    if (!state.selectedCell) return false;
    const tr = state.selectedCell.closest("tr");
    if (!tr || isNonDataMatrixRow(tr)) return false;
    const tbody = tableRef()?.querySelector("tbody");
    return tbody ? listMatrixTbodyRows(tbody).includes(tr) : false;
  }

  function selectedBodyRowIndex() {
    if (!state.selectedCell) return -1;
    const tr = state.selectedCell.closest("tr");
    if (!tr) return -1;
    const tbody = tableRef()?.querySelector("tbody");
    if (!tbody) return -1;
    return listMatrixTbodyRows(tbody).indexOf(tr);
  }

  function refreshMoveButtons() {
    const enabled = state.enabled && !!state.selectedCell;
    const layoutOps = state.enabled && canPersistStructuralLayoutOps();
    const canCol = enabled && layoutOps && canMoveSelectedColumn();
    const canRow = enabled && layoutOps && canMoveSelectedRow();
    if (btnMoveColLeft) btnMoveColLeft.disabled = !canCol;
    if (btnMoveColRight) btnMoveColRight.disabled = !canCol;
    if (btnMoveRowUp) btnMoveRowUp.disabled = !canRow;
    if (btnMoveRowDown) btnMoveRowDown.disabled = !canRow;
    if (btnAddCol) btnAddCol.disabled = !layoutOps;
    if (btnAddRow) btnAddRow.disabled = !layoutOps;
    if (btnDeleteCol) btnDeleteCol.disabled = !canCol;
    if (btnDeleteRow) btnDeleteRow.disabled = !canRow;
  }

  function movableColumnBounds() {
    const table = tableRef();
    if (!table) return null;
    const row = table.querySelector("tr");
    if (!row) return null;
    const colCount = row.children.length;
    if (colCount < 3) return null;
    return { min: 1, max: colCount - 2 };
  }

  function matrixBodyRows() {
    const tbody = tableRef()?.querySelector("tbody");
    return listMatrixTbodyRows(tbody);
  }

  function willApplyMatrixMove(axis, from, dropTarget) {
    if (!Number.isInteger(from) || !Number.isInteger(dropTarget) || from === dropTarget) return false;
    if (axis === "col") {
      const bounds = movableColumnBounds();
      if (!bounds) return false;
      return dropTarget >= bounds.min && dropTarget <= bounds.max;
    }
    const movable = matrixBodyRows();
    return dropTarget >= 0 && dropTarget < movable.length;
  }

  function applyMoveColumn(fromIdx, toIdx, options) {
    const cfg = options && typeof options === "object" ? options : {};
    if (!guardStructuralLayoutOp(cfg)) return false;
    const table = tableRef();
    if (!table) return false;
    const bounds = movableColumnBounds();
    if (!bounds) return false;
    const rows = Array.from(table.querySelectorAll("tr"));
    if (!rows.length) return false;
    const from = clampIndex(Number(fromIdx), bounds.min, bounds.max);
    const to = clampIndex(Number(toIdx), bounds.min, bounds.max);
    if (!Number.isFinite(from) || !Number.isFinite(to) || from === to) return false;
    rows.forEach((row) => {
      const cells = Array.from(row.children);
      const src = cells[from];
      const tgt = cells[to];
      if (!src || !tgt) return;
      if (from < to) row.insertBefore(src, tgt.nextSibling);
      else row.insertBefore(src, tgt);
    });
    mapEditableCells();
    if (cfg.keepSelection) {
      const sc = selectedCoords();
      if (sc) {
        const selected = table.querySelector(`[data-po-edit-key="r${sc.r}c${to}"]`);
        if (selected) setSelectedCell(selected);
      }
    }
    if (cfg.registerOp !== false) {
      ensurePageDraft(currentPageKey()).ops.push({ type: "move_col", from, to });
      afterStructuralLayoutOpCommitted({ type: "move_column", from, to });
    }
    refreshMoveButtons();
    return true;
  }

  function applyMoveRow(fromBodyIdx, toBodyIdx, options) {
    const cfg = options && typeof options === "object" ? options : {};
    if (!guardStructuralLayoutOp(cfg)) return false;
    const table = tableRef();
    if (!table) return false;
    const tbody = table.querySelector("tbody");
    if (!tbody) return false;
    const movable = listMatrixTbodyRows(tbody);
    if (movable.length < 2) return false;
    const max = movable.length - 1;
    const from = clampIndex(Number(fromBodyIdx), 0, max);
    const to = clampIndex(Number(toBodyIdx), 0, max);
    if (!Number.isFinite(from) || !Number.isFinite(to) || from === to) return false;
    const src = movable[from];
    const tgt = movable[to];
    if (!src || !tgt) return false;
    if (from < to) tbody.insertBefore(src, tgt.nextSibling);
    else tbody.insertBefore(src, tgt);
    mapEditableCells();
    if (cfg.keepSelection && src) {
      const nameCell = src.querySelector(".row-name, .sticky-left") || src.querySelector("td,th");
      if (nameCell) setSelectedCell(nameCell);
    }
    if (cfg.registerOp !== false) {
      const nameCell = src.querySelector(".row-name, .sticky-left");
      const rowLabel = nameCell ? rowDisplayLabelFromNameCell(nameCell) : "";
      ensurePageDraft(currentPageKey()).ops.push({ type: "move_row", from, to });
      afterStructuralLayoutOpCommitted({
        type: "move_row",
        context: buildStructuralRowContext(currentPageKey()),
        label: rowLabel,
        from,
        to,
      });
    }
    refreshMoveButtons();
    return true;
  }

  function ensureRowNameWrap(doc, nameCell) {
    let wrap = nameCell.querySelector(".po-mapa-row-name-wrap");
    if (wrap) return wrap;
    wrap = doc.createElement("div");
    wrap.className = "po-mapa-row-name-wrap";
    while (nameCell.firstChild) {
      wrap.appendChild(nameCell.firstChild);
    }
    nameCell.appendChild(wrap);
    return wrap;
  }

  function ensureDragHandle(doc, parent, label) {
    parent.querySelectorAll(":scope > .po-mapa-dnd-handle").forEach((el, idx) => {
      if (idx > 0) el.remove();
    });
    let handle = parent.querySelector(":scope > .po-mapa-dnd-handle");
    if (!handle) {
      handle = doc.createElement("button");
      handle.type = "button";
      handle.className = "po-mapa-dnd-handle";
      handle.title = label;
      handle.setAttribute("aria-label", label);
      const icon = doc.createElement("i");
      icon.className = "bi bi-grip-vertical po-mapa-dnd-handle__icon";
      icon.setAttribute("aria-hidden", "true");
      handle.appendChild(icon);
      parent.insertBefore(handle, parent.firstChild);
    } else if (!handle.querySelector(".po-mapa-dnd-handle__icon")) {
      handle.textContent = "";
      const icon = doc.createElement("i");
      icon.className = "bi bi-grip-vertical po-mapa-dnd-handle__icon";
      icon.setAttribute("aria-hidden", "true");
      handle.appendChild(icon);
    } else if (handle.textContent.trim() && handle.textContent.trim() !== "") {
      const icon = handle.querySelector(".po-mapa-dnd-handle__icon");
      handle.textContent = "";
      if (icon) handle.appendChild(icon);
    }
    handle.hidden = !state.enabled;
    return handle;
  }

  function sanitizeRowNameCellContent(nameCell) {
    if (!nameCell) return;
    nameCell.querySelectorAll(":scope > .po-mapa-dnd-handle").forEach((el) => el.remove());
    const wrap = nameCell.querySelector(".po-mapa-row-name-wrap");
    if (!wrap) return;
    wrap.querySelectorAll(".po-mapa-dnd-handle").forEach((el, idx) => {
      if (idx > 0) el.remove();
    });
    wrap.querySelectorAll(".row-name-txt, a.row-link").forEach((el) => {
      const next = sanitizeRowDisplayLabel(el.textContent);
      if (next) el.textContent = next;
    });
    Array.from(wrap.childNodes).forEach((node) => {
      if (node.nodeType !== Node.TEXT_NODE) return;
      const next = sanitizeRowDisplayLabel(node.textContent);
      if (!next) wrap.removeChild(node);
      else node.textContent = next;
    });
  }

  function clearMatrixDnDHighlights() {
    const doc = frame.contentDocument;
    if (!doc) return;
    doc.querySelectorAll(".po-mapa-dnd-dragging").forEach((el) => el.classList.remove("po-mapa-dnd-dragging"));
    doc.querySelectorAll(".po-mapa-dnd-row-slot").forEach((el) => el.classList.remove("po-mapa-dnd-row-slot"));
    doc.querySelectorAll(".po-mapa-dnd-col-slot").forEach((el) => el.classList.remove("po-mapa-dnd-col-slot"));
    doc.querySelectorAll(".po-mapa-dnd-handle.is-dragging").forEach((el) => el.classList.remove("is-dragging"));
  }

  function enhanceMatrixDragHandles() {
    const doc = frame.contentDocument;
    const table = doc && doc.querySelector(".matrix-table");
    if (!doc || !table) return;

    doc.querySelectorAll(".po-mapa-dnd-handle").forEach((el) => {
      el.hidden = !state.enabled;
    });
    if (!state.enabled) return;

    const headerRow = table.querySelector("thead tr");
    if (headerRow) {
      const colCount = headerRow.children.length;
      Array.from(headerRow.children).forEach((cell, colIndex) => {
        if (colIndex <= 0 || colIndex >= colCount - 1) return;
        if (!cell.classList.contains("vertical")) return;
        ensureDragHandle(doc, cell, "Arrastar para mover coluna");
        cell.dataset.poDndCol = String(colIndex);
      });
    }

    matrixBodyRows().forEach((tr, bodyIndex) => {
      const nameCell = tr.querySelector(".row-name, .sticky-left");
      if (!nameCell) return;
      const wrap = ensureRowNameWrap(doc, nameCell);
      sanitizeRowNameCellContent(nameCell);
      ensureDragHandle(doc, wrap, "Arrastar para mover linha");
      tr.dataset.poDndRow = String(bodyIndex);
    });
  }

  function cleanupMatrixDnDListeners() {
    const doc = frame.contentDocument;
    const handle = matrixDnD.handleEl;
    const pid = matrixDnD.pointerId;
    if (handle && matrixDnD.onPointerMove) {
      handle.removeEventListener("pointermove", matrixDnD.onPointerMove);
      handle.removeEventListener("pointerup", matrixDnD.onPointerEnd);
      handle.removeEventListener("pointercancel", matrixDnD.onPointerEnd);
      handle.removeEventListener("lostpointercapture", matrixDnD.onPointerEnd);
    }
    if (doc && matrixDnD.onPointerEnd) {
      doc.removeEventListener("pointerup", matrixDnD.onPointerEnd, true);
      doc.removeEventListener("pointercancel", matrixDnD.onPointerEnd, true);
    }
    if (matrixDnD.onPointerEnd) {
      window.removeEventListener("pointerup", matrixDnD.onPointerEnd, true);
      window.removeEventListener("pointercancel", matrixDnD.onPointerEnd, true);
      window.removeEventListener("blur", matrixDnD.onPointerEnd);
    }
    if (handle && pid != null) {
      try {
        if (handle.hasPointerCapture && handle.hasPointerCapture(pid)) {
          handle.releasePointerCapture(pid);
        }
      } catch (e) {
        void e;
      }
    }
    matrixDnD.active = false;
    matrixDnD.axis = null;
    matrixDnD.from = null;
    matrixDnD.dropTarget = null;
    matrixDnD.dragEl = null;
    matrixDnD.handleEl = null;
    matrixDnD.pointerId = null;
    matrixDnD.onPointerMove = null;
    matrixDnD.onPointerEnd = null;
    clearMatrixDnDHighlights();
  }

  /** Coluna cujo campo inteiro (faixa vertical da tabela × largura do cabeçalho) contém o ponteiro. */
  function colTargetIndexFromPointer(clientX, clientY) {
    const bounds = movableColumnBounds();
    const table = tableRef();
    if (!bounds || !table) return null;
    const headerRow = table.querySelector("thead tr");
    if (!headerRow) return null;
    const tableRect = table.getBoundingClientRect();
    if (clientY < tableRect.top || clientY > tableRect.bottom) return null;

    for (let c = bounds.min; c <= bounds.max; c += 1) {
      const cell = headerRow.children[c];
      if (!cell) continue;
      const rect = cell.getBoundingClientRect();
      if (clientX >= rect.left && clientX <= rect.right) return c;
    }
    return null;
  }

  /** Linha cujo campo inteiro (altura da linha) contém clientY. */
  function rowTargetIndexFromY(clientY) {
    const rows = matrixBodyRows();
    for (let i = 0; i < rows.length; i += 1) {
      const rect = rows[i].getBoundingClientRect();
      if (clientY >= rect.top && clientY <= rect.bottom) return i;
    }
    return null;
  }

  function updateMatrixDnDHighlights() {
    const doc = frame.contentDocument;
    if (!doc || !matrixDnD.active) return;
    clearMatrixDnDHighlights();
    if (matrixDnD.dragEl) matrixDnD.dragEl.classList.add("po-mapa-dnd-dragging");
    if (matrixDnD.handleEl) matrixDnD.handleEl.classList.add("is-dragging");

    const slot = matrixDnD.dropTarget;
    if (!Number.isInteger(slot) || slot === matrixDnD.from) return;

    if (matrixDnD.axis === "row") {
      const rows = matrixBodyRows();
      const target = rows[slot];
      if (target && target !== matrixDnD.dragEl) target.classList.add("po-mapa-dnd-row-slot");
      return;
    }

    if (matrixDnD.axis === "col") {
      const headerRow = tableRef()?.querySelector("thead tr");
      if (!headerRow) return;
      const cell = headerRow.children[slot];
      if (cell) cell.classList.add("po-mapa-dnd-col-slot");
    }
  }

  function onMatrixDnDPointerMove(event) {
    if (!matrixDnD.active || event.pointerId !== matrixDnD.pointerId) return;
    event.preventDefault();
    if (matrixDnD.axis === "col") {
      const t = colTargetIndexFromPointer(event.clientX, event.clientY);
      if (t != null) matrixDnD.dropTarget = t;
    } else {
      const t = rowTargetIndexFromY(event.clientY);
      if (t != null) matrixDnD.dropTarget = t;
    }
    updateMatrixDnDHighlights();
  }

  function endMatrixDnD(commit) {
    const ctx = {
      axis: matrixDnD.axis,
      from: matrixDnD.from,
      dropTarget: matrixDnD.dropTarget,
    };
    cleanupMatrixDnDListeners();
    if (!commit || !state.enabled) return;

    if (ctx.axis === "col" && Number.isInteger(ctx.from) && Number.isInteger(ctx.dropTarget)) {
      if (!willApplyMatrixMove("col", ctx.from, ctx.dropTarget)) return;
      if (applyMoveColumn(ctx.from, ctx.dropTarget, { registerOp: true, keepSelection: true })) {
        updateStatus("Coluna reorganizada.");
      }
      return;
    }

    if (ctx.axis === "row" && Number.isInteger(ctx.from) && Number.isInteger(ctx.dropTarget)) {
      if (!willApplyMatrixMove("row", ctx.from, ctx.dropTarget)) return;
      if (applyMoveRow(ctx.from, ctx.dropTarget, { registerOp: true, keepSelection: true })) {
        updateStatus("Linha reorganizada.");
      }
    }
  }

  function beginMatrixDnD(event, axis, fromIndex, dragEl, handleEl) {
    if (!state.enabled || !dragEl || !handleEl) return;
    if (event.button != null && event.button !== 0) return;
    event.preventDefault();
    event.stopPropagation();
    finishInlineEdit({ commit: true });
    hideContextMenu();
    cleanupMatrixDnDListeners();

    matrixDnD.active = true;
    matrixDnD.axis = axis;
    matrixDnD.from = fromIndex;
    matrixDnD.dropTarget = fromIndex;
    matrixDnD.dragEl = dragEl;
    matrixDnD.handleEl = handleEl;
    matrixDnD.pointerId = event.pointerId;

    try {
      handleEl.setPointerCapture(event.pointerId);
    } catch (e) {
      void e;
    }

    updateMatrixDnDHighlights();

    let ended = false;
    const finish = (upEvent, doCommit) => {
      if (ended) return;
      if (upEvent && upEvent.pointerId != null && upEvent.pointerId !== matrixDnD.pointerId) return;
      ended = true;
      endMatrixDnD(doCommit);
    };

    matrixDnD.onPointerMove = onMatrixDnDPointerMove;
    matrixDnD.onPointerEnd = (upEvent) => finish(upEvent, true);

    handleEl.addEventListener("pointermove", matrixDnD.onPointerMove);
    handleEl.addEventListener("pointerup", matrixDnD.onPointerEnd);
    handleEl.addEventListener("pointercancel", matrixDnD.onPointerEnd);
    handleEl.addEventListener("lostpointercapture", matrixDnD.onPointerEnd);

    const doc = frame.contentDocument;
    if (doc) {
      doc.addEventListener("pointerup", matrixDnD.onPointerEnd, true);
      doc.addEventListener("pointercancel", matrixDnD.onPointerEnd, true);
    }
    window.addEventListener("pointerup", matrixDnD.onPointerEnd, true);
    window.addEventListener("pointercancel", matrixDnD.onPointerEnd, true);
    window.addEventListener("blur", () => finish(null, false));
  }

  function onMatrixDnDStart(event) {
    if (!state.enabled) return;
    const target = resolveEventElement(event.target);
    if (!target || !target.classList.contains("po-mapa-dnd-handle")) return;
    const colCell = target.closest("th[data-po-dnd-col]");
    if (colCell) {
      beginMatrixDnD(event, "col", Number(colCell.dataset.poDndCol), colCell, target);
      return;
    }
    const rowEl = target.closest("tr[data-po-dnd-row]");
    if (rowEl) {
      beginMatrixDnD(event, "row", Number(rowEl.dataset.poDndRow), rowEl, target);
    }
  }

  function bindMatrixDragReorder() {
    const doc = frame.contentDocument;
    if (!doc || doc.__poMatrixDnDBound) return;
    doc.__poMatrixDnDBound = true;
    doc.addEventListener("pointerdown", onMatrixDnDStart, true);
  }

  function parseCurrentScope() {
    const scope = parseScopeFromPageKey(currentPageKey());
    const domMode = readMatrixModeFromIframeDom();
    if (domMode) scope.requestedMode = domMode;
    return {
      mode: resolveMatrixMode(scope),
      setor: scope.setor,
      bloco: scope.bloco,
      pavimento: scope.pavimento,
    };
  }

  function cleanupRowAddControls() {
    const doc = frame.contentDocument;
    if (!doc) return;
    doc.querySelectorAll(".po-mapa-row-inline-add").forEach((el) => el.remove());
    doc.querySelectorAll(".po-mapa-row-add").forEach((el) => el.remove());
    doc.querySelectorAll(".po-mapa-row-name-wrap").forEach((wrap) => {
      const parent = wrap.parentElement;
      if (!parent) return;
      while (wrap.firstChild) {
        parent.insertBefore(wrap.firstChild, wrap);
      }
      wrap.remove();
    });
  }

  function scopeDisplayLabel() {
    const scope = parseCurrentScope();
    if (scope.mode === "apto" && scope.bloco && scope.pavimento) {
      return `bloco ${scope.bloco} / pavimento ${scope.pavimento}`;
    }
    if (scope.mode === "pavimento" && scope.bloco) {
      return `bloco ${scope.bloco}`;
    }
    if (scope.mode === "bloco" && scope.setor) {
      return `setor ${scope.setor}`;
    }
    return "recorte atual";
  }

  function applyInsertColumn(index, label, options) {
    const cfg = options && typeof options === "object" ? options : {};
    if (!guardStructuralLayoutOp(cfg)) return false;
    const table = tableRef();
    if (!table) return false;
    const rows = Array.from(table.querySelectorAll("tr"));
    if (!rows.length) return false;
    const colCount = rows[0].children.length;
    if (colCount < 2) return false;
    const totalIndex = colCount - 1;
    const insertAt = clampIndex(Number(index), 1, totalIndex);
    const title = String(label || "Nova coluna").trim() || "Nova coluna";

    rows.forEach((row) => {
      const isHeader = row.parentElement && row.parentElement.tagName === "THEAD";
      let newCell = null;
      if (isHeader) {
        newCell = document.createElement("th");
        newCell.className = "vertical";
        const span = document.createElement("span");
        span.className = "matrix-col-head-link";
        span.textContent = title;
        newCell.appendChild(span);
      } else if (row.classList.contains("totals-row")) {
        newCell = document.createElement("td");
        newCell.className = "total-col";
        newCell.textContent = "-";
      } else {
        newCell = document.createElement("td");
        newCell.className = "cell-empty";
        newCell.textContent = "-";
      }
      const anchor = row.children[insertAt] || null;
      row.insertBefore(newCell, anchor);
    });

    mapEditableCells();
    if (cfg.keepSelection && state.selectedCell) {
      const sc = selectedCoords();
      if (sc) {
        const sel = table.querySelector(`[data-po-edit-key="r${sc.r}c${insertAt}"]`);
        if (sel) setSelectedCell(sel);
      }
    }
    if (cfg.registerOp !== false) {
      ensurePageDraft(currentPageKey()).ops.push({ type: "insert_col", index: insertAt, label: title });
      afterStructuralLayoutOpCommitted({ type: "create_column", index: insertAt, label: title });
    }
    refreshMoveButtons();
    return true;
  }

  function applyInsertRow(index, label, options) {
    const cfg = options && typeof options === "object" ? options : {};
    if (!guardStructuralLayoutOp(cfg)) return false;
    const table = tableRef();
    if (!table) return false;
    const tbody = table.querySelector("tbody");
    if (!tbody) return false;
    const pageKey = currentPageKey();
    const removedEmpty = removeMatrixEmptyRows(tbody);
    const bodyRows = listMatrixTbodyRows(tbody);
    const colCount = table.querySelector("tr") ? table.querySelector("tr").children.length : 0;
    if (!colCount || colCount < 2) return false;

    const insertAt = clampIndex(Number(index), 0, bodyRows.length);
    const title = String(label || "Nova linha").trim() || "Nova linha";
    const anchor = bodyRows[insertAt] || tbody.querySelector("tr.totals-row") || null;

    const doc = frame.contentDocument || document;
    const row = document.createElement("tr");
    const first = document.createElement("td");
    populateRowNameCell(first, sanitizeRowDisplayLabel(title) || title, pageKey);
    row.appendChild(first);
    for (let c = 1; c < colCount - 1; c += 1) {
      const td = document.createElement("td");
      td.className = "cell-empty";
      td.textContent = "-";
      row.appendChild(td);
    }
    const total = document.createElement("td");
    total.className = "total-col";
    total.textContent = "-";
    row.appendChild(total);

    if (anchor) tbody.insertBefore(row, anchor);
    else tbody.appendChild(row);

    mapEditableCells();
    if (cfg.keepSelection) {
      const cell = row.querySelector("td");
      if (cell) setSelectedCell(cell);
    }
    if (cfg.registerOp !== false) {
      const structuralOp = {
        type: "create_row",
        context: buildStructuralRowContext(pageKey),
        label: title,
        order: insertAt,
      };
      ensurePageDraft(pageKey).ops.push({
        type: "insert_row",
        index: insertAt,
        label: title,
        mode: getMatrixEditContext().mode,
      });
      poMapaDebug("insert_row", {
        url: pageKey,
        contexto: getMatrixEditContext(pageKey),
        label: title,
        index: insertAt,
        removedEmpty,
        structuralOp,
      });
      afterStructuralLayoutOpCommitted(structuralOp);
    }
    refreshMoveButtons();
    return true;
  }

  function applyDeleteColumn(index, options) {
    const cfg = options && typeof options === "object" ? options : {};
    if (!guardStructuralLayoutOp(cfg)) return false;
    const table = tableRef();
    if (!table) return false;
    const rows = Array.from(table.querySelectorAll("tr"));
    if (!rows.length) return false;
    const colCount = rows[0].children.length;
    const idx = clampIndex(Number(index), 0, colCount - 1);
    if (!Number.isFinite(idx)) return false;
    // Nunca remove primeira coluna (rótulo) nem última (Total)
    if (idx <= 0 || idx >= colCount - 1) return false;

    const headerCell = rows[0].children[idx];
    const colLabel = headerCell ? String(textNodeForCell(headerCell).textContent || "").trim() : "";

    rows.forEach((row) => {
      const cell = row.children[idx];
      if (cell) row.removeChild(cell);
    });

    mapEditableCells();
    if (cfg.keepSelection && state.selectedCell) {
      const sc = selectedCoords();
      if (sc) {
        const targetCol = Math.max(1, Math.min(idx - 1, (table.querySelector("tr")?.children.length || 2) - 2));
        const next = table.querySelector(`[data-po-edit-key="r${sc.r}c${targetCol}"]`);
        if (next) setSelectedCell(next);
      }
    }
    if (cfg.registerOp !== false) {
      ensurePageDraft(currentPageKey()).ops.push({ type: "delete_col", index: idx });
      afterStructuralLayoutOpCommitted({ type: "delete_column", index: idx, label: colLabel });
    }
    refreshMoveButtons();
    return true;
  }

  function applyDeleteRow(index, options) {
    const cfg = options && typeof options === "object" ? options : {};
    if (!guardStructuralLayoutOp(cfg)) return false;
    const table = tableRef();
    if (!table) return false;
    const tbody = table.querySelector("tbody");
    if (!tbody) return false;
    const rows = listMatrixTbodyRows(tbody);
    if (!rows.length) return false;
    const idx = clampIndex(Number(index), 0, rows.length - 1);
    if (!Number.isFinite(idx)) return false;
    const row = rows[idx];
    if (!row) return false;
    const nameCell = row.querySelector(".row-name, .sticky-left");
    const rowLabel = nameCell ? rowDisplayLabelFromNameCell(nameCell) : "";
    tbody.removeChild(row);

    mapEditableCells();
    if (cfg.keepSelection) {
      const remaining = listMatrixTbodyRows(tbody);
      if (remaining.length) {
        const pick = remaining[Math.max(0, Math.min(idx, remaining.length - 1))];
        const firstCell = pick.querySelector("td,th");
        if (firstCell) setSelectedCell(firstCell);
      }
    }
    if (cfg.registerOp !== false) {
      ensurePageDraft(currentPageKey()).ops.push({ type: "delete_row", index: idx });
      afterStructuralLayoutOpCommitted({
        type: "delete_row",
        context: buildStructuralRowContext(currentPageKey()),
        label: rowLabel,
      });
    }
    refreshMoveButtons();
    return true;
  }

  function addColumnFromToolbar() {
    if (!state.enabled) return;
    const table = tableRef();
    if (!table) return;
    showInsertDialog({
      kind: "column",
      onSubmit: ({ name, position }) => {
        const insertAt = resolveColumnInsertIndex(position);
        if (applyInsertColumn(insertAt, name, { registerOp: true, keepSelection: true })) {
          updateStatus(`Coluna "${name}" adicionada no ${scopeDisplayLabel()}.`);
        }
      },
    });
  }

  function addRowFromToolbar() {
    if (!state.enabled) return;
    const table = tableRef();
    if (!table) return;
    showInsertDialog({
      kind: "row",
      onSubmit: ({ name, position }) => {
        const insertAt = resolveRowInsertIndex(position);
        if (applyInsertRow(insertAt, name, { registerOp: true, keepSelection: true })) {
          updateStatus(`Linha "${name}" adicionada no ${scopeDisplayLabel()}.`);
          if (state.selectedCell) startInlineEdit(state.selectedCell);
        }
      },
    });
  }

  function deleteColumnFromToolbar() {
    if (!state.enabled || !canMoveSelectedColumn()) return;
    const sc = selectedCoords();
    if (!sc) return;
    const ok = window.confirm("Apagar a coluna selecionada? Esta ação afeta apenas o rascunho local.");
    if (!ok) return;
    if (applyDeleteColumn(sc.c, { registerOp: true, keepSelection: true })) {
      updateStatus("Coluna removida do rascunho local.");
    }
  }

  function deleteRowFromToolbar() {
    if (!state.enabled || !canMoveSelectedRow()) return;
    const bodyIndex = selectedBodyRowIndex();
    if (bodyIndex < 0) return;
    const ok = window.confirm("Apagar a linha selecionada? Esta ação afeta apenas o rascunho local.");
    if (!ok) return;
    if (applyDeleteRow(bodyIndex, { registerOp: true, keepSelection: true })) {
      updateStatus("Linha removida do rascunho local.");
    }
  }

  function applyQuickColor(color) {
    if (!state.enabled || !state.selectedCell || !state.selectedKey) return;
    if (!canEditPercentCell(state.selectedCell, { silent: true })) return;
    if (inpColor) inpColor.value = color;
    applyColorChange();
    updateStatus("Cor aplicada na célula.");
  }

  function buildContextMenu(cell, event) {
    if (!cell || !event) return;
    setSelectedCell(cell);
    const sc = selectedCoords();
    const layoutOps = state.enabled && canPersistStructuralLayoutOps();
    const canCol = layoutOps && canMoveSelectedColumn();
    const canRow = layoutOps && canMoveSelectedRow();
    const colName = sc ? `c${sc.c}` : "";
    const rowName = sc ? `r${sc.r}` : "";

    contextMenuEl.innerHTML = "";
    const title = document.createElement("div");
    title.className = "po-mapa-context-menu__title";
    title.textContent = state.enabled ? `Célula ${rowName}/${colName}` : "Modo visualização";
    contextMenuEl.appendChild(title);

    const canDirectEdit =
      canEditPercentCell(cell, { silent: true }) || canEditStructuralCell(cell);
    const canPercentDirect = canEditPercentCell(cell, { silent: true });
    contextMenuEl.appendChild(
      menuItem(
        state.enabled ? "Iniciar edição direta" : "Ativar edição",
        state.enabled ? "duplo clique" : "",
        {
          primary: true,
          disabled: state.enabled && !canDirectEdit,
          onClick: () => {
            if (!state.enabled) {
              state.enabled = true;
              updateToggleUi();
            }
            if (!startInlineEdit(cell)) return;
            updateStatus("Edição direta ativa. Enter confirma, Esc cancela.");
          },
        },
      ),
    );

    contextMenuEl.appendChild(menuSeparator());
    contextMenuEl.appendChild(menuItem("Mover coluna para esquerda", "", { disabled: !canCol, onClick: () => btnMoveColLeft && btnMoveColLeft.click() }));
    contextMenuEl.appendChild(menuItem("Mover coluna para direita", "", { disabled: !canCol, onClick: () => btnMoveColRight && btnMoveColRight.click() }));
    contextMenuEl.appendChild(menuItem("Mover linha para cima", "", { disabled: !canRow, onClick: () => btnMoveRowUp && btnMoveRowUp.click() }));
    contextMenuEl.appendChild(menuItem("Mover linha para baixo", "", { disabled: !canRow, onClick: () => btnMoveRowDown && btnMoveRowDown.click() }));

    contextMenuEl.appendChild(menuSeparator());
    contextMenuEl.appendChild(
      menuItem("Adicionar coluna", "", { disabled: !layoutOps, onClick: addColumnFromToolbar }),
    );
    contextMenuEl.appendChild(
      menuItem("Adicionar linha", scopeDisplayLabel(), { disabled: !layoutOps, onClick: addRowFromToolbar }),
    );
    contextMenuEl.appendChild(menuItem("Apagar coluna", "", { disabled: !canCol, danger: true, onClick: deleteColumnFromToolbar }));
    contextMenuEl.appendChild(menuItem("Apagar linha", "", { disabled: !canRow, danger: true, onClick: deleteRowFromToolbar }));

    contextMenuEl.appendChild(menuSeparator());
    contextMenuEl.appendChild(
      menuItem("Cor: azul", "", { disabled: !canPercentDirect, onClick: () => applyQuickColor("#2563eb") }),
    );
    contextMenuEl.appendChild(
      menuItem("Cor: verde", "", { disabled: !canPercentDirect, onClick: () => applyQuickColor("#16a34a") }),
    );
    contextMenuEl.appendChild(
      menuItem("Cor: laranja", "", { disabled: !canPercentDirect, onClick: () => applyQuickColor("#ea580c") }),
    );
    contextMenuEl.appendChild(
      menuItem(
        "Cor personalizada",
        "",
        { disabled: !canPercentDirect, onClick: () => inpColor && inpColor.click() },
      ),
    );

    contextMenuEl.appendChild(menuSeparator());
    contextMenuEl.appendChild(menuItem("Salvar no servidor", "", { disabled: !state.enabled, onClick: () => saveDraftToServer() }));
    contextMenuEl.appendChild(menuItem("Descartar rascunho", "", { disabled: !state.enabled, danger: true, onClick: discardDraft }));

    showContextMenu(event.clientX, event.clientY);
  }

  function onDocClick(event) {
    if (state.context.visible) hideContextMenu();
    const target = resolveEventElement(event.target);
    if (!target) return;
    if (target.closest("a.row-link")) {
      return;
    }
    if (target.closest(".po-mapa-dnd-handle")) {
      return;
    }
    if (!state.enabled) return;
    if (state.inline.node && (target === state.inline.node || target.closest('[data-po-inline-edit="1"]'))) {
      return;
    }
    const cell = target.closest(".matrix-table td, .matrix-table th");
    if (!cell) return;
    const canPercent = canEditPercentCell(cell, { silent: true });
    const canStructural = canEditStructuralCell(cell);
    if (!canPercent && !canStructural) {
      if (isMatrixPercentDataCell(cell)) {
        event.preventDefault();
        event.stopPropagation();
        showBlockedPercentEditMessage();
      }
      return;
    }
    event.preventDefault();
    event.stopPropagation();
    setSelectedCell(cell);
    if (canStructural && !canPercent) {
      updateStatus("Célula estrutural selecionada. Edite o texto e aplique.");
    } else {
      updateStatus("Célula selecionada. Edite texto/cor e aplique.");
    }
  }

  function onDocDoubleClick(event) {
    if (!state.enabled) return;
    const target = resolveEventElement(event.target);
    if (!target) return;
    if (target.closest("a.row-link")) return;
    const cell = target.closest(".matrix-table td, .matrix-table th");
    if (!cell) return;
    if (!canEditPercentCell(cell, { silent: true }) && !canEditStructuralCell(cell)) {
      if (isMatrixPercentDataCell(cell)) {
        event.preventDefault();
        event.stopPropagation();
        showBlockedPercentEditMessage();
      }
      return;
    }
    event.preventDefault();
    event.stopPropagation();
    if (startInlineEdit(cell)) {
      updateStatus("Edição direta ativa. Enter confirma, Esc cancela.");
    }
  }

  function onDocContextMenu(event) {
    const target = resolveEventElement(event.target);
    if (!target) return;
    const cell = target.closest(".matrix-table td, .matrix-table th");
    if (!cell) {
      hideContextMenu();
      return;
    }
    event.preventDefault();
    event.stopPropagation();
    buildContextMenu(cell, event);
  }

  function onAnyDocKeyDown(event) {
    if (matrixDnD.active && event.key === "Escape") {
      event.preventDefault();
      endMatrixDnD(false);
      updateStatus("Reorganização cancelada.");
      return;
    }
    if (insertDialog.open && event.key === "Escape") {
      hideInsertDialog();
      return;
    }
    if (!state.context.visible) return;
    if (event.key === "Escape") {
      hideContextMenu();
    }
  }

  function onDocKeyDown(event) {
    if (!state.enabled || !state.inline.node) return;
    const target = resolveEventElement(event.target);
    if (!target || target !== state.inline.node) return;
    if (event.key === "Enter") {
      event.preventDefault();
      finishInlineEdit({ commit: true });
      updateStatus("Texto aplicado na célula.");
      return;
    }
    if (event.key === "Escape") {
      event.preventDefault();
      finishInlineEdit({ commit: false });
      updateStatus("Edição direta cancelada.");
    }
  }

  function onDocFocusOut(event) {
    if (!state.enabled || !state.inline.node) return;
    const target = resolveEventElement(event.target);
    if (!target || target !== state.inline.node) return;
    window.setTimeout(() => {
      if (!state.inline.node) return;
      const doc = frame.contentDocument;
      if (!doc) return;
      const active = doc.activeElement;
      if (active !== state.inline.node) {
        finishInlineEdit({ commit: true });
        updateStatus("Texto aplicado na célula.");
      }
    }, 0);
  }

  function toggleControls(enabled) {
    [btnSaveDraft, btnDiscardDraft].forEach((el) => {
      if (el) el.disabled = !enabled;
    });
    if (!enabled) {
      [inpText, btnApplyText, inpColor, btnApplyColor].forEach((el) => {
        if (el) el.disabled = true;
      });
    } else {
      refreshToolbarEditState();
    }
    refreshMoveButtons();
  }

  function updateStatus(msg) {
    if (!statusEl) return;
    statusEl.textContent = msg;
    statusEl.classList.toggle("is-dirty", state.dirty);
  }

  function updateToggleUi() {
    if (!btnToggle) return;
    btnToggle.classList.toggle("btn-outline-primary", !state.enabled);
    btnToggle.classList.toggle("btn-primary", state.enabled);
    btnToggle.innerHTML = state.enabled
      ? '<i class="bi bi-eye"></i> Desativar edição'
      : '<i class="bi bi-pencil-square"></i> Ativar edição';
    toggleControls(state.enabled);
    if (!state.enabled) {
      finishInlineEdit({ commit: true });
      cleanupRowAddControls();
      if (state.selectedCell) {
        state.selectedCell.style.outline = "";
        state.selectedCell.style.outlineOffset = "";
      }
      state.selectedCell = null;
      state.selectedKey = "";
      updateStatus("Somente visualização");
    }
    ensureEditModeIframeGuards();
    cleanupRowAddControls();
    enhanceMatrixDragHandles();
    if (!state.enabled) cleanupMatrixDnDListeners();
    refreshMoveButtons();
  }

  function markDirty() {
    state.dirty = true;
    updateStatus("Alterações locais não salvas.");
    try {
      window.localStorage.setItem(storageKey, JSON.stringify(state.draft));
    } catch (e) {
      void e;
    }
  }

  function afterStructuralLayoutOpCommitted(structuralOp) {
    if (structuralOp && typeof structuralOp === "object") {
      const page = ensurePageDraft(currentPageKey());
      page.structuralOps.push(structuralOp);
      poMapaDebug("structuralOp registrada", structuralOp);
    }
    markDirty();
  }

  function applyTextChange() {
    if (!state.enabled || !state.selectedCell || !state.selectedKey) return;
    if (!canEditPercentCell(state.selectedCell, { silent: true }) && !canEditStructuralCell(state.selectedCell)) {
      return;
    }
    finishInlineEdit({ commit: true });
    const page = ensurePageDraft(currentPageKey());
    const value = normalizeCellText(state.selectedCell, inpText ? inpText.value : "");
    if (inpText) inpText.value = value;
    textNodeForCell(state.selectedCell).textContent = value;
    page.text[state.selectedKey] = value;
    rememberCellPatch(state.selectedCell, state.selectedKey, value);
    markDirty();
  }

  function syncToolbarTextToCell() {
    if (!state.enabled || !state.selectedCell || !state.selectedKey || !inpText) return;
    if (!canEditPercentCell(state.selectedCell, { silent: true }) && !canEditStructuralCell(state.selectedCell)) {
      return;
    }
    finishInlineEdit({ commit: true });
    const page = ensurePageDraft(currentPageKey());
    const value = normalizeCellText(state.selectedCell, String(inpText.value || ""));
    inpText.value = value;
    textNodeForCell(state.selectedCell).textContent = value;
    page.text[state.selectedKey] = value;
    rememberCellPatch(state.selectedCell, state.selectedKey, value);
    markDirty();
  }

  function applyColorChange() {
    if (!state.enabled || !state.selectedCell || !state.selectedKey) return;
    if (!canEditPercentCell(state.selectedCell)) return;
    finishInlineEdit({ commit: true });
    const page = ensurePageDraft(currentPageKey());
    const color = inpColor ? inpColor.value : "";
    state.selectedCell.style.backgroundColor = color;
    state.selectedCell.style.color = "#ffffff";
    page.color[state.selectedKey] = color;
    markDirty();
  }

  function discardDraft() {
    finishInlineEdit({ commit: false });
    const pageKey = currentPageKey();
    if (state.draft.pages && state.draft.pages[pageKey]) {
      delete state.draft.pages[pageKey];
    }
    try {
      window.localStorage.setItem(storageKey, JSON.stringify(state.draft));
    } catch (e) {
      void e;
    }
    state.dirty = false;
    frame.contentWindow.location.reload();
  }

  function initDocumentHooks() {
    document.querySelectorAll(".po-mapa-dnd-guide").forEach((el) => el.remove());
    const doc = frame.contentDocument;
    if (!doc) return;
    const pageKey = currentPageKey();
    const pageDraft = (state.draft.pages || {})[pageKey];
    poMapaDebug("iframe load", {
      pageKey,
      temRascunho: !!pageDraft,
      ops: pageDraft && pageDraft.ops ? pageDraft.ops.length : 0,
      structuralOps: pageDraft && pageDraft.structuralOps ? pageDraft.structuralOps.length : 0,
      edicaoAtiva: state.enabled,
      emptyRows: doc.querySelectorAll("tr.matrix-empty-row").length,
      dataRows: listMatrixTbodyRows(doc.querySelector(".matrix-table tbody")).length,
    });
    mapEditableCells();
    ensureEditModeIframeGuards();
    doc.addEventListener("click", onDocClick, true);
    doc.addEventListener("dblclick", onDocDoubleClick, true);
    doc.addEventListener("contextmenu", onDocContextMenu, true);
    doc.addEventListener("keydown", onDocKeyDown, true);
    doc.addEventListener("keydown", onAnyDocKeyDown, true);
    doc.addEventListener("focusout", onDocFocusOut, true);
    try {
      applyDraftToDoc();
    } catch (e) {
      void e;
      updateStatus("Edição ativa (rascunho local parcialmente indisponível).");
    }
    updateStatus(state.enabled ? "Edição ativa. Selecione uma célula." : "Somente visualização");
    if (state.enabled) {
      updateToggleUi();
    }
  }

  frame.addEventListener("load", () => {
    hideLoading();
    cleanupRowAddControls();
    if (state.restoreEditOnNextLoad) {
      state.enabled = true;
      state.restoreEditOnNextLoad = false;
    }
    initDocumentHooks();
    resizeFrameToContent();
    scrollIframeToMatrix();
    window.setTimeout(() => {
      resizeFrameToContent();
      scrollIframeToMatrix();
    }, 120);
    if (typeof restoreParentScrollY === "number") {
      const targetY = restoreParentScrollY;
      restoreParentScrollY = null;
      window.requestAnimationFrame(() => {
        window.scrollTo({ top: targetY, left: 0, behavior: "auto" });
      });
    }
  });
  frame.addEventListener("error", () => {
    if (!loading) return;
    loading.textContent = "Falha ao carregar o mapa para edição.";
    loading.style.display = "flex";
  });

  window.addEventListener("message", (event) => {
    if (event.origin !== window.location.origin) return;
    if (event.source !== frame.contentWindow) return;
    const data = event.data;
    if (!data || typeof data !== "object") return;
    if (data.type === "po:iframe-nav-start") {
      restoreParentScrollY = window.scrollY;
      return;
    }
    if (data.type !== "po:iframe-scroll-bridge") return;
    const payload = data.payload;
    const dy = Number(payload && payload.deltaY);
    if (!Number.isFinite(dy) || dy === 0) return;
    bridgedDeltaY += dy;
    if (bridgeRaf) return;
    bridgeRaf = window.requestAnimationFrame(() => {
      bridgeRaf = 0;
      const delta = bridgedDeltaY;
      bridgedDeltaY = 0;
      if (!delta) return;
      window.scrollBy({ top: delta, left: 0, behavior: "auto" });
    });
  });

  document.addEventListener("click", (event) => {
    if (!state.context.visible) return;
    if (!contextMenuEl.contains(event.target)) {
      hideContextMenu();
    }
  });
  document.addEventListener("keydown", onAnyDocKeyDown, true);
  window.addEventListener("resize", hideContextMenu);
  window.addEventListener("scroll", hideContextMenu, true);

  if (btnToggle) {
    btnToggle.addEventListener("click", () => {
      state.enabled = !state.enabled;
      updateToggleUi();
      if (state.enabled) updateStatus("Edição ativa. Selecione uma célula.");
    });
  }
  if (btnApplyText) btnApplyText.addEventListener("click", applyTextChange);
  if (inpText) {
    let toolbarInputTimer = 0;
    inpText.addEventListener("input", () => {
      if (!state.enabled || !state.selectedCell) return;
      if (toolbarInputTimer) window.clearTimeout(toolbarInputTimer);
      toolbarInputTimer = window.setTimeout(() => {
        syncToolbarTextToCell();
      }, 120);
    });
    inpText.addEventListener("change", syncToolbarTextToCell);
    inpText.addEventListener("blur", syncToolbarTextToCell);
    inpText.addEventListener("keydown", (event) => {
      if (event.key !== "Enter") return;
      event.preventDefault();
      syncToolbarTextToCell();
      updateStatus("Texto aplicado na célula.");
    });
  }
  if (btnApplyColor) btnApplyColor.addEventListener("click", applyColorChange);
  if (btnAddCol) btnAddCol.addEventListener("click", addColumnFromToolbar);
  if (btnAddRow) btnAddRow.addEventListener("click", addRowFromToolbar);
  if (btnDeleteCol) btnDeleteCol.addEventListener("click", deleteColumnFromToolbar);
  if (btnDeleteRow) btnDeleteRow.addEventListener("click", deleteRowFromToolbar);
  if (btnMoveColLeft) {
    btnMoveColLeft.addEventListener("click", () => {
      const sc = selectedCoords();
      if (!sc || !canMoveSelectedColumn()) return;
      const target = Math.max(1, sc.c - 1);
      if (applyMoveColumn(sc.c, target, { registerOp: true, keepSelection: true })) {
        updateStatus("Coluna movida para a esquerda.");
      }
    });
  }
  if (btnMoveColRight) {
    btnMoveColRight.addEventListener("click", () => {
      const table = tableRef();
      const sc = selectedCoords();
      if (!table || !sc || !canMoveSelectedColumn()) return;
      const row = table.querySelector("tr");
      if (!row) return;
      const target = Math.min(row.children.length - 2, sc.c + 1);
      if (applyMoveColumn(sc.c, target, { registerOp: true, keepSelection: true })) {
        updateStatus("Coluna movida para a direita.");
      }
    });
  }
  if (btnMoveRowUp) {
    btnMoveRowUp.addEventListener("click", () => {
      const fromBody = selectedBodyRowIndex();
      if (fromBody < 0 || !canMoveSelectedRow()) return;
      const target = Math.max(0, fromBody - 1);
      if (applyMoveRow(fromBody, target, { registerOp: true, keepSelection: true })) {
        updateStatus("Linha movida para cima.");
      }
    });
  }
  if (btnMoveRowDown) {
    btnMoveRowDown.addEventListener("click", () => {
      const movable = matrixBodyRows();
      const fromBody = selectedBodyRowIndex();
      if (fromBody < 0 || !canMoveSelectedRow()) return;
      const target = Math.min(movable.length - 1, fromBody + 1);
      if (applyMoveRow(fromBody, target, { registerOp: true, keepSelection: true })) {
        updateStatus("Linha movida para baixo.");
      }
    });
  }
  if (btnSaveDraft) btnSaveDraft.addEventListener("click", () => saveDraftToServer());
  if (btnDiscardDraft) btnDiscardDraft.addEventListener("click", discardDraft);

  updateToggleUi();

  // Fallback para conexões lentas.
  window.setTimeout(hideLoading, 6500);
  window.addEventListener("resize", () => {
    resizeFrameToContent();
  });
})();
