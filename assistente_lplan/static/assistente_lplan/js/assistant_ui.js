(function () {
    const chat = document.getElementById("assistant-chat");
    const form = document.getElementById("assistant-form");
    const input = document.getElementById("assistant-input");
    const loading = document.getElementById("assistant-loading");
    const historyList = document.getElementById("history-list");
    const app = document.getElementById("assistant-app");
    const maxHistoryItems = Number.parseInt(historyList?.dataset?.historyLimit || "20", 10) || 20;
    const rawPid = app?.dataset?.selectedProjectId;
    const selectedProjectId =
        rawPid && String(rawPid).trim() !== "" ? Number.parseInt(String(rawPid), 10) : null;

    if (!chat || !form || !input) return;

    function appendMessage(role, html) {
        const node = document.createElement("div");
        node.className = `assistant-msg ${role}`;
        node.innerHTML = html;
        chat.appendChild(node);
        chat.scrollTop = chat.scrollHeight;
    }

    function escapeHtml(value) {
        const text = String(value == null ? "" : value);
        return text
            .replaceAll("&", "&amp;")
            .replaceAll("<", "&lt;")
            .replaceAll(">", "&gt;")
            .replaceAll('"', "&quot;")
            .replaceAll("'", "&#39;");
    }

    function renderBadges(badges) {
        if (!Array.isArray(badges) || !badges.length) return "";
        return `<div class="assistant-badges">${badges.map((b) => `<span class="assistant-badge">${escapeHtml(b)}</span>`).join("")}</div>`;
    }

    function renderCards(cards) {
        if (!Array.isArray(cards) || !cards.length) return "";
        return `
            <div class="assistant-section-title">Indicadores</div>
            <div class="assistant-cards">
                ${cards
                    .map(
                        (c) => `
                    <div class="assistant-card">
                        <div class="title">${escapeHtml(c.title || "-")}</div>
                        <div class="value">${escapeHtml(c.value || "-")}</div>
                    </div>
                `
                    )
                    .join("")}
            </div>
        `;
    }

    function renderTable(table) {
        if (!table || !Array.isArray(table.columns) || !Array.isArray(table.rows) || !table.columns.length) return "";
        return `
            <div class="assistant-section-title">Tabela</div>
            <div class="assistant-table-wrap">
                <table class="assistant-table">
                    ${table.caption ? `<caption>${escapeHtml(table.caption)}</caption>` : ""}
                    <thead>
                        <tr>${table.columns.map((c) => `<th>${escapeHtml(c)}</th>`).join("")}</tr>
                    </thead>
                    <tbody>
                        ${table.rows
                            .map(
                                (row) => `
                            <tr>${table.columns.map((c) => `<td>${escapeHtml(row[c] ?? "-")}</td>`).join("")}</tr>
                        `
                            )
                            .join("")}
                    </tbody>
                </table>
            </div>
        `;
    }

    function riskClass(level) {
        const normalized = String(level || "").toUpperCase();
        if (normalized === "ALTO") return "high";
        if (normalized === "MEDIO") return "medium";
        return "low";
    }

    function trendSymbol(trend) {
        const normalized = String(trend || "").toLowerCase();
        if (normalized.includes("pior")) return "↑";
        if (normalized.includes("melhor")) return "↓";
        return "→";
    }

    function renderRadar(data) {
        if (data.radar_score == null) return "";
        const cls = riskClass(data.risk_level);
        const score = Number(data.radar_score) || 0;
        return `
            <div class="assistant-section-title">Radar de Obra</div>
            <div class="assistant-radar">
                <div class="assistant-radar-top">
                    <div class="assistant-radar-score">${score}</div>
                    <div class="assistant-radar-meta">
                        <span class="assistant-radar-pill ${cls}">${escapeHtml(data.risk_level || "N/A")}</span>
                        <span class="assistant-radar-pill trend">${trendSymbol(data.trend)} ${escapeHtml(data.trend || "Estavel")}</span>
                    </div>
                </div>
                <div class="assistant-radar-bar">
                    <div class="assistant-radar-fill ${cls}" style="width:${Math.max(0, Math.min(score, 100))}%"></div>
                </div>
                ${Array.isArray(data.causes) && data.causes.length
                    ? `<ul class="assistant-causes">${data.causes.map((c) => `<li>${escapeHtml(c)}</li>`).join("")}</ul>`
                    : ""}
                ${
                    data.recommended_action && data.recommended_action.label
                        ? `
                    <div class="assistant-recommended">
                        <div class="assistant-recommended-title">Acao recomendada</div>
                        <div class="assistant-recommended-label">${escapeHtml(data.recommended_action.label)}</div>
                    </div>
                `
                        : ""
                }
            </div>
        `;
    }

    function renderTimeline(timeline) {
        if (!Array.isArray(timeline) || !timeline.length) return "";
        return `
            <div class="assistant-section-title">Linha do tempo</div>
            <div class="assistant-timeline">
                ${timeline
                    .map(
                        (item) => `
                    <div class="assistant-timeline-item">
                        <span class="assistant-timeline-dot"></span>
                        <div class="assistant-timeline-text">
                            <strong>${escapeHtml(item.date || "-")}</strong> - ${escapeHtml(item.label || "")}: ${escapeHtml(
                            item.value || "-"
                        )}
                        </div>
                    </div>
                `
                    )
                    .join("")}
            </div>
        `;
    }

    function renderSuggestedReplies(replies) {
        if (!Array.isArray(replies) || !replies.length) return "";
        return `
            <div class="assistant-section-title">Respostas rapidas sugeridas</div>
            <div class="assistant-actions" style="flex-direction:column;align-items:stretch;">
                ${replies
                    .map(
                        (text) => `
                    <button type="button" class="assistant-btn text-left js-suggested-reply" style="width:100%;white-space:normal;">
                        ${escapeHtml(text)}
                    </button>
                `
                    )
                    .join("")}
            </div>
        `;
    }

    function renderAlerts(alerts) {
        if (!Array.isArray(alerts) || !alerts.length) return "";
        return `
            <div class="assistant-section-title">Alertas</div>
            ${alerts
                .map(
                    (a) => `
                <div class="assistant-msg assistant" style="margin:0; border-left:4px solid ${
                    a.level === "error" ? "#dc2626" : a.level === "warning" ? "#f59e0b" : "#2563eb"
                }">
                    ${escapeHtml(a.message || "")}
                </div>
            `
                )
                .join("")}
        `;
    }

    function renderFeedback(payload) {
        const qid = payload.question_log_id || (payload.raw_data && payload.raw_data.question_log_id) || "";
        if (!qid) return "";
        return `
            <div class="assistant-feedback" data-question-log-id="${escapeHtml(qid)}">
                <div class="assistant-feedback-actions">
                    <span class="text-slate-500 text-xs">Essa resposta ajudou?</span>
                    <button type="button" class="assistant-feedback-btn good js-feedback-good">👍 Sim</button>
                    <button type="button" class="assistant-feedback-btn bad js-feedback-bad">👎 Não</button>
                    <button type="button" class="assistant-feedback-btn js-feedback-open">Corrigir intenção</button>
                </div>
                <div class="assistant-feedback-form js-feedback-form">
                    <input class="assistant-feedback-input js-correct-intent" placeholder="Intenção correta (ex.: resumo_obra)">
                    <input class="assistant-feedback-input js-correct-obra" placeholder="Obra correta (opcional)">
                    <input class="assistant-feedback-input js-correct-insumo" placeholder="Insumo correto (opcional)">
                    <input class="assistant-feedback-input js-correct-usuario" placeholder="Usuário correto (opcional)">
                    <textarea class="assistant-feedback-input assistant-feedback-note js-correct-note" placeholder="Observação (opcional)"></textarea>
                    <button type="button" class="assistant-feedback-btn js-feedback-send">Enviar correção</button>
                </div>
                <div class="assistant-feedback-status js-feedback-status"></div>
            </div>
        `;
    }

    function renderResponse(payload) {
        return `
            <div class="font-semibold mb-1">Assistente LPLAN</div>
            <div>${escapeHtml(payload.summary || "Sem resposta.")}</div>
            ${renderBadges(payload.badges)}
            ${renderRadar(payload)}
            ${renderCards(payload.cards)}
            ${renderTable(payload.table)}
            ${renderTimeline(payload.timeline)}
            ${renderAlerts(payload.alerts)}
            ${renderSuggestedReplies(payload.suggested_replies)}
            ${renderFeedback(payload)}
        `;
    }

    function getCsrfToken() {
        const inputCsrf = form.querySelector("input[name='csrfmiddlewaretoken']");
        if (inputCsrf && inputCsrf.value) return inputCsrf.value;
        const meta = document.querySelector("meta[name='csrf-token']");
        return meta ? meta.getAttribute("content") : "";
    }

    function appendToHistory(question, summary) {
        if (!historyList) return;
        const empty = historyList.querySelector(".text-slate-500.text-sm");
        if (empty) empty.remove();
        const item = document.createElement("div");
        item.className = "p-2 rounded-lg border border-slate-200 bg-slate-50";
        item.innerHTML = `<div class="font-medium text-slate-700">${escapeHtml(question)}</div><div class="text-slate-500 text-xs">${escapeHtml(
            summary || ""
        )}</div>`;
        historyList.prepend(item);
        while (historyList.children.length > maxHistoryItems) historyList.removeChild(historyList.lastChild);
    }

    form.addEventListener("submit", async function (event) {
        event.preventDefault();
        const question = (input.value || "").trim();
        if (!question) return;
        appendMessage("user", `<div>${escapeHtml(question)}</div>`);
        input.value = "";
        loading && loading.classList.add("show");

        try {
            const payload = { pergunta: question };
            if (selectedProjectId != null && !Number.isNaN(selectedProjectId)) {
                payload.contexto = { selected_project_id: selectedProjectId };
            }
            const response = await fetch("/assistente/perguntar/", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "X-CSRFToken": getCsrfToken(),
                },
                body: JSON.stringify(payload),
            });
            const payload = await response.json();
            appendMessage("assistant", renderResponse(payload));
            appendToHistory(question, payload.summary || "");
        } catch (error) {
            appendMessage("assistant", `<div>Falha de rede ao consultar o assistente.</div>`);
        } finally {
            loading && loading.classList.remove("show");
        }
    });

    async function sendFeedback(container, helpful, correctionPayload = null) {
        const questionLogId = container.getAttribute("data-question-log-id");
        const statusNode = container.querySelector(".js-feedback-status");
        if (!questionLogId) return;
        statusNode.textContent = "Enviando feedback...";

        const body = {
            question_log_id: Number(questionLogId),
            helpful: !!helpful,
            corrected_intent: "",
            corrected_entities: {},
            note: "",
        };
        if (correctionPayload) {
            body.corrected_intent = correctionPayload.corrected_intent || "";
            body.corrected_entities = correctionPayload.corrected_entities || {};
            body.note = correctionPayload.note || "";
        }

        try {
            const response = await fetch("/assistente/feedback/", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "X-CSRFToken": getCsrfToken(),
                },
                body: JSON.stringify(body),
            });
            const payload = await response.json();
            if (!response.ok) {
                statusNode.textContent = payload.error || "Falha ao enviar feedback.";
                return;
            }
            statusNode.textContent = payload.message || "Feedback registrado.";
        } catch (error) {
            statusNode.textContent = "Erro de rede ao enviar feedback.";
        }
    }

    chat.addEventListener("click", async function (event) {
        const target = event.target.closest("button");
        if (!target) return;
        const block = target.closest(".assistant-feedback");
        if (!block) return;

        if (target.classList.contains("js-feedback-good")) {
            await sendFeedback(block, true);
            return;
        }
        if (target.classList.contains("js-feedback-bad")) {
            await sendFeedback(block, false);
            return;
        }
        if (target.classList.contains("js-feedback-open")) {
            const formNode = block.querySelector(".js-feedback-form");
            if (formNode) formNode.classList.toggle("show");
            return;
        }
        if (target.classList.contains("js-feedback-send")) {
            const corrected_intent = (block.querySelector(".js-correct-intent")?.value || "").trim();
            const obra = (block.querySelector(".js-correct-obra")?.value || "").trim();
            const insumo = (block.querySelector(".js-correct-insumo")?.value || "").trim();
            const usuario = (block.querySelector(".js-correct-usuario")?.value || "").trim();
            const note = (block.querySelector(".js-correct-note")?.value || "").trim();
            const corrected_entities = {};
            if (obra) corrected_entities.obra = obra;
            if (insumo) corrected_entities.insumo = insumo;
            if (usuario) corrected_entities.usuario = usuario;
            await sendFeedback(block, false, { corrected_intent, corrected_entities, note });
        }
    });

    document.querySelectorAll(".js-suggested-question").forEach((button) => {
        button.addEventListener("click", function () {
            input.value = button.textContent.trim();
            input.focus();
        });
    });

    chat.addEventListener("click", function (event) {
        const btn = event.target.closest(".js-suggested-reply");
        if (!btn) return;
        input.value = btn.textContent.trim();
        input.focus();
        form.requestSubmit();
    });
})();

