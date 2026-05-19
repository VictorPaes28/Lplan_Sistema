"""
Regras de participação por alçada (etapa atual do processo).

Toda decisão (fila, botões, POST, motor) deve usar estas funções — nunca
participação em qualquer etapa do fluxo (``step__flow_id``).
"""
from __future__ import annotations

from typing import Optional

from django.contrib.auth import get_user_model
from django.db.models import Exists, OuterRef, Q

from workflow_aprovacao.models import (
    ApprovalPolicy,
    ApprovalProcess,
    ApprovalStep,
    ApprovalStepParticipant,
    ParticipantRole,
    ProcessStatus,
    SubjectKind,
)

User = get_user_model()

DECISION_ROLES = (ParticipantRole.OWNER, ParticipantRole.APPROVER)


def _participant_match_q(*, user: User, step_id: int) -> Q:
    """Participante decisor na alçada ``step_id`` para este utilizador."""
    q = Q(
        step_id=step_id,
        role__in=DECISION_ROLES,
        subject_kind=SubjectKind.USER,
        user_id=user.pk,
    )
    group_ids = list(user.groups.values_list('pk', flat=True))
    if group_ids:
        q = q | Q(
            step_id=step_id,
            role__in=DECISION_ROLES,
            subject_kind=SubjectKind.DJANGO_GROUP,
            django_group_id__in=group_ids,
        )
    return q


def user_is_decision_participant_on_step(user: User, step_id: int | None) -> bool:
    """Utilizador pode decidir na alçada indicada (utilizador direto ou grupo da etapa)."""
    if not user or not user.is_authenticated or not step_id:
        return False
    return ApprovalStepParticipant.objects.filter(_participant_match_q(user=user, step_id=step_id)).exists()


def user_can_decide_on_process(user: User, process: ApprovalProcess) -> bool:
    """
    Pode aprovar/reprovar/assinar agora: processo aguardando etapa, alçada atual
    configurada e participação apenas nessa alçada.
    """
    if not user or not user.is_authenticated:
        return False
    if process.status != ProcessStatus.AWAITING_STEP:
        return False
    step_id = process.current_step_id
    if not step_id:
        return False
    step = process.current_step
    if step is None:
        step = ApprovalStep.objects.filter(pk=step_id).first()
    if not step or not step.is_active:
        return False
    if step.approval_policy != ApprovalPolicy.SINGLE_ANY:
        return False
    return user_is_decision_participant_on_step(user, step_id)


def pending_processes_filter_q(user: User) -> Q:
    """Filtro Q para processos na fila pessoal do utilizador (etapa atual)."""
    if not user or not user.is_authenticated:
        return Q(pk__in=[])
    group_ids = list(user.groups.values_list('pk', flat=True))
    participant_filter = Q(
        step_id=OuterRef('current_step_id'),
        role__in=DECISION_ROLES,
        subject_kind=SubjectKind.USER,
        user_id=user.pk,
    )
    if group_ids:
        participant_filter = participant_filter | Q(
            step_id=OuterRef('current_step_id'),
            role__in=DECISION_ROLES,
            subject_kind=SubjectKind.DJANGO_GROUP,
            django_group_id__in=group_ids,
        )
    return Q(
        status=ProcessStatus.AWAITING_STEP,
        current_step_id__isnull=False,
    ) & Q(
        Exists(
            ApprovalStepParticipant.objects.filter(participant_filter)
        )
    )
