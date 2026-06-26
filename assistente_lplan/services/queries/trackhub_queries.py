"""Consultas TrackHub."""
from __future__ import annotations

from django.db.models import Count
from django.utils import timezone

from assistente_lplan.services.permissions import UserScope

from ._scope import LIMITE_LISTA, trackhub_obras_qs


def _agregar_obra(obra, hoje):
    from trackhub.models import Pendencia

    qs = Pendencia.objects.filter(obra=obra).exclude(status__in=["concluida", "cancelada"])
    vencidas_qs = qs.filter(prazo__isnull=False, prazo__lt=hoje)
    resp_atraso = {}
    for p in vencidas_qs.select_related("responsavel_interno"):
        nome = p.responsavel_nome or (
            p.responsavel_interno.get_full_name() if p.responsavel_interno else "Sem responsavel"
        )
        if nome not in resp_atraso:
            resp_atraso[nome] = 0
        resp_atraso[nome] += 1
    return {
        "obra": obra.nome,
        "total_abertas": qs.count(),
        "vencidas": vencidas_qs.count(),
        "responsaveis_atrasados": [
            {"responsavel": k, "pendencias_vencidas": v}
            for k, v in sorted(resp_atraso.items(), key=lambda x: -x[1])
        ],
    }


def pendencias_obra(user, scope: UserScope, *, obra_nome: str = "") -> dict:
    qs_obras = trackhub_obras_qs(scope)
    if obra_nome:
        qs_obras = qs_obras.filter(nome__icontains=obra_nome)
    hoje = timezone.localdate()
    items = [_agregar_obra(o, hoje) for o in qs_obras[:LIMITE_LISTA]]
    total_v = sum(i["vencidas"] for i in items)
    total_a = sum(i["total_abertas"] for i in items)
    return {
        "ok": True,
        "obras": items,
        "total_abertas": total_a,
        "total_vencidas": total_v,
        "summary_hint": f"{total_a} pendencia(s) TrackHub abertas ({total_v} vencidas).",
    }


def pendencias_vencidas(user, scope: UserScope) -> dict:
    data = pendencias_obra(user, scope)
    vencidas_obras = [o for o in data.get("obras", []) if o.get("vencidas", 0) > 0]
    return {
        "ok": True,
        "obras": vencidas_obras,
        "total_vencidas": sum(o.get("vencidas", 0) for o in vencidas_obras),
        "summary_hint": f"{len(vencidas_obras)} obra(s) com pendencias TrackHub vencidas.",
    }


def pendencias_por_responsavel(user, scope: UserScope, *, responsavel_nome: str = "", limit_self: bool = False) -> dict:
    from trackhub.models import Pendencia

    hoje = timezone.localdate()
    obras = list(trackhub_obras_qs(scope))
    obra_ids = [o.id for o in obras]
    qs = Pendencia.objects.filter(obra_id__in=obra_ids).exclude(status__in=["concluida", "cancelada"])
    qs = qs.filter(prazo__isnull=False, prazo__lt=hoje)

    por_resp = {}
    for p in qs.select_related("responsavel_interno"):
        nome = p.responsavel_nome or (
            p.responsavel_interno.get_full_name() if p.responsavel_interno else "Sem responsavel"
        )
        if limit_self:
            if p.responsavel_interno_id != user.id and (user.get_full_name() or "") not in nome:
                if user.username not in nome:
                    continue
        if responsavel_nome and responsavel_nome.lower() not in nome.lower():
            continue
        if nome not in por_resp:
            por_resp[nome] = {"responsavel": nome, "pendencias_vencidas": 0, "pendencias_abertas": 0}
        por_resp[nome]["pendencias_vencidas"] += 1

    abertas = Pendencia.objects.filter(obra_id__in=obra_ids).exclude(status__in=["concluida", "cancelada"])
    for p in abertas.select_related("responsavel_interno"):
        nome = p.responsavel_nome or (
            p.responsavel_interno.get_full_name() if p.responsavel_interno else "Sem responsavel"
        )
        if nome in por_resp:
            por_resp[nome]["pendencias_abertas"] += 1

    ranking = sorted(por_resp.values(), key=lambda x: (-x["pendencias_vencidas"], -x["pendencias_abertas"]))[:30]
    return {
        "ok": True,
        "gerencial_limited": limit_self,
        "ranking": ranking,
        "summary_hint": f"Ranking TrackHub: {len(ranking)} responsavel(is) com pendencias.",
    }


def quick_trackhub_vencidas_count(user, scope: UserScope) -> int:
    return int(pendencias_vencidas(user, scope).get("total_vencidas", 0))
