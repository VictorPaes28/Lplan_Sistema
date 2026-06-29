"""
Sugestões de perguntas para a home do Assistente — contextualizadas à obra da sessão
e ao papel, evitando exemplos genéricos (ex.: 'bloco C') que não são da realidade do usuário.
"""
from __future__ import annotations

from datetime import timedelta

from django.utils import timezone

from accounts.groups import GRUPOS
from assistente_lplan.services.clarification import accessible_projects_for_scope
from assistente_lplan.services.permissions import AssistantPermissionService
from core.frontend_views import get_selected_project
from core.models import Project


def _user_can_use_project(request, project, scope, perm: AssistantPermissionService) -> bool:
    if not project:
        return False
    if scope.role == "admin":
        return True
    return perm.can_access_project_id(project.id, scope)


def build_assistant_home_context(request) -> dict:
    """
    Retorna:
      - active_project: {id, code, name} | None
      - suggestion_groups: [{"title": str, "questions": [str, ...]}, ...]
      - welcome_chat: dict — conteúdo estruturado do primeiro bloco do chat (título, modo, textos)
      - welcome_lines: [str] — texto plano do chat (compatível com versões antigas / fallback)
      - selected_project_id: int | None — para o JS enviar em contexto
      - persist_session_project: bool — gravar selected_project_id na sessão (obra única inferida)
      - available_projects: list[{id, code, name}] — obras escolhíveis quando não há sessão e há várias
    """
    perm = AssistantPermissionService(request.user)
    scope = perm.build_scope()
    raw = get_selected_project(request)
    project = raw if _user_can_use_project(request, raw, scope, perm) else None
    persist_session_project = False
    available_projects: list[dict] = []

    accessible = accessible_projects_for_scope(scope, limit=80)

    # Sem sessão válida: uma obra no escopo → usamos como padrão (evita “nenhuma obra” sem necessidade)
    if project is None:
        if len(accessible) == 1:
            project = Project.objects.filter(is_active=True, id=accessible[0]["id"]).first()
            if project:
                persist_session_project = True

    # Mais de uma obra: manter lista no contexto mesmo com sessão já definida, para o painel permitir trocar.
    if len(accessible) > 1:
        available_projects = accessible[:50]

    user = request.user
    hoje = timezone.localdate().strftime("%d/%m/%Y")
    ontem = (timezone.localdate() - timedelta(days=1)).strftime("%d/%m/%Y")
    groups = []

    is_gestao_user = user.groups.filter(
        name__in=[GRUPOS.APROVADOR, GRUPOS.SOLICITANTE, GRUPOS.RESPONSAVEL_EMPRESA]
    ).exists()

    if project:
        code = project.code
        nome_curto = (project.name or code)[:48]
        # Ordem pensada para uso real: (1) decisão / risco, (2) campo ou aprovações conforme perfil,
        # (3) materiais, (4) registro diário, (5) pedidos amplos quando couber.
        # JS envia selected_project_id; citar outra obra na pergunta prevalece sobre o painel.

        grupo_visao = {
            "title": "Visão e pendências",
            "accent": "exec",
            "questions": [
                f"Visao integrada da obra {code} (Diario, Mapa e Gestao)",
                f"Quais pendencias operacionais na obra {code}?",
                f"Quais gargalos na obra {code}?",
                "Resumo operacional da obra atual",
            ],
        }
        grupo_mapa = {
            "title": "Mapa de suprimentos",
            "accent": "supply",
            "questions": [
                f"Itens sem alocacao no mapa da obra {code}",
                f"Onde esta o insumo cimento na obra {code}?",
                "Localizar um insumo pelo nome ou codigo nesta obra",
                "Como esta um apartamento ou bloco no mapa? (indique o nome do local na pergunta)",
            ],
        }
        grupo_rdo = {
            "title": "Diário de obra (RDO)",
            "accent": "diary",
            "questions": [
                f"RDO do dia {hoje} na obra {code}",
                f"RDO do dia {ontem} na obra {code}",
                f"PDF dos ultimos 15 dias de RDO da obra {code}",
                "PDF consolidado do diario dos ultimos 7 dias nesta obra",
            ],
        }
        grupo_gestao = {
            "title": "GestControll (pedidos)",
            "accent": "flow",
            "questions": [
                f"Aprovacoes pendentes na obra {code}",
                f"Solicitacoes reprovadas na obra {code}",
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
            # Aprovadores / gestão: prioriza fila de pedidos logo após a visão consolidada.
            groups = [grupo_visao, grupo_gestao, grupo_mapa, grupo_rdo]
        else:
            # Campo / engenharia: mapa e RDO logo após visão; pedidos por último (escopo amplo).
            groups = [grupo_visao, grupo_mapa, grupo_rdo, grupo_pedidos_geral]

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
            "project_code": code,
            "project_name": nome_curto,
            "hint_other_project": (
                "Outro projeto? Cite só o código na pergunta; caso contrário uso a obra do painel."
            ),
            "order_detail": ordem_hint,
        }
        welcome_lines = [
            f"Pergunte sobre a obra {code} ({nome_curto}) ou use as sugestões ao lado.",
            welcome_chat["hint_other_project"],
        ]
    else:
        if available_projects:
            groups = [
                {
                    "title": "Enquanto não escolhe a obra no painel",
                    "accent": "exec",
                    "questions": [
                        "Aprovacoes pendentes no meu acesso",
                        "Visao integrada da obra (ex.: diga obra 260 ou o codigo do projeto)",
                        "Gargalos na obra (cite o codigo do projeto na pergunta)",
                    ],
                },
            ]
            welcome_chat = {
                "mode": "pick_project",
                "title": "Escolha o contexto",
                "lines": [
                    "Várias obras no seu acesso: escolha uma ao lado ou cite o código na pergunta.",
                    "A escolha no painel vale para Diário, Mapa e GestControll.",
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
                    "Quando houver acesso, as sugestões serão montadas pelo código da obra.",
                ],
            }
            welcome_lines = list(welcome_chat["lines"])

    # Lista plana para compatibilidade com JS que itera botões (primeiro grupo primeiro, etc.)
    flat: list[str] = []
    for g in groups:
        flat.extend(g["questions"])

    # Sidebar: primeiros 3 temas visíveis; demais em "Mais temas" (menos peso visual)
    suggestion_groups_primary = groups[:3]
    suggestion_groups_more = groups[3:]

    return {
        "active_project": (
            {"id": project.id, "code": project.code, "name": project.name or project.code} if project else None
        ),
        "suggestion_groups": groups,
        "suggestion_groups_primary": suggestion_groups_primary,
        "suggestion_groups_more": suggestion_groups_more,
        "suggested_questions": flat,
        "welcome_chat": welcome_chat,
        "welcome_lines": welcome_lines,
        "selected_project_id": project.id if project else None,
        "persist_session_project": persist_session_project,
        "available_projects": available_projects,
    }
