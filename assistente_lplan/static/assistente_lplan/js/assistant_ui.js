(function () {
    const chat = document.getElementById("assistant-chat");
    const chatToolbar = document.getElementById("assistant-chat-toolbar");
    const backBtn = document.getElementById("assistant-back-btn");
    const form = document.getElementById("assistant-form");
    const input = document.getElementById("assistant-input");
    const loading = document.getElementById("assistant-loading");
    const historyList = document.getElementById("history-list");
    const dashboard = document.getElementById("assistant-dashboard");
    const app = document.getElementById("assistant-app");
    const maxHistoryItems = 5;

    const placeholders = [
        "Quais obras estão sem RDO esta semana?",
        "Pedidos parados há mais de 30 dias",
        "Quem tem mais restrições vencidas?",
        "Qual obra está mais crítica hoje?",
    ];
    let placeholderIdx = 0;
    if (input) {
        setInterval(() => {
            placeholderIdx = (placeholderIdx + 1) % placeholders.length;
            input.placeholder = placeholders[placeholderIdx];
        }, 4500);
    }

    if (!chat || !form || !input || !app) return;

    function enterChatMode() {
        app.classList.add("assistant-chat-active");
        if (dashboard) dashboard.hidden = true;
        chat.hidden = false;
        if (chatToolbar) chatToolbar.hidden = false;
    }

    function resetToDashboard() {
        app.classList.remove("assistant-chat-active");
        chat.innerHTML = "";
        chat.hidden = true;
        if (chatToolbar) chatToolbar.hidden = true;
        if (dashboard) dashboard.hidden = false;
        input.value = "";
        chat.scrollTop = 0;
    }

    function appendMessage(role, html) {
        enterChatMode();
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
                ${cards.map((c) => `
                    <div class="assistant-card">
                        <div class="title">${escapeHtml(c.title || "-")}</div>
                        <div class="value">${escapeHtml(c.value || "-")}</div>
                    </div>`).join("")}
            </div>`;
    }

    function renderTable(table) {
        const rows = table && Array.isArray(table.rows) ? table.rows : [];
        const columns = table && Array.isArray(table.columns) ? table.columns : [];
        if (!rows.length || !columns.length) return "";
        return `
            <div class="assistant-section-title">Detalhes</div>
            <div class="assistant-table-wrap">
                <table class="assistant-table">
                    ${table.caption ? `<caption>${escapeHtml(table.caption)}</caption>` : ""}
                    <thead><tr>${columns.map((c) => `<th>${escapeHtml(c)}</th>`).join("")}</tr></thead>
                    <tbody>
                        ${rows.map((row) => `
                            <tr>${columns.map((c) => `<td>${escapeHtml(row[c] ?? "-")}</td>`).join("")}</tr>
                        `).join("")}
                    </tbody>
                </table>
            </div>`;
    }

    function riskClass(level) {
        const n = String(level || "").toUpperCase();
        if (n === "ALTO") return "high";
        if (n === "MEDIO") return "medium";
        return "low";
    }

    function renderRadar(data) {
        if (data.radar_score == null) return "";
        const cls = riskClass(data.risk_level);
        const score = Number(data.radar_score) || 0;
        return `
            <div class="assistant-section-title">Radar de Obra</div>
            <div class="assistant-radar">
                <div class="assistant-radar-score">${score}</div>
                <span class="assistant-radar-pill ${cls}">${escapeHtml(data.risk_level || "N/A")}</span>
                <div class="assistant-radar-bar"><div class="assistant-radar-fill ${cls}" style="width:${Math.max(0, Math.min(score, 100))}%"></div></div>
                ${Array.isArray(data.causes) && data.causes.length
                    ? `<ul class="assistant-causes">${data.causes.map((c) => `<li>${escapeHtml(c)}</li>`).join("")}</ul>`
                    : ""}
            </div>`;
    }

    function renderAlerts(alerts) {
        if (!Array.isArray(alerts) || !alerts.length) return "";
        return alerts.map((a) => `
            <div style="margin-top:0.35rem;padding:0.4rem;border-left:3px solid ${
                a.level === "error" ? "#dc2626" : a.level === "warning" ? "#f59e0b" : "#2563eb"
            };font-size:0.8rem;">${escapeHtml(a.message || "")}</div>`).join("");
    }

    function renderActions(actions) {
        if (!Array.isArray(actions) || !actions.length) return "";
        return `
            <div class="assistant-section-title">Ações</div>
            <div class="assistant-actions">
                ${actions.map((a) => `<a href="${escapeHtml(a.url || "#")}" class="assistant-btn ${a.style === "primary" ? "primary" : ""}">${escapeHtml(a.label || "Abrir")}</a>`).join("")}
            </div>`;
    }

    function renderLinks(links) {
        if (!Array.isArray(links) || !links.length) return "";
        return `<div class="assistant-links">${links.map((l) => `<a href="${escapeHtml(l.url || "#")}" class="assistant-link">${escapeHtml(l.label || "")}</a>`).join("")}</div>`;
    }

    function renderSuggestedReplies(replies) {
        if (!Array.isArray(replies) || !replies.length) return "";
        return `
            <div class="assistant-section-title">Próximas perguntas</div>
            <div class="assistant-reply-chips">
                ${replies.map((text) => `<button type="button" class="assistant-reply-chip js-suggested-reply">${escapeHtml(text)}</button>`).join("")}
            </div>`;
    }

    function renderFeedback(payload) {
        const qid = payload.question_log_id || (payload.raw_data && payload.raw_data.question_log_id) || "";
        if (!qid) return "";
        return `
            <div class="assistant-feedback" data-question-log-id="${escapeHtml(qid)}">
                <span class="text-xs text-slate-500">Essa resposta ajudou?</span>
                <button type="button" class="assistant-feedback-btn js-feedback-good">👍</button>
                <button type="button" class="assistant-feedback-btn js-feedback-bad">👎</button>
            </div>`;
    }

    function renderResponse(payload) {
        return `
            <div class="font-semibold mb-1">Assistente LPLAN</div>
            <div>${escapeHtml(payload.summary || "Sem resposta.")}</div>
            ${renderBadges(payload.badges)}
            ${renderRadar(payload)}
            ${renderCards(payload.cards)}
            ${renderTable(payload.table)}
            ${renderAlerts(payload.alerts)}
            ${renderActions(payload.actions)}
            ${renderLinks(payload.links)}
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

    function appendToHistory(question) {
        if (!historyList) return;
        historyList.hidden = false;
        historyList.classList.remove("assistant-history--empty");
        const item = document.createElement("button");
        item.type = "button";
        item.className = "assistant-history-item js-ask";
        item.dataset.question = question;
        item.textContent = question;
        historyList.prepend(item);
        while (historyList.children.length > maxHistoryItems) {
            historyList.removeChild(historyList.lastChild);
        }
    }

    function askQuestion(question) {
        const q = (question || "").trim();
        if (!q) return;
        submitQuestion(q);
    }

    async function submitQuestion(question) {
        const q = (question || "").trim();
        if (!q) return;
        appendMessage("user", `<div>${escapeHtml(q)}</div>`);
        input.value = "";
        loading && loading.classList.add("show");
        try {
            const response = await fetch("/assistente/perguntar/", {
                method: "POST",
                headers: { "Content-Type": "application/json", "X-CSRFToken": getCsrfToken() },
                body: JSON.stringify({ pergunta: q }),
            });
            const data = await response.json();
            if (!response.ok) {
                appendMessage("assistant", `<div>${escapeHtml(data.error || "Erro ao consultar.")}</div>`);
                return;
            }
            appendMessage("assistant", renderResponse(data));
            appendToHistory(q);
        } catch (e) {
            appendMessage("assistant", `<div>Falha de rede ao consultar o assistente.</div>`);
        } finally {
            loading && loading.classList.remove("show");
        }
    }

    if (backBtn) {
        backBtn.addEventListener("click", resetToDashboard);
    }

    form.addEventListener("submit", function (e) {
        e.preventDefault();
        askQuestion(input.value);
    });

    document.addEventListener("click", function (e) {
        const askBtn = e.target.closest(".js-ask");
        if (askBtn && askBtn.dataset.question) {
            e.preventDefault();
            askQuestion(askBtn.dataset.question);
            return;
        }

        const replyBtn = e.target.closest(".js-suggested-reply");
        if (replyBtn) {
            e.preventDefault();
            askQuestion(replyBtn.textContent.trim());
        }
    });

    chat.addEventListener("click", async function (event) {
        const target = event.target.closest("button");
        if (!target) return;
        const block = target.closest(".assistant-feedback");
        if (!block) return;
        const qid = block.getAttribute("data-question-log-id");
        if (!qid) return;
        if (!target.classList.contains("js-feedback-good") && !target.classList.contains("js-feedback-bad")) return;
        const helpful = target.classList.contains("js-feedback-good");
        try {
            await fetch("/assistente/feedback/", {
                method: "POST",
                headers: { "Content-Type": "application/json", "X-CSRFToken": getCsrfToken() },
                body: JSON.stringify({ question_log_id: Number(qid), helpful: !!helpful }),
            });
        } catch (err) {
            /* ignore */
        }
    });
})();
