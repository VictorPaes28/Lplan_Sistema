from django.contrib.auth.models import User

from assistente_lplan.services.obra_entity import obra_display_name
from assistente_lplan.schemas import AssistantResponse
from assistente_lplan.services.obras_service import ObrasAssistantService
from core.models import Project
from impedimentos.services.assistant_queries import (
    resolve_obra_from_project,
    restricoes_criticas_queryset,
    restricoes_obra_queryset,
    restricoes_por_responsavel_queryset,
    stats_restricoes_escopo_projetos,
    stats_restricoes_por_obra,
)


class ImpedimentosAssistantService:
    def __init__(self, scope):
        self.scope = scope

    def _resolve_project(self, entities: dict):
        return ObrasAssistantService(self.scope)._resolve_project(entities)

    def _projects_escopo(self):
        qs = Project.objects.filter(is_active=True).order_by("code")
        if self.scope.role != "admin":
            if not self.scope.project_ids:
                return Project.objects.none()
            qs = qs.filter(id__in=self.scope.project_ids)
        return qs

    def consultar_restricoes_obra(self, entities: dict) -> AssistantResponse:
        project = self._resolve_project(entities)
        if not project:
            return AssistantResponse(
                summary="Informe a obra para consultar restricoes (impeditivos).",
                badges=["Restricoes"],
                alerts=[{"level": "warning", "message": "Cite o nome da obra ou selecione na sessao."}],
            )
        obra = resolve_obra_from_project(project)
        if not obra:
            return AssistantResponse(
                summary=f"A obra {obra_display_name(project)} nao tem obra de GestControll vinculada para restrições.",
                badges=["Restricoes"],
                alerts=[{"level": "info", "message": "Cadastre a obra no modulo de impeditivos."}],
            )

        stats = stats_restricoes_por_obra(obra)
        qs = restricoes_obra_queryset(obra).order_by("-prioridade", "prazo")[:25]
        rows = []
        for imp in qs:
            resp = ", ".join(
                (u.get_full_name() or u.username) for u in imp.responsaveis.all()[:3]
            ) or "Sem responsavel"
            rows.append(
                {
                    "titulo": (imp.titulo or "")[:80],
                    "prioridade": imp.get_prioridade_display(),
                    "prazo": imp.prazo.strftime("%d/%m/%Y") if imp.prazo else "-",
                    "status": imp.status.nome if imp.status else "-",
                    "responsavel": resp[:60],
                }
            )

        return AssistantResponse(
            summary=(
                f"Obra {obra_display_name(project)}: {stats['abertas']} restricao(oes) abertas, "
                f"{stats['vencidas']} vencidas, {stats['criticas']} criticas."
            ),
            cards=[
                {"title": "Abertas", "value": str(stats["abertas"]), "tone": "warning"},
                {"title": "Vencidas", "value": str(stats["vencidas"]), "tone": "danger"},
                {"title": "Criticas", "value": str(stats["criticas"]), "tone": "danger"},
            ],
            table={
                "caption": "Restricoes abertas (amostra)",
                "columns": ["titulo", "prioridade", "prazo", "status", "responsavel"],
                "rows": rows,
            },
            badges=["Restricoes", obra_display_name(project)],
            actions=[{"label": "Abrir Restricoes", "url": "/impedimentos/", "style": "primary"}],
            links=[{"label": "Gestao de Impeditivos", "url": "/impedimentos/"}],
        )

    def restricoes_criticas_escopo(self, entities: dict) -> AssistantResponse:
        cards_data = stats_restricoes_escopo_projetos(self._projects_escopo()[:30])
        total_crit = sum(c.get("criticas", 0) for c in cards_data)
        total_venc = sum(c.get("vencidas", 0) for c in cards_data)
        total_abertas = sum(c.get("abertas", 0) for c in cards_data)

        rows = []
        for c in sorted(cards_data, key=lambda x: (-x.get("criticas", 0), -x.get("vencidas", 0)))[:20]:
            if not c.get("has_obra"):
                continue
            rows.append(
                {
                    "obra": obra_display_name({"name": c.get("project_name"), "code": c.get("project_code")}),
                    "abertas": str(c["abertas"]),
                    "vencidas": str(c["vencidas"]),
                    "criticas": str(c["criticas"]),
                }
            )

        if not rows:
            return AssistantResponse(
                summary="Nenhuma restricao aberta encontrada no seu escopo de obras.",
                badges=["Restricoes", "Sem dados"],
                alerts=[{"level": "info", "message": "Verifique vinculo a projetos com modulo de impeditivos."}],
            )

        return AssistantResponse(
            summary=(
                f"No escopo: {total_abertas} restricoes abertas, "
                f"{total_venc} vencidas, {total_crit} criticas."
            ),
            cards=[
                {"title": "Obras com restricoes", "value": str(len(rows)), "tone": "warning"},
                {"title": "Vencidas (total)", "value": str(total_venc), "tone": "danger"},
                {"title": "Criticas (total)", "value": str(total_crit), "tone": "danger"},
            ],
            table={
                "caption": "Panorama de restricoes por obra",
                "columns": ["obra", "abertas", "vencidas", "criticas"],
                "rows": rows,
            },
            badges=["Restricoes", "Panorama"],
            actions=[{"label": "Abrir Restricoes", "url": "/impedimentos/", "style": "primary"}],
            links=[{"label": "Gestao de Impeditivos", "url": "/impedimentos/"}],
        )

    def restricoes_por_responsavel(self, entities: dict) -> AssistantResponse:
        project = self._resolve_project(entities)
        usuario_term = (entities.get("usuario") or "").strip()
        if not usuario_term:
            return AssistantResponse(
                summary="Informe o responsavel para listar restricoes atribuidas.",
                badges=["Restricoes"],
                alerts=[{"level": "warning", "message": "Ex.: restricoes do usuario Joao na obra SUNRISE."}],
            )
        if not project:
            return AssistantResponse(
                summary="Informe tambem a obra para filtrar restricoes por responsavel.",
                badges=["Restricoes"],
                alerts=[{"level": "warning", "message": "Cite o nome da obra na pergunta."}],
            )
        obra = resolve_obra_from_project(project)
        if not obra:
            return AssistantResponse(
                summary=f"A obra {obra_display_name(project)} nao tem cadastro de impeditivos vinculado.",
                badges=["Restricoes"],
            )

        qs = restricoes_por_responsavel_queryset(obra, usuario_term)[:25]
        rows = []
        for imp in qs:
            rows.append(
                {
                    "titulo": (imp.titulo or "")[:80],
                    "prioridade": imp.get_prioridade_display(),
                    "prazo": imp.prazo.strftime("%d/%m/%Y") if imp.prazo else "-",
                    "status": imp.status.nome if imp.status else "-",
                }
            )

        if not rows:
            return AssistantResponse(
                summary=f"Nenhuma restricao aberta atribuida a '{usuario_term}' na obra {obra_display_name(project)}.",
                badges=["Restricoes"],
                alerts=[{"level": "info", "message": "Confira o nome ou login do responsavel."}],
            )

        return AssistantResponse(
            summary=f"{len(rows)} restricao(oes) abertas atribuidas a '{usuario_term}' na obra {obra_display_name(project)}.",
            table={
                "caption": "Restricoes por responsavel",
                "columns": ["titulo", "prioridade", "prazo", "status"],
                "rows": rows,
            },
            badges=["Restricoes", obra_display_name(project)],
            actions=[{"label": "Abrir Restricoes", "url": "/impedimentos/", "style": "primary"}],
        )
