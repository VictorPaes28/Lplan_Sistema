(function () {
  const context = window.PO_CONTEXT || {};
  const tableBody = document.getElementById("poTableBody");
  const alertBox = document.getElementById("poAlert");
  const btnRefresh = document.getElementById("poRecarregar");
  const btnCreate = document.getElementById("poCriar");
  const inputName = document.getElementById("poNome");
  const selectType = document.getElementById("poTipo");
  let currentItems = [];

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
    return baseUrl.replace(/0\/?$/, `${ambienteId}/`);
  }

  async function requestJson(url, options) {
    const response = await fetch(url, options || {});
    const data = await response.json();
    if (!response.ok || data.success === false) {
      throw new Error(data.error || "Falha na requisição.");
    }
    return data;
  }

  function renderRows(items) {
    currentItems = Array.isArray(items) ? items.slice() : [];
    if (!tableBody) return;
    tableBody.innerHTML = "";
    if (!items || !items.length) {
      tableBody.innerHTML = '<tr><td colspan="5" class="text-muted">Sem ambientes para esta obra.</td></tr>';
      return;
    }
    items.forEach((item) => {
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td><strong>${item.nome || "-"}</strong></td>
        <td>${item.tipo || "-"}</td>
        <td>${item.versao_publicada ?? "-"}</td>
        <td>${item.versao_rascunho ?? "-"}</td>
        <td class="text-end">
          <div class="po-actions">
            <a class="btn btn-outline-secondary btn-sm" href="/engenharia/ferramenta/ambientes/${item.id}/">Editor</a>
            <button class="btn btn-outline-primary btn-sm" data-action="save" data-id="${item.id}">Salvar rascunho</button>
            <button class="btn btn-success btn-sm" data-action="publish" data-id="${item.id}">Publicar</button>
          </div>
        </td>
      `;
      tableBody.appendChild(tr);
    });
  }

  async function loadAmbientes() {
    hideAlert();
    const sep = context.endpoints.list.includes("?") ? "&" : "?";
    const url = `${context.endpoints.list}${sep}_ts=${Date.now()}`;
    const data = await requestJson(url, { credentials: "same-origin" });
    renderRows(data.items || []);
  }

  async function createAmbiente() {
    hideAlert();
    const payload = {
      nome: (inputName && inputName.value ? inputName.value : "").trim() || "Novo ambiente",
      tipo: selectType ? selectType.value : "mapa_controle",
    };
    const data = await requestJson(context.endpoints.create, {
      method: "POST",
      credentials: "same-origin",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": context.csrfToken,
      },
      body: JSON.stringify(payload),
    });
    if (inputName) inputName.value = "";
    if (data && data.item) {
      const next = [data.item, ...currentItems.filter((item) => item.id !== data.item.id)];
      renderRows(next);
    }
    showAlert("Ambiente criado com sucesso.", "success");
    loadAmbientes().catch(() => {});
  }

  async function saveDraft(ambienteId) {
    const url = replaceAmbienteId(context.endpoints.saveBase, ambienteId);
    await requestJson(url, {
      method: "POST",
      credentials: "same-origin",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": context.csrfToken,
      },
      body: JSON.stringify({ metadados: { source: "shell_mvp" } }),
    });
    showAlert("Rascunho salvo.", "success");
    await loadAmbientes();
  }

  async function publishAmbiente(ambienteId) {
    const url = replaceAmbienteId(context.endpoints.publishBase, ambienteId);
    await requestJson(url, {
      method: "POST",
      credentials: "same-origin",
      headers: {
        "X-CSRFToken": context.csrfToken,
      },
    });
    showAlert("Versão publicada.", "success");
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

  if (tableBody) {
    tableBody.addEventListener("click", (event) => {
      const target = event.target;
      if (!(target instanceof HTMLElement)) return;
      const action = target.getAttribute("data-action");
      const id = target.getAttribute("data-id");
      if (!action || !id) return;
      const ambienteId = Number(id);
      if (!Number.isFinite(ambienteId)) return;
      const run = action === "save" ? saveDraft(ambienteId) : publishAmbiente(ambienteId);
      run.catch((err) => showAlert(err.message, "danger"));
    });
  }

  try {
    const initial = JSON.parse(document.getElementById("poInitialAmbientes").textContent || "[]");
    renderRows(initial);
  } catch (err) {
    renderRows([]);
  }
  // Sempre sincroniza ao abrir a página para evitar inconsistências de cache HTML.
  loadAmbientes().catch((err) => showAlert(err.message, "danger"));
})();

