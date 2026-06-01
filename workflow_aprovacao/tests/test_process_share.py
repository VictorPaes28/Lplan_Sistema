from datetime import date

from django.contrib.auth.models import User
from django.test import RequestFactory, TestCase
from django.urls import reverse

from core.models import Project
from workflow_aprovacao.models import (
    ApprovalFlowDefinition,
    ApprovalProcess,
    ProcessCategory,
    ProcessStatus,
)
from workflow_aprovacao.services.share import build_process_share_payload


def _project(code: str) -> Project:
    return Project.objects.create(
        code=code,
        name=f'Obra {code}',
        start_date=date(2025, 1, 1),
        end_date=date(2026, 12, 31),
    )


class ProcessShareTests(TestCase):
    def setUp(self):
        self.cat = ProcessCategory.objects.get(code='contrato')
        self.project = _project('WPP-01')
        self.flow = ApprovalFlowDefinition.objects.create(
            project=self.project,
            category=self.cat,
            is_active=True,
        )
        self.user = User.objects.create_user('share_user', password='x')
        self.process = ApprovalProcess.objects.create(
            flow_definition=self.flow,
            project=self.project,
            category=self.cat,
            status=ProcessStatus.AWAITING_STEP,
            title='Contrato teste',
        )
        self.factory = RequestFactory()

    def test_build_process_share_payload(self):
        path = reverse('workflow_aprovacao:process_detail', kwargs={'pk': self.process.pk})
        request = self.factory.get(path)
        request.user = self.user
        payload = build_process_share_payload(request=request, process=self.process)
        self.assertIn(path, payload['url'])
        self.assertIn('Contrato teste', payload['message'])
        self.assertIn('Central de Aprovações', payload['message'])
        self.assertIn('vínculo com este processo', payload['message'])
        self.assertTrue(payload['whatsapp_url'].startswith('https://wa.me/?text='))
