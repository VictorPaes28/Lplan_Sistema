"""Converte dicts de query em AssistantResponse."""
from __future__ import annotations

from assistente_lplan.schemas import AssistantResponse


def permission_denied(module: str) -> AssistantResponse:
    labels = {
        "rh": "Recursos Humanos (RH/DP)",
        "mapa_geo": "Mapa Geografico",
        "gerencial": "visao gerencial",
        "trackhub": "TrackHub",
        "restricoes": "Restricoes / Impedimentos",
        "mapa_controle": "Mapa de Controle",
    }
    label = labels.get(module, module)
    return AssistantResponse(
        summary=f"Voce nao tem permissao para consultar {label}.",
        badges=["Sem permissao"],
        alerts=[
            {
                "level": "warning",
                "message": "Solicite ao gestor o grupo de acesso correspondente no cadastro de usuario.",
            }
        ],
    )


def from_error(error: str, *, domain: str = "") -> AssistantResponse:
    messages = {
        "obra_nao_encontrada": "Nao foi possivel identificar a obra no seu escopo. Informe o codigo ou selecione no painel.",
        "obra_mapa_nao_encontrada": "Obra sem mapa de suprimentos vinculado ao projeto.",
        "usuario_fora_escopo": "Este usuario esta fora do seu escopo de visibilidade.",
        "usuario_nao_identificado": "Nao identifiquei o usuario. Informe nome ou login.",
        "insumo_ausente": "Informe o nome do insumo ou material na pergunta.",
        "sem_dados_controle": "Dados de mapa de controle indisponiveis para esta obra.",
    }
    summary = messages.get(error, "Nao foi possivel concluir a consulta.")
    return AssistantResponse(
        summary=summary,
        badges=["Sem dados suficientes"],
        alerts=[{"level": "info", "message": "Revise o codigo da obra ou reformule a pergunta."}],
        raw_data={"error": error, "domain": domain},
    )


def from_query(
    data: dict,
    *,
    domain: str,
    badges: list[str] | None = None,
    suggested_replies: list[str] | None = None,
) -> AssistantResponse:
    if not data.get("ok", True):
        return from_error(data.get("error", "unknown"), domain=domain)

    summary = data.get("summary") or data.get("summary_hint", "Consulta concluida.")
    if data.get("gerencial_limited"):
        summary = (
            f"{summary} (Visao limitada: ranking apenas com seus dados — "
            "sem permissao gerencial para ver toda a equipe.)"
        )

    cards = []
    for key, title in (
        ("total", "Total"),
        ("total_abertas", "Abertas"),
        ("total_vencidas", "Vencidas"),
        ("total_criticas", "Criticas"),
        ("colaboradores_ativos", "Colaboradores ativos"),
        ("alertas_criticos", "Alertas RH"),
        ("total_com_elementos", "Com elementos geo"),
        ("percentual_medio", "% conclusao"),
        ("sem_alocacao", "Sem alocacao"),
        ("atrasados", "Atrasados"),
        ("logins_30d", "Logins 30d"),
        ("diarios_30d", "Diarios 30d"),
        ("pedidos_30d", "Pedidos 30d"),
    ):
        if key in data and data[key] is not None:
            val = data[key]
            if isinstance(val, float):
                val = f"{val:.1f}"
            cards.append({"title": title, "value": str(val), "tone": "info"})

    if data.get("stats"):
        st = data["stats"]
        cards.extend(
            [
                {"title": "Restricoes abertas", "value": str(st.get("total_abertas", 0)), "tone": "warning"},
                {"title": "Vencidas", "value": str(st.get("vencidas", 0)), "tone": "danger"},
            ]
        )

    table = {}
    rows = data.get("rows") or data.get("ranking") or data.get("obras") or data.get("segmentos")
    if rows and isinstance(rows, list) and rows and isinstance(rows[0], dict):
        columns = list(rows[0].keys())[:6]
        table = {"caption": domain.replace("_", " ").title(), "columns": columns, "rows": rows[:30]}

    alerts = []
    if data.get("total", 0) == 0 and data.get("ok") and not rows:
        alerts.append({"level": "info", "message": "Nenhum registro encontrado para os filtros atuais."})

    chips = list(suggested_replies or [])
    if domain == "rdo" and data.get("multi"):
        chips.append("Quais obras estao sem RDO esta semana?")
    if domain == "pedidos":
        chips.append("Pedidos parados ha mais de 30 dias")

    return AssistantResponse(
        summary=summary,
        cards=cards[:8],
        table=table,
        badges=badges or [domain.replace("_", " ").title()],
        alerts=alerts,
        suggested_replies=chips[:8],
        raw_data={"query": {k: v for k, v in data.items() if k != "raw_internal"}},
    )
