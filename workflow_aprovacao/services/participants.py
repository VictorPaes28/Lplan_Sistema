from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional

from django.contrib.auth import get_user_model
from django.db import transaction

from workflow_aprovacao.models import (
    ApprovalProcess,
    ApprovalProcessParticipant,
    ApprovalStep,
    ApprovalStepParticipant,
    ParticipantRole,
    SubjectKind,
)

User = get_user_model()


@dataclass(frozen=True)
class VariableParticipantInput:
    step_participant_id: int
    subject_kind: str
    user_id: Optional[int] = None
    django_group_id: Optional[int] = None


def participants_for_step(process: ApprovalProcess, step_id: int) -> Iterable[ApprovalProcessParticipant | ApprovalStepParticipant]:
    """
    Participantes efetivos da alçada no processo; fallback para fluxo legado.
    """
    effective = list(
        ApprovalProcessParticipant.objects.filter(process=process, step_id=step_id).select_related(
            'user', 'django_group'
        )
    )
    if effective:
        return effective
    return list(
        ApprovalStepParticipant.objects.filter(step_id=step_id).select_related('user', 'django_group')
    )


def step_requires_runtime_values(step: ApprovalStep) -> bool:
    return ApprovalStepParticipant.objects.filter(step=step, is_variable=True, required_on_create=True).exists()


@transaction.atomic
def initialize_process_participants(
    *,
    process: ApprovalProcess,
    variable_inputs: Iterable[VariableParticipantInput] | None = None,
    allow_missing_required_variables: bool = False,
) -> None:
    """
    Resolve participantes de fluxo em participantes efetivos no processo.
    """
    inputs = {int(v.step_participant_id): v for v in (variable_inputs or [])}
    rows: list[ApprovalProcessParticipant] = []
    for source in ApprovalStepParticipant.objects.filter(step__flow=process.flow_definition).order_by(
        'step__sequence', 'pk'
    ):
        if source.is_variable:
            provided = inputs.get(source.pk)
            if not provided:
                if source.required_on_create and not allow_missing_required_variables:
                    raise ValueError(
                        f'Participante variável obrigatório não informado na alçada {source.step.sequence}.'
                    )
                continue
            if provided.subject_kind not in (SubjectKind.USER, SubjectKind.DJANGO_GROUP):
                raise ValueError('Tipo de participante variável inválido.')
            if provided.subject_kind == SubjectKind.USER and not provided.user_id:
                raise ValueError('Utilizador obrigatório para participante variável.')
            if provided.subject_kind == SubjectKind.DJANGO_GROUP and not provided.django_group_id:
                raise ValueError('Grupo obrigatório para participante variável.')
            rows.append(
                ApprovalProcessParticipant(
                    process=process,
                    step_id=source.step_id,
                    role=source.role,
                    subject_kind=provided.subject_kind,
                    user_id=provided.user_id,
                    django_group_id=provided.django_group_id,
                    source_step_participant=source,
                    is_runtime_variable=True,
                    label_override=(source.variable_label or '').strip(),
                )
            )
            continue
        rows.append(
            ApprovalProcessParticipant(
                process=process,
                step_id=source.step_id,
                role=source.role,
                subject_kind=source.subject_kind,
                user_id=source.user_id,
                django_group_id=source.django_group_id,
                source_step_participant=source,
                is_runtime_variable=False,
                label_override='',
            )
        )
    if rows:
        ApprovalProcessParticipant.objects.bulk_create(rows)


def process_has_effective_participants(process: ApprovalProcess) -> bool:
    return ApprovalProcessParticipant.objects.filter(process=process).exists()


@transaction.atomic
def bind_external_user_to_process_step(
    *,
    process: ApprovalProcess,
    step: ApprovalStep,
    user: User,
    label: str = 'Terceirizado responsável',
) -> ApprovalProcessParticipant:
    """
    Força vinculação de usuário externo à alçada no processo (fallback manual).
    """
    ApprovalProcessParticipant.objects.filter(
        process=process,
        step=step,
        role=ParticipantRole.APPROVER,
    ).delete()
    return ApprovalProcessParticipant.objects.create(
        process=process,
        step=step,
        role=ParticipantRole.APPROVER,
        subject_kind=SubjectKind.USER,
        user=user,
        django_group=None,
        source_step_participant=None,
        is_runtime_variable=True,
        label_override=(label or '').strip(),
    )


def bind_external_user_to_variable_slot(*, request_obj, user: User) -> ApprovalProcessParticipant:
    """
    Vincula usuário externo aprovado ao participante variável pendente.
    """
    process = request_obj.process
    step = request_obj.step
    source = ApprovalStepParticipant.objects.filter(
        step=step,
        is_variable=True,
        variable_key=request_obj.variable_key,
    ).order_by('pk').first()
    if not source:
        return bind_external_user_to_process_step(
            process=process,
            step=step,
            user=user,
            label='Terceirizado responsável',
        )
    row, _ = ApprovalProcessParticipant.objects.update_or_create(
        process=process,
        step=step,
        source_step_participant=source,
        defaults={
            'role': source.role,
            'subject_kind': SubjectKind.USER,
            'user': user,
            'django_group': None,
            'is_runtime_variable': True,
            'label_override': (source.variable_label or '').strip(),
        },
    )
    return row
