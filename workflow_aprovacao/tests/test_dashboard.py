"""Visão geral da Central de Aprovações."""
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
    ParticipantRole,
    ProcessCategory,
    SubjectKind,
)
from workflow_aprovacao.services.dashboard import dashboard_context_for_user
from workflow_aprovacao.services.engine import ApprovalEngine


class DashboardContextTests(TestCase):
    def setUp(self):
        self.cat = ProcessCategory.objects.get(code='contrato')
        self.project = Project.objects.create(
            name='Dash',
            code='DASH-1',
            start_date=date(2025, 1, 1),
            end_date=date(2026, 1, 1),
        )
        self.flow = ApprovalFlowDefinition.objects.create(
            project=self.project, category=self.cat, is_active=True
        )
        self.step = ApprovalStep.objects.create(flow=self.flow, sequence=1, name='Única')
        self.user = User.objects.create_user(username='dash_user', password='x')
        g, _ = Group.objects.get_or_create(name=GRUPOS.CENTRAL_APROVACOES_APROVADOR)
        self.user.groups.add(g)
        ApprovalStepParticipant.objects.create(
            step=self.step,
            role=ParticipantRole.APPROVER,
            subject_kind=SubjectKind.USER,
            user=self.user,
        )

    def test_kpis_include_pending_count(self):
        ApprovalEngine.start(
            project=self.project,
            category=self.cat,
            initiated_by=self.user,
            title='Pendente',
        )
        ctx = dashboard_context_for_user(self.user)
        self.assertGreaterEqual(ctx['pending_count'], 1)
        keys = [k['key'] for k in ctx['dashboard_kpis']]
        self.assertIn('pendente', keys)
        self.assertIn('aprovado', keys)

    def test_dashboard_page_no_config_backlog_tile(self):
        client = Client()
        client.login(username='dash_user', password='x')
        admin = User.objects.create_user(username='dash_admin', password='x')
        ga, _ = Group.objects.get_or_create(name=GRUPOS.CENTRAL_APROVACOES_ADMIN)
        admin.groups.add(ga)
        client.login(username='dash_admin', password='x')
        r = client.get(reverse('workflow_aprovacao:home'))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'wf-dashboard-stats')
        self.assertContains(r, 'wf-dashboard-top')
        self.assertNotContains(r, 'Pendências de configuração')
        self.assertNotContains(r, 'Visão geral</p>')
