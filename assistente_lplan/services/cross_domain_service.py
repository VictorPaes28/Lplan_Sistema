from assistente_lplan.schemas import AssistantResponse
from core.kpi_queries import (
    count_diarios_nao_aprovados,
    count_itens_sem_alocacao_efetiva,
    count_pedidos_pendentes,
)
from core.models import Project

from .llm_provider import LLMProvider
from .messages import MessageCatalog
from .radar_obra_service import RadarObraService, RadarResult


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

        diarios_abertos = count_diarios_nao_aprovados(project)
        aprov_pend = count_pedidos_pendentes(project)
        sem_aloc = count_itens_sem_alocacao_efetiva(project)

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

    def inteligencia_integrada(self, entities: dict) -> AssistantResponse:
        """Visao consolidada da obra: radar numerico + narrativa (LLM) ancorada nos mesmos fatos."""
        project = self._resolve_project(entities)
        if not project:
            msg = MessageCatalog.resolve("assistant.cross.project_missing", {"domain": "cross_domain"})
            return AssistantResponse(
                summary=msg["text"],
                alerts=[{"level": "warning", "message": msg["next_steps"][0]}],
                raw_data={"message_code": msg["code"], "message_kind": msg["kind"]},
            )

        radar = RadarObraService(project).build()
        facts = self._facts_for_narrative(project, radar)
        llm = LLMProvider()
        narrative = llm.narrate_obra_intelligence(facts)
        used_llm = bool(narrative)
        summary = narrative or self._fallback_inteligencia_text(project, radar)

        response = AssistantResponse(
            summary=summary,
            badges=["Inteligencia integrada", "Obra", "Radar"],
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
            raw_data={
                "inteligencia": True,
                "narrative_from_llm": used_llm,
                "project_id": project.id,
            },
        )
        return self._apply_radar_instance(response, radar)

    @staticmethod
    def _facts_for_narrative(project: Project, radar: RadarResult) -> dict:
        rc = radar.raw_components or {}
        facts = {
            "codigo_obra": project.code,
            "nome_obra": project.name,
            "score_radar": radar.score,
            "nivel_risco": radar.level,
            "tendencia": radar.trend,
            "principais_causas": list(radar.causes or []),
            "alertas": [a.get("message", str(a)) for a in (radar.alerts or []) if isinstance(a, dict)][:12],
        }
        for key in ("suprimentos", "approvals", "diary", "history"):
            block = rc.get(key)
            if isinstance(block, dict) and block.get("cause"):
                facts[f"detalhe_{key}"] = block.get("cause", "")
        return facts

    @staticmethod
    def _fallback_inteligencia_text(project: Project, radar: RadarResult) -> str:
        causas = "; ".join(radar.causes or []) or "Sem causas ranqueadas."
        return (
            f"Obra {project.code} ({project.name}): score {radar.score}, risco {radar.level}, "
            f"tendencia {radar.trend}. Pontos: {causas}"
        )

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
        return self._apply_radar_instance(response, radar)

    def _apply_radar_instance(self, response: AssistantResponse, radar: RadarResult) -> AssistantResponse:
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

