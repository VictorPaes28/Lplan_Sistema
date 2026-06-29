"""
Esclarecimentos obrigatórios antes do dispatch: evita assumir a 'obra mais recente'
quando o usuário tem várias obras, e aproxima a resposta do dado correto.
"""
from __future__ import annotations

from django.contrib.auth.models import User

from assistente_lplan.schemas import AssistantResponse
from assistente_lplan.services.intents import (
    INTENT_INTELIGENCIA_INTEGRADA,
    INTENT_LIST_OBRA_PENDING,
    INTENT_OBRA_BOTTLENECKS,
    INTENT_OBRA_SUMMARY,
    INTENT_RELATORIO_LOCAL_MAPA,
    INTENT_RELATORIO_RDO_PERIOD,
    INTENT_USER_STATUS,
)
from assistente_lplan.services.permissions import AssistantPermissionService, UserScope
from core.models import Project
from assistente_lplan.services.llm_provider import LLMProvider


def _has_usuario(entities: dict) -> bool:
    return bool((entities.get("usuario") or "").strip())

# Intenções que cruzam Diário + Mapa + Gestão de forma explícita — precisam de obra explícita
# se o usuário tiver mais de um projeto no escopo (exceto quando já há sessão/entidade).
INTENTS_REQUIRING_OBRA_CHOICE: frozenset[str] = frozenset(
    {
        INTENT_INTELIGENCIA_INTEGRADA,
        INTENT_OBRA_BOTTLENECKS,
        INTENT_LIST_OBRA_PENDING,
        INTENT_OBRA_SUMMARY,
        INTENT_RELATORIO_LOCAL_MAPA,
        INTENT_RELATORIO_RDO_PERIOD,
    }
)

# Valor = uma frase com {code} OU lista de frases (rotacionamos por obra para dar variedade).
_CLARIFY_CHIP: dict[str, str | list[str]] = {
    INTENT_INTELIGENCIA_INTEGRADA: "Visao integrada da obra {code} (radar Diario, Mapa e Gestao)",
    INTENT_OBRA_BOTTLENECKS: "Gargalos na obra {code} (diario, pedidos e mapa)",
    INTENT_LIST_OBRA_PENDING: "Pendencias operacionais na obra {code}",
    INTENT_OBRA_SUMMARY: "Resumo operacional da obra {code}",
    INTENT_RELATORIO_LOCAL_MAPA: [
        "Como esta o apartamento no mapa de controle da obra {code}?",
        "Situacao do apto/unidade no mapa de suprimentos — obra {code}",
        "Relatorio do local no mapa (alocacao e pendencias) obra {code}",
        "O que falta no apartamento no mapa da obra {code}?",
        "Status do bloco ou pavimento no mapa de controle obra {code}",
        "Comparar local no mapa com a media da obra {code}",
    ],
    INTENT_RELATORIO_RDO_PERIOD: [
        "PDF dos ultimos 15 dias de RDO da obra {code}",
        "Gerar relatorio em PDF do diario (ultimos dias) obra {code}",
        "Baixar PDF consolidado do RDO na obra {code}",
    ],
}


def _clarify_templates_for_intent(intent: str) -> list[str]:
    raw = _CLARIFY_CHIP.get(intent, "Consulta na obra {code} (Diario, Mapa e GestControll)")
    if isinstance(raw, list):
        return raw
    return [raw]


def _has_obra_pointer(entities: dict) -> bool:
    if entities.get("project_id"):
        return True
    return bool((entities.get("obra") or "").strip())


def accessible_projects_for_scope(scope: UserScope, limit: int = 18):
    """Lista {id, code, name} das obras-projeto acessíveis."""
    qs = Project.objects.filter(is_active=True).order_by("code")
    if scope.role != "admin":
        if not scope.project_ids:
            return []
        qs = qs.filter(id__in=scope.project_ids)
    rows = []
    for p in qs[:limit]:
        rows.append({"id": p.id, "code": p.code, "name": (p.name or p.code)[:80]})
    return rows


