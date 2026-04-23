"""Ingestão Sienge → Central (workflow), sem rede."""
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
    ProcessStatus,
    SubjectKind,
)
from workflow_aprovacao.services.sienge_measurement_sync import (
    contract_external_id,
    measurement_external_id,
    sync_sienge_central_inbound,
    sync_sienge_contracts_to_central,
    sync_sienge_measurements_to_central,
)


class _FakeSiengeClient:
    def __init__(self, measurements=None, contracts=None):
        self._measurements = measurements or []
        self._contracts = contracts or []

    def iter_supply_contract_measurements(self, *, page_size=25, max_rows=100):
        for row in self._measurements[:max_rows]:
            yield row

    def iter_supply_contracts_all(self, *, page_size=25, max_rows=100):
        for row in self._contracts[:max_rows]:
            yield row


class SiengeMeasurementSyncTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username='sync_init', password='x')
        self.cat_med = ProcessCategory.objects.get(code='medicao')
        self.project = Project.objects.create(
            name='Obra sync',
            code='TST-SIENGE-SYNC',
            start_date=date(2025, 1, 1),
            end_date=date(2026, 12, 31),
            contract_number='45',
        )
        flow = ApprovalFlowDefinition.objects.create(
            project=self.project,
            category=self.cat_med,
            is_active=True,
        )
        s1 = ApprovalStep.objects.create(flow=flow, sequence=1, name='A1')
        ApprovalStepParticipant.objects.create(
            step=s1,
            role=ParticipantRole.APPROVER,
            subject_kind=SubjectKind.USER,
            user=self.user,
        )

    def test_creates_process_when_pending_and_project_matches(self):
        row = {
            'documentId': 'CT',
            'contractNumber': '45',
            'buildingId': 143,
            'measurementNumber': 1,
            'authorized': False,
            'statusApproval': 'X',
            'responsibleName': 'Fulano',
            'notes': '',
        }
        client = _FakeSiengeClient(measurements=[row])
        stats = sync_sienge_measurements_to_central(
            client=client,
            initiated_by=self.user,
            category_code='medicao',
            max_rows=10,
        )
        self.assertEqual(stats['created'], 1)
        ext = measurement_external_id(row)
        proc = ApprovalProcess.objects.get(external_id=ext, external_system='sienge')
        self.assertEqual(proc.status, ProcessStatus.AWAITING_STEP)
        self.assertEqual(proc.project_id, self.project.id)
        self.assertEqual(proc.category_id, self.cat_med.id)

    def test_second_run_skips_duplicate(self):
        row = {
            'documentId': 'CT',
            'contractNumber': '45',
            'buildingId': 143,
            'measurementNumber': 2,
            'authorized': False,
        }
        client = _FakeSiengeClient(measurements=[row])
        sync_sienge_measurements_to_central(client=client, category_code='medicao', max_rows=10)
        stats = sync_sienge_measurements_to_central(client=client, category_code='medicao', max_rows=10)
        self.assertEqual(stats['skipped_duplicate'], 1)
        self.assertEqual(stats['created'], 0)

    def test_skips_when_authorized_in_sienge(self):
        row = {
            'documentId': 'CT',
            'contractNumber': '45',
            'buildingId': 143,
            'measurementNumber': 3,
            'authorized': True,
        }
        client = _FakeSiengeClient(measurements=[row])
        stats = sync_sienge_measurements_to_central(client=client, category_code='medicao', max_rows=10)
        self.assertEqual(stats['skipped_not_pending'], 1)
        self.assertEqual(stats['created'], 0)

    def test_pending_when_authorized_missing_treated_as_not_true(self):
        row = {
            'documentId': 'CT',
            'contractNumber': '45',
            'buildingId': 1,
            'measurementNumber': 9,
        }
        client = _FakeSiengeClient(measurements=[row])
        stats = sync_sienge_measurements_to_central(client=client, category_code='medicao', max_rows=10)
        self.assertEqual(stats['created'], 1)

    def test_skips_when_no_project_for_contract(self):
        row = {
            'documentId': 'CT',
            'contractNumber': '99999',
            'buildingId': 1,
            'measurementNumber': 1,
            'authorized': False,
        }
        client = _FakeSiengeClient(measurements=[row])
        stats = sync_sienge_measurements_to_central(client=client, category_code='medicao', max_rows=10)
        self.assertEqual(stats['skipped_no_project'], 1)

    def test_resolves_obra_by_project_code_not_only_contract_number(self):
        """contractNumber Sienge pode coincidir com Project.code (obras já existentes)."""
        self.project.contract_number = ''
        self.project.code = 'SIENGE-99'
        self.project.save(update_fields=['contract_number', 'code'])
        row = {
            'documentId': 'CT',
            'contractNumber': 'SIENGE-99',
            'buildingId': 1,
            'measurementNumber': 5,
            'authorized': False,
        }
        client = _FakeSiengeClient(measurements=[row])
        stats = sync_sienge_measurements_to_central(client=client, category_code='medicao', max_rows=10)
        self.assertEqual(stats['created'], 1)

    def test_no_flow_records_backlog(self):
        """Sem fluxo ativo: não cria processo mas regista fila administrativa."""
        User = get_user_model()
        user = User.objects.create_user(username='noflow_u', password='x')
        p = Project.objects.create(
            name='Obra sem fluxo',
            code='TST-NOFLOW',
            start_date=date(2025, 1, 1),
            end_date=date(2026, 12, 31),
            contract_number='88',
        )
        row = {
            'documentId': 'CT',
            'contractNumber': '88',
            'buildingId': 1,
            'measurementNumber': 7,
            'authorized': False,
        }
        client = _FakeSiengeClient(measurements=[row])
        stats = sync_sienge_measurements_to_central(
            client=client,
            initiated_by=user,
            category_code='medicao',
            max_rows=10,
        )
        self.assertEqual(stats['created'], 0)
        self.assertEqual(stats['errors_no_flow'], 1)
        ext = measurement_external_id(row)
        b = ApprovalConfigBacklog.objects.get(external_id=ext, external_system='sienge')
        self.assertEqual(b.status, ApprovalConfigBacklogStatus.PENDING)
        self.assertEqual(b.project_id, p.id)
        self.assertFalse(ApprovalProcess.objects.filter(external_id=ext).exists())


class SiengeContractSyncTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username='sync_ctr', password='x')
        self.cat = ProcessCategory.objects.get(code='contrato')
        self.project = Project.objects.create(
            name='Obra contrato',
            code='TST-SIENGE-CTR',
            start_date=date(2025, 1, 1),
            end_date=date(2026, 12, 31),
            contract_number='99',
        )
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

    def test_contract_pending_creates_process(self):
        row = {
            'documentId': 'CT',
            'contractNumber': '99',
            'isAuthorized': False,
            'status': 'A',
            'companyName': 'Empresa',
        }
        client = _FakeSiengeClient(contracts=[row])
        stats = sync_sienge_contracts_to_central(client=client, max_rows=10)
        self.assertEqual(stats['created'], 1)
        ext = contract_external_id(row)
        proc = ApprovalProcess.objects.get(external_id=ext, external_system='sienge')
        self.assertEqual(proc.category_id, self.cat.id)

    def test_inbound_runs_both_sources(self):
        cat_contrato = ProcessCategory.objects.get(code='contrato')
        User = get_user_model()
        user = User.objects.create_user(username='inbound_u', password='x')
        p = Project.objects.create(
            name='Obra full',
            code='TST-INBOUND',
            start_date=date(2025, 1, 1),
            end_date=date(2026, 12, 31),
            contract_number='77',
        )
        for cat in (cat_contrato, ProcessCategory.objects.get(code='medicao')):
            f = ApprovalFlowDefinition.objects.create(project=p, category=cat, is_active=True)
            s = ApprovalStep.objects.create(flow=f, sequence=1, name='S')
            ApprovalStepParticipant.objects.create(
                step=s,
                role=ParticipantRole.APPROVER,
                subject_kind=SubjectKind.USER,
                user=user,
            )

        client = _FakeSiengeClient(
            contracts=[{'documentId': 'X', 'contractNumber': '77', 'isAuthorized': False}],
            measurements=[
                {
                    'documentId': 'X',
                    'contractNumber': '77',
                    'buildingId': 1,
                    'measurementNumber': 2,
                    'authorized': False,
                }
            ],
        )
        out = sync_sienge_central_inbound(client=client, max_rows=10)
        self.assertEqual(out['contracts']['created'], 1)
        self.assertEqual(out['measurements']['created'], 1)
