"""Consultas reutilizáveis para o painel e relatórios."""
from django.db.models import Q

from workflow_aprovacao.models import (
    ApprovalProcess,
    ParticipantRole,
    ProcessStatus,
    SubjectKind,
)


def processes_pending_for_user(user):
    """
    Processos aguardando ação em que o usuário é aprovador na alçada atual
    (usuário direto ou membro de grupo Django).
    """
    if not user or not user.is_authenticated:
        return ApprovalProcess.objects.none()

    group_ids = list(user.groups.values_list('pk', flat=True))
    role_ok = (ParticipantRole.APPROVER, ParticipantRole.OWNER)

    user_q = Q(
        current_step__participants__subject_kind=SubjectKind.USER,
        current_step__participants__user=user,
        current_step__participants__role__in=role_ok,
    )
    group_q = Q()
    if group_ids:
        group_q = Q(
            current_step__participants__subject_kind=SubjectKind.DJANGO_GROUP,
            current_step__participants__django_group_id__in=group_ids,
            current_step__participants__role__in=role_ok,
        )

    return (
        ApprovalProcess.objects.filter(status=ProcessStatus.AWAITING_STEP)
        .filter(user_q | group_q)
        .select_related('project', 'category', 'current_step', 'flow_definition')
        .distinct()
        .order_by('-created_at')
    )


def processes_inbox_snapshot(user, limit: int = 100):
    """Pendentes + últimos concluídos/reprovados envolvendo o usuário (visão resumida)."""
    pending = processes_pending_for_user(user)
    # Concluídos recentes onde o usuário aparece no histórico
    from workflow_aprovacao.models import ApprovalHistoryEntry

    touched_ids = ApprovalHistoryEntry.objects.filter(actor=user).values_list(
        'process_id', flat=True
    )
    recent = (
        ApprovalProcess.objects.filter(pk__in=touched_ids)
        .exclude(status=ProcessStatus.AWAITING_STEP)
        .select_related('project', 'category')
        .order_by('-updated_at')[: limit]
    )
    return pending, recent
