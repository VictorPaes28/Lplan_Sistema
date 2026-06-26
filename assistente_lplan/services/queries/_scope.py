"""Resolução de escopo e entidades por usuário Django."""
from __future__ import annotations

from core.models import Project
from gestao_aprovacao.models import Obra as ObraGestao
from mapa_obras.models import Obra as ObraMapa

from assistente_lplan.services.permissions import UserScope

LIMITE_LISTA = 50


def projects_qs(scope: UserScope):
    qs = Project.objects.filter(is_active=True).order_by("code")
    if scope.role != "admin":
        if not scope.project_ids:
            return qs.none()
        qs = qs.filter(id__in=scope.project_ids)
    return qs


def project_ids(scope: UserScope) -> list[int]:
    if scope.role == "admin":
        return list(Project.objects.filter(is_active=True).values_list("id", flat=True))
    return list(scope.project_ids)


def resolve_project(scope: UserScope, *, obra: str = "", project_id=None) -> Project | None:
    if project_id:
        try:
            pid = int(project_id)
        except (TypeError, ValueError):
            pid = None
        if pid:
            qs = projects_qs(scope).filter(id=pid)
            return qs.first()

    term = (obra or "").strip()
    qs = projects_qs(scope)
    if term:
        return qs.filter(name__icontains=term).first() or qs.filter(code__icontains=term).first()
    return qs.first()


def resolve_obra_gestao(scope: UserScope, *, obra: str = "", project: Project | None = None) -> ObraGestao | None:
    mapa_ids = mapa_obras_qs(scope).values_list("id", flat=True)
    qs = ObraGestao.objects.filter(ativo=True, project__obra_mapa__id__in=mapa_ids)
    if project:
        return qs.filter(project_id=project.id).first()
    term = (obra or "").strip()
    if term:
        exato = qs.filter(nome__iexact=term).first()
        if exato:
            return exato
        return qs.filter(nome__icontains=term).first()
    return None


def mapa_obras_qs(scope: UserScope):
    qs = ObraMapa.objects.filter(ativa=True)
    if scope.role == "admin":
        return qs
    if scope.project_codes:
        return qs.filter(codigo_sienge__in=scope.project_codes)
    if scope.project_ids:
        return qs.filter(project_id__in=scope.project_ids)
    return qs.none()


def trackhub_obras_qs(scope: UserScope):
    """TrackHub inclui Sede/escritório para admin."""
    qs = ObraMapa.objects.filter(ativa=True)
    if scope.role == "admin":
        return qs.order_by("nome")
    if scope.project_ids:
        return qs.filter(project_id__in=scope.project_ids).order_by("nome")
    return qs.none()


def resolve_obra_mapa(scope: UserScope, project: Project | None = None, obra_nome: str = "") -> ObraMapa | None:
    qs = mapa_obras_qs(scope)
    if project:
        from core.kpi_queries import mapa_obra_for_project

        o = mapa_obra_for_project(project)
        if o and qs.filter(pk=o.pk).exists():
            return o
        code = (project.code or "").strip()
        if code:
            return qs.filter(codigo_sienge=code).first()
    term = (obra_nome or "").strip()
    if term:
        return qs.filter(nome__icontains=term).first() or qs.filter(codigo_sienge__icontains=term).first()
    return None
