from __future__ import annotations

from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import render
from django.views.decorators.cache import cache_control

from accounts.decorators import require_group
from accounts.groups import GRUPOS
from mapa_obras.models import Obra
from mapa_obras.contexto_obra import resolve_obra_context
from suprimentos.models import ItemMapaServico


def _resolve_obra_for_request(request):
    return resolve_obra_context(request)


def _status_bucket(item: ItemMapaServico) -> str:
    if item.status_percentual is not None:
        v = float(item.status_percentual)
        if v >= 1.0:
            return "concluido"
        if v <= 0.0:
            return "nao_iniciado"
        return "em_andamento"

    txt = (item.status_texto or "").strip().lower()
    if any(t in txt for t in ["conclu", "final", "entreg"]):
        return "concluido"
    if any(t in txt for t in ["exec", "anda", "parcial"]):
        return "em_andamento"
    if any(t in txt for t in ["nao", "não", "pend", "aguard"]):
        return "nao_iniciado"
    return "indefinido"


@login_required
@require_group(GRUPOS.ENGENHARIA)
@cache_control(no_store=True, no_cache=True, must_revalidate=True, max_age=0)
def mapa_servico(request):
    ctx = _resolve_obra_for_request(request)
    obras, obra = ctx
    if not obra:
        return render(
            request,
            "suprimentos/mapa_servico.html",
            {
                **ctx.to_template_context(),
                "items": [],
                "kpis": {"total": 0, "concluido": 0, "em_andamento": 0, "nao_iniciado": 0},
                "filters": {},
                "options": {"setores": [], "blocos": [], "pavimentos": []},
            },
        )

    setor = (request.GET.get("setor") or "").strip()
    bloco = (request.GET.get("bloco") or "").strip()
    pavimento = (request.GET.get("pavimento") or "").strip()
    status = (request.GET.get("status") or "").strip()
    search = (request.GET.get("search") or "").strip()

    qs = ItemMapaServico.objects.filter(obra=obra)
    if setor:
        qs = qs.filter(setor__iexact=setor)
    if bloco:
        qs = qs.filter(bloco__iexact=bloco)
    if pavimento:
        qs = qs.filter(pavimento__iexact=pavimento)
    if search:
        qs = qs.filter(
            Q(atividade__icontains=search)
            | Q(grupo_servicos__icontains=search)
            | Q(apto__icontains=search)
            | Q(status_texto__icontains=search)
            | Q(observacao__icontains=search)
        )

    items_all = list(qs.order_by("setor", "bloco", "pavimento", "apto", "atividade"))
    if status:
        items_all = [i for i in items_all if _status_bucket(i) == status]

    total = len(items_all)
    concluidos = sum(1 for i in items_all if _status_bucket(i) == "concluido")
    em_andamento = sum(1 for i in items_all if _status_bucket(i) == "em_andamento")
    nao_iniciado = sum(1 for i in items_all if _status_bucket(i) == "nao_iniciado")
    pct_concluido = round((concluidos / total) * 100, 2) if total else 0.0

    options_qs = ItemMapaServico.objects.filter(obra=obra)
    setores = sorted({x for x in options_qs.values_list("setor", flat=True) if x})
    blocos = sorted({x for x in options_qs.values_list("bloco", flat=True) if x})
    pavimentos = sorted({x for x in options_qs.values_list("pavimento", flat=True) if x})

    return render(
        request,
        "suprimentos/mapa_servico.html",
        {
            **ctx.to_template_context(),
            "items": items_all[:500],
            "total_items": total,
            "kpis": {
                "total": total,
                "concluido": concluidos,
                "em_andamento": em_andamento,
                "nao_iniciado": nao_iniciado,
                "percentual_concluido": pct_concluido,
            },
            "filters": {
                "setor": setor,
                "bloco": bloco,
                "pavimento": pavimento,
                "status": status,
                "search": search,
            },
            "options": {
                "setores": setores,
                "blocos": blocos,
                "pavimentos": pavimentos,
            },
        },
    )
