"""Consultas reutilizáveis para o painel e relatórios."""
from django.db.models import Exists, OuterRef, Q

from workflow_aprovacao.models import (
    ApprovalHistoryEntry,
    ApprovalProcess,
    ProcessStatus,
)
from workflow_aprovacao.services.step_access import pending_processes_filter_q

GESTAO_ENTITY_TYPES = ('gestao_workorder',)


def processes_list_base_qs():
    return ApprovalProcess.objects.select_related(
        'project', 'category', 'current_step', 'flow_definition', 'initiated_by'
    ).order_by('-updated_at', '-pk')


def processes_awaiting_base_qs():
    return processes_list_base_qs().filter(status=ProcessStatus.AWAITING_STEP)


def processes_pending_for_user(user):
    """
    Processos aguardando ação em que o usuário é aprovador na alçada atual
    (usuário direto ou membro de grupo Django).
    """
    if not user or not user.is_authenticated:
        return ApprovalProcess.objects.none()

    return processes_awaiting_base_qs().filter(pending_processes_filter_q(user))


def processes_awaiting_in_central():
    """Todos os processos aguardando alguma alçada (visão de monitoramento)."""
    return processes_awaiting_base_qs()


def processes_inbox_snapshot(user, limit: int = 100):
    """Pendentes pessoais + últimos concluídos/reprovados envolvendo o usuário."""
    pending = processes_pending_for_user(user)
    if not user or not user.is_authenticated:
        return pending, ApprovalProcess.objects.none()
    acted = ApprovalHistoryEntry.objects.filter(
        process_id=OuterRef('pk'),
        actor_id=user.pk,
    )
    recent = (
        ApprovalProcess.objects.filter(Exists(acted))
        .exclude(status=ProcessStatus.AWAITING_STEP)
        .select_related('project', 'category')
        .order_by('-updated_at')[:limit]
    )
    return pending, recent


def annotate_pending_assigned_to_user(qs, user):
    """Anota cada processo com flag se o usuário deve decidir na alçada atual."""
    if not user or not user.is_authenticated:
        return list(qs), set()
    my_ids = set(processes_pending_for_user(user).values_list('pk', flat=True))
    rows = []
    for p in qs:
        p.assigned_to_me = p.pk in my_ids
        rows.append(p)
    return rows, my_ids
