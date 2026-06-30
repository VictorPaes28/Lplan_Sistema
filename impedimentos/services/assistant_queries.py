"""Consultas puras para o Assistente LPLAN (extraídas da lógica de views)."""
from __future__ import annotations

from datetime import date

from django.db.models import Count, F, OuterRef, Q, Subquery
from django.utils import timezone

from core.models import Project
from gestao_aprovacao.models import Obra
from impedimentos.models import Impedimento, StatusImpedimento


def _empty_obra_stats():
    return {"has_obra": False, "abertas": 0, "vencidas": 0, "criticas": 0}


def stats_restricoes_por_obra(obra) -> dict:
    """Indicadores de restrições abertas para uma obra GestControll."""
    if not obra:
        return _empty_obra_stats()
    hoje = date.today()
    final_status_subq = (
        StatusImpedimento.objects.filter(obra_id=OuterRef("obra_id"))
        .order_by("-ordem")
        .values("pk")[:1]
    )
    row = (
        Impedimento.objects.filter(obra=obra, parent__isnull=True)
        .annotate(final_status_id=Subquery(final_status_subq))
        .exclude(status_id=F("final_status_id"))
        .aggregate(
            abertas=Count("id", distinct=True),
            vencidas=Count(
                "id",
                filter=Q(prazo__isnull=False, prazo__lt=hoje),
                distinct=True,
            ),
            criticas=Count(
                "id",
                filter=Q(prioridade=Impedimento.PRIORIDADE_CRITICA),
                distinct=True,
            ),
        )
    )
    return {
        "has_obra": True,
        "abertas": row["abertas"] or 0,
        "vencidas": row["vencidas"] or 0,
        "criticas": row["criticas"] or 0,
    }


def restricoes_obra_queryset(obra, *, apenas_abertas: bool = True):
    """Query base de restrições de topo (sem subtarefas) para uma obra."""
    qs = Impedimento.objects.filter(obra=obra, parent__isnull=True).select_related(
        "status", "criado_por"
    ).prefetch_related("responsaveis")
    if apenas_abertas:
        status_final = StatusImpedimento.objects.filter(obra=obra).order_by("-ordem").first()
        if status_final:
            qs = qs.exclude(status_id=status_final.id)
    return qs


def restricoes_criticas_queryset(obra):
    hoje = timezone.localdate()
    return restricoes_obra_queryset(obra).filter(
        Q(prioridade=Impedimento.PRIORIDADE_CRITICA)
        | Q(prioridade=Impedimento.PRIORIDADE_ALTA)
        | Q(prazo__isnull=False, prazo__lt=hoje)
    )


def restricoes_por_responsavel_queryset(obra, usuario_term: str):
    from django.contrib.auth.models import User

    qs = restricoes_obra_queryset(obra)
    term = (usuario_term or "").strip()
    if not term:
        return qs.none()
    user_ids = list(
        User.objects.filter(
            Q(username__icontains=term)
            | Q(first_name__icontains=term)
            | Q(last_name__icontains=term)
        ).values_list("id", flat=True)[:20]
    )
    if not user_ids:
        return qs.none()
    return qs.filter(responsaveis__id__in=user_ids).distinct()


def stats_restricoes_escopo_projetos(projects) -> list[dict]:
    """Panorama multi-obra: stats por projeto vinculado."""
    project_list = list(projects)
    if not project_list:
        return []
    project_ids = [p.pk for p in project_list]
    obras_by_project = {
        o.project_id: o
        for o in Obra.objects.filter(project_id__in=project_ids).only("id", "project_id", "nome", "codigo")
    }
    cards = []
    for project in project_list:
        obra = obras_by_project.get(project.pk)
        stats = stats_restricoes_por_obra(obra) if obra else _empty_obra_stats()
        cards.append(
            {
                "project_id": project.id,
                "project_code": project.code,
                "project_name": project.name or project.code,
                "obra_nome": obra.nome if obra else "",
                **stats,
            }
        )
    return cards


def resolve_obra_from_project(project: Project | None):
    if not project:
        return None
    return Obra.objects.filter(project_id=project.id).first()
