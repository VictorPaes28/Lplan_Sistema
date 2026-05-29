"""Smoke tests das views da Central de Aprovações."""
from datetime import date

from django.contrib.auth.models import Group, User
from django.test import Client, TestCase
from django.urls import reverse

from accounts.groups import GRUPOS
from accounts.models import UserSignupRequest
from core.models import Project
from workflow_aprovacao.models import (
    ApprovalFlowDefinition,
    ApprovalStep,
    ApprovalStepParticipant,
    ProcessCategory,
    SubjectKind,
    ParticipantRole,
)
from workflow_aprovacao.views import _workflow_select_options
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

    def test_home_redirects_aprovador_to_fila(self):
        self.client.login(username='wfview', password='secret')
        r = self.client.get(reverse('workflow_aprovacao:home'))
        self.assertEqual(r.status_code, 302)
        self.assertIn('/fila/', r.url)

    def test_config_forbidden_for_aprovador_only(self):
        self.client.login(username='wfview', password='secret')
        r = self.client.get(reverse('workflow_aprovacao:config_flow_list'))
        self.assertEqual(r.status_code, 403)

    def test_flow_edit_200_for_admin(self):
        admin_user = User.objects.create_user(username='wfadmin', password='secret')
        g, _ = Group.objects.get_or_create(name=GRUPOS.ADMINISTRADOR)
        admin_user.groups.add(g)
        self.client.login(username='wfadmin', password='secret')
        r = self.client.get(reverse('workflow_aprovacao:flow_edit', args=[self.flow.pk]))
        self.assertEqual(r.status_code, 200)


class WorkflowSelectOptionsTests(TestCase):
    def setUp(self):
        self.g_aprovador, _ = Group.objects.get_or_create(name=GRUPOS.CENTRAL_APROVACOES_APROVADOR)
        self.g_admin, _ = Group.objects.get_or_create(name=GRUPOS.CENTRAL_APROVACOES_ADMIN)
        self.g_externo, _ = Group.objects.get_or_create(name=GRUPOS.CENTRAL_APROVACOES_EXTERNO)

    def test_excludes_inactive_and_technical_accounts(self):
        normal = User.objects.create_user(
            username='victor.paes',
            email='victor@email.com',
            first_name='Victor',
            last_name='Paes',
            is_active=True,
        )
        normal.groups.add(self.g_aprovador)

        technical = User.objects.create_user(
            username='check_embed_header_user',
            email='check@email.com',
            first_name='Check',
            last_name='User',
            is_active=True,
        )
        technical.groups.add(self.g_aprovador)

        inactive = User.objects.create_user(
            username='aprovador.inativo',
            email='inativo@email.com',
            first_name='Aprovador',
            last_name='Inativo',
            is_active=False,
        )
        inactive.groups.add(self.g_admin)

        users, _groups = _workflow_select_options()
        ids = {int(row['id']) for row in users}
        self.assertIn(normal.pk, ids)
        self.assertNotIn(technical.pk, ids)
        self.assertNotIn(inactive.pk, ids)

    def test_formats_external_label_and_badge(self):
        externo = User.objects.create_user(
            username='externo.aprovador',
            email='externo@email.com',
            first_name='Aprovador',
            last_name='Externo',
            is_active=True,
        )
        externo.groups.add(self.g_externo)

        users, _groups = _workflow_select_options()
        row = next(item for item in users if int(item['id']) == externo.pk)
        self.assertEqual(row['label'], 'Aprovador Externo')
        self.assertEqual(row['secondary'], 'externo@email.com')
        self.assertEqual(row['badge'], 'Terceirizado')
        self.assertEqual(row['scope'], 'external')

    def test_marks_internal_scope_and_filters_groups_list(self):
        interno = User.objects.create_user(
            username='interno.aprovador',
            email='interno@email.com',
            first_name='Interno',
            last_name='Aprovador',
            is_active=True,
        )
        interno.groups.add(self.g_aprovador)
        Group.objects.get_or_create(name='Grupo Aleatorio Fora da Central')

        users, groups = _workflow_select_options()
        row = next(item for item in users if int(item['id']) == interno.pk)
        self.assertEqual(row['scope'], 'internal')
        group_labels = {g['label'] for g in groups}
        self.assertIn(GRUPOS.CENTRAL_APROVACOES_APROVADOR, group_labels)
        self.assertNotIn('Grupo Aleatorio Fora da Central', group_labels)


class WorkflowExternalPreSignupTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.admin_user = User.objects.create_user(username='wfconfig', password='secret')
        g, _ = Group.objects.get_or_create(name=GRUPOS.ADMINISTRADOR)
        self.admin_user.groups.add(g)
        self.project = Project.objects.create(
            name='Obra Externa',
            code='OB-EXT',
            start_date=date(2025, 1, 1),
            end_date=date(2026, 1, 1),
        )

    def test_creates_pending_external_signup_request(self):
        self.client.login(username='wfconfig', password='secret')
        url = reverse('workflow_aprovacao:external_signup_prefill_create')
        resp = self.client.post(
            url,
            data={
                'full_name': 'Fornecedor Externo',
                'company_name': 'Empresa XPTO',
                'email': 'externo.novo@email.com',
                'phone_whatsapp': '11999999999',
                'cnpj': '12.345.678/0001-99',
                'note': 'Pré-cadastro via configuração de fluxo',
            },
        )
        self.assertEqual(resp.status_code, 200)
        payload = resp.json()
        self.assertTrue(payload.get('ok'))
        req = UserSignupRequest.objects.get(email='externo.novo@email.com')
        self.assertEqual(req.status, UserSignupRequest.STATUS_PENDENTE)
        self.assertIn(GRUPOS.CENTRAL_APROVACOES_EXTERNO, req.requested_groups)
        self.assertEqual(req.requested_by_id, self.admin_user.pk)

    def test_returns_conflict_when_external_user_already_exists(self):
        ext = User.objects.create_user(
            username='externo.aprovado',
            password='secret',
            email='externo.existente@email.com',
            is_active=True,
        )
        g_ext, _ = Group.objects.get_or_create(name=GRUPOS.CENTRAL_APROVACOES_EXTERNO)
        ext.groups.add(g_ext)

        self.client.login(username='wfconfig', password='secret')
        url = reverse('workflow_aprovacao:external_signup_prefill_create')
        resp = self.client.post(
            url,
            data={
                'full_name': 'Fornecedor Existente',
                'email': 'externo.existente@email.com',
            },
        )
        self.assertEqual(resp.status_code, 409)
        payload = resp.json()
        self.assertFalse(payload.get('ok'))

    def test_premarked_project_is_sent_to_signup_request(self):
        self.client.login(username='wfconfig', password='secret')
        url = reverse('workflow_aprovacao:external_signup_prefill_create')
        resp = self.client.post(
            url,
            data={
                'full_name': 'Terceiro Projeto',
                'email': 'terceiro.projeto@email.com',
                'project_id': self.project.pk,
                'project_code': self.project.code,
                'project_name': self.project.name,
                'category_name': 'Contrato',
            },
        )
        self.assertEqual(resp.status_code, 200)
        req = UserSignupRequest.objects.get(email='terceiro.projeto@email.com')
        self.assertIn(self.project.pk, req.requested_project_ids)
        self.assertIn('Tipo de solicitação: Terceirizado externo', req.notes)
