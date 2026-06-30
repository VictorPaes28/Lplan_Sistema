"""
Sugestões de perguntas para a home do Assistente — contextualizadas à obra da sessão
e ao papel, evitando exemplos genéricos (ex.: 'bloco C') que não são da realidade do usuário.
"""
from __future__ import annotations

from datetime import timedelta

from django.utils import timezone

from accounts.groups import GRUPOS
from assistente_lplan.services.clarification import accessible_projects_for_scope
from assistente_lplan.services.obra_entity import obra_display_name
from assistente_lplan.services.permissions import (
    MODULE_APROVACOES,
    MODULE_CONTROLE,
    MODULE_IMPEDIMENTOS,
    MODULE_MAPA_GEO,
    MODULE_RH,
    MODULE_TRACKHUB,
    AssistantPermissionService,
)
from assistente_lplan.services.intents import (
    INTENT_DESEMPENHO_EQUIPE_GEST,
    INTENT_FILA_ATRASO_APROVACOES,
    INTENT_LISTAR_FRENTES_OBRA,
)

from core.models import Project


def _user_can_use_project(request, project, scope, perm: AssistantPermissionService) -> bool:
    if not project:
        return False
    if scope.role == "admin":
        return True
    return perm.can_access_project_id(project.id, scope)


def _optional_module_groups(perm: AssistantPermissionService, obra: str | None = None) -> list[dict]:
    """Blocos extras por módulo — só entram se o usuário tiver permissão."""
    groups: list[dict] = []
    obra_na = f" na obra {obra}" if obra else " no meu escopo"
    obra_da = f" da obra {obra}" if obra else " no meu escopo"

    if perm.can_access_module(MODULE_IMPEDIMENTOS):
        groups.append(
            {
                "title": "Restrições",
                "accent": "restrict",
                "questions": [
                    f"Restricoes abertas{obra_na}",
                    "Tem restricao critica ou vencida?",
                    "Restricoes sem responsavel",
                ],
            }
        )

    if perm.can_access_module(MODULE_TRACKHUB):
        groups.append(
            {
                "title": "TrackHub",
                "accent": "track",
                "questions": [
                    f"Pendencias abertas{obra_na}",
                    "Tem pendencia vencida no meu escopo?",
                    "Resumo da fila TrackHub",
                ],
            }
        )

    if perm.can_access_module(MODULE_CONTROLE):
        groups.append(
            {
                "title": "Mapa de Controle",
                "accent": "control",
                "questions": [
                    f"Qual o percentual do mapa de controle{obra_da}?",
                    f"Ambientes operacionais{obra_da}",
                ],
            }
        )

    if perm.can_access_module(MODULE_MAPA_GEO):
        groups.append(
            {
                "title": "Mapa Geográfico",
                "accent": "geo",
                "questions": [
                    f"Elementos geograficos{obra_da}",
                    f"Tem alerta no mapa geografico{obra_da}?",
                ],
            }
        )

    if perm.can_access_module(MODULE_RH):
        groups.append(
            {
                "title": "RH / DP",
                "accent": "hr",
                "questions": [
                    "Quantas admissoes estao em andamento?",
                    "Documentos vencendo nos proximos 30 dias",
                    "Contratos em periodo de experiencia",
                ],
            }
        )

    aprov_questions: list[str] = []
    if perm.can_run_intent(INTENT_FILA_ATRASO_APROVACOES):
        aprov_questions.append("Pedidos na fila ha mais de 7 dias")
    if perm.can_run_intent(INTENT_DESEMPENHO_EQUIPE_GEST):
        aprov_questions.append("Desempenho dos aprovadores")
    if perm.can_access_module(MODULE_APROVACOES) and perm.can_run_intent(INTENT_LISTAR_FRENTES_OBRA):
        aprov_questions.append(
            f"Frentes ativas da obra {obra}" if obra else "Frentes ativas no meu escopo"
        )
    if aprov_questions:
        groups.append(
            {
                "title": "Aprovações avançadas",
                "accent": "flow",
                "questions": aprov_questions,
            }
        )

    return groups


