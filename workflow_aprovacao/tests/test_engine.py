"""Testes do motor de aprovação (workflow_aprovacao)."""
from datetime import date

from django.contrib.auth.models import Group, User
from django.test import TestCase

from core.models import Project
from workflow_aprovacao.exceptions import (
    InvalidTransitionError,
    NoFlowConfigurationError,
)
from workflow_aprovacao.models import (
    ApprovalFlowDefinition,
    ApprovalStep,
    ApprovalStepParticipant,
    HistoryAction,
    ParticipantRole,
    ProcessCategory,
    ProcessStatus,
    SubjectKind,
)
from workflow_aprovacao.services.engine import ApprovalEngine


def _minimal_project(code_suffix: str) -> Project:
    return Project.objects.create(
        name=f'Obra teste {code_suffix}',
        code=f'TST-{code_suffix}',
        start_date=date(2025, 1, 1),
        end_date=date(2026, 12, 31),
    )


class ApprovalEngineFlowTests(TestCase):
    def setUp(self):
        self.cat = ProcessCategory.objects.get(code='contrato')
        self.project = _minimal_project('wf1')
        self.flow = ApprovalFlowDefinition.objects.create(
            project=self.project,
            category=self.cat,
            is_active=True,
        )
        self.s1 = ApprovalStep.objects.create(
            flow=self.flow,
            sequence=1,
            name='Alçada 1',
        )
        self.s2 = ApprovalStep.objects.create(
            flow=self.flow,
            sequence=2,
            name='Alçada 2',
        )
        self.user_a = User.objects.create_user(username='aprov1', password='x')
        self.user_b = User.objects.create_user(username='aprov2', password='x')
        self.other = User.objects.create_user(username='other', password='x')
        ApprovalStepParticipant.objects.create(
            step=self.s1,
            role=ParticipantRole.APPROVER,
            subject_kind=SubjectKind.USER,
            user=self.user_a,
        )
        ApprovalStepParticipant.objects.create(
            step=self.s2,
            role=ParticipantRole.APPROVER,
            subject_kind=SubjectKind.USER,
            user=self.user_b,
        )

    def test_start_without_flow_raises(self):
        p = _minimal_project('noflow')
        with self.assertRaises(NoFlowConfigurationError):
            ApprovalEngine.start(project=p, category=self.cat, initiated_by=self.user_a)

    def test_happy_path_two_steps(self):
        proc = ApprovalEngine.start(
            project=self.project,
            category=self.cat,
            initiated_by=self.user_a,
            title='Teste',
        )
        self.assertEqual(proc.status, ProcessStatus.AWAITING_STEP)
        self.assertEqual(proc.current_step_id, self.s1.id)

        with self.assertRaises(InvalidTransitionError):
            ApprovalEngine.reject(proc, user=self.user_b, comment='x')

        ApprovalEngine.approve(proc, user=self.user_a, comment='ok')
        proc.refresh_from_db()
        self.assertEqual(proc.current_step_id, self.s2.id)
        self.assertEqual(proc.status, ProcessStatus.AWAITING_STEP)

        ApprovalEngine.approve(proc, user=self.user_b)
        proc.refresh_from_db()
        self.assertEqual(proc.status, ProcessStatus.APPROVED)
        self.assertIsNone(proc.current_step)

        entries = list(proc.history_entries.order_by('created_at').values_list('action', flat=True))
        self.assertEqual(
            entries,
            [HistoryAction.SUBMITTED, HistoryAction.APPROVED_STEP, HistoryAction.APPROVED_STEP],
        )

    def test_reject_stops(self):
        proc = ApprovalEngine.start(
            project=self.project,
            category=self.cat,
            initiated_by=self.user_a,
        )
        ApprovalEngine.reject(proc, user=self.user_a, comment='não')
        proc.refresh_from_db()
        self.assertEqual(proc.status, ProcessStatus.REJECTED)

    def test_group_participant(self):
        g = Group.objects.create(name='WF-Test-Group')
        self.user_a.groups.add(g)
        ApprovalStepParticipant.objects.filter(step=self.s1).delete()
        ApprovalStepParticipant.objects.create(
            step=self.s1,
            role=ParticipantRole.APPROVER,
            subject_kind=SubjectKind.DJANGO_GROUP,
            django_group=g,
        )
        proc = ApprovalEngine.start(project=self.project, category=self.cat, initiated_by=self.other)
        self.assertTrue(ApprovalEngine.user_can_act_on_current_step(proc, self.user_a))
        self.assertFalse(ApprovalEngine.user_can_act_on_current_step(proc, self.other))
