"""Consultas puras para o Assistente LPLAN (extraídas de trackhub/views.py)."""
from __future__ import annotations

from datetime import timedelta

from django.db.models import Q
from django.utils import timezone

from core.models import ProjectMember, ProjectOwner
from trackhub.models import EtapaPendencia, Pendencia


def trackhub_has_full_access(user) -> bool:
    from trackhub.decorators import user_has_trackhub_access

    if not user or not user.is_authenticated:
        return False
    if user.is_superuser or user.is_staff:
        return True
    from accounts.groups import GRUPOS

    admin_groups = {
        GRUPOS.ADMINISTRADOR,
        GRUPOS.CENTRAL_APROVACOES_ADMIN,
        GRUPOS.TRACKHUB,
        GRUPOS.TRACKHUB_ADMIN,
    }
    return user.groups.filter(name__in=admin_groups).exists()


def trackhub_roles(user) -> dict:
    from accounts.groups import GRUPOS

    gs = set(user.groups.values_list("name", flat=True)) if user.is_authenticated else set()
    return {
        "admin": trackhub_has_full_access(user),
        "aprovador": GRUPOS.TRACKHUB_APROVADOR in gs or GRUPOS.TRACKHUB in gs,
        "solicitante": GRUPOS.TRACKHUB_SOLICITANTE in gs,
    }


def obra_pks_designadas(user) -> list[int]:
    from mapa_obras.models import Obra

    if trackhub_has_full_access(user):
        return list(Obra.objects.filter(ativa=True).values_list("pk", flat=True))
    project_ids = set(
        ProjectOwner.objects.filter(user=user).values_list("project_id", flat=True)
    ) | set(ProjectMember.objects.filter(user=user).values_list("project_id", flat=True))
    if not project_ids:
        return []
    return list(
        Obra.objects.filter(ativa=True, project_id__in=project_ids).values_list("pk", flat=True)
    )


def pendencias_qs_for_user(user):
    if trackhub_has_full_access(user):
        return Pendencia.objects.all()
    roles = trackhub_roles(user)
    if not (roles["aprovador"] or roles["solicitante"]):
        return Pendencia.objects.none()
    obra_pks = obra_pks_designadas(user)
    resp_q = Q(etapas__responsavel_interno=user) | Q(responsavel_interno=user)
    if not obra_pks:
        return Pendencia.objects.filter(resp_q).distinct()
    return Pendencia.objects.filter(Q(obra_id__in=obra_pks) | resp_q).distinct()


def fila_stats_for_user(user) -> dict:
    hoje = timezone.localdate()
    mes_inicio = hoje.replace(day=1)
    pendencias_base = pendencias_qs_for_user(user)
    etapas_pendentes = (
        EtapaPendencia.objects.filter(pendencia__in=pendencias_base, status="pendente")
        .exclude(pendencia__status="cancelada")
        .count()
    )
    return {
        "urgentes_vencidas": pendencias_base.filter(Q(prioridade="urgente") | Q(prazo__lt=hoje))
        .exclude(status__in=["concluida", "cancelada"])
        .count(),
        "em_andamento": pendencias_base.filter(status="em_andamento").count(),
        "etapas_pendentes": etapas_pendentes,
        "concluidas_mes": pendencias_base.filter(
            status="concluida", updated_at__gte=mes_inicio
        ).count(),
        "abertas": pendencias_base.exclude(status__in=["concluida", "cancelada"]).count(),
    }


def pendencias_vencidas_qs(user):
    hoje = timezone.localdate()
    return (
        pendencias_qs_for_user(user)
        .filter(prazo__isnull=False, prazo__lt=hoje)
        .exclude(status__in=["concluida", "cancelada"])
        .select_related("obra", "responsavel_interno")
        .order_by("prazo")
    )


def pendencias_abertas_qs(user, *, obra_id=None):
    qs = (
        pendencias_qs_for_user(user)
        .exclude(status__in=["concluida", "cancelada"])
        .select_related("obra", "responsavel_interno")
        .order_by("prazo", "-prioridade")
    )
    if obra_id:
        qs = qs.filter(obra_id=obra_id)
    return qs
