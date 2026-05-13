"""Consultas reutilizáveis para o painel e relatórios."""
from django.db.models import Exists, OuterRef, Q

from workflow_aprovacao.models import (
    ApprovalHistoryEntry,
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
    if not user or not user.is_authenticated:
        return pending, ApprovalProcess.objects.none()
    # Evita montar lista gigante ``pk__in`` com todos os processos já tocados no histórico
    # (para utilizadores antigos isto pode ser dezenas de milhares de IDs → consulta pesada).
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
