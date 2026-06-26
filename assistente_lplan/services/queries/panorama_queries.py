"""Panorama multi-obra e dados da sidebar."""
from __future__ import annotations

from django.utils import timezone

from assistente_lplan.services.permissions import AssistantPermissionService, UserScope
from core.kpi_queries import count_diarios_aguardando_gestor

from ._scope import projects_qs, resolve_obra_gestao, resolve_obra_mapa
from . import pedidos_queries, rdo_queries, restricoes_queries, trackhub_queries


def quick_status_cards(
    user,
    scope: UserScope,
    perm: AssistantPermissionService,
    *,
    project=None,
) -> list[dict]:
    cards = []
    if scope.role == "admin" or scope.project_ids:
        if project:
            rdo_val = str(count_diarios_aguardando_gestor(project))
        else:
            rdo_val = str(rdo_queries.quick_rdo_pendentes_count(scope))
        cards.append(
            {
                "id": "rdo_pendentes",
                "title": "RDOs pendentes",
                "value": rdo_val,
                "tone": "warning",
                "module": "rdo",
            }
        )
        if project:
            ped_val = str(pedidos_queries.pedidos_atrasados(user, scope, dias_limite=7, project=project).get("total", 0))
        else:
            ped_val = str(pedidos_queries.quick_pedidos_atrasados_count(user, scope))
        cards.append(
            {
                "id": "pedidos_atrasados",
                "title": "Pedidos atrasados",
                "value": ped_val,
                "tone": "danger",
                "module": "pedidos",
            }
        )
    if perm.can_view_restricoes(scope):
        if project:
            og = resolve_obra_gestao(scope, project=project)
            rest_val = "0"
            if og:
                st = restricoes_queries._stats_obra(og)
                rest_val = str(st.get("criticas_altas", 0) + st.get("vencidas", 0))
        else:
            rest_val = str(restricoes_queries.quick_restricoes_criticas_count(user, scope))
        cards.append(
            {
                "id": "restricoes_criticas",
                "title": "Restricoes criticas",
                "value": rest_val,
                "tone": "danger",
                "module": "restricoes",
            }
        )
    if perm.can_view_trackhub(scope):
        if project:
            obra_th = resolve_obra_mapa(scope, project=project)
            if obra_th:
                agg = trackhub_queries._agregar_obra(obra_th, timezone.localdate())
                th_val = str(agg.get("vencidas", 0))
            else:
                th_val = "0"
        else:
            th_val = str(trackhub_queries.quick_trackhub_vencidas_count(user, scope))
        cards.append(
            {
                "id": "trackhub_vencidas",
                "title": "TrackHub vencidas",
                "value": th_val,
                "tone": "warning",
                "module": "trackhub",
            }
        )
    return cards


def _criticidade_obra(project, user, scope, perm) -> tuple[str, int]:
    """Retorna (cor, badge_alertas): vermelho|laranja|verde|cinza."""
    from core.models import ConstructionDiary

    alertas = 0
    critico = False
    if not ConstructionDiary.objects.filter(project=project).exists():
        return "vermelho", 1
    freq = rdo_queries._metricas_rdo_frequencia(project, front_id="todas")
    if freq.get("nunca_teve_rdo") or freq.get("sem_rdo_recente"):
        critico = True
        alertas += 1
    ped = pedidos_queries.pedidos_atrasados(user, scope, dias_limite=7, project=project)
    if ped.get("total", 0) > 0:
        alertas += ped["total"]
        if ped["total"] >= 3:
            critico = True
    if perm.can_view_restricoes(scope):
        from ._scope import resolve_obra_gestao

        og = resolve_obra_gestao(scope, project=project)
        if og:
            st = restricoes_queries._stats_obra(og)
            if st["vencidas"] or st["criticas_altas"]:
                alertas += st["vencidas"] + st["criticas_altas"]
                critico = True
    if critico:
        return "vermelho", alertas
    if alertas > 0:
        return "laranja", alertas
    if ConstructionDiary.objects.filter(project=project).exists():
        return "verde", 0
    return "cinza", 0


def obras_sidebar(user, scope: UserScope, perm: AssistantPermissionService) -> list[dict]:
    items = []
    for p in projects_qs(scope)[:40]:
        cor, badge = _criticidade_obra(p, user, scope, perm)
        items.append(
            {
                "id": p.id,
                "code": p.code,
                "name": (p.name or p.code)[:48],
                "criticidade": cor,
                "alertas": badge,
            }
        )
    return items


def situacao_geral(user, scope: UserScope, perm: AssistantPermissionService) -> dict:
    from . import mapa_geo_queries, rh_queries, suprimentos_queries

    hoje_cards = quick_status_cards(user, scope, perm)
    obras_sb = obras_sidebar(user, scope, perm)
    criticas = [o for o in obras_sb if o["criticidade"] == "vermelho"]
    resumo = {
        "cards": hoje_cards,
        "obras_criticas": criticas[:10],
        "total_obras": len(obras_sb),
        "rdo": rdo_queries.obras_sem_rdo(user, scope),
        "pedidos_atrasados": pedidos_queries.pedidos_atrasados(user, scope, dias_limite=7),
    }
    if perm.can_view_restricoes(scope):
        resumo["restricoes"] = restricoes_queries.restricoes_criticas_escopo(user, scope)
    if perm.can_view_trackhub(scope):
        resumo["trackhub"] = trackhub_queries.pendencias_vencidas(user, scope)
    if perm.can_view_mapa_geo():
        resumo["mapa_geo"] = mapa_geo_queries.panorama_mapa_geo(user, scope)
    if perm.can_view_rh(scope):
        resumo["rh"] = rh_queries.resumo_rh(user, scope)
    resumo["ok"] = True
    resumo["summary_hint"] = (
        f"Panorama: {len(criticas)} obra(s) em situacao critica de {len(obras_sb)} no escopo."
    )
    return resumo
