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
  const btnReload = document.getElementById("btnReloadDraft");
  const btnPublish = document.getElementById("btnPublish");
  const saveStatusBadge = document.getElementById("saveStatusBadge");
  const canvasQuickActions = document.getElementById("canvasQuickActions");
  const btnQuickDuplicateSelected = document.getElementById("btnQuickDuplicateSelected");
  const btnQuickDeleteSelected = document.getElementById("btnQuickDeleteSelected");
  const miniMap = document.getElementById("miniMap");
  const inspectorEmpty = document.getElementById("inspectorEmpty");
  const inspectorForm = document.getElementById("inspectorForm");
  const insTitle = document.getElementById("insTitle");
  const insSemantica = document.getElementById("insSemantica");
  const insSetor = document.getElementById("insSetor");
  const insBloco = document.getElementById("insBloco");
  const insPavimento = document.getElementById("insPavimento");
  const insUnidade = document.getElementById("insUnidade");
  const btnApplyInspector = document.getElementById("btnApplyInspector");
  const btnDuplicateSection = document.getElementById("btnDuplicateSection");
  const btnRemoveSection = document.getElementById("btnRemoveSection");
  const matrixTools = document.getElementById("matrixTools");
  const matrixGridEditor = document.getElementById("matrixGridEditor");
  const btnAddRow = document.getElementById("btnAddRow");
  const btnAddCol = document.getElementById("btnAddCol");

  const GRID = 24;
  const BOARD_WIDTH = 3200;
  const BOARD_HEIGHT = 2000;
  const MIN_W = 120;
  const MIN_H = 90;
  const stageState = { stage: null, layer: null, tr: null };
  const state = {
    draft: {},
    elementos: [],
    selectedId: null,
    editMode: true,
    semanticas: [],
    renderQueued: false,
    dirty: false,
    autoSaveTimer: null,
  };

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

  function pretty(data) {
    return JSON.stringify(data || {}, null, 2);
  }

  function clamp(value, min, max) {
    return Math.max(min, Math.min(max, value));
  }

  function snap(value) {
    return Math.round(value / GRID) * GRID;
  }

  function uuidShort() {
    return `sec_${Math.random().toString(16).slice(2, 10)}`;
  }

  function ensureMatrixData(el) {
    if (!isMatrixKind(el.kind)) return;
    if (!el.data || !Array.isArray(el.data.rows) || !el.data.rows.length) {
      el.data = { rows: [["Coluna 1", "Coluna 2"], ["", ""], ["", ""]] };
    }
  }

  function isMatrixKind(kind) {
    return kind === "matrix_table" || kind === "table";
  }

  function normalizeElement(item, index) {
    const normalized = {
      id: item.id || null,
      key: item.chave_externa || item.key || uuidShort(),
      title: item.titulo || item.title || "Sem título",
      kind: item.kind || (item.dados && item.dados.kind) || "block",
      semantica: item.semantica || (item.dados && item.dados.semantica) || "",
      x: Number.isFinite(item.x) ? item.x : 80 + ((index % 4) * 280),
      y: Number.isFinite(item.y) ? item.y : 80 + (Math.floor(index / 4) * 220),
      width: Number.isFinite(item.width) ? item.width : (item.kind === "matrix_table" ? 560 : 320),
      height: Number.isFinite(item.height) ? item.height : (item.kind === "matrix_table" ? 320 : 180),
      layer: item.layer || item.camada || {},
      data: item.data || item.dados || {},
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
    const data = await response.json();
    if (!response.ok || data.success === false) {
      throw new Error(data.error || "Falha na operação.");
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
    const sections = state.elementos.map((el) => ({
      id: el.key,
      title: el.title,
      kind: el.kind,
      x: el.x,
      y: el.y,
      width: el.width,
      height: el.height,
      semantica: el.semantica,
      layer: el.layer || {},
      data: el.kind === "matrix_table" ? el.data : {},
    }));
    state.draft.layout = state.draft.layout || {};
    state.draft.layout.sections = sections;
    if (draftPreview) draftPreview.textContent = pretty(state.draft);
  }

  function markDirty() {
    state.dirty = true;
    setSaveState("Alterações não salvas", "text-bg-warning");
    if (state.autoSaveTimer) clearTimeout(state.autoSaveTimer);
    state.autoSaveTimer = setTimeout(() => {
      saveDraft({ silent: true }).catch(() => {});
    }, 2500);
  }

  function scheduleRender() {
    if (state.renderQueued) return;
    state.renderQueued = true;
    requestAnimationFrame(() => {
      state.renderQueued = false;
      renderKonva();
    });
  }

  function initStage() {
    if (!canvasBoard || !window.Konva) return;
    // Pan com botão do meio/direito (evita conflito com edição de blocos).
    if (window.Konva) window.Konva.dragButtons = [1, 2];
    canvasBoard.innerHTML = "";
    const stage = new Konva.Stage({
      container: "canvasBoard",
      width: BOARD_WIDTH,
      height: BOARD_HEIGHT,
      draggable: true,
    });
    const layer = new Konva.Layer();
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
      // Zoom só com Ctrl+Wheel para não degradar scroll/navegação padrão.
      if (!e.evt.ctrlKey) return;
      e.evt.preventDefault();
      const oldScale = stage.scaleX();
      const pointer = stage.getPointerPosition();
      if (!pointer) return;
      const mousePointTo = {
        x: (pointer.x - stage.x()) / oldScale,
        y: (pointer.y - stage.y()) / oldScale,
      };
      let direction = e.evt.deltaY > 0 ? 1 : -1;
      if (e.evt.ctrlKey) direction = -direction;
      const scaleBy = 1.04;
      const newScale = direction > 0 ? oldScale * scaleBy : oldScale / scaleBy;
      stage.scale({ x: clamp(newScale, 0.4, 2.4), y: clamp(newScale, 0.4, 2.4) });
      const newPos = {
        x: pointer.x - mousePointTo.x * stage.scaleX(),
        y: pointer.y - mousePointTo.y * stage.scaleY(),
      };
      stage.position(newPos);
      stage.batchDraw();
      renderMiniMap();
    });
    stage.on("dragmove", () => renderMiniMap());

    stage.on("click tap", (e) => {
      if (e.target === stage) {
        state.selectedId = null;
        tr.nodes([]);
        updateInspector();
        stage.batchDraw();
      }
    });

    stageState.stage = stage;
    stageState.layer = layer;
    stageState.tr = tr;
  }

  function drawElement(el) {
    const layer = stageState.layer;
    const tr = stageState.tr;
    if (!layer || !tr) return;

    const group = new Konva.Group({
      x: el.x,
      y: el.y,
      draggable: state.editMode,
      id: el.key,
      width: el.width,
      height: el.height,
    });

    const bg = new Konva.Rect({
      x: 0,
      y: 0,
      width: el.width,
      height: el.height,
      fill: "#dbeafe",
      stroke: state.selectedId === el.key ? "#1d4ed8" : "#93c5fd",
      strokeWidth: state.selectedId === el.key ? 2 : 1,
      cornerRadius: 8,
      shadowEnabled: false,
    });
    group.add(bg);

    const header = new Konva.Rect({
      x: 0,
      y: 0,
      width: el.width,
      height: 28,
      fill: "#bfdbfe",
      stroke: "#93c5fd",
      strokeWidth: 1,
      cornerRadius: [8, 8, 0, 0],
    });
    group.add(header);

    group.add(
      new Konva.Text({
        x: 8,
        y: 6,
        width: el.width - 16,
        text: `${el.title}   [${isMatrixKind(el.kind) ? "tabela" : el.kind}]`,
        fontSize: 12,
        fill: "#0f172a",
        fontStyle: "bold",
      })
    );

    if (isMatrixKind(el.kind)) {
      ensureMatrixData(el);
      const rows = el.data.rows || [];
      const colsCount = rows.length ? Math.max(...rows.map((r) => (Array.isArray(r) ? r.length : 0))) : 0;
      group.add(
        new Konva.Rect({
          x: 8,
          y: 36,
          width: Math.max(80, el.width - 16),
          height: Math.max(40, el.height - 44),
          fill: "#eef2ff",
          stroke: "#c7d2fe",
          strokeWidth: 1,
          cornerRadius: 6,
        })
      );
      group.add(
        new Konva.Text({
          x: 14,
          y: 46,
          width: el.width - 28,
          text: `Tabela ${rows.length}x${colsCount}\nEdite via Inspector à direita`,
          fontSize: 12,
          fill: "#1e293b",
        })
      );
    } else {
      const layer = el.layer || {};
      const layerParts = [layer.setor, layer.bloco, layer.pavimento, layer.unidade].filter(Boolean);
      group.add(
        new Konva.Text({
          x: 8,
          y: 38,
          width: el.width - 16,
          text: `${el.semantica ? `Semântica: ${el.semantica}\n` : ""}${layerParts.length ? `Camadas: ${layerParts.join(" › ")}` : "Camadas não definidas"}`,
          fontSize: 12,
          fill: "#1e293b",
        })
      );
    }

    group.on("click tap", (evt) => {
      evt.cancelBubble = true;
      state.selectedId = el.key;
      tr.nodes([group]);
      updateInspector();
      stageState.stage && stageState.stage.batchDraw();
    });

    group.on("dragend", () => {
      el.x = snap(clamp(group.x(), 0, BOARD_WIDTH - el.width));
      el.y = snap(clamp(group.y(), 0, BOARD_HEIGHT - el.height));
      group.position({ x: el.x, y: el.y });
      updatePreview();
      markDirty();
    });

    group.on("transformend", () => {
      const sx = group.scaleX();
      const sy = group.scaleY();
      el.width = snap(clamp(group.width() * sx, MIN_W, 1200));
      el.height = snap(clamp(group.height() * sy, MIN_H, 1000));
      group.scale({ x: 1, y: 1 });
      group.width(el.width);
      group.height(el.height);
      group.findOne("Rect").width(el.width);
      updatePreview();
      markDirty();
      scheduleRender();
    });

    layer.add(group);
    if (state.selectedId === el.key) {
      tr.nodes([group]);
    }
  }

  function renderKonva() {
    if (!stageState.stage) initStage();
    if (!stageState.layer || !stageState.stage) return;
    const layer = stageState.layer;
    const tr = stageState.tr;
    layer.destroyChildren();
    state.elementos.forEach((el) => drawElement(el));
    layer.add(tr);
    stageState.stage.batchDraw();
    updateInspector();
    renderMiniMap();
  }

  function renderMiniMap() {
    if (!miniMap || !stageState.stage) return;
    const stage = stageState.stage;
    const w = miniMap.clientWidth || 180;
    const h = miniMap.clientHeight || 120;
    const sx = w / BOARD_WIDTH;
    const sy = h / BOARD_HEIGHT;
    const body = [];
    state.elementos.forEach((el) => {
      body.push(
        `<div class="po-minimap-el" style="left:${el.x * sx}px;top:${el.y * sy}px;width:${Math.max(2, el.width * sx)}px;height:${Math.max(2, el.height * sy)}px"></div>`
      );
    });
    const worldW = stage.width() / stage.scaleX();
    const worldH = stage.height() / stage.scaleY();
    const worldX = -stage.x() / stage.scaleX();
    const worldY = -stage.y() / stage.scaleY();
    body.push(
      `<div class="po-minimap-view" style="left:${worldX * sx}px;top:${worldY * sy}px;width:${Math.max(8, worldW * sx)}px;height:${Math.max(8, worldH * sy)}px"></div>`
    );
    miniMap.innerHTML = body.join("");
  }

  function fitView() {
    if (!stageState.stage) return;
    const stage = stageState.stage;
    if (!state.elementos.length) {
      stage.position({ x: 0, y: 0 });
      stage.scale({ x: 1, y: 1 });
      stage.batchDraw();
      renderMiniMap();
      return;
    }
    const minX = Math.min(...state.elementos.map((e) => e.x));
    const minY = Math.min(...state.elementos.map((e) => e.y));
    const maxX = Math.max(...state.elementos.map((e) => e.x + e.width));
    const maxY = Math.max(...state.elementos.map((e) => e.y + e.height));
    const boxW = Math.max(100, maxX - minX + 80);
    const boxH = Math.max(100, maxY - minY + 80);
    const scale = clamp(Math.min(stage.width() / boxW, stage.height() / boxH), 0.4, 1.2);
    stage.scale({ x: scale, y: scale });
    stage.position({
      x: -minX * scale + 40,
      y: -minY * scale + 40,
    });
    stage.batchDraw();
    renderMiniMap();
  }

  function updateInspector() {
    const selected = getSelected();
    const has = !!selected;
    if (inspectorEmpty) inspectorEmpty.classList.toggle("d-none", has);
    if (inspectorForm) inspectorForm.classList.toggle("d-none", !has);
    if (canvasQuickActions) canvasQuickActions.classList.toggle("d-none", !has);
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
    renderMatrixInspector(selected);
  }

  function renderMatrixInspector(selected) {
    if (!matrixGridEditor) return;
    if (!selected || !isMatrixKind(selected.kind)) {
      matrixGridEditor.innerHTML = "";
      return;
    }
    ensureMatrixData(selected);
    const rows = selected.data.rows || [];
    if (!rows.length) rows.push([""]);
    const colCount = Math.max(...rows.map((r) => (Array.isArray(r) ? r.length : 0)), 1);
    const header = Array.from({ length: colCount }, (_, i) => `<th>C${i + 1}</th>`).join("");
    const body = rows
      .map((row, rIdx) => {
        const cells = Array.from({ length: colCount }, (_, cIdx) => {
          const value = row[cIdx] ?? "";
          return `<td contenteditable="true" data-r="${rIdx}" data-c="${cIdx}">${String(value).replace(/</g, "&lt;")}</td>`;
        }).join("");
        return `<tr>${cells}</tr>`;
      })
      .join("");
    matrixGridEditor.innerHTML = `<table><thead><tr>${header}</tr></thead><tbody>${body}</tbody></table>`;
  }

  async function loadDetails() {
    hideAlert();
    const data = await requestJson(ctx.endpoints.detail, { credentials: "same-origin" });
    state.draft = data.draft || {};
    populateSemanticas(data.semanticas || []);
    if (Array.isArray(data.elementos) && data.elementos.length) {
      state.elementos = data.elementos.map((it, idx) => normalizeElement(it, idx));
    } else {
      const sections = (state.draft.layout && Array.isArray(state.draft.layout.sections)) ? state.draft.layout.sections : [];
      state.elementos = sections.map((it, idx) => normalizeElement(it, idx));
    }
    if (!state.selectedId && state.elementos[0]) state.selectedId = state.elementos[0].key;
    state.dirty = false;
    setSaveState("Sem alterações", "text-bg-light");
    renderKonva();
    fitView();
  }

  async function addSection() {
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
    const opts = options || {};
    hideAlert();
    setSaveState("Salvando...", "text-bg-info");
    const payload = { items: buildSyncPayload() };
    await requestJson(ctx.endpoints.syncElements, {
      method: "POST",
      credentials: "same-origin",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": ctx.csrfToken,
      },
      body: JSON.stringify(payload),
    });
    await requestJson(ctx.endpoints.saveDraft, {
      method: "POST",
      credentials: "same-origin",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": ctx.csrfToken,
      },
      body: JSON.stringify({ layout: state.draft.layout || {}, metadados: state.draft.metadados || {} }),
    });
    state.dirty = false;
    if (state.autoSaveTimer) {
      clearTimeout(state.autoSaveTimer);
      state.autoSaveTimer = null;
    }
    setSaveState("Salvo", "text-bg-success");
    if (!opts.silent) showAlert("Rascunho salvo com elementos estruturados.", "success");
  }

  async function publish() {
    hideAlert();
    await saveDraft();
    await requestJson(ctx.endpoints.publish, {
      method: "POST",
      credentials: "same-origin",
      headers: {
        "X-CSRFToken": ctx.csrfToken,
      },
    });
    showAlert("Versão publicada com sucesso.", "success");
    await loadDetails();
  }

  function applyInspectorChanges() {
    const selected = getSelected();
    if (!selected) return;
    selected.title = (insTitle && insTitle.value ? insTitle.value : selected.title || "").trim() || "Sem título";
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
    const selected = getSelected();
    if (!selected) return;
    const copy = JSON.parse(JSON.stringify(selected));
    copy.id = null;
    copy.key = uuidShort();
    copy.title = `${copy.title} (cópia)`;
    copy.x = snap(copy.x + GRID);
    copy.y = snap(copy.y + GRID);
    state.elementos.push(copy);
    state.selectedId = copy.key;
    updatePreview();
    markDirty();
    scheduleRender();
  }

  function removeSelectedSection() {
    const selected = getSelected();
    if (!selected) return;
    state.elementos = state.elementos.filter((it) => it.key !== selected.key);
    state.selectedId = state.elementos[0] ? state.elementos[0].key : null;
    updatePreview();
    markDirty();
    scheduleRender();
  }

  function addMatrixRow() {
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
    ensureMatrixData(selected);
    const cols = Math.max(2, (selected.data.rows[0] || []).length);
    selected.data.rows.push(Array.from({ length: cols }, () => ""));
    updatePreview();
    markDirty();
    scheduleRender();
  }

  function addMatrixCol() {
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
    ensureMatrixData(selected);
    selected.data.rows.forEach((row, idx) => row.push(idx === 0 ? `Coluna ${row.length + 1}` : ""));
    updatePreview();
    markDirty();
    scheduleRender();
  }

  if (btnAddSection) btnAddSection.addEventListener("click", () => addSection().catch((err) => showAlert(err.message, "danger")));
  if (btnQuickTable) btnQuickTable.addEventListener("click", () => addQuickSection("matrix_table", "Matriz de Controle").catch((err) => showAlert(err.message, "danger")));
  if (btnQuickBlock) btnQuickBlock.addEventListener("click", () => addQuickSection("list_table", "Bloco de Controle").catch((err) => showAlert(err.message, "danger")));
  if (btnQuickKpi) btnQuickKpi.addEventListener("click", () => addQuickSection("kpi_strip", "Faixa KPI").catch((err) => showAlert(err.message, "danger")));
  if (btnQuickDetail) btnQuickDetail.addEventListener("click", () => addQuickSection("detail_panel", "Detalhamento").catch((err) => showAlert(err.message, "danger")));
  if (btnFitView) btnFitView.addEventListener("click", fitView);
  if (btnToggleEdit) {
    btnToggleEdit.addEventListener("click", () => {
      state.editMode = !state.editMode;
      btnToggleEdit.textContent = `Modo edição: ${state.editMode ? "ON" : "OFF"}`;
      renderKonva();
    });
  }
  if (btnSaveDraft) btnSaveDraft.addEventListener("click", () => saveDraft().catch((err) => showAlert(err.message, "danger")));
  if (btnReload) btnReload.addEventListener("click", () => loadDetails().catch((err) => showAlert(err.message, "danger")));
  if (btnPublish) btnPublish.addEventListener("click", () => publish().catch((err) => showAlert(err.message, "danger")));
  if (btnApplyInspector) btnApplyInspector.addEventListener("click", applyInspectorChanges);
  if (btnDuplicateSection) btnDuplicateSection.addEventListener("click", duplicateSelectedSection);
  if (btnRemoveSection) btnRemoveSection.addEventListener("click", removeSelectedSection);
  if (btnQuickDuplicateSelected) btnQuickDuplicateSelected.addEventListener("click", duplicateSelectedSection);
  if (btnQuickDeleteSelected) btnQuickDeleteSelected.addEventListener("click", removeSelectedSection);
  if (btnAddRow) btnAddRow.addEventListener("click", addMatrixRow);
  if (btnAddCol) btnAddCol.addEventListener("click", addMatrixCol);
  if (miniMap) {
    miniMap.addEventListener("click", (event) => {
      if (!stageState.stage) return;
      const rect = miniMap.getBoundingClientRect();
      const mx = event.clientX - rect.left;
      const my = event.clientY - rect.top;
      const wx = (mx / rect.width) * BOARD_WIDTH;
      const wy = (my / rect.height) * BOARD_HEIGHT;
      const stage = stageState.stage;
      stage.position({
        x: -(wx * stage.scaleX()) + stage.width() / 2,
        y: -(wy * stage.scaleY()) + stage.height() / 2,
      });
      stage.batchDraw();
      renderMiniMap();
    });
  }
  if (matrixGridEditor) {
    matrixGridEditor.addEventListener(
      "blur",
      (event) => {
        const target = event.target;
        if (!(target instanceof HTMLElement) || target.tagName !== "TD") return;
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
      },
      true
    );
  }

  window.addEventListener("keydown", (event) => {
    const target = event.target;
    const isTyping =
      target instanceof HTMLElement &&
      (target.tagName === "INPUT" || target.tagName === "TEXTAREA" || target.isContentEditable);
    if (isTyping) return;

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
    if (event.key === "Delete") {
      const selected = getSelected();
      if (selected) removeSelectedSection();
    }
  });

  loadDetails().catch((err) => showAlert(err.message, "danger"));
})();

