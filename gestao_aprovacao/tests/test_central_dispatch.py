from datetime import date

from django.contrib.auth.models import Group, User
from django.test import TestCase

from accounts.groups import GRUPOS
from core.models import Project
from gestao_aprovacao.models import GestaoCentralDispatch, Obra, StatusHistory, WorkOrder
from gestao_aprovacao.services.central_dispatch import (
    GestaoCentralDispatchDuplicateError,
    GestaoCentralNoFlowError,
    build_manual_request_initial,
    dispatch_workorder_to_central,
    workorder_dispatch_block_reason,
)
from gestao_aprovacao.gestao_central_access import user_can_send_workorder_to_central
from workflow_aprovacao.models import (
    ApprovalFlowDefinition,
    ApprovalStep,
    ApprovalStepParticipant,
    ParticipantRole,
    ProcessCategory,
    SubjectKind,
)


class GestaoCentralDispatchTests(TestCase):
    def setUp(self):
        self.cat = ProcessCategory.objects.get(code='contrato')
        self.project = Project.objects.create(
            code='T-001',
            name='Obra teste',
            is_active=True,
            start_date=date(2025, 1, 1),
            end_date=date(2026, 12, 31),
        )
        self.obra = Obra.objects.create(codigo='T-001', nome='Obra teste', project=self.project)
        self.sender = User.objects.create_user('envia_central', password='x')
        g, _ = Group.objects.get_or_create(name=GRUPOS.ENVIAR_PARA_CENTRAL_APROVACOES)
        self.sender.groups.add(g)
        self.aprovador = User.objects.create_user('aprov_central', password='x')
        flow = ApprovalFlowDefinition.objects.create(
            project=self.project,
            category=self.cat,
            is_active=True,
        )
        step = ApprovalStep.objects.create(
            flow=flow,
            sequence=1,
            name='Alçada 1',
            is_active=True,
        )
        ApprovalStepParticipant.objects.create(
            step=step,
            role=ParticipantRole.APPROVER,
            subject_kind=SubjectKind.USER,
            user=self.aprovador,
        )
        self.workorder = WorkOrder.objects.create(
            obra=self.obra,
            codigo='PED-001',
            nome_credor='Fornecedor X',
            tipo_solicitacao='contrato',
            status='aprovado',
            criado_por=self.sender,
        )

    def test_permission_group(self):
        self.assertTrue(user_can_send_workorder_to_central(self.sender))
        other = User.objects.create_user('outro', password='x')
        self.assertFalse(user_can_send_workorder_to_central(other))

    def test_dispatch_creates_process_and_link(self):
        dispatch = dispatch_workorder_to_central(self.workorder, user=self.sender, send_comment='Teste')
        self.assertIsInstance(dispatch, GestaoCentralDispatch)
        self.assertEqual(dispatch.work_order_id, self.workorder.pk)
        self.assertEqual(dispatch.approval_process.category_id, self.cat.pk)
        self.assertEqual(dispatch.approval_process.external_entity_type, 'gestao_workorder')
        self.assertTrue(
            StatusHistory.objects.filter(
                work_order=self.workorder,
                observacao__icontains='Central de Aprovações',
            ).exists()
        )
        self.assertTrue(workorder_dispatch_block_reason(self.workorder))

    def test_duplicate_dispatch_blocked(self):
        dispatch_workorder_to_central(self.workorder, user=self.sender)
        with self.assertRaises(GestaoCentralDispatchDuplicateError):
            dispatch_workorder_to_central(self.workorder, user=self.sender)

    def test_no_flow_raises_friendly_error(self):
        wo = WorkOrder.objects.create(
            obra=self.obra,
            codigo='PED-002',
            nome_credor='Y',
            tipo_solicitacao='mapa_cotacao',
            status='aprovado',
            criado_por=self.sender,
        )
        with self.assertRaises(GestaoCentralNoFlowError):
            dispatch_workorder_to_central(wo, user=self.sender)

    def test_manual_request_initial_maps_contrato_fields(self):
        wo = WorkOrder.objects.create(
            obra=self.obra,
            codigo='PED-CNT',
            nome_credor='Fornecedor ABC',
            tipo_solicitacao='contrato',
            status='aprovado',
            observacoes='Escopo de 12 meses para manutenção',
            valor_estimado='15000.00',
            criado_por=self.sender,
        )
        prefill = build_manual_request_initial(wo)
        self.assertEqual(prefill['category'].code, 'contrato')
        self.assertEqual(prefill['project'].pk, self.project.pk)
        self.assertIn('PED-CNT', prefill['initial']['title'])
        self.assertEqual(prefill['initial']['vendor_name'], 'Fornecedor ABC')
        self.assertEqual(prefill['initial']['amount'], wo.valor_estimado)
        self.assertEqual(
            prefill['category_payload'].get('vigencia_escopo'),
            'Escopo de 12 meses para manutenção',
        )

    def test_manual_request_initial_maps_medicao_fields(self):
        wo = WorkOrder.objects.create(
            obra=self.obra,
            codigo='PED-MED',
            nome_credor='Medição Ltda',
            tipo_solicitacao='medicao',
            status='aprovado',
            valor_medicao='9876.54',
            observacoes='Jan/2026',
            criado_por=self.sender,
        )
        prefill = build_manual_request_initial(wo)
        self.assertEqual(prefill['category'].code, 'medicao')
        self.assertEqual(prefill['initial']['amount'], wo.valor_medicao)
        self.assertEqual(prefill['category_payload'].get('periodo_medicao'), 'Jan/2026')
        self.assertEqual(prefill['category_payload'].get('numero_medicao'), 'PED-MED')

    def test_manual_request_initial_maps_ordem_servico_prazo(self):
        wo = WorkOrder.objects.create(
            obra=self.obra,
            codigo='PED-OS',
            nome_credor='OS Credor',
            tipo_solicitacao='ordem_servico',
            status='aprovado',
            prazo_estimado=45,
            criado_por=self.sender,
        )
        prefill = build_manual_request_initial(wo)
        self.assertEqual(prefill['category'].code, 'ordem_servico')
        self.assertEqual(prefill['category_payload'].get('prazo_estimado'), '45 dias')
