"""Testes da fila (abas e filtros) da Central de Aprovações."""
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
    ProcessStatus,
    SubjectKind,
)
from workflow_aprovacao.services.engine import ApprovalEngine
from workflow_aprovacao.services.inbox import (
    TAB_APROVADO,
    TAB_PENDENTE,
    TAB_REPROVADO,
    available_inbox_tabs,
    build_inbox_queryset,
    inbox_tab_counts,
)


class InboxServiceTests(TestCase):
    def setUp(self):
        self.cat = ProcessCategory.objects.get(code='contrato')
        self.project = Project.objects.create(
            name='Obra inbox',
            code='INB-1',
            start_date=date(2025, 1, 1),
            end_date=date(2026, 1, 1),
        )
        self.flow = ApprovalFlowDefinition.objects.create(
            project=self.project,
            category=self.cat,
            is_active=True,
        )
        self.step = ApprovalStep.objects.create(flow=self.flow, sequence=1, name='Única')
        self.approver = User.objects.create_user(username='inb_apr', password='x')
        g, _ = Group.objects.get_or_create(name=GRUPOS.CENTRAL_APROVACOES_APROVADOR)
        self.approver.groups.add(g)
        ApprovalStepParticipant.objects.create(
            step=self.step,
            role=ParticipantRole.APPROVER,
            subject_kind=SubjectKind.USER,
            user=self.approver,
        )

    def test_pending_tab_lists_awaiting_process(self):
        proc = ApprovalEngine.start(
            project=self.project,
            category=self.cat,
            initiated_by=self.approver,
            title='Pendente teste',
        )
        self.assertEqual(proc.status, ProcessStatus.AWAITING_STEP)
        qs = build_inbox_queryset(self.approver, tab=TAB_PENDENTE)
        self.assertIn(proc.pk, list(qs.values_list('pk', flat=True)))

    def test_approved_tab_after_decision(self):
        proc = ApprovalEngine.start(
            project=self.project,
            category=self.cat,
            initiated_by=self.approver,
            title='Aprovar',
        )
        ApprovalEngine.approve(proc, user=self.approver)
        proc.refresh_from_db()
        self.assertEqual(proc.status, ProcessStatus.APPROVED)
        qs = build_inbox_queryset(self.approver, tab=TAB_APROVADO)
        self.assertIn(proc.pk, list(qs.values_list('pk', flat=True)))
        pending = build_inbox_queryset(self.approver, tab=TAB_PENDENTE)
        self.assertNotIn(proc.pk, list(pending.values_list('pk', flat=True)))

    def test_rejected_tab(self):
        proc = ApprovalEngine.start(
            project=self.project,
            category=self.cat,
            initiated_by=self.approver,
            title='Reprovar',
        )
        ApprovalEngine.reject(proc, user=self.approver, comment='não')
        proc.refresh_from_db()
        self.assertEqual(proc.status, ProcessStatus.REJECTED)
        qs = build_inbox_queryset(self.approver, tab=TAB_REPROVADO)
        self.assertIn(proc.pk, list(qs.values_list('pk', flat=True)))

    def test_tabs_include_counts(self):
        ApprovalEngine.start(
            project=self.project,
            category=self.cat,
            initiated_by=self.approver,
            title='Um pendente',
        )
        tabs = available_inbox_tabs(self.approver)
        keys = {t['key'] for t in tabs}
        self.assertIn(TAB_PENDENTE, keys)
        self.assertIn(TAB_APROVADO, keys)
        counts = inbox_tab_counts(self.approver)
        self.assertGreaterEqual(counts[TAB_PENDENTE], 1)
        pendente_tab = next(t for t in tabs if t['key'] == TAB_PENDENTE)
        self.assertEqual(pendente_tab['count'], counts[TAB_PENDENTE])

    def test_search_by_pk(self):
        proc = ApprovalEngine.start(
            project=self.project,
            category=self.cat,
            initiated_by=self.approver,
            title='Busca',
        )
        qs = build_inbox_queryset(self.approver, tab=TAB_PENDENTE, q=str(proc.pk))
        self.assertEqual(list(qs.values_list('pk', flat=True)), [proc.pk])


class InboxViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.cat = ProcessCategory.objects.get(code='contrato')
        self.project = Project.objects.create(
            name='Obra view',
            code='INB-V',
            start_date=date(2025, 1, 1),
            end_date=date(2026, 1, 1),
        )
        self.flow = ApprovalFlowDefinition.objects.create(
            project=self.project,
            category=self.cat,
            is_active=True,
        )
        self.step = ApprovalStep.objects.create(flow=self.flow, sequence=1, name='Única')
        self.user = User.objects.create_user(username='inb_view', password='secret')
        g, _ = Group.objects.get_or_create(name=GRUPOS.CENTRAL_APROVACOES_APROVADOR)
        self.user.groups.add(g)
        ApprovalStepParticipant.objects.create(
            step=self.step,
            role=ParticipantRole.APPROVER,
            subject_kind=SubjectKind.USER,
            user=self.user,
        )

    def test_pending_page_renders_tabs(self):
        self.client.login(username='inb_view', password='secret')
        r = self.client.get(reverse('workflow_aprovacao:pending'))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'wf-inbox-tabs')
        self.assertContains(r, 'Minhas pendências')
        self.assertContains(r, 'Aprovados')

    def test_aba_aprovado_query(self):
        proc = ApprovalEngine.start(
            project=self.project,
            category=self.cat,
            initiated_by=self.user,
            title='Concluído',
        )
        ApprovalEngine.approve(proc, user=self.user)
        self.client.login(username='inb_view', password='secret')
        r = self.client.get(reverse('workflow_aprovacao:pending'), {'aba': TAB_APROVADO})
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, f'#{proc.pk}')
