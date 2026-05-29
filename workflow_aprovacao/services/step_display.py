"""Exibição da alçada atual e responsáveis na Central de Aprovações."""
from __future__ import annotations

from typing import Any, Optional

from django.contrib.auth import get_user_model

from workflow_aprovacao.models import (
    ApprovalPolicy,
    ApprovalProcess,
    ApprovalProcessParticipant,
    ApprovalStep,
    ApprovalStepParticipant,
    ParticipantRole,
    ProcessStatus,
    SubjectKind,
)

User = get_user_model()

_DECISION_ROLES = (ParticipantRole.OWNER, ParticipantRole.APPROVER)


def _participant_label(participant: ApprovalStepParticipant | ApprovalProcessParticipant) -> str:
    if participant.subject_kind == SubjectKind.USER and participant.user_id:
        u = participant.user
        return (u.get_full_name() or '').strip() or u.username
    if participant.subject_kind == SubjectKind.DJANGO_GROUP and participant.django_group_id:
        return f'Grupo «{participant.django_group.name}»'
    return 'Participante não configurado'


def _role_display(role: str) -> str:
    if role == ParticipantRole.OWNER:
        return 'Responsável'
    if role == ParticipantRole.APPROVER:
        return 'Aprovador'
    return 'Visualização'


def _user_matches_participant(user: User, process: ApprovalProcess, participant: ApprovalStepParticipant | ApprovalProcessParticipant) -> bool:
    from workflow_aprovacao.services.step_access import user_is_decision_participant_on_process_step

    if participant.role not in _DECISION_ROLES:
        return False
    return user_is_decision_participant_on_process_step(user, process, participant.step_id)


def _active_steps_count(flow_id: int) -> int:
    from workflow_aprovacao.models import ApprovalStep

    return ApprovalStep.objects.filter(flow_id=flow_id, is_active=True).count()


def build_current_step_display(
    process: ApprovalProcess,
    *,
    viewer: Optional[User] = None,
) -> dict[str, Any]:
    """
    Dados para destacar alçada atual e quem decide.
    Espera ``current_step`` com participantes em cache (prefetch) quando possível.
    """
    empty: dict[str, Any] = {
        'is_active': False,
        'sequence': None,
        'name': '',
        'description': '',
        'position_label': '',
        'policy_label': '',
        'responsibles': [],
        'responsibles_summary': '',
        'viewers': [],
        'viewer_is_responsible': False,
        'total_steps': 0,
    }
    if process.status != ProcessStatus.AWAITING_STEP:
        return empty
    step: Optional[ApprovalStep] = process.current_step
    if not step:
        return empty

    total = 0
    if process.flow_definition_id:
        total = _active_steps_count(process.flow_definition_id)

    from workflow_aprovacao.services.participants import participants_for_step

    participants = list(participants_for_step(process, step.pk))
    responsibles: list[dict[str, str]] = []
    viewers: list[dict[str, str]] = []
    viewer_is_responsible = False

    for p in participants:
        entry = {
            'label': _participant_label(p),
            'role': p.role,
            'role_display': _role_display(p.role),
            'kind': p.subject_kind,
        }
        if p.role in _DECISION_ROLES:
            responsibles.append(entry)
            if viewer and viewer.is_authenticated and _user_matches_participant(viewer, process, p):
                viewer_is_responsible = True
        elif p.role == ParticipantRole.VIEWER:
            viewers.append(entry)

    if not responsibles:
        responsibles.append(
            {
                'label': 'Nenhum aprovador configurado nesta alçada',
                'role': '',
                'role_display': 'Atenção',
                'kind': '',
            }
        )

    summary_parts = [
        f'{r["label"]} ({r["role_display"].lower()})' for r in responsibles if r.get('label')
    ]
    position = f'Alçada {step.sequence}'
    if total:
        position = f'{position} de {total}'

    return {
        'is_active': True,
        'sequence': step.sequence,
        'name': step.name,
        'description': (step.description or '').strip(),
        'position_label': position,
        'policy_label': '',
        'responsibles': responsibles,
        'responsibles_summary': ' · '.join(summary_parts),
        'viewers': viewers,
        'viewer_is_responsible': viewer_is_responsible,
        'total_steps': total,
    }
