from assistente_lplan.schemas import AssistantResponse
from core.models import ConstructionDiary, DiaryStatus, Project
from gestao_aprovacao.models import WorkOrder
from suprimentos.models import ItemMapa

from .messages import MessageCatalog
from .radar_obra_service import RadarObraService


class CrossDomainAssistantService:
    def __init__(self, scope):
        self.scope = scope
        self.radar_service = None

    def gargalos_obra(self, entities: dict) -> AssistantResponse:
        project = self._resolve_project(entities)
        if not project:
            msg = MessageCatalog.resolve("assistant.cross.project_missing", {"domain": "cross_domain"})
            return AssistantResponse(
                summary=msg["text"],
                alerts=[{"level": "warning", "message": msg["next_steps"][0]}],
                raw_data={"message_code": msg["code"], "message_kind": msg["kind"]},
            )

        diarios_abertos = ConstructionDiary.objects.filter(project=project).exclude(status=DiaryStatus.APROVADO).count()
        aprov_pend = WorkOrder.objects.filter(obra__project=project, status="pendente").count()
        sem_aloc = ItemMapa.objects.filter(
            obra__codigo_sienge=project.code,
            quantidade_planejada__gt=0,
            alocacoes__isnull=True,
        ).count()

        alerts = []
        if diarios_abertos:
            alerts.append({"level": "warning", "message": "Ha diarios em aberto no fluxo da obra."})
        if aprov_pend:
            alerts.append({"level": "error", "message": "Ha pedidos pendentes de aprovacao no GestControll."})
        if sem_aloc:
            alerts.append({"level": "error", "message": "Ha itens sem alocacao no Mapa de Suprimentos."})

        if not alerts:
            msg = MessageCatalog.resolve("assistant.cross.bottlenecks_empty", {"domain": "cross_domain", "obra": project.code})
            return AssistantResponse(
                summary=msg["text"],
                badges=["Sem dados suficientes"],
                alerts=[{"level": "info", "message": msg["next_steps"][0]}],
                raw_data={"message_code": msg["code"], "message_kind": msg["kind"]},
            )

        response = AssistantResponse(
            summary=f"Principais gargalos da obra {project.code} consolidados entre Diario, Aprovacao e Suprimentos.",
            cards=[
                {"title": "Diarios em aberto", "value": str(diarios_abertos), "tone": "warning"},
                {"title": "Aprovacoes pendentes", "value": str(aprov_pend), "tone": "warning"},
                {"title": "Itens sem alocacao", "value": str(sem_aloc), "tone": "danger"},
            ],
            alerts=alerts,
            badges=["Cross-domain", "Gargalos"],
            actions=[
                {"label": "Abrir diario", "url": "/reports/", "style": "secondary"},
                {"label": "Abrir pedidos", "url": "/gestao/pedidos/", "style": "secondary"},
                {"label": "Abrir mapa", "url": "/engenharia/mapa/", "style": "secondary"},
            ],
            links=[
                {"label": "Diario", "url": "/reports/"},
                {"label": "GestControll", "url": "/gestao/pedidos/"},
                {"label": "Mapa", "url": "/engenharia/mapa/"},
            ],
        )
        return self._attach_radar(response, project)

    def _resolve_project(self, entities: dict):
        project_id = entities.get("project_id")
        if project_id:
            try:
                pid = int(project_id)
            except (TypeError, ValueError):
                pid = None
            if pid:
                qs_by_id = Project.objects.filter(is_active=True, id=pid)
                if self.scope.role != "admin":
                    qs_by_id = qs_by_id.filter(id__in=self.scope.project_ids)
                p = qs_by_id.first()
                if p:
                    return p

        term = (entities.get("obra") or "").strip()
        qs = Project.objects.filter(is_active=True)
        if self.scope.role != "admin":
            qs = qs.filter(id__in=self.scope.project_ids)
        if term:
            project = qs.filter(code__icontains=term).first() or qs.filter(name__icontains=term).first()
            return project
        return qs.order_by("-created_at").first()

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

