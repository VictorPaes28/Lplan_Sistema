"""URLs e fila de resolução acionável para o portfólio multi-obra."""

from __future__ import annotations

from typing import Any
from urllib.parse import urlencode

from django.urls import reverse

PRIORIDADE_ORDEM = {
    "URGENTE": 0,
    "ALTA": 1,
    "MEDIA": 2,
    "MÉDIA": 2,
    "ROTINA": 3,
    "BAIXA": 4,
}


def portfolio_obra_links(
    obra_id: int,
    *,
    gestao_obra_id: int | None = None,
    ambiente_id: int | None = None,
    periodo_preset: str = "",
) -> dict[str, str | None]:
    bi = reverse("engenharia:analise_obra") + f"?obra={obra_id}"
    if periodo_preset:
        bi += f"&periodo={periodo_preset}"
    mapa_base = reverse("engenharia:mapa") + f"?obra={obra_id}"
    mc_base = reverse("engenharia:mapa_controle") + f"?obra={obra_id}"
    if ambiente_id:
        mc_base = (
            reverse("engenharia:ferramenta_editor_ambiente", args=[ambiente_id])
            + f"?obra={obra_id}"
        )
    return {
        "bi": bi,
        "bi_controle": bi + "#bloco-1",
        "bi_cruzamento": bi + "#bloco-1b",
        "bi_restricoes": bi + "#bloco-3",
        "bi_suprimentos": bi + "#bloco-5",
        "bi_diario": bi + "#bloco-4",
        "bi_gestao": bi + "#bloco-2",
        "bi_pendencias": bi + "#bloco-6",
        "bi_trackhub": bi + "#bloco-6",
        "mapa": mapa_base,
        "mapa_atrasados": mapa_base + "&status=atrasados",
        "mapa_nao_alocado": mapa_base + "&status=nao_alocado",
        "mapa_controle": mc_base,
        "trackhub": reverse("trackhub:fila") + f"?obra={obra_id}",
        "impedimentos": (
            reverse("impedimentos:list_impedimentos", args=[gestao_obra_id])
            if gestao_obra_id
            else None
        ),
        "gestao_pedidos": reverse("gestao:list_workorders"),
    }


def mapa_controle_filtro_url(
    obra_id: int,
    ambiente_id: int | None,
    *,
    bloco: str = "",
    setor: str = "",
    pavimento: str = "",
) -> str:
    if ambiente_id:
        base = reverse("engenharia:ferramenta_editor_ambiente", args=[ambiente_id])
        params = {"obra": obra_id}
    else:
        base = reverse("engenharia:mapa_controle")
        params = {"obra": obra_id}
    if bloco:
        params["bloco"] = bloco
    if setor:
        params["setor"] = setor
    if pavimento:
        params["pavimento"] = pavimento
    return base + "?" + urlencode(params)


def _item(
    *,
    prioridade: str,
    tipo: str,
    titulo: str,
    url: str,
    subtitulo: str = "",
    url_secundaria: str | None = None,
    label_secundaria: str = "",
    score: float = 0,
) -> dict[str, Any]:
    return {
        "prioridade": prioridade.upper(),
        "tipo": tipo,
        "titulo": titulo,
        "subtitulo": subtitulo,
        "url": url,
        "url_secundaria": url_secundaria,
        "label_secundaria": label_secundaria,
        "score": score,
    }


