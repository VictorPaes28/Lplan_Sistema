"""Smoke tests das views da Central de Aprovações."""
from datetime import date

from django.contrib.auth.models import Group, User
from django.test import Client, TestCase
from django.urls import reverse

from accounts.groups import GRUPOS
from core.models import Project
from workflow_aprovacao.models import (
    ApprovalFlowDefinition,
    ApprovalStep,
    ApprovalStepParticipant,
    ProcessCategory,
    SubjectKind,
    ParticipantRole,
)
class WorkflowViewsSmokeTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.project = Project.objects.create(
            name='P',
            code='VW-1',
            start_date=date(2025, 1, 1),
            end_date=date(2026, 1, 1),
        )
        self.cat = ProcessCategory.objects.get(code='contrato')
        self.flow = ApprovalFlowDefinition.objects.create(
            project=self.project,
            category=self.cat,
            is_active=True,
        )
        self.step = ApprovalStep.objects.create(
            flow=self.flow,
            sequence=1,
            name='Única',
        )
        self.user = User.objects.create_user(username='wfview', password='secret')
        g, _ = Group.objects.get_or_create(name=GRUPOS.CENTRAL_APROVACOES_APROVADOR)
        self.user.groups.add(g)
        ApprovalStepParticipant.objects.create(
            step=self.step,
            role=ParticipantRole.APPROVER,
            subject_kind=SubjectKind.USER,
            user=self.user,
        )

    def test_pending_requires_login(self):
        r = self.client.get(reverse('workflow_aprovacao:pending'))
        self.assertEqual(r.status_code, 302)

    def test_pending_200_when_logged_in(self):
        self.client.login(username='wfview', password='secret')
        r = self.client.get(reverse('workflow_aprovacao:pending'))
        self.assertEqual(r.status_code, 200)

    def test_config_forbidden_for_aprovador_only(self):
        self.client.login(username='wfview', password='secret')
        r = self.client.get(reverse('workflow_aprovacao:config_flow_list'))
        self.assertEqual(r.status_code, 403)
