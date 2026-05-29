from datetime import date

from django.test import RequestFactory, TestCase

from accounts.signup_services import build_default_password
from core.models import Project
from workflow_aprovacao.models import (
    ApprovalFlowDefinition,
    ApprovalProcess,
    ApprovalStep,
    ExternalParticipantSignupRequest,
    ExternalSignupStatus,
    ProcessCategory,
)
from workflow_aprovacao.services.external_credentials_share import (
    build_external_credentials_message,
    build_external_credentials_whatsapp_url,
)


class ExternalCredentialsShareTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.category = ProcessCategory.objects.get(code='contrato')
        self.project = Project.objects.create(
            name='Obra WA',
            code='WA-1',
            is_active=True,
            start_date=date(2025, 1, 1),
            end_date=date(2026, 1, 1),
        )
        self.flow = ApprovalFlowDefinition.objects.create(
            project=self.project,
            category=self.category,
            is_active=True,
        )
        self.step = ApprovalStep.objects.create(flow=self.flow, sequence=1, name='Externo')
        self.process = ApprovalProcess.objects.create(
            project=self.project,
            category=self.category,
            flow_definition=self.flow,
            current_step=self.step,
            title='Pedido teste',
        )

    def test_whatsapp_url_includes_credentials_for_new_user(self):
        from django.contrib.auth.models import User

        user = User.objects.create_user('novo.ext', 'novo@example.com', 'x')
        req = ExternalParticipantSignupRequest.objects.create(
            process=self.process,
            step=self.step,
            full_name='João Silva',
            email='novo@example.com',
            phone_whatsapp='11987654321',
            status=ExternalSignupStatus.APPROVED,
            linked_user=user,
            created_linked_user=True,
        )
        request = self.factory.get('/aprovacoes/config/externos/')
        url = build_external_credentials_whatsapp_url(request=request, signup_request=req)
        self.assertIn('https://wa.me/5511987654321?text=', url)
        message = build_external_credentials_message(
            signup_request=req,
            login_url='http://test/login/',
            process_access_url='http://test/processo/1/',
        )
        expected_password = build_default_password('João', 'Silva')
        self.assertIn('Usuário: novo.ext', message)
        self.assertIn(f'Senha temporária: {expected_password}', message)
        self.assertIn('http://test/processo/1/', message)

    def test_whatsapp_url_without_phone_uses_generic_wa_me(self):
        from django.contrib.auth.models import User

        user = User.objects.create_user('ext2', 'ext2@example.com', 'x')
        req = ExternalParticipantSignupRequest.objects.create(
            process=self.process,
            step=self.step,
            full_name='Maria',
            email='ext2@example.com',
            status=ExternalSignupStatus.APPROVED,
            linked_user=user,
            created_linked_user=False,
        )
        request = self.factory.get('/aprovacoes/config/externos/')
        url = build_external_credentials_whatsapp_url(request=request, signup_request=req)
        self.assertTrue(url.startswith('https://wa.me/?text='))

    def test_central_signup_whatsapp_url_for_workflow_linked(self):
        from django.contrib.auth.models import User

        from accounts.models import UserSignupRequest
        from workflow_aprovacao.services.external_credentials_share import build_central_signup_whatsapp_url

        user = User.objects.create_user('cent.ext', 'cent@example.com', 'x')
        central = UserSignupRequest.objects.create(
            full_name='Cent Ext',
            email='cent@example.com',
            phone='11987654321',
            status=UserSignupRequest.STATUS_APROVADO,
            approved_user=user,
            requested_groups=['Central Aprovacoes Externo'],
        )
        wf = ExternalParticipantSignupRequest.objects.create(
            process=self.process,
            step=self.step,
            full_name='Cent Ext',
            email='cent@example.com',
            phone_whatsapp='11987654321',
            status=ExternalSignupStatus.APPROVED,
            linked_user=user,
            created_linked_user=True,
            central_signup_request=central,
        )
        request = self.factory.get('/central/cadastros/')
        url = build_central_signup_whatsapp_url(request=request, signup_request=central)
        self.assertIn('https://wa.me/5511987654321?text=', url)
        self.assertIn('cent.ext', url)