def build_assistant_home_context(request) -> dict:
    """
    Retorna:
      - active_project: {id, code, name} | None
      - suggestion_groups: [{"title": str, "questions": [str, ...]}, ...]
      - welcome_chat: dict — conteúdo estruturado do primeiro bloco do chat (título, modo, textos)
      - welcome_lines: [str] — texto plano do chat (compatível com versões antigas / fallback)
      - selected_project_id: int | None — para o JS enviar em contexto
      - available_projects: list[{id, code, name}] — obras escolhíveis no painel lateral
    """
    perm = AssistantPermissionService(request.user)
    scope = perm.build_scope()
    project = None
    pid = request.session.get("assistente_project_id")
    if pid:
        try:
            raw = Project.objects.get(pk=int(pid), is_active=True)
        except (Project.DoesNotExist, TypeError, ValueError):
            request.session.pop("assistente_project_id", None)
            request.session.modified = True
        else:
            project = raw if _user_can_use_project(request, raw, scope, perm) else None
            if project is None:
                request.session.pop("assistente_project_id", None)
                request.session.modified = True
    available_projects: list[dict] = []

    accessible = accessible_projects_for_scope(scope, limit=80)

    if accessible:
        available_projects = accessible[:50]

    user = request.user
    hoje = timezone.localdate().strftime("%d/%m/%Y")
    ontem = (timezone.localdate() - timedelta(days=1)).strftime("%d/%m/%Y")
    groups = []

    is_gestao_user = user.groups.filter(
        name__in=[GRUPOS.APROVADOR, GRUPOS.SOLICITANTE, GRUPOS.RESPONSAVEL_EMPRESA]
    ).exists()

    if project:
        obra = obra_display_name(project)
        # Ordem pensada para uso real: (1) decisão / risco, (2) campo ou aprovações conforme perfil,
        # (3) materiais, (4) registro diário, (5) pedidos amplos quando couber.
        # JS envia selected_project_id; citar outra obra na pergunta prevalece sobre o painel.

        grupo_visao = {
            "title": "Visão e pendências",
            "accent": "exec",
            "questions": [
                f"Visao integrada da obra {obra} (Diario, Mapa e Gestao)",
                f"Quais pendencias operacionais na obra {obra}?",
                f"Quais gargalos na obra {obra}?",
                "Resumo operacional da obra atual",
            ],
        }
        grupo_mapa = {
            "title": "Mapa de suprimentos",
            "accent": "supply",
            "questions": [
                f"Itens sem alocacao no mapa da obra {obra}",
                f"Onde esta o insumo cimento na obra {obra}?",
                "Localizar um insumo pelo nome ou codigo nesta obra",
                "Como esta um apartamento ou bloco no mapa? (indique o nome do local na pergunta)",
            ],
        }
        grupo_rdo = {
            "title": "Diário de obra (RDO)",
            "accent": "diary",
            "questions": [
                f"RDO do dia {hoje} na obra {obra}",
                f"RDO do dia {ontem} na obra {obra}",
                f"PDF dos ultimos 15 dias de RDO da obra {obra}",
                "PDF consolidado do diario dos ultimos 7 dias nesta obra",
            ],
        }
        grupo_gestao = {
            "title": "GestControll (pedidos)",
            "accent": "flow",
            "questions": [
                f"Aprovacoes pendentes na obra {obra}",
                f"Solicitacoes reprovadas na obra {obra}",
                "Aprovacoes pendentes no meu acesso (todas as obras visiveis)",
            ],
        }
        grupo_pedidos_geral = {
            "title": "Pedidos no seu acesso",
            "accent": "flow",
            "questions": [
                "Aprovacoes pendentes no meu acesso",
                "Solicitacoes reprovadas recentemente no GestControll",
            ],
        }

        if is_gestao_user:
            groups = [grupo_visao, grupo_gestao, grupo_mapa, grupo_rdo]
            groups.extend(_optional_module_groups(perm, obra))
        else:
            groups = [grupo_visao, grupo_mapa, grupo_rdo]
            groups.extend(_optional_module_groups(perm, obra))
            groups.append(grupo_pedidos_geral)

        if is_gestao_user:
            ordem_hint = (
                "Ordem sugerida na barra lateral: visão e risco → GestControll → mapa → diário. "
                "Perguntas em 'meu acesso' podem incluir várias obras."
            )
        else:
            ordem_hint = (
                "Ordem sugerida na barra lateral: visão e risco → mapa → diário → pedidos no seu acesso. "
                "Perguntas em 'meu acesso' podem incluir várias obras."
            )
        welcome_chat = {
            "mode": "project",
            "title": "Comece por aqui",
            "project_name": obra,
            "hint_other_project": (
                "Outro projeto? Cite o nome da obra na pergunta; caso contrário uso a obra do painel."
            ),
            "order_detail": ordem_hint,
        }
        welcome_lines = [
            f"Pergunte sobre a obra {obra} ou use as sugestões ao lado.",
            welcome_chat["hint_other_project"],
        ]
    else:
        if available_projects:
            grupo_visao = {
                "title": "Visão e pendências",
                "accent": "exec",
                "questions": [
                    "Visao integrada das obras do meu acesso (Diario, Mapa e Gestao)",
                    "Quais pendencias operacionais no meu escopo?",
                    "Quais gargalos nas obras do meu acesso?",
                    "Resumo operacional das obras visiveis",
                ],
            }
            grupo_mapa = {
                "title": "Mapa de suprimentos",
                "accent": "supply",
                "questions": [
                    "Itens sem alocacao no mapa das obras do meu acesso",
                    "Onde esta um insumo no meu escopo? (cite o nome na pergunta)",
                    "Localizar um insumo pelo nome ou codigo",
                    "Como esta um apartamento ou bloco no mapa? (indique o nome do local na pergunta)",
                ],
            }
            grupo_rdo = {
                "title": "Diário de obra (RDO)",
                "accent": "diary",
                "questions": [
                    f"RDO do dia {hoje} (cite a obra na pergunta se quiser uma so)",
                    f"RDO do dia {ontem} (cite a obra na pergunta se quiser uma so)",
                    "PDF dos ultimos 15 dias de RDO (cite a obra na pergunta)",
                    "PDF consolidado do diario dos ultimos 7 dias (cite a obra na pergunta)",
                ],
            }
            grupo_gestao = {
                "title": "GestControll (pedidos)",
                "accent": "flow",
                "questions": [
                    "Aprovacoes pendentes no meu acesso (todas as obras visiveis)",
                    "Solicitacoes reprovadas no meu acesso",
                    "Aprovacoes pendentes no meu acesso",
                ],
            }
            grupo_pedidos_geral = {
                "title": "Pedidos no seu acesso",
                "accent": "flow",
                "questions": [
                    "Aprovacoes pendentes no meu acesso",
                    "Solicitacoes reprovadas recentemente no GestControll",
                ],
            }
            if is_gestao_user:
                groups = [grupo_visao, grupo_gestao, grupo_mapa, grupo_rdo]
                groups.extend(_optional_module_groups(perm))
            else:
                groups = [grupo_visao, grupo_mapa, grupo_rdo]
                groups.extend(_optional_module_groups(perm))
                groups.append(grupo_pedidos_geral)
            welcome_chat = {
                "mode": "all_projects",
                "title": "Comece por aqui",
                "lines": [
                    "Pergunte sobre todas as obras do seu acesso ou cite uma obra pelo nome.",
                    "Use as sugestões ao lado ou digite abaixo. Para focar em uma obra, escolha na lista ao lado.",
                ],
            }
            welcome_lines = list(welcome_chat["lines"])
        else:
            groups = [
                {
                    "title": "Acesso",
                    "accent": "exec",
                    "questions": [
                        "Contate o gestor para vincular seu usuario a um projeto no Diario de Obra.",
                    ],
                }
            ]
            welcome_chat = {
                "mode": "no_access",
                "title": "Sem projeto vinculado",
                "lines": [
                    "Nenhum projeto vinculado a este usuário ainda.",
                    "Quando houver acesso, as sugestões serão montadas pelo nome da obra.",
                ],
            }
            welcome_lines = list(welcome_chat["lines"])

    # Lista plana para compatibilidade com JS que itera botões (primeiro grupo primeiro, etc.)
    flat: list[str] = []
    for g in groups:
        flat.extend(g["questions"])

    # Todos os temas visíveis na sidebar (scroll se necessário)
    suggestion_groups_primary = groups
    suggestion_groups_more: list[dict] = []

    return {
        "active_project": (
            {
                "id": project.id,
                "code": project.code,
                "name": project.name or project.code,
                "display_name": obra_display_name(project),
            }
            if project
            else None
        ),
        "suggestion_groups": groups,
        "suggestion_groups_primary": suggestion_groups_primary,
        "suggestion_groups_more": suggestion_groups_more,
        "suggested_questions": flat,
        "welcome_chat": welcome_chat,
        "welcome_lines": welcome_lines,
        "selected_project_id": project.id if project else None,
        "available_projects": available_projects,
    }
