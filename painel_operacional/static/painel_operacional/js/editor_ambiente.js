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
  const btnCanvasFullscreen = document.getElementById("btnCanvasFullscreen");
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
  const insMatrixAxisPct = document.getElementById("insMatrixAxisPct");
  const insMxGroupName = document.getElementById("insMxGroupName");
  const insMxGroupLayer = document.getElementById("insMxGroupLayer");
  const insMxGroupSel = document.getElementById("insMxGroupSel");
  const insMxLayerNow = document.getElementById("insMxLayerNow");
  const insMxLayerTrail = document.getElementById("insMxLayerTrail");
  const insMxLayerJump = document.getElementById("insMxLayerJump");
  const insMxRowStart = document.getElementById("insMxRowStart");
  const insMxRowEnd = document.getElementById("insMxRowEnd");
  const insMxColStart = document.getElementById("insMxColStart");
  const insMxColEnd = document.getElementById("insMxColEnd");
  const insMxBindingSel = document.getElementById("insMxBindingSel");
  const matrixCsvArea = document.getElementById("matrixCsvArea");
  const matrixExcelFile = document.getElementById("matrixExcelFile");
  const matrixExcelSheet = document.getElementById("matrixExcelSheet");
  const matrixExcelMode = document.getElementById("matrixExcelMode");
  const matrixExcelPreviewInfo = document.getElementById("matrixExcelPreviewInfo");
  const matrixExcelPreviewArea = document.getElementById("matrixExcelPreviewArea");
  const btnMatrixExcelApply = document.getElementById("btnMatrixExcelApply");
  const canvasViewport = document.getElementById("canvasViewport");
  const canvasCardShell = document.getElementById("canvasCardShell");
  const fullscreenHost = document.getElementById("poEditorRoot") || canvasCardShell;
  const ctxSetor = document.getElementById("ctxSetor");
  const ctxBloco = document.getElementById("ctxBloco");
  const ctxPavimento = document.getElementById("ctxPavimento");
  const ctxUnidade = document.getElementById("ctxUnidade");
  const ctxOnlyMatches = document.getElementById("ctxOnlyMatches");
  const ctxMatrixReadEnabled = document.getElementById("ctxMatrixReadEnabled");
  const ctxMatrixReadStrategy = document.getElementById("ctxMatrixReadStrategy");
  const ctxAliasSetor = document.getElementById("ctxAliasSetor");
  const ctxAliasBloco = document.getElementById("ctxAliasBloco");
  const ctxAliasPavimento = document.getElementById("ctxAliasPavimento");
  const ctxAliasUnidade = document.getElementById("ctxAliasUnidade");
  const btnCtxClear = document.getElementById("btnCtxClear");
  const btnCtxSave = document.getElementById("btnCtxSave");
  const btnCtxRestore = document.getElementById("btnCtxRestore");
  const ctxBlocoChips = document.getElementById("ctxBlocoChips");
  const ctxDrilldown = document.getElementById("ctxDrilldown");
  const ctxMatchInfo = document.getElementById("ctxMatchInfo");
  const ctxKpiCoverage = document.getElementById("ctxKpiCoverage");
  const ctxKpiMissing = document.getElementById("ctxKpiMissing");
  const ctxTrail = document.getElementById("ctxTrail");
  const layerSetorList = document.getElementById("layerSetorList");
  const layerBlocoList = document.getElementById("layerBlocoList");
  const layerPavimentoList = document.getElementById("layerPavimentoList");
  const layerUnidadeList = document.getElementById("layerUnidadeList");
  const missingLayerSummary = document.getElementById("missingLayerSummary");
  const missingLayerList = document.getElementById("missingLayerList");
  const btnApplyContextToSelectedMissing = document.getElementById("btnApplyContextToSelectedMissing");

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
  /** Intervalo para verificar se a versão remota mudou (evita pedidos excessivos em rede instável). */
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
  /** Primeira faixa de cabeçalho mais alta para suportar títulos verticais sem "aperto". */
  const MATRIX_VERT_HEADER_MIN_RH = 56;
  /** Debounce de relayout para resize/fullscreen (evita tempestade de renders). */
  const VIEWPORT_RELAYOUT_DEBOUNCE_MS = 130;
  /** Controlo de reordenação discreto (mapas densos). */
  const MX_REORDER_COL_GRIP_H = 6;
  const MX_REORDER_ROW_GRIP_W = 10;
  const stageState = { stage: null, layer: null, tr: null, panBg: null };
  const history = { past: [], future: [], max: 40, suppress: false };
  const DEFAULT_READING_CONFIG = {
    // Modo por camadas é padrão estrutural do produto.
    enabled: true,
    strategy: "auto",
    aliases: {
      setor: "SETOR",
      bloco: "BLOCO, TORRE, BL",
      pavimento: "PAVIMENTO, PAV, ANDAR, NIVEL",
      unidade: "UNIDADE, APTO, LOCAL, AMBIENTE",
    },
  };
  const urlParams = new URLSearchParams(window.location.search || "");
  const isEmbedMode = parseModeFlag(urlParams.get("embed"), false);
  function parseModeFlag(value, fallback) {
    const raw = String(value == null ? "" : value).trim().toLowerCase();
    if (!raw) return !!fallback;
    if (["1", "true", "on", "yes", "sim"].includes(raw)) return true;
    if (["0", "false", "off", "no", "nao", "não"].includes(raw)) return false;
    return !!fallback;
  }
  const initialEditMode = parseModeFlag(urlParams.get("edit"), true);
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
    editMode: initialEditMode,
    semanticas: [],
    renderQueued: false,
    dirty: false,
    autoSaveTimer: null,
    contextMenuAnchor: { x: 0, y: 0 },
    lastAppearanceAnchor: { x: 0, y: 0 },
    viewMode: "draft",
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
    /** Estado de navegação por camada da matriz (somente sessão/UI; não persiste no layout). */
    matrixLayerNavByElKey: {},
    /** Filtro global de contexto (setor/bloco/pavimento/unidade) para leitura operacional. */
    layerFilter: { setor: "", bloco: "", pavimento: "", unidade: "", onlyMatches: true },
    layerCatalog: { setor: [], bloco: [], pavimento: [], unidade: [] },
    layerMissingSelected: [],
    matrixExcelPreview: null,
    readingConfig: JSON.parse(JSON.stringify(DEFAULT_READING_CONFIG)),
    /** Controle de visibilidade dos botões flutuantes da prancheta. */
    quickFabHoverSelected: false,
    quickFabHoverFab: false,
    lastRenderAt: 0,
    renderThrottleTimer: null,
    viewportRelayoutTimer: null,
  };

  let matrixInlineEl = null;
  let matrixInlineBlurTimer = null;
  let matrixLinkHintEl = null;
  let mxGridDragMove = null;
  let mxGridDragUp = null;
  let mxReorderMove = null;
  let mxReorderUp = null;

  function syncEditModeUi() {
    if (btnToggleEdit) {
      btnToggleEdit.innerHTML = `<i class="bi bi-pencil-square"></i> Modo edição: ${state.editMode ? "ON" : "OFF"}`;
      btnToggleEdit.setAttribute("aria-pressed", String(state.editMode));
      btnToggleEdit.setAttribute("title", state.editMode ? "Modo edição ativo" : "Modo edição inativo");
    }
  }

  function setEditMode(nextMode, options) {
    if (state.viewMode !== "draft") return;
    const cfg = options && typeof options === "object" ? options : {};
    const next = !!nextMode;
    const changed = state.editMode !== next;
    state.editMode = next;
    syncEditModeUi();
    if (!state.editMode) setTransformerNodes([]);
    if (!changed && !cfg.forceRender) return;
    updateMatrixViewportSizingForReading();
    renderKonva();
    if (isEmbedMode && window.parent && window.parent !== window) {
      window.parent.postMessage(
        {
          type: "po:editModeChanged",
          payload: { editMode: state.editMode },
        },
        window.location.origin
      );
    }
  }

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

  function boardViewportSize() {
    if (canvasViewport) {
      return {
        w: Math.max(120, Number(canvasViewport.clientWidth) || 0),
        h: Math.max(120, Number(canvasViewport.clientHeight) || 0),
      };
    }
    if (stageState.stage) {
      return { w: Math.max(120, stageState.stage.width()), h: Math.max(120, stageState.stage.height()) };
    }
    return { w: 1200, h: 720 };
  }

  function dynamicZoomMin() {
    const stage = stageState.stage;
    if (!stage) return ZOOM_MIN;
    const visible = getVisibleElements();
    if (!visible.length) return ZOOM_MIN;
    const minX = Math.min(...visible.map((e) => e.x));
    const minY = Math.min(...visible.map((e) => e.y));
    const maxX = Math.max(...visible.map((e) => e.x + e.width));
    const maxY = Math.max(...visible.map((e) => e.y + e.height));
    const boxW = Math.max(100, maxX - minX + 40);
    const boxH = Math.max(100, maxY - minY + 40);
    const vp = boardViewportSize();
    const fit = Math.min(vp.w / boxW, vp.h / boxH);
    return clamp(Math.min(ZOOM_MIN, fit * 0.9), 0.12, ZOOM_MIN);
  }

  function clampStageToViewportBounds() {
    const stage = stageState.stage;
    if (!stage) return;
    const vp = boardViewportSize();
    const sx = Math.max(0.05, stage.scaleX() || 1);
    const sy = Math.max(0.05, stage.scaleY() || sx);
    const boardW = BOARD_WIDTH * sx;
    const boardH = BOARD_HEIGHT * sy;
    const minX = Math.min(0, vp.w - boardW);
    const minY = Math.min(0, vp.h - boardH);
    const maxX = 0;
    const maxY = 0;
    stage.position({
      x: clamp(stage.x(), minX, maxX),
      y: clamp(stage.y(), minY, maxY),
    });
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

  function applyMatrixMutationAndRefresh(el, opts) {
    const selected = getSelected();
    ensureMatrixData(el);
    updatePreview();
    markDirty();
    if (selected && selected.key === el.key) renderMatrixInspector(selected);
    scheduleRender();
    if (opts && opts.message) showAlert(opts.message, opts.type || "success");
  }

  function insertMatrixRowAt(el, insertAt) {
    if (!el || !isMatrixKind(el.kind)) return false;
    ensureMatrixData(el);
    const rowLen = Math.max(1, ...el.data.rows.map((r) => (Array.isArray(r) ? r.length : 0)));
    const at = clamp(Math.round(Number(insertAt) || 0), 0, el.data.rows.length);
    pushHistory();
    el.data.rows.splice(at, 0, Array.from({ length: rowLen }, () => ""));
    const tR = getTotalsRowAuto(el.data);
    if (Array.isArray(el.data.rowWeights)) {
      const idxW = tR ? Math.min(at, Math.max(0, el.data.rowWeights.length - 1)) : at;
      const leftW = idxW - 1 >= 0 ? Number(el.data.rowWeights[idxW - 1]) || 1 : 1;
      const rightW = idxW < el.data.rowWeights.length ? Number(el.data.rowWeights[idxW]) || leftW : leftW;
      el.data.rowWeights.splice(idxW, 0, Math.max(MIN_MATRIX_WEIGHT, (leftW + rightW) / 2));
    }
    applyMatrixMutationAndRefresh(el);
    return true;
  }

  function insertMatrixColAt(el, insertIdx) {
    if (!el || !isMatrixKind(el.kind)) return false;
    ensureMatrixData(el);
    const h = getHeaderBandCount(el.data);
    const tCol = getTotalsColumnAuto(el.data);
    const colCount0 = Math.max(1, ...el.data.rows.map((r) => (Array.isArray(r) ? r.length : 0)));
    let at = clamp(Math.round(Number(insertIdx) || 1), 1, colCount0);
    if (tCol) at = Math.min(at, colCount0 - 1);
    const numData = colCount0 - 1 - (tCol ? 1 : 0);
    const cellLabel = `Atividade ${Math.max(1, numData + 1)}`;
    pushHistory();
    el.data.rows.forEach((row, idx) => {
      if (!Array.isArray(row)) return;
      while (row.length < colCount0) row.push("");
      let cell = "";
      if (idx < h - 1) cell = "";
      else if (idx === h - 1) cell = cellLabel;
      row.splice(at, 0, cell);
    });
    if (Array.isArray(el.data.colWeights) && el.data.colWeights.length === colCount0) {
      const leftW = at - 1 >= 0 ? Number(el.data.colWeights[at - 1]) || 1 : Number(el.data.colWeights[0]) || 1;
      const rightW = at < el.data.colWeights.length ? Number(el.data.colWeights[at]) || leftW : leftW;
      el.data.colWeights.splice(at, 0, Math.max(MIN_MATRIX_WEIGHT, (leftW + rightW) / 2));
    }
    ensureMatrixNoRightCut(el);
    applyMatrixMutationAndRefresh(el);
    return true;
  }

  function removeMatrixRowAt(el, rowIdx) {
    if (!el || !isMatrixKind(el.kind)) return false;
    ensureMatrixData(el);
    const h = getHeaderBandCount(el.data);
    const tR = getTotalsRowAuto(el.data);
    const maxBody = tR ? el.data.rows.length - 2 : el.data.rows.length - 1;
    if (rowIdx < h || rowIdx > maxBody) return false;
    if (el.data.rows.length <= h + 1) return false;
    pushHistory();
    el.data.rows.splice(rowIdx, 1);
    if (Array.isArray(el.data.rowWeights) && el.data.rowWeights.length > 0) {
      const idxW = tR ? Math.min(rowIdx, el.data.rowWeights.length - 2) : rowIdx;
      if (idxW >= 0 && idxW < el.data.rowWeights.length) el.data.rowWeights.splice(idxW, 1);
    }
    applyMatrixMutationAndRefresh(el);
    return true;
  }

  function removeMatrixColAt(el, colIdx) {
    if (!el || !isMatrixKind(el.kind)) return false;
    ensureMatrixData(el);
    const tCol = getTotalsColumnAuto(el.data);
    const colCount = Math.max(1, ...el.data.rows.map((r) => (Array.isArray(r) ? r.length : 0)));
    const minCols = tCol ? 3 : 2;
    if (colIdx <= 0) return false;
    if (tCol && colIdx === colCount - 1) return false;
    if (colCount <= minCols) return false;
    pushHistory();
    el.data.rows.forEach((row) => {
      if (Array.isArray(row) && row.length > colIdx) row.splice(colIdx, 1);
    });
    if (Array.isArray(el.data.colWeights) && el.data.colWeights.length > colIdx) {
      el.data.colWeights.splice(colIdx, 1);
    }
    applyMatrixMutationAndRefresh(el);
    return true;
  }

  function moveMatrixRowByStep(el, rowIdx, step) {
    if (!el || !isMatrixKind(el.kind) || !step) return false;
    ensureMatrixData(el);
    const { minR, maxR } = matrixDraggableRowBounds(el);
    if (rowIdx < minR || rowIdx > maxR) return false;
    const to = clamp(rowIdx + step, minR, maxR);
    if (to === rowIdx) return false;
    pushHistory();
    moveArrayItemToFinalIndex(el.data.rows, rowIdx, to);
    if (Array.isArray(el.data.rowWeights) && el.data.rowWeights.length > Math.max(rowIdx, to)) {
      moveArrayItemToFinalIndex(el.data.rowWeights, rowIdx, to);
    }
    applyMatrixMutationAndRefresh(el);
    return true;
  }

  function moveMatrixColByStep(el, colIdx, step) {
    if (!el || !isMatrixKind(el.kind) || !step) return false;
    ensureMatrixData(el);
    const { minC, maxC } = matrixDraggableColBounds(el);
    if (colIdx < minC || colIdx > maxC) return false;
    const to = clamp(colIdx + step, minC, maxC);
    if (to === colIdx) return false;
    pushHistory();
    el.data.rows.forEach((row) => {
      if (Array.isArray(row)) moveArrayItemToFinalIndex(row, colIdx, to);
    });
    if (Array.isArray(el.data.colWeights) && el.data.colWeights.length > Math.max(colIdx, to)) {
      moveArrayItemToFinalIndex(el.data.colWeights, colIdx, to);
    }
    ensureMatrixNoRightCut(el);
    applyMatrixMutationAndRefresh(el);
    return true;
  }

  function openMatrixCellContextMenu(clientX, clientY, elKey, group, cell) {
    closeCardContextMenu();
    const el = state.elementos.find((it) => it.key === elKey);
    if (!el || !isMatrixKind(el.kind)) return;
    const m = computeMatrixGridMetrics(el);
    const isFoot = m.tRow && cell.r === m.rows.length;
    const isHeader = !isFoot && cell.r < m.hBand;
    const canEditCell = !cell.readOnly;
    const canRemoveRow = cell.r >= m.hBand && !isFoot && m.rows.length > m.hBand + 1;
    const canMoveRow = canRemoveRow;
    const canRemoveCol =
      cell.c > 0 &&
      !(m.tCol && cell.c === m.colCount - 1) &&
      m.colCount > (m.tCol ? 3 : 2);
    const canMoveCol =
      cell.c > 0 &&
      !(m.tCol && cell.c === m.colCount - 1);

    let menu = document.getElementById("po-card-context-menu");
    if (!menu) {
      menu = document.createElement("div");
      menu.id = "po-card-context-menu";
      menu.className = "po-card-context-menu";
      menu.setAttribute("role", "menu");
      document.body.appendChild(menu);
    }

    const rows = [
      '<div class="po-card-context-hint small text-muted px-2 py-2 border-bottom">Edição rápida da matriz</div>',
      `<button type="button" class="po-card-context-item${canEditCell ? "" : " disabled"}" data-action="mx-edit"${canEditCell ? "" : " disabled"}><i class="bi bi-pencil-square"></i> Editar célula</button>`,
      '<button type="button" class="po-card-context-item" data-action="mx-color"><i class="bi bi-palette"></i> Ajustar cores da matriz</button>',
      '<div class="border-top my-1"></div>',
      '<button type="button" class="po-card-context-item" data-action="mx-add-row"><i class="bi bi-plus-square"></i> Inserir linha abaixo</button>',
      `<button type="button" class="po-card-context-item${canRemoveRow ? "" : " disabled"}" data-action="mx-del-row"${canRemoveRow ? "" : " disabled"}><i class="bi bi-dash-square"></i> Remover linha</button>`,
      `<button type="button" class="po-card-context-item${canMoveRow ? "" : " disabled"}" data-action="mx-row-up"${canMoveRow ? "" : " disabled"}><i class="bi bi-arrow-up"></i> Mover linha para cima</button>`,
      `<button type="button" class="po-card-context-item${canMoveRow ? "" : " disabled"}" data-action="mx-row-down"${canMoveRow ? "" : " disabled"}><i class="bi bi-arrow-down"></i> Mover linha para baixo</button>`,
      '<div class="border-top my-1"></div>',
      '<button type="button" class="po-card-context-item" data-action="mx-add-col"><i class="bi bi-plus-square"></i> Inserir coluna à direita</button>',
      `<button type="button" class="po-card-context-item${canRemoveCol ? "" : " disabled"}" data-action="mx-del-col"${canRemoveCol ? "" : " disabled"}><i class="bi bi-dash-square"></i> Remover coluna</button>`,
      `<button type="button" class="po-card-context-item${canMoveCol ? "" : " disabled"}" data-action="mx-col-left"${canMoveCol ? "" : " disabled"}><i class="bi bi-arrow-left"></i> Mover coluna para esquerda</button>`,
      `<button type="button" class="po-card-context-item${canMoveCol ? "" : " disabled"}" data-action="mx-col-right"${canMoveCol ? "" : " disabled"}><i class="bi bi-arrow-right"></i> Mover coluna para direita</button>`,
    ];
    menu.innerHTML = rows.join("");
    menu.style.left = `${clientX}px`;
    menu.style.top = `${clientY}px`;
    menu.classList.add("is-open");

    menu.addEventListener(
      "click",
      (ev) => {
        const btn = ev.target.closest("[data-action]");
        if (!btn || !menu.contains(btn) || btn.hasAttribute("disabled")) return;
        ev.preventDefault();
        ev.stopPropagation();
        const action = btn.getAttribute("data-action");
        closeCardContextMenu();
        state.selectedId = el.key;
        updateInspector();
        if (action === "mx-edit") {
          openMatrixCellInlineEditor(group, el, cell);
        } else if (action === "mx-color") {
          openAppearancePopover(clientX, clientY, el.key);
        } else if (action === "mx-add-row") {
          const insertAt = isHeader ? m.hBand : Math.min(cell.r + 1, m.rows.length);
          insertMatrixRowAt(el, insertAt);
        } else if (action === "mx-del-row") {
          if (!removeMatrixRowAt(el, cell.r)) showAlert("Não foi possível remover esta linha.", "warning");
        } else if (action === "mx-row-up") {
          if (!moveMatrixRowByStep(el, cell.r, -1)) showAlert("Não foi possível mover a linha para cima.", "warning");
        } else if (action === "mx-row-down") {
          if (!moveMatrixRowByStep(el, cell.r, 1)) showAlert("Não foi possível mover a linha para baixo.", "warning");
        } else if (action === "mx-add-col") {
          const insertAt = Math.min(cell.c + 1, m.tCol ? m.colCount - 1 : m.colCount);
          insertMatrixColAt(el, insertAt);
        } else if (action === "mx-del-col") {
          if (!removeMatrixColAt(el, cell.c)) showAlert("Não foi possível remover esta coluna.", "warning");
        } else if (action === "mx-col-left") {
          if (!moveMatrixColByStep(el, cell.c, -1)) showAlert("Não foi possível mover a coluna para esquerda.", "warning");
        } else if (action === "mx-col-right") {
          if (!moveMatrixColByStep(el, cell.c, 1)) showAlert("Não foi possível mover a coluna para direita.", "warning");
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
      if (ev.type === "keydown" && ev.key !== "Escape") return;
      if (panelEl && panelEl.contains(ev.target)) return;
      if (menu.contains(ev.target)) return;
      closeCardContextMenu();
    };
    setTimeout(() => {
      document.addEventListener("click", cardContextMenuDismiss, true);
      document.addEventListener("contextmenu", cardContextMenuDismiss, true);
      document.addEventListener("keydown", cardContextMenuDismiss, true);
    }, 0);
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
    const rows = [];
    const headerRow = ["Bloco / local"];
    for (let i = 0; i < dataCols; i += 1) {
      headerRow.push(`Atividade ${i + 1}`);
    }
    headerRow.push("Total");
    rows.push(headerRow);
    for (let r = 0; r < dataRows; r += 1) {
      const row = [r < 2 ? `Bloco ${String.fromCharCode(65 + r)}` : `Eixo ${r - 1}`];
      for (let c = 0; c < dataCols; c += 1) row.push("");
      row.push("");
      rows.push(row);
    }
    return rows;
  }

  function matrixMapaPresetWeights(rows, totalsRowAuto = true) {
    const colCount = Math.max(1, ...rows.map((r) => (Array.isArray(r) ? r.length : 0)));
    const visRowCount = rows.length + (totalsRowAuto ? 1 : 0);
    const colWeights = [0.7];
    for (let c = 1; c < colCount - 1; c += 1) colWeights.push(1);
    if (colCount > 1) colWeights.push(0.9);
    const rowWeights = [2.2];
    for (let r = 1; r < visRowCount - 1; r += 1) rowWeights.push(1);
    if (visRowCount > 1) rowWeights.push(1.1);
    return { colWeights, rowWeights };
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
    const denseRatio = colCount >= 18 ? 0.1 : colCount >= 12 ? 0.14 : 0.22;
    const firstColW =
      colCount > 1
        ? clamp(ic * denseRatio, 28, Math.min(ic * 0.34, ic - (colCount - 1) * 14))
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

  function normalizeWeightsForCount(weights, count) {
    const n = Math.max(1, Number(count) || 1);
    const src = Array.isArray(weights) ? weights : [];
    const out = [];
    for (let i = 0; i < n; i += 1) {
      const v = Number(src[i]);
      out.push(Math.max(MIN_MATRIX_WEIGHT, Number.isFinite(v) ? v : 1));
    }
    return out;
  }

  function ensureMatrixData(el) {
    if (!isMatrixKind(el.kind)) return;
    if (!el.data) el.data = {};
    const d = el.data;
    if (!Array.isArray(d.rows) || !d.rows.length) {
      const isMapaControleTemplate = !!(d.mapaControleTemplate || d.mapa_controle_template);
      if (isMapaControleTemplate) {
        const rows = matrixMapaPresetRows();
        const weights = matrixMapaPresetWeights(rows, true);
        d.rows = rows;
        d.headerBandCount = 1;
        d.heatmap = true;
        d.totalsColumnAuto = true;
        d.totalsRowAuto = true;
        d.verticalHeaders = true;
        d.colWeights = weights.colWeights;
        d.rowWeights = weights.rowWeights;
      } else {
        d.rows = defaultMatrixRowsTemplate();
        d.headerBandCount = 2;
        d.heatmap = true;
      }
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
    ensureMatrixLinksData(d);
  }

  function ensureMatrixLinksData(d) {
    if (!d || typeof d !== "object") return;
    if (!d.matrixLinks || typeof d.matrixLinks !== "object") d.matrixLinks = {};
    const ml = d.matrixLinks;
    if (!Array.isArray(ml.groups)) ml.groups = [];
    if (!Array.isArray(ml.bindings)) ml.bindings = [];
    // `nav` era persistido em versões anteriores; agora é apenas estado de sessão.
    if (Object.prototype.hasOwnProperty.call(ml, "nav")) delete ml.nav;
    ml.groups = ml.groups
      .map((g, idx) => {
        if (!g || typeof g !== "object") return null;
        const id = String(g.id || `g${idx + 1}`).trim() || `g${idx + 1}`;
        const name = String(g.name || "").trim();
        const layerKey = String(g.layerKey || "").trim();
        return { id, name: name || id, layerKey };
      })
      .filter(Boolean);
    ml.bindings = ml.bindings
      .map((b, idx) => {
        if (!b || typeof b !== "object") return null;
        const id = String(b.id || `b${idx + 1}`).trim() || `b${idx + 1}`;
        const groupId = String(b.groupId || "").trim();
        const sourceLayer = String(b.sourceLayer || "root").trim() || "root";
        const rowStart = Math.max(0, Number(b.rowStart) || 0);
        const rowEnd = Math.max(rowStart, Number(b.rowEnd) || rowStart);
        const colStart = Math.max(0, Number(b.colStart) || 0);
        const colEnd = Math.max(colStart, Number(b.colEnd) || colStart);
        return { id, groupId, sourceLayer, rowStart, rowEnd, colStart, colEnd };
      })
      .filter((b) => b && ml.groups.some((g) => g.id === b.groupId));
  }

  function matrixActiveLayerKey(el) {
    ensureMatrixData(el);
    const nav = matrixLayerNavState(el);
    return String(nav.activeLayer || "root");
  }

  function matrixBindingsForActiveLayer(el) {
    ensureMatrixData(el);
    const ml = el.data.matrixLinks;
    const active = matrixActiveLayerKey(el);
    return (ml.bindings || []).filter((b) => String(b.sourceLayer || "root") === active);
  }

  function matrixLayerNavState(el) {
    const k = el && el.key ? String(el.key) : "";
    if (!k) return { activeLayer: "root", stack: ["root"] };
    if (!state.matrixLayerNavByElKey || typeof state.matrixLayerNavByElKey !== "object") {
      state.matrixLayerNavByElKey = {};
    }
    let nav = state.matrixLayerNavByElKey[k];
    if (!nav || typeof nav !== "object") {
      const src = el && el.data && el.data.matrixLinks && el.data.matrixLinks.nav && typeof el.data.matrixLinks.nav === "object"
        ? el.data.matrixLinks.nav
        : null;
      const active = String((src && src.activeLayer) || "root").trim() || "root";
      const stackSrc = src && Array.isArray(src.stack) ? src.stack : [];
      let stack = stackSrc.map((x) => String(x || "").trim()).filter(Boolean);
      if (!stack.length) stack = [active];
      if (stack[stack.length - 1] !== active) stack.push(active);
      nav = { activeLayer: active, stack };
      state.matrixLayerNavByElKey[k] = nav;
    }
    return nav;
  }

  function matrixDataBounds(el) {
    ensureMatrixData(el);
    const rows = el.data.rows || [];
    const h = getHeaderBandCount(el.data);
    const tCol = getTotalsColumnAuto(el.data);
    const colCount = Math.max(1, ...rows.map((r) => (Array.isArray(r) ? r.length : 0)));
    const dataRows = Math.max(0, rows.length - h);
    const dataCols = Math.max(1, colCount - 1 - (tCol ? 1 : 0));
    return { hBand: h, dataRows, dataCols };
  }

  function matrixNextId(arr, prefix) {
    const used = new Set((arr || []).map((x) => String(x && x.id ? x.id : "")));
    for (let i = 1; i <= 9999; i += 1) {
      const id = `${prefix}${i}`;
      if (!used.has(id)) return id;
    }
    return `${prefix}${Date.now()}`;
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

  function isLegacyMatrixVisual(el) {
    return !!(isEmbedMode && !state.editMode && el && isMatrixKind(el.kind));
  }

  /** Matriz ou tabela de lista — único bloco desse tipo em tela cheia pode usar todo o viewport. */
  function isTableBlockKind(kind) {
    return isMatrixKind(kind) || kind === "list_table";
  }

  function shouldFitSingleTableToViewport() {
    const visible = getVisibleElements();
    if (visible.length !== 1) return false;
    const only = visible[0];
    if (!isTableBlockKind(only.kind)) return false;
    if (isMatrixKind(only.kind)) {
      const rows = (only.data && Array.isArray(only.data.rows) ? only.data.rows : []);
      const colCount = Math.max(1, ...rows.map((r) => (Array.isArray(r) ? r.length : 0)));
      const rowCount = rows.length;
      // Matrizes muito densas não devem "encaixar tudo" em fullscreen, senão ficam ilegíveis.
      if (colCount >= 28 || rowCount >= 120) return false;
    }
    return (
      isCanvasFullscreen() &&
      visible.length === 1 &&
      isTableBlockKind(visible[0].kind)
    );
  }

  function getMatrixBodyBox(el) {
    if (isLegacyMatrixVisual(el)) {
      return {
        bodyX: 0,
        bodyY: 0,
        bodyW: Math.max(40, el.width),
        bodyH: Math.max(24, el.height),
      };
    }
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
    const hBand = getHeaderBandCount(d);
    const sourceRows = d.rows || [[""]];
    const sourceColCount = Math.max(1, ...sourceRows.map((r) => (Array.isArray(r) ? r.length : 0)));
    const rows = matrixRowsForContext(el, sourceRows, hBand, sourceColCount);
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
    const layerMode = isLayerReadingMode();
    // Em matrizes densas (ex.: 20+ colunas), priorizar encaixe total no cartão.
    const denseColsMode = colCount >= 18;
    const veryDenseColsMode = colCount >= 40;
    const colWeightsNow = normalizeWeightsForCount(d.colWeights, colCount);
    const rowWeightsNow = normalizeWeightsForCount(d.rowWeights, visRowCount);
    const readCfg = mergeReadingConfig(state.readingConfig);
    if (readCfg.enabled !== false && colWeightsNow.length > 1) {
      // Coluna de contexto (Bloco/Pavimento/Unidade) mais enxuta no modo camadas.
      colWeightsNow[0] = Math.max(MIN_MATRIX_WEIGHT, colWeightsNow[0] * 0.28);
    }
    const cwPix = sizesFromWeights(colAvail, colWeightsNow, {
      // Em matriz muito larga, permitir overflow horizontal e preservar leitura.
      allowOverflow: layerMode ? false : (veryDenseColsMode ? true : !denseColsMode),
      minReadablePx: layerMode ? 6 : (veryDenseColsMode ? 16 : denseColsMode ? 9 : MATRIX_MIN_COL_PX),
    });
    const rhPix = sizesFromWeights(rowAvail, rowWeightsNow, {
      allowOverflow: true,
      minReadablePx: layerMode ? 10 : MATRIX_MIN_ROW_PX,
    });
    const verticalHeadersOn = getVerticalHeaders(d) || isLayerReadingMode();
    if (verticalHeadersOn && hBand >= 1 && rhPix.length >= hBand) {
      const headIdx = hBand - 1;
      rhPix[headIdx] = Math.max(rhPix[headIdx], MATRIX_VERT_HEADER_MIN_RH);
    }
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

  function normalizeLayerHeaderToken(value) {
    return String(value || "")
      .normalize("NFD")
      .replace(/[\u0300-\u036f]/g, "")
      .toUpperCase()
      .trim();
  }

  function normalizeAliasesCsv(value) {
    return String(value || "")
      .split(",")
      .map((s) => normalizeLayerHeaderToken(s))
      .filter(Boolean)
      .filter((v, i, arr) => arr.indexOf(v) === i);
  }

  function mergeReadingConfig(raw) {
    const base = JSON.parse(JSON.stringify(DEFAULT_READING_CONFIG));
    const src = raw && typeof raw === "object" ? raw : {};
    const strategyRaw = String(src.strategy || base.strategy).trim().toLowerCase();
    const strategy = ["auto", "bloco", "pavimento", "unidade"].includes(strategyRaw)
      ? strategyRaw
      : "auto";
    const aliases = src.aliases && typeof src.aliases === "object" ? src.aliases : {};
    return {
      // Refatoração: leitura por camadas passa a ser obrigatória (sem estado "desligado").
      enabled: true,
      strategy,
      aliases: {
        setor: String(aliases.setor || base.aliases.setor),
        bloco: String(aliases.bloco || base.aliases.bloco),
        pavimento: String(aliases.pavimento || base.aliases.pavimento),
        unidade: String(aliases.unidade || base.aliases.unidade),
      },
    };
  }

  function headerAliasesByField() {
    const cfg = mergeReadingConfig(state.readingConfig);
    return {
      setor: normalizeAliasesCsv(cfg.aliases.setor || DEFAULT_READING_CONFIG.aliases.setor),
      bloco: normalizeAliasesCsv(cfg.aliases.bloco || DEFAULT_READING_CONFIG.aliases.bloco),
      pavimento: normalizeAliasesCsv(cfg.aliases.pavimento || DEFAULT_READING_CONFIG.aliases.pavimento),
      unidade: normalizeAliasesCsv(cfg.aliases.unidade || DEFAULT_READING_CONFIG.aliases.unidade),
    };
  }

  function isLayerReadingMode() {
    const cfg = mergeReadingConfig(state.readingConfig);
    return cfg.enabled !== false;
  }

  function matrixLayerFieldFromHeaderLabel(label) {
    const token = normalizeLayerHeaderToken(label);
    if (!token) return "";
    const byField = headerAliasesByField();
    const fields = ["setor", "bloco", "pavimento", "unidade"];
    for (let i = 0; i < fields.length; i += 1) {
      const field = fields[i];
      const aliases = byField[field] || [];
      const matched = aliases.some((alias) => {
        if (!alias) return false;
        if (token === alias || token.startsWith(`${alias} `)) return true;
        // Heurística tolerante para cabeçalhos abreviados/truncados (ex.: PAVIME, TORR, UNID).
        if (token.length >= 4 && alias.startsWith(token)) return true;
        if (alias.length >= 4 && token.startsWith(alias.slice(0, 4))) return true;
        return false;
      });
      if (matched) return field;
    }
    // Fallback semântico para formatos não padronizados.
    if (token.startsWith("SET")) return "setor";
    if (token.startsWith("BLOC") || token.startsWith("TORR") || token === "BL") return "bloco";
    if (token.startsWith("PAV") || token.startsWith("AND") || token.startsWith("NIV")) return "pavimento";
    if (token.startsWith("APT") || token.startsWith("UNID") || token.startsWith("AMB")) return "unidade";
    return "";
  }

  function matrixResolveTargetField(cfg, filter, hasIdx) {
    if (!hasIdx("bloco")) return "";
    if (cfg.strategy === "bloco") return "bloco";
    if (cfg.strategy === "pavimento") return hasIdx("pavimento") ? "pavimento" : "bloco";
    if (cfg.strategy === "unidade") {
      if (hasIdx("unidade")) return "unidade";
      if (hasIdx("pavimento")) return "pavimento";
      return "bloco";
    }
    // Auto: navegação progressiva por camadas (igual mapa de controle).
    if (!filter.bloco) return "bloco";
    if (hasIdx("pavimento") && !filter.pavimento) return "pavimento";
    if (hasIdx("unidade")) return "unidade";
    return hasIdx("pavimento") ? "pavimento" : "bloco";
  }

  function matrixHasStructuredLayerColumns(m) {
    if (!m || !Array.isArray(m.rows) || m.hBand < 1) return false;
    const head = Array.isArray(m.rows[m.hBand - 1]) ? m.rows[m.hBand - 1] : [];
    const fields = new Set();
    for (let c = 0; c < Math.min(m.colCount, 8); c += 1) {
      const f = matrixLayerFieldFromHeaderLabel(head[c]);
      if (f) fields.add(f);
    }
    return fields.size >= 2;
  }

  function matrixLayerFieldByColumn(el, m, c) {
    if (!m || !Array.isArray(m.rows) || m.hBand < 1 || c < 0 || c >= m.colCount) return "";
    const head = Array.isArray(m.rows[m.hBand - 1]) ? m.rows[m.hBand - 1] : [];
    return matrixLayerFieldFromHeaderLabel(head[c]);
  }

  function matrixLayerColumnIndexMap(rows, hBand, colCount) {
    if (!Array.isArray(rows) || !rows.length || hBand < 1) return {};
    const head = Array.isArray(rows[hBand - 1]) ? rows[hBand - 1] : [];
    const out = {};
    for (let c = 0; c < colCount; c += 1) {
      const field = matrixLayerFieldFromHeaderLabel(head[c]);
      if (!field || Number.isInteger(out[field])) continue;
      out[field] = c;
    }
    return out;
  }

  /**
   * Modo principal por camadas (drilldown): muda a "tela" da matriz conforme o contexto.
   * Fluxo: bloco -> pavimento -> unidade, semelhante ao mapa de controle.
   */
  function matrixRowsForContext(el, sourceRows, hBand, colCount) {
    if (!Array.isArray(sourceRows) || !sourceRows.length) return sourceRows;
    if (state.viewMode !== "draft") return sourceRows;
    const cfg = mergeReadingConfig(state.readingConfig);
    if (!cfg.enabled) return sourceRows;
    const probe = { rows: sourceRows, hBand, colCount };
    if (!matrixHasStructuredLayerColumns(probe)) return sourceRows;
    const idx = matrixLayerColumnIndexMap(sourceRows, hBand, colCount);
    const f = state.layerFilter || {};
    const fields = ["setor", "bloco", "pavimento", "unidade"];
    const hasIdx = (field) => Number.isInteger(idx[field]);
    if (!hasIdx("bloco")) return sourceRows;
    const targetField = matrixResolveTargetField(cfg, f, hasIdx);
    if (!targetField) return sourceRows;
    const headerRow = Array.isArray(sourceRows[hBand - 1]) ? sourceRows[hBand - 1] : [];
    const activityCols = [];
    for (let c = 0; c < colCount; c += 1) {
      if (fields.some((k) => idx[k] === c)) continue;
      const label = String(headerRow[c] || "").trim();
      if (!label) continue;
      if (normalizeLayerHeaderToken(label) === "TOTAL") continue;
      activityCols.push(c);
    }
    if (!activityCols.length) return sourceRows;
    const body = sourceRows.slice(hBand);
    const activeContextFilters = fields
      .filter((field) => field !== targetField && f[field] && hasIdx(field));
    const scoped = body.filter((row) =>
      activeContextFilters.every((field) =>
        valuesEqualLoose((Array.isArray(row) ? row[idx[field]] : ""), f[field])
      )
    );
    const groups = new Map();
    scoped.forEach((row) => {
      if (!Array.isArray(row)) return;
      const rawKey = String(row[idx[targetField]] || "").trim();
      const key = rawKey || `Sem ${targetField}`;
      if (!groups.has(key)) {
        groups.set(key, { key, values: activityCols.map(() => []) });
      }
      const g = groups.get(key);
      activityCols.forEach((c, j) => {
        const cell = row[c];
        const num = parsePercentCell(cell);
        if (num !== null) g.values[j].push(num);
      });
    });
    const targetLabel =
      targetField === "bloco"
        ? "Bloco"
        : targetField === "pavimento"
          ? "Pavimento"
          : "Unidade";
    const resultHeader = [targetLabel, ...activityCols.map((c) => String(headerRow[c] || "").trim())];
    const groupsList = Array.from(groups.values()).sort((a, b) => layerValueSort(a.key, b.key));
    if (!groupsList.length) return [resultHeader];
    const activeValueMask = activityCols.map((_, j) => groupsList.some((g) => (g.values[j] || []).length > 0));
    const compactActivityIdx = [];
    for (let j = 0; j < activityCols.length; j += 1) {
      if (activeValueMask[j]) compactActivityIdx.push(j);
    }
    if (!compactActivityIdx.length) return [[targetLabel]];
    const compactHeader = [targetLabel, ...compactActivityIdx.map((j) => String(headerRow[activityCols[j]] || "").trim())];
    const groupedRows = groupsList
      .map((g) => {
        const vals = compactActivityIdx.map((j) => {
          const arr = g.values[j] || [];
          if (!arr.length) return "";
          const avg = arr.reduce((s, n) => s + n, 0) / arr.length;
          if (!Number.isFinite(avg)) return "";
          return `${Math.round(avg)}%`;
        });
        const hasAny = vals.some((v) => String(v || "").trim());
        if (!hasAny) return null;
        return [g.key, ...vals];
      })
      .filter(Boolean);
    if (!groupedRows.length) return [compactHeader];
    return [compactHeader, ...groupedRows];
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

  function normalizeLayerValue(v) {
    return String(v || "").trim().toLowerCase();
  }

  function valuesEqualLoose(a, b) {
    const na = normalizeLayerValue(a);
    const nb = normalizeLayerValue(b);
    if (!na || !nb) return na === nb;
    if (na === nb) return true;
    return na.replace(/^bloco\s+/, "") === nb.replace(/^bloco\s+/, "");
  }

  function layerValueSort(a, b) {
    return String(a || "").localeCompare(String(b || ""), "pt-BR", { numeric: true, sensitivity: "base" });
  }

  function collectLayerCatalog() {
    const catalog = { setor: new Set(), bloco: new Set(), pavimento: new Set(), unidade: new Set() };
    state.elementos.forEach((el) => {
      const layer = el.layer || {};
      if (layer.setor) catalog.setor.add(String(layer.setor).trim());
      if (layer.bloco) catalog.bloco.add(String(layer.bloco).trim());
      if (layer.pavimento) catalog.pavimento.add(String(layer.pavimento).trim());
      if (layer.unidade) catalog.unidade.add(String(layer.unidade).trim());
    });
    state.layerCatalog = {
      setor: Array.from(catalog.setor).sort(layerValueSort),
      bloco: Array.from(catalog.bloco).sort(layerValueSort),
      pavimento: Array.from(catalog.pavimento).sort(layerValueSort),
      unidade: Array.from(catalog.unidade).sort(layerValueSort),
    };
  }

  function layerContextStorageKey() {
    const ambienteId = ctx && ctx.ambienteId ? String(ctx.ambienteId) : "default";
    return `po_layer_context_${ambienteId}`;
  }

  function saveLayerContextToStorage() {
    try {
      const payload = {
        setor: state.layerFilter.setor || "",
        bloco: state.layerFilter.bloco || "",
        pavimento: state.layerFilter.pavimento || "",
        unidade: state.layerFilter.unidade || "",
        onlyMatches: state.layerFilter.onlyMatches !== false,
      };
      window.localStorage.setItem(layerContextStorageKey(), JSON.stringify(payload));
    } catch {
      // Sem storage disponível (modo restrito), ignorar silenciosamente.
    }
  }

  function loadLayerContextFromStorage() {
    try {
      const raw = window.localStorage.getItem(layerContextStorageKey());
      if (!raw) return null;
      const obj = JSON.parse(raw);
      if (!obj || typeof obj !== "object") return null;
      return {
        setor: String(obj.setor || "").trim(),
        bloco: String(obj.bloco || "").trim(),
        pavimento: String(obj.pavimento || "").trim(),
        unidade: String(obj.unidade || "").trim(),
        onlyMatches: obj.onlyMatches !== false,
      };
    } catch {
      return null;
    }
  }

  function syncReadingConfigUi() {
    const cfg = mergeReadingConfig(state.readingConfig);
    if (ctxMatrixReadEnabled) {
      ctxMatrixReadEnabled.checked = true;
      ctxMatrixReadEnabled.disabled = true;
      ctxMatrixReadEnabled.title = "Este modo é o padrão da ferramenta (sempre ativo).";
    }
    if (ctxMatrixReadStrategy) ctxMatrixReadStrategy.value = cfg.strategy || "auto";
    if (ctxAliasSetor) ctxAliasSetor.value = cfg.aliases.setor || "";
    if (ctxAliasBloco) ctxAliasBloco.value = cfg.aliases.bloco || "";
    if (ctxAliasPavimento) ctxAliasPavimento.value = cfg.aliases.pavimento || "";
    if (ctxAliasUnidade) ctxAliasUnidade.value = cfg.aliases.unidade || "";
    if (ctxOnlyMatches) {
      const strictLayerMode = cfg.enabled !== false;
      if (strictLayerMode) ctxOnlyMatches.checked = true;
      ctxOnlyMatches.disabled = strictLayerMode;
      ctxOnlyMatches.title = strictLayerMode
        ? "No modo principal por camadas, o recorte por contexto permanece sempre ativo."
        : "";
    }
  }

  function persistReadingConfigOnDraft() {
    state.draft = state.draft && typeof state.draft === "object" ? state.draft : {};
    state.draft.metadados = state.draft.metadados && typeof state.draft.metadados === "object" ? state.draft.metadados : {};
    state.draft.metadados.reading_config = mergeReadingConfig(state.readingConfig);
  }

  function setReadingConfig(partial, options) {
    const opts = options || {};
    state.readingConfig = mergeReadingConfig({ ...mergeReadingConfig(state.readingConfig), ...(partial || {}) });
    state.layerFilter = { ...(state.layerFilter || {}), onlyMatches: true };
    persistReadingConfigOnDraft();
    syncReadingConfigUi();
    if (opts.render !== false) {
      renderKonva();
      if (opts.refit) fitView();
    }
    if (opts.markDirty !== false) {
      updatePreview();
      markDirty();
    }
  }

  function applyReadingPreset(preset) {
    const p = String(preset || "").toLowerCase();
    const strategy = ["auto", "bloco", "pavimento", "unidade"].includes(p) ? p : "auto";
    setReadingConfig({ strategy, enabled: true }, { markDirty: true, render: true, refit: false });
    showAlert(`Leitura aplicada: ${strategy}.`, "success");
  }

  function availableLayerValues(field) {
    const values = new Set();
    const f = state.layerFilter || {};
    state.elementos.forEach((el) => {
      const l = el.layer || {};
      if (field !== "setor" && f.setor && !valuesEqualLoose(l.setor, f.setor)) return;
      if (field !== "bloco" && f.bloco && !valuesEqualLoose(l.bloco, f.bloco)) return;
      if (field !== "pavimento" && f.pavimento && !valuesEqualLoose(l.pavimento, f.pavimento)) return;
      if (field !== "unidade" && f.unidade && !valuesEqualLoose(l.unidade, f.unidade)) return;
      const v = String(l[field] || "").trim();
      if (v) values.add(v);
    });
    return Array.from(values).sort(layerValueSort);
  }

  function hasAnyValueMatch(field, value) {
    if (!value) return true;
    return state.elementos.some((el) => valuesEqualLoose((el.layer || {})[field], value));
  }

  function renderContextTrail() {
    if (!ctxTrail) return;
    ctxTrail.innerHTML = "";
    const f = state.layerFilter || {};
    const parts = [
      { k: "setor", v: f.setor },
      { k: "bloco", v: f.bloco },
      { k: "pavimento", v: f.pavimento },
      { k: "unidade", v: f.unidade },
    ].filter((p) => p.v);
    if (!parts.length) {
      const hint = document.createElement("span");
      hint.className = "small text-muted";
      hint.textContent = "Sem contexto ativo";
      ctxTrail.appendChild(hint);
      return;
    }
    parts.forEach((p) => {
      const chip = document.createElement("button");
      chip.type = "button";
      chip.className = "btn btn-outline-secondary btn-sm";
      chip.textContent = `${p.k}: ${p.v}`;
      chip.title = "Clique para limpar este nível";
      chip.dataset.ctxClearLevel = p.k;
      ctxTrail.appendChild(chip);
    });
  }

  function contextMatchedElements() {
    return state.elementos.filter((el) => matchesLayerFilter(el));
  }

  function updateContextKpis() {
    const total = state.elementos.length;
    const matched = contextMatchedElements();
    const matchedCount = matched.length;
    const coverage = total ? Math.round((matchedCount * 100) / total) : 0;
    const missing = matched.filter((el) => hasMissingLayerInfo(el)).length;
    if (ctxKpiCoverage) ctxKpiCoverage.textContent = `Cobertura: ${matchedCount}/${total} (${coverage}%)`;
    if (ctxKpiMissing) ctxKpiMissing.textContent = `Pendências: ${missing}`;
  }

  function renderDrilldownHints() {
    if (!ctxDrilldown) return;
    const f = state.layerFilter || {};
    ctxDrilldown.innerHTML = "";
    let nextField = "";
    if (f.setor && !f.bloco) nextField = "bloco";
    else if (f.bloco && !f.pavimento) nextField = "pavimento";
    else if (f.pavimento && !f.unidade) nextField = "unidade";
    if (!nextField) return;
    const values = availableLayerValues(nextField).slice(0, 8);
    if (!values.length) return;
    const hint = document.createElement("span");
    hint.className = "small text-muted";
    hint.textContent = `Próximo nível (${nextField}):`;
    ctxDrilldown.appendChild(hint);
    values.forEach((v) => {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "btn btn-outline-secondary btn-sm";
      btn.textContent = v;
      btn.dataset.drillField = nextField;
      btn.dataset.drillValue = v;
      ctxDrilldown.appendChild(btn);
    });
  }

  function hasMissingLayerInfo(el) {
    const l = el.layer || {};
    return !(String(l.setor || "").trim() && String(l.bloco || "").trim() && String(l.pavimento || "").trim() && String(l.unidade || "").trim());
  }

  function renderMissingLayerPanel() {
    if (!missingLayerSummary || !missingLayerList) return;
    const missing = state.elementos.filter((el) => hasMissingLayerInfo(el));
    if (!missing.length) {
      missingLayerSummary.textContent = "Tudo certo: sem pendências de camada.";
      missingLayerList.innerHTML = "";
      state.layerMissingSelected = [];
      return;
    }
    missingLayerSummary.textContent = `${missing.length} bloco(s) com camada incompleta.`;
    const validSelected = new Set(state.layerMissingSelected || []);
    const missingKeys = new Set(missing.map((m) => m.key));
    state.layerMissingSelected = Array.from(validSelected).filter((k) => missingKeys.has(k));
    missingLayerList.innerHTML = "";
    missing.forEach((el) => {
      const btn = document.createElement("button");
      btn.type = "button";
      const selected = state.layerMissingSelected.includes(el.key);
      btn.className = `btn btn-outline-warning btn-sm po-layer-missing-item${selected ? " is-selected" : ""}`;
      btn.textContent = el.title || el.key;
      btn.title = "Selecionar para aplicar o contexto atual";
      btn.dataset.missingLayerKey = el.key;
      missingLayerList.appendChild(btn);
    });
  }

  function fillSelectOptions(selectNode, values, labelBase) {
    if (!selectNode) return;
    const current = String(selectNode.value || "");
    selectNode.innerHTML = `<option value="">${labelBase}</option>`;
    values.forEach((v) => {
      const opt = document.createElement("option");
      opt.value = v;
      opt.textContent = v;
      selectNode.appendChild(opt);
    });
    if (current && values.includes(current)) selectNode.value = current;
    else if (!values.includes(current)) selectNode.value = "";
  }

  function fillDatalistOptions(listNode, values) {
    if (!listNode) return;
    listNode.innerHTML = "";
    values.forEach((v) => {
      const opt = document.createElement("option");
      opt.value = v;
      listNode.appendChild(opt);
    });
  }

  function hasLayerFilterActive() {
    const f = state.layerFilter || {};
    return !!(f.setor || f.bloco || f.pavimento || f.unidade);
  }

  function matchesLayerFilter(el) {
    const f = state.layerFilter || {};
    if (!f.setor && !f.bloco && !f.pavimento && !f.unidade) return true;
    const layer = el.layer || {};
    if (f.setor && !valuesEqualLoose(layer.setor, f.setor)) return false;
    if (f.bloco && !valuesEqualLoose(layer.bloco, f.bloco)) return false;
    if (f.pavimento && !valuesEqualLoose(layer.pavimento, f.pavimento)) return false;
    if (f.unidade && !valuesEqualLoose(layer.unidade, f.unidade)) return false;
    return true;
  }

  function getVisibleElements() {
    if (!hasLayerFilterActive()) return state.elementos;
    const matched = state.elementos.filter((el) => matchesLayerFilter(el));
    if ((state.layerFilter && state.layerFilter.onlyMatches) !== false) return matched;
    return state.elementos;
  }

  function ensureSelectedVisibleAfterFilter() {
    const visible = getVisibleElements();
    const hasCurrent = state.selectedId && visible.some((el) => el.key === state.selectedId);
    if (hasCurrent) return;
    state.selectedId = visible[0] ? visible[0].key : null;
    state.matrixBandSel = null;
  }

  function renderBlocoChips() {
    if (!ctxBlocoChips) return;
    const blocos = state.layerCatalog.bloco || [];
    ctxBlocoChips.innerHTML = "";
    if (!blocos.length) return;
    blocos.forEach((bloco) => {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = `btn btn-sm ${valuesEqualLoose(state.layerFilter.bloco, bloco) ? "btn-primary" : "btn-outline-secondary"}`;
      btn.textContent = bloco;
      btn.dataset.blocoChip = bloco;
      ctxBlocoChips.appendChild(btn);
    });
  }

  function updateLayerFilterSummary() {
    if (!ctxMatchInfo) return;
    const total = state.elementos.length;
    const matched = state.elementos.filter((el) => matchesLayerFilter(el)).length;
    const visible = getVisibleElements().length;
    if (!hasLayerFilterActive()) {
      ctxMatchInfo.textContent = total ? `Todos os blocos (${total})` : "Sem blocos";
      return;
    }
    const f = state.layerFilter || {};
    const tag = [f.setor, f.bloco, f.pavimento, f.unidade].filter(Boolean).join(" • ");
    const extra = visible !== matched ? ` (visíveis ${visible})` : "";
    ctxMatchInfo.textContent = `${matched}/${total} no contexto${extra}${tag ? `: ${tag}` : ""}`;
  }

  function syncLayerFilterUiValues() {
    if (ctxSetor) ctxSetor.value = state.layerFilter.setor || "";
    if (ctxBloco) ctxBloco.value = state.layerFilter.bloco || "";
    if (ctxPavimento) ctxPavimento.value = state.layerFilter.pavimento || "";
    if (ctxUnidade) ctxUnidade.value = state.layerFilter.unidade || "";
    if (ctxOnlyMatches) ctxOnlyMatches.checked = (state.layerFilter.onlyMatches !== false);
  }

  function refreshLayerCatalogUi() {
    collectLayerCatalog();
    if (state.layerFilter.setor && !hasAnyValueMatch("setor", state.layerFilter.setor)) {
      state.layerFilter.setor = "";
      state.layerFilter.bloco = "";
      state.layerFilter.pavimento = "";
      state.layerFilter.unidade = "";
    }
    if (state.layerFilter.bloco && !hasAnyValueMatch("bloco", state.layerFilter.bloco)) {
      state.layerFilter.bloco = "";
      state.layerFilter.pavimento = "";
      state.layerFilter.unidade = "";
    }
    if (state.layerFilter.pavimento && !hasAnyValueMatch("pavimento", state.layerFilter.pavimento)) {
      state.layerFilter.pavimento = "";
      state.layerFilter.unidade = "";
    }
    if (state.layerFilter.unidade && !hasAnyValueMatch("unidade", state.layerFilter.unidade)) {
      state.layerFilter.unidade = "";
    }
    fillSelectOptions(ctxSetor, availableLayerValues("setor"), "Setor");
    fillSelectOptions(ctxBloco, availableLayerValues("bloco"), "Bloco");
    fillSelectOptions(ctxPavimento, availableLayerValues("pavimento"), "Pavimento");
    fillSelectOptions(ctxUnidade, availableLayerValues("unidade"), "Unidade");
    fillDatalistOptions(layerSetorList, state.layerCatalog.setor);
    fillDatalistOptions(layerBlocoList, state.layerCatalog.bloco);
    fillDatalistOptions(layerPavimentoList, state.layerCatalog.pavimento);
    fillDatalistOptions(layerUnidadeList, state.layerCatalog.unidade);
    syncLayerFilterUiValues();
    renderContextTrail();
    renderBlocoChips();
    renderDrilldownHints();
    updateLayerFilterSummary();
    updateContextKpis();
    renderMissingLayerPanel();
  }

  function applyLayerFilterAndRender(options) {
    const opts = options || {};
    updateMatrixViewportSizingForReading();
    ensureSelectedVisibleAfterFilter();
    updateLayerFilterSummary();
    renderBlocoChips();
    renderKonva();
    if (opts.refit) fitView();
  }

  function updateMatrixViewportSizingForReading() {
    const cfg = mergeReadingConfig(state.readingConfig);
    state.elementos.forEach((el) => {
      if (!isMatrixKind(el.kind)) return;
      ensureMatrixData(el);
      const backup = el.data._viewCompactBase;
      if (cfg.enabled === false) {
        if (backup && Number.isFinite(backup.w) && Number.isFinite(backup.h)) {
          el.width = backup.w;
          el.height = backup.h;
        }
        if (el.data && typeof el.data === "object") delete el.data._viewCompactBase;
        return;
      }
      const hBand = getHeaderBandCount(el.data);
      const rawRows = Array.isArray(el.data.rows) ? el.data.rows : [];
      const colCount = Math.max(1, ...rawRows.map((r) => (Array.isArray(r) ? r.length : 0)));
      const rows = matrixRowsForContext(el, rawRows, hBand, colCount);
      const cols = Math.max(1, ...rows.map((r) => (Array.isArray(r) ? r.length : 0)));
      const rowsN = Math.max(1, rows.length);
      if (!backup) {
        el.data._viewCompactBase = { w: Number(el.width) || 900, h: Number(el.height) || 520 };
      }
      const targetW = clamp(Math.max(520, Math.min(1400, 130 + cols * 22)), MIN_W, MAX_CARD_W);
      // Refatoração de layout: matriz de camadas fica compacta verticalmente
      // e usa scroll interno quando houver muitas linhas.
      const targetH = clamp(Math.max(140, Math.min(340, 76 + rowsN * 18)), MIN_H, MAX_CARD_H);
      el.width = targetW;
      el.height = targetH;
      if (el.data.matrixPan && typeof el.data.matrixPan === "object") {
        el.data.matrixPan.x = 0;
        el.data.matrixPan.y = 0;
      }
    });
  }

  function setLayerFilter(next, options) {
    const prev = state.layerFilter || {};
    const readCfg = mergeReadingConfig(state.readingConfig);
    const updated = {
      setor: String(next && next.setor != null ? next.setor : state.layerFilter.setor || "").trim(),
      bloco: String(next && next.bloco != null ? next.bloco : state.layerFilter.bloco || "").trim(),
      pavimento: String(next && next.pavimento != null ? next.pavimento : state.layerFilter.pavimento || "").trim(),
      unidade: String(next && next.unidade != null ? next.unidade : state.layerFilter.unidade || "").trim(),
      onlyMatches:
        next && Object.prototype.hasOwnProperty.call(next, "onlyMatches")
          ? !!next.onlyMatches
          : state.layerFilter.onlyMatches !== false,
    };
    if (readCfg.enabled !== false) updated.onlyMatches = true;
    if (next && Object.prototype.hasOwnProperty.call(next, "setor") && !valuesEqualLoose(updated.setor, prev.setor)) {
      updated.bloco = "";
      updated.pavimento = "";
      updated.unidade = "";
    } else if (next && Object.prototype.hasOwnProperty.call(next, "bloco") && !valuesEqualLoose(updated.bloco, prev.bloco)) {
      updated.pavimento = "";
      updated.unidade = "";
    } else if (next && Object.prototype.hasOwnProperty.call(next, "pavimento") && !valuesEqualLoose(updated.pavimento, prev.pavimento)) {
      updated.unidade = "";
    }
    state.layerFilter = updated;
    saveLayerContextToStorage();
    refreshLayerCatalogUi();
    applyLayerFilterAndRender(options);
  }

  function clearLayerFilterFromLevel(level) {
    if (level === "setor") setLayerFilter({ setor: "", bloco: "", pavimento: "", unidade: "" }, { refit: true });
    else if (level === "bloco") setLayerFilter({ bloco: "", pavimento: "", unidade: "" }, { refit: true });
    else if (level === "pavimento") setLayerFilter({ pavimento: "", unidade: "" }, { refit: true });
    else if (level === "unidade") setLayerFilter({ unidade: "" }, { refit: true });
  }

  function applyContextToMissingSelected() {
    const selectedKeys = state.layerMissingSelected || [];
    if (!selectedKeys.length) {
      showAlert("Selecione ao menos um item em «Pendências de camada».", "warning");
      return;
    }
    const f = state.layerFilter || {};
    if (!f.setor && !f.bloco && !f.pavimento && !f.unidade) {
      showAlert("Defina um contexto ativo antes de aplicar.", "warning");
      return;
    }
    pushHistory();
    let changed = 0;
    state.elementos.forEach((el) => {
      if (!selectedKeys.includes(el.key)) return;
      el.layer = el.layer || {};
      if (f.setor) el.layer.setor = f.setor;
      if (f.bloco) el.layer.bloco = f.bloco;
      if (f.pavimento) el.layer.pavimento = f.pavimento;
      if (f.unidade) el.layer.unidade = f.unidade;
      changed += 1;
    });
    if (!changed) return;
    refreshLayerCatalogUi();
    updatePreview();
    markDirty();
    scheduleRender();
    showAlert(`Contexto aplicado a ${changed} item(ns).`, "success");
  }

  function getSelected() {
    if (!state.selectedId) return null;
    return state.elementos.find((it) => it.key === state.selectedId) || null;
  }

  function normalizeCsrfToken(raw) {
    const token = String(raw || "").trim();
    if (!token) return "";
    const invalid = ["notprovided", "none", "null", "undefined"];
    if (invalid.includes(token.toLowerCase())) return "";
    return token;
  }

  function readCsrfTokenSync() {
    const fromCtx = normalizeCsrfToken(ctx && ctx.csrfToken);
    if (fromCtx) return fromCtx;
    const fromWindow = normalizeCsrfToken(window.__LPLAN_CSRF_TOKEN__);
    if (fromWindow) return fromWindow;
    const bodyToken = normalizeCsrfToken(document.body && document.body.getAttribute("data-csrf-token"));
    if (bodyToken) return bodyToken;
    const meta = document.querySelector('meta[name="csrf-token"]');
    const metaToken = normalizeCsrfToken(meta && meta.getAttribute("content"));
    if (metaToken) return metaToken;
    const hiddenInput = document.querySelector('input[name="csrfmiddlewaretoken"]');
    const inputToken = normalizeCsrfToken(hiddenInput && hiddenInput.value);
    if (inputToken) return inputToken;
    return "";
  }

  function isLikelyCsrfFailure(status, text) {
    const msg = String(text || "").toLowerCase();
    if (status !== 403) return false;
    return msg.includes("csrf") || msg.includes("token de segurança") || msg.includes("token de seguranca");
  }

  async function ensureCsrfToken(forceRefresh) {
    const cached = forceRefresh ? "" : readCsrfTokenSync();
    if (cached) return cached;
    const url =
      (document.body && document.body.getAttribute("data-csrf-token-url")) ||
      window.__LPLAN_CSRF_TOKEN_URL__ ||
      "/api/csrf-token/";
    try {
      const response = await fetch(url, {
        method: "GET",
        credentials: "same-origin",
        headers: { "X-Requested-With": "XMLHttpRequest" },
      });
      const payload = await response.json();
      const token = normalizeCsrfToken(payload && payload.csrfToken);
      if (!token) return "";
      if (document.body) document.body.setAttribute("data-csrf-token", token);
      const meta = document.querySelector('meta[name="csrf-token"]');
      if (meta) meta.setAttribute("content", token);
      window.__LPLAN_CSRF_TOKEN__ = token;
      return token;
    } catch (e) {
      return "";
    }
  }

  async function requestJson(url, options) {
    const config = { ...(options || {}) };
    const csrfRetry = Number(config._csrfRetry || 0);
    delete config._csrfRetry;
    config.credentials = config.credentials || "same-origin";
    const method = String(config.method || "GET").toUpperCase();
    const headers = new Headers(config.headers || {});
    headers.set("X-Requested-With", "XMLHttpRequest");
    if (!["GET", "HEAD", "OPTIONS", "TRACE"].includes(method) && !headers.has("X-CSRFToken")) {
      const csrf = await ensureCsrfToken();
      if (!csrf) {
        throw new Error("Não foi possível validar segurança da sessão (CSRF). Recarregue a página.");
      }
      headers.set("X-CSRFToken", csrf);
    }
    config.headers = headers;

    const response = await fetch(url, config);
    const raw = await response.text();
    let data = {};
    try {
      data = raw ? JSON.parse(raw) : {};
    } catch (e) {
      const contentType = String(response.headers.get("content-type") || "").toLowerCase();
      const lower = raw.toLowerCase();
      if (contentType.includes("text/html") || lower.startsWith("<!doctype") || lower.startsWith("<html")) {
        const finalUrl = String(response.url || "");
        if (response.redirected && /\/accounts\/login\/?/i.test(finalUrl)) {
          throw new Error("Sua sessão expirou. Recarregue a página e faça login novamente.");
        }
        if (lower.includes("csrf")) {
          if (csrfRetry < 1) {
            await ensureCsrfToken(true);
            return requestJson(url, { ...(options || {}), _csrfRetry: csrfRetry + 1 });
          }
          throw new Error("Falha de segurança (CSRF) no envio. Recarregue a página e tente novamente.");
        }
        throw new Error(`A API retornou HTML em vez de JSON (${response.status}) em ${url}. URL final: ${finalUrl || "n/d"}.`);
      }
      throw new Error(response.ok ? "Resposta inválida do servidor." : `Erro HTTP ${response.status}.`);
    }
    if (!response.ok || data.success === false) {
      if (isLikelyCsrfFailure(response.status, data && (data.error || data.message || raw))) {
        if (csrfRetry < 1) {
          await ensureCsrfToken(true);
          return requestJson(url, { ...(options || {}), _csrfRetry: csrfRetry + 1 });
        }
      }
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
    const src = state.elementos;
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
            "Não foi possível salvar em segundo plano. Verifique a ligação à rede e tente «Salvar».",
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

  function updateCanvasQuickFabVisibility() {
    if (!canvasQuickActions) return;
    const draftUi = state.viewMode === "draft";
    const has = !!getSelected();
    const visible = draftUi && has && (state.quickFabHoverSelected || state.quickFabHoverFab);
    canvasQuickActions.classList.toggle("d-none", !visible);
  }

  function scheduleRender() {
    if (state.renderQueued) return;
    state.renderQueued = true;
    requestAnimationFrame(() => {
      state.renderQueued = false;
      renderKonva();
    });
  }

  function scheduleRenderThrottled(minIntervalMs) {
    const interval = Math.max(8, Number(minIntervalMs) || 0);
    const now = Date.now();
    const elapsed = now - (state.lastRenderAt || 0);
    if (elapsed >= interval) {
      scheduleRender();
      return;
    }
    if (state.renderThrottleTimer) return;
    state.renderThrottleTimer = setTimeout(() => {
      state.renderThrottleTimer = null;
      scheduleRender();
    }, Math.max(0, interval - elapsed));
  }

  function scheduleViewportRelayout() {
    if (state.viewportRelayoutTimer) clearTimeout(state.viewportRelayoutTimer);
    state.viewportRelayoutTimer = setTimeout(() => {
      state.viewportRelayoutTimer = null;
      requestAnimationFrame(() => {
        if (shouldFitSingleTableToViewport()) fitView();
        else clampStageToViewportBounds();
        positionCanvasQuickActions();
        repositionMatrixInlineIfOpen();
      });
    }, VIEWPORT_RELAYOUT_DEBOUNCE_MS);
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
    const sc = clamp(newScale, dynamicZoomMin(), ZOOM_MAX);
    stage.scale({ x: sc, y: sc });
    stage.position({
      x: pointer.x - mousePointTo.x * sc,
      y: pointer.y - mousePointTo.y * sc,
    });
    clampStageToViewportBounds();
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
    const dynMinPct = Math.round(dynamicZoomMin() * 100);
    zr.min = String(dynMinPct);
    const v = String(clamp(pct, dynMinPct, Math.round(ZOOM_MAX * 100)));
    zr.value = v;
    zr.setAttribute("aria-valuenow", v);
  }

  function fullscreenElementNow() {
    return document.fullscreenElement || document.webkitFullscreenElement || null;
  }

  function isCanvasFullscreen() {
    const fsEl = fullscreenElementNow();
    return !!(fsEl && fullscreenHost && fsEl === fullscreenHost);
  }

  function updateCanvasFullscreenButton() {
    if (!btnCanvasFullscreen) return;
    const on = isCanvasFullscreen();
    btnCanvasFullscreen.innerHTML = on
      ? '<i class="bi bi-fullscreen-exit"></i> Sair tela cheia do editor'
      : '<i class="bi bi-fullscreen"></i> Tela cheia do editor';
    btnCanvasFullscreen.setAttribute("aria-label", on ? "Sair tela cheia do editor" : "Tela cheia do editor");
    btnCanvasFullscreen.setAttribute("title", on ? "Sair tela cheia do editor" : "Tela cheia do editor");
    btnCanvasFullscreen.setAttribute("aria-pressed", on ? "true" : "false");
  }

  async function toggleCanvasFullscreen() {
    if (!fullscreenHost) return;
    const on = isCanvasFullscreen();
    try {
      if (!on) {
        if (fullscreenHost.requestFullscreen) await fullscreenHost.requestFullscreen();
        else if (fullscreenHost.webkitRequestFullscreen) fullscreenHost.webkitRequestFullscreen();
      } else {
        if (document.exitFullscreen) await document.exitFullscreen();
        else if (document.webkitExitFullscreen) document.webkitExitFullscreen();
      }
    } catch {
      showAlert("Não foi possível alternar tela cheia neste navegador.", "warning");
    }
    updateCanvasFullscreenButton();
    requestAnimationFrame(() => {
      fitView();
      positionCanvasQuickActions();
      repositionMatrixInlineIfOpen();
    });
  }

  /** Corpo da matriz sob o ponteiro (coordenadas do palco), para scroll interno. */
  function matrixBodyHitAtStagePoint(stageX, stageY) {
    const visible = getVisibleElements();
    for (let i = visible.length - 1; i >= 0; i -= 1) {
      const el = visible[i];
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
      state.quickFabHoverSelected = false;
      state.quickFabHoverFab = false;
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
      scheduleRenderThrottled(22);
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
    const stageScale = stageState.stage ? Math.max(0.05, stageState.stage.scaleX() || 1) : 1;
    const clipLeft = m.bodyX - 1;
    const clipTop = m.bodyY - 1;
    const clipRight = m.bodyX + m.bodyW + 1;
    const clipBottom = m.bodyY + m.bodyH + 1;
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
    const avgColW = m.colWidths.length ? m.colWidths.reduce((a, b) => a + b, 0) / m.colWidths.length : 12;
    const avgRowH = m.rowHeights.length ? m.rowHeights.reduce((a, b) => a + b, 0) / m.rowHeights.length : 12;
    const colStride = Math.max(1, Math.min(8, Math.floor(5 / Math.max(1, avgColW * stageScale))));
    const rowStride = Math.max(1, Math.min(10, Math.floor(5 / Math.max(1, avgRowH * stageScale))));
    for (let c = 0; c <= m.colCount; c += 1) {
      const isBoundary = c === 0 || c === m.colCount || c === 1;
      if (colStride > 1 && !isBoundary && c % colStride !== 0) continue;
      const x =
        c === 0
          ? m.colLefts[0]
          : c === m.colCount
            ? m.colLefts[m.colCount - 1] + m.colWidths[m.colCount - 1]
            : m.colLefts[c];
      const xl = x - panX;
      if (xl < clipLeft || xl > clipRight) continue;
      target.add(
        new Konva.Line({
          points: [xl, top, xl, bot],
          ...lineOpts,
        })
      );
    }
    for (let r = 0; r <= m.visRowCount; r += 1) {
      const isBoundary = r === 0 || r === m.visRowCount || r === m.hBand;
      if (rowStride > 1 && !isBoundary && r % rowStride !== 0) continue;
      const y =
        r === 0
          ? m.rowTops[0]
          : r === m.visRowCount
            ? m.rowTops[m.visRowCount - 1] + m.rowHeights[m.visRowCount - 1]
            : m.rowTops[r];
      const yl = y - panY;
      if (yl < clipTop || yl > clipBottom) continue;
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

  function drawMatrixLinksHighlight(clipG, el, m, panX, panY) {
    const list = matrixBindingsForActiveLayer(el);
    if (!list.length) return;
    list.forEach((b) => {
      const r0 = clamp(b.rowStart, m.hBand, m.rows.length - 1);
      const r1 = clamp(b.rowEnd, m.hBand, m.rows.length - 1);
      const c0 = clamp(b.colStart, 1, m.colCount - 1);
      const c1 = clamp(b.colEnd, 1, m.colCount - 1);
      const x = m.colLefts[c0] - panX;
      const y = m.rowTops[r0] - panY;
      const w = m.colLefts[c1] + m.colWidths[c1] - m.colLefts[c0];
      const h = m.rowTops[r1] + m.rowHeights[r1] - m.rowTops[r0];
      clipG.add(
        new Konva.Rect({
          x,
          y,
          width: w,
          height: h,
          fill: "rgba(2, 132, 199, 0.08)",
          stroke: "rgba(2, 132, 199, 0.28)",
          strokeWidth: 0.5,
          dash: [3, 2],
          listening: false,
        })
      );
    });
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
    const clipLeft = m.bodyX - 1;
    const clipTop = m.bodyY - 1;
    const clipRight = m.bodyX + m.bodyW + 1;
    const clipBottom = m.bodyY + m.bodyH + 1;
    const vHeadCanvas = getVerticalHeaders(el.data) || isLayerReadingMode();
    const baseText = st.matrixTextColor;
    const headerBandFills = [st.matrixHeaderBg, st.matrixHeaderAltBg, st.matrixHeaderBg];
    const stageScale = stageState.stage ? Math.max(0.05, stageState.stage.scaleX() || 1) : 1;

    for (let r = 0; r < m.visRowCount; r += 1) {
      const rh = m.rowHeights[r];
      const layerMode = isLayerReadingMode();
      const fontHeadAuto = layerMode
        ? Math.max(6, Math.min(8, Math.floor(rh * 0.28)))
        : Math.max(6, Math.min(9, Math.floor(rh * 0.38)));
      const fontBodyAuto = layerMode
        ? Math.max(6, Math.min(8, Math.floor(rh * 0.3)))
        : Math.max(6, Math.min(10, Math.floor(rh * 0.42)));
      const fontHead =
        st.matrixFontPx > 0 ? clamp(Math.round(st.matrixFontPx * 0.86), 5, 11) : fontHeadAuto;
      const fontBody =
        st.matrixFontPx > 0 ? clamp(Math.round(st.matrixFontPx), 5, 11) : fontBodyAuto;
      const isFoot = m.tRow && r === m.rows.length;
      const isHeader = !isFoot && r < m.hBand;
      const isBody = !isFoot && !isHeader;
      for (let c = 0; c < m.colCount; c += 1) {
        const cx = m.colLefts[c] - panX;
        const cy = m.rowTops[r] - panY;
        const cw = m.colWidths[c];
        if (cx + cw < clipLeft || cx > clipRight || cy + rh < clipTop || cy > clipBottom) continue;
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
        const rawTrim = String(raw || "").trim();
        const skipBgForEmptyBody =
          !isHeader &&
          !isFoot &&
          c > 0 &&
          !(m.tCol && c === m.colCount - 1) &&
          !m.heatmapOn &&
          !rawTrim;
        if (skipBgForEmptyBody) continue;
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
    drawMatrixLinksHighlight(clipG, el, m, panX, panY);
    drawMatrixBandHighlight(clipG, el, m, panX, panY);
    for (let r = 0; r < m.visRowCount; r += 1) {
      const rh = m.rowHeights[r];
      const layerMode = isLayerReadingMode();
      const fontHeadAuto = layerMode
        ? Math.max(6, Math.min(8, Math.floor(rh * 0.28)))
        : Math.max(6, Math.min(9, Math.floor(rh * 0.38)));
      const fontBodyAuto = layerMode
        ? Math.max(6, Math.min(8, Math.floor(rh * 0.3)))
        : Math.max(6, Math.min(10, Math.floor(rh * 0.42)));
      const fontHead =
        st.matrixFontPx > 0 ? clamp(Math.round(st.matrixFontPx * 0.86), 5, 11) : fontHeadAuto;
      const fontBody =
        st.matrixFontPx > 0 ? clamp(Math.round(st.matrixFontPx), 5, 11) : fontBodyAuto;
      const isFoot = m.tRow && r === m.rows.length;
      const isHeader = !isFoot && r < m.hBand;
      const isBody = !isFoot && !isHeader;
      for (let c = 0; c < m.colCount; c += 1) {
        const cx = m.colLefts[c] - panX;
        const cy = m.rowTops[r] - panY;
        const cw = m.colWidths[c];
        if (cx + cw < clipLeft || cx > clipRight || cy + rh < clipTop || cy > clipBottom) continue;
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
        const txt = isHeader ? String(raw || "") : (raw.length > 80 ? `${raw.slice(0, 77)}…` : raw);
        const txtTrim = String(txt || "").trim();
        const skipTxtForEmptyBody =
          !isHeader &&
          !isFoot &&
          c > 0 &&
          !(m.tCol && c === m.colCount - 1) &&
          !txtTrim;
        if (skipTxtForEmptyBody) continue;
        const fs = isHeader || isFoot ? fontHead : fontBody;
        const align = isBody && c === 0 ? "left" : "center";
        const padX = align === "left" ? 4 : 2;
        const projectedCW = cw * stageScale;
        const projectedRH = rh * stageScale;
        const hideBodyTextForTinyCells =
          isBody &&
          c > 0 &&
          !(m.tCol && c === m.colCount - 1) &&
          projectedCW < 20 &&
          projectedRH < 12;
        if (hideBodyTextForTinyCells) continue;
        const lastHeadBand = isHeader && r === m.hBand - 1;
        const vertColHeader = (() => {
          if (!vHeadCanvas || c <= 0) return false;
          if (isLayerReadingMode()) return isHeader;
          return (
            lastHeadBand &&
            cw >= MATRIX_VERT_HEADER_MIN_CW &&
            projectedCW >= 10 &&
            projectedRH >= 14
          );
        })();
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
              wrap: "none",
              ellipsis: true,
              fontStyle: "normal",
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
              fontStyle: (isHeader || isFoot) ? "bold" : "normal",
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
    const ctx = state.mxGridDrag;
    const had = !!ctx;
    state.mxGridDrag = null;
    if (commit && had && ctx.didMove) {
      updatePreview();
      markDirty();
      scheduleRender();
    }
  }

  function beginMxGridDrag(ev, el, mode, index) {
    if (state.mxReorder) return;
    endMxGridDrag(false);
    if (state.mxReorder) endMxReorder(false);
    if (state.viewMode !== "draft" || !state.editMode) return;
    ensureMatrixData(el);
    const evt = ev.evt || ev;
    const t = evt.touches && evt.touches[0];
    const cx = Number.isFinite(t ? t.clientX : evt.clientX) ? (t ? t.clientX : evt.clientX) : 0;
    const cy = Number.isFinite(t ? t.clientY : evt.clientY) ? (t ? t.clientY : evt.clientY) : 0;
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
      didMove: false,
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
      let changed = false;
      if (state.mxGridDrag.mode === "col") {
        const c = state.mxGridDrag.index;
        const w = el.data.colWeights;
        const prevL = Number(w[c - 1]) || 0;
        const prevR = Number(w[c]) || 0;
        const S = state.mxGridDrag.pairSum;
        const dw = (dx / Math.max(1, colA)) * S;
        let a = state.mxGridDrag.startWeights[c - 1] + dw;
        let b = state.mxGridDrag.startWeights[c] - dw;
        a = Math.max(MIN_MATRIX_WEIGHT, a);
        b = Math.max(MIN_MATRIX_WEIGHT, b);
        const s = a + b || 1;
        w[c - 1] = (a / s) * S;
        w[c] = (b / s) * S;
        changed = Math.abs(w[c - 1] - prevL) > 1e-9 || Math.abs(w[c] - prevR) > 1e-9;
      } else {
        const rr = state.mxGridDrag.index;
        const w = el.data.rowWeights;
        const prevU = Number(w[rr - 1]) || 0;
        const prevD = Number(w[rr]) || 0;
        const S = state.mxGridDrag.pairSum;
        const dh = (dy / Math.max(1, rowA)) * S;
        let a = state.mxGridDrag.startWeights[rr - 1] + dh;
        let b = state.mxGridDrag.startWeights[rr] - dh;
        a = Math.max(MIN_MATRIX_WEIGHT, a);
        b = Math.max(MIN_MATRIX_WEIGHT, b);
        const s = a + b || 1;
        w[rr - 1] = (a / s) * S;
        w[rr] = (b / s) * S;
        changed = Math.abs(w[rr - 1] - prevU) > 1e-9 || Math.abs(w[rr] - prevD) > 1e-9;
      }
      if (!changed) return;
      if (!state.mxGridDrag.didMove) {
        pushHistory();
        state.mxGridDrag.didMove = true;
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
    const innerRight = m.bodyX + m.bodyW - m.gap;
    const innerBot = m.bodyY + m.bodyH - m.gap;
    const innerWRect = Math.max(8, innerRight - innerLeft);
    const innerHRect = Math.max(8, innerBot - innerTop);
    hg.clip({ x: m.bodyX, y: m.bodyY, width: m.bodyW, height: m.bodyH });
    const lineIdle = "rgba(148, 163, 184, 0.22)";
    const lineHover = "rgba(37, 99, 235, 0.55)";
    const bindDrag = (hit, mode, idx) => {
      hit.on("mousedown touchstart", (e) => {
        if (state.mxReorder) return;
        if (state.viewMode !== "draft" || !state.editMode) return;
        if (e.evt && e.evt.preventDefault) e.evt.preventDefault();
        if (e.evt && e.evt.stopPropagation) e.evt.stopPropagation();
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
      if (el2 && willApplyMatrixReorder(el2, ctx.axis, ctx.fromIndex, ctx.dropBefore)) {
        pushHistory();
        if (ctx.axis === "col") {
          applied = applyMatrixColReorder(el2, ctx.fromIndex, ctx.dropBefore);
        } else {
          applied = applyMatrixRowReorder(el2, ctx.fromIndex, ctx.dropBefore);
        }
      }
      if (applied) ctx.didApply = true;
      endMxReorder(true);
    };
    window.addEventListener("mousemove", mxReorderMove);
    window.addEventListener("mouseup", mxReorderUp);
    window.addEventListener("touchmove", mxReorderMove, { passive: false });
    window.addEventListener("touchend", mxReorderUp);
    window.addEventListener("touchcancel", mxReorderUp);
    if (evt.preventDefault) evt.preventDefault();
  }

  function willApplyMatrixReorder(el, axis, fromIndex, dropBefore) {
    if (!el || dropBefore == null) return false;
    if (axis === "col") {
      const { minC, maxC } = matrixDraggableColBounds(el);
      if (fromIndex < minC || fromIndex > maxC) return false;
      let toFinal = columnDropBeforeToFinalIndex(fromIndex, dropBefore);
      if (toFinal < minC) toFinal = minC;
      if (toFinal > maxC) toFinal = maxC;
      return toFinal !== fromIndex;
    }
    const { minR, maxR } = matrixDraggableRowBounds(el);
    if (fromIndex < minR || fromIndex > maxR) return false;
    let toFinal = rowDropBeforeToFinalIndex(fromIndex, dropBefore);
    if (toFinal < minR) toFinal = minR;
    if (toFinal > maxR) toFinal = maxR;
    return toFinal !== fromIndex;
  }

  function drawMatrixReorderHandles(group, el) {
    const prev = group.findOne(".po-mx-reorder-g");
    if (prev) prev.destroy();
    const rg = new Konva.Group({ name: "po-mx-reorder-g", listening: true });
    const m = computeMatrixGridMetrics(el);
    const px = m.panX || 0;
    const py = m.panY || 0;
    rg.clip({ x: m.bodyX, y: m.bodyY, width: m.bodyW, height: m.bodyH });
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
          if (state.mxGridDrag) return;
          if (state.viewMode !== "draft" || !state.editMode) return;
          if (e.evt && e.evt.preventDefault) e.evt.preventDefault();
          if (e.evt && e.evt.stopPropagation) e.evt.stopPropagation();
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
          if (state.mxGridDrag) return;
          if (state.viewMode !== "draft" || !state.editMode) return;
          if (e.evt && e.evt.preventDefault) e.evt.preventDefault();
          if (e.evt && e.evt.stopPropagation) e.evt.stopPropagation();
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
    const offContext = hasLayerFilterActive() && !matchesLayerFilter(el) && state.layerFilter.onlyMatches === false;
    const borderW = clamp(Math.round(sel ? st.selectionStrokeWidth : st.cardStrokeWidth), 1, 6);
    const borderColor = sel ? st.selectionStroke : st.cardStroke;
    const useLegacyMatrix = isLegacyMatrixVisual(el);

    const group = new Konva.Group({
      x: el.x,
      y: el.y,
      draggable: state.editMode && state.viewMode === "draft",
      id: el.key,
      width: el.width,
      height: el.height,
      opacity: offContext ? 0.26 : 1,
    });

    if (useLegacyMatrix) {
      group.add(
        new Konva.Rect({
          name: "po-card-bg",
          x: 0,
          y: 0,
          width: el.width,
          height: el.height,
          fill: "#ffffff",
          stroke: sel ? borderColor : "#d1d9e6",
          strokeWidth: sel ? Math.max(1, borderW) : 1,
          cornerRadius: 0,
          shadowEnabled: false,
        })
      );
    } else {
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
    }

    if (isMatrixKind(el.kind)) {
      ensureMatrixData(el);
      const { bodyX, bodyY, bodyW, bodyH } = getMatrixBodyBox(el);
      group.add(
        new Konva.Rect({
          x: bodyX,
          y: bodyY,
          width: bodyW,
          height: bodyH,
          fill: useLegacyMatrix ? "#ffffff" : st.bodyPanelBg,
          stroke: useLegacyMatrix ? "#e5e7eb" : st.bodyPanelStroke,
          strokeWidth: useLegacyMatrix ? 0.4 : 0.55,
          cornerRadius: useLegacyMatrix ? 0 : 4,
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
      state.quickFabHoverSelected = true;
      const tn = evt.target.name && typeof evt.target.name === "function" ? evt.target.name() : "";
      const skipBandSel = tn === "po-mx-resize-handle" || tn === "po-mx-reorder-grip";
      state.matrixBandSel = null;
      if (!skipBandSel && isMatrixKind(el.kind)) {
        const pos = group.getRelativePointerPosition();
        if (pos && Number.isFinite(pos.x) && Number.isFinite(pos.y)) {
          const cell = matrixCellAtPointer(el, pos.x, pos.y);
          if (cell) {
            const m = computeMatrixGridMetrics(el);
            const isFoot = m.tRow && cell.r === m.rows.length;
            const layerField = matrixLayerFieldByColumn(el, m, cell.c);
            const readCfg = mergeReadingConfig(state.readingConfig);
            if (cell.r >= m.hBand && !isFoot && state.viewMode === "draft" && readCfg.enabled !== false) {
              if (layerField) {
                const row = Array.isArray(m.rows[cell.r]) ? m.rows[cell.r] : [];
                const rawVal = String(row[cell.c] || "").trim();
                if (rawVal) {
                  const next = { [layerField]: rawVal };
                  if (layerField === "setor") Object.assign(next, { bloco: "", pavimento: "", unidade: "" });
                  else if (layerField === "bloco") Object.assign(next, { pavimento: "", unidade: "" });
                  else if (layerField === "pavimento") Object.assign(next, { unidade: "" });
                  setLayerFilter(next, { refit: true });
                  showAlert(`Contexto aplicado: ${layerField} ${rawVal}.`, "info");
                  return;
                }
              } else if (cell.c === 0) {
                const rowLabel = String((m.rows[cell.r] && m.rows[cell.r][0]) || "").trim();
                const blocoMatch = rowLabel.match(/^bloco\s+(.+)$/i);
                if (blocoMatch && blocoMatch[1]) {
                  setLayerFilter({ bloco: blocoMatch[1] }, { refit: true });
                  showAlert(`Contexto aplicado: bloco ${blocoMatch[1]}.`, "info");
                  return;
                }
              }
            }
            const isBodyData =
              cell.r >= m.hBand &&
              !isFoot &&
              cell.c > 0 &&
              !(m.tCol && cell.c === m.colCount - 1) &&
              !layerField;
            if (state.viewMode === "draft" && !state.editMode && isBodyData) {
              const b = matrixBindingAtCell(el, cell.r, cell.c);
              if (b && matrixNavigateToBindingLayer(el, b)) {
                renderMatrixInspector(el);
                scheduleRender();
                return;
              }
            }
            if (state.viewMode === "draft" && state.editMode) {
              if (cell.c === 0 && cell.r >= m.hBand && !isFoot) {
                state.matrixBandSel = { elKey: el.key, band: "row", index: cell.r };
              } else if (cell.c >= 1 && cell.r < m.hBand && !isFoot) {
                state.matrixBandSel = { elKey: el.key, band: "col", index: cell.c };
              }
            }
          }
        }
      }
      setTransformerNodes(state.viewMode === "draft" && state.editMode ? [group] : []);
      updateInspector();
      stageState.stage && stageState.stage.batchDraw();
    });

    group.on("mouseenter", () => {
      if (state.selectedId !== el.key) return;
      state.quickFabHoverSelected = true;
      updateCanvasQuickFabVisibility();
      requestAnimationFrame(() => positionCanvasQuickActions());
    });
    group.on("mouseleave", () => {
      if (state.selectedId !== el.key) return;
      state.quickFabHoverSelected = false;
      updateCanvasQuickFabVisibility();
    });

    group.on("dblclick dbltap", (evt) => {
      if (state.viewMode !== "draft" || !state.editMode) return;
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
      setTransformerNodes(state.viewMode === "draft" && state.editMode ? [group] : []);
      updateInspector();
      stageState.stage && stageState.stage.batchDraw();
      if (state.viewMode === "draft" && state.editMode && isMatrixKind(el.kind)) {
        const pos = group.getRelativePointerPosition();
        if (pos && Number.isFinite(pos.x) && Number.isFinite(pos.y)) {
          const cell = matrixCellAtPointer(el, pos.x, pos.y);
          if (cell) {
            openMatrixCellContextMenu(evt.evt.clientX, evt.evt.clientY, el.key, group, cell);
            return;
          }
        }
      }
      if (state.viewMode === "draft" && state.editMode) openCardContextMenu(evt.evt.clientX, evt.evt.clientY, el.key);
    });

    group.on("dragstart", () => {
      if (!state.editMode || state.viewMode !== "draft") {
        group.stopDrag();
        group.position({ x: el.x, y: el.y });
        return;
      }
      pushHistory();
    });

    group.on("dragmove", () => {
      if (!state.editMode || state.viewMode !== "draft") {
        group.position({ x: el.x, y: el.y });
        stageState.stage && stageState.stage.batchDraw();
        return;
      }
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
      if (!state.editMode || state.viewMode !== "draft") {
        group.scale({ x: 1, y: 1 });
        return;
      }
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
    updateMatrixViewportSizingForReading();
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
    const visible = getVisibleElements();
    visible.forEach((el) => drawElement(el));
    if (panBg) panBg.moveToBottom();
    tr.moveToTop();
    stageState.stage.batchDraw();
    state.lastRenderAt = Date.now();
    updateInspector();
    requestAnimationFrame(() => repositionMatrixInlineIfOpen());
  }

  function fitView() {
    if (!stageState.stage) return;
    const stage = stageState.stage;
    const visible = getVisibleElements();
    if (!visible.length) {
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
    const minX = Math.min(...visible.map((e) => e.x));
    const minY = Math.min(...visible.map((e) => e.y));
    const maxX = Math.max(...visible.map((e) => e.x + e.width));
    const maxY = Math.max(...visible.map((e) => e.y + e.height));
    const singleTableFs = shouldFitSingleTableToViewport();
    const innerPad = singleTableFs ? 24 : 80;
    const edgePad = singleTableFs ? 16 : 40;
    const boxW = Math.max(100, maxX - minX + innerPad);
    const boxH = Math.max(100, maxY - minY + innerPad);
    let scale;
    if (singleTableFs && canvasViewport) {
      const vw = Math.max(120, canvasViewport.clientWidth - edgePad * 2);
      const vh = Math.max(120, canvasViewport.clientHeight - edgePad * 2);
      scale = clamp(Math.min(vw / boxW, vh / boxH), dynamicZoomMin(), ZOOM_MAX);
    } else {
      scale = clamp(Math.min(stage.width() / boxW, stage.height() / boxH), dynamicZoomMin(), ZOOM_FIT_CAP);
    }
    stage.scale({ x: scale, y: scale });
    stage.position({
      x: -minX * scale + edgePad,
      y: -minY * scale + edgePad,
    });
    clampStageToViewportBounds();
    if (singleTableFs && canvasViewport) {
      canvasViewport.scrollLeft = 0;
      canvasViewport.scrollTop = 0;
    }
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
    if (!has) {
      state.quickFabHoverSelected = false;
      state.quickFabHoverFab = false;
    }
    updateCanvasQuickFabVisibility();
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
      if (insMatrixAxisPct) insMatrixAxisPct.value = String(matrixAxisPctFromWeights(selected.data));
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
      renderMatrixLinksEditor(null);
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
    renderMatrixLinksEditor(selected);
  }

  function renderMatrixLinksEditor(selected) {
    const nodesReady =
      insMxGroupSel &&
      insMxBindingSel &&
      insMxRowStart &&
      insMxRowEnd &&
      insMxColStart &&
      insMxColEnd;
    if (!nodesReady) return;
    if (!selected || !isMatrixKind(selected.kind)) {
      insMxGroupSel.innerHTML = "";
      insMxBindingSel.innerHTML = "";
      if (insMxLayerNow) insMxLayerNow.textContent = "Camada: raiz";
      return;
    }
    ensureMatrixData(selected);
    const ml = selected.data.matrixLinks || { groups: [], bindings: [] };
    const activeLayer = matrixActiveLayerKey(selected);
    if (insMxLayerNow) insMxLayerNow.textContent = `Camada: ${activeLayer}`;
    const { hBand, dataRows, dataCols } = matrixDataBounds(selected);
    insMxGroupSel.innerHTML = ml.groups
      .map((g) => `<option value="${escMxCell(g.id)}">${escMxCell(g.name)}${g.layerKey ? ` → ${escMxCell(g.layerKey)}` : ""}</option>`)
      .join("");
    if (!ml.groups.length) {
      insMxGroupSel.innerHTML = '<option value="">(sem grupos)</option>';
    }
    const groupById = Object.fromEntries(ml.groups.map((g) => [g.id, g]));
    const visBindings = matrixBindingsForActiveLayer(selected);
    insMxBindingSel.innerHTML = visBindings
      .map((b) => {
        const g = groupById[b.groupId];
        const gName = g ? g.name : b.groupId;
        const rs = Math.max(1, b.rowStart - hBand + 1);
        const re = Math.max(1, b.rowEnd - hBand + 1);
        const cs = Math.max(1, b.colStart);
        const ce = Math.max(1, b.colEnd);
        return `<option value="${escMxCell(b.id)}">${escMxCell(gName)} • L${rs}-${re} • C${cs}-${ce}</option>`;
      })
      .join("");
    if (!visBindings.length) {
      insMxBindingSel.innerHTML = '<option value="">(sem vínculos)</option>';
    }
    const clampInput = (node, min, max) => {
      node.min = String(min);
      node.max = String(Math.max(min, max));
      const cur = Number(node.value) || min;
      node.value = String(clamp(cur, min, Math.max(min, max)));
    };
    clampInput(insMxRowStart, 1, dataRows || 1);
    clampInput(insMxRowEnd, 1, dataRows || 1);
    clampInput(insMxColStart, 1, dataCols || 1);
    clampInput(insMxColEnd, 1, dataCols || 1);
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
    const mapaWeights = matrixMapaPresetWeights(selected.data.rows, true);
    selected.data.headerBandCount = 1;
    selected.data.heatmap = true;
    selected.data.totalsColumnAuto = true;
    selected.data.totalsRowAuto = true;
    selected.data.verticalHeaders = true;
    selected.data.colWeights = mapaWeights.colWeights;
    selected.data.rowWeights = mapaWeights.rowWeights;
    if (insMatrixLevels) insMatrixLevels.value = "1";
    if (insMatrixHeatmap) insMatrixHeatmap.checked = true;
    if (insMatrixTotalsCol) insMatrixTotalsCol.checked = true;
    if (insMatrixTotalsRow) insMatrixTotalsRow.checked = true;
    if (insMatrixVerticalHeaders) insMatrixVerticalHeaders.checked = true;
    ensureMatrixData(selected);
    ensureMatrixNoRightCut(selected);
    updatePreview();
    markDirty();
    renderMatrixInspector(selected);
    scheduleRender();
  }

  /**
   * Evita "corte da direita" após presets/adição de colunas:
   * se o conteúdo horizontal ultrapassar o corpo visível, cresce o cartão no limite da prancheta.
   */
  function ensureMatrixNoRightCut(el) {
    if (!el || !isMatrixKind(el.kind)) return;
    ensureMatrixData(el);
    const m = computeMatrixGridMetrics(el);
    const overflowX = Number(m.overflowPanMaxX) || 0;
    if (overflowX <= 0.5) return;
    const maxGrow = Math.max(0, BOARD_WIDTH - el.x - el.width);
    if (maxGrow <= 0.5) return;
    const grow = Math.min(maxGrow, overflowX + 20);
    if (grow <= 0.5) return;
    el.width = clamp(el.width + grow, MIN_W, MAX_CARD_W);
    ensureMatrixData(el);
    if (el.data && el.data.matrixPan && typeof el.data.matrixPan === "object") {
      el.data.matrixPan.x = 0;
    }
  }

  function matrixAxisPctFromWeights(d) {
    if (!d || !Array.isArray(d.colWeights) || d.colWeights.length < 2) return 22;
    const sum = d.colWeights.reduce((a, b) => a + (Number(b) || 0), 0) || 1;
    return Math.round(clamp((100 * (Number(d.colWeights[0]) || 0)) / sum, 1, 90));
  }

  function spreadWithMin(baseValues, targetSum, minEach) {
    const n = baseValues.length;
    if (!n) return [];
    const floor = n * minEach;
    const target = Math.max(floor, targetSum);
    const extra = target - floor;
    const base = baseValues.map((v) => Math.max(0, Number(v) || 0));
    const baseSum = base.reduce((a, b) => a + b, 0);
    if (baseSum <= 0) {
      const eq = target / n;
      return Array.from({ length: n }, () => eq);
    }
    return base.map((v) => minEach + (extra * v) / baseSum);
  }

  function applyMatrixAxisWidth() {
    if (state.viewMode !== "draft") return;
    const selected = getSelected();
    if (!selected || !isMatrixKind(selected.kind)) {
      showAlert("Selecione a matriz na prancheta.", "warning");
      return;
    }
    ensureMatrixData(selected);
    const w = selected.data.colWeights;
    if (!Array.isArray(w) || w.length < 2) return;
    let pct = Number((insMatrixAxisPct && insMatrixAxisPct.value) || 14);
    if (!Number.isFinite(pct)) pct = 14;
    pct = clamp(pct, 8, 40);
    pushHistory();
    const sum = w.reduce((a, b) => a + (Number(b) || 0), 0) || w.length;
    const minOtherTotal = (w.length - 1) * MIN_MATRIX_WEIGHT;
    const axisTarget = clamp((sum * pct) / 100, MIN_MATRIX_WEIGHT, Math.max(MIN_MATRIX_WEIGHT, sum - minOtherTotal));
    const others = w.slice(1);
    const othersTarget = sum - axisTarget;
    const nextOthers = spreadWithMin(others, othersTarget, MIN_MATRIX_WEIGHT);
    selected.data.colWeights = [axisTarget, ...nextOthers];
    ensureMatrixData(selected);
    if (insMatrixAxisPct) insMatrixAxisPct.value = String(matrixAxisPctFromWeights(selected.data));
    updatePreview();
    markDirty();
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

  function pollDraftConflictOnce() {
    if (state.viewMode !== "draft" || !state.dirty || document.hidden) return;
    if (!state.draftKnownUpdatedAt) return;
    requestJson(ctx.endpoints.detail, { credentials: "same-origin" })
      .then((data) => {
        const srv = (data.versao && data.versao.updated_at) || (data.draft && data.draft.updated_at);
        if (srv && srv !== state.draftKnownUpdatedAt) {
          showAlert(
            "Os dados mudaram no servidor (outra aba ou outro utilizador). Use «Recarregar dados» para alinhar com a versão remota, ou «Salvar» para substituir o servidor pela sua cópia (será pedida confirmação).",
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
      const srv = (data.versao && data.versao.updated_at) || (data.draft && data.draft.updated_at);
      if (!srv || srv === state.draftKnownUpdatedAt) return true;
      if (silent) {
        setSaveState("Conflito: versão remota mais nova", "text-bg-warning");
        if (!state.conflictSkipAlertShown) {
          state.conflictSkipAlertShown = true;
          showAlert(
            "Há uma versão mais recente no servidor. O salvamento automático não foi guardado para não apagar essas alterações. Faça «Recarregar dados» para editar a versão remota, ou «Salvar» e confirme para substituir.",
            "warning"
          );
        }
        return false;
      }
      return window.confirm(
        "Os dados no servidor foram alterados (outra sessão ou outro utilizador).\n\nDeseja substituir a versão remota pela sua cópia local?\n\nOK — Enviar e substituir no servidor.\nCancelar — Não guardar; use «Recarregar dados» para obter os dados remotos."
      );
    } catch {
      return true;
    }
  }

  async function loadDetails() {
    const btnReload = document.getElementById("btnReloadDraft");
    hideAlert();
    cleanupMxGridDragListeners();
    cleanupMxReorderListeners();
    state.mxGridDrag = null;
    state.mxReorder = null;
    state.matrixBandSel = null;
    state.matrixLayerNavByElKey = {};
    state.quickFabHoverSelected = false;
    state.quickFabHoverFab = false;
    closeMatrixInlineEditor(false);
    setButtonLoading(btnReload, true);
    try {
      const data = await requestJson(ctx.endpoints.detail, { credentials: "same-origin" });
      state.draft = data.versao || data.draft || {};
      const readingCfg =
        state.draft &&
        state.draft.metadados &&
        typeof state.draft.metadados === "object"
          ? state.draft.metadados.reading_config
          : null;
      state.readingConfig = mergeReadingConfig(readingCfg);
      persistReadingConfigOnDraft();
      syncReadingConfigUi();
      if (state.readingConfig.enabled !== false) {
        state.layerFilter = { ...(state.layerFilter || {}), onlyMatches: true };
      }
      state.draftKnownUpdatedAt =
        (data.versao && data.versao.updated_at) || (data.draft && data.draft.updated_at) || null;
      populateSemanticas(data.semanticas || []);
      const sectionsFallback =
        state.draft.layout && Array.isArray(state.draft.layout.sections) ? state.draft.layout.sections : [];
      const draftElementos = Array.isArray(data.elementos) && data.elementos.length
        ? data.elementos.map((it, idx) => normalizeElement(it, idx))
        : sectionsFallback.map((it, idx) => normalizeElement(it, idx));
      state.elementos = draftElementos;
      if (
        !state.selectedId ||
        !state.elementos.some((e) => e.key === state.selectedId)
      ) {
        state.selectedId = state.elementos[0] ? state.elementos[0].key : null;
      }
      refreshLayerCatalogUi();
      ensureSelectedVisibleAfterFilter();
      updateMatrixViewportSizingForReading();
      state.dirty = false;
      state.matrixEditUndoPushed = false;
      state.conflictSkipAlertShown = false;
      resetHistory();
      setSaveState("Sem alterações", "text-bg-light");
      renderKonva();
      fitView();
      setInspectorReadOnly(false);
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
      layer: {
        setor: (state.layerFilter && state.layerFilter.setor) || "",
        bloco: (state.layerFilter && state.layerFilter.bloco) || "",
        pavimento: (state.layerFilter && state.layerFilter.pavimento) || "",
        unidade: (state.layerFilter && state.layerFilter.unidade) || "",
      },
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
      },
      body: JSON.stringify(payload),
    });
    if (secTitle) secTitle.value = "";
    await loadDetails();
    showAlert("Seção adicionada com sucesso.", "success");
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
        },
        body: JSON.stringify(payload),
      });
      const syncVersao = resSync.versao || resSync.rascunho;
      if (syncVersao && syncVersao.updated_at) state.draftKnownUpdatedAt = syncVersao.updated_at;
      const resSave = await requestJson(ctx.endpoints.saveDraft, {
        method: "POST",
        credentials: "same-origin",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ layout: state.draft.layout || {}, metadados: state.draft.metadados || {} }),
      });
      const saveVersao = resSave.versao || resSave.rascunho;
      if (saveVersao && saveVersao.updated_at) state.draftKnownUpdatedAt = saveVersao.updated_at;
      state.dirty = false;
      state.conflictSkipAlertShown = false;
      if (state.autoSaveTimer) {
        clearTimeout(state.autoSaveTimer);
        state.autoSaveTimer = null;
      }
      setSaveState("Salvo", "text-bg-success");
      if (!silent) showAlert("Dados salvos com sucesso.", "success");
      startDraftConflictPoll();
      return true;
    } catch (err) {
      setSaveState("Erro ao salvar", "text-bg-danger");
      if (!silent && btnSave) btnSave.title = err.message || "Falha ao salvar";
      if (!silent) showAlert(err.message || "Não foi possível salvar os dados.", "danger");
      throw err;
    } finally {
      if (!silent) setButtonLoading(btnSave, false);
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
    refreshLayerCatalogUi();
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
    refreshLayerCatalogUi();
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
    refreshLayerCatalogUi();
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
    ensureMatrixNoRightCut(selected);
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
    applyParsedRowsToSelectedMatrix(selected, parsed);
    showAlert(`CSV importado (${parsed.length}x${colCount}).`, "success");
  }

  function applyParsedRowsToSelectedMatrix(selected, parsed) {
    pushHistory();
    const cols = Math.max(1, ...parsed.map((r) => (Array.isArray(r) ? r.length : 0)));
    const rowsN = Math.max(1, parsed.length);
    selected.data.rows = parsed;
    selected.data.headerBandCount = 1;
    selected.data.totalsColumnAuto = false;
    selected.data.totalsRowAuto = false;
    selected.data.verticalHeaders = false;
    selected.data.colWeights = null;
    selected.data.rowWeights = null;
    // Pós-importação: aumentar área de leitura para não "apertar" valores (ex.: 100% virando "1").
    const targetW = clamp(Math.max(920, Math.min(3000, 180 + cols * 28)), MIN_W, MAX_CARD_W);
    const targetH = clamp(Math.max(420, Math.min(1500, 140 + rowsN * 26)), MIN_H, MAX_CARD_H);
    selected.width = Math.min(targetW, BOARD_WIDTH - selected.x);
    selected.height = Math.min(targetH, BOARD_HEIGHT - selected.y);
    if (insMatrixLevels) insMatrixLevels.value = "1";
    if (insMatrixTotalsCol) insMatrixTotalsCol.checked = false;
    if (insMatrixTotalsRow) insMatrixTotalsRow.checked = false;
    if (insMatrixVerticalHeaders) insMatrixVerticalHeaders.checked = false;
    ensureMatrixData(selected);
    ensureMatrixNoRightCut(selected);
    updatePreview();
    markDirty();
    renderMatrixInspector(selected);
    scheduleRender();
  }

  function clearMatrixExcelPreview(message) {
    state.matrixExcelPreview = null;
    if (btnMatrixExcelApply) btnMatrixExcelApply.disabled = true;
    if (matrixExcelPreviewInfo) matrixExcelPreviewInfo.textContent = message || "Sem prévia.";
    if (matrixExcelPreviewArea) matrixExcelPreviewArea.value = "";
  }

  function computeMatrixImportDiff(currentRows, incomingRows) {
    const oldRows = Array.isArray(currentRows) ? currentRows : [];
    const newRows = Array.isArray(incomingRows) ? incomingRows : [];
    const oldR = oldRows.length;
    const newR = newRows.length;
    const oldC = Math.max(0, ...oldRows.map((r) => (Array.isArray(r) ? r.length : 0)));
    const newC = Math.max(0, ...newRows.map((r) => (Array.isArray(r) ? r.length : 0)));
    const maxR = Math.max(oldR, newR);
    const maxC = Math.max(oldC, newC);
    let changed = 0;
    let addedFilled = 0;
    let removedFilled = 0;
    for (let r = 0; r < maxR; r += 1) {
      for (let c = 0; c < maxC; c += 1) {
        const oldV = r < oldR && c < oldC ? String((oldRows[r] && oldRows[r][c]) ?? "") : "";
        const newV = r < newR && c < newC ? String((newRows[r] && newRows[r][c]) ?? "") : "";
        if (oldV === newV) continue;
        changed += 1;
        if (!oldV && newV) addedFilled += 1;
        if (oldV && !newV) removedFilled += 1;
      }
    }
    return { oldR, oldC, newR, newC, changed, addedFilled, removedFilled };
  }

  function renderMatrixExcelPreview(data) {
    const selected = getSelected();
    const rows = Array.isArray(data.rows) ? data.rows : [];
    const colCount = Math.max(...rows.map((r) => (Array.isArray(r) ? r.length : 0)), 0);
    const strategyTag = data.strategy ? ` ${data.strategy}` : "";
    const selectedSheet = (data.read && data.read.selected_sheet) || data.sheet || "-";
    const diff = selected && isMatrixKind(selected.kind) ? computeMatrixImportDiff(selected.data && selected.data.rows, rows) : null;
    const diffTag = diff ? ` | Δ ${diff.changed}` : "";
    const sizeTag = diff ? ` | ${diff.oldR}x${diff.oldC}→${diff.newR}x${diff.newC}` : ` | ${rows.length}x${colCount}`;
    const scoreTag = data.report && data.report.strategy_scores && Object.keys(data.report.strategy_scores).length
      ? ` | s${Object.keys(data.report.strategy_scores).length}`
      : "";
    if (matrixExcelPreviewInfo) {
      matrixExcelPreviewInfo.textContent = `${selectedSheet}${sizeTag}${diffTag}${strategyTag}${scoreTag}`;
    }
    if (matrixExcelPreviewArea) {
      const sample = rows.slice(0, 12);
      matrixExcelPreviewArea.value = exportMatrixCsv(sample);
    }
    if (btnMatrixExcelApply) btnMatrixExcelApply.disabled = !rows.length;
  }

  async function fetchMatrixExcelImportData(forceMode) {
    if (state.viewMode !== "draft") return;
    if (!ctx.endpoints || !ctx.endpoints.importMatrixExcel) {
      throw new Error("Endpoint de importação não configurado.");
    }
    const file = matrixExcelFile && matrixExcelFile.files && matrixExcelFile.files[0];
    if (!file) {
      throw new Error("Selecione um arquivo Excel/CSV para importar.");
    }
    const fd = new FormData();
    fd.append("arquivo", file);
    if (matrixExcelSheet && matrixExcelSheet.value.trim()) fd.append("sheet", matrixExcelSheet.value.trim());
    if (forceMode) fd.append("mode", forceMode);
    else if (matrixExcelMode && matrixExcelMode.value) fd.append("mode", matrixExcelMode.value);
    return requestJson(ctx.endpoints.importMatrixExcel, {
      method: "POST",
      headers: {},
      credentials: "same-origin",
      body: fd,
    });
  }

  async function previewMatrixExcelImport() {
    try {
      const data = await fetchMatrixExcelImportData();
      const rows = Array.isArray(data.rows) ? data.rows : [];
      if (!rows.length) throw new Error("Nenhum dado encontrado para prévia.");
      state.matrixExcelPreview = data;
      renderMatrixExcelPreview(data);
      showAlert("Prévia carregada. Revise e clique em «Aplicar prévia na matriz».", "info");
    } catch (err) {
      clearMatrixExcelPreview("Falha ao gerar prévia.");
      showAlert(err.message || "Falha ao analisar planilha.", "danger");
    }
  }

  function applyMatrixExcelPreviewToMatrix() {
    const selected = getSelected();
    if (!selected || !isMatrixKind(selected.kind)) {
      showAlert("Selecione a matriz na prancheta.", "warning");
      return;
    }
    const data = state.matrixExcelPreview;
    const rows = data && Array.isArray(data.rows) ? data.rows : [];
    if (!rows.length) {
      showAlert("Primeiro gere a prévia da planilha.", "warning");
      return;
    }
    const diff = computeMatrixImportDiff(selected.data && selected.data.rows, rows);
    const colCount = Math.max(...rows.map((r) => (Array.isArray(r) ? r.length : 0)), 0);
    applyParsedRowsToSelectedMatrix(selected, rows);
    if (matrixCsvArea) matrixCsvArea.value = exportMatrixCsv(rows);
    const strategyTag = data.strategy ? ` [${data.strategy}]` : "";
    const selectedSheet = (data.read && data.read.selected_sheet) || data.sheet;
    showAlert(
      `Importação aplicada (${rows.length}x${colCount})${selectedSheet ? ` - aba ${selectedSheet}` : ""}${strategyTag} | ${diff.changed} células alteradas.`,
      "success"
    );
  }

  async function applyMatrixExcelSmartImport() {
    const selected = getSelected();
    if (!selected || !isMatrixKind(selected.kind)) {
      showAlert("Selecione a matriz na prancheta.", "warning");
      return;
    }
    try {
      const data = await fetchMatrixExcelImportData("auto");
      const rows = Array.isArray(data.rows) ? data.rows : [];
      if (!rows.length) throw new Error("Nenhum dado encontrado para importação.");
      const confidence = Number(data.report && data.report.confidence);
      const isHighConfidence = Number.isFinite(confidence) ? confidence >= 0.62 : false;
      const strongStrategy = ["pivot_registros", "pivot_atividade_colunas"].includes(
        String(data.strategy || "")
      );
      if (!isHighConfidence && !strongStrategy) {
        state.matrixExcelPreview = data;
        renderMatrixExcelPreview(data);
        showAlert("Leitura com baixa confiança. Revise em «Opções avançadas» e aplique a prévia.", "warning");
        return;
      }
      state.matrixExcelPreview = data;
      applyMatrixExcelPreviewToMatrix();
    } catch (err) {
      clearMatrixExcelPreview("Falha ao importar.");
      showAlert(err.message || "Falha ao importar planilha.", "danger");
    }
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

  function matrixLinksAddGroup() {
    if (state.viewMode !== "draft") return;
    const selected = getSelected();
    if (!selected || !isMatrixKind(selected.kind)) return;
    ensureMatrixData(selected);
    const name = String((insMxGroupName && insMxGroupName.value) || "").trim();
    if (!name) {
      showAlert("Informe o nome do grupo.", "warning");
      return;
    }
    const layerKey = String((insMxGroupLayer && insMxGroupLayer.value) || "").trim();
    pushHistory();
    const ml = selected.data.matrixLinks;
    const id = matrixNextId(ml.groups, "g");
    ml.groups.push({ id, name, layerKey });
    if (insMxGroupName) insMxGroupName.value = "";
    updatePreview();
    markDirty();
    renderMatrixInspector(selected);
    scheduleRender();
  }

  function matrixLinksDelGroup() {
    if (state.viewMode !== "draft") return;
    const selected = getSelected();
    if (!selected || !isMatrixKind(selected.kind)) return;
    ensureMatrixData(selected);
    const groupId = String((insMxGroupSel && insMxGroupSel.value) || "").trim();
    if (!groupId) return;
    pushHistory();
    const ml = selected.data.matrixLinks;
    ml.groups = ml.groups.filter((g) => g.id !== groupId);
    ml.bindings = ml.bindings.filter((b) => b.groupId !== groupId);
    updatePreview();
    markDirty();
    renderMatrixInspector(selected);
    scheduleRender();
  }

  function matrixLinksAddBinding() {
    if (state.viewMode !== "draft") return;
    const selected = getSelected();
    if (!selected || !isMatrixKind(selected.kind)) return;
    ensureMatrixData(selected);
    const groupId = String((insMxGroupSel && insMxGroupSel.value) || "").trim();
    if (!groupId) {
      showAlert("Selecione um grupo para vincular.", "warning");
      return;
    }
    const { hBand, dataRows, dataCols } = matrixDataBounds(selected);
    const r1 = clamp(Number((insMxRowStart && insMxRowStart.value) || 1) || 1, 1, Math.max(1, dataRows));
    const r2 = clamp(Number((insMxRowEnd && insMxRowEnd.value) || r1) || r1, 1, Math.max(1, dataRows));
    const c1 = clamp(Number((insMxColStart && insMxColStart.value) || 1) || 1, 1, Math.max(1, dataCols));
    const c2 = clamp(Number((insMxColEnd && insMxColEnd.value) || c1) || c1, 1, Math.max(1, dataCols));
    pushHistory();
    const ml = selected.data.matrixLinks;
    const id = matrixNextId(ml.bindings, "b");
    ml.bindings.push({
      id,
      groupId,
      sourceLayer: matrixActiveLayerKey(selected),
      rowStart: hBand + Math.min(r1, r2) - 1,
      rowEnd: hBand + Math.max(r1, r2) - 1,
      colStart: Math.min(c1, c2),
      colEnd: Math.max(c1, c2),
    });
    updatePreview();
    markDirty();
    renderMatrixInspector(selected);
    scheduleRender();
  }

  function matrixLinksDelBinding() {
    if (state.viewMode !== "draft") return;
    const selected = getSelected();
    if (!selected || !isMatrixKind(selected.kind)) return;
    ensureMatrixData(selected);
    const bId = String((insMxBindingSel && insMxBindingSel.value) || "").trim();
    if (!bId) return;
    pushHistory();
    const ml = selected.data.matrixLinks;
    ml.bindings = ml.bindings.filter((b) => b.id !== bId);
    updatePreview();
    markDirty();
    renderMatrixInspector(selected);
    scheduleRender();
  }

  function matrixBindingAtCell(el, r, c) {
    ensureMatrixData(el);
    const list = matrixBindingsForActiveLayer(el);
    for (let i = 0; i < list.length; i += 1) {
      const b = list[i];
      if (r >= b.rowStart && r <= b.rowEnd && c >= b.colStart && c <= b.colEnd) return b;
    }
    return null;
  }

  function matrixNavigateToBindingLayer(el, binding) {
    if (!el || !binding) return false;
    ensureMatrixData(el);
    const ml = el.data.matrixLinks;
    const g = (ml.groups || []).find((x) => x.id === binding.groupId);
    if (!g || !g.layerKey) return false;
    const target = String(g.layerKey).trim();
    if (!target) return false;
    const nav = matrixLayerNavState(el);
    const current = String(nav.activeLayer || "root");
    if (current === target) return false;
    if (!Array.isArray(nav.stack) || !nav.stack.length) nav.stack = [current || "root"];
    nav.stack.push(target);
    nav.activeLayer = target;
    return true;
  }

  function matrixNavigateBackLayer(el) {
    if (!el || !isMatrixKind(el.kind)) return false;
    ensureMatrixData(el);
    const nav = matrixLayerNavState(el);
    if (!Array.isArray(nav.stack) || nav.stack.length <= 1) return false;
    nav.stack.pop();
    nav.activeLayer = nav.stack[nav.stack.length - 1] || "root";
    return true;
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
  if (btnCanvasFullscreen) btnCanvasFullscreen.addEventListener("click", () => toggleCanvasFullscreen());
  if (btnToggleEdit) {
    btnToggleEdit.addEventListener("click", () => {
      setEditMode(!state.editMode);
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
  if (btnSaveDraft) btnSaveDraft.addEventListener("click", () => saveDraft().catch((err) => showAlert(err.message, "danger")));
  if (ctxSetor) {
    ctxSetor.addEventListener("change", () => setLayerFilter({ setor: ctxSetor.value }, { refit: true }));
  }
  if (ctxBloco) {
    ctxBloco.addEventListener("change", () => setLayerFilter({ bloco: ctxBloco.value }, { refit: true }));
  }
  if (ctxPavimento) {
    ctxPavimento.addEventListener("change", () => setLayerFilter({ pavimento: ctxPavimento.value }, { refit: true }));
  }
  if (ctxUnidade) {
    ctxUnidade.addEventListener("change", () => setLayerFilter({ unidade: ctxUnidade.value }, { refit: true }));
  }
  if (ctxOnlyMatches) {
    ctxOnlyMatches.addEventListener("change", () =>
      setLayerFilter({ onlyMatches: ctxOnlyMatches.checked }, { refit: false })
    );
  }
  if (ctxMatrixReadEnabled) {
    ctxMatrixReadEnabled.addEventListener("change", () => {
      // Modo estrutural: mantém ativo e apenas sincroniza UI.
      setReadingConfig({ enabled: true }, { markDirty: false, render: true, refit: false });
    });
  }
  if (ctxMatrixReadStrategy) {
    ctxMatrixReadStrategy.addEventListener("change", () => {
      setReadingConfig({ strategy: String(ctxMatrixReadStrategy.value || "auto") }, { markDirty: true, render: true, refit: false });
    });
  }
  [ctxAliasSetor, ctxAliasBloco, ctxAliasPavimento, ctxAliasUnidade].forEach((input) => {
    if (!input) return;
    input.addEventListener("change", () => {
      setReadingConfig(
        {
          aliases: {
            setor: ctxAliasSetor ? ctxAliasSetor.value : "",
            bloco: ctxAliasBloco ? ctxAliasBloco.value : "",
            pavimento: ctxAliasPavimento ? ctxAliasPavimento.value : "",
            unidade: ctxAliasUnidade ? ctxAliasUnidade.value : "",
          },
        },
        { markDirty: true, render: true, refit: false }
      );
    });
  });
  const layerFilterShell = document.querySelector(".po-layer-filter");
  if (layerFilterShell) {
    layerFilterShell.addEventListener("click", (event) => {
      const target = event.target;
      if (!(target instanceof HTMLElement)) return;
      const btn = target.closest("[data-read-preset]");
      if (!btn) return;
      applyReadingPreset(btn.getAttribute("data-read-preset") || "auto");
    });
  }
  if (btnCtxClear) {
    btnCtxClear.addEventListener("click", () =>
      setLayerFilter({ setor: "", bloco: "", pavimento: "", unidade: "" }, { refit: true })
    );
  }
  if (btnCtxSave) {
    btnCtxSave.addEventListener("click", () => {
      saveLayerContextToStorage();
      showAlert("Contexto salvo para este ambiente.", "success");
    });
  }
  if (btnCtxRestore) {
    btnCtxRestore.addEventListener("click", () => {
      const stored = loadLayerContextFromStorage();
      if (!stored) {
        showAlert("Não há contexto salvo para restaurar.", "info");
        return;
      }
      setLayerFilter(stored, { refit: true });
      showAlert("Contexto restaurado.", "success");
    });
  }
  if (ctxTrail) {
    ctxTrail.addEventListener("click", (event) => {
      const target = event.target;
      if (!(target instanceof HTMLElement)) return;
      const btn = target.closest("[data-ctx-clear-level]");
      if (!btn) return;
      clearLayerFilterFromLevel(String(btn.getAttribute("data-ctx-clear-level") || ""));
    });
  }
  if (ctxDrilldown) {
    ctxDrilldown.addEventListener("click", (event) => {
      const target = event.target;
      if (!(target instanceof HTMLElement)) return;
      const btn = target.closest("[data-drill-field]");
      if (!btn) return;
      const field = String(btn.getAttribute("data-drill-field") || "");
      const value = String(btn.getAttribute("data-drill-value") || "");
      if (!field) return;
      if (field === "bloco") setLayerFilter({ bloco: value }, { refit: true });
      else if (field === "pavimento") setLayerFilter({ pavimento: value }, { refit: true });
      else if (field === "unidade") setLayerFilter({ unidade: value }, { refit: true });
    });
  }
  if (ctxBlocoChips) {
    ctxBlocoChips.addEventListener("click", (event) => {
      const target = event.target;
      if (!(target instanceof HTMLElement)) return;
      const btn = target.closest("[data-bloco-chip]");
      if (!btn) return;
      const bloco = String(btn.getAttribute("data-bloco-chip") || "");
      const same = valuesEqualLoose(state.layerFilter.bloco, bloco);
      setLayerFilter({ bloco: same ? "" : bloco }, { refit: true });
    });
  }
  if (missingLayerList) {
    missingLayerList.addEventListener("click", (event) => {
      const target = event.target;
      if (!(target instanceof HTMLElement)) return;
      const btn = target.closest("[data-missing-layer-key]");
      if (!btn) return;
      const key = String(btn.getAttribute("data-missing-layer-key") || "");
      if (!key) return;
      const cur = new Set(state.layerMissingSelected || []);
      if (cur.has(key)) cur.delete(key);
      else cur.add(key);
      state.layerMissingSelected = Array.from(cur);
      renderMissingLayerPanel();
    });
  }
  if (btnApplyContextToSelectedMissing) {
    btnApplyContextToSelectedMissing.addEventListener("click", () => applyContextToMissingSelected());
  }

  const poEditorPanel = document.getElementById("poEditorPanel");
  if (poEditorPanel) {
    poEditorPanel.addEventListener("click", (ev) => {
      const btn = ev.target.closest("[data-po-action]");
      if (!btn || !poEditorPanel.contains(btn)) return;
      const action = btn.getAttribute("data-po-action");
      if (!action) return;
      ev.preventDefault();
      const needsEditMode = [
        "apply",
        "dup-section",
        "remove-section",
        "add-row",
        "add-col",
        "remove-row",
        "remove-col",
        "matrix-preset-mapa",
        "matrix-csv-import",
        "matrix-excel-smart",
        "matrix-excel-apply",
        "matrix-axis-apply",
        "mx-group-add",
        "mx-group-del",
        "mx-bind-add",
        "mx-bind-del",
        "appearance-pop",
      ];
      if (needsEditMode.includes(action) && (state.viewMode !== "draft" || !state.editMode)) {
        showAlert(
          isEmbedMode
            ? "Edição desativada. No topo, clique em 'Edição estrutural' para liberar alterações."
            : "Com modo edição OFF, a prancheta fica somente para navegação de camadas.",
          "info"
        );
        return;
      }
      if (action === "reload") {
        loadDetails().catch((err) => showAlert(err.message, "danger"));
      } else if (action === "save") {
        saveDraft().catch((err) => showAlert(err.message, "danger"));
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
      } else if (action === "matrix-excel-smart") {
        applyMatrixExcelSmartImport();
      } else if (action === "matrix-excel-preview") {
        previewMatrixExcelImport();
      } else if (action === "matrix-excel-apply") {
        applyMatrixExcelPreviewToMatrix();
      } else if (action === "matrix-csv-export") {
        applyMatrixCsvExport();
      } else if (action === "matrix-axis-apply") {
        applyMatrixAxisWidth();
      } else if (action === "mx-group-add") {
        matrixLinksAddGroup();
      } else if (action === "mx-group-del") {
        matrixLinksDelGroup();
      } else if (action === "mx-bind-add") {
        matrixLinksAddBinding();
      } else if (action === "mx-bind-del") {
        matrixLinksDelBinding();
      } else if (action === "mx-layer-back") {
        if (state.viewMode !== "draft") return;
        const sel = getSelected();
        if (sel && isMatrixKind(sel.kind) && matrixNavigateBackLayer(sel)) {
          renderMatrixInspector(sel);
          scheduleRender();
        }
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
      if (state.viewMode !== "draft" || !state.editMode) return;
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
        refreshLayerCatalogUi();
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
    if (insMxGroupSel) {
      insMxGroupSel.addEventListener("change", () => {
        const sel = getSelected();
        if (!sel || !isMatrixKind(sel.kind)) return;
        ensureMatrixData(sel);
        const gid = String(insMxGroupSel.value || "");
        const g = (sel.data.matrixLinks.groups || []).find((x) => x.id === gid);
        if (g && insMxGroupLayer) insMxGroupLayer.value = g.layerKey || "";
      });
    }
    [matrixExcelFile, matrixExcelSheet, matrixExcelMode].forEach((el) => {
      if (!el) return;
      const evt = el === matrixExcelFile ? "change" : "input";
      el.addEventListener(evt, () => clearMatrixExcelPreview("Prévia limpa: ajuste detectado no arquivo/configuração."));
    });
  }
  clearMatrixExcelPreview();
  const btnQuickAppearanceSelected = document.getElementById("btnQuickAppearanceSelected");
  if (btnQuickAppearanceSelected) {
    btnQuickAppearanceSelected.addEventListener("click", (e) => {
      const r = e.currentTarget.getBoundingClientRect();
      openAppearanceFromUi(r.right + 4, r.top);
    });
  }
  if (btnQuickDuplicateSelected) btnQuickDuplicateSelected.addEventListener("click", duplicateSelectedSection);
  if (btnQuickDeleteSelected) btnQuickDeleteSelected.addEventListener("click", removeSelectedSection);
  if (canvasQuickActions) {
    canvasQuickActions.addEventListener("mouseenter", () => {
      state.quickFabHoverFab = true;
      updateCanvasQuickFabVisibility();
    });
    canvasQuickActions.addEventListener("mouseleave", () => {
      state.quickFabHoverFab = false;
      updateCanvasQuickFabVisibility();
    });
  }
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
  window.addEventListener("resize", scheduleViewportRelayout);
  document.addEventListener("fullscreenchange", () => {
    updateCanvasFullscreenButton();
    scheduleViewportRelayout();
  });
  document.addEventListener("webkitfullscreenchange", () => {
    updateCanvasFullscreenButton();
    scheduleViewportRelayout();
  });
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
        if (state.viewMode !== "draft" || !state.editMode) return;
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
      if (state.viewMode !== "draft" || !state.editMode) return;
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

  window.addEventListener("message", (event) => {
    if (event.origin !== window.location.origin) return;
    if (isEmbedMode && event.source !== window.parent) return;
    const data = event.data;
    if (!data || typeof data !== "object") return;
    if (data.type !== "po:setEditMode") return;
    const payload = data.payload;
    if (!payload || typeof payload !== "object" || typeof payload.editMode !== "boolean") return;
    setEditMode(payload.editMode, { forceRender: true });
  });

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
      if (state.viewMode !== "draft" || !state.editMode) return;
      event.preventDefault();
      duplicateSelectedSection();
      return;
    }
    if (event.key === "Delete" && state.viewMode === "draft" && state.editMode) {
      const selected = getSelected();
      if (selected) removeSelectedSection();
    }
  });

  syncEditModeUi();
  updateCanvasFullscreenButton();
  syncReadingConfigUi();
  if (ctxOnlyMatches) state.layerFilter.onlyMatches = !!ctxOnlyMatches.checked;
  const storedLayerCtx = loadLayerContextFromStorage();
  if (storedLayerCtx) {
    state.layerFilter = { ...state.layerFilter, ...storedLayerCtx };
  }
  refreshLayerCatalogUi();
  loadDetails().catch((err) => showAlert(err.message, "danger"));
})();

