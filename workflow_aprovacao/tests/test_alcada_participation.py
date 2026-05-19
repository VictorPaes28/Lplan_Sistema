"""Garante que aprovação respeita apenas a alçada atual (current_step)."""
from datetime import date

from django.contrib.auth.models import Group, User
from django.test import Client, TestCase
from django.urls import reverse

from accounts.groups import GRUPOS
from core.models import Project
from workflow_aprovacao.access import user_is_approver_on_current_step
from workflow_aprovacao.models import (
    ApprovalFlowDefinition,
    ApprovalStep,
    ApprovalStepParticipant,
    ParticipantRole,
    ProcessCategory,
    ProcessStatus,
    SubjectKind,
)
from workflow_aprovacao.querysets import processes_pending_for_user
from workflow_aprovacao.services.engine import ApprovalEngine


def _project(code: str) -> Project:
    return Project.objects.create(
        code=code,
        name=f'Obra {code}',
        start_date=date(2025, 1, 1),
        end_date=date(2026, 12, 31),
    )


class AlcadaParticipationTests(TestCase):
    def setUp(self):
        self.cat = ProcessCategory.objects.get(code='contrato')
        self.project = _project('ALC-01')
        self.flow = ApprovalFlowDefinition.objects.create(
            project=self.project,
            category=self.cat,
            is_active=True,
        )
        self.step1 = ApprovalStep.objects.create(
            flow=self.flow, sequence=1, name='1ª alçada', is_active=True
        )
        self.step2 = ApprovalStep.objects.create(
            flow=self.flow, sequence=2, name='2ª alçada', is_active=True
        )
        self.user_a = User.objects.create_user('alcada_a', password='secret')
        self.user_b = User.objects.create_user('alcada_b', password='secret')
        g, _ = Group.objects.get_or_create(name=GRUPOS.CENTRAL_APROVACOES_APROVADOR)
        self.user_a.groups.add(g)
        self.user_b.groups.add(g)
        ApprovalStepParticipant.objects.create(
            step=self.step1,
            role=ParticipantRole.APPROVER,
            subject_kind=SubjectKind.USER,
            user=self.user_a,
        )
        ApprovalStepParticipant.objects.create(
            step=self.step2,
            role=ParticipantRole.APPROVER,
            subject_kind=SubjectKind.USER,
            user=self.user_b,
        )
        self.process = ApprovalEngine.start(
            project=self.project,
            category=self.cat,
            initiated_by=self.user_a,
            title='Teste alçadas',
        )

    def test_user_a_pending_only_on_step1(self):
        pending_ids = set(processes_pending_for_user(self.user_a).values_list('pk', flat=True))
        self.assertEqual(pending_ids, {self.process.pk})
        self.assertTrue(user_is_approver_on_current_step(self.user_a, self.process))
        self.assertFalse(user_is_approver_on_current_step(self.user_b, self.process))

    def test_after_step1_user_a_not_pending_user_b_is(self):
        ApprovalEngine.approve(self.process, user=self.user_a, comment='ok')
        self.process.refresh_from_db()
        self.assertEqual(self.process.current_step_id, self.step2.id)

        self.assertFalse(user_is_approver_on_current_step(self.user_a, self.process))
        self.assertTrue(user_is_approver_on_current_step(self.user_b, self.process))

        pending_a = set(processes_pending_for_user(self.user_a).values_list('pk', flat=True))
        pending_b = set(processes_pending_for_user(self.user_b).values_list('pk', flat=True))
        self.assertEqual(pending_a, set())
        self.assertEqual(pending_b, {self.process.pk})

    def test_user_a_cannot_post_approve_on_step2_via_url(self):
        ApprovalEngine.approve(self.process, user=self.user_a, comment='ok')
        self.process.refresh_from_db()
        client = Client()
        client.login(username='alcada_a', password='secret')
        url = reverse('workflow_aprovacao:process_detail', args=[self.process.pk])
        r = client.post(
            url,
            {
                'action': 'approve',
                'comment': '',
                'signer_name': 'alcada_a',
                'confirm_read': 'on',
                'signature_data': 'data:image/png;base64,' + ('x' * 600),
            },
        )
        self.assertEqual(r.status_code, 403)
        self.process.refresh_from_db()
        self.assertEqual(self.process.current_step_id, self.step2.id)
        self.assertEqual(self.process.status, ProcessStatus.AWAITING_STEP)

    def test_group_only_on_step1_does_not_carry_to_step2(self):
        """Grupo na 1ª alçada: membro não decide na 2ª se a 2ª não tiver esse grupo."""
        flow2 = ApprovalFlowDefinition.objects.create(
            project=_project('ALC-02'),
            category=self.cat,
            is_active=True,
        )
        s1 = ApprovalStep.objects.create(flow=flow2, sequence=1, name='G1', is_active=True)
        s2 = ApprovalStep.objects.create(flow=flow2, sequence=2, name='G2', is_active=True)
        g_only = Group.objects.create(name='Grupo Só Alçada 1')
        self.user_a.groups.add(g_only)
        ApprovalStepParticipant.objects.create(
            step=s1,
            role=ParticipantRole.APPROVER,
            subject_kind=SubjectKind.DJANGO_GROUP,
            django_group=g_only,
        )
        ApprovalStepParticipant.objects.create(
            step=s2,
            role=ParticipantRole.APPROVER,
            subject_kind=SubjectKind.USER,
            user=self.user_b,
        )
        proc = ApprovalEngine.start(project=flow2.project, category=self.cat, initiated_by=self.user_a)
        self.assertTrue(user_is_approver_on_current_step(self.user_a, proc))
        ApprovalEngine.approve(proc, user=self.user_a)
        proc.refresh_from_db()
        self.assertFalse(user_is_approver_on_current_step(self.user_a, proc))
        self.assertTrue(user_is_approver_on_current_step(self.user_b, proc))
