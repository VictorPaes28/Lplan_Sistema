from django.db.models import Count, Q

from assistente_lplan.schemas import AssistantResponse
from core.kpi_queries import (
    count_diarios_nao_aprovados,
    count_itens_sem_alocacao_efetiva,
    count_pedidos_pendentes,
)
from core.models import ConstructionDiary, DiaryStatus, Project
from gestao_aprovacao.models import WorkOrder

from .messages import MessageCatalog
from .obra_entity import obra_display_name, resolve_project_from_entities
from .radar_obra_service import RadarObraService


class ObrasAssistantService:
    def __init__(self, scope):
        self.scope = scope
        self.radar_service = None

    def listar_pendencias_obra(self, entities: dict) -> AssistantResponse:
        project = self._resolve_project(entities)
        if not project:
            msg = MessageCatalog.resolve("assistant.obras.project_missing", {"domain": "obras"})
            return AssistantResponse(
                summary=msg["text"],
                alerts=[{"level": "warning", "message": msg["next_steps"][0]}],
                raw_data={"message_code": msg["code"], "message_kind": msg["kind"]},
            )

        diarios_pend = count_diarios_nao_aprovados(project)
        pedidos_pend = count_pedidos_pendentes(project)
        itens_sem_aloc = count_itens_sem_alocacao_efetiva(project)

        if diarios_pend == 0 and pedidos_pend == 0 and itens_sem_aloc == 0:
            msg = MessageCatalog.resolve(
                "assistant.obras.pending_empty", {"domain": "obras", "obra": obra_display_name(project)}
            )
            return AssistantResponse(
                summary=msg["text"],
                badges=["Sem dados suficientes"],
                alerts=[{"level": "info", "message": msg["next_steps"][0]}],
                raw_data={"project_id": project.id, "message_code": msg["code"], "message_kind": msg["kind"]},
            )

        response = AssistantResponse(
            summary=f"Pendencias consolidadas da obra {obra_display_name(project)}.",
            cards=[
                {"title": "Diarios pendentes", "value": str(diarios_pend), "tone": "warning"},
                {"title": "Aprovacoes pendentes", "value": str(pedidos_pend), "tone": "warning"},
                {"title": "Itens sem alocacao", "value": str(itens_sem_aloc), "tone": "danger"},
            ],
            badges=["Obra", "Pendencias"],
            alerts=(
                [{"level": "warning", "message": "Existem pendencias operacionais nesta obra."}]
                if any([diarios_pend, pedidos_pend, itens_sem_aloc])
                else []
            ),
            actions=[
                {"label": "Abrir diario", "url": "/reports/", "style": "secondary"},
                {"label": "Abrir GestControll", "url": "/gestao/pedidos/", "style": "secondary"},
                {"label": "Abrir mapa", "url": "/engenharia/mapa/", "style": "secondary"},
            ],
            links=[
                {"label": "Diario", "url": "/reports/"},
                {"label": "GestControll", "url": "/gestao/pedidos/"},
                {"label": "Mapa", "url": "/engenharia/mapa/"},
            ],
            raw_data={"project_id": project.id},
        )
        return self._attach_radar(response, project)

    def resumo_obra(self, entities: dict) -> AssistantResponse:
        project = self._resolve_project(entities)
        if not project:
            msg = MessageCatalog.resolve("assistant.obras.summary_project_missing", {"domain": "obras"})
            return AssistantResponse(
                summary=msg["text"],
                raw_data={"message_code": msg["code"], "message_kind": msg["kind"]},
            )

        diario_agg = ConstructionDiary.objects.filter(project=project).aggregate(
            total_diarios=Count("id"),
            diarios_aprovados=Count("id", filter=Q(status=DiaryStatus.APROVADO)),
        )
        pedidos_agg = WorkOrder.objects.filter(obra__project=project).aggregate(
            total_pedidos=Count("id"),
            pendentes_pedido=Count("id", filter=Q(status="pendente")),
            reprovados=Count("id", filter=Q(status="reprovado")),
        )

        total_diarios = diario_agg.get("total_diarios") or 0
        diarios_aprovados = diario_agg.get("diarios_aprovados") or 0
        total_pedidos = pedidos_agg.get("total_pedidos") or 0
        pendentes_pedido = pedidos_agg.get("pendentes_pedido") or 0
        reprovados = pedidos_agg.get("reprovados") or 0

        rows = [
            {"indicador": "Diarios totais", "valor": total_diarios},
            {"indicador": "Diarios aprovados", "valor": diarios_aprovados},
            {"indicador": "Pedidos totais", "valor": total_pedidos},
            {"indicador": "Pedidos pendentes", "valor": pendentes_pedido},
            {"indicador": "Pedidos reprovados", "valor": reprovados},
        ]
        if total_diarios == 0 and total_pedidos == 0:
            msg = MessageCatalog.resolve(
                "assistant.obras.summary_empty", {"domain": "obras", "obra": obra_display_name(project)}
            )
            return AssistantResponse(
                summary=msg["text"],
                badges=["Sem dados suficientes"],
                alerts=[{"level": "warning", "message": msg["next_steps"][0]}],
                raw_data={"project_id": project.id, "message_code": msg["code"], "message_kind": msg["kind"]},
            )

        taxa_aprov = int((diarios_aprovados / total_diarios) * 100) if total_diarios else 0
        response = AssistantResponse(
            summary=f"Resumo operacional da obra {obra_display_name(project)} pronto para decisao.",
            cards=[
                {"title": "Taxa de aprovacao diario", "value": f"{taxa_aprov:.1f}%", "tone": "info"},
                {"title": "Pedidos pendentes", "value": str(pendentes_pedido), "tone": "warning"},
                {"title": "Pedidos reprovados", "value": str(reprovados), "tone": "danger"},
            ],
            table={
                "caption": f"Resumo da obra {obra_display_name(project)}",
                "columns": ["indicador", "valor"],
                "rows": rows,
            },
            badges=["Resumo da Obra"],
            actions=[{"label": "Abrir obra no diario", "url": "/reports/", "style": "primary"}],
            links=[
                {"label": "Relatorios", "url": "/reports/"},
                {"label": "Pedidos", "url": "/gestao/pedidos/"},
            ],
        )
        return self._attach_radar(response, project)

    def _resolve_project(self, entities: dict):
        return resolve_project_from_entities(entities, self.scope, allow_default=True)

    def _attach_radar(self, response: AssistantResponse, project: Project) -> AssistantResponse:
        radar = RadarObraService(project).build()
        response.radar_score = radar.score
        response.risk_level = radar.level
        response.trend = radar.trend
        response.causes = radar.causes
        response.recommended_action = radar.recommended_action
        response.secondary_actions = radar.secondary_actions
        response.cards = list(response.cards) + list(radar.cards)
        response.timeline = list(response.timeline) + list(radar.timeline)
        response.alerts = list(response.alerts) + list(radar.alerts)
        response.actions = list(response.actions) + [radar.recommended_action] + list(radar.secondary_actions)
        response.links = list(response.links) + list(radar.links)
        response.raw_data.update({"radar": radar.raw_components})
        return response

