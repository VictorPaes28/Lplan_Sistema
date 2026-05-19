from datetime import date

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase

from core.models import Project
from workflow_aprovacao.models import (
    ApprovalFlowDefinition,
    ApprovalProcess,
    ApprovalStep,
    ApprovalStepParticipant,
    ParticipantRole,
    ProcessCategory,
    ProcessStatus,
    SubjectKind,
)
from workflow_aprovacao.services.step_display import build_current_step_display

User = get_user_model()


class CurrentStepDisplayTests(TestCase):
    def setUp(self):
        self.category = ProcessCategory.objects.get(code='contrato')
        self.project = Project.objects.create(
            code='P1-STEP',
            name='Obra Teste',
            start_date=date(2025, 1, 1),
            end_date=date(2026, 12, 31),
        )
        self.flow = ApprovalFlowDefinition.objects.create(
            project=self.project,
            category=self.category,
            is_active=True,
        )
        self.step1 = ApprovalStep.objects.create(
            flow=self.flow, sequence=1, name='1ª alçada', is_active=True
        )
        ApprovalStep.objects.create(
            flow=self.flow, sequence=2, name='2ª alçada', is_active=True
        )
        self.approver = User.objects.create_user(username='aprov1', password='x')
        self.viewer = User.objects.create_user(username='view1', password='x')
        ApprovalStepParticipant.objects.create(
            step=self.step1,
            role=ParticipantRole.OWNER,
            subject_kind=SubjectKind.USER,
            user=self.approver,
        )
        self.process = ApprovalProcess.objects.create(
            project=self.project,
            category=self.category,
            flow_definition=self.flow,
            current_step=self.step1,
            status=ProcessStatus.AWAITING_STEP,
            title='Teste',
        )

    def test_mostra_alcada_e_responsavel(self):
        info = build_current_step_display(self.process, viewer=self.viewer)
        self.assertTrue(info['is_active'])
        self.assertEqual(info['position_label'], 'Alçada 1 de 2')
        self.assertEqual(len(info['responsibles']), 1)
        self.assertEqual(info['responsibles'][0]['role_display'], 'Responsável')
        self.assertIn('aprov1', info['responsibles'][0]['label'].lower())
        self.assertFalse(info['viewer_is_responsible'])

    def test_viewer_designado(self):
        info = build_current_step_display(self.process, viewer=self.approver)
        self.assertTrue(info['viewer_is_responsible'])

    def test_grupo_django(self):
        grp = Group.objects.create(name='Aprovadores Obra')
        self.approver.groups.add(grp)
        ApprovalStepParticipant.objects.filter(step=self.step1).delete()
        ApprovalStepParticipant.objects.create(
            step=self.step1,
            role=ParticipantRole.APPROVER,
            subject_kind=SubjectKind.DJANGO_GROUP,
            django_group=grp,
        )
        info = build_current_step_display(self.process, viewer=self.approver)
        self.assertTrue(info['viewer_is_responsible'])
        self.assertIn('Aprovadores Obra', info['responsibles'][0]['label'])
