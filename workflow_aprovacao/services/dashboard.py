"""Dados da visão geral da Central de Aprovações."""
from __future__ import annotations

from workflow_aprovacao.access import user_can_see_central_monitoring_queue
from workflow_aprovacao.querysets import processes_list_base_qs, processes_pending_for_user
from workflow_aprovacao.services.inbox import (
    TAB_AGUARDANDO,
    TAB_APROVADO,
    TAB_PENDENTE,
    TAB_REPROVADO,
    inbox_tab_counts,
    user_involved_filter_q,
)


def dashboard_context_for_user(user) -> dict:
    counts = inbox_tab_counts(user)
    show_monitoring = user_can_see_central_monitoring_queue(user)
    pending_preview = list(processes_pending_for_user(user)[:12])
    recent = _recent_processes(user, show_monitoring=show_monitoring, limit=12)
    if pending_preview:
        skip = {p.pk for p in pending_preview}
        recent = [p for p in recent if p.pk not in skip]

    return {
        'pending_count': counts.get(TAB_PENDENTE, 0),
        'inbox_counts': counts,
        'dashboard_show_monitoring': show_monitoring,
        'pending_preview': pending_preview,
        'dashboard_recent': recent,
        'dashboard_kpis': _kpis_for_user(counts, show_monitoring=show_monitoring),
    }


def _kpis_for_user(counts: dict[str, int], *, show_monitoring: bool) -> list[dict]:
    kpis = [
        {
            'key': TAB_PENDENTE,
            'label': 'Minhas pendências',
            'count': counts.get(TAB_PENDENTE, 0),
            'modifier': 'pending',
            'icon': 'fa-inbox',
        },
        {
            'key': TAB_APROVADO,
            'label': 'Aprovados',
            'count': counts.get(TAB_APROVADO, 0),
            'modifier': 'ok',
            'icon': 'fa-check-circle',
        },
        {
            'key': TAB_REPROVADO,
            'label': 'Reprovados',
            'count': counts.get(TAB_REPROVADO, 0),
            'modifier': 'no',
            'icon': 'fa-times-circle',
        },
    ]
    if show_monitoring:
        kpis.append(
            {
                'key': TAB_AGUARDANDO,
                'label': 'Aguardando na Central',
                'count': counts.get(TAB_AGUARDANDO, 0),
                'modifier': 'warn',
                'icon': 'fa-hourglass-half',
            }
        )
    return kpis


def _recent_processes(user, *, show_monitoring: bool, limit: int):
    if show_monitoring:
        return list(processes_list_base_qs()[:limit])

    pending = list(processes_pending_for_user(user)[:limit])
    if len(pending) >= limit:
        return pending

    seen = {p.pk for p in pending}
    extra = (
        processes_list_base_qs()
        .filter(user_involved_filter_q(user))
        .exclude(pk__in=seen)
        .distinct()[: limit - len(pending)]
    )
    return pending + list(extra)
