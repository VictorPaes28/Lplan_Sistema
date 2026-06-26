"""Consultas mapa geográfico."""
from __future__ import annotations

from assistente_lplan.services.permissions import UserScope

from ._scope import LIMITE_LISTA, projects_qs, resolve_project


def panorama_mapa_geo(user, scope: UserScope) -> dict:
    from mapa_geo.services import get_map_summary

    obras = []
    for project in projects_qs(scope)[:LIMITE_LISTA]:
        summary = get_map_summary(project)
        total = summary["total"]
        obras.append(
            {
                "obra": project.name,
                "codigo": project.code,
                "total_elementos": total,
                "pontos": summary["points"],
                "marcadores_gps": summary["gps_markers"],
                "progresso_pct": summary.get("overall_progress_pct", 0),
                "tem_elementos": total > 0,
            }
        )
    com_elementos = [o for o in obras if o["tem_elementos"]]
    return {
        "ok": True,
        "obras": obras,
        "total_com_elementos": len(com_elementos),
        "summary_hint": f"{len(com_elementos)} obra(s) com elementos no mapa geografico.",
    }


def elementos_obra(user, scope: UserScope, *, project=None, obra: str = "") -> dict:
    project = project or resolve_project(scope, obra=obra)
    if not project:
        return {"ok": False, "error": "obra_nao_encontrada"}
    from mapa_geo.services import get_map_summary

    summary = get_map_summary(project)
    return {
        "ok": True,
        "obra": project.name,
        "codigo": project.code,
        "total_elementos": summary["total"],
        "linhas": summary["segments"],
        "pontos": summary["points"],
        "areas": summary["areas"],
        "marcadores_gps": summary["gps_markers"],
        "progresso_pct": summary.get("overall_progress_pct", 0),
        "summary_hint": (
            f"Mapa geo {project.code}: {summary['total']} elementos, "
            f"{summary['gps_markers']} marcadores GPS."
        ),
    }
