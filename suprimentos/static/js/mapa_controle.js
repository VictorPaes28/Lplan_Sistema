(function () {
    "use strict";

    const initialEl = document.getElementById("mapa-controle-inicial");
    const initial = initialEl ? JSON.parse(initialEl.textContent || "{}") : {};

    const fields = {
        obra: document.getElementById("filtro-obra"),
        categoria: document.getElementById("filtro-categoria"),
        local: document.getElementById("filtro-local"),
        prioridade: document.getElementById("filtro-prioridade"),
        status: document.getElementById("filtro-status"),
        search: document.getElementById("filtro-search"),
    };

    const kpiContainer = document.getElementById("kpi-container");
    const rankingLocais = document.getElementById("ranking-locais");
    const rankingCategorias = document.getElementById("ranking-categorias");
    const rankingFornecedores = document.getElementById("ranking-fornecedores");
    const quemCobrar = document.getElementById("quem-cobrar");
    const itensBody = document.getElementById("itens-body");
    const detalhesSection = document.getElementById("controle-detalhes");
    const toggleDetalhesBtn = document.getElementById("btn-toggle-detalhes");
    const lastUpdateEl = document.getElementById("controle-last-update");

    const escapeHtml = (text) =>
        String(text || "")
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#039;");

    function getParams() {
        const params = new URLSearchParams();
        if (fields.obra && fields.obra.value) params.set("obra", fields.obra.value);
        if (fields.categoria && fields.categoria.value) params.set("categoria", fields.categoria.value);
        if (fields.local && fields.local.value) params.set("local", fields.local.value);
        if (fields.prioridade && fields.prioridade.value) params.set("prioridade", fields.prioridade.value);
        if (fields.status && fields.status.value) params.set("status", fields.status.value);
        if (fields.search && fields.search.value.trim()) params.set("search", fields.search.value.trim());
        params.set("limit", "300");
        return params;
    }

    function setOptions(selectEl, options, selectedValue) {
        if (!selectEl) return;
        const current = selectedValue !== undefined ? selectedValue : selectEl.value;
        const base = selectEl.querySelector("option") ? selectEl.querySelector("option").outerHTML : "";
        let html = base;
        options.forEach((opt) => {
            const id = opt.id !== undefined ? opt.id : opt.value;
            const label = opt.label !== undefined ? opt.label : opt.nome;
            html += `<option value="${escapeHtml(id)}">${escapeHtml(label)}</option>`;
        });
        selectEl.innerHTML = html;
        if (current !== undefined && current !== null) {
            selectEl.value = String(current);
        }
    }

    function fmtNumber(value) {
        return Number(value || 0).toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    }

    function setLoadingState(message) {
        itensBody.innerHTML = `<tr class="controle-loading-row"><td colspan="13">${escapeHtml(message || "Carregando...")}</td></tr>`;
    }

    function setErrorState(message) {
        itensBody.innerHTML = `<tr class="controle-error-row"><td colspan="13">${escapeHtml(message || "Erro ao carregar o mapa de controle.")}</td></tr>`;
    }

    function setEmptyState(message) {
        itensBody.innerHTML = `<tr class="controle-empty-row"><td colspan="13">${escapeHtml(message || "Nenhum item encontrado para os filtros atuais.")}</td></tr>`;
    }

    function updateLastRefreshLabel() {
        if (!lastUpdateEl) return;
        const now = new Date();
        lastUpdateEl.textContent = `Atualizado às ${now.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" })}`;
    }

    function renderKpis(kpis) {
        const cards = [
            { label: "Total", value: kpis.total_itens || 0, icon: "bi-list-ul", className: "kpi-total" },
            { label: "Sem SC", value: kpis.sem_sc || 0, icon: "bi-file-earmark-minus", className: "kpi-solicitados" },
            { label: "Sem PC", value: kpis.sem_pc || 0, icon: "bi-cart-x", className: "kpi-compra" },
            { label: "Sem Entrega", value: kpis.sem_entrega || 0, icon: "bi-truck", className: "kpi-compra" },
            { label: "Sem Alocação", value: kpis.sem_alocacao || 0, icon: "bi-box-seam", className: "kpi-parciais" },
            { label: "Atrasados", value: kpis.atrasados || 0, icon: "bi-exclamation-triangle-fill", className: "kpi-atrasados text-danger" },
            { label: "Alocação Média", value: `${Number(kpis.percentual_medio_alocacao || 0).toFixed(2)}%`, icon: "bi-speedometer2", className: "kpi-entregues text-success" },
        ];
        kpiContainer.innerHTML = cards
            .map(
                (c) => `
                <div class="kpi-card ${escapeHtml(c.className)}">
                    <div class="kpi-icon"><i class="bi ${escapeHtml(c.icon)}"></i></div>
                    <div class="kpi-content">
                        <div class="kpi-valor">${escapeHtml(c.value)}</div>
                        <div class="kpi-label">${escapeHtml(c.label)}</div>
                    </div>
                </div>
            `
            )
            .join("");
    }

    function renderList(target, pairs) {
        target.innerHTML = (pairs || [])
            .map(
                (item) => `
                <li>
                    <span>${escapeHtml(item[0])}</span>
                    <strong>${escapeHtml(item[1])}</strong>
                </li>
            `
            )
            .join("");
        if (!target.innerHTML) target.innerHTML = "<li><span>Sem dados</span><strong>0</strong></li>";
    }

    function groupedByCategory(items) {
        const groups = {};
        (items || []).forEach((item) => {
            const category = item.categoria || "A CLASSIFICAR";
            if (!groups[category]) groups[category] = [];
            groups[category].push(item);
        });
        return Object.keys(groups)
            .sort((a, b) => a.localeCompare(b, "pt-BR"))
            .map((name) => ({ name, items: groups[name] }));
    }

    function renderItems(items) {
        if (!items || !items.length) {
            setEmptyState("Nenhum item encontrado para os filtros atuais.");
            return;
        }

        const rows = [];
        groupedByCategory(items).forEach((group) => {
            rows.push(`
                <tr class="categoria-header">
                    <td colspan="13">${escapeHtml(group.name)} (${group.items.length} itens)</td>
                </tr>
            `);
            group.items.forEach((item) => {
                const atrasoBadge = item.atrasado ? '<span class="badge bg-danger ms-1">Atrasado</span>' : "";
                rows.push(`
                    <tr class="linha-item-mapa ${escapeHtml(item.status_css || "")}">
                        <td>
                            <div><strong>${escapeHtml(item.insumo_descricao)}</strong> ${atrasoBadge}</div>
                            <small class="text-muted">${escapeHtml(item.insumo_codigo)}</small>
                        </td>
                        <td>${escapeHtml(item.local)}</td>
                        <td>${escapeHtml(item.responsavel || "-")}</td>
                        <td>${escapeHtml(item.numero_sc)}</td>
                        <td>${escapeHtml(item.numero_pc)}</td>
                        <td>${escapeHtml(item.fornecedor || "-")}</td>
                        <td><strong>${escapeHtml(item.quem_cobrar)}</strong></td>
                        <td>${fmtNumber(item.qtd_planejada)}</td>
                        <td>${fmtNumber(item.qtd_recebida_obra)}</td>
                        <td>${fmtNumber(item.qtd_alocada_local)}</td>
                        <td>${fmtNumber(item.saldo_pendente_alocacao)}</td>
                        <td>${escapeHtml(item.percentual_alocado)}%</td>
                        <td class="status-cell ${escapeHtml(item.status_css || "")}"><span class="status-pill">${escapeHtml(item.status_etapa || "")}</span></td>
                    </tr>
                `);
            });
        });

        itensBody.innerHTML = rows.join("");
    }

    async function fetchJson(url) {
        const response = await fetch(url, { headers: { "X-Requested-With": "XMLHttpRequest" } });
        if (!response.ok) throw new Error("Falha ao carregar dados.");
        return response.json();
    }

    async function refresh() {
        if (!fields.obra || !fields.obra.value) {
            setEmptyState("Selecione uma obra para visualizar as pendências.");
            kpiContainer.innerHTML = "";
            return;
        }

        setLoadingState("Atualizando painel de controle...");
        const params = getParams();
        const query = params.toString();
        const [summaryResp, itemsResp] = await Promise.all([
            fetchJson(`/api/internal/mapa-controle/summary?${query}`),
            fetchJson(`/api/internal/mapa-controle/items?${query}`),
        ]);

        const summary = summaryResp.data || {};
        const itemsPayload = itemsResp.data || {};
        const filtros = summary.filtros || {};
        const options = filtros.options || {};
        const values = filtros.values || {};

        setOptions(fields.categoria, (options.categorias || []).map((c) => ({ id: c, label: c })), values.categoria);
        setOptions(fields.local, options.locais || [], values.local_id);
        setOptions(fields.prioridade, options.prioridades || [], values.prioridade);
        setOptions(fields.status, options.status || [], values.status);

        renderKpis(summary.kpis || {});
        renderList(rankingLocais, (summary.ranking || {}).locais || []);
        renderList(rankingCategorias, (summary.ranking || {}).categorias || []);
        renderList(rankingFornecedores, (summary.ranking || {}).fornecedores || []);
        renderList(quemCobrar, summary.quem_cobrar || []);
        renderItems(itemsPayload.items || []);
        updateLastRefreshLabel();
        if (fields.obra && fields.obra.value) {
            const btnMapa = document.getElementById("btn-abrir-mapa");
            if (btnMapa) btnMapa.href = `/engenharia/mapa/?obra=${encodeURIComponent(fields.obra.value)}`;
        }
    }

    function applyInitial() {
        if (!initial || !initial.filtros) return;
        const values = initial.filtros.values || {};
        if (fields.search && values.search) fields.search.value = values.search;
        setOptions(fields.categoria, (initial.filtros.options.categorias || []).map((c) => ({ id: c, label: c })), values.categoria);
        setOptions(fields.local, initial.filtros.options.locais || [], values.local_id);
        setOptions(fields.prioridade, initial.filtros.options.prioridades || [], values.prioridade);
        setOptions(fields.status, initial.filtros.options.status || [], values.status);
        renderKpis(initial.kpis || {});
        renderList(rankingLocais, (initial.ranking || {}).locais || []);
        renderList(rankingCategorias, (initial.ranking || {}).categorias || []);
        renderList(rankingFornecedores, (initial.ranking || {}).fornecedores || []);
        renderList(quemCobrar, initial.quem_cobrar || []);
    }

    let searchTimer = null;
    function bindEvents() {
        ["obra", "categoria", "local", "prioridade", "status"].forEach((name) => {
            const el = fields[name];
            if (!el) return;
            el.addEventListener("change", () => {
                refresh().catch(console.error);
            });
        });

        if (fields.search) {
            fields.search.addEventListener("input", () => {
                clearTimeout(searchTimer);
                searchTimer = setTimeout(() => {
                    refresh().catch(console.error);
                }, 350);
            });
        }

        if (toggleDetalhesBtn && detalhesSection) {
            toggleDetalhesBtn.addEventListener("click", () => {
                const hidden = detalhesSection.classList.toggle("d-none");
                toggleDetalhesBtn.textContent = hidden ? "Ver detalhes" : "Ocultar detalhes";
            });
        }
    }

    applyInitial();
    bindEvents();
    refresh().catch(() => {
        setErrorState("Erro ao carregar o mapa de controle.");
    });
})();
