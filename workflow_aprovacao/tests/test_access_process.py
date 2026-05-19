from datetime import date

from django.contrib.auth.models import Group, User
from django.test import TestCase

from accounts.groups import GRUPOS
from core.models import Project
from workflow_aprovacao.access import user_can_view_process
from workflow_aprovacao.models import (
    ApprovalFlowDefinition,
    ApprovalProcess,
    ApprovalStep,
    ApprovalStepParticipant,
    ParticipantRole,
    ProcessCategory,
    SubjectKind,
)
from workflow_aprovacao.services.engine import ApprovalEngine


class WorkflowProcessAccessTests(TestCase):
    def setUp(self):
        self.cat = ProcessCategory.objects.get(code='medicao')
        self.project = Project.objects.create(
            code='WF-01',
            name='Proj',
            is_active=True,
            start_date=date(2025, 1, 1),
            end_date=date(2026, 12, 31),
        )
        self.admin = User.objects.create_user('wf_admin', password='x')
        g, _ = Group.objects.get_or_create(name=GRUPOS.CENTRAL_APROVACOES_ADMIN)
        self.admin.groups.add(g)
        self.externo = User.objects.create_user('wf_ext', password='x')
        g2, _ = Group.objects.get_or_create(name=GRUPOS.CENTRAL_APROVACOES_EXTERNO)
        self.externo.groups.add(g2)
        self.outsider = User.objects.create_user('wf_out', password='x')
        flow = ApprovalFlowDefinition.objects.create(
            project=self.project,
            category=self.cat,
            is_active=True,
        )
        step = ApprovalStep.objects.create(flow=flow, sequence=1, name='S1', is_active=True)
        ApprovalStepParticipant.objects.create(
            step=step,
            role=ParticipantRole.APPROVER,
            subject_kind=SubjectKind.USER,
            user=self.externo,
        )
        self.process = ApprovalEngine.start(
            project=self.project,
            category=self.cat,
            initiated_by=self.admin,
            title='Teste',
        )

    def test_admin_can_view_any_process(self):
        self.assertTrue(user_can_view_process(self.admin, self.process))

    def test_participant_can_view(self):
        self.assertTrue(user_can_view_process(self.externo, self.process))

    def test_outsider_cannot_view(self):
        self.assertFalse(user_can_view_process(self.outsider, self.process))
