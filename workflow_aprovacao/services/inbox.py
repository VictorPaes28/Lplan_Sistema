"""Fila da Central de Aprovações — abas, filtros e consultas."""
from __future__ import annotations

from typing import Any

from django.db.models import Q, QuerySet

from workflow_aprovacao.access import user_can_see_central_monitoring_queue
from workflow_aprovacao.models import (
    ApprovalProcess,
    ParticipantRole,
    ProcessCategory,
    ProcessStatus,
    SubjectKind,
)
from workflow_aprovacao.querysets import (
    annotate_pending_assigned_to_user,
    processes_awaiting_in_central,
    processes_list_base_qs,
    processes_pending_for_user,
)

TAB_PENDENTE = 'pendente'
TAB_APROVADO = 'aprovado'
TAB_REPROVADO = 'reprovado'
TAB_AGUARDANDO = 'aguardando'

INBOX_DISPLAY_LIMIT = 150


def user_involved_filter_q(user) -> Q:
    """Processos em que o utilizador iniciou, atuou no histórico ou é participante do fluxo."""
    if not user or not user.is_authenticated:
        return Q(pk__in=[])
    roles = (ParticipantRole.APPROVER, ParticipantRole.OWNER, ParticipantRole.VIEWER)
    q = Q(history_entries__actor=user) | Q(initiated_by=user)
    participant = Q(
        flow_definition__steps__participants__subject_kind=SubjectKind.USER,
        flow_definition__steps__participants__user=user,
        flow_definition__steps__participants__role__in=roles,
    )
    group_ids = list(user.groups.values_list('pk', flat=True))
    if group_ids:
        participant |= Q(
            flow_definition__steps__participants__subject_kind=SubjectKind.DJANGO_GROUP,
            flow_definition__steps__participants__django_group_id__in=group_ids,
            flow_definition__steps__participants__role__in=roles,
        )
    return q | participant


def available_inbox_tabs(user) -> list[dict[str, Any]]:
    counts = inbox_tab_counts(user)
    tabs = [
        {'key': TAB_PENDENTE, 'label': 'Minhas pendências'},
        {'key': TAB_APROVADO, 'label': 'Aprovados'},
        {'key': TAB_REPROVADO, 'label': 'Reprovados'},
    ]
    if user_can_see_central_monitoring_queue(user):
        tabs.append({'key': TAB_AGUARDANDO, 'label': 'Aguardando na Central'})
    return [{**tab, 'count': counts.get(tab['key'], 0)} for tab in tabs]


def _normalize_tab(tab: str | None, *, show_admin: bool) -> str:
    allowed = {TAB_PENDENTE, TAB_APROVADO, TAB_REPROVADO}
    if show_admin:
        allowed.add(TAB_AGUARDANDO)
    if tab in allowed:
        return tab
    return TAB_PENDENTE


def _apply_search_filter(qs: QuerySet, q: str) -> QuerySet:
    q = (q or '').strip()
    if not q:
        return qs
    criteria = (
        Q(title__icontains=q)
        | Q(project__code__icontains=q)
        | Q(project__name__icontains=q)
        | Q(external_id__icontains=q)
        | Q(summary__icontains=q)
    )
    if q.isdigit():
        criteria |= Q(pk=int(q))
    return qs.filter(criteria)


def _apply_origin_filter(qs: QuerySet, origin: str) -> QuerySet:
    origin = (origin or '').strip().lower()
    if origin == 'gestao':
        return qs.filter(
            Q(external_entity_type='gestao_workorder') | Q(gestao_dispatch__isnull=False)
        )
    if origin == 'sienge':
        return qs.filter(
            external_entity_type__in=(
                'sienge_supply_contract',
                'sienge_supply_contract_measurement',
            )
        )
    return qs


def build_inbox_queryset(
    user,
    *,
    tab: str,
    project_id: int | None = None,
    category_id: int | None = None,
    q: str = '',
    origin: str = '',
) -> QuerySet:
    show_admin = user_can_see_central_monitoring_queue(user)
    tab = _normalize_tab(tab, show_admin=show_admin)

    if tab == TAB_PENDENTE:
        qs = processes_pending_for_user(user)
    elif tab == TAB_AGUARDANDO:
        qs = processes_awaiting_in_central()
    elif tab == TAB_APROVADO:
        qs = processes_list_base_qs().filter(status=ProcessStatus.APPROVED)
        if not show_admin:
            qs = qs.filter(user_involved_filter_q(user)).distinct()
    elif tab == TAB_REPROVADO:
        qs = processes_list_base_qs().filter(status=ProcessStatus.REJECTED)
        if not show_admin:
            qs = qs.filter(user_involved_filter_q(user)).distinct()
    else:
        qs = processes_pending_for_user(user)

    if project_id:
        qs = qs.filter(project_id=project_id)
    if category_id:
        qs = qs.filter(category_id=category_id)
    qs = _apply_origin_filter(qs, origin)
    qs = _apply_search_filter(qs, q)
    return qs


def inbox_tab_counts(user) -> dict[str, int]:
    show_admin = user_can_see_central_monitoring_queue(user)
    counts = {
        TAB_PENDENTE: processes_pending_for_user(user).count(),
        TAB_APROVADO: build_inbox_queryset(user, tab=TAB_APROVADO).count(),
        TAB_REPROVADO: build_inbox_queryset(user, tab=TAB_REPROVADO).count(),
    }
    if show_admin:
        counts[TAB_AGUARDANDO] = processes_awaiting_in_central().count()
    return counts


def inbox_filter_options(user) -> dict[str, Any]:
    from core.models import Project

    if user_can_see_central_monitoring_queue(user):
        visible = processes_list_base_qs()
    else:
        visible = processes_list_base_qs().filter(user_involved_filter_q(user)).distinct()

    project_ids = visible.values_list('project_id', flat=True).distinct()
    projects = Project.objects.filter(pk__in=project_ids, is_active=True).order_by('code')
    category_ids = visible.values_list('category_id', flat=True).distinct()
    categories = ProcessCategory.objects.filter(pk__in=category_ids, is_active=True).order_by(
        'sort_order', 'name'
    )
    return {'projects': projects, 'categories': categories}


def fetch_inbox_page(
    user,
    *,
    tab: str,
    project_id: int | None = None,
    category_id: int | None = None,
    q: str = '',
    origin: str = '',
    limit: int = INBOX_DISPLAY_LIMIT,
) -> tuple[list[ApprovalProcess], int, str]:
    """Lista paginada (limite fixo), total filtrado e aba normalizada."""
    show_admin = user_can_see_central_monitoring_queue(user)
    tab = _normalize_tab(tab, show_admin=show_admin)
    qs = build_inbox_queryset(
        user,
        tab=tab,
        project_id=project_id,
        category_id=category_id,
        q=q,
        origin=origin,
    )
    total = qs.count()
    if tab == TAB_AGUARDANDO:
        slice_qs = qs[:limit]
        rows, _ = annotate_pending_assigned_to_user(slice_qs, user)
        return rows, total, tab
    return list(qs[:limit]), total, tab
