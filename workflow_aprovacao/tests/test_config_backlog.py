"""Fila administrativa de pendências sem fluxo (ApprovalConfigBacklog)."""
from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase

from core.models import Project
from workflow_aprovacao.models import (
    ApprovalConfigBacklog,
    ApprovalConfigBacklogStatus,
    ApprovalFlowDefinition,
    ApprovalProcess,
    ApprovalStep,
    ApprovalStepParticipant,
    ParticipantRole,
    ProcessCategory,
    SubjectKind,
)
from workflow_aprovacao.services.backlog import dismiss_backlog, reopen_backlog, try_start_from_backlog
from workflow_aprovacao.services.engine import ApprovalEngine


class ConfigBacklogTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username='backlog_admin', password='x')
        self.cat = ProcessCategory.objects.get(code='medicao')
        self.project = Project.objects.create(
            name='Obra backlog',
            code='TST-BACKLOG',
            start_date=date(2025, 1, 1),
            end_date=date(2026, 12, 31),
            contract_number='BR-1',
        )
        self.backlog = ApprovalConfigBacklog.objects.create(
            project=self.project,
            category=self.cat,
            external_system='sienge',
            external_id='m|CT|BR-1|1|9',
            external_entity_type='sienge_supply_contract_measurement',
            title='Sienge — teste',
            summary='linha1',
            source_payload={'documentId': 'CT', 'contractNumber': 'BR-1'},
            status=ApprovalConfigBacklogStatus.PENDING,
        )

    def test_try_start_creates_process_and_resolves(self):
        flow = ApprovalFlowDefinition.objects.create(
            project=self.project,
            category=self.cat,
            is_active=True,
        )
        s1 = ApprovalStep.objects.create(flow=flow, sequence=1, name='A1')
        ApprovalStepParticipant.objects.create(
            step=s1,
            role=ParticipantRole.APPROVER,
            subject_kind=SubjectKind.USER,
            user=self.user,
        )
        proc, err = try_start_from_backlog(self.backlog, initiated_by=self.user)
        self.assertFalse(err)
        self.assertIsNotNone(proc)
        self.backlog.refresh_from_db()
        self.assertEqual(self.backlog.status, ApprovalConfigBacklogStatus.RESOLVED)
        self.assertEqual(self.backlog.linked_process_id, proc.pk)

    def test_dismiss_and_reopen(self):
        dismiss_backlog(self.backlog, user=self.user, note='teste')
        self.backlog.refresh_from_db()
        self.assertEqual(self.backlog.status, ApprovalConfigBacklogStatus.DISMISSED)
        reopen_backlog(self.backlog)
        self.backlog.refresh_from_db()
        self.assertEqual(self.backlog.status, ApprovalConfigBacklogStatus.PENDING)

    def test_engine_start_marks_backlog_resolved(self):
        flow = ApprovalFlowDefinition.objects.create(
            project=self.project,
            category=self.cat,
            is_active=True,
        )
        s1 = ApprovalStep.objects.create(flow=flow, sequence=1, name='A1')
        ApprovalStepParticipant.objects.create(
            step=s1,
            role=ParticipantRole.APPROVER,
            subject_kind=SubjectKind.USER,
            user=self.user,
        )
        ApprovalEngine.start(
            project=self.project,
            category=self.cat,
            initiated_by=self.user,
            title='x',
            external_id=self.backlog.external_id,
            external_entity_type=self.backlog.external_entity_type,
        )
        self.backlog.refresh_from_db()
        self.assertEqual(self.backlog.status, ApprovalConfigBacklogStatus.RESOLVED)
        self.assertTrue(
            ApprovalProcess.objects.filter(external_id=self.backlog.external_id).exists()
        )