def inject_single_project_if_unique(entities: dict, scope: UserScope) -> dict:
    """Se o usuário só tem um projeto, usa sem perguntar."""
    if _has_obra_pointer(entities):
        return entities
    projects = accessible_projects_for_scope(scope, limit=2)
    if len(projects) == 1:
        out = dict(entities)
        out["project_id"] = projects[0]["id"]
        return out
    return entities


def build_obra_clarification_response(
    *,
    intent: str,
    user_question: str,
    scope: UserScope,
    projects: list[dict],
    llm: LLMProvider,
) -> AssistantResponse:
    templates = _clarify_templates_for_intent(intent)
    suggested = []
    for i, p in enumerate(projects):
        tmpl = templates[i % len(templates)]
        suggested.append(tmpl.format(code=p["code"]))
    suggested = suggested[:12]

    intro = None
    if llm.can_use():
        intro = llm.clarify_missing_obra(
            user_question=user_question,
            intent_key=intent,
            projects=projects,
        )
    if not intro:
        codes = ", ".join(p["code"] for p in projects[:8])
        intro = (
            "Para cruzar Diario de Obra, Mapa de Suprimentos e GestControll (pedidos), "
            "preciso saber qual obra. Voce tem varias no seu acesso."
            f" Obras: {codes}"
            + ("…" if len(projects) > 8 else "")
            + " Use um dos atalhos abaixo ou digite o codigo na pergunta."
        )

    return AssistantResponse(
        summary=intro,
        badges=["Falta a obra", "LPLAN"],
        alerts=[
            {
                "level": "info",
                "message": "Selecione um atalho com o codigo da obra ou informe a obra na frase.",
            }
        ],
        suggested_replies=suggested[:12],
        actions=[
            {"label": "Abrir Relatorios (escolher obra)", "url": "/reports/", "style": "secondary"},
            {"label": "Selecionar obra", "url": "/select-project/", "style": "secondary"},
        ],
        links=[
            {"label": "Relatorios do diario", "url": "/reports/"},
            {"label": "Selecionar obra na sessao", "url": "/select-project/"},
        ],
        raw_data={
            "clarification": "obra",
            "pending_intent": intent,
            "projects_offered": [p["code"] for p in projects],
        },
    )


def build_usuario_clarification_response(
    *,
    intent: str,
    sample_users: list[User],
) -> AssistantResponse:
    suggested = []
    for u in sample_users[:10]:
        label = (u.get_full_name() or u.username or "").strip() or u.username
        suggested.append(f"Status do usuario {label} nos ultimos 30 dias")

    summary = (
        "Para medir desempenho (diario, pedidos, aprovacoes e acessos nos ultimos 30 dias), "
        "preciso de qual usuario. Escolha um atalho com o nome ou login, ou escreva: "
        "'Status do usuario FULANO nos ultimos 30 dias'."
    )

    return AssistantResponse(
        summary=summary,
        badges=["Falta o usuario", "Equipe"],
        alerts=[{"level": "info", "message": "Use um dos nomes sugeridos ou digite o login."}],
        suggested_replies=suggested,
        actions=[{"label": "Abrir Desempenho da equipe", "url": "/gestao/desempenho-equipe/", "style": "secondary"}],
        links=[{"label": "GestControll - Desempenho", "url": "/gestao/desempenho-equipe/"}],
        raw_data={"clarification": "usuario", "pending_intent": intent},
    )


def sample_users_for_clarification(permission_service: AssistantPermissionService, scope: UserScope, limit: int = 10):
    """Alguns usuários do mesmo ecossistema para sugerir (sem expor lista enorme)."""
    allowed = permission_service.allowed_user_ids_for_visibility(scope)
    if not allowed:
        return []
    return list(User.objects.filter(id__in=allowed, is_active=True).order_by("first_name", "username")[:limit])
