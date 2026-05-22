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
    .po-map-edit-enabled .po-mapa-row-name-wrap {
      display: flex;
      align-items: center;
      gap: 6px;
      min-width: 0;
    }
    .po-map-edit-enabled .po-mapa-row-name-wrap > :not(.po-mapa-row-add) {
      flex: 1 1 auto;
      min-width: 0;
    }
    .po-map-edit-enabled .po-mapa-row-add {
      flex: 0 0 auto;
      width: 22px;
      height: 22px;
      padding: 0;
      border: 1px solid #cbd5e1;
      border-radius: 6px;
      background: #f8fafc;
      color: #2563eb;
      font-size: 0.95rem;
      line-height: 1;
      cursor: pointer;
    }
    .po-map-edit-enabled .po-mapa-row-add:hover {
      background: #eff6ff;
      border-color: #93c5fd;
    }
    .po-mapa-row-inline-add {
      display: flex;
      align-items: center;
      gap: 6px;
      margin-top: 4px;
      padding-top: 4px;
      border-top: 1px dashed #e2e8f0;
    }
    .po-mapa-row-inline-add input {
      flex: 1 1 auto;
      min-width: 0;
      border: 1px solid #93c5fd;
      border-radius: 6px;
      padding: 4px 8px;
      font-size: 0.82rem;
    }
    .po-mapa-row-inline-add input:focus {
      outline: 2px solid #bfdbfe;
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
    const rows = Array.from(tbody.querySelectorAll("tr")).filter((tr) => !tr.classList.contains("totals-row"));
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
    const tbodyRows = Array.from(table.querySelectorAll("tbody tr"));
    let insertAt = tbodyRows.findIndex((tr) => tr.classList.contains("totals-row"));
    if (insertAt < 0) insertAt = tbodyRows.length;
    const sc = selectedCoords();
    if (!sc || sc.r <= 0) return insertAt;
    const base = sc.r - 1;
    const mode = String(position || "below").trim().toLowerCase();
    if (mode === "above") return Math.max(0, base);
    if (mode === "end") {
      insertAt = tbodyRows.findIndex((tr) => tr.classList.contains("totals-row"));
      return insertAt < 0 ? tbodyRows.length : insertAt;
    }
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

  function rowDisplayLabelFromNameCell(nameCell) {
    if (!nameCell) return "";
    const plain = nameCell.querySelector(".row-name-txt");
    if (plain) return String(plain.textContent || "").trim();
    const link = nameCell.querySelector("a.row-link");
    if (link) return String(link.textContent || "").trim();
    const wrap = nameCell.querySelector(".po-mapa-row-name-wrap");
    if (wrap) {
      const clone = wrap.cloneNode(true);
      clone.querySelectorAll(".po-mapa-row-add, .po-mapa-row-inline-add").forEach((el) => el.remove());
      return String(clone.textContent || "").trim();
    }
    return String(textNodeForCell(nameCell).textContent || "").trim();
  }

  function rowLabelForCell(cell) {
    if (!cell) return "";
    const tr = cell.closest("tr");
    if (!tr) return "";
    const nameCell = tr.querySelector(".row-name, .sticky-left");
    if (!nameCell) return "";
    return rowDisplayLabelFromNameCell(nameCell);
  }

  function rememberCellPatch(cell, key, text) {
    const page = ensurePageDraft(currentPageKey());
    const coords = cellCoordsFromKey(cell);
    if (!coords) return;
    page.cells = page.cells || {};
    page.cells[key] = {
      colIndex: coords.c,
      rowLabel: rowLabelForCell(cell),
      text: String(text || ""),
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

  function exportTableBodyRows(table, header, axisMap) {
    if (!table || !Array.isArray(header) || !header.length) return [];
    const colCount = header.length;
    const out = [];
    const filters = parsePageFilters(currentPageKey());
    const rowAxisKey = inferRowAxisKeyFromPage();
    const rowAxisIdx = axisMap[rowAxisKey];
    const bodyRows = Array.from(table.querySelectorAll("tbody tr")).filter(
      (tr) => !tr.classList.contains("totals-row")
    );
    bodyRows.forEach((tr) => {
      const row = new Array(colCount).fill("");
      ["setor", "bloco", "pavimento", "apto"].forEach((key) => {
        const idx = axisMap[key];
        if (Number.isInteger(idx) && filters[key]) row[idx] = filters[key];
      });
      const nameCell = tr.querySelector(".row-name, .sticky-left");
      if (nameCell && Number.isInteger(rowAxisIdx)) {
        let label = rowDisplayLabelFromNameCell(nameCell);
        if (label === "-") label = "";
        row[rowAxisIdx] = label;
      }
      tr.querySelectorAll("td").forEach((cell) => {
        if (cell.classList.contains("row-name") || cell.classList.contains("sticky-left")) return;
        const coords = cellCoordsFromKey(cell);
        const colIndex = coords ? coords.c : null;
        if (colIndex == null || colIndex < 0 || colIndex >= colCount) return;
        let text = String(textNodeForCell(cell).textContent || "").trim();
        if (text === "-") text = "";
        if (text.endsWith("%")) {
          text = text.replace(/%/g, "").trim();
        }
        row[colIndex] = text;
      });
      out.push(row);
    });
    return out;
  }

  function replaceLayoutRowsFromTableExport(data, axisMap, meta) {
    const doc = frame.contentDocument;
    const table = doc && doc.querySelector(".matrix-table");
    if (!table || !data || !Array.isArray(data.rows) || !data.rows.length) return;
    const header = data.rows[0];
    const exported = exportTableBodyRows(table, header, axisMap);
    if (!exported.length) return;

    const filters = parsePageFilters(currentPageKey());
    const manualFlat = isManualFlatLayout(meta, axisMap);
    const hasScopedAxisFilter = Object.entries(filters).some(([key, value]) => {
      if (!value) return false;
      return Number.isInteger(axisMap[key]);
    });

    if (manualFlat || !hasScopedAxisFilter) {
      data.rows = [header, ...exported];
      return;
    }

    const kept = [];
    for (let ri = 1; ri < data.rows.length; ri += 1) {
      const row = data.rows[ri];
      if (!Array.isArray(row)) continue;
      if (!rowMatchesFilters(row, axisMap, filters)) {
        kept.push(row);
      }
    }
    data.rows = [header, ...kept, ...exported];
  }

  function mergeVisibleTableIntoLayoutRows(rows, axisMap, filters) {
    const doc = frame.contentDocument;
    const table = doc && doc.querySelector(".matrix-table");
    if (!table || !Array.isArray(rows) || !rows.length) return;
    const bodyRows = Array.from(table.querySelectorAll("tbody tr")).filter(
      (tr) => !tr.classList.contains("totals-row")
    );
    bodyRows.forEach((tr) => {
      const nameCell = tr.querySelector(".row-name, .sticky-left");
      if (!nameCell) return;
      const rowLabel = rowDisplayLabelFromNameCell(nameCell);
      tr.querySelectorAll("td").forEach((cell) => {
        if (cell.classList.contains("row-name") || cell.classList.contains("sticky-left")) return;
        const coords = cellCoordsFromKey(cell);
        if (!coords) return;
        const text = String(textNodeForCell(cell).textContent || "").trim();
        applyCellTextToLayoutRows(rows, axisMap, filters, rowLabel, coords.c, text, inferRowAxisKeyFromPage());
      });
    });
  }

  function mergeAllDraftsIntoLayout(layout) {
    const next = layout && typeof layout === "object" ? layout : { sections: [] };
    const sections = Array.isArray(next.sections) ? next.sections : [];
    sections.forEach((section) => {
      const data = section && section.data;
      if (!data || !Array.isArray(data.rows) || !data.rows.length) return;
      const header = data.rows[0];
      const meta = data.importMeta && typeof data.importMeta === "object" ? data.importMeta : {};
      const axisMap = buildAxisMapFromMeta(meta, header);
      const pages = state.draft.pages || {};
      Object.entries(pages).forEach(([pageKey, pageDraft]) => {
        const filters = parsePageFilters(pageKey);
        const texts = (pageDraft && pageDraft.text) || {};
        const cells = (pageDraft && pageDraft.cells) || {};
        const keys = new Set([...Object.keys(texts), ...Object.keys(cells)]);
        keys.forEach((key) => {
          const patch = cells[key] || {};
          const colIndex = Number.isInteger(patch.colIndex) ? patch.colIndex : null;
          const rowLabel = patch.rowLabel != null ? String(patch.rowLabel).trim() : "";
          const text =
            texts[key] != null ? String(texts[key]) : patch.text != null ? String(patch.text) : "";
          if (!rowLabel || colIndex == null) return;
        const rowAxisKey = inferRowAxisKeyFromPage(pageKey);
        applyCellTextToLayoutRows(data.rows, axisMap, filters, rowLabel, colIndex, text, rowAxisKey);
      });
    });
      mergeVisibleTableIntoLayoutRows(data.rows, axisMap, parsePageFilters(currentPageKey()));
      replaceLayoutRowsFromTableExport(data, axisMap, meta);
    });
    return next;
  }

  async function saveDraftToServer() {
    if (!ctx.ambienteId || !ctx.endpoints || !ctx.endpoints.saveDraft) {
      saveDraftToStorage();
      return;
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
      const layout = mergeAllDraftsIntoLayout(JSON.parse(JSON.stringify(draft.layout || {})));
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
      if (!saveRes.ok || !saveJson.success) {
        throw new Error((saveJson && saveJson.error) || "Falha ao salvar no servidor.");
      }
      state.dirty = false;
      state.draft = { pages: {} };
      try {
        window.localStorage.removeItem(storageKey);
      } catch (e) {
        void e;
      }
      updateStatus("Mapa salvo no servidor.");
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
    if (!state.draft.pages[pageKey]) state.draft.pages[pageKey] = { text: {}, color: {}, ops: [] };
    if (!Array.isArray(state.draft.pages[pageKey].ops)) state.draft.pages[pageKey].ops = [];
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

  function isPercentEligibleCell(cell) {
    if (!cell || cell.tagName !== "TD") return false;
    if (cell.classList.contains("row-name") || cell.classList.contains("sticky-left")) return false;
    const coords = cellCoordsFromKey(cell);
    if (!coords) return false;
    return coords.c > 0;
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
      inline.node.textContent = nextText;
      page.text[inline.key] = nextText;
      rememberCellPatch(inline.cell, inline.key, nextText);
      if (hasChanged) markDirty();
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
    if (!state.enabled || !cell) return;
    setSelectedCell(cell);
    finishInlineEdit({ commit: true });
    const node = textNodeForCell(cell);
    if (!node) return;
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
  }

  function applyDraftToDoc() {
    const doc = frame.contentDocument;
    if (!doc) return;
    const page = ensurePageDraft(currentPageKey());
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
      textNodeForCell(cell).textContent = String(value || "");
    });
    Object.entries(page.color || {}).forEach(([key, value]) => {
      const cell = doc.querySelector(`[data-po-edit-key="${escapeSelectorValue(key)}"]`);
      if (!cell) return;
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
    ensureRowInlineAddControls();
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
    const table = tableRef();
    const sc = selectedCoords();
    if (!table || !sc) return false;
    const bodyRows = Array.from(table.querySelectorAll("tbody tr"));
    const bodyIndex = sc.r - 1;
    if (bodyIndex < 0 || bodyIndex >= bodyRows.length) return false;
    const row = bodyRows[bodyIndex];
    if (!row) return false;
    // Não move linha de totais.
    return !row.classList.contains("totals-row");
  }

  function refreshMoveButtons() {
    const enabled = state.enabled && !!state.selectedCell;
    const canCol = enabled && canMoveSelectedColumn();
    const canRow = enabled && canMoveSelectedRow();
    if (btnMoveColLeft) btnMoveColLeft.disabled = !canCol;
    if (btnMoveColRight) btnMoveColRight.disabled = !canCol;
    if (btnMoveRowUp) btnMoveRowUp.disabled = !canRow;
    if (btnMoveRowDown) btnMoveRowDown.disabled = !canRow;
    if (btnAddCol) btnAddCol.disabled = !state.enabled;
    if (btnAddRow) btnAddRow.disabled = !state.enabled;
    if (btnDeleteCol) btnDeleteCol.disabled = !(enabled && canMoveSelectedColumn());
    if (btnDeleteRow) btnDeleteRow.disabled = !(enabled && canMoveSelectedRow());
  }

  function applyMoveColumn(fromIdx, toIdx, options) {
    const cfg = options && typeof options === "object" ? options : {};
    const table = tableRef();
    if (!table) return false;
    const rows = Array.from(table.querySelectorAll("tr"));
    if (!rows.length) return false;
    const colCount = rows[0].children.length;
    const from = clampIndex(Number(fromIdx), 0, colCount - 1);
    const to = clampIndex(Number(toIdx), 0, colCount - 1);
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
      markDirty();
    }
    refreshMoveButtons();
    return true;
  }

  function applyMoveRow(fromBodyIdx, toBodyIdx, options) {
    const cfg = options && typeof options === "object" ? options : {};
    const table = tableRef();
    if (!table) return false;
    const tbody = table.querySelector("tbody");
    if (!tbody) return false;
    const rows = Array.from(tbody.querySelectorAll("tr"));
    if (!rows.length) return false;
    const max = rows.length - 1;
    const from = clampIndex(Number(fromBodyIdx), 0, max);
    const to = clampIndex(Number(toBodyIdx), 0, max);
    if (!Number.isFinite(from) || !Number.isFinite(to) || from === to) return false;
    const src = rows[from];
    const tgt = rows[to];
    if (!src || !tgt) return false;
    if (src.classList.contains("totals-row") || tgt.classList.contains("totals-row")) return false;
    if (from < to) tbody.insertBefore(src, tgt.nextSibling);
    else tbody.insertBefore(src, tgt);
    mapEditableCells();
    if (cfg.keepSelection) {
      const selected = table.querySelector(`[data-po-edit-key="r${to + 1}c0"]`);
      if (selected) setSelectedCell(selected);
    }
    if (cfg.registerOp !== false) {
      ensurePageDraft(currentPageKey()).ops.push({ type: "move_row", from, to });
      markDirty();
    }
    refreshMoveButtons();
    return true;
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

  function cancelRowInlineAdd() {
    const doc = frame.contentDocument;
    if (!doc) return;
    doc.querySelectorAll(".po-mapa-row-inline-add").forEach((el) => el.remove());
  }

  function openRowInlineAdd(anchorRow, insertAfterBodyIndex) {
    if (!state.enabled || !anchorRow) return;
    cancelRowInlineAdd();
    const nameCell = anchorRow.querySelector(".row-name, .sticky-left");
    if (!nameCell) return;
    const wrap = nameCell.querySelector(".po-mapa-row-name-wrap") || nameCell;
    const line = document.createElement("div");
    line.className = "po-mapa-row-inline-add";
    const input = document.createElement("input");
    input.type = "text";
    input.placeholder = rowAxisPlaceholder(inferRowAxisKeyFromPage());
    input.setAttribute("aria-label", `Novo ${rowAxisHumanLabel(inferRowAxisKeyFromPage()).toLowerCase()}`);
    line.appendChild(input);
    wrap.appendChild(line);
    input.focus();

    const commit = () => {
      const name = String(input.value || "").trim();
      if (!name) {
        cancelRowInlineAdd();
        return;
      }
      const insertAt = Math.max(0, Number(insertAfterBodyIndex) + 1);
      if (applyInsertRow(insertAt, name, { registerOp: true, keepSelection: true })) {
        updateStatus(`${rowAxisHumanLabel(inferRowAxisKeyFromPage())} "${name}" adicionado em ${scopeDisplayLabel()}.`);
      }
      cancelRowInlineAdd();
    };

    input.addEventListener("keydown", (event) => {
      if (event.key === "Enter") {
        event.preventDefault();
        commit();
      }
      if (event.key === "Escape") {
        event.preventDefault();
        cancelRowInlineAdd();
      }
    });
    input.addEventListener("blur", () => {
      window.setTimeout(() => {
        if (!line.isConnected) return;
        if (line.contains(doc.activeElement)) return;
        cancelRowInlineAdd();
      }, 120);
    });
  }

  function ensureRowInlineAddControls() {
    const doc = frame.contentDocument;
    if (!doc) return;
    const tbody = doc.querySelector(".matrix-table tbody");
    if (!tbody) return;
    const bodyRows = Array.from(tbody.querySelectorAll("tr")).filter((tr) => !tr.classList.contains("totals-row"));
    bodyRows.forEach((tr, bodyIndex) => {
      const nameCell = tr.querySelector(".row-name, .sticky-left");
      if (!nameCell) return;
      let wrap = nameCell.querySelector(".po-mapa-row-name-wrap");
      if (!wrap) {
        wrap = doc.createElement("div");
        wrap.className = "po-mapa-row-name-wrap";
        while (nameCell.firstChild) {
          wrap.appendChild(nameCell.firstChild);
        }
        nameCell.appendChild(wrap);
      }
      let btn = wrap.querySelector(".po-mapa-row-add");
      if (!btn) {
        btn = doc.createElement("button");
        btn.type = "button";
        btn.className = "po-mapa-row-add";
        btn.title = "Adicionar linha abaixo neste nível";
        btn.setAttribute("aria-label", "Adicionar linha abaixo");
        btn.textContent = "+";
        btn.addEventListener("click", (event) => {
          event.preventDefault();
          event.stopPropagation();
          if (!state.enabled) return;
          openRowInlineAdd(tr, bodyIndex);
        });
        wrap.insertBefore(btn, wrap.firstChild);
      }
      btn.hidden = !state.enabled;
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
      markDirty();
    }
    refreshMoveButtons();
    return true;
  }

  function applyInsertRow(index, label, options) {
    const cfg = options && typeof options === "object" ? options : {};
    const table = tableRef();
    if (!table) return false;
    const tbody = table.querySelector("tbody");
    if (!tbody) return false;
    const rows = Array.from(tbody.querySelectorAll("tr"));
    const colCount = table.querySelector("tr") ? table.querySelector("tr").children.length : 0;
    if (!colCount || colCount < 2) return false;

    const totalsIndex = rows.findIndex((tr) => tr.classList.contains("totals-row"));
    const maxInsert = totalsIndex >= 0 ? totalsIndex : rows.length;
    const insertAt = clampIndex(Number(index), 0, maxInsert);
    const title = String(label || "Nova linha").trim() || "Nova linha";

    const row = document.createElement("tr");
    const first = document.createElement("td");
    first.className = "sticky-left row-name";
    first.textContent = title;
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

    const anchor = rows[insertAt] || null;
    if (anchor) tbody.insertBefore(row, anchor);
    else tbody.appendChild(row);

    mapEditableCells();
    if (cfg.keepSelection) {
      const cell = row.querySelector("td");
      if (cell) setSelectedCell(cell);
    }
    if (cfg.registerOp !== false) {
      ensurePageDraft(currentPageKey()).ops.push({ type: "insert_row", index: insertAt, label: title });
      markDirty();
    }
    ensureRowInlineAddControls();
    refreshMoveButtons();
    return true;
  }

  function applyDeleteColumn(index, options) {
    const cfg = options && typeof options === "object" ? options : {};
    const table = tableRef();
    if (!table) return false;
    const rows = Array.from(table.querySelectorAll("tr"));
    if (!rows.length) return false;
    const colCount = rows[0].children.length;
    const idx = clampIndex(Number(index), 0, colCount - 1);
    if (!Number.isFinite(idx)) return false;
    // Nunca remove primeira coluna (rótulo) nem última (Total)
    if (idx <= 0 || idx >= colCount - 1) return false;

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
      markDirty();
    }
    refreshMoveButtons();
    return true;
  }

  function applyDeleteRow(index, options) {
    const cfg = options && typeof options === "object" ? options : {};
    const table = tableRef();
    if (!table) return false;
    const tbody = table.querySelector("tbody");
    if (!tbody) return false;
    const rows = Array.from(tbody.querySelectorAll("tr"));
    if (!rows.length) return false;
    const idx = clampIndex(Number(index), 0, rows.length - 1);
    if (!Number.isFinite(idx)) return false;
    const row = rows[idx];
    if (!row || row.classList.contains("totals-row")) return false;
    tbody.removeChild(row);

    mapEditableCells();
    if (cfg.keepSelection) {
      const remaining = Array.from(tbody.querySelectorAll("tr")).filter((tr) => !tr.classList.contains("totals-row"));
      if (remaining.length) {
        const pick = remaining[Math.max(0, Math.min(idx, remaining.length - 1))];
        const firstCell = pick.querySelector("td,th");
        if (firstCell) setSelectedCell(firstCell);
      }
    }
    if (cfg.registerOp !== false) {
      ensurePageDraft(currentPageKey()).ops.push({ type: "delete_row", index: idx });
      markDirty();
    }
    ensureRowInlineAddControls();
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
    const tbodyRows = Array.from(table.querySelectorAll("tbody tr"));
    if (!tbodyRows.length) return;
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
    const sc = selectedCoords();
    if (!sc) return;
    const bodyIndex = sc.r - 1;
    const ok = window.confirm("Apagar a linha selecionada? Esta ação afeta apenas o rascunho local.");
    if (!ok) return;
    if (applyDeleteRow(bodyIndex, { registerOp: true, keepSelection: true })) {
      updateStatus("Linha removida do rascunho local.");
    }
  }

  function applyQuickColor(color) {
    if (!state.enabled || !state.selectedCell || !state.selectedKey) return;
    if (inpColor) inpColor.value = color;
    applyColorChange();
    updateStatus("Cor aplicada na célula.");
  }

  function buildContextMenu(cell, event) {
    if (!cell || !event) return;
    setSelectedCell(cell);
    const sc = selectedCoords();
    const canCol = state.enabled && canMoveSelectedColumn();
    const canRow = state.enabled && canMoveSelectedRow();
    const colName = sc ? `c${sc.c}` : "";
    const rowName = sc ? `r${sc.r}` : "";

    contextMenuEl.innerHTML = "";
    const title = document.createElement("div");
    title.className = "po-mapa-context-menu__title";
    title.textContent = state.enabled ? `Célula ${rowName}/${colName}` : "Modo visualização";
    contextMenuEl.appendChild(title);

    contextMenuEl.appendChild(
      menuItem(
        state.enabled ? "Iniciar edição direta" : "Ativar edição",
        state.enabled ? "duplo clique" : "",
        {
          primary: true,
          onClick: () => {
            if (!state.enabled) {
              state.enabled = true;
              updateToggleUi();
            }
            startInlineEdit(cell);
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
    contextMenuEl.appendChild(menuItem("Adicionar coluna", "", { disabled: !state.enabled, onClick: addColumnFromToolbar }));
    contextMenuEl.appendChild(menuItem("Adicionar linha", scopeDisplayLabel(), { disabled: !state.enabled, onClick: addRowFromToolbar }));
    contextMenuEl.appendChild(menuItem("Apagar coluna", "", { disabled: !canCol, danger: true, onClick: deleteColumnFromToolbar }));
    contextMenuEl.appendChild(menuItem("Apagar linha", "", { disabled: !canRow, danger: true, onClick: deleteRowFromToolbar }));

    contextMenuEl.appendChild(menuSeparator());
    contextMenuEl.appendChild(menuItem("Cor: azul", "", { disabled: !state.enabled, onClick: () => applyQuickColor("#2563eb") }));
    contextMenuEl.appendChild(menuItem("Cor: verde", "", { disabled: !state.enabled, onClick: () => applyQuickColor("#16a34a") }));
    contextMenuEl.appendChild(menuItem("Cor: laranja", "", { disabled: !state.enabled, onClick: () => applyQuickColor("#ea580c") }));
    contextMenuEl.appendChild(menuItem("Cor personalizada", "", { disabled: !state.enabled, onClick: () => inpColor && inpColor.click() }));

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
    if (target.closest(".po-mapa-row-add, .po-mapa-row-inline-add")) {
      return;
    }
    if (!state.enabled) return;
    if (state.inline.node && (target === state.inline.node || target.closest('[data-po-inline-edit="1"]'))) {
      return;
    }
    const cell = target.closest(".matrix-table td, .matrix-table th");
    if (!cell) return;
    event.preventDefault();
    event.stopPropagation();
    setSelectedCell(cell);
    updateStatus("Célula selecionada. Edite texto/cor e aplique.");
  }

  function onDocDoubleClick(event) {
    if (!state.enabled) return;
    const target = resolveEventElement(event.target);
    if (!target) return;
    const cell = target.closest(".matrix-table td, .matrix-table th");
    if (!cell) return;
    event.preventDefault();
    event.stopPropagation();
    startInlineEdit(cell);
    updateStatus("Edição direta ativa. Enter confirma, Esc cancela.");
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
    [inpText, btnApplyText, inpColor, btnApplyColor, btnSaveDraft, btnDiscardDraft].forEach((el) => {
      if (el) el.disabled = !enabled;
    });
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
      cancelRowInlineAdd();
      if (state.selectedCell) {
        state.selectedCell.style.outline = "";
        state.selectedCell.style.outlineOffset = "";
      }
      state.selectedCell = null;
      state.selectedKey = "";
      updateStatus("Somente visualização");
    }
    ensureEditModeIframeGuards();
    ensureRowInlineAddControls();
    refreshMoveButtons();
  }

  function markDirty() {
    state.dirty = true;
    updateStatus("Alterações locais não salvas.");
  }

  function applyTextChange() {
    if (!state.enabled || !state.selectedCell || !state.selectedKey) return;
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
    const doc = frame.contentDocument;
    if (!doc) return;
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
  }

  frame.addEventListener("load", () => {
    hideLoading();
    cancelRowInlineAdd();
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
      const sc = selectedCoords();
      if (!sc || !canMoveSelectedRow()) return;
      const fromBody = sc.r - 1;
      const target = Math.max(0, fromBody - 1);
      if (applyMoveRow(fromBody, target, { registerOp: true, keepSelection: true })) {
        updateStatus("Linha movida para cima.");
      }
    });
  }
  if (btnMoveRowDown) {
    btnMoveRowDown.addEventListener("click", () => {
      const table = tableRef();
      const sc = selectedCoords();
      if (!table || !sc || !canMoveSelectedRow()) return;
      const movable = Array.from(table.querySelectorAll("tbody tr")).filter((tr) => !tr.classList.contains("totals-row"));
      const fromBody = sc.r - 1;
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
