from assistente_lplan.services.obra_entity import obra_display_name
from assistente_lplan.schemas import AssistantResponse
from assistente_lplan.services.obras_service import ObrasAssistantService
from mapa_obras.models import Obra
from painel_operacional.models import AmbienteOperacional, AmbienteTipo, VersaoEstado
from suprimentos.services.analise_obra_service import AnaliseObraService
from suprimentos.services.mapa_controle_service import MapaControleFilters, MapaControleService
from suprimentos.services.mapa_controle_viewmodel import AmbienteProvider
from suprimentos.views_controle import (
    _build_matrix_payload_from_rows,
    _extract_first_matrix_rows_from_layout,
)


class ControleAssistantService:
    def __init__(self, scope):
        self.scope = scope

    def _resolve_mapa_obra(self, entities: dict) -> Obra | None:
        project = ObrasAssistantService(self.scope)._resolve_project(entities)
        if not project:
            return None
        code = (project.code or "").strip()
        if not code:
            return None
        o = Obra.objects.filter(ativa=True, codigo_sienge=code).first()
        if o:
            return o
        for obra in Obra.objects.filter(ativa=True):
            if code in obra.chaves_sienge_busca_importacao():
                return obra
        return None

    def _obra_label(self, entities: dict, obra: Obra | None = None) -> str:
        project = ObrasAssistantService(self.scope)._resolve_project(entities)
        return obra_display_name(project or obra)

    def panorama_mapa_controle(self, entities: dict) -> AssistantResponse:
        obra = self._resolve_mapa_obra(entities)
        if not obra:
            return AssistantResponse(
                summary="Informe a obra para consultar o mapa de controle.",
                badges=["Mapa Controle"],
                alerts=[{"level": "warning", "message": "Cite o nome da obra."}],
            )

        ambientes = AmbienteOperacional.objects.filter(
            obra=obra, tipo=AmbienteTipo.MAPA_CONTROLE, ativo=True
        ).order_by("-updated_at")

        label = self._obra_label(entities, obra)

        if not ambientes.exists():
            bundle = AnaliseObraService(obra).controle_base_from_ambiente(obra)
            if not bundle or not bundle.get("rows"):
                return AssistantResponse(
                    summary=f"Obra {label}: sem mapa de controle cadastrado.",
                    badges=["Mapa Controle"],
                    actions=[{"label": "Abrir Mapa de Controle", "url": "/engenharia/mapa-controle/", "style": "primary"}],
                )

        provider = AmbienteProvider(
            extract_first_matrix_rows_from_layout=_extract_first_matrix_rows_from_layout,
            build_matrix_payload_from_rows=_build_matrix_payload_from_rows,
        )

        mapas_rows = []
        pct_values = []
        for amb in ambientes[:5]:
            try:
                payload = provider.build(obra=obra, ambiente_id=amb.id, selected={})
            except Exception:
                continue
            pct = payload.get("consolidated_pct") or payload.get("percentual_geral") or 0
            try:
                pct_f = float(pct)
            except (TypeError, ValueError):
                pct_f = 0.0
            pct_values.append(pct_f)
            mapas_rows.append(
                {
                    "ambiente": (amb.nome or "")[:40],
                    "percentual": f"{pct_f:.1f}%",
                    "atualizado": amb.updated_at.strftime("%d/%m/%Y") if amb.updated_at else "-",
                }
            )

        if not mapas_rows:
            svc = MapaControleService(obra, MapaControleFilters())
            summary = svc.build_summary_payload()
            kpis = summary.get("kpis", {})
            return AssistantResponse(
                summary=(
                    f"Mapa de controle obra {label}: "
                    f"{kpis.get('total_itens', 0)} itens no pipeline vinculado."
                ),
                cards=[
                    {"title": "Itens", "value": str(kpis.get("total_itens", 0)), "tone": "info"},
                    {"title": "Atrasados", "value": str(kpis.get("atrasados", 0)), "tone": "danger"},
                ],
                badges=["Mapa Controle", label],
                actions=[{"label": "Abrir Mapa de Controle", "url": "/engenharia/mapa-controle/", "style": "primary"}],
            )

        media_pct = sum(pct_values) / len(pct_values) if pct_values else 0.0
        multi = len(mapas_rows) > 1

        return AssistantResponse(
            summary=(
                f"Obra {label}: "
                + (
                    f"{len(mapas_rows)} mapas de controle; media {media_pct:.1f}%."
                    if multi
                    else f"mapa de controle em {media_pct:.1f}%."
                )
            ),
            cards=[
                {"title": "Mapas", "value": str(len(mapas_rows)), "tone": "info"},
                {"title": "Percentual medio", "value": f"{media_pct:.1f}%", "tone": "info"},
            ],
            table={
                "caption": "Mapas de controle da obra",
                "columns": ["ambiente", "percentual", "atualizado"],
                "rows": mapas_rows,
            },
            badges=["Mapa Controle", label],
            alerts=[
                {"level": "info", "message": "Varios mapas: consulte cada ambiente individualmente."}
            ]
            if multi
            else [],
            actions=[{"label": "Abrir Mapa de Controle", "url": "/engenharia/mapa-controle/", "style": "primary"}],
            links=[{"label": "Ferramenta Operacional", "url": "/engenharia/ferramenta-operacional/"}],
        )

    def listar_ambientes(self, entities: dict) -> AssistantResponse:
        obra = self._resolve_mapa_obra(entities)
        if not obra:
            return AssistantResponse(
                summary="Informe a obra para listar ambientes operacionais.",
                badges=["Ferramenta Operacional"],
            )

        ambientes = AmbienteOperacional.objects.filter(obra=obra, ativo=True).order_by("-updated_at")[:30]
        rows = []
        for amb in ambientes:
            draft = amb.versoes.filter(estado=VersaoEstado.DRAFT).order_by("-numero").first()
            published = amb.versoes.filter(estado=VersaoEstado.PUBLISHED).order_by("-numero").first()
            estado = "rascunho" if draft else ("publicada" if published else "sem versao")
            rows.append(
                {
                    "nome": (amb.nome or "")[:40],
                    "tipo": amb.get_tipo_display() if hasattr(amb, "get_tipo_display") else amb.tipo,
                    "versao": estado,
                    "atualizado": amb.updated_at.strftime("%d/%m/%Y") if amb.updated_at else "-",
                }
            )

        if not rows:
            return AssistantResponse(
                summary=f"Obra {label}: nenhum ambiente operacional cadastrado.",
                badges=["Ferramenta Operacional"],
                actions=[{"label": "Abrir Ferramenta", "url": "/engenharia/ferramenta-operacional/", "style": "primary"}],
            )

        return AssistantResponse(
            summary=f"{len(rows)} ambiente(s) operacional(is) na obra {self._obra_label(entities, obra)}.",
            table={
                "caption": "Ambientes operacionais",
                "columns": ["nome", "tipo", "versao", "atualizado"],
                "rows": rows,
            },
            badges=["Ferramenta Operacional", self._obra_label(entities, obra)],
            actions=[{"label": "Abrir Ferramenta", "url": "/engenharia/ferramenta-operacional/", "style": "primary"}],
        )
