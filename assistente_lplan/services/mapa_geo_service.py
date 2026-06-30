from assistente_lplan.services.obra_entity import obra_display_name
from assistente_lplan.schemas import AssistantResponse
from assistente_lplan.services.obras_service import ObrasAssistantService
from core.models import ConstructionDiary
from mapa_geo.enrichment import get_map_alerts
from mapa_geo.models import GeoFeature
from mapa_geo.services import get_map_summary


class MapaGeoAssistantService:
    def __init__(self, scope):
        self.scope = scope

    def _resolve_project(self, entities: dict):
        return ObrasAssistantService(self.scope)._resolve_project(entities)

    def resumo_obra(self, entities: dict) -> AssistantResponse:
        project = self._resolve_project(entities)
        if not project:
            return AssistantResponse(
                summary="Informe a obra para consultar o mapa geografico.",
                badges=["Mapa Geo"],
                alerts=[{"level": "warning", "message": "Cite o nome da obra ou selecione na sessao."}],
            )

        summary = get_map_summary(project)
        total = summary.get("total", 0)
        if total == 0:
            return AssistantResponse(
                summary=f"Obra {obra_display_name(project)}: nenhum elemento geografico cadastrado no mapa.",
                badges=["Mapa Geo", obra_display_name(project)],
                alerts=[{"level": "info", "message": "Importe elementos ou vincule ao EAP/RDO."}],
                actions=[{"label": "Abrir Mapa Geografico", "url": "/mapa-geo/", "style": "primary"}],
            )

        pct = summary.get("overall_progress_pct", 0)
        return AssistantResponse(
            summary=(
                f"Mapa geografico da obra {obra_display_name(project)}: {total} elementos "
                f"({summary.get('points', 0)} pontos, {summary.get('segments', 0)} linhas, "
                f"{summary.get('areas', 0)} areas). Progresso geral: {pct:.1f}%."
            ),
            cards=[
                {"title": "Elementos", "value": str(total), "tone": "info"},
                {"title": "Marcadores GPS RDO", "value": str(summary.get("gps_markers", 0)), "tone": "info"},
                {"title": "Diarios c/ GPS", "value": str(summary.get("diaries_with_gps", 0)), "tone": "info"},
                {"title": "Progresso %", "value": f"{pct:.1f}", "tone": "info"},
            ],
            badges=["Mapa Geografico", obra_display_name(project)],
            actions=[{"label": "Abrir Mapa Geografico", "url": "/mapa-geo/", "style": "primary"}],
            links=[{"label": "Mapa Geografico", "url": "/mapa-geo/"}],
            raw_data={"map_summary": summary},
        )

    def alertas_obra(self, entities: dict) -> AssistantResponse:
        project = self._resolve_project(entities)
        if not project:
            return AssistantResponse(
                summary="Informe a obra para alertas do mapa geografico.",
                badges=["Mapa Geo"],
            )

        payload = get_map_alerts(project)
        items = payload.get("items") or payload.get("alerts") or []
        if isinstance(payload, dict) and not items and "items" not in payload:
            items = payload if isinstance(payload, list) else []

        rows = []
        for item in (items if isinstance(items, list) else [])[:20]:
            if not isinstance(item, dict):
                continue
            rows.append(
                {
                    "tipo": str(item.get("type", item.get("tipo", "-")))[:30],
                    "nome": str(item.get("name", item.get("nome", "-")))[:50],
                    "severidade": str(item.get("severity", item.get("severidade", "-")))[:20],
                    "detalhe": str(item.get("message", item.get("detalhe", "")))[:80],
                }
            )

        if not rows:
            return AssistantResponse(
                summary=f"Obra {obra_display_name(project)}: nenhum alerta ativo no mapa geografico.",
                badges=["Mapa Geo", obra_display_name(project)],
                alerts=[{"level": "info", "message": "Elementos sem bloqueio ou estagnacao detectada."}],
            )

        return AssistantResponse(
            summary=f"{len(rows)} alerta(s) no mapa geografico da obra {obra_display_name(project)}.",
            table={
                "caption": "Alertas do mapa geografico",
                "columns": ["tipo", "nome", "severidade", "detalhe"],
                "rows": rows,
            },
            badges=["Mapa Geo", "Alertas"],
            actions=[{"label": "Abrir Mapa Geografico", "url": "/mapa-geo/", "style": "primary"}],
        )

    def marcadores_gps_rdo(self, entities: dict) -> AssistantResponse:
        project = self._resolve_project(entities)
        if not project:
            return AssistantResponse(
                summary="Informe a obra para marcadores GPS de RDO.",
                badges=["Mapa Geo"],
            )

        diaries = (
            ConstructionDiary.objects.filter(project=project, geolocation_data__isnull=False)
            .exclude(geolocation_data={})
            .order_by("-date")[:20]
        )
        rows = []
        for d in diaries:
            geo = d.geolocation_data or {}
            lat = geo.get("lat") or geo.get("latitude") or "-"
            lng = geo.get("lng") or geo.get("longitude") or "-"
            rows.append(
                {
                    "data": d.date.strftime("%d/%m/%Y"),
                    "status": d.get_status_display() if hasattr(d, "get_status_display") else d.status,
                    "lat": str(lat)[:16],
                    "lng": str(lng)[:16],
                }
            )

        gps_features = GeoFeature.objects.filter(project=project, is_active=True, diary__isnull=False).count()

        if not rows and gps_features == 0:
            return AssistantResponse(
                summary=f"Obra {obra_display_name(project)}: nenhum marcador GPS de RDO no mapa.",
                badges=["Mapa Geo"],
            )

        return AssistantResponse(
            summary=(
                f"Obra {obra_display_name(project)}: {len(rows)} RDO(s) recentes com geolocalizacao; "
                f"{gps_features} elemento(s) GPS no mapa."
            ),
            cards=[
                {"title": "RDOs c/ GPS", "value": str(len(rows)), "tone": "info"},
                {"title": "Elementos GPS", "value": str(gps_features), "tone": "info"},
            ],
            table={
                "caption": "Ultimos RDOs com GPS",
                "columns": ["data", "status", "lat", "lng"],
                "rows": rows,
            },
            badges=["Mapa Geo", "GPS RDO"],
            actions=[{"label": "Abrir Mapa Geografico", "url": "/mapa-geo/", "style": "primary"}],
        )
