"""
Motor de transição do workflow (iniciar, aprovar, reprovar).

Mantém regras de negócio fora das views e modelos.
"""
from __future__ import annotations

from typing import Optional

from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone

from workflow_aprovacao.exceptions import (
    InvalidTransitionError,
    NoFlowConfigurationError,
    UnsupportedPolicyError,
)
from workflow_aprovacao.models import (
    ApprovalFlowDefinition,
    ApprovalHistoryEntry,
    ApprovalPolicy,
    ApprovalProcess,
    ApprovalStep,
    ApprovalStepParticipant,
    HistoryAction,
    OutboxStatus,
    ParticipantRole,
    ProcessStatus,
    SubjectKind,
    SyncStatus,
)

User = get_user_model()


class ApprovalEngine:
    """API síncrona do workflow."""

    @staticmethod
    def _first_active_step(flow: ApprovalFlowDefinition) -> Optional[ApprovalStep]:
        return (
            ApprovalStep.objects.filter(flow=flow, is_active=True)
            .order_by('sequence')
            .first()
        )

    @staticmethod
    def _next_active_step(flow: ApprovalFlowDefinition, after_sequence: int) -> Optional[ApprovalStep]:
        return (
            ApprovalStep.objects.filter(flow=flow, is_active=True, sequence__gt=after_sequence)
            .order_by('sequence')
            .first()
        )

    @classmethod
    def user_can_act_on_current_step(cls, process: ApprovalProcess, user: User) -> bool:
        if not user or not user.is_authenticated:
            return False
        if user.is_superuser:
            return process.status == ProcessStatus.AWAITING_STEP
        if process.status != ProcessStatus.AWAITING_STEP:
            return False
        step = process.current_step
        if not step:
            return False
        if step.approval_policy != ApprovalPolicy.SINGLE_ANY:
            return False
        roles = (ParticipantRole.APPROVER, ParticipantRole.OWNER)
        qs = ApprovalStepParticipant.objects.filter(step=step, role__in=roles)
        for p in qs:
            if p.subject_kind == SubjectKind.USER and p.user_id == user.id:
                return True
            if (
                p.subject_kind == SubjectKind.DJANGO_GROUP
                and p.django_group_id
                and user.groups.filter(pk=p.django_group_id).exists()
            ):
                return True
        return False

    @classmethod
    @transaction.atomic
    def start(
        cls,
        *,
        project,
        category,
        initiated_by: Optional[User] = None,
        title: str = '',
        summary: str = '',
        content_object=None,
        external_id: str = '',
        external_entity_type: str = '',
        sync_status=SyncStatus.NOT_APPLICABLE,
    ) -> ApprovalProcess:
        """
        Localiza fluxo ativo (project + category), cria processo na primeira alçada.
        """
        flow = (
            ApprovalFlowDefinition.objects.filter(
                project=project,
                category=category,
                is_active=True,
            )
            .select_for_update(of=('self',))
            .first()
        )
        if not flow:
            raise NoFlowConfigurationError(
                f'Sem fluxo ativo para obra {getattr(project, "code", project)} e categoria {category.code}.'
            )

        first = cls._first_active_step(flow)
        if not first:
            raise NoFlowConfigurationError('Fluxo sem alçadas ativas.')

        if first.approval_policy != ApprovalPolicy.SINGLE_ANY:
            raise UnsupportedPolicyError(
                'A primeira alçada usa uma política ainda não suportada.'
            )

        kwargs = {
            'flow_definition': flow,
            'project': project,
            'category': category,
            'status': ProcessStatus.AWAITING_STEP,
            'current_step': first,
            'title': title,
            'summary': summary,
            'initiated_by': initiated_by,
            'external_id': external_id or '',
            'external_entity_type': external_entity_type or '',
            'sync_status': sync_status,
        }
        if content_object is not None:
            kwargs['content_object'] = content_object

        process = ApprovalProcess.objects.create(**kwargs)

        ApprovalHistoryEntry.objects.create(
            process=process,
            step=first,
            step_sequence_snapshot=first.sequence,
            actor=initiated_by,
            action=HistoryAction.SUBMITTED,
            comment='',
            previous_status='',
            new_status=process.status,
            payload={},
        )
        if (external_id or '').strip():
            from workflow_aprovacao.services.backlog import mark_backlog_resolved_for_process

            mark_backlog_resolved_for_process(process)
        return process

    @classmethod
    @transaction.atomic
    def approve(cls, process: ApprovalProcess, *, user: User, comment: str = '') -> ApprovalProcess:
        process = ApprovalProcess.objects.select_for_update().get(pk=process.pk)
        if process.status != ProcessStatus.AWAITING_STEP:
            raise InvalidTransitionError('Processo não está aguardando aprovação.')

        if not cls.user_can_act_on_current_step(process, user):
            raise InvalidTransitionError('Usuário não pode aprovar nesta alçada.')

        step = process.current_step
        prev = process.status

        if step.approval_policy != ApprovalPolicy.SINGLE_ANY:
            raise UnsupportedPolicyError('Política de alçada não suportada.')

        next_step = cls._next_active_step(process.flow_definition, step.sequence)

        if next_step is None:
            process.status = ProcessStatus.APPROVED
            process.current_step = None
        else:
            process.current_step = next_step

        process.save(update_fields=['status', 'current_step', 'updated_at'])

        ApprovalHistoryEntry.objects.create(
            process=process,
            step=step,
            step_sequence_snapshot=step.sequence,
            actor=user,
            action=HistoryAction.APPROVED_STEP,
            comment=comment,
            previous_status=prev,
            new_status=process.status,
            payload={'advanced_to_sequence': next_step.sequence if next_step else None},
        )

        if process.status == ProcessStatus.APPROVED:
            cls._enqueue_final_sync_if_needed(process)

        return process

    @classmethod
    @transaction.atomic
    def reject(cls, process: ApprovalProcess, *, user: User, comment: str = '') -> ApprovalProcess:
        process = ApprovalProcess.objects.select_for_update().get(pk=process.pk)
        if process.status != ProcessStatus.AWAITING_STEP:
            raise InvalidTransitionError('Processo não está aguardando aprovação.')

        if not cls.user_can_act_on_current_step(process, user):
            raise InvalidTransitionError('Usuário não pode reprovar nesta alçada.')

        step = process.current_step
        prev = process.status
        process.status = ProcessStatus.REJECTED
        process.save(update_fields=['status', 'updated_at'])

        ApprovalHistoryEntry.objects.create(
            process=process,
            step=step,
            step_sequence_snapshot=step.sequence if step else None,
            actor=user,
            action=HistoryAction.REJECTED,
            comment=comment,
            previous_status=prev,
            new_status=process.status,
            payload={},
        )

        cls._enqueue_final_sync_if_needed(process)
        return process

    @classmethod
    def _enqueue_final_sync_if_needed(cls, process: ApprovalProcess) -> None:
        """
        Quando houver integração externa configurada, registra item na outbox.
        Implementação mínima: apenas estrutura; worker Celery pode consumir depois.
        """
        from workflow_aprovacao.models import ApprovalIntegrationOutbox

        if process.status not in (ProcessStatus.APPROVED, ProcessStatus.REJECTED):
            return
        if process.sync_status == SyncStatus.NOT_APPLICABLE and not (process.external_id or '').strip():
            return

        if process.sync_status == SyncStatus.NOT_APPLICABLE:
            process.sync_status = SyncStatus.PENDING
            process.save(update_fields=['sync_status', 'updated_at'])

        event_type = 'approval_finished'
        if ApprovalIntegrationOutbox.objects.filter(
            process=process,
            event_type=event_type,
            status=OutboxStatus.PENDING,
        ).exists():
            return

        ApprovalIntegrationOutbox.objects.create(
            process=process,
            event_type=event_type,
            payload={
                'process_id': process.pk,
                'status': process.status,
                'external_system': process.external_system,
                'external_id': process.external_id,
                'finished_at': timezone.now().isoformat(),
            },
            status=OutboxStatus.PENDING,
        )
