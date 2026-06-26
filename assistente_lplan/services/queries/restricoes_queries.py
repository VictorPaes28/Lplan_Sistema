"""Consultas de restrições / impedimentos."""
from __future__ import annotations

from django.db.models import Count, Q
from django.utils import timezone

from assistente_lplan.services.permissions import UserScope

from ._scope import LIMITE_LISTA, mapa_obras_qs, resolve_obra_gestao


def _restricoes_qs_abertas(obra_gestao):
    from impedimentos.models import Impedimento, StatusImpedimento

    if not obra_gestao:
        return Impedimento.objects.none()
    status_final = StatusImpedimento.objects.filter(obra=obra_gestao).order_by("-ordem").first()
    qs = Impedimento.objects.filter(obra=obra_gestao, parent__isnull=True)
    if status_final:
        qs = qs.exclude(status_id=status_final.id)
    return qs


def _stats_obra(obra_gestao) -> dict:
    qs = _restricoes_qs_abertas(obra_gestao)
    hoje = timezone.localdate()
    return {
        "total_abertas": qs.count(),
        "vencidas": qs.filter(prazo__isnull=False, prazo__lt=hoje).count(),
        "criticas_altas": qs.filter(prioridade__in=["ALTA", "CRITICA"]).count(),
        "sem_responsavel": qs.annotate(_nresp=Count("responsaveis")).filter(_nresp=0).count(),
    }


def restricoes_obra(user, scope: UserScope, *, obra: str = "", project=None) -> dict:
    obra_g = resolve_obra_gestao(scope, obra=obra, project=project)
    if not obra_g:
        return {"ok": False, "error": "obra_nao_encontrada"}
    qs = _restricoes_qs_abertas(obra_g)
    hoje = timezone.localdate()
    por_prioridade = {}
    for imp in qs:
        por_prioridade[imp.prioridade] = por_prioridade.get(imp.prioridade, 0) + 1
    rows = []
    for imp in qs.select_related("status").order_by("-prioridade", "prazo")[:20]:
        rows.append(
            {
                "titulo": (imp.titulo or "")[:80],
                "prioridade": imp.prioridade,
                "prazo": imp.prazo.strftime("%d/%m/%Y") if imp.prazo else "-",
                "vencida": "sim" if imp.prazo and imp.prazo < hoje else "nao",
                "status": imp.status.nome if imp.status else "-",
            }
        )
    stats = _stats_obra(obra_g)
    return {
        "ok": True,
        "obra": obra_g.nome,
        "stats": stats,
        "por_prioridade": por_prioridade,
        "rows": rows,
        "summary_hint": (
            f"{stats['total_abertas']} restricao(oes) abertas na obra {obra_g.nome} "
            f"({stats['vencidas']} vencidas)."
        ),
    }


def restricoes_criticas_escopo(user, scope: UserScope) -> dict:
    from gestao_aprovacao.models import Obra as ObraGestao

    mapa_ids = mapa_obras_qs(scope).values_list("id", flat=True)
    obras = ObraGestao.objects.filter(ativo=True, project__obra_mapa__id__in=mapa_ids)
    resultado = []
    total_crit = 0
    for obra_g in obras[:LIMITE_LISTA]:
        stats = _stats_obra(obra_g)
        if stats["criticas_altas"] > 0 or stats["vencidas"] > 0:
            resultado.append({"obra": obra_g.nome, **stats})
            total_crit += stats["criticas_altas"]
    resultado.sort(key=lambda x: (-x["vencidas"], -x["criticas_altas"]))
    return {
        "ok": True,
        "obras": resultado,
        "total_criticas": total_crit,
        "summary_hint": f"{len(resultado)} obra(s) com restricoes criticas ou vencidas.",
    }


def restricoes_por_responsavel(
    user,
    scope: UserScope,
    *,
    responsavel_nome: str = "",
    gerencial: bool = True,
    limit_self: bool = False,
) -> dict:
    from django.contrib.auth.models import User

    from gestao_aprovacao.models import Obra as ObraGestao
    from impedimentos.models import Impedimento, StatusImpedimento

    mapa_ids = list(mapa_obras_qs(scope).values_list("id", flat=True))
    obras_ids = list(
        ObraGestao.objects.filter(ativo=True, project__obra_mapa__id__in=mapa_ids).values_list("id", flat=True)
    )
    status_final_por_obra = {}
    for oid in obras_ids:
        sf = StatusImpedimento.objects.filter(obra_id=oid).order_by("-ordem").first()
        if sf:
            status_final_por_obra[oid] = sf.id

    qs = Impedimento.objects.filter(parent__isnull=True, obra_id__in=obras_ids).prefetch_related("responsaveis")
    hoje = timezone.localdate()
    por_resp = {}

    filtro_user = None
    if responsavel_nome:
        filtro_user = User.objects.filter(
            Q(username__icontains=responsavel_nome)
            | Q(first_name__icontains=responsavel_nome)
            | Q(last_name__icontains=responsavel_nome)
        ).first()
    elif limit_self:
        filtro_user = user

    for imp in qs:
        final_id = status_final_por_obra.get(imp.obra_id)
        if final_id and imp.status_id == final_id:
            continue
        vencida = imp.prazo is not None and imp.prazo < hoje
        for resp in imp.responsaveis.all():
            if filtro_user and resp.id != filtro_user.id:
                continue
            uid = resp.id
            if uid not in por_resp:
                por_resp[uid] = {
                    "responsavel": resp.get_full_name() or resp.username,
                    "restricoes_abertas": 0,
                    "vencidas": 0,
                }
            por_resp[uid]["restricoes_abertas"] += 1
            if vencida:
                por_resp[uid]["vencidas"] += 1

    ranking = sorted(por_resp.values(), key=lambda x: (-x["vencidas"], -x["restricoes_abertas"]))[:30]
    return {
        "ok": True,
        "gerencial_limited": limit_self,
        "ranking": ranking,
        "summary_hint": f"Ranking de {len(ranking)} responsavel(is) por restricoes abertas.",
    }


def quick_restricoes_criticas_count(user, scope: UserScope) -> int:
    data = restricoes_criticas_escopo(user, scope)
    return sum(o.get("criticas_altas", 0) + o.get("vencidas", 0) for o in data.get("obras", []))
