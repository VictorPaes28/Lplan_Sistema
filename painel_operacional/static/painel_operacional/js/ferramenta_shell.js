(function () {
  const context = window.PO_CONTEXT || {};
  const tableBody = document.getElementById("poTableBody");
  const alertBox = document.getElementById("poAlert");
  const btnRefresh = document.getElementById("poRecarregar");
  const btnCreate = document.getElementById("poCriar");
  const btnOpenCreateModal = document.getElementById("poOpenCreateModal");
  const inputName = document.getElementById("poNome");
  const selectType = document.getElementById("poTipo");
  const createModalEl = document.getElementById("poCreateModal");
  const createImportWrap = document.getElementById("poCreateImportWrap");
  const createImportFile = document.getElementById("poCreateImportFile");
  const createImportSheet = document.getElementById("poCreateImportSheet");
  const inputSearch = document.getElementById("poSearch");
  const countBadge = document.getElementById("poCountBadge");
  const updatedAt = document.getElementById("poUpdatedAt");
  const obraForm = document.getElementById("poObraForm");
  const overlay = document.getElementById("poPageOverlay");
  const table = document.querySelector(".po-table");
  let currentItems = [];
  let currentQuery = "";
  const createModal =
    createModalEl && window.bootstrap && window.bootstrap.Modal
      ? new window.bootstrap.Modal(createModalEl, { backdrop: true, keyboard: true })
      : null;

  function isMapaControleType(value) {
    return String(value || "").trim() === "mapa_controle";
  }

  function mapaControleAtivoNaObra(items) {
    return (items || []).find((item) => isMapaControleType(item.tipo));
  }

  function syncMapaControleCreateGuard(items) {
    const existente = mapaControleAtivoNaObra(items);
    const mapaOption = selectType
      ? Array.from(selectType.options).find((opt) => isMapaControleType(opt.value))
      : null;
    if (mapaOption) {
      mapaOption.disabled = !!existente;
      if (existente && isMapaControleType(selectType.value)) {
        const fallback = Array.from(selectType.options).find((opt) => !opt.disabled && !isMapaControleType(opt.value));
        if (fallback) selectType.value = fallback.value;
      }
    }
    if (btnOpenCreateModal) {
      btnOpenCreateModal.disabled = false;
    }
    if (existente && createModalEl) {
      createModalEl.dataset.mapaControleExistenteId = String(existente.id);
    } else if (createModalEl) {
      delete createModalEl.dataset.mapaControleExistenteId;
    }
  }

  function syncCreateModalContext() {
    syncMapaControleCreateGuard(currentItems);
    const showImport = isMapaControleType(selectType && selectType.value);
    if (createImportWrap) createImportWrap.classList.toggle("d-none", !showImport);
    if (!showImport && createImportFile) createImportFile.value = "";
    if (!showImport && createImportSheet) createImportSheet.value = "";
  }

  function buildImportedLayoutFromRows(baseLayout, rows, interpretationMeta) {
    const norm = (v) =>
      String(v || "")
        .normalize("NFD")
        .replace(/[\u0300-\u036f]/g, "")
        .toUpperCase()
        .trim();
    const layout = baseLayout && typeof baseLayout === "object" ? JSON.parse(JSON.stringify(baseLayout)) : {};
    const sections = Array.isArray(layout.sections) ? layout.sections : [];
    const header = Array.isArray(rows && rows[0]) ? rows[0] : [];
    const headerNorm = header.map((h) => norm(h));
    const layerTokenSet = new Set(["SETOR", "BLOCO", "PAVIMENTO", "PAV", "ANDAR", "NIVEL", "APTO", "UNIDADE", "LOCAL"]);
    const layerIdx = [];
    headerNorm.forEach((h, idx) => {
      if (!h) return;
      if (layerTokenSet.has(h) || h.startsWith("SETOR") || h.startsWith("BLOCO") || h.startsWith("PAV") || h.startsWith("APTO") || h.startsWith("UNIDADE")) {
        layerIdx.push(idx);
      }
    });
    const importMeta =
      interpretationMeta && typeof interpretationMeta === "object"
        ? JSON.parse(JSON.stringify(interpretationMeta))
        : {};
    let totalColumnIndex =
      Number.isInteger(importMeta.total_col_interpreted) && importMeta.total_col_interpreted >= 1
        ? importMeta.total_col_interpreted
        : -1;
    if (Number.isInteger(importMeta.total_col_source) && importMeta.total_col_source >= 1 && totalColumnIndex < 0) {
      totalColumnIndex = importMeta.total_col_source;
    }
    for (let i = headerNorm.length - 1; i >= 1; i -= 1) {
      const h = String(headerNorm[i] || "").trim();
      if (!h) continue;
      if (h === "TOTAL" || h === "TOTAL GERAL" || h.startsWith("TOTAL")) {
        if (totalColumnIndex < 0) totalColumnIndex = i;
        break;
      }
    }

    // Matriz única: preserva fielmente o output do parser.
    let matrix = sections.find((s) => s && (s.kind === "matrix_table" || s.kind === "table"));
    if (!matrix) {
      matrix = {
        id: `sec_${Math.random().toString(16).slice(2, 10)}`,
        title: "Matriz de Controle",
        kind: "matrix_table",
        x: 80,
        y: 80,
        width: 680,
        height: 420,
        layer: {},
        data: {},
      };
      sections.unshift(matrix);
    }
    matrix.data = matrix.data && typeof matrix.data === "object" ? matrix.data : {};
    const cols = Math.max(1, ...rows.map((r) => (Array.isArray(r) ? r.length : 0)));
    const rowsN = Math.max(1, rows.length);
    matrix.data.rows = rows;
    matrix.data.mapaControleTemplate = true;
    matrix.data.totalColumnIndex = totalColumnIndex >= 1 ? totalColumnIndex : null;
    matrix.data.importMeta = importMeta;
    matrix.data.headerBandCount = 1;
    matrix.data.totalsColumnAuto = false;
    matrix.data.totalsRowAuto = false;
    matrix.data.verticalHeaders = false;
    matrix.data.colWeights = null;
    matrix.data.rowWeights = null;
    matrix.width = Math.max(Number(matrix.width) || 0, Math.min(3000, 180 + cols * 28));
    matrix.height = Math.max(Number(matrix.height) || 0, Math.min(1500, 140 + rowsN * 26));
    layout.sections = sections;
    return layout;
  }

  async function importPlanilhaParaAmbiente(ambienteId) {
    if (!isMapaControleType(selectType && selectType.value)) return null;
    const file = createImportFile && createImportFile.files && createImportFile.files[0];
    if (!file) return null;
    const importUrl = replaceAmbienteId(context.endpoints.importMatrixBase, ambienteId);
    const detailUrl = replaceAmbienteId(context.endpoints.detailBase, ambienteId);
    const saveUrl = replaceAmbienteId(context.endpoints.saveBase, ambienteId);
    if (String(importUrl).includes("/ambientes/0/")) {
      throw new Error("Falha ao montar URL de importação (ID do ambiente não aplicado).");
    }

    const fd = new FormData();
    fd.append("arquivo", file);
    if (createImportSheet && createImportSheet.value.trim()) fd.append("sheet", createImportSheet.value.trim());
    fd.append("mode", "auto");

    const importData = await requestJson(importUrl, {
      method: "POST",
      credentials: "same-origin",
      body: fd,
    });
    const rows = Array.isArray(importData.rows) ? importData.rows : [];
    if (!rows.length) throw new Error("A planilha não trouxe linhas válidas para importar.");

    const detail = await requestJson(detailUrl, { credentials: "same-origin" });
    const versao = detail.versao || detail.draft || {};
    const interpretationMeta =
      importData && importData.interpretation_meta && typeof importData.interpretation_meta === "object"
        ? importData.interpretation_meta
        : {};
    const layoutNovo = buildImportedLayoutFromRows(versao.layout, rows, interpretationMeta);

    await requestJson(saveUrl, {
      method: "POST",
      credentials: "same-origin",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ layout: layoutNovo, metadados: { source: "shell_create_import" } }),
    });

    const cols = Math.max(0, ...rows.map((r) => (Array.isArray(r) ? r.length : 0)));
    return {
      rows: rows.length,
      cols,
      strategy: importData.strategy || "",
      sheet: (importData.read && importData.read.selected_sheet) || importData.sheet || "",
    };
  }

  function setTableLoading(isLoading) {
    if (!table) return;
    table.classList.toggle("po-table-loading", !!isLoading);
  }

  function setButtonLoading(button, isLoading, textLoading) {
    if (!(button instanceof HTMLButtonElement)) return;
    if (isLoading) {
      if (!button.dataset.poLabel) button.dataset.poLabel = button.innerHTML;
      button.disabled = true;
      button.innerHTML = `<span class="spinner-border spinner-border-sm me-1" aria-hidden="true"></span>${textLoading || "Carregando..."}`;
    } else {
      if (button.dataset.poLabel) button.innerHTML = button.dataset.poLabel;
      button.disabled = false;
    }
  }

  function showPageOverlay() {
    if (!overlay) return;
    overlay.classList.add("is-active");
  }

  window.PO_submitObra = function submitObra(form) {
    showPageOverlay();
    setTimeout(() => form.submit(), 120);
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

  function replaceAmbienteId(baseUrl, ambienteId) {
    return baseUrl.replace(/\/ambientes\/0\//, `/ambientes/${ambienteId}/`);
  }

  function normalizeCsrfToken(raw) {
    const token = String(raw || "").trim();
    if (!token) return "";
    const invalid = ["notprovided", "none", "null", "undefined"];
    if (invalid.includes(token.toLowerCase())) return "";
    return token;
  }

  function readCsrfTokenSync() {
    const fromContext = normalizeCsrfToken(context.csrfToken);
    if (fromContext) return fromContext;
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

  function formatTipo(tipo) {
    const raw = String(tipo || "").trim();
    if (!raw) return "-";
    return raw
      .replace(/_/g, " ")
      .replace(/\b\w/g, (c) => c.toUpperCase());
  }

  function formatRevisao(item) {
    const versao = item.versao_atual ?? item.versao_rascunho ?? "-";
    const updated = item.updated_at ? new Date(item.updated_at) : null;
    if (!(updated instanceof Date) || Number.isNaN(updated.getTime())) return `v${versao}`;
    const when = updated.toLocaleDateString("pt-BR", { day: "2-digit", month: "2-digit" });
    return `v${versao} • ${when}`;
  }

  function ambienteOpenHref(item) {
    const id = Number(item && item.id);
    if (!Number.isFinite(id) || id <= 0) return "#";
    return `/engenharia/ferramenta/ambientes/${id}/`;
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
      const isHtml = contentType.includes("text/html") || raw.trim().startsWith("<!DOCTYPE") || raw.trim().startsWith("<html");
      if (isHtml) {
        const lower = raw.toLowerCase();
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
      throw new Error("Resposta inválida do servidor (JSON malformado).");
    }
    if (!response.ok || data.success === false) {
      if (isLikelyCsrfFailure(response.status, data && (data.error || data.message || raw))) {
        if (csrfRetry < 1) {
          await ensureCsrfToken(true);
          return requestJson(url, { ...(options || {}), _csrfRetry: csrfRetry + 1 });
        }
      }
      throw new Error(data.error || `Falha na requisição (${response.status}).`);
    }
    return data;
  }

  function renderRows(items) {
    currentItems = Array.isArray(items) ? items.slice() : [];
    const q = String(currentQuery || "").trim().toLowerCase();
    const filtered = q
      ? currentItems.filter((item) => {
          const name = String(item.nome || "").toLowerCase();
          const type = String(item.tipo || "").toLowerCase();
          return name.includes(q) || type.includes(q);
        })
      : currentItems;
    if (countBadge) {
      countBadge.textContent = `${filtered.length} ambiente${filtered.length === 1 ? "" : "s"}`;
    }
    if (updatedAt) updatedAt.textContent = `Atualizado às ${new Date().toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" })}`;
    if (!tableBody) return;
    tableBody.innerHTML = "";
    if (!filtered.length) {
      const msg = q ? "Nenhum ambiente encontrado para o filtro informado." : "Sem ambientes para esta obra.";
      tableBody.innerHTML = `<tr><td colspan="4" class="text-muted">${msg}</td></tr>`;
      return;
    }
    filtered.forEach((item, idx) => {
      const tr = document.createElement("tr");
      tr.className = "po-row-enter";
      tr.style.animationDelay = `${Math.min(idx * 22, 220)}ms`;
      tr.innerHTML = `
        <td><strong>${item.nome || "-"}</strong></td>
        <td><span class="badge po-type-badge">${formatTipo(item.tipo)}</span></td>
        <td><span class="badge text-bg-light">${formatRevisao(item)}</span></td>
        <td class="text-end">
          <div class="po-actions">
            <a class="btn btn-primary btn-sm" href="${ambienteOpenHref(item)}"><i class="bi bi-pencil-square me-1"></i>Abrir</a>
            <button class="btn btn-outline-secondary btn-sm" data-action="save" data-id="${item.id}"><i class="bi bi-save me-1"></i>Salvar</button>
            <button type="button" class="btn btn-outline-danger btn-sm" data-action="delete" data-id="${item.id}" title="Remover da lista"><i class="bi bi-trash3 me-1"></i>Excluir</button>
          </div>
        </td>
      `;
      tableBody.appendChild(tr);
    });
    syncMapaControleCreateGuard(currentItems);
  }

  async function loadAmbientes() {
    hideAlert();
    setTableLoading(true);
    const sep = context.endpoints.list.includes("?") ? "&" : "?";
    const url = `${context.endpoints.list}${sep}_ts=${Date.now()}`;
    try {
      const data = await requestJson(url, { credentials: "same-origin" });
      const items = data.items || [];
      if (data.mapa_controle_ativo && !items.some((row) => Number(row.id) === Number(data.mapa_controle_ativo.id))) {
        items.unshift(data.mapa_controle_ativo);
      }
      renderRows(items);
    } finally {
      setTableLoading(false);
    }
  }

  async function createAmbiente() {
    hideAlert();
    const tipo = selectType ? selectType.value : "mapa_controle";
    const existente = mapaControleAtivoNaObra(currentItems);
    if (isMapaControleType(tipo) && existente) {
      showAlert(
        `Esta obra já possui o Mapa de Controle "${existente.nome || "ativo"}". Abra-o na lista ou exclua-o antes de criar outro.`,
        "warning",
      );
      return;
    }
    setButtonLoading(btnCreate, true, "Criando...");
    const payload = {
      nome: (inputName && inputName.value ? inputName.value : "").trim() || "Novo ambiente",
      tipo,
    };
    try {
      const data = await requestJson(context.endpoints.create, {
        method: "POST",
        credentials: "same-origin",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(payload),
      });
      if (inputName) inputName.value = "";
      syncCreateModalContext();
      let importInfo = null;
      if (data && data.item && data.item.id) {
        setButtonLoading(btnCreate, true, "Importando...");
        importInfo = await importPlanilhaParaAmbiente(Number(data.item.id));
      }
      if (createModal) createModal.hide();
      if (data && data.item) {
        const next = [data.item, ...currentItems.filter((item) => item.id !== data.item.id)];
        renderRows(next);
      }
      if (createImportFile) createImportFile.value = "";
      if (createImportSheet) createImportSheet.value = "";
      const importMsg = importInfo
        ? ` Importação aplicada (${importInfo.rows}x${importInfo.cols})${importInfo.sheet ? ` - aba ${importInfo.sheet}` : ""}${importInfo.strategy ? ` [${importInfo.strategy}]` : ""}.`
        : "";
      showAlert(`Ambiente criado com sucesso.${importMsg}`, "success");
      if (data && data.item && data.item.id && data.item.modo_editor === "mapa_dedicado") {
        window.location.href = `/engenharia/ferramenta/ambientes/${data.item.id}/`;
        return;
      }
      loadAmbientes().catch(() => {});
    } finally {
      setButtonLoading(btnCreate, false);
    }
  }

  async function saveDraft(ambienteId) {
    const url = replaceAmbienteId(context.endpoints.saveBase, ambienteId);
    await requestJson(url, {
      method: "POST",
      credentials: "same-origin",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ metadados: { source: "shell_mvp" } }),
    });
    showAlert("Dados salvos.", "success");
    await loadAmbientes();
  }

  async function deleteAmbiente(ambienteId) {
    const nome =
      (currentItems.find((row) => Number(row.id) === ambienteId) || {}).nome || "este ambiente";
    if (!window.confirm(`Excluir "${nome}"? Ele deixará de aparecer na lista nesta ferramenta.`)) {
      return;
    }
    const url = replaceAmbienteId(context.endpoints.deleteBase, ambienteId);
    await requestJson(url, {
      method: "POST",
      credentials: "same-origin",
      headers: {
        "Content-Type": "application/json",
      },
      body: "{}",
    });
    showAlert("Ambiente excluído.", "success");
    await loadAmbientes();
  }

  if (btnRefresh) {
    btnRefresh.addEventListener("click", () => {
      loadAmbientes().catch((err) => showAlert(err.message, "danger"));
    });
  }

  if (btnCreate) {
    btnCreate.addEventListener("click", () => {
      createAmbiente().catch((err) => showAlert(err.message, "danger"));
    });
  }
  if (btnOpenCreateModal) {
    btnOpenCreateModal.addEventListener("click", () => {
      hideAlert();
      syncCreateModalContext();
      if (createModal) {
        createModal.show();
        setTimeout(() => {
          if (inputName) inputName.focus();
        }, 180);
      }
    });
  }
  if (selectType) {
    selectType.addEventListener("change", syncCreateModalContext);
  }
  if (createModalEl) {
    createModalEl.addEventListener("shown.bs.modal", () => {
      if (inputName) inputName.focus();
    });
  }
  if (inputName) {
    inputName.addEventListener("keydown", (event) => {
      if (event.key !== "Enter") return;
      event.preventDefault();
      createAmbiente().catch((err) => showAlert(err.message, "danger"));
    });
  }
  if (inputSearch) {
    inputSearch.addEventListener("input", () => {
      currentQuery = inputSearch.value || "";
      renderRows(currentItems);
    });
  }

  if (tableBody) {
    tableBody.addEventListener("click", (event) => {
      const target = event.target;
      if (!(target instanceof HTMLElement)) return;
      const actionBtn = target.closest("button[data-action]");
      if (!actionBtn) return;
      const action = actionBtn.getAttribute("data-action");
      const id = actionBtn.getAttribute("data-id");
      if (!action || !id) return;
      const ambienteId = Number(id);
      if (!Number.isFinite(ambienteId)) return;
      let run;
      if (action === "save") {
        setButtonLoading(actionBtn, true, "Salvando...");
        run = saveDraft(ambienteId).finally(() => setButtonLoading(actionBtn, false));
      } else if (action === "delete") {
        setButtonLoading(actionBtn, true, "Excluindo...");
        run = deleteAmbiente(ambienteId).finally(() => setButtonLoading(actionBtn, false));
      }
      else return;
      run.catch((err) => showAlert(err.message, "danger"));
    });
  }

  try {
    const initial = JSON.parse(document.getElementById("poInitialAmbientes").textContent || "[]");
    renderRows(initial);
  } catch (err) {
    renderRows([]);
  }
  syncCreateModalContext();
  // Sempre sincroniza ao abrir a página para evitar inconsistências de cache HTML.
  loadAmbientes().catch((err) => showAlert(err.message, "danger"));
})();

