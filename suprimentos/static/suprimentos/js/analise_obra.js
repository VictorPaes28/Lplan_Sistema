/**
 * BI da Obra — lazy loading das seções pesadas via API interna.
 */
(function () {
  "use strict";

  var NAV_SVG =
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="9 18 15 12 9 6"/></svg>';

  function esc(s) {
    if (s == null) return "";
    return String(s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function num(v) {
    var n = parseFloat(v);
    return isFinite(n) ? n : 0;
  }

  function formatBrl(v) {
    return num(v).toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  }

  function pctClass(p) {
    if (p < 30) return "red";
    if (p < 60) return "yellow";
    if (p < 80) return "blue";
    return "green";
  }

  function apiUrl(el) {
    var base = window.__ANALISE_API_URL__ || "/api/internal/analise-obra/";
    var qp = new URLSearchParams(window.location.search);
    qp.set("obra", el.dataset.obra || "");
    qp.set("secao", el.dataset.secao || "");
    if (el.dataset.periodoInicio) qp.set("data_inicio", el.dataset.periodoInicio);
    if (el.dataset.periodoFim) qp.set("data_fim", el.dataset.periodoFim);
    return base.replace(/\/?$/, "/") + "?" + qp.toString();
  }

  function renderGestcontroll(g) {
    if (!g) return '<p class="analise-loading-skeleton">Sem dados de GestControll.</p>';
    var kpis = g.kpis || {};
    var obraQ = g.gestao_obra_id ? "&obra=" + encodeURIComponent(g.gestao_obra_id) : "";
    var repHtml = "";
    var tipos = kpis.reprovados_por_tipo || {};
    Object.keys(tipos).forEach(function (k) {
      repHtml += '<div class="chip chip-red">' + esc(k) + " · " + esc(tipos[k]) + "</div>";
    });
    if (!repHtml) repHtml = '<div class="chip chip-gray">Nenhum</div>';

    var alcHtml = "";
    (kpis.alcadas_detalhes || []).forEach(function (a, i) {
      alcHtml +=
        '<div class="chip chip-' +
        (i === 0 ? "red" : "yellow") +
        '">' +
        esc(a.nome) +
        " · " +
        esc(a.count) +
        "</div>";
    });
    if (!alcHtml) alcHtml = '<div class="chip chip-gray">—</div>';

    var apr = num(kpis.aprovados_count);
    var rep = num(kpis.reprovados_count);
    var totalAprRep = apr + rep;
    var repPct = totalAprRep ? Math.round((rep / totalAprRep) * 100) : 0;

    var pedidos = "";
    (g.pedidos_pendentes || []).slice(0, 7).forEach(function (p) {
      var val = p.valor_estimado != null ? "R$ " + formatBrl(p.valor_estimado) : p.valor_medicao != null ? "R$ " + formatBrl(p.valor_medicao) : "—";
      var dias = num(p.dias_pendente);
      var detailUrl =
        (window.__AO_URLS__ && window.__AO_URLS__.gestao_detail_prefix
          ? window.__AO_URLS__.gestao_detail_prefix + p.id + "/"
          : "/gestao/pedidos/" + p.id + "/");
      pedidos +=
        '<div class="pedido-row" onclick="location.href=\'' +
        esc(detailUrl) +
        '\'">' +
        '<div class="pedido-code">' +
        esc(p.codigo || "—") +
        "</div>" +
        '<div class="pedido-credor">' +
        esc(p.nome_credor || "—") +
        '<div style="font-size:10px;color:var(--bi-text3)">' +
        esc(p.tipo_solicitacao || "—") +
        " · há " +
        dias +
        " dias" +
        (dias > 7 ? " ⚠️" : "") +
        "</div></div>" +
        '<div class="pedido-valor">' +
        val +
        "</div>" +
        '<div class="pedido-badge pend">Pendente</div><div class="pedido-arrow">›</div></div>';
    });
    if (!pedidos) pedidos = '<div style="font-size:12px;color:var(--bi-text3);padding:12px 0">Nenhum pedido pendente</div>';

    var aprovadores = "";
    (g.aprovadores || []).forEach(function (a) {
      var tm = num(a.tempo_medio_dias);
      var tb = tm <= 2 ? "fast" : tm <= 5 ? "mid" : "slow";
      aprovadores +=
        '<div class="resp-row"><div class="resp-avatar">' +
        esc((a.nome || "").slice(0, 2).toUpperCase()) +
        '</div><div><div class="resp-name">' +
        esc(a.nome) +
        '</div><div class="resp-sub">' +
        esc(a.nivel || "Aprovador") +
        '</div></div><div class="resp-stats"><div class="resp-stat"><div class="resp-stat-val green">' +
        num(a.aprovados) +
        '</div><div class="resp-stat-label">Aprov.</div></div><div class="resp-divider"></div><div class="resp-stat"><div class="resp-stat-val red">' +
        num(a.reprovados) +
        '</div><div class="resp-stat-label">Repr.</div></div><div class="resp-divider"></div><div class="resp-stat"><div class="tempo-badge ' +
        tb +
        '">' +
        tm.toFixed(1) +
        'd</div><div class="resp-stat-label" style="margin-top:2px;text-align:center">Tempo</div></div></div></div>';
    });
    if (!aprovadores) aprovadores = '<div style="font-size:12px;color:var(--bi-text3);padding:12px 0">Sem dados de aprovadores</div>';

    var tmGeral = kpis.tempo_medio_geral != null ? num(kpis.tempo_medio_geral).toFixed(1) + " dias" : "—";

    return (
      '<div class="grid-4" style="margin-bottom:12px">' +
      '<div class="card"><div class="card-title">Pendentes <span class="card-tag tag-gest">GESTCONTROLL</span></div>' +
      '<div class="big-num yellow">' +
      num(kpis.pendentes_count) +
      '</div><div class="big-sub">aguardando aprovação</div>' +
      '<div style="margin-top:12px;padding-top:12px;border-top:1px solid var(--bi-border)"><div style="font-size:10px;color:var(--bi-text3);margin-bottom:3px">Valor em análise</div>' +
      '<div style="font-size:18px;font-weight:800;font-family:\'JetBrains Mono\',monospace;color:var(--bi-yellow)">R$&nbsp;' +
      formatBrl(kpis.pendentes_valor) +
      "</div></div>" +
      '<a href="' +
      esc((window.__AO_URLS__ && window.__AO_URLS__.gestao_list_pendente) || "/gestao/pedidos/?status=pendente") +
      obraQ +
      '" class="nav-link">Ver fila ' +
      NAV_SVG +
      "</a></div>" +
      '<div class="card"><div class="card-title">Reprovados <span class="card-tag tag-gest">GESTCONTROLL</span></div>' +
      '<div class="big-num red">' +
      num(kpis.reprovados_count) +
      '</div><div class="big-sub">no período</div><div class="chips" style="margin-top:10px">' +
      repHtml +
      "</div>" +
      '<a href="' +
      esc((window.__AO_URLS__ && window.__AO_URLS__.gestao_list_reprovado) || "/gestao/pedidos/?status=reprovado") +
      obraQ +
      '" class="nav-link">Ver reprovados ' +
      NAV_SVG +
      "</a></div>" +
      '<div class="card"><div class="card-title">Taxa aprovação <span class="card-tag tag-gest">GESTCONTROLL</span></div>' +
      '<div class="big-num green">' +
      Math.round(num(kpis.taxa_aprovacao)) +
      '%</div><div class="big-sub">no período</div>' +
      '<div class="prog-wrap" style="margin-top:12px"><div class="prog-label"><span style="color:var(--bi-green)">✓ ' +
      apr +
      ' apr.</span><span style="color:var(--bi-red)">✕ ' +
      rep +
      ' repr.</span></div><div class="prog-bar" style="height:8px;display:flex">' +
      '<div style="height:100%;width:' +
      num(kpis.taxa_aprovacao) +
      '%;background:var(--bi-green);border-radius:99px 0 0 99px"></div>' +
      '<div style="height:100%;width:' +
      repPct +
      '%;background:var(--bi-red);border-radius:0 99px 99px 0"></div></div></div></div>' +
      '<div class="card"><div class="card-title">Alçadas travadas <span class="card-tag tag-gest">CENTRAL</span></div>' +
      '<div class="big-num red">' +
      num(kpis.alcadas_travadas) +
      '</div><div class="big-sub">parados há +5 dias</div><div class="chips" style="margin-top:10px">' +
      alcHtml +
      "</div></div></div>" +
      '<div class="grid-2" style="margin-bottom:12px">' +
      '<div class="card"><div class="card-title">Pedidos pendentes <span class="card-tag tag-gest">GESTCONTROLL</span></div>' +
      pedidos +
      (num(kpis.pendentes_count) > 0
        ? '<a href="' +
          esc((window.__AO_URLS__ && window.__AO_URLS__.gestao_list_pendente) || "/gestao/pedidos/?status=pendente") +
          obraQ +
          '" class="nav-link">Ver todos os ' +
          num(kpis.pendentes_count) +
          " pendentes " +
          NAV_SVG +
          "</a>"
        : "") +
      '</div><div class="card"><div class="card-title">Aprovadores <span class="card-tag tag-gest">GESTCONTROLL</span></div>' +
      aprovadores +
      '<div style="margin-top:12px;padding:10px;background:var(--bi-yellow-bg);border-radius:8px"><div style="font-size:10px;font-weight:700;color:var(--bi-yellow);margin-bottom:3px">⏱ Tempo médio geral</div>' +
      '<div style="font-size:20px;font-weight:800;font-family:\'JetBrains Mono\',monospace;color:var(--bi-yellow)">' +
      tmGeral +
      "</div></div></div></div>"
    );
  }

  function renderRestricoes(r, el) {
    if (!r) return '<p class="analise-loading-skeleton">Sem dados de restrições.</p>';
    var kpis = r.kpis || {};
    var projectId = el.dataset.projectId || "";
    var dataOntem = el.dataset.restricoesDataOntem || "";
    var listUrl = projectId
      ? (window.__AO_URLS__ && window.__AO_URLS__.impedimentos_list
          ? window.__AO_URLS__.impedimentos_list.replace("0", projectId)
          : "/impedimentos/" + projectId + "/")
      : (window.__AO_URLS__ && window.__AO_URLS__.impedimentos_select) || "/impedimentos/";

    var chips = "";
    var prio = kpis.por_prioridade || {};
    Object.keys(prio).forEach(function (k) {
      if (!prio[k]) return;
      var cls = k === "CRITICA" ? "red" : k === "ALTA" ? "yellow" : k === "NORMAL" ? "blue" : "gray";
      chips += '<div class="chip chip-' + cls + '">' + esc(k) + " " + esc(prio[k]) + "</div>";
    });

    var venc = "";
    (r.vencidas_recentes || []).forEach(function (v) {
      venc +=
        '<div class="tl-item"><div class="tl-date">há ' +
        num(v.dias_vencido) +
        ' dias</div><div class="tl-content">' +
        esc((v.titulo || "").slice(0, 40)) +
        '<div class="tl-meta">' +
        esc(v.prioridade || "") +
        " · " +
        esc(v.responsavel || "Sem responsável") +
        "</div></div></div>";
    });
    if (!venc) venc = '<div style="font-size:12px;color:var(--bi-text3);padding:8px 0">Nenhuma vencida</div>';

    var resp = "";
    (r.por_responsavel || []).forEach(function (row, i) {
      var dot = i === 0 ? "var(--bi-red)" : i === 1 ? "var(--bi-yellow)" : i === 2 ? "var(--bi-blue)" : "var(--bi-text3)";
      resp +=
        '<div class="stat-row"><div class="stat-row-label"><div class="stat-dot" style="background:' +
        dot +
        '"></div>' +
        esc(row.nome) +
        '</div><div class="stat-row-value">' +
        esc(row.total) +
        "</div></div>";
    });

    return (
      '<div class="grid-4">' +
      '<div class="card"><div class="card-title">Total aberto <span class="card-tag tag-rest">RESTRIÇÕES</span></div>' +
      '<div class="big-num red">' +
      num(kpis.total_aberto) +
      '</div><div class="big-sub">em aberto</div><div class="chips" style="margin-top:10px">' +
      chips +
      '</div><a href="' +
      esc(listUrl + "?view=tabela&prioridade=CRITICA") +
      '" class="nav-link">Ver críticas ' +
      NAV_SVG +
      "</a></div>" +
      '<div class="card"><div class="card-title">Prazo vencido <span class="card-tag tag-rest">RESTRIÇÕES</span></div>' +
      '<div class="big-num red">' +
      num(kpis.vencidas) +
      '</div><div class="big-sub">prazo expirado</div><div style="margin-top:10px">' +
      venc +
      '</div><a href="' +
      esc(listUrl + (dataOntem ? "?view=tabela&data_fim=" + dataOntem : "")) +
      '" class="nav-link">Ver vencidas ' +
      NAV_SVG +
      "</a></div>" +
      '<div class="card"><div class="card-title">Por responsável <span class="card-tag tag-rest">RESTRIÇÕES</span></div>' +
      resp +
      (num(kpis.sem_responsavel) > 0
        ? '<div class="stat-row"><div class="stat-row-label" style="color:var(--bi-red)">⚠ Sem responsável</div><div class="stat-row-value" style="color:var(--bi-red)">' +
          num(kpis.sem_responsavel) +
          "</div></div>"
        : "") +
      "</div>" +
      '<div class="card"><div class="card-title">Subtarefas bloqueando <span class="card-tag tag-rest">RESTRIÇÕES</span></div>' +
      '<div class="big-num yellow">' +
      num(kpis.subtarefas_bloqueando) +
      '</div><div class="big-sub">subtarefas abertas</div>' +
      (kpis.restricoes_com_subtarefa_aberta
        ? '<div style="margin-top:12px;padding-top:12px;border-top:1px solid var(--bi-border)"><div class="chip chip-red" style="display:inline-flex">' +
          num(kpis.restricoes_com_subtarefa_aberta) +
          " restrições bloqueadas</div></div>"
        : "") +
      "</div></div>"
    );
  }

  function formatDateBr(iso) {
    if (!iso) return "—";
    var d = new Date(iso + "T12:00:00");
    if (isNaN(d.getTime())) return esc(iso);
    return ("0" + d.getDate()).slice(-2) + "/" + ("0" + (d.getMonth() + 1)).slice(-2);
  }

  function renderDiario(d, el) {
    if (!d) return '<p class="analise-loading-skeleton">Sem dados do diário.</p>';
    var vinculo = el.dataset.diarioVinculo === "1" || d.vinculo_projeto;
    var rs = d.rdos_resumo || {};
    var dias = el.dataset.periodoDias || "";
    var projId = el.dataset.projetoDiarioId || "";

    var rdoBar =
      '<div class="rdo-bar"><div class="rdo-seg" style="flex:' +
      Math.max(1, num(rs.aprovados)) +
      ';background:var(--bi-green);opacity:.8"></div>';
    if (num(rs.pendentes) > 0) rdoBar += '<div class="rdo-seg" style="flex:' + num(rs.pendentes) + ';background:var(--bi-yellow)"></div>';
    if (num(rs.sem_rdo) > 0) rdoBar += '<div class="rdo-seg" style="flex:' + num(rs.sem_rdo) + ';background:var(--bi-border2)"></div>';
    rdoBar += "</div>";

    var tags = "";
    if (vinculo) {
      (d.tags_top || []).forEach(function (t) {
        tags +=
          '<div class="stat-row"><div class="stat-row-label"><div class="stat-dot" style="background:' +
          esc(t.cor || "#6366f1") +
          '"></div>' +
          esc(t.nome) +
          '</div><div class="stat-row-value">' +
          num(t.total) +
          "</div></div>";
      });
      if (!tags) tags = '<div style="font-size:12px;color:var(--bi-text3);padding:8px 0">Sem ocorrências no período</div>';
    } else {
      tags = '<div style="font-size:12px;color:var(--bi-text3);padding:8px 0">⚠️ Diário sem vínculo — configure o código Sienge da obra</div>';
    }

    var diasHtml = "";
    if (vinculo) {
      (d.ultimos_dias_calendario || []).slice(0, 7).forEach(function (dia) {
        var data = dia.data;
        var inner = dia.tem_rdo
          ? "RDO #" +
            esc(dia.report_number) +
            " · " +
            (dia.status === "AP"
              ? '<span style="color:var(--bi-green)">Aprovado</span>'
              : dia.status === "AG"
                ? '<span style="color:var(--bi-yellow)">Pendente</span>'
                : esc(dia.status)) +
            '<div class="tl-meta">' +
            num(dia.ocorrencias) +
            " ocorr. · " +
            esc(dia.responsavel || "—") +
            "</div>"
          : '<span style="color:var(--bi-text3);font-style:italic">Sem RDO registrado</span>';
        diasHtml += '<div class="tl-item"><div class="tl-date">' + formatDateBr(data) + '</div><div class="tl-content">' + inner + "</div></div>";
      });
      if (projId) {
        diasHtml +=
          '<a href="' +
          esc((window.__AO_URLS__ && window.__AO_URLS__.report_list) || "/diaries/") +
          "?project=" +
          encodeURIComponent(projId) +
          '" class="nav-link">Ver todos os diários ' +
          NAV_SVG +
          "</a>";
      }
    } else {
      diasHtml = '<div style="font-size:12px;color:var(--bi-text3);padding:8px 0">Diário sem vínculo com esta obra.</div>';
    }

    return (
      '<div class="grid-3">' +
      '<div class="card"><div class="card-title">Status dos RDOs <span class="card-tag tag-campo">DIÁRIO</span></div>' +
      '<div style="display:flex;gap:16px;align-items:center">' +
      '<div><div class="big-num green" style="font-size:28px">' +
      num(rs.aprovados) +
      '</div><div class="big-sub">aprovados</div></div>' +
      '<div style="width:1px;height:40px;background:var(--bi-border)"></div>' +
      '<div><div class="big-num yellow" style="font-size:22px">' +
      num(rs.pendentes) +
      '</div><div class="big-sub">pendentes</div></div>' +
      '<div style="width:1px;height:40px;background:var(--bi-border)"></div>' +
      '<div><div class="big-num red" style="font-size:22px">' +
      num(rs.sem_rdo) +
      '</div><div class="big-sub">sem RDO</div></div></div>' +
      rdoBar +
      '<div style="font-size:10.5px;color:var(--bi-text3)">' +
      esc(dias) +
      " dias · " +
      num(rs.aprovados) +
      " apr · " +
      num(rs.pendentes) +
      " pend. · " +
      num(rs.sem_rdo) +
      " sem registro</div></div>" +
      '<div class="card"><div class="card-title">Ocorrências por tag <span class="card-tag tag-campo">DIÁRIO</span></div>' +
      tags +
      '</div><div class="card"><div class="card-title">Últimos dias <span class="card-tag tag-campo">DIÁRIO</span></div>' +
      diasHtml +
      "</div></div>"
    );
  }

  function renderSuprimentos(s) {
    if (!s) return '<p class="analise-loading-skeleton">Sem dados de suprimentos.</p>';
    var sk = s.kpis || {};
    var denom = Math.max(1, num(sk.total_itens));
    function funnel(cls, label, val) {
      var w = Math.round((num(val) / denom) * 100);
      return (
        '<div class="funnel-item"><div class="funnel-label">' +
        label +
        '</div><div class="funnel-bar-wrap"><div class="funnel-bar ' +
        cls +
        '" style="width:' +
        w +
        '%;min-width:28px"><span class="funnel-num">' +
        num(val) +
        "</span></div></div></div>"
      );
    }
    var locais = (s.ranking && s.ranking.locais) || [];
    var mx = locais.length ? num(locais[0][1]) : 1;
    var locHtml = "";
    locais.forEach(function (row) {
      var q = num(row[1]);
      var cls = q >= 15 ? "red" : q >= 8 ? "yellow" : q >= 4 ? "accent" : "green";
      var w = Math.round((q / mx) * 100);
      locHtml +=
        '<div class="prog-wrap"><div class="prog-label"><span>' +
        esc(row[0] || "—") +
        "</span><span>" +
        q +
        ' pend.</span></div><div class="prog-bar"><div class="prog-fill ' +
        cls +
        '" style="width:' +
        w +
        '%"></div></div></div>';
    });
    if (!locHtml) locHtml = '<div class="big-sub" style="color:var(--bi-text3)">Sem dados de locais</div>';

    var funnelHtml;
    if (sk.manual_mode) {
      funnelHtml =
        funnel("f1", "Em levantamento", sk.levantamento || sk.sem_alocacao) +
        funnel("f2", "Parcial", sk.parciais || 0) +
        funnel("f3", "Entregue (local)", sk.entregues || 0) +
        funnel("f4", "Sem alocação", sk.sem_alocacao);
    } else {
      funnelHtml =
        funnel("f1", "Sem pedido (SC)", sk.sem_sc) +
        funnel("f2", "SC sem compra (PC)", sk.sem_pc) +
        funnel("f3", "PC sem entrega", sk.sem_entrega) +
        funnel("f4", "Entregue s/ alocar", sk.sem_alocacao);
    }

    return (
      '<div class="grid-2">' +
      '<div class="card"><div class="card-title">Funil de materiais <span class="card-tag tag-mat">SUPRIMENTOS</span></div>' +
      '<div class="funnel">' +
      funnelHtml +
      "</div>" +
      '<div style="margin-top:12px;padding-top:12px;border-top:1px solid var(--bi-border);display:flex;align-items:center;justify-content:space-between">' +
      '<div style="font-size:11px;color:var(--bi-text2)">Itens atrasados</div>' +
      '<div style="font-size:16px;font-weight:800;font-family:\'JetBrains Mono\',monospace;color:var(--bi-red)">' +
      num(sk.atrasados) +
      "</div></div></div>" +
      '<div class="card"><div class="card-title">Locais com mais pressão <span class="card-tag tag-mat">SUPRIMENTOS</span></div>' +
      locHtml +
      "</div></div>"
    );
  }

  function renderTrackhub(th, el) {
    if (!th) return '<p class="analise-loading-skeleton">Sem dados do TrackHub.</p>';
    var res = th.resumo || {};
    var obraId = el.dataset.obra || "";
    var filaUrl = (window.__AO_URLS__ && window.__AO_URLS__.trackhub_fila) || "/trackhub/fila/";
    if (obraId) filaUrl += (filaUrl.indexOf("?") >= 0 ? "&" : "?") + "obra=" + encodeURIComponent(obraId);

    var tipos = "";
    (th.por_tipo || []).slice(0, 7).forEach(function (row, i) {
      var dot = i === 0 ? "var(--bi-red)" : i === 1 ? "var(--bi-yellow)" : i === 2 ? "var(--bi-blue)" : "var(--bi-text3)";
      tipos +=
        '<div class="stat-row"><div class="stat-row-label"><div class="stat-dot" style="background:' +
        dot +
        '"></div>' +
        esc(row.tipo) +
        '</div><div class="stat-row-value">' +
        num(row.total) +
        "</div></div>";
    });
    if (!tipos) tipos = '<div class="stat-row"><div class="stat-row-label">Sem pendências abertas</div><div class="stat-row-value">—</div></div>';

    var resp = "";
    (th.responsaveis || []).slice(0, 7).forEach(function (r, i) {
      var dot = i === 0 ? "var(--bi-red)" : i === 1 ? "var(--bi-yellow)" : i === 2 ? "var(--bi-blue)" : "var(--bi-text3)";
      resp +=
        '<div class="stat-row"><div class="stat-row-label"><div class="stat-dot" style="background:' +
        dot +
        '"></div>' +
        esc(r.nome) +
        '</div><div class="stat-row-value">' +
        num(r.total) +
        "</div></div>";
    });

    var atras = "";
    (th.mais_atrasadas || []).slice(0, 5).forEach(function (item) {
      atras +=
        '<div class="stat-row"><div class="stat-row-label"><div class="stat-dot" style="background:var(--bi-red)"></div>' +
        esc((item.titulo || "").slice(0, 40)) +
        '</div><div class="stat-row-value" style="color:var(--bi-red)">' +
        num(item.dias_atraso) +
        " dias</div></div>";
    });
    if (!atras) atras = '<div class="stat-row"><div class="stat-row-label">Nenhuma vencida</div><div class="stat-row-value">—</div></div>';

    return (
      '<div class="grid-3" style="margin-bottom:12px">' +
      '<div class="card"><div class="card-title">Resumo geral <span class="card-tag tag-gest">TRACKHUB</span></div>' +
      '<div class="big-num ' +
      (num(res.vencidas) > 0 ? "red" : "green") +
      '">' +
      num(res.total_aberto) +
      '</div><div class="big-sub">pendências abertas</div>' +
      '<div class="stat-row" style="margin-top:10px"><div class="stat-row-label"><div class="stat-dot" style="background:var(--bi-red)"></div>Prazo vencido</div><div class="stat-row-value" style="color:var(--bi-red)">' +
      num(res.vencidas) +
      '</div></div><div class="stat-row"><div class="stat-row-label"><div class="stat-dot" style="background:var(--bi-blue)"></div>Em andamento</div><div class="stat-row-value" style="color:var(--bi-blue)">' +
      num(res.em_andamento) +
      '</div></div><a href="' +
      esc(filaUrl) +
      '" class="nav-link">Abrir TrackHub ' +
      NAV_SVG +
      "</a></div>" +
      '<div class="card"><div class="card-title">Por tipo <span class="card-tag tag-gest">TRACKHUB</span></div>' +
      tipos +
      '</div><div class="card"><div class="card-title">Concluídas recentemente <span class="card-tag tag-gest">TRACKHUB</span></div>' +
      '<div class="big-num green">' +
      num(res.concluidas_30d) +
      '</div><div class="big-sub">concluídas nos últimos 30 dias</div></div></div>' +
      '<div class="grid-2">' +
      '<div class="card"><div class="card-title">Responsáveis com etapas pendentes <span class="card-tag tag-gest">TRACKHUB</span></div>' +
      resp +
      '</div><div class="card"><div class="card-title">Pendências mais atrasadas <span class="card-tag tag-gest">TRACKHUB</span></div>' +
      atras +
      "</div></div>"
    );
  }

  function renderSecao(secao, payload, el) {
    var data = payload && payload.data ? payload.data : payload;
    if (!data) return '<p style="color:var(--bi-red)">Resposta vazia.</p>';
    if (secao === "gestcontroll") return renderGestcontroll(data.gestcontroll);
    if (secao === "restricoes") return renderRestricoes(data.restricoes, el);
    if (secao === "diario") return renderDiario(data.diario, el);
    if (secao === "suprimentos") return renderSuprimentos(data.suprimentos);
    if (secao === "trackhub") return renderTrackhub(data.trackhub, el);
    return '<p>Seção não suportada: ' + esc(secao) + "</p>";
  }

  function carregarSecaoLazy(el) {
    var secao = el.dataset.secao;
    if (!secao || !el.dataset.obra) return;
    fetch(apiUrl(el), { credentials: "same-origin", headers: { Accept: "application/json" } })
      .then(function (r) {
        return r.json();
      })
      .then(function (j) {
        if (!j.success) throw new Error(j.error || "Falha ao carregar seção");
        el.innerHTML = renderSecao(secao, j, el);
      })
      .catch(function () {
        el.innerHTML = '<p style="padding:16px;color:var(--bi-red)">Erro ao carregar. Tente recarregar a página.</p>';
      });
  }

  function initLazySections() {
    document.querySelectorAll(".analise-secao-lazy").forEach(carregarSecaoLazy);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initLazySections);
  } else {
    initLazySections();
  }
})();
