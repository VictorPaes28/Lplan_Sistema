(function () {
  const ctx = window.PO_MAPA_EDIT_CONTEXT || {};
  const frame = document.getElementById("poMapaEditFrame");
  const loading = document.getElementById("poMapaEditLoading");
  const btnToggle = document.getElementById("btnMapaEditToggle");
  const inpText = document.getElementById("inpMapaEditText");
  const inpColor = document.getElementById("inpMapaEditColor");
  const btnColorPicker = document.getElementById("btnMapaColorPicker");
  const colorSwatchEl = document.getElementById("poMapaColorSwatch");
  const btnMoveColLeft = document.getElementById("btnMapaMoveColLeft");
  const btnMoveColRight = document.getElementById("btnMapaMoveColRight");
  const btnMoveRowUp = document.getElementById("btnMapaMoveRowUp");
  const btnMoveRowDown = document.getElementById("btnMapaMoveRowDown");
  const btnAddCol = document.getElementById("btnMapaAddCol");
  const btnAddRow = document.getElementById("btnMapaAddRow");
  const btnDeleteCol = document.getElementById("btnMapaDeleteCol");
  const btnDeleteRow = document.getElementById("btnMapaDeleteRow");
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
  /** Debounce do autosave: evita rajadas de POST enquanto o usuário edita. */
  const AUTO_SAVE_DELAY_MS = 2200;
  let autoSaveTimer = 0;
  let autoSaveInFlight = false;
  let autoSaveQueued = false;
  /** Evita navegar no 1º clique quando o usuário está fazendo duplo clique para renomear. */
  let rowNameDrillClickTimer = 0;
  const ROW_NAME_DRILL_CLICK_DELAY_MS = 280;

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
    layoutMeta: {},
    layoutHeaderLen: 0,
    autoSaveBlocked: false,
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
      return `${crumbs.join(" › ")} · + Linha para novo ${rowAxisHumanLabel(axisKey).toLowerCase()}.`;
    }
    return `+ Linha para novo ${rowAxisHumanLabel(axisKey).toLowerCase()}.`;
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

  /**
   * Em níveis estruturais (bloco/pavimento), inserir no meio pode deslocar vínculo implícito
   * de linhas filhas no layout esparso. Para evitar "roubo" de aptos, sempre anexamos no fim.
   */
  function shouldForceRowInsertAtEnd(pageKey) {
    return inferRowAxisKeyFromPage(pageKey) !== "apto";
  }

  function syncInsertDialogPositionUi(kind) {
    const isColumn = kind === "column";
    const forceEndRows = !isColumn && shouldForceRowInsertAtEnd();
    const ref = isColumn ? selectedColumnReferenceLabel() : selectedRowReferenceLabel();
    const hasRef = Boolean(ref);
    const { posAbove, posBelow, posEnd, posAboveLabel, posBelowLabel } = insertDialog.els;
    const endHint = posEnd ? posEnd.querySelector("small") : null;
    if (posAbove) {
      posAbove.hidden = forceEndRows || !hasRef;
      if (posAboveLabel) {
        if (isColumn) {
          posAboveLabel.textContent = hasRef ? `Antes de «${ref}»` : "Antes da coluna selecionada";
        } else {
          posAboveLabel.textContent = hasRef ? `Acima de «${ref}»` : "Acima da linha selecionada";
        }
      }
    }
    if (posBelow) {
      posBelow.hidden = forceEndRows || !hasRef;
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
        : forceEndRows
          ? "Inserção no fim para preservar o vínculo dos aptos por pavimento/bloco"
          : "Depois de todas as linhas visíveis";
    }
    const defaultPos = !isColumn && forceEndRows ? "end" : hasRef ? "below" : "end";
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
    if (shouldForceRowInsertAtEnd()) {
      const level = inferRowAxisKeyFromPage();
      if (level === "pavimento") {
        const ctx = getMatrixEditContext(currentPageKey());
        const blocoAtual = String(ctx.bloco || "").trim();
        if (blocoAtual) {
          const readBlocoFromDomRow = (tr) => {
            if (!tr) return "";
            const byData = String((tr.dataset && tr.dataset.bloco) || "").trim();
            if (byData) return byData;
            const link = tr.querySelector("a.row-link[href]");
            const href = link ? String(link.getAttribute("href") || "").trim() : "";
            if (!href) return "";
            try {
              const url = new URL(href, window.location.origin);
              return String(url.searchParams.get("bloco") || "").trim();
            } catch (e) {
              void e;
              return "";
            }
          };
          for (let i = bodyRows.length - 1; i >= 0; i -= 1) {
            const blocoRow = readBlocoFromDomRow(bodyRows[i]);
            if (blocoRow && blocoRow === blocoAtual) {
              return i + 1;
            }
          }
        }
      }
      return bodyRows.length;
    }
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

  function isPlaceholderRowLabel(label) {
    const t = String(label || "")
      .trim()
      .toLowerCase()
      .replace(/\.$/, "");
    return t === "sem dados para matriz";
  }

  function rowDisplayLabelFromNameCell(nameCell) {
    if (!nameCell) return "";
    const tr = nameCell.closest("tr");
    if (tr && isMatrixEmptyRow(tr)) return "";
    const plain = nameCell.querySelector(".row-name-txt");
    if (plain) {
      const lbl = sanitizeRowDisplayLabel(plain.textContent);
      return isPlaceholderRowLabel(lbl) ? "" : lbl;
    }
    const link = nameCell.querySelector("a.row-link");
    if (link) {
      const lbl = sanitizeRowDisplayLabel(link.textContent);
      return isPlaceholderRowLabel(lbl) ? "" : lbl;
    }
    const wrap = nameCell.querySelector(".po-mapa-row-name-wrap");
    if (wrap) {
      const clone = wrap.cloneNode(true);
      clone.querySelectorAll(".po-mapa-row-add, .po-mapa-row-inline-add").forEach((el) => el.remove());
      const lbl = sanitizeRowDisplayLabel(clone.textContent);
      return isPlaceholderRowLabel(lbl) ? "" : lbl;
    }
    const lbl = sanitizeRowDisplayLabel(textNodeForCell(nameCell).textContent);
    return isPlaceholderRowLabel(lbl) ? "" : lbl;
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
    return !!(
      tr &&
      tr.classList &&
      (tr.classList.contains("matrix-empty-row") || String(tr.getAttribute("data-empty-row") || "") === "1")
    );
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

  /** Espelha _matrix_row_drillable (views_controle): placeholders não são eixo estrutural. */
  function isMatrixRowLabelDrillable(rowLabel) {
    const key = String(rowLabel || "").trim();
    if (!key) return false;
    const low = key.toLowerCase();
    if (
      low === "sem valor" ||
      low === "sem bloco" ||
      low === "sem pav." ||
      low === "sem pavimento" ||
      low === "sem apto" ||
      low === "sem setor"
    ) {
      return false;
    }
    if (/^linha\s+\d+$/i.test(key)) return false;
    return true;
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
      if (!label || !isMatrixRowLabelDrillable(label)) return null;
      const ctx = getMatrixEditContext(pageKey);
      if (ctx.mode === "bloco") {
        p.set("bloco", label);
        p.delete("pavimento");
        p.delete("apto");
        p.delete("matrix_mode");
      } else if (ctx.mode === "pavimento") {
        if (ctx.bloco) p.set("bloco", ctx.bloco);
        p.set("pavimento", label);
        p.delete("apto");
        p.delete("matrix_mode");
      } else if (ctx.mode === "apto") {
        if (ctx.bloco) p.set("bloco", ctx.bloco);
        if (ctx.pavimento) p.set("pavimento", ctx.pavimento);
        p.set("apto", label);
        p.delete("matrix_mode");
      }
      if (ctx.setor && !p.get("setor")) p.set("setor", ctx.setor);
      return `${u.pathname}?${p.toString()}`;
    } catch (e) {
      void e;
      return null;
    }
  }

  function rowDrillLinkTitle(ctx) {
    if (ctx.mode === "bloco") return "Ver pavimentos deste bloco na matriz";
    if (ctx.mode === "pavimento" && !ctx.isAreaComum) {
      return "Ver unidades (aptos) deste pavimento na matriz";
    }
    if (ctx.mode === "apto" && !ctx.isAreaComum) {
      return "Ver detalhe desta unidade na matriz";
    }
    return "";
  }

  function isMatrixRowNameCell(cell) {
    return !!(
      cell &&
      cell.tagName === "TD" &&
      (cell.classList.contains("row-name") || cell.classList.contains("sticky-left")) &&
      cell.closest("tbody") &&
      !cell.closest(".totals-row")
    );
  }

  function findMatrixRowNameCellFromTarget(target) {
    const el = resolveEventElement(target);
    if (!el) return null;
    const cell = el.closest("tbody tr:not(.totals-row) > td.row-name, tbody tr:not(.totals-row) > td.sticky-left");
    return cell && isMatrixRowNameCell(cell) ? cell : null;
  }

  /** Link ou rótulo do nome (clique simples navega; duplo clique não entra em edição). */
  function isRowNameDrillLabelTarget(target) {
    const el = resolveEventElement(target);
    if (!el) return false;
    if (!el.closest("a.row-link, .row-name-txt")) return false;
    return !!findMatrixRowNameCellFromTarget(el);
  }

  function cancelRowNameDrillClick() {
    if (rowNameDrillClickTimer) {
      window.clearTimeout(rowNameDrillClickTimer);
      rowNameDrillClickTimer = 0;
    }
  }

  function scheduleRowNameDrillClick(nameCell) {
    cancelRowNameDrillClick();
    rowNameDrillClickTimer = window.setTimeout(() => {
      rowNameDrillClickTimer = 0;
      navigateMatrixRowDrill(nameCell, null);
    }, ROW_NAME_DRILL_CLICK_DELAY_MS);
  }

  function refreshRowDrillLinkForNameCell(nameCell, pageKey) {
    if (!nameCell || !shouldRowNameBeDrillLink(pageKey)) return;
    const key = pageKey || currentPageKey();
    const label = rowDisplayLabelFromNameCell(nameCell);
    const href = buildMatrixDrillHref(label, key);
    if (!href || !label) {
      const stale = nameCell.querySelector("a.row-link");
      if (stale && !href) {
        const span = document.createElement("span");
        span.className = "row-name-txt";
        span.textContent = label || stale.textContent || "";
        stale.replaceWith(span);
      }
      return;
    }
    const ctx = getMatrixEditContext(key);
    const title = rowDrillLinkTitle(ctx);
    const wrap = nameCell.querySelector(".po-mapa-row-name-wrap");
    let link = nameCell.querySelector("a.row-link");
    if (!link) {
      link = document.createElement("a");
      link.className = "cell-link row-link";
      const plain = nameCell.querySelector(".row-name-txt");
      if (plain) {
        link.textContent = label;
        plain.replaceWith(link);
      } else if (wrap) {
        const handle = wrap.querySelector(".po-mapa-dnd-handle");
        Array.from(wrap.childNodes).forEach((node) => {
          if (node.nodeType === Node.TEXT_NODE) wrap.removeChild(node);
          else if (node !== handle && node.classList && !node.classList.contains("po-mapa-dnd-handle")) {
            wrap.removeChild(node);
          }
        });
        link.textContent = label;
        wrap.appendChild(link);
      } else {
        nameCell.textContent = "";
        link.textContent = label;
        nameCell.appendChild(link);
      }
    }
    link.href = href;
    link.textContent = label;
    if (title) link.title = title;
    else link.removeAttribute("title");
  }

  function refreshAllMatrixRowDrillLinks() {
    const pageKey = currentPageKey();
    if (!shouldRowNameBeDrillLink(pageKey)) return;
    matrixBodyRows().forEach((tr) => {
      const nameCell = tr.querySelector(".row-name, .sticky-left");
      refreshRowDrillLinkForNameCell(nameCell, pageKey);
    });
  }

  function navigateMatrixRowDrill(nameCell, event) {
    if (!nameCell) return false;
    const pageKey = currentPageKey();
    if (!shouldRowNameBeDrillLink(pageKey)) return false;
    refreshRowDrillLinkForNameCell(nameCell, pageKey);
    const link = nameCell.querySelector("a.row-link");
    const href = link && link.getAttribute("href");
    if (!href) return false;
    if (event) {
      event.preventDefault();
      event.stopPropagation();
    }
    frame.contentWindow.location.assign(href);
    return true;
  }

  function isMatrixColumnHeadCell(cell) {
    return !!(
      cell &&
      cell.tagName === "TH" &&
      cell.classList.contains("vertical") &&
      cell.closest("thead")
    );
  }

  function columnActivityLabelFromHeadCell(thCell) {
    if (!thCell) return "";
    const link = thCell.querySelector("a.matrix-col-head-link");
    if (link) return sanitizeRowDisplayLabel(link.textContent);
    const span = thCell.querySelector("span.matrix-col-head-link");
    if (span) return sanitizeRowDisplayLabel(span.textContent);
    return sanitizeRowDisplayLabel(thCell.textContent);
  }

  function buildMatrixActivityFilterHref(activityLabel, pageKey) {
    const label = String(activityLabel || "").trim();
    if (!label) return null;
    try {
      const u = new URL(String(frame.contentWindow.location.href || ""), window.location.origin);
      const p = new URLSearchParams(u.search);
      p.set("atividade", label);
      return `${u.pathname}?${p.toString()}`;
    } catch (e) {
      void e;
      return null;
    }
  }

  function refreshMatrixColumnHeadLink(thCell, pageKey) {
    if (!isMatrixColumnHeadCell(thCell)) return;
    const label = columnActivityLabelFromHeadCell(thCell);
    const href = buildMatrixActivityFilterHref(label, pageKey);
    if (!href || !label) return;
    let link = thCell.querySelector("a.matrix-col-head-link");
    const span = thCell.querySelector("span.matrix-col-head-link");
    if (span && !link) {
      link = document.createElement("a");
      link.className = "matrix-col-head-link";
      span.replaceWith(link);
    }
    if (!link) {
      link = document.createElement("a");
      link.className = "matrix-col-head-link";
      const handle = thCell.querySelector(".po-mapa-dnd-handle");
      Array.from(thCell.childNodes).forEach((node) => {
        if (node === handle) return;
        if (node.nodeType === Node.TEXT_NODE && !String(node.textContent || "").trim()) {
          thCell.removeChild(node);
        } else if (node !== handle) {
          thCell.removeChild(node);
        }
      });
      thCell.appendChild(link);
    }
    link.href = href;
    link.textContent = label;
    link.title = "Filtrar por esta atividade";
  }

  function refreshAllMatrixColumnHeadLinks() {
    const table = tableRef();
    if (!table) return;
    const pageKey = currentPageKey();
    table.querySelectorAll("thead th.vertical").forEach((th) => {
      refreshMatrixColumnHeadLink(th, pageKey);
    });
  }

  function navigateMatrixColumnFilter(thCell, event) {
    if (!thCell) return false;
    refreshMatrixColumnHeadLink(thCell);
    const link = thCell.querySelector("a.matrix-col-head-link");
    const href = (link && link.getAttribute("href")) || buildMatrixActivityFilterHref(columnActivityLabelFromHeadCell(thCell));
    if (!href) return false;
    if (event) {
      event.preventDefault();
      event.stopPropagation();
    }
    frame.contentWindow.location.assign(href);
    return true;
  }

  function isFocusMovingToMapaFrame(relatedTarget) {
    if (!relatedTarget || !frame) return false;
    if (relatedTarget === frame) return true;
    try {
      const doc = frame.contentDocument;
      if (doc && doc.contains(relatedTarget)) return true;
    } catch (e) {
      void e;
    }
    return false;
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
      const linkTitle = rowDrillLinkTitle(ctx);
      if (linkTitle) a.title = linkTitle;
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

  function isValidStructuralCreateOp(op) {
    if (!op || op.type !== "create_row") return false;
    const label = String(op.label || "").trim();
    if (!label || isPlaceholderRowLabel(label)) return false;
    return !!(op.context && op.context.level);
  }

  function layoutRowHasPlaceholderLabel(row, axisMap) {
    if (!Array.isArray(row)) return false;
    for (const key of ["setor", "bloco", "pavimento", "apto"]) {
      const idx = axisMap[key];
      if (!Number.isInteger(idx)) continue;
      if (isPlaceholderRowLabel(row[idx])) return true;
    }
    return row.some((cell) => isPlaceholderRowLabel(cell));
  }

  function isStructuralGhostLayoutRow(row, axisMap) {
    if (!Array.isArray(row)) return true;
    const keys = ["setor", "bloco", "pavimento", "apto"];
    let hasAxis = false;
    for (const key of keys) {
      const idx = axisMap[key];
      if (!Number.isInteger(idx)) continue;
      hasAxis = true;
      if (String(row[idx] || "").trim()) return false;
    }
    return hasAxis;
  }

  function layoutRowHasActivityLaunch(row, activityCols) {
    if (!Array.isArray(row) || !activityCols.length) return false;
    return activityCols.some(
      (ci) => Number.isInteger(ci) && ci < row.length && String(row[ci] || "").trim(),
    );
  }

  /**
   * Espelha mapa_controle_viewmodel._forward_fill_hierarchy_axes — linhas de continuação da
   * importação (eixo vazio, % nas colunas) precisam herdar bloco/pavimento/apto antes do purge.
   * Linhas estruturais do editor (bloco ou pavimento sem filhos) não recebem forward-fill nos eixos vazios.
   */
  function forwardFillHierarchyAxesInLayout(data, axisMap) {
    if (!data || !Array.isArray(data.rows) || data.rows.length < 2) return;
    const chain = ["setor", "bloco", "pavimento", "apto"];
    const last = { setor: "", bloco: "", pavimento: "", apto: "" };
    for (let ri = 1; ri < data.rows.length; ri += 1) {
      const row = data.rows[ri];
      if (!Array.isArray(row)) continue;
      const axisAtStart = (key) => {
        const idx = axisMap[key];
        if (!Number.isInteger(idx)) return "";
        return String(row[idx] || "").trim();
      };
      const blocoAtStart = axisAtStart("bloco");
      const pavAtStart = axisAtStart("pavimento");
      const aptoAtStart = axisAtStart("apto");
      const structuralBlocoRow = !!(blocoAtStart && !pavAtStart && !aptoAtStart);
      const hasNonAxisCellData = (() => {
        const skip = new Set(
          ["setor", "bloco", "pavimento", "apto"]
            .map((k) => axisMap[k])
            .filter((idx) => Number.isInteger(idx)),
        );
        for (let ci = 0; ci < row.length; ci += 1) {
          if (skip.has(ci)) continue;
          if (String(row[ci] || "").trim()) return true;
        }
        return false;
      })();
      const structuralPavimentoRow = !!(pavAtStart && !aptoAtStart && !hasNonAxisCellData);
      chain.forEach((key) => {
        const idx = axisMap[key];
        if (!Number.isInteger(idx)) return;
        while (row.length <= idx) row.push("");
        const val = String(row[idx] || "").trim();
        if (val) {
          if (key === "setor" && val !== last.setor) {
            last.bloco = "";
            last.pavimento = "";
            last.apto = "";
          } else if (key === "bloco" && val !== last.bloco) {
            last.pavimento = "";
            last.apto = "";
          } else if (key === "pavimento" && val !== last.pavimento) {
            last.apto = "";
          }
          last[key] = val;
        } else if (last[key]) {
          if (structuralBlocoRow && (key === "pavimento" || key === "apto")) return;
          if (structuralPavimentoRow && key === "apto") return;
          if (
            key === "pavimento" &&
            aptoAtStart &&
            !pavAtStart &&
            !String(last.apto || "").trim()
          ) {
            return;
          }
          row[idx] = last[key];
        }
      });
    }
  }

  function purgeInvalidStructuralLayoutRows(data, axisMap) {
    if (!data || !Array.isArray(data.rows) || data.rows.length < 2) return;
    const header = data.rows[0];
    const meta = data.importMeta && typeof data.importMeta === "object" ? data.importMeta : {};
    const activityCols = activityColsFromMeta(meta, header ? header.length : 0);
    const axisValue = (row, key) => {
      const idx = axisMap[key];
      if (!Number.isInteger(idx) || !Array.isArray(row) || idx >= row.length) return "";
      return String(row[idx] || "").trim();
    };
    const kept = [header];
    for (let ri = 1; ri < data.rows.length; ri += 1) {
      const row = data.rows[ri];
      if (!Array.isArray(row)) continue;
      if (layoutRowHasPlaceholderLabel(row, axisMap)) continue;
      const isGhost = isStructuralGhostLayoutRow(row, axisMap);
      const hasActivity = layoutRowHasActivityLaunch(row, activityCols);
      if (isGhost && !hasActivity) {
        const blocoVal = axisValue(row, "bloco");
        const pavVal = axisValue(row, "pavimento");
        const aptoVal = axisValue(row, "apto");
        const isParentStructuralRow = !aptoVal && (pavVal || blocoVal);
        if (!isParentStructuralRow) continue;
      }
      kept.push(row);
    }
    data.rows = kept;
  }

  /** Remove slots vazios duplicados (preset antigo + enrich de %) quando já existe unidade no mesmo bloco/pavimento. */
  function purgeRedundantEmptyUnitSlots(data, axisMap) {
    if (!data || !Array.isArray(data.rows) || data.rows.length < 2) return;
    const aptoIdx = axisMap.apto;
    if (!Number.isInteger(aptoIdx)) return;
    const meta = data.importMeta && typeof data.importMeta === "object" ? data.importMeta : {};
    const activityCols = activityColsFromMeta(meta, data.rows[0] ? data.rows[0].length : 0);
    const hasActivity = (row) =>
      activityCols.some((ci) => Array.isArray(row) && ci < row.length && String(row[ci] || "").trim());
    const parentKey = (row) => {
      const parts = [];
      ["bloco", "pavimento"].forEach((key) => {
        const idx = axisMap[key];
        if (Number.isInteger(idx) && Array.isArray(row) && idx < row.length) {
          parts.push(String(row[idx] || "").trim());
        }
      });
      return parts.join("|");
    };
    const remove = [];
    for (let ri = 1; ri < data.rows.length; ri += 1) {
      const row = data.rows[ri];
      if (!Array.isArray(row)) continue;
      if (String(row[aptoIdx] || "").trim()) continue;
      if (hasActivity(row)) continue;
      // Linha estrutural de pavimento (pav preenchido, apto vazio, sem atividade) não entra nesta purge.
      const pavIdx = axisMap.pavimento;
      const pavVal = Number.isInteger(pavIdx) ? String(row[pavIdx] || "").trim() : "";
      if (pavVal) continue;
      // Linha estrutural de bloco (bloco preenchido, pavimento e apto vazios, sem atividade) não entra nesta purge.
      const blocoIdx = axisMap.bloco;
      const blocoVal = Number.isInteger(blocoIdx) ? String(row[blocoIdx] || "").trim() : "";
      if (blocoVal) continue;
      const pk = parentKey(row);
      if (!pk) continue;
      let siblingWithUnit = false;
      for (let rj = 1; rj < data.rows.length; rj += 1) {
        if (rj === ri) continue;
        const other = data.rows[rj];
        if (!Array.isArray(other)) continue;
        if (parentKey(other) !== pk) continue;
        if (String(other[aptoIdx] || "").trim()) {
          siblingWithUnit = true;
          break;
        }
      }
      if (siblingWithUnit) remove.push(ri);
    }
    remove.sort((a, b) => b - a).forEach((ri) => data.rows.splice(ri, 1));
  }

  /** Remove linha duplicada do mesmo apto sem % quando já existe irmã com lançamento (evita média 50%→25%). */
  function purgeDuplicateAptoRowsWithoutActivity(data, axisMap) {
    if (!data || !Array.isArray(data.rows) || data.rows.length < 2) return;
    const aptoIdx = axisMap.apto;
    if (!Number.isInteger(aptoIdx)) return;
    const meta = data.importMeta && typeof data.importMeta === "object" ? data.importMeta : {};
    const activityCols = activityColsFromMeta(meta, data.rows[0] ? data.rows[0].length : 0);
    const hasActivity = (row) =>
      activityCols.some((ci) => Array.isArray(row) && ci < row.length && String(row[ci] || "").trim());
    const parentKey = (row) => {
      const parts = [];
      ["bloco", "pavimento", "apto"].forEach((key) => {
        const idx = axisMap[key];
        if (Number.isInteger(idx) && Array.isArray(row) && idx < row.length) {
          parts.push(String(row[idx] || "").trim());
        }
      });
      return parts.join("|");
    };
    const remove = [];
    for (let ri = 1; ri < data.rows.length; ri += 1) {
      const row = data.rows[ri];
      if (!Array.isArray(row) || !String(row[aptoIdx] || "").trim() || hasActivity(row)) continue;
      const pk = parentKey(row);
      if (!pk) continue;
      for (let rj = 1; rj < data.rows.length; rj += 1) {
        if (rj === ri) continue;
        const other = data.rows[rj];
        if (!Array.isArray(other) || parentKey(other) !== pk) continue;
        if (hasActivity(other)) {
          remove.push(ri);
          break;
        }
      }
    }
    remove.sort((a, b) => b - a).forEach((ri) => data.rows.splice(ri, 1));
  }

  function layoutStructuralRowsForDebug(layout) {
    const { rows, axisMap } = extractLayoutMatrixFromLayout(layout);
    if (!rows.length) return [];
    return rows.slice(1).map((row) => ({
      setor: Number.isInteger(axisMap.setor) ? row[axisMap.setor] : "",
      bloco: Number.isInteger(axisMap.bloco) ? row[axisMap.bloco] : "",
      pavimento: Number.isInteger(axisMap.pavimento) ? row[axisMap.pavimento] : "",
      apto: Number.isInteger(axisMap.apto) ? row[axisMap.apto] : "",
    }));
  }

  function verifyCreateRowsInLayout(layout, structuralOps) {
    const ops = (structuralOps || []).filter((op) => op && op.type === "create_row");
    const invalid = ops.filter((op) => !isValidStructuralCreateOp(op));
    if (invalid.length) return invalid;
    const { rows, axisMap } = extractLayoutMatrixFromLayout(layout);
    if (!rows.length) return ops;
    return ops.filter((op) => {
      const context = op.context || {};
      const label = String(op.label || "").trim();
      return !layoutHasStructuralRow(rows, axisMap, context, label);
    });
  }

  function layoutDataRowIndexFromCell(cell) {
    const tr = cell && cell.closest ? cell.closest("tr") : null;
    const tbody = tr && tr.closest ? tr.closest("tbody") : null;
    if (!tr || !tbody || isNonDataMatrixRow(tr)) return null;
    const dataRows = listMatrixTbodyRows(tbody);
    const bodyIdx = dataRows.indexOf(tr);
    if (bodyIdx < 0) return null;
    return bodyIdx;
  }

  function activityColsFromMeta(meta, headerLen) {
    const fromMeta =
      meta && Array.isArray(meta.activity_cols_interpreted) ? meta.activity_cols_interpreted : [];
    const cols = fromMeta.filter((i) => Number.isInteger(i));
    if (cols.length) return cols;
    const n = Number(headerLen) || 0;
    if (n > 2) {
      return Array.from({ length: Math.max(0, n - 2) }, (_, i) => i + 1);
    }
    return [];
  }

  /** Índice da coluna no layout canônico (≠ índice visual da tabela: col 0 = Bloco, 1+ = atividades). */
  function domMatrixColToLayoutCol(domCol, meta, headerLen) {
    const c = Number(domCol);
    if (!Number.isInteger(c)) return null;
    if (c <= 0) return c;
    const activityCols = activityColsFromMeta(meta, headerLen);
    const idx = c - 1;
    if (idx >= 0 && idx < activityCols.length) return activityCols[idx];
    return c;
  }

  function layoutColIndexForPercentPatch(patch, meta, headerLen) {
    if (!patch || typeof patch !== "object") return null;
    const activityCols = activityColsFromMeta(meta, headerLen);
    if (Number.isInteger(patch.domColIndex)) {
      return domMatrixColToLayoutCol(patch.domColIndex, meta, headerLen);
    }
    if (Number.isInteger(patch.layoutColIndex)) return patch.layoutColIndex;
    if (Number.isInteger(patch.colIndex) && activityCols.includes(patch.colIndex)) {
      return patch.colIndex;
    }
    if (Number.isInteger(patch.colIndex)) {
      return domMatrixColToLayoutCol(patch.colIndex, meta, headerLen);
    }
    return null;
  }

  function cacheLayoutFromExtracted(extracted) {
    const info = extracted && typeof extracted === "object" ? extracted : {};
    state.layoutMeta = info.meta && typeof info.meta === "object" ? info.meta : {};
    state.layoutHeaderLen = Array.isArray(info.header) ? info.header.length : 0;
  }

  async function refreshLayoutMetaCache() {
    if (!ctx.ambienteId || !ctx.endpoints || !ctx.endpoints.detalhe) return;
    try {
      const res = await fetch(ctx.endpoints.detalhe, {
        credentials: "same-origin",
        headers: { "X-Requested-With": "XMLHttpRequest" },
      });
      const json = await res.json();
      if (!res.ok || !json.success) return;
      const layout = (json.draft || json.versao || {}).layout || {};
      cacheLayoutFromExtracted(extractLayoutMatrixFromLayout(layout));
    } catch (e) {
      void e;
    }
  }

  function rememberCellPatch(cell, key, text) {
    const kind = patchKindForCell(cell);
    if (!kind) return;
    const pageKey = currentPageKey();
    const page = ensurePageDraft(pageKey);
    const coords = cellCoordsFromKey(cell);
    if (!coords) return;
    const filters = parsePageFilters(pageKey);
    const meta = state.layoutMeta || {};
    const headerLen = state.layoutHeaderLen || 0;
    const isColumnHeader = cell.tagName === "TH" && isMatrixColumnHeadCell(cell);
    const mapDomToLayout = kind === "percent" || isColumnHeader;
    const layoutCol = mapDomToLayout ? domMatrixColToLayoutCol(coords.c, meta, headerLen) : coords.c;
    page.cells = page.cells || {};
    page.cells[key] = {
      colIndex: layoutCol,
      domColIndex: coords.c,
      layoutColIndex: mapDomToLayout ? layoutCol : undefined,
      rowLabel: rowLabelForCell(cell),
      text: String(text || ""),
      kind,
      isColumnHeader,
      rowAxisKey: inferRowAxisKeyFromPage(pageKey),
      pageFilters: {
        setor: filters.setor || "",
        bloco: filters.bloco || "",
        pavimento: filters.pavimento || "",
      },
      dataRowIndex: layoutDataRowIndexFromCell(cell),
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

    // O recorte ativo manda na camada efetiva. Evita matrix_mode residual
    // causar contexto estrutural errado (ex.: deletar apto como pavimento/bloco).
    if (s.bloco && s.pavimento) return "apto";
    if (s.bloco) return "pavimento";
    if (r === "apto" || r === "pavimento" || r === "bloco") return "bloco";
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

  /**
   * Recorte pai (setor/bloco/pavimento) ao aplicar patch de célula.
   * Célula vazia no eixo não invalida a linha (layout esparso no recorte de UND).
   */
  function rowMatchesParentScope(row, axisMap, pageFilters, rowAxisKey) {
    const scope = pageFilters && typeof pageFilters === "object" ? pageFilters : {};
    const ctx = {
      setor: String(scope.setor || "").trim(),
      bloco: String(scope.bloco || "").trim(),
      pavimento: String(scope.pavimento || "").trim(),
      level: rowAxisKey || "apto",
    };
    const parentF = parentFiltersForStructuralLevel(ctx);
    return Object.entries(parentF).every(([key, value]) => {
      const idx = axisMap[key];
      if (!Number.isInteger(idx)) return true;
      const rowVal = String(row[idx] || "").trim();
      const wanted = String(value || "").trim();
      if (!wanted) return true;
      if (!rowVal) return false;
      return rowVal === wanted;
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

  function resolveLayoutRowIndexForPatch(
    rows,
    axisMap,
    pageFilters,
    rowLabel,
    axisKey,
    domBodyRowIndex,
    colIndex
  ) {
    if (!Array.isArray(rows) || rows.length < 2) return null;
    const matchesScope = (row) => rowMatchesParentScope(row, axisMap, pageFilters, axisKey);
    const levelIdx = Number.isInteger(axisMap[axisKey]) ? axisMap[axisKey] : primaryAxisIndex(axisMap);
    const label = String(rowLabel || "").trim();
    const labelNorm = label.toLowerCase();
    const scoped = [];
    for (let ri = 1; ri < rows.length; ri += 1) {
      const row = rows[ri];
      if (Array.isArray(row) && matchesScope(row)) scoped.push(ri);
    }
    if (!scoped.length) return null;

    const isStructuralCol = [axisMap.setor, axisMap.bloco, axisMap.pavimento, axisMap.apto]
      .filter(Number.isInteger)
      .includes(colIndex);
    if (
      !isStructuralCol &&
      Number.isInteger(domBodyRowIndex) &&
      domBodyRowIndex >= 0 &&
      domBodyRowIndex < scoped.length
    ) {
      return scoped[domBodyRowIndex];
    }

    if (label && Number.isInteger(levelIdx)) {
      for (const ri of scoped) {
        const cellLabel = String(rows[ri][levelIdx] || "").trim();
        if (cellLabel === label || cellLabel.toLowerCase() === labelNorm) return ri;
      }
    }

    if (scoped.length === 1) return scoped[0];
    return null;
  }

  function enrichLayoutRowForPercent(row, axisMap, pageFilters, rowLabel, axisKey) {
    if (!Array.isArray(row)) return;
    const pf = pageFilters && typeof pageFilters === "object" ? pageFilters : {};
    [["setor", pf.setor], ["bloco", pf.bloco], ["pavimento", pf.pavimento]].forEach(([key, val]) => {
      const idx = axisMap[key];
      const v = String(val || "").trim();
      if (Number.isInteger(idx) && v && !String(row[idx] || "").trim()) {
        row[idx] = v;
      }
    });
    const label = String(rowLabel || "").trim();
    const levelIdx = axisMap[axisKey];
    if (label && Number.isInteger(levelIdx) && !String(row[levelIdx] || "").trim()) {
      row[levelIdx] = label;
    }
  }

  function applyCellTextToLayoutRows(rows, axisMap, filters, rowLabel, colIndex, text, rowAxisKey, patchMeta) {
    if (!Array.isArray(rows) || !Number.isInteger(colIndex)) return false;
    const meta = patchMeta && typeof patchMeta === "object" ? patchMeta : {};
    const pageFilters =
      meta.pageFilters && typeof meta.pageFilters === "object" ? meta.pageFilters : filters;
    const label = String(rowLabel || "").trim();
    const axisKey = rowAxisKey || meta.rowAxisKey || "apto";
    const levelIdx = Number.isInteger(axisMap[axisKey]) ? axisMap[axisKey] : primaryAxisIndex(axisMap);
    const domBodyRowIndex = Number.isInteger(meta.dataRowIndex) ? meta.dataRowIndex : null;
    const matchesScope = (row) => rowMatchesParentScope(row, axisMap, pageFilters, axisKey);

    if (meta.kind === "structural" && meta.isColumnHeader) {
      if (!rows.length || !Array.isArray(rows[0])) return false;
      const header = rows[0];
      const title = String(text || "").trim().replace(/%$/, "");
      while (header.length <= colIndex) header.push("");
      header[colIndex] = title;
      return true;
    }

    const writeCell = (row) => {
      if (!Array.isArray(row)) return false;
      while (row.length <= colIndex) row.push("");
      if (meta.kind === "structural" && colIndex === 0 && Number.isInteger(levelIdx)) {
        const title = String(text || "").trim().replace(/%$/, "");
        row[levelIdx] = title;
        return true;
      }
      if (meta.kind === "percent") {
        enrichLayoutRowForPercent(row, axisMap, pageFilters, label, axisKey);
      }
      row[colIndex] = text;
      return true;
    };

    // Em camada de unidade, uma linha visível pode representar várias linhas-fonte.
    // Atualiza todas as linhas da mesma unidade no escopo para evitar média "pela metade".
    if (meta.kind === "percent" && label && Number.isInteger(levelIdx)) {
      let updated = 0;
      for (let ri = 1; ri < rows.length; ri += 1) {
        const row = rows[ri];
        if (!Array.isArray(row)) continue;
        if (!matchesScope(row)) continue;
        if (String(row[levelIdx] || "").trim() !== label) continue;
        if (writeCell(row)) updated += 1;
      }
      if (updated > 0) return true;
    }

    const layoutRi = resolveLayoutRowIndexForPatch(
      rows,
      axisMap,
      pageFilters,
      label,
      axisKey,
      domBodyRowIndex,
      colIndex,
    );
    if (layoutRi != null) {
      return writeCell(rows[layoutRi]);
    }

    if (label) {
      for (let ri = 1; ri < rows.length; ri += 1) {
        const row = rows[ri];
        if (!Array.isArray(row)) continue;
        if (!matchesScope(row)) continue;
        if (String(row[levelIdx] || "").trim() !== label) continue;
        return writeCell(row);
      }
    }
    return false;
  }

  function mergeCellPatchesIntoLayoutRows(dataRows, axisMap, pages, meta) {
    let applied = 0;
    let missed = 0;
    let aptoPercentExpected = 0;
    let aptoPercentMissed = 0;
    const headerLen = Array.isArray(dataRows) && dataRows.length ? dataRows[0].length : state.layoutHeaderLen;
    Object.entries(pages || {}).forEach(([pageKey, pageDraft]) => {
      if (!pageDraft) return;
      const texts = pageDraft.text || {};
      const cells = pageDraft.cells || {};
      const keys = new Set([...Object.keys(texts), ...Object.keys(cells)]);
      keys.forEach((key) => {
        const patch = cells[key] || {};
        const kind = patch.kind || (Number(patch.colIndex) === 0 ? "structural" : "percent");
        if (kind === "percent" && !isAptoUndManualEntryLayer(pageKey)) {
          return;
        }
        let colIndex = Number.isInteger(patch.colIndex) ? patch.colIndex : null;
        if (kind === "percent") {
          colIndex = layoutColIndexForPercentPatch(patch, meta, headerLen);
          aptoPercentExpected += 1;
        }
        const rowLabel = patch.rowLabel != null ? String(patch.rowLabel).trim() : "";
        let text = texts[key] != null ? String(texts[key]) : patch.text != null ? String(patch.text) : "";
        if (colIndex == null) {
          if (kind === "percent") aptoPercentMissed += 1;
          missed += 1;
          return;
        }
        if (!rowLabel && !Number.isInteger(patch.dataRowIndex)) {
          if (kind === "percent") aptoPercentMissed += 1;
          missed += 1;
          return;
        }
        if (kind === "percent" && isAptoUndManualEntryLayer(pageKey)) {
          text = normalizePercentLayoutValue(text);
        }
        const filters = parsePageFilters(pageKey);
        const ok = applyCellTextToLayoutRows(
          dataRows,
          axisMap,
          filters,
          rowLabel,
          colIndex,
          text,
          patch.rowAxisKey || inferRowAxisKeyFromPage(pageKey),
          patch,
        );
        if (ok) applied += 1;
        else {
          missed += 1;
          if (kind === "percent") aptoPercentMissed += 1;
        }
      });
    });
    poMapaDebug("merge cell patches", { applied, missed, aptoPercentExpected, aptoPercentMissed });
    return { applied, missed, aptoPercentExpected, aptoPercentMissed };
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
    if (!title || isPlaceholderRowLabel(title)) return false;
    const levelIdx = axisMap[context.level];
    if (!Number.isInteger(levelIdx)) {
      poMapaDebug("applyCreateRowToLayout falhou: eixo inválido", { context, axisMap });
      return false;
    }
    if (layoutHasStructuralRow(rows, axisMap, context, title)) return false;
    const newRow = newCanonicalLayoutRow(header, axisMap, context, title);
    let insertAt = rows.length;

    if (context.level === "bloco") {
      // Novo bloco: mantém append no fim.
      insertAt = rows.length;
    } else if (context.level === "pavimento") {
      // Novo pavimento: após a última linha do bloco.
      const blocoIdx = axisMap.bloco;
      const blocoVal = String(context.bloco || "").trim();
      if (Number.isInteger(blocoIdx) && blocoVal) {
        for (let ri = rows.length - 1; ri >= 1; ri -= 1) {
          const row = rows[ri];
          if (!Array.isArray(row)) continue;
          if (String(row[blocoIdx] || "").trim() === blocoVal) {
            insertAt = ri + 1;
            break;
          }
        }
      }
    } else if (context.level === "apto") {
      // Novo apto: após a última linha de bloco+pavimento.
      const blocoIdx = axisMap.bloco;
      const pavimentoIdx = axisMap.pavimento;
      const blocoVal = String(context.bloco || "").trim();
      const pavimentoVal = String(context.pavimento || "").trim();
      if (Number.isInteger(blocoIdx) && Number.isInteger(pavimentoIdx) && blocoVal && pavimentoVal) {
        for (let ri = rows.length - 1; ri >= 1; ri -= 1) {
          const row = rows[ri];
          if (!Array.isArray(row)) continue;
          if (
            String(row[blocoIdx] || "").trim() === blocoVal &&
            String(row[pavimentoIdx] || "").trim() === pavimentoVal
          ) {
            insertAt = ri + 1;
            break;
          }
        }
      }
    }

    rows.splice(insertAt, 0, newRow);
    return true;
  }

  function applyDeleteRowToLayout(rows, axisMap, context, label) {
    const want = String(label || "").trim();
    if (!want) return;
    let level = String((context && context.level) || "").trim();
    const blocoScope = String((context && context.bloco) || "").trim();
    const pavScope = String((context && context.pavimento) || "").trim();
    // Dentro de um bloco (recorte na URL), a linha apagada é pavimento — não usar cascata de bloco.
    if (level === "bloco" && blocoScope && !pavScope) {
      level = "pavimento";
    }
    const levelIdx = axisMap[level];
    if (!Number.isInteger(levelIdx)) return;
    const parentF = parentFiltersForStructuralLevel({ ...context, level });
    const remove = [];
    const pavIdx = axisMap.pavimento;
    const lastAxis = { setor: "", bloco: "", pavimento: "" };
    for (let ri = 1; ri < rows.length; ri += 1) {
      const row = rows[ri];
      if (!Array.isArray(row)) continue;
      ["setor", "bloco", "pavimento"].forEach((key) => {
        const idx = axisMap[key];
        if (!Number.isInteger(idx)) return;
        const val = String(row[idx] || "").trim();
        if (val) {
          if (key === "setor" && val !== lastAxis.setor) {
            lastAxis.bloco = "";
            lastAxis.pavimento = "";
          } else if (key === "bloco" && val !== lastAxis.bloco) {
            lastAxis.pavimento = "";
          }
          lastAxis[key] = val;
        }
      });
      if (level === "bloco" && !blocoScope) {
        if (
          (!Object.keys(parentF).length || rowMatchesFilters(row, axisMap, parentF)) &&
          String(row[levelIdx] || "").trim() === want
        ) {
          remove.push(ri);
        }
        continue;
      }
      if (Object.keys(parentF).length && !rowMatchesFilters(row, axisMap, parentF)) continue;
      if (level === "pavimento" && isStructuralRowAtLevel(row, axisMap, "bloco")) continue;
      let matches = String(row[levelIdx] || "").trim() === want;
      if (!matches && level === "pavimento" && Number.isInteger(pavIdx)) {
        const pavVal = String(row[pavIdx] || "").trim();
        matches = (pavVal || lastAxis.pavimento || "") === want;
      }
      if (matches) remove.push(ri);
    }
    remove.sort((a, b) => b - a).forEach((ri) => rows.splice(ri, 1));

    const blocoIdx = axisMap.bloco;
    const hasBlocoIdx = Number.isInteger(blocoIdx);
    const hasPavIdx = Number.isInteger(pavIdx);
    const headerLen = Array.isArray(rows[0]) ? rows[0].length : 0;
    if (!headerLen) return;

    // Se a exclusão de apto zerou o pavimento, preserva a linha estrutural do pavimento.
    if (level === "apto" && blocoScope && pavScope && hasBlocoIdx && hasPavIdx) {
      const hasAnyRowInPav = rows.slice(1).some((row) => {
        if (!Array.isArray(row)) return false;
        return (
          String(row[blocoIdx] || "").trim() === blocoScope &&
          String(row[pavIdx] || "").trim() === pavScope
        );
      });
      if (!hasAnyRowInPav) {
        const structural = new Array(headerLen).fill("");
        structural[blocoIdx] = blocoScope;
        structural[pavIdx] = pavScope;
        rows.push(structural);
      }
    }

    // Se a exclusão de pavimento zerou o bloco, preserva a linha estrutural do bloco.
    if (level === "pavimento" && blocoScope && hasBlocoIdx) {
      const hasAnyRowInBloco = rows.slice(1).some((row) => {
        if (!Array.isArray(row)) return false;
        return String(row[blocoIdx] || "").trim() === blocoScope;
      });
      if (!hasAnyRowInBloco) {
        const structural = new Array(headerLen).fill("");
        structural[blocoIdx] = blocoScope;
        rows.push(structural);
      }
    }
  }

  function applyMoveRowToLayout(rows, axisMap, context, label, fromOrder, toOrder, meta) {
    const siblingIdxs = collectStructuralSiblingRowIndices(rows, axisMap, context);
    if (siblingIdxs.length < 2) return;
    const fromPos = clampIndex(Number(fromOrder), 0, siblingIdxs.length - 1);
    const toPos = clampIndex(Number(toOrder), 0, siblingIdxs.length - 1);
    if (fromPos === toPos) return;
    const orderedRows = siblingIdxs.map((ri) => rows[ri]);
    const [moved] = orderedRows.splice(fromPos, 1);
    orderedRows.splice(toPos, 0, moved);
    void label;
    void moved;
    const removeSet = new Set(siblingIdxs);
    for (let ri = rows.length - 1; ri >= 1; ri -= 1) {
      if (removeSet.has(ri)) rows.splice(ri, 1);
    }
    const anchorRi = siblingIdxs[0];
    orderedRows.forEach((row, offset) => {
      rows.splice(anchorRi + offset, 0, row);
    });
    syncRowOrderInMeta(meta, context, orderedRows, axisMap);
  }

  function domActivityColToLayoutIndex(domCol, meta, headerLen) {
    const dom = Number(domCol);
    if (!Number.isInteger(dom) || dom < 1) return null;
    const activityCols = activityColsFromMeta(meta, headerLen);
    const pos = dom - 1;
    if (pos < 0 || pos >= activityCols.length) return null;
    return activityCols[pos];
  }

  function bumpLayoutColIndicesAfter(cols, at, delta) {
    if (!delta) return cols;
    return cols.map((ci) => (Number(ci) >= at ? Number(ci) + delta : Number(ci)));
  }

  function applyCreateColumnToLayout(rows, op, meta) {
    const header = rows[0];
    if (!Array.isArray(header) || header.length < 2) return;
    const headerLen = header.length;
    const activityCols = activityColsFromMeta(meta, headerLen);
    const domIdx = clampIndex(Number(op.index), 1, activityCols.length || 1);
    const actPos = domIdx - 1;
    const layoutIdx =
      actPos < activityCols.length
        ? activityCols[actPos]
        : headerLen > 1
          ? headerLen - 1
          : headerLen;
    const title = String(op.label || "Nova coluna").trim() || "Nova coluna";
    header.splice(layoutIdx, 0, title);
    for (let ri = 1; ri < rows.length; ri += 1) {
      if (!Array.isArray(rows[ri])) continue;
      rows[ri].splice(layoutIdx, 0, "");
    }
    if (meta && typeof meta === "object") {
      const nextCols = bumpLayoutColIndicesAfter(activityCols, layoutIdx, 1);
      nextCols.splice(actPos, 0, layoutIdx);
      meta.activity_cols_interpreted = nextCols;
      meta.activity_headers_interpreted = nextCols.map((ci) =>
        String(header[ci] != null ? header[ci] : "").trim(),
      );
    }
  }

  function applyDeleteColumnToLayout(rows, op, meta) {
    const header = rows[0];
    if (!Array.isArray(header) || header.length < 2) return;
    const headerLen = header.length;
    const activityCols = activityColsFromMeta(meta, headerLen);
    const layoutIdx = domActivityColToLayoutIndex(Number(op.index), meta, headerLen);
    if (!Number.isInteger(layoutIdx) || layoutIdx < 0 || layoutIdx >= headerLen) return;
    header.splice(layoutIdx, 1);
    for (let ri = 1; ri < rows.length; ri += 1) {
      if (!Array.isArray(rows[ri])) continue;
      if (layoutIdx < rows[ri].length) rows[ri].splice(layoutIdx, 1);
    }
    if (meta && typeof meta === "object") {
      const actPos = Number(op.index) - 1;
      const nextCols = activityCols
        .filter((ci) => ci !== layoutIdx)
        .map((ci) => (Number(ci) > layoutIdx ? Number(ci) - 1 : Number(ci)));
      if (actPos >= 0 && actPos < activityCols.length) {
        meta.activity_cols_interpreted = nextCols;
        meta.activity_headers_interpreted = nextCols.map((ci) =>
          String(header[ci] != null ? header[ci] : "").trim(),
        );
      }
    }
  }

  /** Reordena só colunas de atividade no layout (índices DOM ≠ índices do layout canônico). */
  function applyMoveColumnToLayout(rows, op, meta) {
    const header = rows[0];
    if (!Array.isArray(header) || header.length < 2) return;
    const headerLen = header.length;
    const activityCols = activityColsFromMeta(meta, headerLen);
    if (activityCols.length < 2) return;

    const fromPos = Number(op.from) - 1;
    const toPos = Number(op.to) - 1;
    if (
      !Number.isInteger(fromPos) ||
      !Number.isInteger(toPos) ||
      fromPos < 0 ||
      toPos < 0 ||
      fromPos >= activityCols.length ||
      toPos >= activityCols.length ||
      fromPos === toPos
    ) {
      return;
    }

    const reorderedActivityCols = activityCols.slice();
    const [removedCol] = reorderedActivityCols.splice(fromPos, 1);
    reorderedActivityCols.splice(toPos, 0, removedCol);

    if (meta && typeof meta === "object") {
      meta.activity_cols_interpreted = reorderedActivityCols.slice();
      meta.activity_headers_interpreted = reorderedActivityCols.map((ci) =>
        String(header[ci] != null ? header[ci] : "").trim(),
      );
    }

    const reorderRow = (row) => {
      if (!Array.isArray(row)) return;
      const values = activityCols.map((ci) => (ci < row.length ? row[ci] : ""));
      const [item] = values.splice(fromPos, 1);
      values.splice(toPos, 0, item);
      reorderedActivityCols.forEach((ci, i) => {
        while (row.length <= ci) row.push("");
        row[ci] = values[i];
      });
    };

    reorderRow(header);
    for (let ri = 1; ri < rows.length; ri += 1) reorderRow(rows[ri]);
  }

  function structuralOpDedupeKey(op) {
    if (!op || typeof op !== "object") return "";
    if (op.type === "create_row") {
      const c = op.context || {};
      return ["create_row", c.level, c.setor, c.bloco, c.pavimento, op.label].join("|");
    }
    if (op.type === "move_column") {
      return ["move_column", op.from, op.to].join("|");
    }
    if (op.type === "move_row") {
      const c = op.context || {};
      return ["move_row", c.level, c.setor, c.bloco, c.pavimento, op.from, op.to].join("|");
    }
    if (op.type === "delete_row") {
      const c = op.context || {};
      return ["delete_row", c.level, c.setor, c.bloco, c.pavimento, op.label || ""].join("|");
    }
    if (op.type === "delete_column") return ["delete_column", op.index, op.label || ""].join("|");
    if (op.type === "create_column") return ["create_column", op.index, op.label || ""].join("|");
    return "";
  }

  function isStructuralRowAtLevel(row, axisMap, level) {
    if (!Array.isArray(row) || !level) return false;
    const levelIdx = axisMap[level];
    if (!Number.isInteger(levelIdx)) return false;
    if (!String(row[levelIdx] || "").trim()) return false;
    const childAxes =
      level === "bloco" ? ["pavimento", "apto"] : level === "pavimento" ? ["apto"] : [];
    for (let i = 0; i < childAxes.length; i += 1) {
      const childIdx = axisMap[childAxes[i]];
      if (Number.isInteger(childIdx) && String(row[childIdx] || "").trim()) return false;
    }
    return true;
  }

  function collectStructuralSiblingRowIndices(rows, axisMap, context) {
    const parentF = parentFiltersForStructuralLevel(context);
    const level = context && context.level;
    const idxs = [];
    for (let ri = 1; ri < rows.length; ri += 1) {
      const row = rows[ri];
      if (!Array.isArray(row)) continue;
      if (Object.keys(parentF).length && !rowMatchesFilters(row, axisMap, parentF)) continue;
      if (!isStructuralRowAtLevel(row, axisMap, level)) continue;
      idxs.push(ri);
    }
    return idxs;
  }

  function syncRowOrderInMeta(meta, context, orderedRows, axisMap) {
    if (!meta || typeof meta !== "object" || !context || !context.level) return;
    const levelIdx = axisMap[context.level];
    if (!Number.isInteger(levelIdx)) return;
    const labels = orderedRows
      .map((row) => String(row[levelIdx] || "").trim())
      .filter((lbl) => lbl && !isPlaceholderRowLabel(lbl));
    if (!labels.length) return;
    meta[`row_order_${context.level}`] = labels;
  }

  function normalizeLegacyStructuralOp(op, pageKey) {
    if (!op || typeof op !== "object") return null;
    const context = buildStructuralRowContext(pageKey);
    if (op.type === "insert_row") {
      return { type: "create_row", context, label: op.label, order: op.index };
    }
    if (op.type === "create_row" && op.context) return op;
    if (op.type === "move_col") {
      return { type: "move_column", from: op.from, to: op.to };
    }
    if (op.type === "insert_col") {
      return { type: "create_column", index: op.index, label: op.label };
    }
    if (op.type === "delete_col") {
      return { type: "delete_column", index: op.index, label: op.label || "" };
    }
    if (op.type === "move_row") {
      return {
        type: "move_row",
        context: op.context || context,
        label: op.label || "",
        from: op.from,
        to: op.to,
      };
    }
    return null;
  }

  /**
   * Compatibilidade: converte operações legadas em structuralOps e limpa o bucket antigo.
   * Mantém suporte a rascunhos locais antigos sem continuar proliferando "ops".
   */
  function migrateLegacyOpsInPage(pageKey, pageDraft) {
    if (!pageDraft || !Array.isArray(pageDraft.ops) || !pageDraft.ops.length) return;
    if (!Array.isArray(pageDraft.structuralOps)) pageDraft.structuralOps = [];
    let changed = false;
    pageDraft.ops.forEach((op) => {
      const normalized = normalizeLegacyStructuralOp(op, pageKey);
      if (!normalized) return;
      const key = structuralOpDedupeKey(normalized);
      if (!key) return;
      const exists = pageDraft.structuralOps.some((item) => structuralOpDedupeKey(item) === key);
      if (exists) return;
      pageDraft.structuralOps.push(normalized);
      changed = true;
    });
    if (changed) {
      pageDraft.ops = [];
    }
  }

  function gatherStructuralOpsForMerge(pages, axisMap) {
    const seen = new Set();
    const list = [];
    Object.entries(pages || {}).forEach(([pageKey, draft]) => {
      if (!draft || !canPersistStructuralLayoutOps(pageKey)) return;
      migrateLegacyOpsInPage(pageKey, draft);
      const push = (op) => {
        if (!op || typeof op !== "object") return;
        if (op.type === "create_row") {
          if (!isValidStructuralCreateOp(op)) return;
        }
        const key = structuralOpDedupeKey(op);
        if (key) {
          if (seen.has(key)) return;
          seen.add(key);
        }
        list.push(op);
      };
      (draft.structuralOps || []).forEach(push);
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
            if (label && !isPlaceholderRowLabel(label)) {
              push({ type: "create_row", context, label });
            }
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
      const ok = applyCreateRowToLayout(rows, axisMap, context, op.label);
      if (!ok) {
        poMapaDebug("applyCreateRowToLayout não aplicou", { op, axisMap, context });
      }
    });
    deletes.forEach((op) => {
      applyDeleteRowToLayout(rows, axisMap, op.context || {}, op.label);
    });
    const layoutMeta =
      data.importMeta && typeof data.importMeta === "object" ? data.importMeta : {};
    moves.forEach((op) => {
      applyMoveRowToLayout(rows, axisMap, op.context || {}, op.label, op.from, op.to, layoutMeta);
    });
    colCreates.forEach((op) => applyCreateColumnToLayout(rows, op, layoutMeta));
    colDeletes.forEach((op) => applyDeleteColumnToLayout(rows, op, layoutMeta));
    colMoves.forEach((op) => applyMoveColumnToLayout(rows, op, layoutMeta));

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

  /** Remove % gravados em telas bloco/pavimento do rascunho local (não persistem no servidor). */
  function pruneStalePercentPatchesFromDraft() {
    const currentKey = currentPageKey();
    Object.entries(state.draft.pages || {}).forEach(([pageKey, pageDraft]) => {
      if (!pageDraft || pageKey === currentKey || isAptoUndManualEntryLayer(pageKey)) return;
      const cells = pageDraft.cells || {};
      const texts = pageDraft.text || {};
      Object.entries(cells).forEach(([cellKey, patch]) => {
        if (!patch || patch.kind !== "percent") return;
        delete cells[cellKey];
        delete texts[cellKey];
      });
    });
  }

  function mergeAllDraftsIntoLayout(layout) {
    const next = layout && typeof layout === "object" ? layout : { sections: [] };
    const sections = Array.isArray(next.sections) ? next.sections : [];
    const pages = state.draft.pages || {};
    const cellPatchStats = { applied: 0, missed: 0, aptoPercentExpected: 0, aptoPercentMissed: 0 };
    sections.forEach((section) => {
      const data = section && section.data;
      if (!data || !Array.isArray(data.rows) || !data.rows.length) return;
      const header = data.rows[0];
      const meta = data.importMeta && typeof data.importMeta === "object" ? data.importMeta : {};
      const axisMap = buildAxisMapFromMeta(meta, header);
      const rowsBefore = data.rows.length;

      const structuralOps = gatherStructuralOpsForMerge(pages, axisMap);
      if (structuralOps.length) {
        applyStructuralOpsToLayoutData(data, axisMap, structuralOps);
      }

      const patchMerge = mergeCellPatchesIntoLayoutRows(data.rows, axisMap, pages, meta);
      cellPatchStats.applied += patchMerge.applied;
      cellPatchStats.missed += patchMerge.missed;
      cellPatchStats.aptoPercentExpected += patchMerge.aptoPercentExpected || 0;
      cellPatchStats.aptoPercentMissed += patchMerge.aptoPercentMissed || 0;

      forwardFillHierarchyAxesInLayout(data, axisMap);
      purgeInvalidStructuralLayoutRows(data, axisMap);
      purgeRedundantEmptyUnitSlots(data, axisMap);
      purgeDuplicateAptoRowsWithoutActivity(data, axisMap);

      poMapaDebug("merge layout seção", {
        rowsAntes: rowsBefore,
        rowsDepois: data.rows.length,
        structuralOps: structuralOps.length,
        cellPatches: patchMerge,
        pages: Object.keys(pages).length,
      });
    });
    next.__poCellPatchStats = cellPatchStats;
    return next;
  }

  function clearCellSelectionAndToolbar() {
    finishInlineEdit({ commit: false });
    if (state.selectedCell) {
      state.selectedCell.style.outline = "";
      state.selectedCell.style.outlineOffset = "";
    }
    state.selectedCell = null;
    state.selectedKey = "";
    if (inpText) inpText.value = "";
    refreshToolbarEditState();
    refreshMoveButtons();
  }

  function applyToolbarValueToSelectedCell(normalizedValue) {
    if (!state.selectedCell || !state.selectedKey) return;
    const value = String(normalizedValue || "");
    const page = ensurePageDraft(currentPageKey());
    textNodeForCell(state.selectedCell).textContent = value;
    page.text[state.selectedKey] = value;
    rememberCellPatch(state.selectedCell, state.selectedKey, value);
    if (inpText) inpText.value = value;
    markDirty();
    if (patchKindForCell(state.selectedCell) === "percent") {
      refreshPercentCellAfterValueChange(state.selectedCell, value);
    }
  }

  function isInvalidPercentToolbarInput(rawValue) {
    const trimmed = String(rawValue || "").trim();
    if (!trimmed) return false;
    if (isPercentNotApplicableText(trimmed)) return false;
    if (trimmed.includes("%")) return false;
    return !/^-?\d+(?:[.,]\d+)?$/.test(trimmed);
  }

  /** Aplica valor pendente da toolbar na célula antes do save (não exige botão Aplicar). */
  function flushPendingToolbarEditBeforeSave() {
    if (!state.enabled) return true;
    finishInlineEdit({ commit: true });

    if (!state.selectedCell || !state.selectedKey) return true;

    const doc = frame.contentDocument;
    if (!doc || !doc.contains(state.selectedCell)) {
      clearCellSelectionAndToolbar();
      return true;
    }

    const canPercent = canEditPercentCell(state.selectedCell, { silent: true });
    const canStructural = canEditStructuralCell(state.selectedCell);
    const rawInput = inpText ? String(inpText.value || "") : "";

    if (!canPercent && !canStructural) {
      if (rawInput.trim() && isMatrixPercentDataCell(state.selectedCell)) {
        showBlockedPercentEditMessage();
        return false;
      }
      return true;
    }

    if (canPercent && isInvalidPercentToolbarInput(rawInput)) {
      updateStatus("Valor de percentual inválido. Use número (ex.: 10 ou 10%) ou \"-\" para não aplicável.");
      return false;
    }

    const value = normalizeCellText(state.selectedCell, rawInput);
    const currentDisplay = normalizeCellText(
      state.selectedCell,
      String(textNodeForCell(state.selectedCell).textContent || ""),
    );
    if (value !== currentDisplay || rawInput.trim()) {
      applyToolbarValueToSelectedCell(value);
    } else if (canPercent) {
      refreshMatrixTotalsDisplay();
    }
    try {
      window.localStorage.setItem(storageKey, JSON.stringify(state.draft));
    } catch (e) {
      void e;
    }
    poMapaDebug("flush toolbar pré-save", {
      pageKey: currentPageKey(),
      cellKey: state.selectedKey,
      rowLabel: rowLabelForCell(state.selectedCell),
      value,
      patches: Object.keys((state.draft.pages[currentPageKey()] || {}).cells || {}).length,
    });
    return true;
  }

  async function saveDraftToServer(options) {
    const cfg = options && typeof options === "object" ? options : {};
    const isAuto = !!cfg.auto;
    const shouldReload = cfg.reload === true || (!isAuto && cfg.reload !== false);

    if (!ctx.ambienteId || !ctx.endpoints || !ctx.endpoints.saveDraft) {
      if (!flushPendingToolbarEditBeforeSave()) return;
      saveDraftToStorage(isAuto);
      return;
    }
    if (draftHasUnpersistedStructuralLayoutOps()) {
      if (!isAuto) {
        const proceed = window.confirm(STRUCTURAL_OPS_SAVE_WARN_MSG);
        if (!proceed) {
          updateStatus(
            "Salvamento cancelado. Abra um bloco ou pavimento para gravar linhas/colunas no servidor.",
          );
          return;
        }
      }
    }
    if (!flushPendingToolbarEditBeforeSave()) return;
    if (state.autoSaveBlocked) return;
    updateStatus(isAuto ? "Salvando automaticamente..." : "Salvando no servidor...");
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
      cacheLayoutFromExtracted(extractLayoutMatrixFromLayout(layoutIn));
      const pageKeyNow = currentPageKey();
      const structuralOpsPreSave = gatherStructuralOpsForMerge(
        state.draft.pages || {},
        extractLayoutMatrixFromLayout(layoutIn).axisMap,
      );
      poMapaDebug("save trace pré-merge", {
        pageKey: pageKeyNow,
        contexto: getMatrixEditContext(pageKeyNow),
        structuralOps: structuralOpsPreSave,
        draftPages: Object.keys(state.draft.pages || {}),
        domDataRows: listMatrixTbodyRows(frame.contentDocument?.querySelector(".matrix-table tbody")).length,
      });
      poMapaDebug("save servidor início", {
        pageKey: pageKeyNow,
        contexto: getMatrixEditContext(),
        rowsLayout: (layoutIn.sections && layoutIn.sections[0] && layoutIn.sections[0].data && layoutIn.sections[0].data.rows || []).length,
      });
      pruneStalePercentPatchesFromDraft();
      const pagesSnapshot = JSON.parse(JSON.stringify(state.draft.pages || {}));
      const { axisMap: axisMapIn } = extractLayoutMatrixFromLayout(layoutIn);
      const structuralOpsSnapshot = gatherStructuralOpsForMerge(pagesSnapshot, axisMapIn);

      const layout = mergeAllDraftsIntoLayout(layoutIn);
      const cellPatchStats = layout.__poCellPatchStats || {
        applied: 0,
        missed: 0,
        aptoPercentExpected: 0,
        aptoPercentMissed: 0,
      };
      if (cellPatchStats.aptoPercentExpected > 0 && cellPatchStats.aptoPercentMissed > 0) {
        state.autoSaveBlocked = true;
        if (autoSaveTimer) {
          window.clearTimeout(autoSaveTimer);
          autoSaveTimer = 0;
        }
        throw new Error(
          "Os percentuais editados não foram aplicados ao layout antes do envio. Recarregue a página e tente salvar novamente.",
        );
      }
      const { rows: rowsMerged } = extractLayoutMatrixFromLayout(layout);
      const layoutRowsDebug = layoutStructuralRowsForDebug(layout);
      const missingInPayload = verifyCreateRowsInLayout(layout, structuralOpsSnapshot);
      poMapaDebug("save servidor layout merge", {
        rowsLayout: rowsMerged.length,
        structuralOps: structuralOpsSnapshot.length,
        missingInPayload: missingInPayload.map((o) => o.label),
        structuralOpsLista: structuralOpsSnapshot,
        layoutRows: layoutRowsDebug,
        temPlaceholderNoLayout: layoutRowsDebug.some(
          (r) =>
            isPlaceholderRowLabel(r.bloco) ||
            isPlaceholderRowLabel(r.pavimento) ||
            isPlaceholderRowLabel(r.apto),
        ),
      });
      if (missingInPayload.length) {
        const labels = missingInPayload.map((o) => o.label).join(", ");
        throw new Error(
          `As linhas criadas não foram aplicadas ao layout antes do envio (${labels}). Recarregue a página e tente novamente.`,
        );
      }
      const placeholderInLayout = layoutRowsDebug.some(
        (r) =>
          isPlaceholderRowLabel(r.bloco) ||
          isPlaceholderRowLabel(r.pavimento) ||
          isPlaceholderRowLabel(r.apto),
      );
      if (placeholderInLayout) {
        throw new Error(
          'O layout contém linha inválida "Sem dados para matriz". O rascunho local foi mantido.',
        );
      }
      delete layout.__poCellPatchStats;
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

      if (!isAuto) {
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
        poMapaDebug("save servidor verificação GET", {
          ok: verifyRes.ok,
          rowsPersistidas: extractLayoutMatrixFromLayout(savedLayout).rows.length,
          missingAfterSave: missingAfterSave.map((o) => o.label),
          layoutRows: layoutStructuralRowsForDebug(savedLayout),
        });
        if (missingAfterSave.length) {
          throw new Error(
            "O servidor não confirmou as linhas criadas no layout. O rascunho local foi mantido.",
          );
        }
        cacheLayoutFromExtracted(extractLayoutMatrixFromLayout(savedLayout));
      }

      const keepEditEnabled = state.enabled;
      const hadUnpersistedStructuralOps = draftHasUnpersistedStructuralLayoutOps();
      state.dirty = false;
      state.autoSaveBlocked = false;
      state.draft = { pages: {} };
      try {
        window.localStorage.removeItem(storageKey);
      } catch (e) {
        void e;
      }
      if (hadUnpersistedStructuralOps) {
        updateStatus(
          isAuto
            ? "Texto e cores salvos. Linhas/colunas desta camada permanecem só no rascunho local."
            : "Mapa salvo. Algumas alterações estruturais não foram enviadas ao servidor.",
        );
      } else {
        updateStatus(isAuto ? "Alterações salvas automaticamente." : "Mapa salvo no servidor.");
      }
      if (!shouldReload) {
        refreshMatrixTotalsDisplay();
      }
      if (shouldReload) {
        clearCellSelectionAndToolbar();
        state.restoreEditOnNextLoad = keepEditEnabled;
        frame.contentWindow.location.reload();
      }
    } catch (err) {
      const msg = err && err.message ? err.message : "Erro ao salvar no servidor.";
      updateStatus(msg);
      if (!state.autoSaveBlocked) {
        state.autoSaveBlocked = true;
        if (autoSaveTimer) {
          window.clearTimeout(autoSaveTimer);
          autoSaveTimer = 0;
        }
      }
      throw err;
    }
  }

  function saveDraftToStorage(isAuto) {
    if (!flushPendingToolbarEditBeforeSave()) return;
    try {
      window.localStorage.setItem(storageKey, JSON.stringify(state.draft));
      state.dirty = false;
      updateStatus(isAuto ? "Rascunho local atualizado." : "Rascunho salvo localmente.");
    } catch (e) {
      updateStatus("Falha ao salvar rascunho local.");
    }
  }

  async function runAutoSave() {
    if (!state.enabled || state.autoSaveBlocked) return;
    if (autoSaveInFlight) {
      autoSaveQueued = true;
      return;
    }
    if (!state.dirty) return;
    autoSaveInFlight = true;
    try {
      await saveDraftToServer({ auto: true, reload: false });
    } catch (e) {
      void e;
    } finally {
      autoSaveInFlight = false;
      if (autoSaveQueued) {
        autoSaveQueued = false;
        scheduleAutoSave();
      }
    }
  }

  function scheduleAutoSave() {
    if (!state.enabled || state.autoSaveBlocked) return;
    if (autoSaveTimer) window.clearTimeout(autoSaveTimer);
    autoSaveTimer = window.setTimeout(() => {
      autoSaveTimer = 0;
      runAutoSave();
    }, AUTO_SAVE_DELAY_MS);
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
    migrateLegacyOpsInPage(pageKey, state.draft.pages[pageKey]);
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

  function isMatrixActivityColumnIndex(cIdx, totalColIdx) {
    return cIdx > 0 && cIdx < totalColIdx;
  }

  /** Célula de atividade no corpo (não rodapé): lê % para média linha/coluna. */
  function isMatrixBodyPercentValueCell(cell, cIdx, totalColIdx) {
    if (!cell || cell.tagName !== "TD") return false;
    if (!isMatrixActivityColumnIndex(cIdx, totalColIdx)) return false;
    if (cell.classList.contains("row-name") || cell.classList.contains("sticky-left")) return false;
    const tr = cell.closest("tr");
    if (!tr || !tr.closest("tbody") || tr.classList.contains("totals-row")) return false;
    return (
      isMatrixPercentDataCell(cell) ||
      cell.classList.contains("cell-pct") ||
      cell.classList.contains("cell-empty") ||
      PCT_BUCKET_CLASSES.some((cls) => cell.classList.contains(cls))
    );
  }

  /** Célula de atividade na linha Total do rodapé (não confundir com matrix-grand-total). */
  function isMatrixFooterActivityCell(cell, cIdx, totalColIdx) {
    if (!cell || cell.tagName !== "TD") return false;
    if (!isMatrixActivityColumnIndex(cIdx, totalColIdx)) return false;
    if (cell.classList.contains("matrix-grand-total")) return false;
    const tr = cell.closest("tr");
    return !!(tr && tr.classList.contains("totals-row") && cell.classList.contains("footer-activity-col"));
  }

  function refreshMatrixTotalsDisplay() {
    try {
      recalculateMatrixTotals();
    } catch (e) {
      void e;
    }
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

  function cssColorToHex(color) {
    const raw = String(color || "").trim();
    if (!raw) return "";
    if (raw.startsWith("#")) {
      return raw.length === 4
        ? `#${raw[1]}${raw[1]}${raw[2]}${raw[2]}${raw[3]}${raw[3]}`
        : raw.slice(0, 7);
    }
    const m = raw.match(/rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)/i);
    if (!m) return "";
    const hex = [m[1], m[2], m[3]].map((n) => {
      const v = Math.max(0, Math.min(255, Number(n) || 0));
      return v.toString(16).padStart(2, "0");
    });
    return `#${hex.join("")}`;
  }

  function syncColorToolSwatch() {
    if (!colorSwatchEl || !inpColor) return;
    const hex = cssColorToHex(inpColor.value) || inpColor.value || "#0ea5e9";
    colorSwatchEl.style.backgroundColor = hex;
  }

  function syncColorPickerFromCell(cell) {
    if (!inpColor || !cell) return;
    const hex = cssColorToHex(cell.style.backgroundColor);
    if (hex) inpColor.value = hex;
    syncColorToolSwatch();
  }

  function refreshToolbarEditState() {
    const cell = state.selectedCell;
    const canPercent = cell && canEditPercentCell(cell, { silent: true });
    const canStructural = cell && canEditStructuralCell(cell);
    const canText = state.enabled && (canPercent || canStructural);
    const canColor = state.enabled && canPercent;
    if (inpText) inpText.disabled = !canText;
    if (inpColor) inpColor.disabled = !canColor;
    if (btnColorPicker) btnColorPicker.disabled = !canColor;
  }

  function isPercentNotApplicableText(value) {
    const t = String(value || "").trim();
    return t === "-" || t === "--";
  }

  function defaultNewPercentCellText() {
    return "0%";
  }

  function normalizePercentLayoutValue(text) {
    const value = String(text || "").trim();
    if (!value) return "0%";
    if (isPercentNotApplicableText(value)) return "-";
    if (value.includes("%")) return value;
    if (/^-?\d+(?:[.,]\d+)?$/.test(value)) {
      return `${value.replace(",", ".")}%`;
    }
    return "0%";
  }

  function percentNumberFromDisplay(raw) {
    const token = normalizePercentLayoutValue(String(raw || ""));
    if (token === "-") return null;
    const m = token.match(/^(-?\d+(?:\.\d+)?)%$/);
    return m ? Number(m[1]) : null;
  }

  const PCT_BUCKET_CLASSES = ["cell-90", "cell-70", "cell-40", "cell-10", "cell-0"];

  /** Espelha mapa_controle.html (faixas de % na grade). */
  function percentBucketClassesForDisplay(raw) {
    const normalized = normalizePercentLayoutValue(String(raw || ""));
    if (isPercentNotApplicableText(normalized) || normalized === "-") return ["cell-empty"];
    const n = percentNumberFromDisplay(normalized);
    if (n == null) return ["cell-pct", "cell-0"];
    if (n >= 90) return ["cell-pct", "cell-90"];
    if (n >= 70) return ["cell-pct", "cell-70"];
    if (n >= 40) return ["cell-pct", "cell-40"];
    if (n > 0) return ["cell-pct", "cell-10"];
    return ["cell-pct", "cell-0"];
  }

  function stripPercentBucketClasses(cell) {
    if (!cell || !cell.classList) return;
    cell.classList.remove("cell-pct", "cell-empty", ...PCT_BUCKET_CLASSES);
  }

  /** Atualiza classes cell-* no DOM; respeita cor manual gravada em page.color. */
  function applyPercentCellVisualStyle(cell, displayText) {
    if (!cell || !isMatrixPercentDataCell(cell)) return;
    const key = String(cell.getAttribute("data-po-edit-key") || "");
    const page = ensurePageDraft(currentPageKey());
    if (key && page.color && page.color[key]) return;

    stripPercentBucketClasses(cell);
    const classes = percentBucketClassesForDisplay(displayText);
    classes.forEach((cls) => cell.classList.add(cls));
    cell.style.backgroundColor = "";
    cell.style.color = "";
  }

  function refreshPercentCellAfterValueChange(cell, displayText) {
    applyPercentCellVisualStyle(cell, displayText);
    refreshMatrixTotalsDisplay();
  }

  function formatMatrixTotalPct(value) {
    const n = Number(value);
    if (!Number.isFinite(n)) return "-";
    return `${n.toFixed(2)}%`;
  }

  /** Recalcula coluna Total e rodapé a partir das células de % visíveis (só exibição). */
  function recalculateMatrixTotals() {
    // Em bloco/pavimento os percentuais são consolidados no servidor.
    // Recalcular pelo que está visível pode zerar/invalidar totais legítimos.
    if (!isAptoUndManualEntryLayer()) return;
    const doc = frame.contentDocument;
    const table = doc && doc.querySelector(".matrix-table");
    if (!table) return;
    const headerRow = table.querySelector("thead tr");
    if (!headerRow) return;
    const colCount = headerRow.children.length;
    if (colCount < 3) return;
    const totalColIdx = colCount - 1;
    const tbody = table.querySelector("tbody");
    if (!tbody) return;

    const colBuckets = Array.from({ length: colCount }, () => []);

    listMatrixTbodyRows(tbody).forEach((tr) => {
      if (isNonDataMatrixRow(tr)) return;
      const cells = tr.querySelectorAll("td");
      let rowSum = 0;
      let rowCount = 0;
      cells.forEach((cell, cIdx) => {
        if (!isMatrixBodyPercentValueCell(cell, cIdx, totalColIdx)) return;
        const displayText = String(textNodeForCell(cell).textContent || "").trim();
        if (!displayText) return;
        const n = percentNumberFromDisplay(displayText);
        if (n == null) return;
        rowSum += n;
        rowCount += 1;
        colBuckets[cIdx].push(n);
      });
      const totalCell = tr.querySelector("td.total-col");
      if (totalCell) {
        const node = textNodeForCell(totalCell);
        if (rowCount) {
          node.textContent = formatMatrixTotalPct(rowSum / rowCount);
        } else {
          node.textContent = "-";
        }
      }
    });

    const totalsTr = tbody.querySelector("tr.totals-row");
    if (!totalsTr) return;
    totalsTr.querySelectorAll("td").forEach((cell, cIdx) => {
      if (!isMatrixFooterActivityCell(cell, cIdx, totalColIdx)) return;
      const vals = (colBuckets[cIdx] || []).filter((n) => n != null);
      const node = textNodeForCell(cell);
      if (!vals.length) {
        node.textContent = "-";
        return;
      }
      node.textContent = formatMatrixTotalPct(vals.reduce((a, b) => a + b, 0) / vals.length);
    });
    const footerTotal = totalsTr.querySelector("td.matrix-grand-total");
    if (footerTotal) {
      const all = colBuckets.flat().filter((n) => n != null);
      const node = textNodeForCell(footerTotal);
      if (!all.length) {
        node.textContent = "-";
      } else {
        node.textContent = formatMatrixTotalPct(all.reduce((a, b) => a + b, 0) / all.length);
      }
    }
  }

  function normalizeCellText(cell, rawValue) {
    const value = String(rawValue || "").trim();
    if (!isPercentEligibleCell(cell)) return value;
    return normalizePercentLayoutValue(value);
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
        .po-map-edit-enabled .matrix-table a.row-link,
        .po-map-edit-enabled .matrix-table a.matrix-col-head-link {
          pointer-events: auto !important;
          cursor: pointer !important;
          text-decoration: underline !important;
          position: relative;
          z-index: 2;
        }
        .po-map-edit-enabled .matrix-table .row-name a.row-link,
        .po-map-edit-enabled .matrix-table .sticky-left.row-name a.row-link {
          pointer-events: auto !important;
        }
        .po-map-edit-enabled th.vertical a.matrix-col-head-link {
          pointer-events: auto !important;
        }
        .po-map-edit-enabled .matrix-table tr > :first-child {
          min-width: 5.5rem;
        }
        .po-map-edit-enabled tbody td.row-name,
        .po-map-edit-enabled tbody td.sticky-left.row-name {
          cursor: text;
        }
        .po-map-edit-enabled .po-mapa-row-name-wrap {
          display: flex;
          align-items: center;
          gap: 6px;
          min-width: 0;
          flex: 1 1 auto;
          align-self: stretch;
          width: 100%;
          min-height: 100%;
          box-sizing: border-box;
        }
        .po-map-edit-enabled .po-mapa-row-name-wrap > a.row-link,
        .po-map-edit-enabled .po-mapa-row-name-wrap > .row-name-txt {
          flex: 0 1 auto !important;
          width: auto !important;
          max-width: calc(100% - 1.5rem);
        }
        .po-map-edit-enabled .po-mapa-row-name-wrap > :not(.po-mapa-dnd-handle) {
          min-width: 0;
        }
        .po-map-edit-enabled tbody td.row-name [data-po-inline-edit="1"],
        .po-map-edit-enabled tbody td.sticky-left.row-name [data-po-inline-edit="1"] {
          display: inline-block !important;
          width: fit-content !important;
          min-width: 40px !important;
          flex: 0 0 auto !important;
          box-sizing: border-box;
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

  function commitPercentEditAndAutoSave() {
    const cell = state.inline.cell;
    if (!cell || !canEditPercentCell(cell, { silent: true })) {
      finishInlineEdit({ commit: true });
      return;
    }
    const raw = state.inline.node ? String(state.inline.node.textContent || "") : "";
    if (isInvalidPercentToolbarInput(raw)) {
      updateStatus("Valor de percentual inválido. Use número (ex.: 10 ou 10%) ou \"-\" para não aplicável.");
      return;
    }
    finishInlineEdit({ commit: true });
    if (!state.dirty) return;
    updateStatus("Salvando percentual…");
    void runAutoSave();
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
        if (hasChanged) {
          markDirty();
        }
        if (patchKindForCell(inline.cell) === "percent") {
          refreshPercentCellAfterValueChange(inline.cell, nextText);
        }
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
    if (commit && isMatrixRowNameCell(inline.cell)) {
      refreshRowDrillLinkForNameCell(inline.cell);
    }
    if (commit && isMatrixColumnHeadCell(inline.cell)) {
      refreshMatrixColumnHeadLink(inline.cell);
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
      syncColorPickerFromCell(state.selectedCell);
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
    (page.structuralOps || []).forEach((op) => {
      if (!op || typeof op !== "object") return;
      if (op.type === "move_column") {
        applyMoveColumn(op.from, op.to, { registerOp: false, keepSelection: false });
      } else if (op.type === "create_column") {
        applyInsertColumn(op.index, op.label, { registerOp: false, keepSelection: false });
      } else if (op.type === "delete_column") {
        applyDeleteColumn(op.index, { registerOp: false, keepSelection: false });
      } else if (op.type === "move_row") {
        applyMoveRow(op.from, op.to, { registerOp: false, keepSelection: false });
      } else if (op.type === "create_row") {
        const order = Number.isInteger(op.order) ? op.order : Number.isInteger(op.index) ? op.index : Number.MAX_SAFE_INTEGER;
        applyInsertRow(order, op.label, { registerOp: false, keepSelection: false });
      } else if (op.type === "delete_row") {
        let rowIdx = Number.isInteger(op.index) ? op.index : -1;
        if (rowIdx < 0 && op.label) {
          const rows = matrixBodyRows();
          rowIdx = rows.findIndex((tr) => {
            const nameCell = tr.querySelector(".row-name, .sticky-left");
            return rowDisplayLabelFromNameCell(nameCell) === String(op.label || "").trim();
          });
        }
        if (rowIdx >= 0) {
          applyDeleteRow(rowIdx, { registerOp: false, keepSelection: false });
        }
      }
    });
    mapEditableCells();
    Object.entries(page.text || {}).forEach(([key, value]) => {
      const cell = doc.querySelector(`[data-po-edit-key="${escapeSelectorValue(key)}"]`);
      if (!cell) return;
      if (!canEditPercentCell(cell, { silent: true }) && !canEditStructuralCell(cell)) return;
      textNodeForCell(cell).textContent = String(value || "");
      if (canEditPercentCell(cell, { silent: true })) {
        applyPercentCellVisualStyle(cell, String(value || ""));
      }
    });
    Object.entries(page.color || {}).forEach(([key, value]) => {
      const cell = doc.querySelector(`[data-po-edit-key="${escapeSelectorValue(key)}"]`);
      if (!cell || !canEditPercentCell(cell, { silent: true })) return;
      cell.style.backgroundColor = String(value || "");
      cell.style.color = "#ffffff";
    });
    refreshAllMatrixRowDrillLinks();
    refreshAllMatrixColumnHeadLinks();
    refreshMatrixTotalsDisplay();
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
    refreshAllMatrixRowDrillLinks();
    refreshAllMatrixColumnHeadLinks();
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

  function reorderDomRowChildren(row, from, to) {
    if (!row || from === to) return;
    const cells = Array.from(row.children);
    if (from < 0 || to < 0 || from >= cells.length || to >= cells.length) return;
    const [item] = cells.splice(from, 1);
    cells.splice(to, 0, item);
    cells.forEach((cell) => row.appendChild(cell));
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
    rows.forEach((row) => reorderDomRowChildren(row, from, to));
    mapEditableCells();
    if (cfg.keepSelection) {
      const sc = selectedCoords();
      if (sc) {
        const selected = table.querySelector(`[data-po-edit-key="r${sc.r}c${to}"]`);
        if (selected) setSelectedCell(selected);
      }
    }
    if (cfg.registerOp !== false) {
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
    const [movedTr] = movable.splice(from, 1);
    if (!movedTr) return false;
    movable.splice(to, 0, movedTr);
    const totalsRow = tbody.querySelector("tr.totals-row");
    movable.forEach((tr) => {
      if (totalsRow) tbody.insertBefore(tr, totalsRow);
      else tbody.appendChild(tr);
    });
    mapEditableCells();
    if (cfg.keepSelection && movedTr) {
      const nameCell = movedTr.querySelector(".row-name, .sticky-left") || movedTr.querySelector("td,th");
      if (nameCell) setSelectedCell(nameCell);
    }
    if (cfg.registerOp !== false) {
      const nameCell = movedTr ? movedTr.querySelector(".row-name, .sticky-left") : null;
      const rowLabel = nameCell ? rowDisplayLabelFromNameCell(nameCell) : "";
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
      if (isMatrixEmptyRow(tr)) return;
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
        const headLink = document.createElement("a");
        headLink.className = "matrix-col-head-link";
        headLink.textContent = title;
        newCell.appendChild(headLink);
      } else if (row.classList.contains("totals-row")) {
        newCell = document.createElement("td");
        newCell.className = "footer-activity-col";
        newCell.textContent = "-";
      } else if (!isNonDataMatrixRow(row)) {
        newCell = document.createElement("td");
        newCell.className = "cell-pct cell-0";
        newCell.textContent = isAptoUndManualEntryLayer()
          ? defaultNewPercentCellText()
          : "-";
      }
      const anchor = row.children[insertAt] || null;
      if (newCell) row.insertBefore(newCell, anchor);
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
    const title = sanitizeRowDisplayLabel(String(label || "Nova linha").trim() || "Nova linha");
    if (isPlaceholderRowLabel(title)) {
      updateStatus('Não é possível criar linha com o nome "Sem dados para matriz".');
      return false;
    }
    const anchor = bodyRows[insertAt] || tbody.querySelector("tr.totals-row") || null;

    const doc = frame.contentDocument || document;
    const row = document.createElement("tr");
    const first = document.createElement("td");
    populateRowNameCell(first, sanitizeRowDisplayLabel(title) || title, pageKey);
    row.appendChild(first);
    for (let c = 1; c < colCount - 1; c += 1) {
      const td = document.createElement("td");
      td.className = isAptoUndManualEntryLayer(pageKey) ? "cell-pct cell-0" : "cell-empty";
      td.textContent = isAptoUndManualEntryLayer(pageKey) ? defaultNewPercentCellText() : "-";
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
      if (rowLabel && !isPlaceholderRowLabel(rowLabel)) {
        afterStructuralLayoutOpCommitted({
          type: "delete_row",
          context: buildStructuralRowContext(currentPageKey()),
          label: rowLabel,
          index: idx,
        });
      }
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
    syncColorToolSwatch();
    applyColorChange();
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

    showContextMenu(event.clientX, event.clientY);
  }

  function onDocClick(event) {
    if (state.context.visible) hideContextMenu();
    const target = resolveEventElement(event.target);
    if (!target) return;
    if (target.closest(".po-mapa-dnd-handle")) {
      return;
    }
    const colHeadLink = target.closest("a.matrix-col-head-link");
    if (colHeadLink) {
      const thCell = colHeadLink.closest("thead th");
      if (thCell && navigateMatrixColumnFilter(thCell, event)) return;
    }
    const rowHeadLink = target.closest("a.row-link");
    if (rowHeadLink) {
      const linkCell = rowHeadLink.closest("td.row-name, td.sticky-left");
      if (linkCell && isMatrixRowNameCell(linkCell)) {
        event.preventDefault();
        event.stopPropagation();
        scheduleRowNameDrillClick(linkCell);
        return;
      }
      const fallbackHref = rowHeadLink.getAttribute("href");
      if (fallbackHref && fallbackHref !== "#") {
        event.preventDefault();
        frame.contentWindow.location.assign(fallbackHref);
      }
      return;
    }
    const rowNameCell = findMatrixRowNameCellFromTarget(target);
    if (rowNameCell) {
      event.preventDefault();
      event.stopPropagation();
      setSelectedCell(rowNameCell);
      updateStatus("Clique no nome para abrir o nível. Duplo clique na linha para renomear.");
      return;
    }
    if (!state.enabled) return;
    if (state.inline.node && (target === state.inline.node || target.closest('[data-po-inline-edit="1"]'))) {
      return;
    }
    const cell = target.closest(".matrix-table td, .matrix-table th");
    if (!cell) return;
    if (isMatrixStructuralCell(cell)) {
      return;
    }
    const canPercent = canEditPercentCell(cell, { silent: true });
    if (!canPercent) {
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
    updateStatus("Célula selecionada. Texto e cor são salvos automaticamente.");
  }

  function onDocDoubleClick(event) {
    if (!state.enabled) return;
    const target = resolveEventElement(event.target);
    if (!target) return;
    if (target.closest(".po-mapa-dnd-handle")) return;

    const rowNameCell = findMatrixRowNameCellFromTarget(target);
    if (rowNameCell && canEditStructuralCell(rowNameCell)) {
      cancelRowNameDrillClick();
      event.preventDefault();
      event.stopPropagation();
      if (isRowNameDrillLabelTarget(target)) {
        return;
      }
      if (startInlineEdit(rowNameCell)) {
        updateStatus("Renomear: Enter confirma. Clique no nome para abrir o nível.");
      }
      return;
    }

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
      if (isMatrixColumnHeadCell(cell)) {
        updateStatus("Renomear: Enter confirma. Clique no texto para abrir o nível ou filtrar.");
      } else {
        updateStatus("Edição direta ativa. Enter confirma, Esc cancela.");
      }
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
      if (state.inline.cell && canEditPercentCell(state.inline.cell, { silent: true })) {
        commitPercentEditAndAutoSave();
      } else {
        finishInlineEdit({ commit: true });
      }
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
      }
    }, 0);
  }

  function toggleControls(enabled) {
    if (!enabled) {
      if (autoSaveTimer) {
        window.clearTimeout(autoSaveTimer);
        autoSaveTimer = 0;
      }
      [inpText, inpColor, btnColorPicker].forEach((el) => {
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
    updateStatus("Alterações pendentes… salvando em instantes.");
    try {
      window.localStorage.setItem(storageKey, JSON.stringify(state.draft));
    } catch (e) {
      void e;
    }
    scheduleAutoSave();
  }

  function afterStructuralLayoutOpCommitted(structuralOp) {
    if (structuralOp && typeof structuralOp === "object") {
      if (structuralOp.type === "create_row" && !isValidStructuralCreateOp(structuralOp)) {
        poMapaDebug("structuralOp ignorada (inválida)", structuralOp);
        return;
      }
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
    const value = normalizeCellText(state.selectedCell, inpText ? inpText.value : "");
    applyToolbarValueToSelectedCell(value);
  }

  function syncToolbarTextToCell() {
    if (!state.enabled || !state.selectedCell || !state.selectedKey || !inpText) return;
    if (!canEditPercentCell(state.selectedCell, { silent: true }) && !canEditStructuralCell(state.selectedCell)) {
      return;
    }
    finishInlineEdit({ commit: true });
    const node = textNodeForCell(state.selectedCell);
    const currentFromCell = normalizeCellText(state.selectedCell, node.textContent);
    const value = normalizeCellText(state.selectedCell, String(inpText.value || ""));
    if (value === currentFromCell) return;
    const page = ensurePageDraft(currentPageKey());
    inpText.value = value;
    node.textContent = value;
    page.text[state.selectedKey] = value;
    rememberCellPatch(state.selectedCell, state.selectedKey, value);
    if (isMatrixRowNameCell(state.selectedCell)) {
      refreshRowDrillLinkForNameCell(state.selectedCell);
    }
    if (isMatrixColumnHeadCell(state.selectedCell)) {
      refreshMatrixColumnHeadLink(state.selectedCell);
    }
    markDirty();
    if (patchKindForCell(state.selectedCell) === "percent") {
      refreshPercentCellAfterValueChange(state.selectedCell, value);
    }
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
    if (autoSaveTimer) {
      window.clearTimeout(autoSaveTimer);
      autoSaveTimer = 0;
    }
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
    clearCellSelectionAndToolbar();
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
    window.requestAnimationFrame(() => {
      resizeFrameToContent();
      scrollIframeToMatrix();
    });
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
    inpText.addEventListener("blur", (blurEvent) => {
      if (isFocusMovingToMapaFrame(blurEvent.relatedTarget)) return;
      syncToolbarTextToCell();
    });
    inpText.addEventListener("keydown", (event) => {
      if (event.key !== "Enter") return;
      event.preventDefault();
      if (!state.enabled || !state.selectedCell) return;
      if (canEditPercentCell(state.selectedCell, { silent: true })) {
        const raw = String(inpText.value || "");
        if (isInvalidPercentToolbarInput(raw)) {
          updateStatus("Valor de percentual inválido. Use número (ex.: 10 ou 10%) ou \"-\" para não aplicável.");
          return;
        }
        syncToolbarTextToCell();
        if (state.dirty) {
          updateStatus("Salvando percentual…");
          void runAutoSave();
        }
        return;
      }
      syncToolbarTextToCell();
    });
  }
  if (btnColorPicker && inpColor) {
    btnColorPicker.addEventListener("click", () => {
      if (!state.enabled || !state.selectedCell || btnColorPicker.disabled) return;
      inpColor.click();
    });
  }
  if (inpColor) {
    inpColor.addEventListener("input", () => {
      syncColorToolSwatch();
      if (!state.enabled || !state.selectedCell) return;
      applyColorChange();
    });
  }
  syncColorToolSwatch();
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
  window.addEventListener("beforeunload", () => {
    if (!state.enabled || !state.dirty) return;
    if (autoSaveTimer) {
      window.clearTimeout(autoSaveTimer);
      autoSaveTimer = 0;
    }
    try {
      window.localStorage.setItem(storageKey, JSON.stringify(state.draft));
    } catch (e) {
      void e;
    }
  });

  updateToggleUi();
  void refreshLayoutMetaCache();

  // Fallback para conexões lentas.
  window.setTimeout(hideLoading, 6500);
  window.addEventListener("resize", () => {
    resizeFrameToContent();
  });
})();
