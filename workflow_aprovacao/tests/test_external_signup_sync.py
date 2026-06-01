"""Sincronização entre Central de Cadastros e solicitações externas do workflow."""
from datetime import date

from django.contrib.auth.models import Group, User
from django.test import Client, TestCase
from django.urls import reverse

from accounts.groups import GRUPOS
from accounts.models import UserSignupRequest
from accounts.signup_services import approve_signup_request
from core.models import Project, ProjectMember
from workflow_aprovacao.models import (
    ApprovalFlowDefinition,
    ApprovalStep,
    ApprovalStepParticipant,
    ExternalSignupStatus,
    ParticipantRole,
    ProcessCategory,
    SubjectKind,
)
from workflow_aprovacao.services.engine import ApprovalEngine
from workflow_aprovacao.services.external_signup import (
    ExternalCandidate,
    approve_external_signup_request,
    complete_workflow_external_from_central,
    create_external_signup_request,
)


class ExternalSignupSyncTests(TestCase):
    def setUp(self):
        self.project = Project.objects.create(
            name='Obra sync',
            code='SYNC-1',
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
        self.step = ApprovalStep.objects.create(flow=self.flow, sequence=1, name='Externo')
        ApprovalStepParticipant.objects.create(
            step=self.step,
            role=ParticipantRole.APPROVER,
            subject_kind=SubjectKind.USER,
            is_variable=True,
            variable_key='terceiro',
            required_on_create=True,
        )
        self.creator = User.objects.create_user('sync_creator', password='x')
        self.admin = User.objects.create_superuser('sync_admin', 'admin@example.com', 'x')
        Group.objects.get_or_create(name=GRUPOS.CENTRAL_APROVACOES_ADMIN)[0].user_set.add(self.creator)

    def _create_pending(self):
        process = ApprovalEngine.start(
            project=self.project,
            category=self.category,
            initiated_by=self.creator,
            title='Pedido sync',
            external_system='manual',
            external_entity_type='manual_request',
            allow_missing_required_variables=True,
        )
        wf = create_external_signup_request(
            process=process,
            step=self.step,
            requester=self.creator,
            variable_key='terceiro',
            candidate=ExternalCandidate(
                full_name='Terceiro Sync',
                company_name='Empresa Sync',
                email='terceiro.sync@example.com',
                phone_whatsapp='11999998888',
            ),
        )
        return process, wf

    def test_approve_in_workflow_syncs_central_and_applies_project(self):
        process, wf = self._create_pending()
        central = wf.central_signup_request
        self.assertIsNotNone(central)
        self.assertEqual(central.status, UserSignupRequest.STATUS_PENDENTE)

        linked = approve_external_signup_request(
            request_obj=wf,
            reviewer=self.admin,
            access_url_builder=lambda _u, p: reverse('workflow_aprovacao:process_detail', kwargs={'pk': p.pk}),
        )
        central.refresh_from_db()
        wf.refresh_from_db()

        self.assertEqual(wf.status, ExternalSignupStatus.APPROVED)
        self.assertEqual(central.status, UserSignupRequest.STATUS_APROVADO)
        self.assertEqual(central.approved_user_id, linked.pk)
        self.assertTrue(ProjectMember.objects.filter(user=linked, project=self.project).exists())
        self.assertTrue(linked.groups.filter(name=GRUPOS.CENTRAL_APROVACOES_EXTERNO).exists())

    def test_approve_in_central_syncs_workflow(self):
        process, wf = self._create_pending()
        central = wf.central_signup_request

        user = approve_signup_request(
            central,
            self.admin,
            selected_groups=[GRUPOS.CENTRAL_APROVACOES_EXTERNO],
            selected_project_ids=[self.project.pk],
        )
        complete_workflow_external_from_central(
            workflow_request=wf,
            user=user,
            reviewer=self.admin,
            access_url_builder=lambda _u, p: reverse('workflow_aprovacao:process_detail', kwargs={'pk': p.pk}),
        )
        wf.refresh_from_db()
        central.refresh_from_db()

        self.assertEqual(wf.status, ExternalSignupStatus.APPROVED)
        self.assertEqual(wf.linked_user_id, user.pk)
        self.assertTrue(wf.created_linked_user)
        self.assertEqual(central.status, UserSignupRequest.STATUS_APROVADO)

    def test_prefill_list_excludes_linked_central_records(self):
        self._create_pending()
        self.client.force_login(self.admin)
        resp = self.client.get(reverse('workflow_aprovacao:external_signup_requests'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'terceiro.sync@example.com')
        self.assertEqual(resp.content.decode().count('terceiro.sync@example.com'), 1)
