from assistente_lplan.services.obra_entity import obra_display_name
from assistente_lplan.schemas import AssistantResponse
from assistente_lplan.services.obras_service import ObrasAssistantService
from mapa_obras.models import Obra
from trackhub.services.assistant_queries import (
    fila_stats_for_user,
    pendencias_abertas_qs,
    pendencias_vencidas_qs,
)


class TrackHubAssistantService:
    def __init__(self, user, scope):
        self.user = user
        self.scope = scope

    def _resolve_obra_id(self, entities: dict):
        project = ObrasAssistantService(self.scope)._resolve_project(entities)
        if not project:
            return None
        obra = Obra.objects.filter(project_id=project.id, ativa=True).first()
        return obra.pk if obra else None

    def _row_from_pendencia(self, p):
        resp = ""
        if p.responsavel_interno_id:
            resp = p.responsavel_interno.get_full_name() or p.responsavel_interno.username
        return {
            "titulo": (p.titulo or "")[:70],
            "obra": obra_display_name(p.obra) if p.obra_id else "-",
            "status": p.get_status_display() if hasattr(p, "get_status_display") else p.status,
            "prazo": p.prazo.strftime("%d/%m/%Y") if p.prazo else "-",
            "responsavel": resp[:50] or "-",
        }

    def consultar_pendencias(self, entities: dict) -> AssistantResponse:
        obra_id = self._resolve_obra_id(entities)
        qs = pendencias_abertas_qs(self.user, obra_id=obra_id)[:30]
        rows = [self._row_from_pendencia(p) for p in qs]

        if not rows:
            scope_note = f" na obra informada" if obra_id else " no seu escopo"
            return AssistantResponse(
                summary=f"Nenhuma pendencia TrackHub aberta{scope_note}.",
                badges=["TrackHub", "Sem dados"],
                alerts=[{"level": "info", "message": "A fila pode estar vazia ou fora do seu acesso."}],
                actions=[{"label": "Abrir TrackHub", "url": "/trackhub/", "style": "primary"}],
            )

        return AssistantResponse(
            summary=f"{len(rows)} pendencia(s) TrackHub abertas no escopo consultado.",
            cards=[{"title": "Abertas", "value": str(len(rows)), "tone": "warning"}],
            table={
                "caption": "Pendencias TrackHub",
                "columns": ["titulo", "obra", "status", "prazo", "responsavel"],
                "rows": rows,
            },
            badges=["TrackHub"],
            actions=[{"label": "Abrir TrackHub", "url": "/trackhub/", "style": "primary"}],
            links=[{"label": "Fila TrackHub", "url": "/trackhub/"}],
        )

    def pendencias_vencidas(self, entities: dict) -> AssistantResponse:
        obra_id = self._resolve_obra_id(entities)
        qs = pendencias_vencidas_qs(self.user)
        if obra_id:
            qs = qs.filter(obra_id=obra_id)
        rows = [self._row_from_pendencia(p) for p in qs[:30]]

        if not rows:
            return AssistantResponse(
                summary="Nenhuma pendencia TrackHub vencida no escopo.",
                badges=["TrackHub"],
                alerts=[{"level": "info", "message": "Prazos em dia ou sem acesso as obras."}],
            )

        return AssistantResponse(
            summary=f"{len(rows)} pendencia(s) TrackHub com prazo vencido.",
            cards=[{"title": "Vencidas", "value": str(len(rows)), "tone": "danger"}],
            table={
                "caption": "Pendencias vencidas",
                "columns": ["titulo", "obra", "status", "prazo", "responsavel"],
                "rows": rows,
            },
            badges=["TrackHub", "Vencidas"],
            alerts=[{"level": "error", "message": "Priorize pendencias com prazo ultrapassado."}],
            actions=[{"label": "Abrir TrackHub", "url": "/trackhub/", "style": "primary"}],
        )

    def resumo_fila(self, entities: dict) -> AssistantResponse:
        stats = fila_stats_for_user(self.user)
        return AssistantResponse(
            summary=(
                f"Fila TrackHub: {stats['abertas']} abertas, "
                f"{stats['urgentes_vencidas']} urgentes/vencidas, "
                f"{stats['etapas_pendentes']} etapas pendentes, "
                f"{stats['concluidas_mes']} concluidas no mes."
            ),
            cards=[
                {"title": "Abertas", "value": str(stats["abertas"]), "tone": "warning"},
                {"title": "Urgentes/vencidas", "value": str(stats["urgentes_vencidas"]), "tone": "danger"},
                {"title": "Etapas pendentes", "value": str(stats["etapas_pendentes"]), "tone": "info"},
                {"title": "Concluidas no mes", "value": str(stats["concluidas_mes"]), "tone": "info"},
            ],
            badges=["TrackHub", "Resumo fila"],
            actions=[{"label": "Abrir TrackHub", "url": "/trackhub/", "style": "primary"}],
            links=[{"label": "Calendario TrackHub", "url": "/trackhub/calendario/"}],
        )
