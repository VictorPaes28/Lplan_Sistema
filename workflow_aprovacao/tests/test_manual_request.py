from datetime import date

from django.contrib.auth.models import Group, User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase
from django.urls import reverse

from accounts.groups import GRUPOS
from accounts.models import UserSignupRequest
from core.models import Project
from workflow_aprovacao.models import (
    ApprovalFlowDefinition,
    ApprovalProcess,
    ApprovalProcessAttachment,
    ApprovalProcessParticipant,
    ApprovalStep,
    ApprovalStepParticipant,
    ExternalParticipantSignupRequest,
    ExternalSignupStatus,
    ParticipantRole,
    ProcessCategory,
    ProcessStatus,
    SubjectKind,
)
from workflow_aprovacao.services.participants import VariableParticipantInput
from workflow_aprovacao.services.external_signup import ExternalCandidate, approve_external_signup_request, create_external_signup_request
from workflow_aprovacao.services.engine import ApprovalEngine


class ManualRequestWorkflowTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.project = Project.objects.create(
            name='Obra manual',
            code='MAN-1',
            is_active=True,
            start_date=date(2025, 1, 1),
            end_date=date(2026, 1, 1),
        )
        self.category = ProcessCategory.objects.get(code='contrato')
        self.flow = ApprovalFlowDefinition.objects.create(
            project=self.project,
            category=self.category,
            is_active=True,
        )
        self.step1 = ApprovalStep.objects.create(flow=self.flow, sequence=1, name='Externo')
        self.step2 = ApprovalStep.objects.create(flow=self.flow, sequence=2, name='Interno')
        self.slot = ApprovalStepParticipant.objects.create(
            step=self.step1,
            role=ParticipantRole.APPROVER,
            subject_kind=SubjectKind.USER,
            is_variable=True,
            variable_key='terceiro_responsavel',
            variable_label='Terceirizado',
            required_on_create=True,
            variable_subject_kind=SubjectKind.USER,
            user=None,
        )
        self.internal_approver = User.objects.create_user('apr_int', password='x')
        ApprovalStepParticipant.objects.create(
            step=self.step2,
            role=ParticipantRole.APPROVER,
            subject_kind=SubjectKind.USER,
            user=self.internal_approver,
        )
        self.creator = User.objects.create_user('creator_manual', password='x')
        Group.objects.get_or_create(name=GRUPOS.CENTRAL_APROVACOES_APROVADOR)[0].user_set.add(
            self.creator
        )
        self.admin = User.objects.create_user('wf_admin_manual', password='x')
        Group.objects.get_or_create(name=GRUPOS.CENTRAL_APROVACOES_ADMIN)[0].user_set.add(self.admin)
        self.external_existing = User.objects.create_user(
            username='ext_exist',
            email='ext.exist@example.com',
            password='x',
        )
        Group.objects.get_or_create(name=GRUPOS.CENTRAL_APROVACOES_EXTERNO)[0].user_set.add(
            self.external_existing
        )

    def _base_payload(self):
        return {
            'project': str(self.project.pk),
            'category': str(self.category.pk),
            'title': 'Pedido manual contrato',
            'summary': 'Resumo manual',
            'notes': 'obs',
            'amount': '1200.50',
            'period_reference': '05/2026',
            'vendor_name': 'Fornecedor XPTO',
            'document_url': 'https://example.com/doc.pdf',
            'category_payload_json': '{"vigencia_escopo":"12 meses"}',
        }

    def test_create_manual_request_with_existing_external_user(self):
        process = ApprovalEngine.start(
            project=self.project,
            category=self.category,
            initiated_by=self.creator,
            title='Pedido manual contrato',
            summary='Resumo manual',
            external_system='manual',
            external_entity_type='manual_request',
            variable_inputs=[
                VariableParticipantInput(
                    step_participant_id=self.slot.pk,
                    subject_kind='user',
                    user_id=self.external_existing.pk,
                )
            ],
        )
        self.assertIsNotNone(process)
        self.assertEqual(process.external_system, 'manual')
        self.assertEqual(process.external_entity_type, 'manual_request')
        row = ApprovalProcessParticipant.objects.filter(
            process=process,
            step=self.step1,
            user=self.external_existing,
            is_runtime_variable=True,
        ).first()
        self.assertIsNotNone(row)
        self.assertFalse(
            ExternalParticipantSignupRequest.objects.filter(process=process).exists()
        )

    def test_create_manual_request_generates_pending_external_signup(self):
        process = ApprovalEngine.start(
            project=self.project,
            category=self.category,
            initiated_by=self.creator,
            title='Pedido manual pendente externo',
            summary='Resumo manual',
            external_system='manual',
            external_entity_type='manual_request',
            allow_missing_required_variables=True,
        )
        create_external_signup_request(
            process=process,
            step=self.step1,
            requester=self.creator,
            variable_key=self.slot.variable_key,
            candidate=ExternalCandidate(
                full_name='Terceiro Novo',
                company_name='Terceiros SA',
                email='novo.terceiro@example.com',
                phone_whatsapp='11999999999',
            ),
        )
        self.assertIsNotNone(process)
        req = ExternalParticipantSignupRequest.objects.filter(process=process).first()
        self.assertIsNotNone(req)
        self.assertEqual(req.status, ExternalSignupStatus.PENDING)
        self.assertIsNotNone(req.central_signup_request_id)
        central = req.central_signup_request
        self.assertEqual(central.status, UserSignupRequest.STATUS_PENDENTE)
        self.assertIn(GRUPOS.CENTRAL_APROVACOES_EXTERNO, central.requested_groups or [])
        self.assertFalse(
            ApprovalProcessParticipant.objects.filter(process=process, step=self.step1).exists()
        )

    def test_admin_approves_external_signup_and_binds_participant(self):
        process = ApprovalEngine.start(
            project=self.project,
            category=self.category,
            initiated_by=self.creator,
            title='Pedido manual aprovacao externo',
            summary='Resumo',
            external_system='manual',
            external_entity_type='manual_request',
            allow_missing_required_variables=True,
        )
        req = create_external_signup_request(
            process=process,
            step=self.step1,
            requester=self.creator,
            variable_key=self.slot.variable_key,
            candidate=ExternalCandidate(
                full_name='Terceiro Novo',
                company_name='Terceiros SA',
                email='novo.bind@example.com',
                phone_whatsapp='11998887777',
            ),
        )
        linked = approve_external_signup_request(
            request_obj=req,
            reviewer=self.admin,
            access_url_builder=lambda _u, _p: f'/aprovacoes/processo/{_p.pk}/',
        )
        req.refresh_from_db()
        self.assertEqual(req.status, ExternalSignupStatus.APPROVED)
        self.assertEqual(req.linked_user_id, linked.pk)
        self.assertTrue(req.created_linked_user)
        self.assertIsNotNone(req.central_signup_request_id)
        req.central_signup_request.refresh_from_db()
        self.assertEqual(req.central_signup_request.status, UserSignupRequest.STATUS_APROVADO)
        self.assertEqual(req.central_signup_request.approved_user_id, linked.pk)
        self.assertTrue(
            ApprovalProcessParticipant.objects.filter(
                process=process, step=self.step1, user_id=req.linked_user_id
            ).exists()
        )

    def test_previous_step_user_cannot_decide_future_step(self):
        from workflow_aprovacao.services.engine import ApprovalEngine

        process = ApprovalEngine.start(
            project=self.project,
            category=self.category,
            initiated_by=self.creator,
            title='Teste alçada',
            variable_inputs=[
                VariableParticipantInput(
                    step_participant_id=self.slot.pk,
                    subject_kind='user',
                    user_id=self.external_existing.pk,
                )
            ],
        )
        ApprovalEngine.approve(process, user=self.external_existing, comment='ok 1')
        process.refresh_from_db()
        self.assertEqual(process.status, ProcessStatus.AWAITING_STEP)
        self.assertEqual(process.current_step_id, self.step2.pk)
        self.assertFalse(
            ApprovalProcessParticipant.objects.filter(
                process=process,
                step=self.step2,
                user=self.external_existing,
            ).exists()
        )
        from workflow_aprovacao.services.step_access import user_can_decide_on_process

        self.assertFalse(user_can_decide_on_process(self.external_existing, process))

    def test_external_user_cannot_open_other_process(self):
        process_ok = ApprovalEngine.start(
            project=self.project,
            category=self.category,
            initiated_by=self.creator,
            title='Pedido do ext A',
            variable_inputs=[
                VariableParticipantInput(
                    step_participant_id=self.slot.pk,
                    subject_kind='user',
                    user_id=self.external_existing.pk,
                )
            ],
        )

        other_ext = User.objects.create_user('other_ext', password='x')
        Group.objects.get_or_create(name=GRUPOS.CENTRAL_APROVACOES_EXTERNO)[0].user_set.add(other_ext)
        process_other = ApprovalEngine.start(
            project=self.project,
            category=self.category,
            initiated_by=self.creator,
            title='Pedido do ext B',
            variable_inputs=[
                VariableParticipantInput(
                    step_participant_id=self.slot.pk,
                    subject_kind='user',
                    user_id=other_ext.pk,
                )
            ],
        )

        self.client.login(username='ext_exist', password='x')
        r_ok = self.client.get(reverse('workflow_aprovacao:process_detail', args=[process_ok.pk]))
        self.assertEqual(r_ok.status_code, 200)
        r_other = self.client.get(reverse('workflow_aprovacao:process_detail', args=[process_other.pk]))
        self.assertEqual(r_other.status_code, 403)

    def test_manual_request_contract_implicit_external_generates_signup(self):
        project2 = Project.objects.create(
            name='Obra fallback',
            code='MAN-2',
            is_active=True,
            start_date=date(2025, 1, 1),
            end_date=date(2026, 1, 1),
        )
        flow2 = ApprovalFlowDefinition.objects.create(
            project=project2,
            category=self.category,
            is_active=True,
        )
        step_a = ApprovalStep.objects.create(flow=flow2, sequence=1, name='Terceiro', is_active=True)
        ApprovalStepParticipant.objects.create(
            step=step_a,
            role=ParticipantRole.APPROVER,
            subject_kind=SubjectKind.USER,
            user=self.internal_approver,
            is_variable=False,
        )

        self.client.login(username='creator_manual', password='x')
        resp = self.client.post(
            reverse('workflow_aprovacao:manual_request_new'),
            {
                'project': str(project2.pk),
                'category': str(self.category.pk),
                'title': 'Pedido fallback',
                'summary': 'Resumo',
                'notes': 'obs',
                'amount': '500.00',
                'vendor_name': 'Fornecedor',
                'category_payload_json': '{"vigencia_escopo":"6 meses"}',
                'implicit_external_full_name': 'Novo Externo',
                'implicit_external_company': 'Empresa X',
                'implicit_external_email': 'novo.fallback@example.com',
                'implicit_external_phone': '11999999999',
                'implicit_external_cnpj': '',
                'implicit_external_note': 'cadastro',
            },
            follow=False,
        )
        self.assertEqual(resp.status_code, 302)
        req = ExternalParticipantSignupRequest.objects.filter(
            process__project=project2,
            status=ExternalSignupStatus.PENDING,
            email='novo.fallback@example.com',
        ).first()
        self.assertIsNotNone(req)
        self.assertIsNotNone(req.central_signup_request_id)
        self.assertEqual(req.central_signup_request.status, UserSignupRequest.STATUS_PENDENTE)

    def test_manual_request_new_terceirizado_always_creates_signup_even_if_email_exists(self):
        """Cadastro via '+ novo terceirizado' deve ir para fila externa, sem vínculo silencioso."""
        self.client.login(username='creator_manual', password='x')
        resp = self.client.post(
            reverse('workflow_aprovacao:manual_request_new'),
            {
                'project': str(self.project.pk),
                'category': str(self.category.pk),
                'title': 'Pedido novo ext existente',
                'summary': 'Resumo',
                'notes': '',
                'amount': '',
                'vendor_name': '',
                'category_payload_json': '{"vigencia_escopo":"12 meses"}',
                f'slot_{self.slot.pk}_existing_user': '__new__',
                f'slot_{self.slot.pk}_full_name': 'Outro Nome',
                f'slot_{self.slot.pk}_company': 'Empresa Nova',
                f'slot_{self.slot.pk}_email': self.external_existing.email,
                f'slot_{self.slot.pk}_phone': '',
                f'slot_{self.slot.pk}_cnpj': '',
                f'slot_{self.slot.pk}_note': '',
            },
        )
        self.assertEqual(resp.status_code, 302)
        req = ExternalParticipantSignupRequest.objects.filter(
            email__iexact=self.external_existing.email,
            status=ExternalSignupStatus.PENDING,
            process__title='Pedido novo ext existente',
        ).first()
        self.assertIsNotNone(req)
        self.assertEqual(req.full_name, 'Outro Nome')

    def test_manual_request_saves_reference_documents(self):
        self.client.login(username='creator_manual', password='x')
        pdf = SimpleUploadedFile('contrato-ref.pdf', b'%PDF-1.4 test', content_type='application/pdf')
        resp = self.client.post(
            reverse('workflow_aprovacao:manual_request_new'),
            {
                'project': str(self.project.pk),
                'category': str(self.category.pk),
                'title': 'Pedido com anexo',
                'summary': 'Resumo',
                'notes': 'obs',
                'amount': '500.00',
                'vendor_name': 'Fornecedor',
                'category_payload_json': '{"vigencia_escopo":"6 meses"}',
                f'slot_{self.slot.pk}_existing_user': str(self.external_existing.pk),
                'documento_referencia_files': pdf,
            },
            format='multipart',
        )
        self.assertEqual(resp.status_code, 302)
        process = ApprovalProcess.objects.filter(title='Pedido com anexo').first()
        self.assertIsNotNone(process)
        self.assertEqual(process.attachments.count(), 1)
        att = process.attachments.first()
        self.assertEqual(att.original_name, 'contrato-ref.pdf')

        detail = self.client.get(reverse('workflow_aprovacao:process_detail', args=[process.pk]))
        self.assertEqual(detail.status_code, 200)
        self.assertContains(detail, 'contrato-ref.pdf')

        download = self.client.get(
            reverse(
                'workflow_aprovacao:manual_process_attachment',
                kwargs={'pk': process.pk, 'attachment_pk': att.pk},
            )
        )
        self.assertEqual(download.status_code, 200)
        body = b''.join(download.streaming_content)
        self.assertIn(b'%PDF', body)
