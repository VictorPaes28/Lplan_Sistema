"""Consultas mapa de controle / execução física (Ferramentas)."""
from __future__ import annotations

from assistente_lplan.services.permissions import UserScope

from ._scope import resolve_obra_mapa, resolve_project


def execucao_fisica_obra(user, scope: UserScope, *, project=None, obra: str = "") -> dict:
    project = project or resolve_project(scope, obra=obra)
    obra_mapa = resolve_obra_mapa(scope, project=project, obra_nome=obra)
    if not obra_mapa:
        return {"ok": False, "error": "obra_nao_encontrada"}

    try:
        from suprimentos.services.analise_obra_service import AnaliseObraService

        section = AnaliseObraService(obra_mapa).build_section("controle")
        if not section:
            return {"ok": False, "error": "sem_dados_controle"}
        controle = section.get("controle", {})
        if controle.get("sem_dados"):
            return {"ok": False, "error": controle.get("mensagem") or "sem_ambiente_ativo"}
        kpis = controle.get("kpis", {})
        return {
            "ok": True,
            "obra": obra_mapa.nome,
            "percentual_medio": kpis.get("percentual_medio", 0),
            "nao_iniciadas": kpis.get("nao_iniciados", 0),
            "em_andamento": kpis.get("em_andamento", 0),
            "concluidas": kpis.get("concluidos", 0),
            "origem": controle.get("origem"),
            "summary_hint": (
                f"Execucao fisica {obra_mapa.nome}: {kpis.get('percentual_medio', 0):.1f}% medio, "
                f"{kpis.get('concluidos', 0)} concluidas."
            ),
        }
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": str(exc)}
