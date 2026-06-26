"""Consultas de suprimentos / mapa de materiais."""
from __future__ import annotations

from decimal import Decimal

from django.db.models import Q, Sum, Value
from django.db.models.functions import Coalesce

from core.kpi_queries import count_itens_sem_alocacao_efetiva, queryset_itens_sem_alocacao_efetiva
from suprimentos.models import ItemMapa

from assistente_lplan.services.permissions import UserScope

from ._scope import LIMITE_LISTA, mapa_obras_qs, resolve_obra_mapa, resolve_project


def localizar_insumo(user, scope: UserScope, *, term: str, bloco: str = "") -> dict:
    term = (term or "").strip()
    if not term:
        return {"ok": False, "error": "insumo_ausente"}
    obras_qs = mapa_obras_qs(scope)
    q = (
        ItemMapa.objects.select_related("obra", "insumo", "local_aplicacao")
        .filter(obra__in=obras_qs)
        .filter(
            Q(insumo__descricao__icontains=term)
            | Q(descricao_override__icontains=term)
            | Q(insumo__codigo_sienge__icontains=term)
        )
        .annotate(total_alocado=Coalesce(Sum("alocacoes__quantidade_alocada"), Value(Decimal("0"))))
    )
    if bloco:
        q = q.filter(Q(local_aplicacao__nome__icontains=bloco) | Q(local_aplicacao__tipo__icontains=bloco))
    rows = []
    for item in q[:20]:
        planejado = item.quantidade_planejada or Decimal("0")
        alocado = item.total_alocado or Decimal("0")
        rows.append(
            {
                "obra": item.obra.nome if item.obra else "-",
                "insumo": item.insumo.descricao if item.insumo else "-",
                "local": item.local_aplicacao.nome if item.local_aplicacao else "Sem local",
                "planejado": str(planejado),
                "alocado": str(alocado),
                "status": "OK" if alocado > 0 else "Sem alocacao",
            }
        )
    return {
        "ok": bool(rows),
        "total": len(rows),
        "rows": rows,
        "term": term,
        "summary_hint": f"{len(rows)} registro(s) para '{term}'." if rows else f"Nenhum insumo encontrado para '{term}'.",
    }


def itens_sem_alocacao(user, scope: UserScope, *, project=None, obra: str = "") -> dict:
    project = project or resolve_project(scope, obra=obra)
    if project:
        qs = queryset_itens_sem_alocacao_efetiva(project).select_related("obra", "insumo", "local_aplicacao")[:30]
        rows = []
        for item in qs:
            rows.append(
                {
                    "obra": item.obra.nome if item.obra else project.code,
                    "insumo": item.insumo.descricao if item.insumo else "-",
                    "local": item.local_aplicacao.nome if item.local_aplicacao else "Sem local",
                    "prioridade": item.prioridade,
                    "prazo": item.prazo_necessidade.strftime("%d/%m/%Y") if item.prazo_necessidade else "-",
                }
            )
        total = count_itens_sem_alocacao_efetiva(project)
        return {
            "ok": True,
            "total": total,
            "rows": rows,
            "summary_hint": f"{total} item(ns) sem alocacao na obra {project.code}.",
        }

    obras_qs = mapa_obras_qs(scope)
    qs = (
        ItemMapa.objects.select_related("obra", "insumo", "local_aplicacao")
        .filter(obra__in=obras_qs)
        .annotate(total_alocado=Coalesce(Sum("alocacoes__quantidade_alocada"), Value(Decimal("0"))))
        .filter(quantidade_planejada__gt=0, total_alocado__lte=0)
        .order_by("-prioridade")[:30]
    )
    rows = [
        {
            "obra": item.obra.nome if item.obra else "-",
            "insumo": item.insumo.descricao if item.insumo else "-",
            "local": item.local_aplicacao.nome if item.local_aplicacao else "Sem local",
            "prioridade": item.prioridade,
            "prazo": item.prazo_necessidade.strftime("%d/%m/%Y") if item.prazo_necessidade else "-",
        }
        for item in qs
    ]
    return {
        "ok": True,
        "total": len(rows),
        "rows": rows,
        "summary_hint": f"{len(rows)} item(ns) sem alocacao no escopo.",
    }


def pipeline_obra(user, scope: UserScope, *, project=None, obra: str = "") -> dict:
    project = project or resolve_project(scope, obra=obra)
    obra_mapa = resolve_obra_mapa(scope, project=project, obra_nome=obra)
    if not obra_mapa:
        return {"ok": False, "error": "obra_mapa_nao_encontrada"}
    qs = ItemMapa.objects.filter(obra=obra_mapa, nao_aplica=False)
    total = qs.count()
    entregues = qs.filter(status_etapa="ENTREGUE").count()
    atrasados = sum(1 for i in qs[:500] if i.is_atrasado)
    sem_aloc = queryset_itens_sem_alocacao_efetiva(project).count() if project else 0
    return {
        "ok": True,
        "obra": obra_mapa.nome,
        "total_itens": total,
        "entregues": entregues,
        "atrasados": atrasados,
        "sem_alocacao": sem_aloc,
        "summary_hint": (
            f"Pipeline {obra_mapa.nome}: {total} itens, {entregues} entregues, "
            f"{atrasados} com atraso, {sem_aloc} sem alocacao."
        ),
    }


def quick_sem_alocacao_count(user, scope: UserScope) -> int:
    total = 0
    from ._scope import projects_qs

    for p in projects_qs(scope)[:LIMITE_LISTA]:
        total += count_itens_sem_alocacao_efetiva(p)
    return total
