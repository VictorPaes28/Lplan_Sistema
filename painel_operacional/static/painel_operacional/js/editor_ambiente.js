(function () {
  const ctx = window.PO_EDITOR_CONTEXT || {};
  const draftPreview = document.getElementById("draftPreview");
  const alertBox = document.getElementById("editorAlert");
  const canvasBoard = document.getElementById("canvasBoard");
  const secTitle = document.getElementById("secTitle");
  const secKind = document.getElementById("secKind");
  const secSemantica = document.getElementById("secSemantica");
  const btnAddSection = document.getElementById("btnAddSection");
  const btnQuickTable = document.getElementById("btnQuickTable");
  const btnQuickBlock = document.getElementById("btnQuickBlock");
  const btnQuickKpi = document.getElementById("btnQuickKpi");
  const btnQuickDetail = document.getElementById("btnQuickDetail");
  const btnToggleEdit = document.getElementById("btnToggleEdit");
  const btnFitView = document.getElementById("btnFitView");
  const btnSaveDraft = document.getElementById("btnSaveDraft");
  const saveStatusBadge = document.getElementById("saveStatusBadge");
  const canvasQuickActions = document.getElementById("canvasQuickActions");
  const btnQuickDuplicateSelected = document.getElementById("btnQuickDuplicateSelected");
  const btnQuickDeleteSelected = document.getElementById("btnQuickDeleteSelected");
  const inspectorEmpty = document.getElementById("inspectorEmpty");
  const inspectorForm = document.getElementById("inspectorForm");
  const insTitle = document.getElementById("insTitle");
  const insSemantica = document.getElementById("insSemantica");
  const insSetor = document.getElementById("insSetor");
  const insBloco = document.getElementById("insBloco");
  const insPavimento = document.getElementById("insPavimento");
  const insUnidade = document.getElementById("insUnidade");
  const matrixTools = document.getElementById("matrixTools");
  const matrixGridEditor = document.getElementById("matrixGridEditor");
  const insMatrixLevels = document.getElementById("insMatrixLevels");
  const insMatrixHeatmap = document.getElementById("insMatrixHeatmap");
  const insMatrixTotalsCol = document.getElementById("insMatrixTotalsCol");
  const insMatrixTotalsRow = document.getElementById("insMatrixTotalsRow");
  const insMatrixVerticalHeaders = document.getElementById("insMatrixVerticalHeaders");
  const matrixCsvArea = document.getElementById("matrixCsvArea");
  const canvasViewport = document.getElementById("canvasViewport");

  const GRID = 24;
  /** Limites de zoom do palco (alinhar ao slider 40–240%). */
  const ZOOM_MIN = 0.4;
  const ZOOM_MAX = 2.4;
  /** Teto ao usar «Ajustar visão» (evita zoom excessivo em prancheta pequena). */
  const ZOOM_FIT_CAP = 1.25;
  const BOARD_WIDTH = 3200;
  const BOARD_HEIGHT = 2000;
  const MIN_W = 120;
  const MIN_H = 90;
  /** Limites na mesma ordem da prancheta (antes 1200×1000 cortava matrizes grandes). */
  const MAX_CARD_W = BOARD_WIDTH;
  const MAX_CARD_H = BOARD_HEIGHT;
  const ALIGN_THRESH = 10;
  const MAX_CSV_BYTES = 512 * 1024;
  const MAX_CSV_ROWS = 2500;
  const MAX_CSV_COLS = 400;
  const MAX_CSV_CELLS = 40_000;
  /** Intervalo para verificar se o rascunho remoto mudou (evita pedidos excessivos em rede instável). */
  const DRAFT_CONFLICT_POLL_MS = 15000;
  const PAN_SURFACE_NAME = "po-pan-surface";
  /** Pesos relativos para redimensionar linhas/colunas da matriz na prancheta (mín. evita colapso). */
  const MIN_MATRIX_WEIGHT = 0.06;
  /** Largura da zona de apanhamento (invisível); o desenho é só uma linha fina. */
  const MX_RESIZE_HIT = 14;
  /** Espaço entre células (0 = máximo leitura; linhas da grelha desenham-se à parte). */
  const MATRIX_GRID_GAP = 0;
  /** Largura / altura mínimas “legíveis”; com muitas colunas/linhas o conteúdo pode ultrapassar o painel (scroll interno). */
  const MATRIX_MIN_COL_PX = 12;
  const MATRIX_MIN_ROW_PX = 12;
  /** Cabeçalhos verticais só se a coluna tiver largura suficiente (evita sobreposição). */
  const MATRIX_VERT_HEADER_MIN_CW = 34;
  /** Controlo de reordenação discreto (mapas densos). */
  const MX_REORDER_COL_GRIP_H = 6;
  const MX_REORDER_ROW_GRIP_W = 10;
  const stageState = { stage: null, layer: null, tr: null, panBg: null };
  const history = { past: [], future: [], max: 40, suppress: false };
  /** Evita tr.nodes([nó já destruído]) → erro interno do Konva (setAttrs of undefined). */
  function setTransformerNodes(nodes) {
    const tr = stageState.tr;
    if (!tr || !tr.getLayer()) return;
    const list = (nodes || []).filter((n) => n && n.getLayer && n.getLayer());
    tr.nodes(list);
  }
  const state = {
    draft: {},
    elementos: [],
    selectedId: null,
    editMode: true,
    semanticas: [],
    renderQueued: false,
    dirty: false,
    autoSaveTimer: null,
    contextMenuAnchor: { x: 0, y: 0 },
    lastAppearanceAnchor: { x: 0, y: 0 },
    viewMode: "draft",
    elementosDraft: null,
    selectedDraftId: null,
    editModeBeforePublished: true,
    draftKnownUpdatedAt: null,
    conflictPollTimer: null,
    matrixEditUndoPushed: false,
    inspectorUndoSelId: null,
    inspectorLiveUndoPushed: false,
    conflictSkipAlertShown: false,
    /** { elKey, r, c, original } enquanto o textarea de edição na prancheta está aberto. */
    matrixInline: null,
    /** { elKey, mode: 'col'|'row', index, startP, startW } — redimensionar grelha da matriz na prancheta */
    mxGridDrag: null,
    /** { elKey, axis: 'col'|'row', fromIndex, dropBefore, dropLine } — reordenar colunas/linhas na prancheta */
    mxReorder: null,
    /** { elKey, band: 'row'|'col', index } — linha (eixo) ou coluna (cabeçalhos) destacada na matriz */
    matrixBandSel: null,
  };

  let matrixInlineEl = null;
  let matrixInlineBlurTimer = null;
  let mxGridDragMove = null;
  let mxGridDragUp = null;
  let mxReorderMove = null;
  let mxReorderUp = null;

  const DEFAULT_CANVAS_STYLE = {
    cardBg: "#dbeafe",
    headerBg: "#bfdbfe",
    cardStroke: "#93c5fd",
    cardStrokeWidth: 1,
    titleColor: "#0f172a",
    titleFontPx: 12,
    titleFontFace: "sys",
    bodyPanelBg: "#f8fafc",
    bodyPanelStroke: "#c7d2fe",
    bodyTextColor: "#1e293b",
    bodyFontPx: 12,
    bodyFontFace: "sys",
    selectionStroke: "#1d4ed8",
    selectionStrokeWidth: 2,
    matrixHeaderBg: "#f1f5f9",
    matrixHeaderAltBg: "#eef2f7",
    matrixAxisBg: "#f8fafc",
    matrixFooterBg: "#f1f5f9",
    matrixFooterAxisBg: "#e2e8f0",
    matrixCellBg: "#ffffff",
    matrixTextColor: "#0f172a",
    matrixFontPx: 0,
    matrixFontFace: "sys",
    matrixGridStroke: "#cbd5e1",
  };

  const FONT_FACE_TO_CSS = {
    sys: 'system-ui, -apple-system, "Segoe UI", sans-serif',
    serif: '"Georgia", "Times New Roman", serif',
    mono: '"Consolas", "Courier New", monospace',
  };

  function resolveFontFace(face) {
    const k = String(face || "sys").toLowerCase();
    return FONT_FACE_TO_CSS[k] || FONT_FACE_TO_CSS.sys;
  }

  function getCanvasStyle(el) {
    const raw = el && el.data && el.data.canvasStyle && typeof el.data.canvasStyle === "object" ? el.data.canvasStyle : {};
    const merged = { ...DEFAULT_CANVAS_STYLE, ...raw };
    delete merged.titleFontFamily;
    delete merged.bodyFontFamily;
    delete merged.matrixFontFamily;
    merged.titleFontFamily = resolveFontFace(merged.titleFontFace);
    merged.bodyFontFamily = resolveFontFace(merged.bodyFontFace);
    merged.matrixFontFamily = resolveFontFace(merged.matrixFontFace);
    return merged;
  }

  function closeAppearancePopover() {
    const p = document.getElementById("poAppearancePop");
    if (p) p.remove();
  }

  function positionAppearancePop(node, ax, ay) {
    const pad = 8;
    const vw = window.innerWidth;
    const vh = window.innerHeight;
    requestAnimationFrame(() => {
      const r = node.getBoundingClientRect();
      let left = ax + pad;
      let top = ay + pad;
      if (left + r.width > vw - pad) left = Math.max(pad, vw - r.width - pad);
      if (top + r.height > vh - pad) top = Math.max(pad, vh - r.height - pad);
      node.style.left = `${left}px`;
      node.style.top = `${top}px`;
    });
  }

  function refreshAppearanceForm(root, el) {
    const s = getCanvasStyle(el);
    root.querySelectorAll("[data-po-style]").forEach((inp) => {
      const key = inp.getAttribute("data-po-style");
      if (!key || !(key in s)) return;
      const v = s[key];
      if (inp.tagName === "SELECT") inp.value = String(v);
      else inp.value = String(v);
    });
  }

  function bindAppearancePopover(root, el, anchorX, anchorY) {
    const applyKey = (key, rawVal) => {
      if (!el.data) el.data = {};
      el.data.canvasStyle = el.data.canvasStyle || {};
      el.data.canvasStyle[key] = rawVal;
      updatePreview();
      markDirty();
      scheduleRender();
    };
    root.querySelectorAll("[data-po-style]").forEach((inp) => {
      const onVal = () => {
        const key = inp.getAttribute("data-po-style");
        if (!key) return;
        let v = inp.value;
        if (inp.type === "range" || inp.type === "number") {
          v = Number(v);
          if (!Number.isFinite(v)) return;
        }
        if (inp.type === "range" && inp.dataset.poInt === "1") v = Math.round(v);
        applyKey(key, v);
      };
      inp.addEventListener("input", onVal);
      inp.addEventListener("change", onVal);
    });
    const btnReset = root.querySelector("[data-po-style-reset]");
    if (btnReset) {
      btnReset.addEventListener("click", (ev) => {
        ev.preventDefault();
        if (!el.data) el.data = {};
        el.data.canvasStyle = {};
        refreshAppearanceForm(root, el);
        updatePreview();
        markDirty();
        scheduleRender();
      });
    }
    const btnClose = root.querySelector("[data-po-style-close]");
    if (btnClose) {
      btnClose.addEventListener("click", (ev) => {
        ev.preventDefault();
        closeAppearancePopover();
      });
    }
    positionAppearancePop(root, anchorX, anchorY);
    state.lastAppearanceAnchor = { x: anchorX, y: anchorY };
  }

  function openAppearancePopover(anchorX, anchorY, elKey) {
    if (state.viewMode !== "draft") return;
    closeAppearancePopover();
    const el = state.elementos.find((it) => it.key === elKey);
    if (!el) return;
    state.selectedId = elKey;
    setTransformerNodes([]);
    if (stageState.stage) {
      const node = stageState.stage.findOne(`#${elKey}`);
      if (node) setTransformerNodes([node]);
      stageState.stage.batchDraw();
    }
    if (!el.data) el.data = {};
    if (!el.data.canvasStyle || typeof el.data.canvasStyle !== "object") el.data.canvasStyle = {};
    const s = getCanvasStyle(el);
    const kStr = String(el.kind || "");
    const isMx = kStr === "matrix_table" || kStr === "table";
    const faces = [
      { v: "sys", l: "Sistema (sans)" },
      { v: "serif", l: "Serif" },
      { v: "mono", l: "Monoespaçada" },
    ];
    const optTitle = faces
      .map((o) => `<option value="${o.v}"${String(s.titleFontFace) === o.v ? " selected" : ""}>${o.l}</option>`)
      .join("");
    const optBody = faces
      .map((o) => `<option value="${o.v}"${String(s.bodyFontFace) === o.v ? " selected" : ""}>${o.l}</option>`)
      .join("");
    const optMx = faces
      .map((o) => `<option value="${o.v}"${String(s.matrixFontFace) === o.v ? " selected" : ""}>${o.l}</option>`)
      .join("");
    const wrap = document.createElement("div");
    wrap.id = "poAppearancePop";
    wrap.className = "po-appearance-pop";
    wrap.setAttribute("role", "dialog");
    wrap.setAttribute("aria-label", "Aparência do bloco");
    wrap.innerHTML = [
      '<div class="po-appearance-pop__head">',
      '<span class="po-appearance-pop__title"><i class="bi bi-palette me-1" aria-hidden="true"></i>Aparência</span>',
      '<button type="button" class="btn-close btn-close-sm" data-po-style-close aria-label="Fechar"></button>',
      "</div>",
      '<div class="po-appearance-pop__scroll">',
      '<fieldset class="po-ap-fieldset"><legend>Card</legend>',
      '<div class="row g-1"><div class="col-6"><label class="form-label form-label-sm mb-0">Fundo</label><input type="color" class="form-control form-control-color w-100" data-po-style="cardBg"></div>',
      '<div class="col-6"><label class="form-label form-label-sm mb-0">Faixa título</label><input type="color" class="form-control form-control-color w-100" data-po-style="headerBg"></div></div>',
      '<div class="row g-1 mt-1"><div class="col-6"><label class="form-label form-label-sm mb-0">Borda</label><input type="color" class="form-control form-control-color w-100" data-po-style="cardStroke"></div>',
      '<div class="col-6"><label class="form-label form-label-sm mb-0">Esp. borda</label><input type="range" class="form-range" min="1" max="4" step="1" data-po-style="cardStrokeWidth" data-po-int="1"></div></div>',
      '<div class="row g-1 mt-1"><div class="col-6"><label class="form-label form-label-sm mb-0">Cor do título</label><input type="color" class="form-control form-control-color w-100" data-po-style="titleColor"></div>',
      '<div class="col-6"><label class="form-label form-label-sm mb-0">Tam. título</label><input type="range" class="form-range" min="8" max="22" step="1" data-po-style="titleFontPx" data-po-int="1"></div></div>',
      `<div class="mt-1"><label class="form-label form-label-sm mb-0">Fonte título</label><select class="form-select form-select-sm" data-po-style="titleFontFace">${optTitle}</select></div>`,
      '<div class="row g-1 mt-1"><div class="col-6"><label class="form-label form-label-sm mb-0">Seleção (borda)</label><input type="color" class="form-control form-control-color w-100" data-po-style="selectionStroke"></div>',
      '<div class="col-6"><label class="form-label form-label-sm mb-0">Esp. seleção</label><input type="range" class="form-range" min="1" max="4" step="1" data-po-style="selectionStrokeWidth" data-po-int="1"></div></div>',
      "</fieldset>",
      '<fieldset class="po-ap-fieldset mt-2"><legend>Texto do corpo (bloco simples)</legend>',
      '<div class="row g-1"><div class="col-6"><label class="form-label form-label-sm mb-0">Cor texto</label><input type="color" class="form-control form-control-color w-100" data-po-style="bodyTextColor"></div>',
      '<div class="col-6"><label class="form-label form-label-sm mb-0">Tam. texto</label><input type="range" class="form-range" min="8" max="20" step="1" data-po-style="bodyFontPx" data-po-int="1"></div></div>',
      `<div class="mt-1"><label class="form-label form-label-sm mb-0">Fonte corpo</label><select class="form-select form-select-sm" data-po-style="bodyFontFace">${optBody}</select></div>`,
      "</fieldset>",
      isMx
        ? `<fieldset class="po-ap-fieldset mt-2" id="poApMatrixFieldset"><legend>Matriz</legend>
      <div class="row g-1"><div class="col-6"><label class="form-label form-label-sm mb-0">Painel da grade</label><input type="color" class="form-control form-control-color w-100" data-po-style="bodyPanelBg"></div>
      <div class="col-6"><label class="form-label form-label-sm mb-0">Borda painel</label><input type="color" class="form-control form-control-color w-100" data-po-style="bodyPanelStroke"></div></div>
      <div class="row g-1 mt-1"><div class="col-6"><label class="form-label form-label-sm mb-0">Cabeçalho (faixa 1)</label><input type="color" class="form-control form-control-color w-100" data-po-style="matrixHeaderBg"></div>
      <div class="col-6"><label class="form-label form-label-sm mb-0">Cabeçalho (faixa 2)</label><input type="color" class="form-control form-control-color w-100" data-po-style="matrixHeaderAltBg"></div></div>
      <div class="row g-1 mt-1"><div class="col-6"><label class="form-label form-label-sm mb-0">Coluna eixo</label><input type="color" class="form-control form-control-color w-100" data-po-style="matrixAxisBg"></div>
      <div class="col-6"><label class="form-label form-label-sm mb-0">Linha totais</label><input type="color" class="form-control form-control-color w-100" data-po-style="matrixFooterBg"></div></div>
      <div class="row g-1 mt-1"><div class="col-6"><label class="form-label form-label-sm mb-0">Canto totais (eixo)</label><input type="color" class="form-control form-control-color w-100" data-po-style="matrixFooterAxisBg"></div>
      <div class="col-6"><label class="form-label form-label-sm mb-0">Fundo célula</label><input type="color" class="form-control form-control-color w-100" data-po-style="matrixCellBg"></div></div>
      <div class="row g-1 mt-1"><div class="col-6"><label class="form-label form-label-sm mb-0">Cor letras</label><input type="color" class="form-control form-control-color w-100" data-po-style="matrixTextColor"></div>
      <div class="col-6"><label class="form-label form-label-sm mb-0">Tam. letras (0=auto)</label><input type="range" class="form-range" min="0" max="14" step="1" data-po-style="matrixFontPx" data-po-int="1"></div></div>
      <div class="mt-1"><label class="form-label form-label-sm mb-0">Fonte células</label><select class="form-select form-select-sm" data-po-style="matrixFontFace">${optMx}</select></div>
      <div class="mt-1"><label class="form-label form-label-sm mb-0">Grade (linhas)</label><input type="color" class="form-control form-control-color w-100" data-po-style="matrixGridStroke"></div>
      </fieldset>`
        : "",
      "</div>",
      '<div class="po-appearance-pop__foot d-flex gap-2 mt-2">',
      '<button type="button" class="btn btn-outline-secondary btn-sm" data-po-style-reset>Restaurar padrão</button>',
      "</div>",
    ].join("");
    document.body.appendChild(wrap);
    refreshAppearanceForm(wrap, el);
    bindAppearancePopover(wrap, el, anchorX, anchorY);
    updateInspector();
    const dismiss = (ev) => {
      if (wrap.contains(ev.target)) return;
      const menu = document.getElementById("po-card-context-menu");
      if (menu && menu.contains(ev.target)) return;
      closeAppearancePopover();
      document.removeEventListener("click", dismiss, true);
      document.removeEventListener("keydown", onKey, true);
    };
    const onKey = (ev) => {
      if (ev.key === "Escape") {
        closeAppearancePopover();
        document.removeEventListener("click", dismiss, true);
        document.removeEventListener("keydown", onKey, true);
      }
    };
    setTimeout(() => {
      document.addEventListener("click", dismiss, true);
      document.addEventListener("keydown", onKey, true);
    }, 0);
  }

  let cardContextMenuDismiss = null;

  function closeContextMenuOnly() {
    const m = document.getElementById("po-card-context-menu");
    if (m) {
      m.classList.remove("is-open");
      m.innerHTML = "";
    }
    if (cardContextMenuDismiss) {
      document.removeEventListener("click", cardContextMenuDismiss, true);
      document.removeEventListener("contextmenu", cardContextMenuDismiss, true);
      document.removeEventListener("keydown", cardContextMenuDismiss, true);
      cardContextMenuDismiss = null;
    }
  }

  function closeCardContextMenu() {
    closeAppearancePopover();
    closeContextMenuOnly();
  }

  function openEditorOffcanvas() {
    closeCardContextMenu();
    const panel = document.getElementById("poEditorPanel");
    const bs = window.bootstrap;
    if (!panel || !bs || !bs.Offcanvas) return;
    bs.Offcanvas.getOrCreateInstance(panel).show();
  }

  function openCardContextMenu(clientX, clientY, elKey) {
    closeCardContextMenu();
    state.contextMenuAnchor = { x: clientX, y: clientY };
    const el = state.elementos.find((it) => it.key === elKey);
    if (!el) return;

    let menu = document.getElementById("po-card-context-menu");
    if (!menu) {
      menu = document.createElement("div");
      menu.id = "po-card-context-menu";
      menu.className = "po-card-context-menu";
      menu.setAttribute("role", "menu");
      document.body.appendChild(menu);
    }

    const mxHint = isMatrixKind(el.kind)
      ? '<div class="po-card-context-hint small text-muted px-2 py-2 border-bottom">Duplo clique numa célula da tabela (ex.: «Local 1») para editar direto na prancheta.</div>'
      : "";
    menu.innerHTML = [
      mxHint,
      '<button type="button" class="po-card-context-item po-card-context-item--row" data-action="appearance"><i class="bi bi-palette"></i><span>Aparência</span></button>',
      '<button type="button" class="po-card-context-item" data-action="panel"><i class="bi bi-sliders"></i> Painel de edição</button>',
      '<button type="button" class="po-card-context-item" data-action="dup"><i class="bi bi-copy"></i> Duplicar</button>',
      '<button type="button" class="po-card-context-item po-card-context-item--danger" data-action="del"><i class="bi bi-trash3"></i> Excluir</button>',
    ].join("");

    menu.style.left = `${clientX}px`;
    menu.style.top = `${clientY}px`;
    menu.classList.add("is-open");

    menu.addEventListener(
      "click",
      (ev) => {
        const btn = ev.target.closest("[data-action]");
        if (!btn || !menu.contains(btn)) return;
        ev.preventDefault();
        ev.stopPropagation();
        const action = btn.getAttribute("data-action");
        closeCardContextMenu();
        state.selectedId = elKey;
        updateInspector();
        if (action === "appearance") {
          const pos = state.contextMenuAnchor || { x: ev.clientX, y: ev.clientY };
          openAppearancePopover(pos.x, pos.y, elKey);
        } else if (action === "panel") {
          openEditorOffcanvas();
        } else if (action === "dup") {
          duplicateSelectedSection();
        } else if (action === "del") {
          removeSelectedSection();
        }
      },
      { once: true }
    );

    requestAnimationFrame(() => {
      const r = menu.getBoundingClientRect();
      let left = clientX;
      let top = clientY;
      if (r.right > window.innerWidth - 6) left = window.innerWidth - r.width - 6;
      if (r.bottom > window.innerHeight - 6) top = window.innerHeight - r.height - 6;
      menu.style.left = `${Math.max(6, left)}px`;
      menu.style.top = `${Math.max(6, top)}px`;
    });

    const panelEl = document.getElementById("poEditorPanel");
    cardContextMenuDismiss = (ev) => {
      if (ev.type === "keydown" && ev.key === "Escape") {
        if (document.getElementById("poAppearancePop")) {
          closeAppearancePopover();
          ev.preventDefault();
          return;
        }
      }
      if (ev.type === "keydown" && ev.key !== "Escape") return;
      if (panelEl && panelEl.contains(ev.target)) return;
      if (menu.contains(ev.target)) return;
      if (ev.target && ev.target.closest && ev.target.closest("#poAppearancePop")) return;
      closeCardContextMenu();
    };
    setTimeout(() => {
      document.addEventListener("click", cardContextMenuDismiss, true);
      document.addEventListener("contextmenu", cardContextMenuDismiss, true);
      document.addEventListener("keydown", cardContextMenuDismiss, true);
    }, 0);
  }

  function showAlert(message, type) {
    if (!alertBox) return;
    alertBox.className = `alert alert-${type || "info"}`;
    alertBox.textContent = message;
    alertBox.classList.remove("d-none");
  }

  function hideAlert() {
    if (!alertBox) return;
    alertBox.classList.add("d-none");
  }

  function setSaveState(label, bootstrapClass) {
    if (!saveStatusBadge) return;
    saveStatusBadge.className = `badge ${bootstrapClass || "text-bg-light"}`;
    saveStatusBadge.textContent = label;
  }

  function setButtonLoading(btn, loading) {
    if (!btn) return;
    if (loading) {
      if (!btn.dataset.poIdleHtml) btn.dataset.poIdleHtml = btn.innerHTML;
      btn.classList.add("po-btn-loading");
      btn.disabled = true;
      btn.innerHTML =
        '<span class="spinner-border spinner-border-sm me-1" role="status" aria-hidden="true"></span>Aguarde…';
    } else {
      btn.classList.remove("po-btn-loading");
      btn.disabled = false;
      if (btn.dataset.poIdleHtml) {
        btn.innerHTML = btn.dataset.poIdleHtml;
        delete btn.dataset.poIdleHtml;
      }
    }
  }

  function pretty(data) {
    return JSON.stringify(data || {}, null, 2);
  }

  function clamp(value, min, max) {
    return Math.max(min, Math.min(max, value));
  }

  function snap(value) {
    return Math.round(value / GRID) * GRID;
  }

  function clearAlignmentGuides() {
    const layer = stageState.layer;
    if (!layer) return;
    const toRemove = [];
    layer.getChildren().forEach((node) => {
      if (typeof node.name === "function" && node.name() === "po-align-guide") toRemove.push(node);
    });
    toRemove.forEach((n) => n.destroy());
  }

  function drawAlignmentGuides(lines) {
    const layer = stageState.layer;
    const tr = stageState.tr;
    if (!layer || !window.Konva) return;
    clearAlignmentGuides();
    lines.forEach((pts) => {
      layer.add(
        new Konva.Line({
          name: "po-align-guide",
          points: pts,
          stroke: "#db2777",
          strokeWidth: 1,
          dash: [6, 4],
          listening: false,
        })
      );
    });
    if (tr) tr.moveToTop();
    layer.batchDraw();
  }

  function snapPositionWithGuides(el, rawX, rawY) {
    let x = snap(clamp(rawX, 0, BOARD_WIDTH - el.width));
    let y = snap(clamp(rawY, 0, BOARD_HEIGHT - el.height));
    const guideLines = [];
    const w = el.width;
    const h = el.height;

    function tryAxis(isX) {
      const pos = isX ? x : y;
      const size = isX ? w : h;
      const boardMax = isX ? BOARD_WIDTH : BOARD_HEIGHT;
      const edges = [pos, pos + size / 2, pos + size];
      const offs = [0, size / 2, size];
      let bestDelta = ALIGN_THRESH + 1;
      let bestPos = pos;
      let guideCoord = null;
      state.elementos.forEach((o) => {
        if (o.key === el.key) return;
        const o0 = isX ? o.x : o.y;
        const os = isX ? o.width : o.height;
        const targets = [o0, o0 + os / 2, o0 + os];
        edges.forEach((me, i) => {
          const off = offs[i];
          targets.forEach((ta) => {
            const d = Math.abs(me - ta);
            if (d < bestDelta && d <= ALIGN_THRESH) {
              bestDelta = d;
              bestPos = ta - off;
              guideCoord = ta;
            }
          });
        });
      });
      if (bestDelta <= ALIGN_THRESH) {
        const clamped = snap(clamp(bestPos, 0, boardMax - size));
        if (isX) x = clamped;
        else y = clamped;
        if (guideCoord != null) {
          if (isX) guideLines.push([guideCoord, 0, guideCoord, BOARD_HEIGHT]);
          else guideLines.push([0, guideCoord, BOARD_WIDTH, guideCoord]);
        }
      }
    }

    tryAxis(true);
    tryAxis(false);
    if (guideLines.length) drawAlignmentGuides(guideLines);
    else clearAlignmentGuides();
    return { x, y };
  }

  function snapshotForHistory() {
    try {
      return JSON.stringify({
        elementos: state.elementos.map((el) => JSON.parse(JSON.stringify(el))),
        selectedId: state.selectedId,
      });
    } catch (e) {
      return null;
    }
  }

  function applyHistorySnapshot(jsonStr) {
    if (!jsonStr) return;
    const o = JSON.parse(jsonStr);
    history.suppress = true;
    state.elementos = (o.elementos || []).map((it, idx) => normalizeElement(it, idx));
    state.selectedId = o.selectedId || (state.elementos[0] ? state.elementos[0].key : null);
    updatePreview();
    renderKonva();
    history.suppress = false;
    markDirty();
  }

  function pushHistory() {
    if (history.suppress) return;
    const snap = snapshotForHistory();
    if (snap == null) return;
    if (history.past.length && history.past[history.past.length - 1] === snap) return;
    history.past.push(snap);
    if (history.past.length > history.max) history.past.shift();
    history.future = [];
    updateUndoRedoButtons();
  }

  function undo() {
    if (state.viewMode !== "draft") return;
    if (!history.past.length) return;
    const cur = snapshotForHistory();
    if (cur == null) return;
    const prev = history.past.pop();
    history.future.push(cur);
    applyHistorySnapshot(prev);
    updateUndoRedoButtons();
  }

  function redo() {
    if (state.viewMode !== "draft") return;
    if (!history.future.length) return;
    const cur = snapshotForHistory();
    if (cur == null) return;
    const next = history.future.pop();
    history.past.push(cur);
    applyHistorySnapshot(next);
    updateUndoRedoButtons();
  }

  function updateUndoRedoButtons() {
    const bu = document.getElementById("btnUndo");
    const br = document.getElementById("btnRedo");
    if (bu) bu.disabled = state.viewMode !== "draft" || !history.past.length;
    if (br) br.disabled = state.viewMode !== "draft" || !history.future.length;
  }

  function updateDraftOnlyControls() {
    const ro = state.viewMode !== "draft";
    if (btnQuickTable) btnQuickTable.disabled = ro;
    if (btnQuickBlock) btnQuickBlock.disabled = ro;
    if (btnQuickKpi) btnQuickKpi.disabled = ro;
    if (btnQuickDetail) btnQuickDetail.disabled = ro;
    if (btnAddSection) btnAddSection.disabled = ro;
    if (secTitle) secTitle.disabled = ro;
    if (secKind) secKind.disabled = ro;
    if (secSemantica) secSemantica.disabled = ro;
    if (btnSaveDraft) btnSaveDraft.disabled = ro;
    updateUndoRedoButtons();
  }

  function resetHistory() {
    history.past = [];
    history.future = [];
    updateUndoRedoButtons();
  }

  function rectsOverlap(ax, ay, aw, ah, bx, by, bw, bh) {
    return !(ax + aw <= bx || bx + bw <= ax || ay + ah <= by || by + bh <= ay);
  }

  function suggestedDuplicatePosition(el) {
    const w = el.width;
    const h = el.height;
    const step = GRID * 2;
    for (let k = 1; k <= 48; k += 1) {
      const nx = snap(clamp(el.x + ((k % 6) + 1) * step, 0, BOARD_WIDTH - w));
      const ny = snap(clamp(el.y + (Math.floor(k / 6) + 1) * step, 0, BOARD_HEIGHT - h));
      const hit = state.elementos.some((o) => {
        if (o.key === el.key) return false;
        return rectsOverlap(nx, ny, w, h, o.x, o.y, o.width, o.height);
      });
      if (!hit) return { x: nx, y: ny };
    }
    return { x: snap(clamp(el.x + step, 0, BOARD_WIDTH - w)), y: snap(clamp(el.y + step, 0, BOARD_HEIGHT - h)) };
  }

  function uuidShort() {
    return `sec_${Math.random().toString(16).slice(2, 10)}`;
  }

  function defaultMatrixRowsTemplate() {
    return [
      ["", "Grupo A", "Grupo A", "Grupo B", "Grupo B", "Total"],
      ["Eixo (linhas)", "Etapa 1", "Etapa 2", "Etapa 3", "Etapa 4", ""],
      ["Local 1", "", "", "", "", ""],
      ["Local 2", "", "", "", "", ""],
    ];
  }

  function matrixMapaPresetRows() {
    const dataCols = 20;
    const dataRows = 20;
    const domainSeeds = [
      "Hidráulica",
      "Elétrica",
      "Arquitetônico",
      "Estrutural",
      "Incêndio",
      "Acabamento",
      "Climatização",
      "Automação",
      "Gás",
      "Drenagem",
    ];
    const rows = [];
    const bandTop = [""];
    const bandBottom = ["Bloco / local"];
    for (let i = 0; i < dataCols; i += 1) {
      bandTop.push(domainSeeds[i % domainSeeds.length]);
      bandBottom.push(`Atividade ${i + 1}`);
    }
    bandTop.push("Total");
    bandBottom.push("");
    rows.push(bandTop, bandBottom);
    for (let r = 0; r < dataRows; r += 1) {
      const row = [r < 2 ? `Bloco ${String.fromCharCode(65 + r)}` : `Eixo ${r - 1}`];
      for (let c = 0; c < dataCols; c += 1) row.push("");
      row.push("");
      rows.push(row);
    }
    return rows;
  }

  function getHeaderBandCount(data) {
    if (!data || typeof data !== "object") return 1;
    const n = Number(data.headerBandCount);
    if (Number.isFinite(n) && n >= 1 && n <= 3) return n;
    return 1;
  }

  function defaultColLinearWeights(innerAvail, gap, colCount) {
    if (colCount <= 1) return [Math.max(MIN_MATRIX_WEIGHT, innerAvail)];
    const ic = innerAvail - gap * (colCount - 1);
    const firstColW =
      colCount > 1
        ? clamp(ic * 0.22, 48, Math.min(ic * 0.34, ic - (colCount - 1) * 16))
        : ic;
    const restW = Math.max(12, (ic - firstColW) / Math.max(1, colCount - 1));
    const arr = [firstColW];
    for (let i = 1; i < colCount; i += 1) arr.push(restW);
    return arr.map((w) => Math.max(MIN_MATRIX_WEIGHT, w));
  }

  /**
   * Converte pesos relativos em tamanhos (px).
   * Com `allowOverflow`, não esmagar abaixo do mínimo legível: a soma pode exceder `avail` (scroll na matriz).
   */
  function sizesFromWeights(avail, weights, options) {
    const opts = options || {};
    const allowOverflow = !!opts.allowOverflow;
    const minReadable = opts.minReadablePx != null ? opts.minReadablePx : 6;
    const n = weights.length || 1;
    const w = weights.map((x) => Math.max(MIN_MATRIX_WEIGHT, Number(x) || MIN_MATRIX_WEIGHT));
    const sum = w.reduce((a, b) => a + b, 0) || 1;
    let s = w.map((x) => (avail * x) / sum);
    const fair = avail / Math.max(1, n);
    const floorPx = Math.max(minReadable, Math.min(32, fair * 0.92));
    s = s.map((sz) => Math.max(floorPx, sz));
    const t = s.reduce((a, b) => a + b, 0);
    if (t > avail + 0.5) {
      if (allowOverflow) {
        return s.map((sz) => Math.max(8, sz));
      }
      return s.map((sz) => (sz * avail) / t);
    }
    if (t < avail - 0.5) {
      const extra = avail - t;
      return s.map((sz, i) => sz + (extra * w[i]) / sum);
    }
    return s;
  }

  function ensureMatrixData(el) {
    if (!isMatrixKind(el.kind)) return;
    if (!el.data) el.data = {};
    const d = el.data;
    if (!Array.isArray(d.rows) || !d.rows.length) {
      d.rows = defaultMatrixRowsTemplate();
      d.headerBandCount = 2;
      d.heatmap = true;
    }
    let h = getHeaderBandCount(d);
    d.headerBandCount = h;
    let colCount = Math.max(1, ...d.rows.map((r) => (Array.isArray(r) ? r.length : 0)));
    d.rows.forEach((row) => {
      if (!Array.isArray(row)) return;
      while (row.length < colCount) row.push("");
    });
    while (d.rows.length <= h) {
      d.rows.push(Array.from({ length: colCount }, () => ""));
    }
    if (d.rows.length <= h) {
      d.headerBandCount = 1;
      h = 1;
    }
    colCount = Math.max(1, ...d.rows.map((r) => (Array.isArray(r) ? r.length : 0)));
    if (getTotalsColumnAuto(d) && colCount < 3) {
      d.totalsColumnAuto = false;
    }
    const tRowAuto = getTotalsRowAuto(d);
    const visRowCount = d.rows.length + (tRowAuto ? 1 : 0);
    const bb = getMatrixBodyBox(el);
    const gapM = MATRIX_GRID_GAP;
    const innerWM = Math.max(4, bb.bodyW - gapM * 2);
    const innerHM = Math.max(4, bb.bodyH - gapM * 2);
    if (!Array.isArray(d.colWeights) || d.colWeights.length !== colCount) {
      if (Array.isArray(d.colWeights) && d.colWeights.length > 0) {
        if (d.colWeights.length > colCount) d.colWeights.length = colCount;
        while (d.colWeights.length < colCount) d.colWeights.push(1);
        d.colWeights = d.colWeights.map((x) => Math.max(MIN_MATRIX_WEIGHT, Number(x) || MIN_MATRIX_WEIGHT));
      } else {
        d.colWeights = defaultColLinearWeights(innerWM, gapM, colCount);
      }
    } else {
      d.colWeights = d.colWeights.map((x) => Math.max(MIN_MATRIX_WEIGHT, Number(x) || MIN_MATRIX_WEIGHT));
    }
    if (!Array.isArray(d.rowWeights) || d.rowWeights.length !== visRowCount) {
      if (Array.isArray(d.rowWeights) && d.rowWeights.length > 0) {
        if (d.rowWeights.length > visRowCount) d.rowWeights.length = visRowCount;
        while (d.rowWeights.length < visRowCount) d.rowWeights.push(1);
        d.rowWeights = d.rowWeights.map((x) => Math.max(MIN_MATRIX_WEIGHT, Number(x) || MIN_MATRIX_WEIGHT));
      } else {
        d.rowWeights = Array.from({ length: visRowCount }, () => 1);
      }
    } else {
      d.rowWeights = d.rowWeights.map((x) => Math.max(MIN_MATRIX_WEIGHT, Number(x) || MIN_MATRIX_WEIGHT));
    }
    if (!d.matrixPan || typeof d.matrixPan !== "object") d.matrixPan = { x: 0, y: 0 };
    else {
      d.matrixPan.x = Number(d.matrixPan.x) || 0;
      d.matrixPan.y = Number(d.matrixPan.y) || 0;
    }
  }

  function parsePercentCell(text) {
    const m = String(text)
      .trim()
      .replace(/\s/g, "")
      .replace(/%/g, "")
      .replace(",", ".");
    const n = parseFloat(m);
    if (!Number.isFinite(n)) return null;
    return n;
  }

  function heatmapBucket(n) {
    const v = clamp(n, 0, 100);
    if (v >= 90) return { fill: "#0284c7", color: "#ffffff" };
    if (v >= 70) return { fill: "#38bdf8", color: "#082f49" };
    if (v >= 40) return { fill: "#bae6fd", color: "#0c4a6e" };
    if (v > 0) return { fill: "#e0f2fe", color: "#334155" };
    return { fill: "#f8fafc", color: "#64748b" };
  }

  function heatClassForValue(text, heatmapOn) {
    if (!heatmapOn) return "";
    const n = parsePercentCell(text);
    if (n === null) return "";
    const v = clamp(n, 0, 100);
    if (v >= 90) return "po-mx-heat-90";
    if (v >= 70) return "po-mx-heat-70";
    if (v >= 40) return "po-mx-heat-40";
    if (v > 0) return "po-mx-heat-10";
    return "po-mx-heat-0";
  }

  function getTotalsColumnAuto(d) {
    return !!(d && d.totalsColumnAuto);
  }

  function getTotalsRowAuto(d) {
    return !!(d && d.totalsRowAuto);
  }

  function getVerticalHeaders(d) {
    return !!(d && d.verticalHeaders);
  }

  function rowTotalDisplay(row, colCount, totalsColAuto) {
    if (!totalsColAuto || colCount < 3) return row[colCount - 1] != null ? String(row[colCount - 1]) : "";
    const nums = [];
    for (let c = 1; c <= colCount - 2; c += 1) {
      const n = parsePercentCell(row[c]);
      if (n !== null) nums.push(n);
    }
    if (!nums.length) return "—";
    const avg = nums.reduce((a, b) => a + b, 0) / nums.length;
    return `${Math.round(avg)}%`;
  }

  function footerCellDisplay(rows, hBand, colCount, totalsRowAuto, totalsColAuto, c) {
    if (!totalsRowAuto) return "";
    if (c === 0) return "Total";
    if (totalsColAuto && c === colCount - 1) return "—";
    const nums = [];
    for (let r = hBand; r < rows.length; r += 1) {
      const row = rows[r];
      if (!Array.isArray(row)) continue;
      const n = parsePercentCell(row[c]);
      if (n !== null) nums.push(n);
    }
    if (!nums.length) return "—";
    const avg = nums.reduce((a, b) => a + b, 0) / nums.length;
    return `${Math.round(avg)}%`;
  }

  function matrixHeatLegendHtml() {
    const items = [
      { c: "#0284c7", l: "≥90%" },
      { c: "#38bdf8", l: "70–89%" },
      { c: "#bae6fd", l: "40–69%" },
      { c: "#e0f2fe", l: "1–39%" },
      { c: "#f8fafc", l: "0%" },
    ];
    const parts = items.map(
      (it) =>
        `<span class="po-mx-legend__item"><span class="po-mx-legend__sw" style="background:${it.c}"></span>${it.l}</span>`
    );
    return `<div class="po-mx-legend" aria-label="Legenda de percentuais">${parts.join("")}</div>`;
  }

  function detectCsvSep(line) {
    const semi = (line.match(/;/g) || []).length;
    const coma = (line.match(/,/g) || []).length;
    return semi >= coma ? ";" : ",";
  }

  function parseMatrixCsv(text) {
    const raw = String(text || "");
    if (raw.length > MAX_CSV_BYTES) return null;
    const lines = raw
      .trim()
      .split(/\r?\n/)
      .map((l) => l.trim())
      .filter(Boolean)
      .slice(0, MAX_CSV_ROWS);
    if (!lines.length) return null;
    const sep = detectCsvSep(lines[0]);
    return lines.map((ln) =>
      ln
        .split(sep)
        .map((cell) => String(cell ?? "").trim())
        .slice(0, MAX_CSV_COLS)
    );
  }

  function exportMatrixCsv(rows) {
    return (rows || [])
      .map((row) =>
        (Array.isArray(row) ? row : []).map((cell) => String(cell ?? "").replace(/\r?\n/g, " ")).join(";")
      )
      .join("\n");
  }

  function isMatrixKind(kind) {
    return kind === "matrix_table" || kind === "table";
  }

  function getMatrixBodyBox(el) {
    const bodyY = 36;
    const bodyX = 8;
    const bodyW = Math.max(40, el.width - 16);
    const bodyH = Math.max(24, el.height - bodyY - 8);
    return { bodyX, bodyY, bodyW, bodyH };
  }

  /** Geometria da grelha no espaço local do cartão (desenho, hit-test, overlay). */
  function computeMatrixGridMetrics(el) {
    ensureMatrixData(el);
    const { bodyX, bodyY, bodyW, bodyH } = getMatrixBodyBox(el);
    const d = el.data;
    const rows = d.rows || [[""]];
    const hBand = getHeaderBandCount(d);
    const heatmapOn = !!d.heatmap;
    const tCol = getTotalsColumnAuto(d);
    const tRow = getTotalsRowAuto(d);
    const colCount = Math.max(1, ...rows.map((r) => (Array.isArray(r) ? r.length : 0)));
    const visRowCount = rows.length + (tRow ? 1 : 0);
    const gap = MATRIX_GRID_GAP;
    const innerW = Math.max(4, bodyW - gap * 2);
    const innerH = Math.max(4, bodyH - gap * 2);
    const colAvail = innerW - gap * Math.max(0, colCount - 1);
    const rowAvail = innerH - gap * Math.max(0, visRowCount - 1);
    const cwPix = sizesFromWeights(colAvail, d.colWeights || [], {
      allowOverflow: true,
      minReadablePx: MATRIX_MIN_COL_PX,
    });
    const rhPix = sizesFromWeights(rowAvail, d.rowWeights || [], {
      allowOverflow: true,
      minReadablePx: MATRIX_MIN_ROW_PX,
    });
    const colLefts = [];
    const colWidths = [];
    let xa = bodyX + gap;
    for (let c = 0; c < colCount; c += 1) {
      colLefts.push(xa);
      colWidths.push(cwPix[c]);
      xa += cwPix[c] + gap;
    }
    const rowTops = [];
    const rowHeights = [];
    let ya = bodyY + gap;
    for (let r = 0; r < visRowCount; r += 1) {
      rowTops.push(ya);
      rowHeights.push(rhPix[r]);
      ya += rhPix[r] + gap;
    }
    const innerRight = bodyX + bodyW - gap;
    const innerBottom = bodyY + bodyH - gap;
    const contentRight = colCount ? colLefts[colCount - 1] + colWidths[colCount - 1] : bodyX + gap;
    const contentBottom = visRowCount ? rowTops[visRowCount - 1] + rowHeights[visRowCount - 1] : bodyY + gap;
    const overflowPanMaxX = Math.max(0, contentRight - innerRight);
    const overflowPanMaxY = Math.max(0, contentBottom - innerBottom);
    if (!d.matrixPan || typeof d.matrixPan !== "object") d.matrixPan = { x: 0, y: 0 };
    d.matrixPan.x = clamp(Number(d.matrixPan.x) || 0, 0, overflowPanMaxX);
    d.matrixPan.y = clamp(Number(d.matrixPan.y) || 0, 0, overflowPanMaxY);
    const panX = d.matrixPan.x;
    const panY = d.matrixPan.y;
    const minRh = rowHeights.length ? Math.min(...rowHeights) : 12;
    return {
      bodyX,
      bodyY,
      bodyW,
      bodyH,
      rows,
      hBand,
      heatmapOn,
      tCol,
      tRow,
      colCount,
      visRowCount,
      gap,
      colLefts,
      colWidths,
      rowTops,
      rowHeights,
      minRowH: minRh,
      panX,
      panY,
      overflowPanMaxX,
      overflowPanMaxY,
    };
  }

  function matrixCellReadonly(m, rowIdx, colIdx) {
    const isFoot = m.tRow && rowIdx === m.rows.length;
    const isHeader = !isFoot && rowIdx < m.hBand;
    if (isFoot) return true;
    if (!isHeader && m.tCol && colIdx === m.colCount - 1) return true;
    return false;
  }

  function matrixCellAtPointer(el, localX, localY) {
    if (!isMatrixKind(el.kind)) return null;
    const m = computeMatrixGridMetrics(el);
    if (
      localX < m.bodyX ||
      localY < m.bodyY ||
      localX >= m.bodyX + m.bodyW ||
      localY >= m.bodyY + m.bodyH
    ) {
      return null;
    }
    const vx = localX + (m.panX || 0);
    const vy = localY + (m.panY || 0);
    let col = -1;
    for (let c = 0; c < m.colCount; c += 1) {
      if (vx >= m.colLefts[c] && vx < m.colLefts[c] + m.colWidths[c]) {
        col = c;
        break;
      }
    }
    if (col < 0) return null;
    let rowIdx = -1;
    for (let r = 0; r < m.visRowCount; r += 1) {
      if (vy >= m.rowTops[r] && vy < m.rowTops[r] + m.rowHeights[r]) {
        rowIdx = r;
        break;
      }
    }
    if (rowIdx < 0) return null;
    return { r: rowIdx, c: col, readOnly: matrixCellReadonly(m, rowIdx, col) };
  }

  function matrixCellRectInGroup(el, r0, c0) {
    const m = computeMatrixGridMetrics(el);
    const px = m.panX || 0;
    const py = m.panY || 0;
    return {
      x: m.colLefts[c0] - px,
      y: m.rowTops[r0] - py,
      w: m.colWidths[c0],
      h: m.rowHeights[r0],
      readOnly: matrixCellReadonly(m, r0, c0),
    };
  }

  /** Colunas de dados reordenáveis: não mexer no eixo (0) nem na coluna de total automático (última). */
  function matrixDraggableColBounds(el) {
    ensureMatrixData(el);
    const colCount = Math.max(1, ...el.data.rows.map((r) => (Array.isArray(r) ? r.length : 0)));
    const tCol = getTotalsColumnAuto(el.data);
    const minC = 1;
    const maxC = tCol ? colCount - 2 : colCount - 1;
    return { minC, maxC, colCount };
  }

  /** Linhas de corpo reordenáveis (abaixo das faixas de cabeçalho). */
  function matrixDraggableRowBounds(el) {
    ensureMatrixData(el);
    const h = getHeaderBandCount(el.data);
    const n = el.data.rows.length;
    const minR = h;
    const maxR = n - 1;
    return { minR, maxR, hBand: h };
  }

  function moveArrayItemToFinalIndex(arr, from, toFinal) {
    if (from === toFinal || from < 0 || toFinal < 0 || from >= arr.length || toFinal > arr.length) return false;
    const [item] = arr.splice(from, 1);
    arr.splice(toFinal, 0, item);
    return true;
  }

  function columnDropBeforeFromX(localX, m) {
    const maxBefore = m.tCol ? m.colCount - 1 : m.colCount;
    for (let b = 1; b <= maxBefore; b += 1) {
      const split =
        b < m.colCount ? m.colLefts[b] - m.gap / 2 : m.colLefts[m.colCount - 1] + m.colWidths[m.colCount - 1] + m.gap;
      if (localX < split) return b;
    }
    return maxBefore;
  }

  function rowDropBeforeFromY(localY, m) {
    const h = m.hBand;
    const lastBody = m.rows.length - 1;
    for (let b = h; b <= m.rows.length; b += 1) {
      const split =
        b <= lastBody ? m.rowTops[b] - m.gap / 2 : m.rowTops[lastBody] + m.rowHeights[lastBody] + m.gap;
      if (localY < split) return b;
    }
    return m.rows.length;
  }

  function columnDropBeforeToFinalIndex(fromC, dropBefore) {
    if (dropBefore === fromC || dropBefore === fromC + 1) return fromC;
    return dropBefore > fromC ? dropBefore - 1 : dropBefore;
  }

  function rowDropBeforeToFinalIndex(fromR, dropBefore) {
    if (dropBefore === fromR || dropBefore === fromR + 1) return fromR;
    return dropBefore > fromR ? dropBefore - 1 : dropBefore;
  }

  function columnGuideX(m, dropBefore) {
    if (dropBefore <= 0) return m.colLefts[0] - m.gap / 2;
    if (dropBefore >= m.colCount) return m.colLefts[m.colCount - 1] + m.colWidths[m.colCount - 1] + m.gap / 2;
    return m.colLefts[dropBefore] - m.gap / 2;
  }

  function rowGuideY(m, dropBefore) {
    const h = m.hBand;
    if (dropBefore <= h) return m.rowTops[h] - m.gap / 2;
    if (dropBefore >= m.rows.length) {
      const lb = m.rows.length - 1;
      return m.rowTops[lb] + m.rowHeights[lb] + m.gap / 2;
    }
    return m.rowTops[dropBefore] - m.gap / 2;
  }

  function applyMatrixColReorder(el, fromC, dropBefore) {
    const { minC, maxC } = matrixDraggableColBounds(el);
    if (fromC < minC || fromC > maxC) return false;
    let toFinal = columnDropBeforeToFinalIndex(fromC, dropBefore);
    if (toFinal < minC) toFinal = minC;
    if (toFinal > maxC) toFinal = maxC;
    if (toFinal === fromC) return false;
    const d = el.data;
    d.rows.forEach((row) => {
      if (Array.isArray(row)) moveArrayItemToFinalIndex(row, fromC, toFinal);
    });
    if (Array.isArray(d.colWeights) && d.colWeights.length > fromC) {
      moveArrayItemToFinalIndex(d.colWeights, fromC, toFinal);
    }
    ensureMatrixData(el);
    return true;
  }

  function applyMatrixRowReorder(el, fromR, dropBefore) {
    const { minR, maxR } = matrixDraggableRowBounds(el);
    if (fromR < minR || fromR > maxR) return false;
    let toFinal = rowDropBeforeToFinalIndex(fromR, dropBefore);
    if (toFinal < minR) toFinal = minR;
    if (toFinal > maxR) toFinal = maxR;
    if (toFinal === fromR) return false;
    const d = el.data;
    moveArrayItemToFinalIndex(d.rows, fromR, toFinal);
    if (Array.isArray(d.rowWeights) && d.rowWeights.length > fromR) {
      moveArrayItemToFinalIndex(d.rowWeights, fromR, toFinal);
    }
    ensureMatrixData(el);
    return true;
  }

  function clientToStageCoords(stage, clientX, clientY) {
    const box = stage.container().getBoundingClientRect();
    const sx = stage.width() / Math.max(1, box.width);
    const sy = stage.height() / Math.max(1, box.height);
    return {
      x: (clientX - box.left) * sx,
      y: (clientY - box.top) * sy,
    };
  }

  function clientPointToGroupLocal(stage, group, clientX, clientY) {
    const p = clientToStageCoords(stage, clientX, clientY);
    return group.getAbsoluteTransform().copy().invert().point(p);
  }

  function normalizeElement(item, index) {
    const kindRaw = String(
      item.kind || item.tipo || (item.dados && item.dados.kind) || "block"
    ).trim();
    const isMatrix = kindRaw === "matrix_table" || kindRaw === "table";
    const normalized = {
      id: item.id || null,
      key: item.chave_externa || item.key || uuidShort(),
      title: item.titulo || item.title || "Sem título",
      kind: kindRaw,
      semantica: item.semantica || (item.dados && item.dados.semantica) || "",
      x: Number.isFinite(item.x) ? item.x : 80 + ((index % 4) * 280),
      y: Number.isFinite(item.y) ? item.y : 80 + (Math.floor(index / 4) * 220),
      width: Number.isFinite(item.width) ? item.width : (isMatrix ? 560 : 320),
      height: Number.isFinite(item.height) ? item.height : (isMatrix ? 320 : 180),
      layer: item.layer || item.camada || {},
      data:
        typeof (item.data || item.dados) === "object" && (item.data || item.dados)
          ? { ...(item.data || item.dados) }
          : {},
    };
    ensureMatrixData(normalized);
    return normalized;
  }

  function getSelected() {
    if (!state.selectedId) return null;
    return state.elementos.find((it) => it.key === state.selectedId) || null;
  }

  async function requestJson(url, options) {
    const response = await fetch(url, options || {});
    let data = {};
    try {
      const text = await response.text();
      data = text ? JSON.parse(text) : {};
    } catch (e) {
      throw new Error(response.ok ? "Resposta inválida do servidor." : `Erro HTTP ${response.status}.`);
    }
    if (!response.ok || data.success === false) {
      throw new Error(data.error || `Falha na operação (${response.status}).`);
    }
    return data;
  }

  function populateSemanticas(list) {
    state.semanticas = Array.isArray(list) ? list : [];
    if (!secSemantica) return;
    secSemantica.innerHTML = "";
    const empty = document.createElement("option");
    empty.value = "";
    empty.textContent = "Nenhuma";
    secSemantica.appendChild(empty);
    state.semanticas.forEach((item) => {
      const opt = document.createElement("option");
      opt.value = item.nome_canonico;
      opt.textContent = `${item.nome_canonico} (${item.dominio})`;
      secSemantica.appendChild(opt);
    });
  }

  function updatePreview() {
    const src =
      state.viewMode === "draft"
        ? state.elementos
        : Array.isArray(state.elementosDraft) && state.elementosDraft.length
          ? state.elementosDraft
          : state.elementos;
    const sections = (src || []).map((el) => ({
      id: el.key,
      title: el.title,
      kind: el.kind,
      x: el.x,
      y: el.y,
      width: el.width,
      height: el.height,
      semantica: el.semantica,
      layer: el.layer || {},
      data: el.data && typeof el.data === "object" ? { ...el.data } : {},
    }));
    state.draft.layout = state.draft.layout || {};
    state.draft.layout.sections = sections;
    if (draftPreview) draftPreview.textContent = pretty(state.draft);
  }

  function markDirty() {
    if (state.viewMode !== "draft") return;
    state.dirty = true;
    setSaveState("Alterações não salvas", "text-bg-warning");
    if (state.autoSaveTimer) clearTimeout(state.autoSaveTimer);
    state.autoSaveTimer = setTimeout(() => {
      saveDraft({ silent: true }).catch((err) => {
        setSaveState("Falha no salvamento automático", "text-bg-danger");
        showAlert(
          err.message ||
            "Não foi possível salvar em segundo plano. Verifique a ligação à rede e tente «Salvar rascunho».",
          "warning"
        );
      });
    }, 2500);
  }

  function positionCanvasQuickActions() {
    if (!canvasQuickActions || !stageState.stage) return;
    if (!state.selectedId || state.viewMode !== "draft") {
      canvasQuickActions.classList.remove("po-quick-fab--fixed");
      canvasQuickActions.style.position = "";
      canvasQuickActions.style.left = "";
      canvasQuickActions.style.top = "";
      canvasQuickActions.style.transform = "";
      return;
    }
    const stage = stageState.stage;
    const node = stage.findOne("#" + state.selectedId);
    const vp = canvasViewport;
    if (!node || !vp) return;
    const rect = node.getClientRect();
    const sx = stage.scaleX();
    const sy = stage.scaleY();
    const stageBox = stage.container().getBoundingClientRect();
    const vpRect = vp.getBoundingClientRect();
    const fabW = canvasQuickActions.offsetWidth || 160;
    const fabH = canvasQuickActions.offsetHeight || 40;
    let left = stageBox.left + rect.x * sx + stage.x() + rect.width * sx + 10;
    let top = stageBox.top + rect.y * sy + stage.y() + 4;
    if (left + fabW > vpRect.right - 8) {
      left = stageBox.left + rect.x * sx + stage.x() - fabW - 10;
    }
    left = Math.max(vpRect.left + 8, Math.min(left, vpRect.right - fabW - 8));
    top = Math.max(vpRect.top + 8, Math.min(top, vpRect.bottom - fabH - 8));
    canvasQuickActions.classList.add("po-quick-fab--fixed");
    canvasQuickActions.style.position = "fixed";
    canvasQuickActions.style.left = `${Math.round(left)}px`;
    canvasQuickActions.style.top = `${Math.round(top)}px`;
    canvasQuickActions.style.transform = "";
  }

  function scheduleRender() {
    if (state.renderQueued) return;
    state.renderQueued = true;
    requestAnimationFrame(() => {
      state.renderQueued = false;
      renderKonva();
    });
  }

  function bindLeftButtonPan(panSurface) {
    const endPan = () => {
      window.removeEventListener("mousemove", onMove);
      window.removeEventListener("mouseup", onUp);
      window.removeEventListener("touchmove", onMove);
      window.removeEventListener("touchend", onUp);
      window.removeEventListener("touchcancel", onUp);
    };
    let startStageX = 0;
    let startStageY = 0;
    let startClientX = 0;
    let startClientY = 0;
    function onMove(ev) {
      const stage = stageState.stage;
      if (!stage) return;
      const t = ev.touches && ev.touches[0];
      const cx = t ? t.clientX : ev.clientX;
      const cy = t ? t.clientY : ev.clientY;
      if (!Number.isFinite(cx) || !Number.isFinite(cy)) return;
      panSurface._poPanDidMove = true;
      stage.position({
        x: startStageX + (cx - startClientX),
        y: startStageY + (cy - startClientY),
      });
      stage.batchDraw();
      requestAnimationFrame(() => {
        positionCanvasQuickActions();
        repositionMatrixInlineIfOpen();
      });
    }
    function onUp() {
      endPan();
      requestAnimationFrame(() => {
        positionCanvasQuickActions();
        repositionMatrixInlineIfOpen();
      });
    }
    panSurface.on("mousedown touchstart", (e) => {
      const evt = e.evt;
      if (evt.type === "mousedown" && evt.button !== 0) return;
      if (evt.type === "touchstart") evt.preventDefault();
      panSurface._poPanDidMove = false;
      const stage = stageState.stage;
      if (!stage) return;
      startStageX = stage.x();
      startStageY = stage.y();
      const t = evt.touches && evt.touches[0];
      startClientX = t ? t.clientX : evt.clientX;
      startClientY = t ? t.clientY : evt.clientY;
      if (!Number.isFinite(startClientX)) return;
      window.addEventListener("mousemove", onMove);
      window.addEventListener("mouseup", onUp);
      window.addEventListener("touchmove", onMove, { passive: false });
      window.addEventListener("touchend", onUp);
      window.addEventListener("touchcancel", onUp);
    });
  }

  function zoomStageApplyScale(newScale, pointerOverride) {
    const stage = stageState.stage;
    if (!stage) return;
    const oldScale = stage.scaleX();
    if (!oldScale || oldScale < 0.01) return;
    const pointer = pointerOverride || stage.getPointerPosition() || { x: stage.width() / 2, y: stage.height() / 2 };
    const mousePointTo = {
      x: (pointer.x - stage.x()) / oldScale,
      y: (pointer.y - stage.y()) / oldScale,
    };
    const sc = clamp(newScale, ZOOM_MIN, ZOOM_MAX);
    stage.scale({ x: sc, y: sc });
    stage.position({
      x: pointer.x - mousePointTo.x * sc,
      y: pointer.y - mousePointTo.y * sc,
    });
    stage.batchDraw();
    syncZoomSliderFromStage();
    requestAnimationFrame(() => {
      positionCanvasQuickActions();
      repositionMatrixInlineIfOpen();
    });
  }

  function syncZoomSliderFromStage() {
    const zr = document.getElementById("poZoomRange");
    const stage = stageState.stage;
    if (!zr || !stage) return;
    const pct = Math.round(stage.scaleX() * 100);
    const v = String(clamp(pct, Math.round(ZOOM_MIN * 100), Math.round(ZOOM_MAX * 100)));
    zr.value = v;
    zr.setAttribute("aria-valuenow", v);
  }

  /** Corpo da matriz sob o ponteiro (coordenadas do palco), para scroll interno. */
  function matrixBodyHitAtStagePoint(stageX, stageY) {
    for (let i = state.elementos.length - 1; i >= 0; i -= 1) {
      const el = state.elementos[i];
      if (!isMatrixKind(el.kind)) continue;
      const lx = stageX - el.x;
      const ly = stageY - el.y;
      const bb = getMatrixBodyBox(el);
      if (lx >= bb.bodyX && lx < bb.bodyX + bb.bodyW && ly >= bb.bodyY && ly < bb.bodyY + bb.bodyH) {
        return { el };
      }
    }
    return null;
  }

  function initStage() {
    if (!canvasBoard || !window.Konva) return;
    // Arraste de blocos e alças do transformer só com botão esquerdo (0=esquerdo, 1=meio, 2=direito).
    window.Konva.dragButtons = [0];
    if (!canvasBoard.dataset.poCtxMenuGuard) {
      canvasBoard.dataset.poCtxMenuGuard = "1";
      canvasBoard.addEventListener("contextmenu", (e) => e.preventDefault());
    }
    canvasBoard.innerHTML = "";
    const stage = new Konva.Stage({
      container: "canvasBoard",
      width: BOARD_WIDTH,
      height: BOARD_HEIGHT,
      draggable: false,
    });
    const layer = new Konva.Layer();
    const panBg = new Konva.Rect({
      name: PAN_SURFACE_NAME,
      x: 0,
      y: 0,
      width: BOARD_WIDTH,
      height: BOARD_HEIGHT,
      fill: "rgba(248, 250, 252, 0.45)",
      listening: true,
      perfectDrawEnabled: false,
    });
    bindLeftButtonPan(panBg);
    panBg.on("click tap", (e) => {
      e.cancelBubble = true;
      if (panBg._poPanDidMove) return;
      state.selectedId = null;
      state.matrixBandSel = null;
      setTransformerNodes([]);
      updateInspector();
      stage.batchDraw();
    });
    layer.add(panBg);
    const tr = new Konva.Transformer({
      rotateEnabled: false,
      keepRatio: false,
      ignoreStroke: true,
      enabledAnchors: ["top-left", "top-right", "bottom-left", "bottom-right"],
      boundBoxFunc(oldBox, newBox) {
        if (newBox.width < MIN_W || newBox.height < MIN_H) return oldBox;
        return newBox;
      },
    });
    layer.add(tr);
    stage.add(layer);

    stage.on("wheel", (e) => {
      if (e.evt.ctrlKey) {
        e.evt.preventDefault();
        const oldScale = stage.scaleX();
        const pointer = stage.getPointerPosition() || { x: stage.width() / 2, y: stage.height() / 2 };
        let direction = e.evt.deltaY > 0 ? 1 : -1;
        direction = -direction;
        const scaleBy = 1.04;
        const newScale = direction > 0 ? oldScale * scaleBy : oldScale / scaleBy;
        zoomStageApplyScale(newScale, pointer);
        return;
      }
      const p = stage.getPointerPosition();
      if (!p) return;
      const hit = matrixBodyHitAtStagePoint(p.x, p.y);
      if (!hit || state.viewMode !== "draft") return;
      ensureMatrixData(hit.el);
      const m = computeMatrixGridMetrics(hit.el);
      const maxPX = m.overflowPanMaxX || 0;
      const maxPY = m.overflowPanMaxY || 0;
      if (maxPX <= 0 && maxPY <= 0) return;
      const d = hit.el.data;
      if (!d.matrixPan) d.matrixPan = { x: 0, y: 0 };
      const dy = e.evt.deltaY;
      let did = false;
      if (e.evt.shiftKey && maxPX > 0) {
        d.matrixPan.x = clamp((d.matrixPan.x || 0) + dy, 0, maxPX);
        did = true;
      } else if (!e.evt.shiftKey && maxPY > 0) {
        d.matrixPan.y = clamp((d.matrixPan.y || 0) + dy, 0, maxPY);
        did = true;
      }
      if (!did) return;
      e.evt.preventDefault();
      markDirty();
      scheduleRender();
    });

    stage.on("click tap", (e) => {
      if (e.target === stage) {
        state.selectedId = null;
        state.matrixBandSel = null;
        setTransformerNodes([]);
        updateInspector();
        stage.batchDraw();
      }
    });

    stageState.stage = stage;
    stageState.layer = layer;
    stageState.tr = tr;
    stageState.panBg = panBg;
  }

  /** Linhas da grelha discretas (sem stroke nas células). */
  function drawMatrixGridLines(target, m, st, panX, panY) {
    const stroke = st.matrixGridStroke || "#e5e7eb";
    const top = m.rowTops[0] - panY;
    const bot = m.rowTops[m.visRowCount - 1] + m.rowHeights[m.visRowCount - 1] - panY;
    const left = m.colLefts[0] - panX;
    const right = m.colLefts[m.colCount - 1] + m.colWidths[m.colCount - 1] - panX;
    const lineOpts = {
      stroke,
      strokeWidth: 0.5,
      listening: false,
      perfectDrawEnabled: false,
      lineCap: "round",
      opacity: 0.55,
    };
    for (let c = 0; c <= m.colCount; c += 1) {
      const x =
        c === 0
          ? m.colLefts[0]
          : c === m.colCount
            ? m.colLefts[m.colCount - 1] + m.colWidths[m.colCount - 1]
            : m.colLefts[c];
      const xl = x - panX;
      target.add(
        new Konva.Line({
          points: [xl, top, xl, bot],
          ...lineOpts,
        })
      );
    }
    for (let r = 0; r <= m.visRowCount; r += 1) {
      const y =
        r === 0
          ? m.rowTops[0]
          : r === m.visRowCount
            ? m.rowTops[m.visRowCount - 1] + m.rowHeights[m.visRowCount - 1]
            : m.rowTops[r];
      const yl = y - panY;
      target.add(
        new Konva.Line({
          points: [left, yl, right, yl],
          ...lineOpts,
        })
      );
    }
  }

  /** Realça linha (clique no eixo) ou coluna (clique nos cabeçalhos). */
  function drawMatrixBandHighlight(clipG, el, m, panX, panY) {
    const b = state.matrixBandSel;
    if (!b || b.elKey !== el.key) return;
    const fill = "rgba(37, 99, 235, 0.07)";
    const stroke = "rgba(29, 78, 216, 0.25)";
    if (b.band === "row") {
      const r = b.index;
      if (r < 0 || r >= m.visRowCount) return;
      const cy = m.rowTops[r] - panY;
      const rh = m.rowHeights[r];
      const x0 = m.colLefts[0] - panX;
      const w = m.colLefts[m.colCount - 1] + m.colWidths[m.colCount - 1] - m.colLefts[0];
      clipG.add(
        new Konva.Rect({
          name: "po-mx-band-hl",
          x: x0,
          y: cy,
          width: w,
          height: rh,
          fill,
          stroke,
          strokeWidth: 0.5,
          listening: false,
        })
      );
    } else if (b.band === "col") {
      const c = b.index;
      if (c < 1 || c >= m.colCount) return;
      const cx = m.colLefts[c] - panX;
      const cw = m.colWidths[c];
      const y0 = m.rowTops[0] - panY;
      const h = m.rowTops[m.visRowCount - 1] + m.rowHeights[m.visRowCount - 1] - m.rowTops[0];
      clipG.add(
        new Konva.Rect({
          name: "po-mx-band-hl",
          x: cx,
          y: y0,
          width: cw,
          height: h,
          fill,
          stroke,
          strokeWidth: 0.5,
          listening: false,
        })
      );
    }
  }

  /** Desenha matriz estilo mapa: cabeçalhos em faixas, eixo fixo, totais opcionais, heatmap. */
  function drawMatrixOnGroup(group, el) {
    ensureMatrixData(el);
    const st = getCanvasStyle(el);
    const m = computeMatrixGridMetrics(el);
    const panX = m.panX || 0;
    const panY = m.panY || 0;
    const clipG = new Konva.Group();
    clipG.clip({ x: m.bodyX, y: m.bodyY, width: m.bodyW, height: m.bodyH });
    group.add(clipG);
    const vHeadCanvas = getVerticalHeaders(el.data);
    const baseText = st.matrixTextColor;
    const headerBandFills = [st.matrixHeaderBg, st.matrixHeaderAltBg, st.matrixHeaderBg];

    for (let r = 0; r < m.visRowCount; r += 1) {
      const rh = m.rowHeights[r];
      const fontHeadAuto = Math.max(6, Math.min(9, Math.floor(rh * 0.38)));
      const fontBodyAuto = Math.max(6, Math.min(10, Math.floor(rh * 0.42)));
      const fontHead =
        st.matrixFontPx > 0 ? clamp(Math.round(st.matrixFontPx * 0.92), 5, 14) : fontHeadAuto;
      const fontBody =
        st.matrixFontPx > 0 ? clamp(Math.round(st.matrixFontPx), 5, 14) : fontBodyAuto;
      const isFoot = m.tRow && r === m.rows.length;
      const isHeader = !isFoot && r < m.hBand;
      const isBody = !isFoot && !isHeader;
      for (let c = 0; c < m.colCount; c += 1) {
        const cx = m.colLefts[c] - panX;
        const cy = m.rowTops[r] - panY;
        const cw = m.colWidths[c];
        let fill = st.matrixCellBg;
        let color = baseText;
        let raw = "";
        if (isFoot) {
          raw = footerCellDisplay(m.rows, m.hBand, m.colCount, m.tRow, m.tCol, c);
        } else {
          const row = Array.isArray(m.rows[r]) ? m.rows[r] : [];
          if (m.tCol && c === m.colCount - 1 && r >= m.hBand) {
            raw = rowTotalDisplay(row, m.colCount, m.tCol);
          } else {
            raw = row[c] != null ? String(row[c]) : "";
          }
        }
        if (isHeader) {
          fill = headerBandFills[r % headerBandFills.length];
          if (c === 0) fill = st.matrixAxisBg;
        } else if (isFoot) {
          fill = st.matrixFooterBg;
          if (c === 0) fill = st.matrixFooterAxisBg;
        } else if (c === 0) {
          fill = st.matrixAxisBg;
        } else if (m.tCol && c === m.colCount - 1) {
          fill = "#eff6ff";
        } else if (m.heatmapOn) {
          const n = parsePercentCell(raw);
          if (n !== null) {
            const hb = heatmapBucket(n);
            fill = hb.fill;
            color = hb.color;
          }
        }
        clipG.add(
          new Konva.Rect({
            x: cx,
            y: cy,
            width: cw,
            height: rh,
            fill,
            strokeWidth: 0,
            listening: false,
          })
        );
      }
    }
    drawMatrixBandHighlight(clipG, el, m, panX, panY);
    for (let r = 0; r < m.visRowCount; r += 1) {
      const rh = m.rowHeights[r];
      const fontHeadAuto = Math.max(6, Math.min(9, Math.floor(rh * 0.38)));
      const fontBodyAuto = Math.max(6, Math.min(10, Math.floor(rh * 0.42)));
      const fontHead =
        st.matrixFontPx > 0 ? clamp(Math.round(st.matrixFontPx * 0.92), 5, 14) : fontHeadAuto;
      const fontBody =
        st.matrixFontPx > 0 ? clamp(Math.round(st.matrixFontPx), 5, 14) : fontBodyAuto;
      const isFoot = m.tRow && r === m.rows.length;
      const isHeader = !isFoot && r < m.hBand;
      const isBody = !isFoot && !isHeader;
      for (let c = 0; c < m.colCount; c += 1) {
        const cx = m.colLefts[c] - panX;
        const cy = m.rowTops[r] - panY;
        const cw = m.colWidths[c];
        let color = baseText;
        let raw = "";
        if (isFoot) {
          raw = footerCellDisplay(m.rows, m.hBand, m.colCount, m.tRow, m.tCol, c);
        } else {
          const row = Array.isArray(m.rows[r]) ? m.rows[r] : [];
          if (m.tCol && c === m.colCount - 1 && r >= m.hBand) {
            raw = rowTotalDisplay(row, m.colCount, m.tCol);
          } else {
            raw = row[c] != null ? String(row[c]) : "";
          }
        }
        if (isBody && m.heatmapOn && c > 0 && !(m.tCol && c === m.colCount - 1)) {
          const n = parsePercentCell(raw);
          if (n !== null) color = heatmapBucket(n).color;
        }
        const txt = raw.length > 80 ? `${raw.slice(0, 77)}…` : raw;
        const fs = isHeader || isFoot ? fontHead : fontBody;
        const align = isBody && c === 0 ? "left" : "center";
        const padX = align === "left" ? 4 : 2;
        const lastHeadBand = isHeader && r === m.hBand - 1;
        const vertColHeader =
          vHeadCanvas && lastHeadBand && c > 0 && cw >= MATRIX_VERT_HEADER_MIN_CW;
        if (vertColHeader) {
          const tg = new Konva.Group({
            x: cx + cw / 2,
            y: cy + rh / 2,
            rotation: -90,
            listening: false,
          });
          tg.add(
            new Konva.Text({
              x: -rh / 2,
              y: -cw / 2,
              width: rh - 2,
              height: cw - 2,
              text: txt || " ",
              fontSize: fs,
              fontFamily: st.matrixFontFamily,
              fill: color,
              align: "center",
              verticalAlign: "middle",
              wrap: "char",
              listening: false,
            })
          );
          clipG.add(tg);
        } else {
          clipG.add(
            new Konva.Text({
              x: cx + padX,
              y: cy + 1,
              width: cw - padX - 2,
              height: rh - 2,
              text: txt || " ",
              fontSize: fs,
              fontFamily: st.matrixFontFamily,
              fill: color,
              align,
              verticalAlign: "middle",
              fontStyle: isFoot ? "bold" : "normal",
              wrap: "word",
              listening: false,
            })
          );
        }
      }
    }
    drawMatrixGridLines(clipG, m, st, panX, panY);
  }

  function clientDeltaToStageWorld(deltaClient) {
    const st = stageState.stage;
    if (!st) return deltaClient;
    const cr = st.container().getBoundingClientRect();
    if (cr.width < 1) return deltaClient;
    return (deltaClient / cr.width) * st.width();
  }

  function cleanupMxGridDragListeners() {
    if (mxGridDragMove) {
      window.removeEventListener("mousemove", mxGridDragMove);
      window.removeEventListener("mouseup", mxGridDragUp);
      window.removeEventListener("touchmove", mxGridDragMove);
      window.removeEventListener("touchend", mxGridDragUp);
      window.removeEventListener("touchcancel", mxGridDragUp);
      mxGridDragMove = null;
      mxGridDragUp = null;
    }
  }

  function endMxGridDrag(commit) {
    cleanupMxGridDragListeners();
    poMatrixResizeCursor(null);
    const had = !!state.mxGridDrag;
    state.mxGridDrag = null;
    if (commit && had) {
      updatePreview();
      markDirty();
      scheduleRender();
    }
  }

  function beginMxGridDrag(ev, el, mode, index) {
    endMxGridDrag(false);
    if (state.mxReorder) endMxReorder(false);
    if (state.viewMode !== "draft" || !state.editMode) return;
    ensureMatrixData(el);
    const evt = ev.evt || ev;
    const t = evt.touches && evt.touches[0];
    const cx = Number.isFinite(t ? t.clientX : evt.clientX) ? (t ? t.clientX : evt.clientX) : 0;
    const cy = Number.isFinite(t ? t.clientY : evt.clientY) ? (t ? t.clientY : evt.clientY) : 0;
    pushHistory();
    const wcol = el.data.colWeights;
    const wrow = el.data.rowWeights;
    state.mxGridDrag = {
      elKey: el.key,
      mode,
      index,
      startClientX: cx,
      startClientY: cy,
      startWeights: mode === "col" ? [...wcol] : [...wrow],
      pairSum:
        mode === "col"
          ? wcol[index - 1] + wcol[index]
          : wrow[index - 1] + wrow[index],
    };
    mxGridDragMove = (e) => {
      if (!state.mxGridDrag || state.mxGridDrag.elKey !== el.key) return;
      if (e.type === "touchmove") e.preventDefault();
      const te = e.touches && e.touches[0];
      const mx = te ? te.clientX : e.clientX;
      const my = te ? te.clientY : e.clientY;
      const dx = clientDeltaToStageWorld(mx - state.mxGridDrag.startClientX);
      const dy = clientDeltaToStageWorld(my - state.mxGridDrag.startClientY);
      const m0 = computeMatrixGridMetrics(el);
      const innerWm = Math.max(4, m0.bodyW - m0.gap * 2);
      const innerHm = Math.max(4, m0.bodyH - m0.gap * 2);
      const colA = innerWm - m0.gap * (m0.colCount - 1);
      const rowA = innerHm - m0.gap * (m0.visRowCount - 1);
      if (state.mxGridDrag.mode === "col") {
        const c = state.mxGridDrag.index;
        const w = el.data.colWeights;
        const S = state.mxGridDrag.pairSum;
        const dw = (dx / Math.max(1, colA)) * S;
        let a = state.mxGridDrag.startWeights[c - 1] + dw;
        let b = state.mxGridDrag.startWeights[c] - dw;
        a = Math.max(MIN_MATRIX_WEIGHT, a);
        b = Math.max(MIN_MATRIX_WEIGHT, b);
        const s = a + b || 1;
        w[c - 1] = (a / s) * S;
        w[c] = (b / s) * S;
      } else {
        const rr = state.mxGridDrag.index;
        const w = el.data.rowWeights;
        const S = state.mxGridDrag.pairSum;
        const dh = (dy / Math.max(1, rowA)) * S;
        let a = state.mxGridDrag.startWeights[rr - 1] + dh;
        let b = state.mxGridDrag.startWeights[rr] - dh;
        a = Math.max(MIN_MATRIX_WEIGHT, a);
        b = Math.max(MIN_MATRIX_WEIGHT, b);
        const s = a + b || 1;
        w[rr - 1] = (a / s) * S;
        w[rr] = (b / s) * S;
      }
      state.mxGridDrag.startClientX = mx;
      state.mxGridDrag.startClientY = my;
      state.mxGridDrag.startWeights =
        state.mxGridDrag.mode === "col" ? [...el.data.colWeights] : [...el.data.rowWeights];
      state.mxGridDrag.pairSum =
        state.mxGridDrag.mode === "col"
          ? el.data.colWeights[state.mxGridDrag.index - 1] + el.data.colWeights[state.mxGridDrag.index]
          : el.data.rowWeights[state.mxGridDrag.index - 1] + el.data.rowWeights[state.mxGridDrag.index];
      stageState.stage && stageState.stage.batchDraw();
    };
    mxGridDragUp = () => {
      endMxGridDrag(true);
    };
    window.addEventListener("mousemove", mxGridDragMove);
    window.addEventListener("mouseup", mxGridDragUp);
    window.addEventListener("touchmove", mxGridDragMove, { passive: false });
    window.addEventListener("touchend", mxGridDragUp);
    window.addEventListener("touchcancel", mxGridDragUp);
  }

  function poMatrixResizeCursor(mode) {
    const st = stageState.stage;
    const c = st && st.container();
    if (!c) return;
    if (!mode) {
      c.style.cursor = "";
      return;
    }
    c.style.cursor = mode === "col" ? "col-resize" : "row-resize";
  }

  /** Linha fina + zona transparente — mapas densos não ficam cobertos por barras azuis. */
  function drawMatrixResizeHandles(group, el) {
    const prev = group.findOne(".po-mx-resize-g");
    if (prev) prev.destroy();
    const hg = new Konva.Group({ name: "po-mx-resize-g", listening: true });
    const m = computeMatrixGridMetrics(el);
    const px = m.panX || 0;
    const py = m.panY || 0;
    const innerLeft = m.bodyX + m.gap - px;
    const innerTop = m.bodyY + m.gap - py;
    const innerRight = m.colLefts[m.colCount - 1] + m.colWidths[m.colCount - 1] - px;
    const innerBot = m.rowTops[m.visRowCount - 1] + m.rowHeights[m.visRowCount - 1] - py;
    const innerWRect = Math.max(8, innerRight - innerLeft);
    const innerHRect = Math.max(8, innerBot - innerTop);
    const lineIdle = "rgba(148, 163, 184, 0.22)";
    const lineHover = "rgba(37, 99, 235, 0.55)";
    const bindDrag = (hit, mode, idx) => {
      hit.on("mousedown touchstart", (e) => {
        if (state.viewMode !== "draft" || !state.editMode) return;
        e.cancelBubble = true;
        beginMxGridDrag(e, el, mode, idx);
      });
    };
    for (let c = 1; c < m.colCount; c += 1) {
      const xmid = m.colLefts[c] - m.gap / 2 - px;
      const x0 = xmid - MX_RESIZE_HIT / 2;
      const g = new Konva.Group({ x: x0, y: innerTop });
      const line = new Konva.Line({
        points: [MX_RESIZE_HIT / 2, 0, MX_RESIZE_HIT / 2, innerHRect],
        stroke: lineIdle,
        strokeWidth: 0.55,
        listening: false,
        perfectDrawEnabled: false,
      });
      const hit = new Konva.Rect({
        name: "po-mx-resize-handle",
        x: 0,
        y: 0,
        width: MX_RESIZE_HIT,
        height: innerHRect,
        fill: "rgba(0,0,0,0.015)",
        listening: true,
      });
      hit.on("mouseenter", () => {
        line.stroke(lineHover);
        line.strokeWidth(1);
        poMatrixResizeCursor("col");
        hit.getLayer() && hit.getLayer().batchDraw();
      });
      hit.on("mouseleave", () => {
        line.stroke(lineIdle);
        line.strokeWidth(0.55);
        poMatrixResizeCursor(null);
        hit.getLayer() && hit.getLayer().batchDraw();
      });
      bindDrag(hit, "col", c);
      g.add(line);
      g.add(hit);
      hg.add(g);
    }
    for (let r = 1; r < m.visRowCount; r += 1) {
      const ymid = m.rowTops[r] - m.gap / 2 - py;
      const y0 = ymid - MX_RESIZE_HIT / 2;
      const g = new Konva.Group({ x: innerLeft, y: y0 });
      const line = new Konva.Line({
        points: [0, MX_RESIZE_HIT / 2, innerWRect, MX_RESIZE_HIT / 2],
        stroke: lineIdle,
        strokeWidth: 0.55,
        listening: false,
        perfectDrawEnabled: false,
      });
      const hit = new Konva.Rect({
        name: "po-mx-resize-handle",
        x: 0,
        y: 0,
        width: innerWRect,
        height: MX_RESIZE_HIT,
        fill: "rgba(0,0,0,0.015)",
        listening: true,
      });
      hit.on("mouseenter", () => {
        line.stroke(lineHover);
        line.strokeWidth(1);
        poMatrixResizeCursor("row");
        hit.getLayer() && hit.getLayer().batchDraw();
      });
      hit.on("mouseleave", () => {
        line.stroke(lineIdle);
        line.strokeWidth(0.55);
        poMatrixResizeCursor(null);
        hit.getLayer() && hit.getLayer().batchDraw();
      });
      bindDrag(hit, "row", r);
      g.add(line);
      g.add(hit);
      hg.add(g);
    }
    group.add(hg);
    hg.moveToTop();
  }

  function cleanupMxReorderListeners() {
    if (mxReorderMove) {
      window.removeEventListener("mousemove", mxReorderMove);
      window.removeEventListener("mouseup", mxReorderUp);
      window.removeEventListener("touchmove", mxReorderMove);
      window.removeEventListener("touchend", mxReorderUp);
      window.removeEventListener("touchcancel", mxReorderUp);
      mxReorderMove = null;
      mxReorderUp = null;
    }
  }

  function endMxReorder(commit) {
    cleanupMxReorderListeners();
    const ctx = state.mxReorder;
    state.mxReorder = null;
    if (ctx && ctx.dropLine) {
      try {
        ctx.dropLine.destroy();
      } catch (e) {
        /* ignore */
      }
    }
    if (commit && ctx && ctx.didApply) {
      updatePreview();
      markDirty();
      const sel = getSelected();
      if (sel && sel.key === ctx.elKey) renderMatrixInspector(sel);
    }
    if (ctx) scheduleRender();
  }

  function beginMxReorder(ev, el, axis, fromIndex) {
    if (state.viewMode !== "draft" || !state.editMode) return;
    if (state.mxGridDrag) endMxGridDrag(false);
    endMxReorder(false);
    closeMatrixInlineEditor(true);
    const stage = stageState.stage;
    if (!stage) return;
    const grp = stage.findOne(`#${el.key}`) || stage.findOne((n) => n.id && typeof n.id === "function" && n.id() === el.key);
    if (!grp) return;
    ensureMatrixData(el);
    const dropLine = new Konva.Line({
      name: "po-mx-reorder-drop",
      points: [0, 0, 0, 0],
      stroke: "#1d4ed8",
      strokeWidth: 2,
      dash: [5, 5],
      visible: false,
      listening: false,
    });
    grp.add(dropLine);
    dropLine.moveToTop();
    state.mxReorder = {
      elKey: el.key,
      axis,
      fromIndex,
      dropBefore: null,
      dropLine,
      didApply: false,
    };
    const evt = ev.evt || ev;
    const updateDrop = (clientX, clientY) => {
      if (!state.mxReorder || state.mxReorder.elKey !== el.key) return;
      const local = clientPointToGroupLocal(stage, grp, clientX, clientY);
      const m = computeMatrixGridMetrics(el);
      const panx = m.panX || 0;
      const pany = m.panY || 0;
      const vx = local.x + panx;
      const vy = local.y + pany;
      const innerLeft = m.bodyX + m.gap - panx;
      const innerTop = m.bodyY + m.gap - pany;
      const innerRight = m.colLefts[m.colCount - 1] + m.colWidths[m.colCount - 1] - panx;
      const innerBot = m.rowTops[m.visRowCount - 1] + m.rowHeights[m.visRowCount - 1] - pany;
      if (state.mxReorder.axis === "col") {
        const dropBefore = columnDropBeforeFromX(vx, m);
        state.mxReorder.dropBefore = dropBefore;
        const xg = columnGuideX(m, dropBefore) - panx;
        const xCl = clamp(xg, m.bodyX + 1, m.bodyX + m.bodyW - 1);
        dropLine.points([xCl, innerTop, xCl, innerBot]);
        dropLine.visible(true);
      } else {
        const dropBefore = rowDropBeforeFromY(vy, m);
        state.mxReorder.dropBefore = dropBefore;
        const yg = rowGuideY(m, dropBefore) - pany;
        const yCl = clamp(yg, m.bodyY + 1, m.bodyY + m.bodyH - 1);
        dropLine.points([innerLeft, yCl, innerRight, yCl]);
        dropLine.visible(true);
      }
      stage.batchDraw();
    };
    const t0 = evt.touches && evt.touches[0];
    updateDrop(
      Number.isFinite(t0 ? t0.clientX : evt.clientX) ? (t0 ? t0.clientX : evt.clientX) : 0,
      Number.isFinite(t0 ? t0.clientY : evt.clientY) ? (t0 ? t0.clientY : evt.clientY) : 0
    );
    mxReorderMove = (e) => {
      if (!state.mxReorder || state.mxReorder.elKey !== el.key) return;
      if (e.type === "touchmove") e.preventDefault();
      const te = e.touches && e.touches[0];
      const mx = te ? te.clientX : e.clientX;
      const my = te ? te.clientY : e.clientY;
      updateDrop(mx, my);
    };
    mxReorderUp = () => {
      const ctx = state.mxReorder;
      if (!ctx || ctx.elKey !== el.key) {
        endMxReorder(false);
        return;
      }
      const el2 = state.elementos.find((e) => e.key === el.key);
      let applied = false;
      if (el2 && ctx.dropBefore != null) {
        if (ctx.axis === "col") {
          applied = applyMatrixColReorder(el2, ctx.fromIndex, ctx.dropBefore);
        } else {
          applied = applyMatrixRowReorder(el2, ctx.fromIndex, ctx.dropBefore);
        }
      }
      if (applied) {
        ctx.didApply = true;
        pushHistory();
      }
      endMxReorder(true);
    };
    window.addEventListener("mousemove", mxReorderMove);
    window.addEventListener("mouseup", mxReorderUp);
    window.addEventListener("touchmove", mxReorderMove, { passive: false });
    window.addEventListener("touchend", mxReorderUp);
    window.addEventListener("touchcancel", mxReorderUp);
    if (evt.preventDefault) evt.preventDefault();
  }

  function drawMatrixReorderHandles(group, el) {
    const prev = group.findOne(".po-mx-reorder-g");
    if (prev) prev.destroy();
    const rg = new Konva.Group({ name: "po-mx-reorder-g", listening: true });
    const m = computeMatrixGridMetrics(el);
    const px = m.panX || 0;
    const py = m.panY || 0;
    const { minC, maxC } = matrixDraggableColBounds(el);
    const { minR, maxR, hBand } = matrixDraggableRowBounds(el);
    const gripFill = "rgba(37,99,235,0.04)";
    const gripStroke = "rgba(29,78,216,0.16)";
    if (maxC >= minC && m.hBand >= 1) {
      const rHead = m.hBand - 1;
      const rh = m.rowHeights[rHead];
      const gripH = Math.min(MX_REORDER_COL_GRIP_H, Math.max(4, rh - 4));
      const yGrip = m.rowTops[rHead] + rh - gripH - 1 - py;
      for (let c = minC; c <= maxC; c += 1) {
        const cx = m.colLefts[c] - px;
        const cw = m.colWidths[c];
        const g = new Konva.Rect({
          name: "po-mx-reorder-grip",
          x: cx + 2,
          y: yGrip,
          width: Math.max(6, cw - 4),
          height: gripH,
          fill: gripFill,
          stroke: gripStroke,
          strokeWidth: 0.55,
          cornerRadius: 2,
          listening: true,
        });
        g.on("mousedown touchstart", (e) => {
          if (state.viewMode !== "draft" || !state.editMode) return;
          e.cancelBubble = true;
          beginMxReorder(e, el, "col", c);
        });
        rg.add(g);
      }
    }
    if (maxR >= minR) {
      for (let r = minR; r <= maxR; r += 1) {
        const cy = m.rowTops[r] - py;
        const rh = m.rowHeights[r];
        const gw = Math.min(MX_REORDER_ROW_GRIP_W, Math.max(6, m.colWidths[0] - 4));
        const g = new Konva.Rect({
          name: "po-mx-reorder-grip",
          x: m.colLefts[0] - px + 2,
          y: cy + 3,
          width: gw,
          height: Math.max(6, rh - 6),
          fill: gripFill,
          stroke: gripStroke,
          strokeWidth: 0.55,
          cornerRadius: 2,
          listening: true,
        });
        g.on("mousedown touchstart", (e) => {
          if (state.viewMode !== "draft" || !state.editMode) return;
          e.cancelBubble = true;
          beginMxReorder(e, el, "row", r);
        });
        rg.add(g);
      }
    }
    group.add(rg);
    rg.moveToTop();
  }

  function repositionMatrixInlineIfOpen() {
    if (!matrixInlineEl || matrixInlineEl.style.display === "none" || !state.matrixInline || !stageState.stage) return;
    const el = state.elementos.find((e) => e.key === state.matrixInline.elKey);
    const grp = stageState.stage.findOne((n) => n.id && n.id() === state.matrixInline.elKey);
    if (el && grp && isMatrixKind(el.kind)) positionMatrixInlineEditor(grp, el, state.matrixInline.r, state.matrixInline.c);
  }

  function positionMatrixInlineEditor(group, el, r, c) {
    const ta = matrixInlineEl;
    const stage = group.getStage();
    if (!ta || !stage || !canvasViewport) return;
    const rect = matrixCellRectInGroup(el, r, c);
    const absT = group.getAbsoluteTransform();
    const p1 = absT.point({ x: rect.x, y: rect.y });
    const p2 = absT.point({ x: rect.x + rect.w, y: rect.y + rect.h });
    const minX = Math.min(p1.x, p2.x);
    const minY = Math.min(p1.y, p2.y);
    const maxX = Math.max(p1.x, p2.x);
    const maxY = Math.max(p1.y, p2.y);
    const cont = stage.container();
    const cr = cont.getBoundingClientRect();
    const sw = stage.width();
    const sh = stage.height();
    if (!sw || !sh) return;
    const scaleX = cr.width / sw;
    const scaleY = cr.height / sh;
    const clientLeft = cr.left + minX * scaleX;
    const clientTop = cr.top + minY * scaleY;
    const clientW = (maxX - minX) * scaleX;
    const clientH = (maxY - minY) * scaleY;
    const vr = canvasViewport.getBoundingClientRect();
    ta.style.left = `${Math.round(clientLeft - vr.left + canvasViewport.scrollLeft)}px`;
    ta.style.top = `${Math.round(clientTop - vr.top + canvasViewport.scrollTop)}px`;
    ta.style.width = `${Math.round(Math.max(clientW + 4, 40))}px`;
    ta.style.height = `${Math.round(Math.max(clientH + 4, 24))}px`;
  }

  function closeMatrixInlineEditor(commit) {
    clearTimeout(matrixInlineBlurTimer);
    const ta = matrixInlineEl;
    if (!state.matrixInline) {
      if (ta && ta.style.display !== "none") ta.style.display = "none";
      return;
    }
    const ctx = state.matrixInline;
    state.matrixInline = null;
    if (!ta) return;
    const val = ta.value;
    ta.style.display = "none";
    if (!commit) return;
    const el = state.elementos.find((e) => e.key === ctx.elKey);
    if (!el || !isMatrixKind(el.kind)) return;
    ensureMatrixData(el);
    while (el.data.rows.length <= ctx.r) el.data.rows.push([]);
    while ((el.data.rows[ctx.r] || []).length <= ctx.c) el.data.rows[ctx.r].push("");
    const orig = ctx.original != null ? String(ctx.original) : "";
    if (val !== orig) pushHistory();
    el.data.rows[ctx.r][ctx.c] = val;
    updatePreview();
    markDirty();
    scheduleRender();
    const sel = getSelected();
    if (sel && sel.key === el.key) renderMatrixInspector(sel);
  }

  function getOrCreateMatrixInlineEl() {
    if (matrixInlineEl) return matrixInlineEl;
    if (!canvasViewport) return null;
    matrixInlineEl = document.createElement("textarea");
    matrixInlineEl.className = "po-matrix-inline-edit form-control form-control-sm";
    matrixInlineEl.setAttribute("aria-label", "Editar célula na prancheta");
    matrixInlineEl.rows = 2;
    matrixInlineEl.style.display = "none";
    matrixInlineEl.style.position = "absolute";
    matrixInlineEl.style.zIndex = "45";
    matrixInlineEl.style.boxSizing = "border-box";
    matrixInlineEl.style.margin = "0";
    matrixInlineEl.addEventListener("keydown", (ev) => {
      if (ev.key === "Enter" && !ev.shiftKey) {
        ev.preventDefault();
        closeMatrixInlineEditor(true);
      } else if (ev.key === "Escape") {
        ev.preventDefault();
        closeMatrixInlineEditor(false);
      }
    });
    matrixInlineEl.addEventListener("blur", () => {
      clearTimeout(matrixInlineBlurTimer);
      matrixInlineBlurTimer = setTimeout(() => {
        if (!matrixInlineEl || matrixInlineEl.style.display === "none") return;
        if (document.activeElement === matrixInlineEl) return;
        closeMatrixInlineEditor(true);
      }, 120);
    });
    canvasViewport.appendChild(matrixInlineEl);
    return matrixInlineEl;
  }

  function openMatrixCellInlineEditor(group, el, cell) {
    if (cell.readOnly) return;
    closeMatrixInlineEditor(true);
    const ta = getOrCreateMatrixInlineEl();
    if (!ta) return;
    ensureMatrixData(el);
    while (el.data.rows.length <= cell.r) el.data.rows.push([]);
    while ((el.data.rows[cell.r] || []).length <= cell.c) el.data.rows[cell.r].push("");
    const cur = el.data.rows[cell.r][cell.c] != null ? String(el.data.rows[cell.r][cell.c]) : "";
    ta.value = cur;
    state.matrixInline = { elKey: el.key, r: cell.r, c: cell.c, original: cur };
    positionMatrixInlineEditor(group, el, cell.r, cell.c);
    ta.style.display = "block";
    ta.focus();
    ta.select();
  }

  function drawElement(el) {
    const layer = stageState.layer;
    const tr = stageState.tr;
    if (!layer || !tr) return;

    const st = getCanvasStyle(el);
    const sel = state.selectedId === el.key;
    const borderW = clamp(Math.round(sel ? st.selectionStrokeWidth : st.cardStrokeWidth), 1, 6);
    const borderColor = sel ? st.selectionStroke : st.cardStroke;

    const group = new Konva.Group({
      x: el.x,
      y: el.y,
      draggable: state.editMode && state.viewMode === "draft",
      id: el.key,
      width: el.width,
      height: el.height,
    });

    const bg = new Konva.Rect({
      name: "po-card-bg",
      x: 0,
      y: 0,
      width: el.width,
      height: el.height,
      fill: st.cardBg,
      stroke: borderColor,
      strokeWidth: borderW,
      cornerRadius: 8,
      shadowEnabled: false,
    });
    group.add(bg);

    const header = new Konva.Rect({
      name: "po-card-header",
      x: 0,
      y: 0,
      width: el.width,
      height: 28,
      fill: st.headerBg,
      stroke: st.cardStroke,
      strokeWidth: 1,
      cornerRadius: [8, 8, 0, 0],
    });
    group.add(header);

    const titleText = new Konva.Text({
      name: "po-card-title",
      x: 8,
      y: 6,
      width: el.width - 16,
      text: `${el.title}   [${isMatrixKind(el.kind) ? "tabela" : el.kind}]`,
      fontSize: clamp(Math.round(st.titleFontPx), 8, 24),
      fontFamily: st.titleFontFamily,
      fill: st.titleColor,
      fontStyle: "bold",
    });
    group.add(titleText);

    if (isMatrixKind(el.kind)) {
      ensureMatrixData(el);
      const { bodyX, bodyY, bodyW, bodyH } = getMatrixBodyBox(el);
      group.add(
        new Konva.Rect({
          x: bodyX,
          y: bodyY,
          width: bodyW,
          height: bodyH,
          fill: st.bodyPanelBg,
          stroke: st.bodyPanelStroke,
          strokeWidth: 0.55,
          cornerRadius: 4,
          listening: false,
        })
      );
      drawMatrixOnGroup(group, el);
      if (state.viewMode === "draft" && state.editMode && state.selectedId === el.key) {
        drawMatrixResizeHandles(group, el);
        drawMatrixReorderHandles(group, el);
      }
    } else {
      const layer = el.layer || {};
      const layerParts = [layer.setor, layer.bloco, layer.pavimento, layer.unidade].filter(Boolean);
      group.add(
        new Konva.Text({
          x: 8,
          y: 38,
          width: el.width - 16,
          text: `${el.semantica ? `Semântica: ${el.semantica}\n` : ""}${layerParts.length ? `Camadas: ${layerParts.join(" › ")}` : "Camadas não definidas"}`,
          fontSize: clamp(Math.round(st.bodyFontPx), 8, 22),
          fontFamily: st.bodyFontFamily,
          fill: st.bodyTextColor,
        })
      );
    }

    group.on("click tap", (evt) => {
      evt.cancelBubble = true;
      state.selectedId = el.key;
      const tn = evt.target.name && typeof evt.target.name === "function" ? evt.target.name() : "";
      const skipBandSel = tn === "po-mx-resize-handle" || tn === "po-mx-reorder-grip";
      state.matrixBandSel = null;
      if (
        !skipBandSel &&
        isMatrixKind(el.kind) &&
        state.viewMode === "draft" &&
        state.editMode
      ) {
        const pos = group.getRelativePointerPosition();
        if (pos && Number.isFinite(pos.x) && Number.isFinite(pos.y)) {
          const cell = matrixCellAtPointer(el, pos.x, pos.y);
          if (cell) {
            const m = computeMatrixGridMetrics(el);
            const isFoot = m.tRow && cell.r === m.rows.length;
            if (cell.c === 0 && cell.r >= m.hBand && !isFoot) {
              state.matrixBandSel = { elKey: el.key, band: "row", index: cell.r };
            } else if (cell.c >= 1 && cell.r < m.hBand && !isFoot) {
              state.matrixBandSel = { elKey: el.key, band: "col", index: cell.c };
            }
          }
        }
      }
      setTransformerNodes(state.viewMode === "draft" ? [group] : []);
      updateInspector();
      stageState.stage && stageState.stage.batchDraw();
    });

    group.on("dblclick dbltap", (evt) => {
      if (state.viewMode !== "draft") return;
      const pos = group.getRelativePointerPosition();
      if (isMatrixKind(el.kind) && pos && Number.isFinite(pos.x) && Number.isFinite(pos.y)) {
        const cell = matrixCellAtPointer(el, pos.x, pos.y);
        if (cell && !cell.readOnly) {
          evt.cancelBubble = true;
          openMatrixCellInlineEditor(group, el, cell);
          return;
        }
      }
      const n = evt.target.name && typeof evt.target.name === "function" ? evt.target.name() : "";
      if (n !== "po-card-title" && n !== "po-card-header") return;
      evt.cancelBubble = true;
      openEditorOffcanvas();
      setTimeout(() => {
        const it = document.getElementById("insTitle");
        if (it) {
          it.focus();
          it.select();
        }
      }, 350);
    });

    group.on("contextmenu", (evt) => {
      evt.evt.preventDefault();
      evt.cancelBubble = true;
      state.selectedId = el.key;
      setTransformerNodes(state.viewMode === "draft" ? [group] : []);
      updateInspector();
      stageState.stage && stageState.stage.batchDraw();
      if (state.viewMode === "draft") openCardContextMenu(evt.evt.clientX, evt.evt.clientY, el.key);
    });

    group.on("dragstart", () => {
      if (!state.editMode || state.viewMode !== "draft") return;
      pushHistory();
    });

    group.on("dragmove", () => {
      if (!state.editMode || state.viewMode !== "draft") return;
      const rawX = group.x();
      const rawY = group.y();
      const next = snapPositionWithGuides(el, rawX, rawY);
      group.position(next);
      stageState.stage && stageState.stage.batchDraw();
    });

    group.on("dragend", () => {
      clearAlignmentGuides();
      const next = snapPositionWithGuides(el, group.x(), group.y());
      el.x = next.x;
      el.y = next.y;
      group.position({ x: el.x, y: el.y });
      updatePreview();
      markDirty();
    });

    group.on("transformstart", () => {
      if (!state.editMode || state.viewMode !== "draft") return;
      pushHistory();
    });

    group.on("transformend", () => {
      clearAlignmentGuides();
      const sx = group.scaleX();
      const sy = group.scaleY();
      const rawW = Math.abs(group.width() * sx);
      const rawH = Math.abs(group.height() * sy);
      // Cantos que movem a origem + largura máx. global faziam x+w > BOARD sem recorte → cartão «sumia» à direita/baixo.
      let nx = snap(clamp(group.x(), 0, BOARD_WIDTH - MIN_W));
      let ny = snap(clamp(group.y(), 0, BOARD_HEIGHT - MIN_H));
      group.scale({ x: 1, y: 1 });
      let nw = snap(clamp(rawW, MIN_W, MAX_CARD_W));
      let nh = snap(clamp(rawH, MIN_H, MAX_CARD_H));
      nw = snap(clamp(Math.min(nw, BOARD_WIDTH - nx), MIN_W, MAX_CARD_W));
      nh = snap(clamp(Math.min(nh, BOARD_HEIGHT - ny), MIN_H, MAX_CARD_H));
      el.width = nw;
      el.height = nh;
      el.x = nx;
      el.y = ny;
      group.width(el.width);
      group.height(el.height);
      group.position({ x: el.x, y: el.y });
      const mainBg = group.findOne(".po-card-bg");
      if (mainBg) {
        mainBg.width(el.width);
        mainBg.height(el.height);
      }
      updatePreview();
      markDirty();
      // Redesenhar no próximo frame: evita reentrância no Transformer durante o fim do transform.
      requestAnimationFrame(() => scheduleRender());
    });

    layer.add(group);
    if (state.selectedId === el.key && state.viewMode === "draft" && state.editMode) {
      setTransformerNodes([group]);
    }
  }

  function renderKonva() {
    if (!stageState.stage) initStage();
    if (!stageState.layer || !stageState.stage) return;
    const layer = stageState.layer;
    const tr = stageState.tr;
    if (!tr) return;
    cleanupMxGridDragListeners();
    cleanupMxReorderListeners();
    state.mxGridDrag = null;
    state.mxReorder = null;
    if (
      !state.selectedId ||
      (state.matrixBandSel && state.matrixBandSel.elKey !== state.selectedId)
    ) {
      state.matrixBandSel = null;
    }
    closeCardContextMenu();
    // Sempre soltar nós do Transformer antes de destruir grupos — senão o Konva chama setAttrs em referências mortas.
    setTransformerNodes([]);
    // Nunca usar destroyChildren(): apaga o Transformer e o fundo de pan.
    const panBg = stageState.panBg;
    layer.getChildren().forEach((node) => {
      if (node !== tr && node !== panBg) node.destroy();
    });
    state.elementos.forEach((el) => drawElement(el));
    if (panBg) panBg.moveToBottom();
    tr.moveToTop();
    stageState.stage.batchDraw();
    updateInspector();
    requestAnimationFrame(() => repositionMatrixInlineIfOpen());
  }

  function fitView() {
    if (!stageState.stage) return;
    const stage = stageState.stage;
    if (!state.elementos.length) {
      stage.position({ x: 0, y: 0 });
      stage.scale({ x: 1, y: 1 });
      stage.batchDraw();
      syncZoomSliderFromStage();
      requestAnimationFrame(() => {
        positionCanvasQuickActions();
        repositionMatrixInlineIfOpen();
      });
      return;
    }
    const minX = Math.min(...state.elementos.map((e) => e.x));
    const minY = Math.min(...state.elementos.map((e) => e.y));
    const maxX = Math.max(...state.elementos.map((e) => e.x + e.width));
    const maxY = Math.max(...state.elementos.map((e) => e.y + e.height));
    const boxW = Math.max(100, maxX - minX + 80);
    const boxH = Math.max(100, maxY - minY + 80);
    const scale = clamp(Math.min(stage.width() / boxW, stage.height() / boxH), ZOOM_MIN, ZOOM_FIT_CAP);
    stage.scale({ x: scale, y: scale });
    stage.position({
      x: -minX * scale + 40,
      y: -minY * scale + 40,
    });
    stage.batchDraw();
    syncZoomSliderFromStage();
    requestAnimationFrame(() => {
      positionCanvasQuickActions();
      repositionMatrixInlineIfOpen();
    });
  }

  function updateInspector() {
    if (state.inspectorUndoSelId !== state.selectedId) {
      state.inspectorUndoSelId = state.selectedId;
      state.inspectorLiveUndoPushed = false;
    }
    const selected = getSelected();
    const has = !!selected;
    const draftUi = state.viewMode === "draft";
    if (inspectorEmpty) inspectorEmpty.classList.toggle("d-none", has);
    if (inspectorForm) inspectorForm.classList.toggle("d-none", !has);
    if (canvasQuickActions) canvasQuickActions.classList.toggle("d-none", !has || !draftUi);
    const panelTitle = document.getElementById("poEditorPanelLabel");
    if (panelTitle) {
      panelTitle.textContent = has && selected.title ? selected.title : "Painel de edição";
      panelTitle.title = has && selected.title ? selected.title : "";
    }
    if (!has) {
      renderMatrixInspector(null);
      return;
    }
    if (insTitle) insTitle.value = selected.title || "";
    if (insSemantica) insSemantica.value = selected.semantica || "";
    const layer = selected.layer || {};
    if (insSetor) insSetor.value = layer.setor || "";
    if (insBloco) insBloco.value = layer.bloco || "";
    if (insPavimento) insPavimento.value = layer.pavimento || "";
    if (insUnidade) insUnidade.value = layer.unidade || "";
    if (matrixTools) matrixTools.classList.toggle("d-none", !isMatrixKind(selected.kind));
    if (isMatrixKind(selected.kind)) {
      if (insMatrixLevels) insMatrixLevels.value = String(getHeaderBandCount(selected.data));
      if (insMatrixHeatmap) insMatrixHeatmap.checked = !!selected.data.heatmap;
      if (insMatrixTotalsCol) insMatrixTotalsCol.checked = getTotalsColumnAuto(selected.data);
      if (insMatrixTotalsRow) insMatrixTotalsRow.checked = getTotalsRowAuto(selected.data);
      if (insMatrixVerticalHeaders) insMatrixVerticalHeaders.checked = getVerticalHeaders(selected.data);
    }
    // Recriar a grelha HTML durante a digitação destroi o contenteditable e perde o foco a cada tecla.
    const skipMatrixDom =
      isMatrixKind(selected.kind) &&
      matrixGridEditor &&
      matrixGridEditor.contains(document.activeElement);
    if (!skipMatrixDom) renderMatrixInspector(selected);
    requestAnimationFrame(() => positionCanvasQuickActions());
  }

  function escMxCell(s) {
    return String(s ?? "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;");
  }

  function renderMatrixInspector(selected) {
    if (!matrixGridEditor) return;
    if (!selected || !isMatrixKind(selected.kind)) {
      matrixGridEditor.innerHTML = "";
      return;
    }
    ensureMatrixData(selected);
    const rows = selected.data.rows || [];
    const h = getHeaderBandCount(selected.data);
    const heatOn = !!selected.data.heatmap;
    const tCol = getTotalsColumnAuto(selected.data);
    const tRow = getTotalsRowAuto(selected.data);
    const vHead = getVerticalHeaders(selected.data);
    const mxReadOnly = state.viewMode !== "draft";
    if (!rows.length) rows.push([""]);
    const colCount = Math.max(...rows.map((r) => (Array.isArray(r) ? r.length : 0)), 1);
    const tableCls = `po-matrix-table-edit${vHead ? " po-mx-vhead" : ""}${mxReadOnly ? " po-mx-readonly" : ""}`;
    const headRows = [];
    for (let hr = 0; hr < h; hr += 1) {
      const row = Array.isArray(rows[hr]) ? rows[hr] : [];
      const cells = Array.from({ length: colCount }, (_, cIdx) => {
        const value = row[cIdx] ?? "";
        const axisCls = hr === h - 1 && cIdx === 0 ? " po-mx-axis" : "";
        const hCls = "po-mx-hcell";
        return `<th class="${hCls}${axisCls}" contenteditable="${mxReadOnly ? "false" : "true"}" data-r="${hr}" data-c="${cIdx}">${escMxCell(value)}</th>`;
      }).join("");
      headRows.push(`<tr>${cells}</tr>`);
    }
    const bodyFixed = rows
      .slice(h)
      .map((row, rIdx) => {
        const absR = h + rIdx;
        const cells = Array.from({ length: colCount }, (_, cIdx) => {
          const value = row[cIdx] ?? "";
          if (tCol && cIdx === colCount - 1) {
            const disp = rowTotalDisplay(row, colCount, tCol);
            const heat = heatClassForValue(disp, heatOn);
            return `<td class="po-mx-ro po-mx-total-col ${heat}" contenteditable="false" data-readonly="1">${escMxCell(disp)}</td>`;
          }
          const heat = cIdx > 0 ? heatClassForValue(value, heatOn) : "";
          return `<td class="${heat}" contenteditable="${mxReadOnly ? "false" : "true"}" data-r="${absR}" data-c="${cIdx}">${escMxCell(value)}</td>`;
        }).join("");
        return `<tr>${cells}</tr>`;
      })
      .join("");
    let foot = "";
    if (tRow) {
      const footCells = Array.from({ length: colCount }, (_, cIdx) => {
        const disp = footerCellDisplay(rows, h, colCount, tRow, tCol, cIdx);
        const heat = cIdx > 0 ? heatClassForValue(disp, heatOn) : "";
        return `<td class="po-mx-ro ${heat}" contenteditable="false" data-readonly="1">${escMxCell(disp)}</td>`;
      }).join("");
      foot = `<tfoot><tr>${footCells}</tr></tfoot>`;
    }
    const legend = heatOn ? matrixHeatLegendHtml() : "";
    matrixGridEditor.innerHTML = `<table class="${tableCls}"><thead>${headRows.join("")}</thead><tbody>${bodyFixed}</tbody>${foot}</table>${legend}`;
  }

  function setMatrixHeaderLevels(next) {
    if (state.viewMode !== "draft") return;
    const selected = getSelected();
    if (!selected || !isMatrixKind(selected.kind)) return;
    pushHistory();
    ensureMatrixData(selected);
    const d = selected.data;
    const rows = d.rows;
    let target = Math.min(3, Math.max(1, Math.floor(Number(next)) || 1));
    let cur = getHeaderBandCount(d);
    const colCount = Math.max(1, ...rows.map((r) => (Array.isArray(r) ? r.length : 0)));
    while (cur < target) {
      rows.unshift(Array.from({ length: colCount }, () => ""));
      cur += 1;
    }
    while (cur > target && rows.length > target + 1) {
      rows.shift();
      cur -= 1;
    }
    d.headerBandCount = target;
    ensureMatrixData(selected);
    updatePreview();
    markDirty();
    renderMatrixInspector(selected);
    scheduleRender();
  }

  function applyMatrixMapaPreset() {
    if (state.viewMode !== "draft") return;
    const selected = getSelected();
    if (!selected || !isMatrixKind(selected.kind)) {
      showAlert("Selecione uma tabela matriz na prancheta.", "warning");
      return;
    }
    pushHistory();
    selected.data.rows = matrixMapaPresetRows();
    selected.data.headerBandCount = 2;
    selected.data.heatmap = true;
    selected.data.totalsColumnAuto = true;
    selected.data.totalsRowAuto = true;
    selected.data.verticalHeaders = true;
    if (insMatrixLevels) insMatrixLevels.value = "2";
    if (insMatrixHeatmap) insMatrixHeatmap.checked = true;
    if (insMatrixTotalsCol) insMatrixTotalsCol.checked = true;
    if (insMatrixTotalsRow) insMatrixTotalsRow.checked = true;
    if (insMatrixVerticalHeaders) insMatrixVerticalHeaders.checked = true;
    ensureMatrixData(selected);
    updatePreview();
    markDirty();
    renderMatrixInspector(selected);
    scheduleRender();
  }

  function setInspectorReadOnly(readOnly) {
    const panel = document.getElementById("poEditorPanel");
    if (!panel) return;
    panel.querySelectorAll("input, select, textarea, button").forEach((node) => {
      if (node.classList.contains("btn-close")) return;
      if (node.type === "hidden") return;
      const act = node.getAttribute("data-po-action");
      if (act === "reload") {
        node.disabled = false;
        return;
      }
      node.disabled = !!readOnly;
    });
  }

  function readPublishedLayout() {
    const node = document.getElementById("poPublishedData");
    if (!node || !node.textContent) return [];
    try {
      const v = JSON.parse(node.textContent);
      if (!v || typeof v !== "object") return [];
      const sections = v.layout && Array.isArray(v.layout.sections) ? v.layout.sections : [];
      return sections.map((it, i) => normalizeElement(it, i));
    } catch (e) {
      return [];
    }
  }

  function updateViewModeButtons() {
    const bd = document.getElementById("btnViewDraft");
    const bp = document.getElementById("btnViewPublished");
    const banner = document.getElementById("poPublishedViewBanner");
    if (bd) bd.classList.toggle("active", state.viewMode === "draft");
    if (bp) bp.classList.toggle("active", state.viewMode === "published");
    if (banner) banner.classList.toggle("d-none", state.viewMode === "draft");
  }

  function pollDraftConflictOnce() {
    if (state.viewMode !== "draft" || !state.dirty || document.hidden) return;
    if (!state.draftKnownUpdatedAt) return;
    requestJson(ctx.endpoints.detail, { credentials: "same-origin" })
      .then((data) => {
        const srv = data.draft && data.draft.updated_at;
        if (srv && srv !== state.draftKnownUpdatedAt) {
          showAlert(
            "O rascunho mudou no servidor (outra aba ou outro utilizador). Use «Recarregar dados» para alinhar com a versão remota, ou «Salvar rascunho» para substituir o servidor pela sua cópia (será pedida confirmação).",
            "warning"
          );
          setSaveState("Conflito: versão remota mais nova", "text-bg-warning");
          if (state.conflictPollTimer) clearInterval(state.conflictPollTimer);
          state.conflictPollTimer = null;
        }
      })
      .catch(() => {});
  }

  function startDraftConflictPoll() {
    if (state.conflictPollTimer) clearInterval(state.conflictPollTimer);
    state.conflictPollTimer = setInterval(pollDraftConflictOnce, DRAFT_CONFLICT_POLL_MS);
    pollDraftConflictOnce();
  }

  document.addEventListener("visibilitychange", () => {
    if (!document.hidden) pollDraftConflictOnce();
  });

  async function ensureDraftNotStaleOrConfirm(silent) {
    if (!state.draftKnownUpdatedAt) return true;
    try {
      const data = await requestJson(ctx.endpoints.detail, { credentials: "same-origin" });
      const srv = data.draft && data.draft.updated_at;
      if (!srv || srv === state.draftKnownUpdatedAt) return true;
      if (silent) {
        setSaveState("Conflito: versão remota mais nova", "text-bg-warning");
        if (!state.conflictSkipAlertShown) {
          state.conflictSkipAlertShown = true;
          showAlert(
            "Há uma versão mais recente do rascunho no servidor. O salvamento automático não foi guardado para não apagar essas alterações. Faça «Recarregar dados» para editar a versão remota, ou «Salvar rascunho» e confirme para substituir.",
            "warning"
          );
        }
        return false;
      }
      return window.confirm(
        "O rascunho no servidor foi alterado (outra sessão ou outro utilizador).\n\nDeseja substituir a versão remota pela sua cópia local?\n\nOK — Enviar e substituir no servidor.\nCancelar — Não guardar; use «Recarregar dados» para obter o rascunho remoto."
      );
    } catch {
      return true;
    }
  }

  function switchViewMode(mode) {
    if (mode === state.viewMode) return;
    closeCardContextMenu();
    cleanupMxGridDragListeners();
    cleanupMxReorderListeners();
    state.mxGridDrag = null;
    state.mxReorder = null;
    state.matrixBandSel = null;
    closeMatrixInlineEditor(true);
    resetHistory();
    if (mode === "published") {
      state.editModeBeforePublished = state.editMode;
      state.elementosDraft = state.elementos.map((el) => JSON.parse(JSON.stringify(el)));
      state.selectedDraftId = state.selectedId;
      const pubEls = readPublishedLayout();
      state.elementos = pubEls.length ? pubEls : [];
      if (!pubEls.length) {
        showAlert("Não há layout na versão publicada (ou ainda não foi publicada).", "info");
      }
      state.selectedId = state.elementos[0] ? state.elementos[0].key : null;
      state.editMode = false;
      if (btnToggleEdit) {
        btnToggleEdit.disabled = true;
        btnToggleEdit.classList.add("disabled");
      }
      setInspectorReadOnly(true);
    } else {
      if (state.elementosDraft) {
        state.elementos = state.elementosDraft.map((it, idx) => normalizeElement(it, idx));
        state.selectedId =
          state.selectedDraftId && state.elementos.some((e) => e.key === state.selectedDraftId)
            ? state.selectedDraftId
            : state.elementos[0]
              ? state.elementos[0].key
              : null;
      }
      state.elementosDraft = null;
      state.editMode = state.editModeBeforePublished;
      if (btnToggleEdit) {
        btnToggleEdit.disabled = false;
        btnToggleEdit.classList.remove("disabled");
      }
      setInspectorReadOnly(false);
    }
    state.viewMode = mode;
    if (btnToggleEdit) {
      btnToggleEdit.innerHTML = `<i class="bi bi-pencil-square"></i> Modo edição: ${state.editMode ? "ON" : "OFF"}`;
    }
    updateViewModeButtons();
    updateDraftOnlyControls();
    updatePreview();
    renderKonva();
    fitView();
  }

  async function loadDetails() {
    const btnReload = document.getElementById("btnReloadDraft");
    hideAlert();
    cleanupMxGridDragListeners();
    cleanupMxReorderListeners();
    state.mxGridDrag = null;
    state.mxReorder = null;
    state.matrixBandSel = null;
    closeMatrixInlineEditor(false);
    setButtonLoading(btnReload, true);
    try {
      const data = await requestJson(ctx.endpoints.detail, { credentials: "same-origin" });
      state.draft = data.draft || {};
      state.draftKnownUpdatedAt = (data.draft && data.draft.updated_at) || null;
      populateSemanticas(data.semanticas || []);
      const sectionsFallback =
        state.draft.layout && Array.isArray(state.draft.layout.sections) ? state.draft.layout.sections : [];
      const draftElementos = Array.isArray(data.elementos) && data.elementos.length
        ? data.elementos.map((it, idx) => normalizeElement(it, idx))
        : sectionsFallback.map((it, idx) => normalizeElement(it, idx));
      const pubNode = document.getElementById("poPublishedData");
      if (pubNode && data.published) pubNode.textContent = JSON.stringify(data.published);
      if (state.viewMode === "published") {
        state.elementosDraft = draftElementos.map((el) => JSON.parse(JSON.stringify(el)));
        const pubEls = readPublishedLayout();
        state.elementos = pubEls.length ? pubEls : [];
        state.selectedId = state.elementos[0] ? state.elementos[0].key : null;
      } else {
        state.elementos = draftElementos;
        if (
          !state.selectedId ||
          !state.elementos.some((e) => e.key === state.selectedId)
        ) {
          state.selectedId = state.elementos[0] ? state.elementos[0].key : null;
        }
      }
      state.dirty = false;
      state.matrixEditUndoPushed = false;
      state.conflictSkipAlertShown = false;
      resetHistory();
      setSaveState("Sem alterações", "text-bg-light");
      renderKonva();
      fitView();
      if (state.viewMode === "draft") setInspectorReadOnly(false);
      else setInspectorReadOnly(true);
      updateDraftOnlyControls();
    } catch (err) {
      showAlert(err.message || "Falha ao recarregar.", "danger");
      throw err;
    } finally {
      setButtonLoading(btnReload, false);
    }
    startDraftConflictPoll();
  }

  async function addSection() {
    if (state.viewMode !== "draft") return;
    hideAlert();
    const payload = {
      title: (secTitle && secTitle.value ? secTitle.value : "").trim(),
      kind: secKind ? secKind.value : "",
      semantica: secSemantica ? secSemantica.value : "",
    };
    if (!payload.title || !payload.kind) {
      showAlert("Informe título e tipo da seção.", "warning");
      return;
    }
    await requestJson(ctx.endpoints.addSection, {
      method: "POST",
      credentials: "same-origin",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": ctx.csrfToken,
      },
      body: JSON.stringify(payload),
    });
    if (secTitle) secTitle.value = "";
    await loadDetails();
    showAlert("Seção adicionada no rascunho.", "success");
  }

  async function addQuickSection(kind, defaultTitle) {
    if (secKind) secKind.value = kind;
    if (secTitle && !secTitle.value.trim()) secTitle.value = defaultTitle;
    await addSection();
  }

  function buildSyncPayload() {
    return state.elementos.map((el) => ({
      id: el.id,
      chave_externa: el.key,
      title: el.title,
      kind: el.kind,
      semantica: el.semantica || "",
      x: snap(el.x),
      y: snap(el.y),
      width: snap(el.width),
      height: snap(el.height),
      layer: el.layer || {},
      data: el.data || {},
    }));
  }

  async function saveDraft(options) {
    if (state.viewMode !== "draft") return undefined;
    const opts = options || {};
    const silent = !!opts.silent;
    const btnSave = document.getElementById("btnSaveDraft");
    if (!(await ensureDraftNotStaleOrConfirm(silent))) {
      if (!silent) setSaveState("Gravação cancelada (conflito com o servidor)", "text-bg-warning");
      return false;
    }
    if (!silent) hideAlert();
    setSaveState("Salvando...", "text-bg-info");
    if (!silent) {
      setButtonLoading(btnSave, true);
      if (btnSave) btnSave.removeAttribute("title");
    }
    try {
      const payload = { items: buildSyncPayload() };
      const resSync = await requestJson(ctx.endpoints.syncElements, {
        method: "POST",
        credentials: "same-origin",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": ctx.csrfToken,
        },
        body: JSON.stringify(payload),
      });
      if (resSync.rascunho && resSync.rascunho.updated_at) state.draftKnownUpdatedAt = resSync.rascunho.updated_at;
      const resSave = await requestJson(ctx.endpoints.saveDraft, {
        method: "POST",
        credentials: "same-origin",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": ctx.csrfToken,
        },
        body: JSON.stringify({ layout: state.draft.layout || {}, metadados: state.draft.metadados || {} }),
      });
      if (resSave.rascunho && resSave.rascunho.updated_at) state.draftKnownUpdatedAt = resSave.rascunho.updated_at;
      state.dirty = false;
      state.conflictSkipAlertShown = false;
      if (state.autoSaveTimer) {
        clearTimeout(state.autoSaveTimer);
        state.autoSaveTimer = null;
      }
      setSaveState("Salvo", "text-bg-success");
      if (!silent) showAlert("Rascunho salvo com elementos estruturados.", "success");
      startDraftConflictPoll();
      return true;
    } catch (err) {
      setSaveState("Erro ao salvar", "text-bg-danger");
      if (!silent && btnSave) btnSave.title = err.message || "Falha ao salvar";
      if (!silent) showAlert(err.message || "Não foi possível salvar o rascunho.", "danger");
      throw err;
    } finally {
      if (!silent) setButtonLoading(btnSave, false);
    }
  }

  async function publish() {
    if (state.viewMode !== "draft") {
      showAlert("Volte ao modo Rascunho para publicar.", "warning");
      return;
    }
    const btnPub = document.querySelector('#poEditorPanel button[data-po-action="publish"]');
    hideAlert();
    setButtonLoading(btnPub, true);
    if (btnPub) btnPub.removeAttribute("title");
    try {
      const saved = await saveDraft();
      if (saved === false) return;
      await requestJson(ctx.endpoints.publish, {
        method: "POST",
        credentials: "same-origin",
        headers: {
          "X-CSRFToken": ctx.csrfToken,
        },
      });
      showAlert("Versão publicada com sucesso.", "success");
      await loadDetails();
    } catch (err) {
      if (btnPub) btnPub.title = err.message || "Falha ao publicar";
      showAlert(err.message || "Não foi possível publicar.", "danger");
      throw err;
    } finally {
      setButtonLoading(btnPub, false);
    }
  }

  function applyInspectorChanges() {
    if (state.viewMode !== "draft") return;
    const selected = getSelected();
    if (!selected) return;
    if (!state.inspectorLiveUndoPushed) {
      pushHistory();
    }
    selected.title = (insTitle && insTitle.value ? insTitle.value : selected.title || "").trim() || "Sem título";
    const pt = document.getElementById("poEditorPanelLabel");
    if (pt) pt.textContent = selected.title;
    selected.semantica = (insSemantica && insSemantica.value ? insSemantica.value : "").trim();
    selected.layer = {
      setor: (insSetor && insSetor.value ? insSetor.value : "").trim(),
      bloco: (insBloco && insBloco.value ? insBloco.value : "").trim(),
      pavimento: (insPavimento && insPavimento.value ? insPavimento.value : "").trim(),
      unidade: (insUnidade && insUnidade.value ? insUnidade.value : "").trim(),
    };
    updatePreview();
    markDirty();
    scheduleRender();
  }

  function duplicateSelectedSection() {
    if (state.viewMode !== "draft") return;
    const selected = getSelected();
    if (!selected) return;
    pushHistory();
    const copy = JSON.parse(JSON.stringify(selected));
    copy.id = null;
    copy.key = uuidShort();
    copy.title = `${copy.title} (cópia)`;
    const pos = suggestedDuplicatePosition(selected);
    copy.x = pos.x;
    copy.y = pos.y;
    state.elementos.push(copy);
    state.selectedId = copy.key;
    updatePreview();
    markDirty();
    scheduleRender();
  }

  function removeSelectedSection() {
    if (state.viewMode !== "draft") return;
    const selected = getSelected();
    if (!selected) return;
    pushHistory();
    state.elementos = state.elementos.filter((it) => it.key !== selected.key);
    state.selectedId = state.elementos[0] ? state.elementos[0].key : null;
    updatePreview();
    markDirty();
    scheduleRender();
  }

  function addMatrixRow() {
    if (state.viewMode !== "draft") return;
    const selected = getSelected();
    if (!selected || !isMatrixKind(selected.kind)) {
      const first = state.elementos.find((it) => isMatrixKind(it.kind));
      if (!first) {
        showAlert("Não há tabela para adicionar linha.", "warning");
        return;
      }
      state.selectedId = first.key;
      updateInspector();
      return;
    }
    pushHistory();
    ensureMatrixData(selected);
    const colCount = Math.max(1, ...selected.data.rows.map((r) => (Array.isArray(r) ? r.length : 0)));
    selected.data.rows.push(Array.from({ length: colCount }, () => ""));
    const tR = getTotalsRowAuto(selected.data);
    if (Array.isArray(selected.data.rowWeights)) {
      if (tR && selected.data.rowWeights.length > 0) {
        selected.data.rowWeights.splice(selected.data.rowWeights.length - 1, 0, 1);
      } else {
        selected.data.rowWeights.push(1);
      }
    }
    ensureMatrixData(selected);
    updatePreview();
    markDirty();
    scheduleRender();
  }

  function addMatrixCol() {
    if (state.viewMode !== "draft") return;
    const selected = getSelected();
    if (!selected || !isMatrixKind(selected.kind)) {
      const first = state.elementos.find((it) => isMatrixKind(it.kind));
      if (!first) {
        showAlert("Não há tabela para adicionar coluna.", "warning");
        return;
      }
      state.selectedId = first.key;
      updateInspector();
      return;
    }
    pushHistory();
    ensureMatrixData(selected);
    const h = getHeaderBandCount(selected.data);
    const tCol = getTotalsColumnAuto(selected.data);
    const colCount0 = Math.max(1, ...selected.data.rows.map((r) => (Array.isArray(r) ? r.length : 0)));
    const insertIdx = tCol ? colCount0 - 1 : colCount0;
    const numData = colCount0 - 1 - (tCol ? 1 : 0);
    const cellLabel = `Atividade ${Math.max(1, numData + 1)}`;
    selected.data.rows.forEach((row, idx) => {
      if (!Array.isArray(row)) return;
      while (row.length < colCount0) row.push("");
      let cell = "";
      if (idx < h - 1) cell = "";
      else if (idx === h - 1) cell = cellLabel;
      else cell = "";
      row.splice(insertIdx, 0, cell);
    });
    if (Array.isArray(selected.data.colWeights) && selected.data.colWeights.length === colCount0) {
      const leftW =
        insertIdx - 1 >= 0
          ? Number(selected.data.colWeights[insertIdx - 1]) || 1
          : Number(selected.data.colWeights[0]) || 1;
      const rightW =
        insertIdx < selected.data.colWeights.length
          ? Number(selected.data.colWeights[insertIdx]) || leftW
          : leftW;
      const wNew = Math.max(MIN_MATRIX_WEIGHT, (leftW + rightW) / 2);
      selected.data.colWeights.splice(insertIdx, 0, wNew);
    }
    ensureMatrixData(selected);
    updatePreview();
    markDirty();
    scheduleRender();
  }

  function removeMatrixRow() {
    if (state.viewMode !== "draft") return;
    const selected = getSelected();
    if (!selected || !isMatrixKind(selected.kind)) {
      showAlert("Selecione a matriz na prancheta.", "warning");
      return;
    }
    ensureMatrixData(selected);
    const h = getHeaderBandCount(selected.data);
    if (selected.data.rows.length <= h + 1) {
      showAlert("É preciso manter ao menos uma linha de dados.", "warning");
      return;
    }
    pushHistory();
    selected.data.rows.pop();
    const tR = getTotalsRowAuto(selected.data);
    if (Array.isArray(selected.data.rowWeights) && selected.data.rowWeights.length > 0) {
      if (tR && selected.data.rowWeights.length > 1) {
        selected.data.rowWeights.splice(selected.data.rowWeights.length - 2, 1);
      } else {
        selected.data.rowWeights.pop();
      }
    }
    ensureMatrixData(selected);
    updatePreview();
    markDirty();
    renderMatrixInspector(selected);
    scheduleRender();
  }

  function removeMatrixCol() {
    if (state.viewMode !== "draft") return;
    const selected = getSelected();
    if (!selected || !isMatrixKind(selected.kind)) {
      showAlert("Selecione a matriz na prancheta.", "warning");
      return;
    }
    ensureMatrixData(selected);
    const tCol = getTotalsColumnAuto(selected.data);
    const colCount = Math.max(1, ...selected.data.rows.map((r) => (Array.isArray(r) ? r.length : 0)));
    const minCols = tCol ? 3 : 2;
    if (colCount <= minCols) {
      showAlert("Não é possível remover mais colunas.", "warning");
      return;
    }
    pushHistory();
    const removeIdx = tCol ? colCount - 2 : colCount - 1;
    selected.data.rows.forEach((row) => {
      if (Array.isArray(row) && row.length > removeIdx) row.splice(removeIdx, 1);
    });
    if (Array.isArray(selected.data.colWeights) && selected.data.colWeights.length > removeIdx) {
      selected.data.colWeights.splice(removeIdx, 1);
    }
    ensureMatrixData(selected);
    updatePreview();
    markDirty();
    renderMatrixInspector(selected);
    scheduleRender();
  }

  function syncMatrixOptionFlagsFromInputs() {
    if (state.viewMode !== "draft") return;
    const sel = getSelected();
    if (!sel || !isMatrixKind(sel.kind)) return;
    pushHistory();
    if (insMatrixTotalsCol) sel.data.totalsColumnAuto = insMatrixTotalsCol.checked;
    if (insMatrixTotalsRow) sel.data.totalsRowAuto = insMatrixTotalsRow.checked;
    if (insMatrixVerticalHeaders) sel.data.verticalHeaders = insMatrixVerticalHeaders.checked;
    ensureMatrixData(sel);
    if (insMatrixTotalsCol) insMatrixTotalsCol.checked = getTotalsColumnAuto(sel.data);
    renderMatrixInspector(sel);
    updatePreview();
    markDirty();
    scheduleRender();
  }

  function applyMatrixCsvImport() {
    if (state.viewMode !== "draft") return;
    const selected = getSelected();
    if (!selected || !isMatrixKind(selected.kind)) {
      showAlert("Selecione a matriz na prancheta.", "warning");
      return;
    }
    if (!matrixCsvArea || !matrixCsvArea.value.trim()) {
      showAlert("Cole o CSV no campo acima.", "warning");
      return;
    }
    const rawCsv = matrixCsvArea.value;
    if (rawCsv.length > MAX_CSV_BYTES) {
      showAlert(`CSV muito grande (máx. ${Math.round(MAX_CSV_BYTES / 1024)} KB).`, "danger");
      return;
    }
    const parsed = parseMatrixCsv(rawCsv);
    if (!parsed || !parsed.length) {
      showAlert("Não foi possível ler o CSV (tamanho ou formato inválido).", "warning");
      return;
    }
    const colCount = Math.max(...parsed.map((r) => r.length));
    let cells = 0;
    parsed.forEach((row) => {
      while (row.length < colCount) row.push("");
      cells += row.length;
    });
    if (parsed.length > MAX_CSV_ROWS || colCount > MAX_CSV_COLS || cells > MAX_CSV_CELLS) {
      showAlert(
        `Limites: até ${MAX_CSV_ROWS} linhas, ${MAX_CSV_COLS} colunas e ${MAX_CSV_CELLS} células. Reduza o CSV.`,
        "danger"
      );
      return;
    }
    pushHistory();
    selected.data.rows = parsed;
    selected.data.headerBandCount = 1;
    selected.data.totalsColumnAuto = false;
    selected.data.totalsRowAuto = false;
    if (insMatrixLevels) insMatrixLevels.value = "1";
    if (insMatrixTotalsCol) insMatrixTotalsCol.checked = false;
    if (insMatrixTotalsRow) insMatrixTotalsRow.checked = false;
    ensureMatrixData(selected);
    updatePreview();
    markDirty();
    renderMatrixInspector(selected);
    scheduleRender();
  }

  function applyMatrixCsvExport() {
    const selected = getSelected();
    if (!selected || !isMatrixKind(selected.kind)) {
      showAlert("Selecione a matriz na prancheta.", "warning");
      return;
    }
    ensureMatrixData(selected);
    const text = exportMatrixCsv(selected.data.rows);
    if (matrixCsvArea) matrixCsvArea.value = text;
  }

  function openAppearanceFromUi(clientX, clientY) {
    if (state.viewMode !== "draft") return;
    const sel = getSelected();
    if (!sel) return;
    const ax = Number.isFinite(clientX) ? clientX : state.contextMenuAnchor.x;
    const ay = Number.isFinite(clientY) ? clientY : state.contextMenuAnchor.y;
    openAppearancePopover(ax, ay, sel.key);
  }

  if (btnAddSection) btnAddSection.addEventListener("click", () => addSection().catch((err) => showAlert(err.message, "danger")));
  if (btnQuickTable) btnQuickTable.addEventListener("click", () => addQuickSection("matrix_table", "Matriz de Controle").catch((err) => showAlert(err.message, "danger")));
  if (btnQuickBlock) btnQuickBlock.addEventListener("click", () => addQuickSection("list_table", "Bloco de Controle").catch((err) => showAlert(err.message, "danger")));
  if (btnQuickKpi) btnQuickKpi.addEventListener("click", () => addQuickSection("kpi_strip", "Faixa KPI").catch((err) => showAlert(err.message, "danger")));
  if (btnQuickDetail) btnQuickDetail.addEventListener("click", () => addQuickSection("detail_panel", "Detalhamento").catch((err) => showAlert(err.message, "danger")));
  if (btnFitView) btnFitView.addEventListener("click", fitView);
  if (btnToggleEdit) {
    btnToggleEdit.addEventListener("click", () => {
      if (state.viewMode !== "draft") return;
      state.editMode = !state.editMode;
      btnToggleEdit.innerHTML = `<i class="bi bi-pencil-square"></i> Modo edição: ${state.editMode ? "ON" : "OFF"}`;
      if (!state.editMode) setTransformerNodes([]);
      renderKonva();
    });
  }
  const btnUndo = document.getElementById("btnUndo");
  const btnRedo = document.getElementById("btnRedo");
  if (btnUndo) btnUndo.addEventListener("click", () => undo());
  if (btnRedo) btnRedo.addEventListener("click", () => redo());
  const btnZoomIn = document.getElementById("btnZoomIn");
  const btnZoomOut = document.getElementById("btnZoomOut");
  const poZoomRange = document.getElementById("poZoomRange");
  if (btnZoomIn) {
    btnZoomIn.addEventListener("click", () => {
      const stage = stageState.stage;
      if (!stage) return;
      const p = stage.getPointerPosition() || { x: stage.width() / 2, y: stage.height() / 2 };
      zoomStageApplyScale(stage.scaleX() * 1.12, p);
    });
  }
  if (btnZoomOut) {
    btnZoomOut.addEventListener("click", () => {
      const stage = stageState.stage;
      if (!stage) return;
      const p = stage.getPointerPosition() || { x: stage.width() / 2, y: stage.height() / 2 };
      zoomStageApplyScale(stage.scaleX() / 1.12, p);
    });
  }
  if (poZoomRange) {
    poZoomRange.addEventListener("input", () => {
      const stage = stageState.stage;
      if (!stage) return;
      const pct = Number(poZoomRange.value);
      if (!Number.isFinite(pct)) return;
      const p = { x: stage.width() / 2, y: stage.height() / 2 };
      zoomStageApplyScale(pct / 100, p);
    });
  }
  const btnViewDraft = document.getElementById("btnViewDraft");
  const btnViewPublished = document.getElementById("btnViewPublished");
  if (btnViewDraft) btnViewDraft.addEventListener("click", () => switchViewMode("draft"));
  if (btnViewPublished) btnViewPublished.addEventListener("click", () => switchViewMode("published"));
  if (btnSaveDraft) btnSaveDraft.addEventListener("click", () => saveDraft().catch((err) => showAlert(err.message, "danger")));

  const poEditorPanel = document.getElementById("poEditorPanel");
  if (poEditorPanel) {
    poEditorPanel.addEventListener("click", (ev) => {
      const btn = ev.target.closest("[data-po-action]");
      if (!btn || !poEditorPanel.contains(btn)) return;
      const action = btn.getAttribute("data-po-action");
      if (!action) return;
      ev.preventDefault();
      if (action === "reload") {
        loadDetails().catch((err) => showAlert(err.message, "danger"));
      } else if (action === "publish") {
        publish().catch((err) => showAlert(err.message, "danger"));
      } else if (action === "apply") {
        applyInspectorChanges();
      } else if (action === "dup-section") {
        duplicateSelectedSection();
      } else if (action === "remove-section") {
        removeSelectedSection();
      } else if (action === "add-row") {
        addMatrixRow();
      } else if (action === "add-col") {
        addMatrixCol();
      } else if (action === "remove-row") {
        removeMatrixRow();
      } else if (action === "remove-col") {
        removeMatrixCol();
      } else if (action === "matrix-preset-mapa") {
        applyMatrixMapaPreset();
      } else if (action === "matrix-csv-import") {
        applyMatrixCsvImport();
      } else if (action === "matrix-csv-export") {
        applyMatrixCsvExport();
      } else if (action === "appearance-pop") {
        openAppearanceFromUi(ev.clientX, ev.clientY);
      }
    });
    if (window.bootstrap && window.bootstrap.Offcanvas) {
      poEditorPanel.addEventListener("shown.bs.offcanvas", () => {
        closeCardContextMenu();
        updateInspector();
      });
    }
    const liveInspectorIds = ["insTitle", "insSemantica", "insSetor", "insBloco", "insPavimento", "insUnidade"];
    poEditorPanel.addEventListener("input", (ev) => {
      if (state.viewMode !== "draft") return;
      const t = ev.target;
      if (!(t instanceof HTMLElement) || !liveInspectorIds.includes(t.id)) return;
      const sel = getSelected();
      if (!sel) return;
      if (!state.inspectorLiveUndoPushed) {
        pushHistory();
        state.inspectorLiveUndoPushed = true;
      }
      if (t.id === "insTitle") {
        sel.title = t.value.trim() || "Sem título";
        const pt = document.getElementById("poEditorPanelLabel");
        if (pt) pt.textContent = sel.title;
      } else if (t.id === "insSemantica") sel.semantica = t.value.trim();
      else {
        sel.layer = sel.layer || {};
        if (t.id === "insSetor") sel.layer.setor = t.value.trim();
        if (t.id === "insBloco") sel.layer.bloco = t.value.trim();
        if (t.id === "insPavimento") sel.layer.pavimento = t.value.trim();
        if (t.id === "insUnidade") sel.layer.unidade = t.value.trim();
      }
      updatePreview();
      scheduleRender();
    });
    if (insMatrixLevels) {
      insMatrixLevels.addEventListener("change", () => setMatrixHeaderLevels(insMatrixLevels.value));
    }
    if (insMatrixHeatmap) {
      insMatrixHeatmap.addEventListener("change", () => {
        if (state.viewMode !== "draft") return;
        const sel = getSelected();
        if (!sel || !isMatrixKind(sel.kind)) return;
        pushHistory();
        sel.data.heatmap = insMatrixHeatmap.checked;
        renderMatrixInspector(sel);
        updatePreview();
        markDirty();
        scheduleRender();
      });
    }
    [insMatrixTotalsCol, insMatrixTotalsRow, insMatrixVerticalHeaders].forEach((el) => {
      if (el) el.addEventListener("change", () => syncMatrixOptionFlagsFromInputs());
    });
  }
  const btnQuickAppearanceSelected = document.getElementById("btnQuickAppearanceSelected");
  if (btnQuickAppearanceSelected) {
    btnQuickAppearanceSelected.addEventListener("click", (e) => {
      const r = e.currentTarget.getBoundingClientRect();
      openAppearanceFromUi(r.right + 4, r.top);
    });
  }
  if (btnQuickDuplicateSelected) btnQuickDuplicateSelected.addEventListener("click", duplicateSelectedSection);
  if (btnQuickDeleteSelected) btnQuickDeleteSelected.addEventListener("click", removeSelectedSection);
  if (canvasViewport) {
    canvasViewport.addEventListener(
      "scroll",
      () =>
        requestAnimationFrame(() => {
          positionCanvasQuickActions();
          repositionMatrixInlineIfOpen();
        }),
      { passive: true }
    );
  }
  window.addEventListener("resize", () =>
    requestAnimationFrame(() => {
      positionCanvasQuickActions();
      repositionMatrixInlineIfOpen();
    })
  );
  if (matrixGridEditor) {
    function clearMatrixGridHighlights() {
      matrixGridEditor.querySelectorAll(".po-mx-highlight-row, .po-mx-highlight-col").forEach((n) => {
        n.classList.remove("po-mx-highlight-row", "po-mx-highlight-col");
      });
    }
    matrixGridEditor.addEventListener("mouseover", (ev) => {
      const cell = ev.target && ev.target.closest && ev.target.closest("td,th");
      if (!cell || !matrixGridEditor.contains(cell)) return;
      const tr = cell.closest("tr");
      const table = cell.closest("table");
      if (!tr || !table) return;
      clearMatrixGridHighlights();
      tr.classList.add("po-mx-highlight-row");
      const c = cell.getAttribute("data-c");
      if (c == null) return;
      table.querySelectorAll(`[data-c="${String(c).replace(/"/g, "")}"]`).forEach((td) => td.classList.add("po-mx-highlight-col"));
    });
    matrixGridEditor.addEventListener("mouseout", (ev) => {
      const rel = ev.relatedTarget;
      if (rel && matrixGridEditor.contains(rel)) return;
      clearMatrixGridHighlights();
    });
    matrixGridEditor.addEventListener(
      "blur",
      (event) => {
        const target = event.target;
        if (!(target instanceof HTMLElement) || (target.tagName !== "TD" && target.tagName !== "TH")) return;
        if (target.closest("[data-readonly]")) return;
        if (state.viewMode !== "draft") return;
        const selected = getSelected();
        if (!selected || !isMatrixKind(selected.kind)) return;
        ensureMatrixData(selected);
        const r = Number(target.getAttribute("data-r"));
        const c = Number(target.getAttribute("data-c"));
        if (!Number.isFinite(r) || !Number.isFinite(c)) return;
        while (selected.data.rows.length <= r) selected.data.rows.push([]);
        while ((selected.data.rows[r] || []).length <= c) selected.data.rows[r].push("");
        selected.data.rows[r][c] = target.textContent || "";
        updatePreview();
        markDirty();
        scheduleRender();
      },
      true
    );
    matrixGridEditor.addEventListener("input", (event) => {
      const target = event.target;
      if (!(target instanceof HTMLElement) || (target.tagName !== "TD" && target.tagName !== "TH")) return;
      if (target.closest("[data-readonly]")) return;
      if (state.viewMode !== "draft") return;
      const selected = getSelected();
      if (!selected || !isMatrixKind(selected.kind)) return;
      if (!state.matrixEditUndoPushed) {
        pushHistory();
        state.matrixEditUndoPushed = true;
      }
      ensureMatrixData(selected);
      const r = Number(target.getAttribute("data-r"));
      const c = Number(target.getAttribute("data-c"));
      if (!Number.isFinite(r) || !Number.isFinite(c)) return;
      while (selected.data.rows.length <= r) selected.data.rows.push([]);
      while ((selected.data.rows[r] || []).length <= c) selected.data.rows[r].push("");
      selected.data.rows[r][c] = target.textContent || "";
      updatePreview();
      scheduleRender();
    });
    matrixGridEditor.addEventListener("focusout", () => {
      setTimeout(() => {
        if (matrixGridEditor.contains(document.activeElement)) return;
        state.matrixEditUndoPushed = false;
        const sel = getSelected();
        if (sel && isMatrixKind(sel.kind)) renderMatrixInspector(sel);
      }, 0);
    });
  }

  window.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      if (document.getElementById("poAppearancePop")) {
        closeAppearancePopover();
        event.preventDefault();
        return;
      }
      const menu = document.getElementById("po-card-context-menu");
      if (menu && menu.classList.contains("is-open")) {
        closeContextMenuOnly();
        event.preventDefault();
        return;
      }
    }
    const target = event.target;
    const isTyping =
      target instanceof HTMLElement &&
      (target.tagName === "INPUT" || target.tagName === "TEXTAREA" || target.isContentEditable);
    if (isTyping) return;

    if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "z" && !event.shiftKey) {
      event.preventDefault();
      undo();
      return;
    }
    if ((event.ctrlKey || event.metaKey) && (event.key.toLowerCase() === "y" || (event.key.toLowerCase() === "z" && event.shiftKey))) {
      event.preventDefault();
      redo();
      return;
    }
    if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "s") {
      event.preventDefault();
      saveDraft().catch((err) => showAlert(err.message, "danger"));
      return;
    }
    if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "d") {
      event.preventDefault();
      duplicateSelectedSection();
      return;
    }
    if (event.key === "Delete" && state.viewMode === "draft") {
      const selected = getSelected();
      if (selected) removeSelectedSection();
    }
  });

  loadDetails().catch((err) => showAlert(err.message, "danger"));
})();