def build_gargalos_e_resolver(
    obra_id: int,
    obra_nome: str,
    modulos: dict[str, Any],
    links: dict[str, str | None],
    *,
    gestao_obra_id: int | None,
    ambiente_id: int | None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any] | None]:
    """
    Gargalos (execução × suprimento) + fila de resolução com URLs diretas.
    """
    resolver: list[dict[str, Any]] = []
    gargalos: list[dict[str, Any]] = []

    restr = modulos.get("restricoes") or {}
    sup = modulos.get("suprimentos") or {}
    gest = modulos.get("gestcontroll") or {}
    diario = modulos.get("diario") or {}
    execucao = modulos.get("execucao") or {}
    cruzamento = modulos.get("cruzamento") or {}
    trackhub_mod = modulos.get("trackhub") or {}

    vencidas = int(restr.get("vencidas") or 0)
    abertas = int(restr.get("abertas") or 0)
    atrasados = int(sup.get("atrasados") or 0)
    sem_aloc = int(sup.get("sem_alocacao") or 0)
    pend_gest = int(gest.get("pendentes") or 0)
    rdos = int(modulos.get("rdos_pendentes") or 0)
    occ_crit = int(diario.get("ocorrencias_criticas") or 0)
    th_vencidas = int(trackhub_mod.get("vencidas") or 0)
    th_abertas = int(trackhub_mod.get("abertas") or 0)

    if th_vencidas > 0 and links.get("trackhub"):
        resolver.append(
            _item(
                prioridade="URGENTE",
                tipo="trackhub",
                titulo=f"{th_vencidas} pendência(s) TrackHub vencida(s)",
                subtitulo="Prazo estourado na fila de pendências",
                url=links["trackhub"],
                url_secundaria=links.get("bi_trackhub"),
                label_secundaria="Ver no BI",
                score=95 + th_vencidas,
            )
        )
    elif th_abertas >= 3 and links.get("trackhub"):
        resolver.append(
            _item(
                prioridade="ALTA" if th_abertas >= 6 else "MEDIA",
                tipo="trackhub",
                titulo=f"{th_abertas} pendência(s) TrackHub aberta(s)",
                subtitulo="Fila operacional da obra",
                url=links["trackhub"],
                url_secundaria=links.get("bi_trackhub"),
                label_secundaria="Ver no BI",
                score=35 + th_abertas,
            )
        )

    if vencidas > 0 and links.get("impedimentos"):
        resolver.append(
            _item(
                prioridade="URGENTE",
                tipo="restricao",
                titulo=f"{vencidas} restrição(ões) vencida(s)",
                subtitulo="Prazo estourado — liberar frente de serviço",
                url=links["impedimentos"],
                url_secundaria=links.get("bi_restricoes"),
                label_secundaria="Ver no BI",
                score=100 + vencidas,
            )
        )
    elif abertas > 0:
        url_r = links.get("impedimentos") or links.get("bi_restricoes") or links["bi"]
        resolver.append(
            _item(
                prioridade="ALTA" if abertas >= 2 else "MEDIA",
                tipo="restricao",
                titulo=f"{abertas} restrição(ões) aberta(s)",
                subtitulo="Impedimentos ativos na obra",
                url=url_r,
                score=50 + abertas,
            )
        )

    for cand in (cruzamento.get("candidatos_atraso_suprimento_e_execucao") or [])[:3]:
        rotulo = (cand.get("rotulo_exibicao") or cand.get("bloco_mapa") or cand.get("local_norm") or "Local").strip()
        pct = cand.get("controle", {}).get("percentual_medio")
        pend = cand.get("suprimentos", {}).get("pendencias_pendentes_ranking") or 0
        pri = (cand.get("prioridade") or "alta").upper()
        if pri == "URGENTE":
            pri = "URGENTE"
        elif pri == "ALTA":
            pri = "ALTA"
        else:
            pri = "MEDIA"
        bloco = (cand.get("bloco_mapa") or "").strip()
        setor = (cand.get("setor_mapa") or "").strip()
        score = float(cand.get("score_risco") or 0)
        url_mapa = mapa_controle_filtro_url(
            obra_id, ambiente_id, bloco=bloco, setor=setor
        )
        gargalo_item = {
            "rotulo": rotulo,
            "exec_pct": pct,
            "sup_pendencias": pend,
            "prioridade": pri,
            "score_risco": score,
            "leitura": cand.get("leitura") or "Execução lenta com material pendente no mesmo eixo.",
            "url_mapa": url_mapa,
            "url_bi_cruzamento": links.get("bi_cruzamento") or links["bi"],
        }
        gargalos.append(gargalo_item)
        resolver.append(
            _item(
                prioridade=pri,
                tipo="cruzamento",
                titulo=f"Gargalo: {rotulo} — exec. {pct}% · {pend} pend. suprimento",
                subtitulo="Execução × material no mesmo bloco/frente",
                url=links.get("bi_cruzamento") or links["bi"],
                url_secundaria=url_mapa,
                label_secundaria="Abrir mapa no bloco",
                score=score,
            )
        )

    if atrasados > 0:
        resolver.append(
            _item(
                prioridade="URGENTE" if atrasados >= 8 else "ALTA" if atrasados >= 3 else "MEDIA",
                tipo="suprimento",
                titulo=f"{atrasados} item(ns) de suprimento atrasado(s)",
                subtitulo="Mapa de suprimentos filtrado por atraso",
                url=links.get("mapa_atrasados") or links["mapa"],
                url_secundaria=links.get("bi_suprimentos"),
                label_secundaria="Ver no BI",
                score=40 + atrasados,
            )
        )

    if sem_aloc >= 5:
        resolver.append(
            _item(
                prioridade="ALTA",
                tipo="suprimento",
                titulo=f"{sem_aloc} itens sem alocação de recebimento",
                subtitulo="Material recebido ou planejado sem vínculo ao local",
                url=links.get("mapa_nao_alocado") or links["mapa"],
                score=25 + sem_aloc,
            )
        )

    if occ_crit > 0:
        resolver.append(
            _item(
                prioridade="URGENTE",
                tipo="diario",
                titulo=f"{occ_crit} ocorrência(s) crítica(s) no diário (30d)",
                subtitulo="Revisar campo e plano de contenção",
                url=links.get("bi_diario") or links["bi"],
                score=80 + occ_crit,
            )
        )

    if rdos > 0:
        resolver.append(
            _item(
                prioridade="ALTA" if rdos >= 3 else "MEDIA",
                tipo="diario",
                titulo=f"{rdos} RDO(s) pendente(s) de aprovação",
                subtitulo="Diário de obras — fila de aprovação",
                url=links.get("bi_diario") or links["bi"],
                score=20 + rdos,
            )
        )

    if pend_gest > 0:
        resolver.append(
            _item(
                prioridade="ALTA" if pend_gest >= 3 else "MEDIA",
                tipo="gestao",
                titulo=f"{pend_gest} pedido(s) aguardando aprovação",
                subtitulo="GestControll — destravar compras/serviços",
                url=links.get("gestao_pedidos") or links.get("bi_gestao") or links["bi"],
                url_secundaria=links.get("bi_gestao"),
                label_secundaria="Ver no BI",
                score=30 + pend_gest,
            )
        )

    piores = execucao.get("piores_blocos") or []
    if piores and not gargalos:
        b = piores[0]
        rotulo = b.get("rotulo") or "Bloco"
        pct = b.get("pct")
        if pct is not None and float(pct) < 45:
            bloco_raw = rotulo.split("·")[-1].strip() if "·" in rotulo else rotulo
            url_mapa = mapa_controle_filtro_url(obra_id, ambiente_id, bloco=bloco_raw)
            gargalos.append(
                {
                    "rotulo": rotulo,
                    "exec_pct": pct,
                    "sup_pendencias": 0,
                    "prioridade": "MEDIA",
                    "score_risco": max(0, 45 - float(pct)),
                    "leitura": "Menor avanço físico entre os blocos monitorados.",
                    "url_mapa": url_mapa,
                    "url_bi_cruzamento": links.get("bi_controle") or links["bi"],
                }
            )
            resolver.append(
                _item(
                    prioridade="MEDIA",
                    tipo="execucao",
                    titulo=f"Avanço baixo em {rotulo} ({pct}%)",
                    subtitulo="Priorizar frente no mapa de controle",
                    url=url_mapa,
                    url_secundaria=links.get("bi_controle"),
                    label_secundaria="Ver no BI",
                    score=float(pct) * -1 + 45,
                )
            )

    for ac in modulos.get("acoes") or []:
        ancora = ac.get("ancora") or ""
        modulo = ac.get("modulo") or ""
        url = links["bi"] + (ancora if ancora.startswith("#") else "")
        if modulo == "suprimentos":
            url = links.get("mapa_atrasados") or url
        elif modulo == "restricoes" and links.get("impedimentos"):
            url = links["impedimentos"]
        elif modulo == "gestcontroll":
            url = links.get("gestao_pedidos") or url
        elif modulo in ("trackhub", "trackhub_vencidas") and links.get("trackhub"):
            url = links["trackhub"]
        bloco = ac.get("bloco")
        if modulo == "controle" and bloco and ambiente_id:
            url = mapa_controle_filtro_url(obra_id, ambiente_id, bloco=bloco)
        if any(r["titulo"] == ac.get("texto") for r in resolver):
            continue
        resolver.append(
            _item(
                prioridade=ac.get("prioridade") or "MEDIA",
                tipo=modulo or "geral",
                titulo=ac.get("texto") or "Ação sugerida",
                url=url,
                score=10,
            )
        )

    resolver.sort(
        key=lambda x: (
            PRIORIDADE_ORDEM.get(x["prioridade"], 9),
            -float(x.get("score") or 0),
        )
    )

    gargalo_principal = gargalos[0] if gargalos else None
    if not gargalo_principal and resolver:
        top = resolver[0]
        gargalo_principal = {
            "rotulo": obra_nome,
            "exec_pct": execucao.get("percentual") if execucao else None,
            "sup_pendencias": atrasados,
            "prioridade": top["prioridade"],
            "score_risco": top.get("score"),
            "leitura": top.get("subtitulo") or top.get("titulo"),
            "url_mapa": top.get("url"),
            "url_bi_cruzamento": top.get("url_secundaria") or links.get("bi"),
        }

    return gargalos, resolver[:8], gargalo_principal


def merge_fila_global(rows: list[dict[str, Any]], limit: int = 24) -> list[dict[str, Any]]:
    fila: list[dict[str, Any]] = []
    for row in rows:
        for item in row.get("resolver") or []:
            fila.append(
                {
                    **item,
                    "obra_id": row["obra_id"],
                    "obra_codigo": row["codigo"],
                    "obra_nome": row["nome"],
                    "obra_situacao": row["situacao"],
                }
            )
    fila.sort(
        key=lambda x: (
            PRIORIDADE_ORDEM.get(x.get("prioridade", ""), 9),
            -float(x.get("score") or 0),
        )
    )
    return fila[:limit]
