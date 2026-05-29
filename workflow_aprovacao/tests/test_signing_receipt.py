"""Comprovante PDF — rótulos e evento final."""
from datetime import date

from django.contrib.auth.models import User
from django.test import TestCase

from core.models import Project
from workflow_aprovacao.models import (
    ApprovalFlowDefinition,
    ApprovalHistoryEntry,
    ApprovalProcess,
    ApprovalStep,
    HistoryAction,
    ProcessCategory,
    ProcessStatus,
)
from workflow_aprovacao.services.signing import (
    _decision_heading,
    _format_geolocation_label,
    _history_event_summary,
    _scaled_logo_size,
    _step_label,
    build_final_signature_audit,
    history_geolocation_display,
    history_geolocation_label,
    latest_final_signature_event,
    logo_path_for_receipt_pdf,
    process_history_for_receipt,
    render_signature_receipt_pdf,
    REPORTLAB_AVAILABLE,
)


def _project(code: str) -> Project:
    return Project.objects.create(
        code=code,
        name=f'Obra {code}',
        start_date=date(2025, 1, 1),
        end_date=date(2026, 12, 31),
    )


class SigningReceiptTests(TestCase):
    def setUp(self):
        self.cat = ProcessCategory.objects.get(code='contrato')
        self.project = _project('PDF-01')
        self.flow = ApprovalFlowDefinition.objects.create(
            project=self.project, category=self.cat, is_active=True
        )
        self.step = ApprovalStep.objects.create(
            flow=self.flow, sequence=1, name='Diretoria', is_active=True
        )
        self.user = User.objects.create_user('signer_pdf', password='x')
        self.process = ApprovalProcess.objects.create(
            flow_definition=self.flow,
            project=self.project,
            category=self.cat,
            status=ProcessStatus.APPROVED,
            current_step=None,
        )

    def test_decision_heading_approved(self):
        ev = ApprovalHistoryEntry(
            process=self.process,
            action=HistoryAction.APPROVED_STEP,
            new_status=ProcessStatus.APPROVED,
        )
        self.assertEqual(_decision_heading(ev, self.process), 'Aprovação — fluxo concluído')

    def test_decision_heading_rejected(self):
        self.process.status = ProcessStatus.REJECTED
        ev = ApprovalHistoryEntry(
            process=self.process,
            action=HistoryAction.REJECTED,
            new_status=ProcessStatus.REJECTED,
        )
        self.assertEqual(_decision_heading(ev, self.process), 'Reprovação do fluxo')

    def test_step_label(self):
        ev = ApprovalHistoryEntry(
            process=self.process,
            step=self.step,
            step_sequence_snapshot=1,
            action=HistoryAction.APPROVED_STEP,
        )
        self.assertEqual(_step_label(ev, {}), 'Alçada 1: Diretoria')

    def test_latest_final_picks_terminal_event(self):
        ApprovalHistoryEntry.objects.create(
            process=self.process,
            step=self.step,
            step_sequence_snapshot=1,
            actor=self.user,
            action=HistoryAction.APPROVED_STEP,
            new_status=ProcessStatus.APPROVED,
            payload={'signature_evidence': {'signature_hash_sha256': 'abc'}},
        )
        found = latest_final_signature_event(self.process)
        self.assertIsNotNone(found)
        self.assertEqual(found.new_status, ProcessStatus.APPROVED)

    def test_process_history_includes_all_alcadas(self):
        step2 = ApprovalStep.objects.create(
            flow=self.flow, sequence=2, name='Segunda alçada', is_active=True
        )
        user_b = User.objects.create_user('signer_b', password='x')
        ApprovalHistoryEntry.objects.create(
            process=self.process,
            actor=self.user,
            action=HistoryAction.SUBMITTED,
            new_status=ProcessStatus.AWAITING_STEP,
        )
        e1 = ApprovalHistoryEntry.objects.create(
            process=self.process,
            step=self.step,
            step_sequence_snapshot=1,
            actor=self.user,
            action=HistoryAction.APPROVED_STEP,
            new_status=ProcessStatus.AWAITING_STEP,
            comment='Ok na 1ª',
        )
        e2 = ApprovalHistoryEntry.objects.create(
            process=self.process,
            step=step2,
            step_sequence_snapshot=2,
            actor=user_b,
            action=HistoryAction.APPROVED_STEP,
            new_status=ProcessStatus.APPROVED,
            comment='Ok na 2ª',
            payload={'signature_evidence': {'signature_hash_sha256': 'f' * 64}},
        )
        hist = process_history_for_receipt(self.process)
        self.assertEqual(len(hist), 3)
        self.assertEqual(_history_event_summary(e1), 'Aprovação — encaminhado à próxima alçada')
        self.assertEqual(_history_event_summary(e2), 'Aprovação — fluxo concluído')
        self.assertEqual(latest_final_signature_event(self.process).pk, e2.pk)

    def test_render_pdf_contains_sections(self):
        if not REPORTLAB_AVAILABLE:
            self.skipTest('ReportLab não instalado')
        step2 = ApprovalStep.objects.create(
            flow=self.flow, sequence=2, name='Alçada 2', is_active=True
        )
        ApprovalHistoryEntry.objects.create(
            process=self.process,
            actor=self.user,
            action=HistoryAction.SUBMITTED,
            new_status=ProcessStatus.AWAITING_STEP,
        )
        ApprovalHistoryEntry.objects.create(
            process=self.process,
            step=self.step,
            step_sequence_snapshot=1,
            actor=self.user,
            action=HistoryAction.APPROVED_STEP,
            new_status=ProcessStatus.AWAITING_STEP,
        )
        ev = ApprovalHistoryEntry.objects.create(
            process=self.process,
            step=step2,
            step_sequence_snapshot=2,
            actor=self.user,
            action=HistoryAction.APPROVED_STEP,
            new_status=ProcessStatus.APPROVED,
            payload={
                'signature_evidence': {
                    'signature_hash_sha256': 'd' * 64,
                    'signed_snapshot': {
                        'signer_name': 'Victor Teste',
                        'ip': '127.0.0.1',
                        'user_agent': 'Test',
                    },
                }
            },
        )
        pdf = render_signature_receipt_pdf(process=self.process, event=ev)
        self.assertTrue(pdf.startswith(b'%PDF'))
        self.assertGreater(len(pdf), 900)

    def test_logo_path_helper_matches_pdf_generator(self):
        path = logo_path_for_receipt_pdf()
        if path is None:
            self.skipTest('Arquivo de logo LPlan não encontrado em core/static/core/images')
        self.assertTrue(path.endswith(('.png', '.jpg', '.jpeg')))
        w, h = _scaled_logo_size(path)
        self.assertGreater(w, 0)
        self.assertGreater(h, 0)

    def test_pdf_with_logo_is_larger_than_without(self):
        if not REPORTLAB_AVAILABLE:
            self.skipTest('ReportLab não instalado')
        logo = logo_path_for_receipt_pdf()
        if not logo:
            self.skipTest('Logo LPlan ausente no ambiente de teste')
        ev = ApprovalHistoryEntry.objects.create(
            process=self.process,
            actor=self.user,
            action=HistoryAction.APPROVED_STEP,
            new_status=ProcessStatus.APPROVED,
            payload={'signature_evidence': {'signature_hash_sha256': 'a' * 64}},
        )
        with_logo = render_signature_receipt_pdf(process=self.process, event=ev)
        self.assertIn(b'/Image', with_logo)
        self.assertGreater(len(with_logo), 1200)

    def test_history_geolocation_label_from_snapshot(self):
        ev = ApprovalHistoryEntry(
            process=self.process,
            payload={
                'signature_evidence': {
                    'signed_snapshot': {
                        'geo_location': {
                            'latitude': -23.55052,
                            'longitude': -46.633308,
                            'accuracy_m': 12.3,
                            'address': 'Av. Paulista, Bela Vista, São Paulo, SP',
                            'maps_url': 'https://www.google.com/maps?q=-23.55052,-46.633308',
                        },
                        'geo_label': 'Av. Paulista, Bela Vista, São Paulo, SP (precisão ~12.3 m)',
                    }
                }
            },
        )
        self.assertIn('Av. Paulista', history_geolocation_label(ev))
        display = history_geolocation_display(ev)
        self.assertIn('google.com/maps', display['maps_url'])

    def test_format_geolocation_label_prefers_address(self):
        label = _format_geolocation_label(
            {
                'latitude': -8.084836,
                'longitude': -34.896197,
                'accuracy_m': 85,
                'address': 'Rua da Aurora, Recife, Pernambuco',
            }
        )
        self.assertIn('Rua da Aurora', label)
        self.assertNotIn('Lat ', label)

    def test_build_final_signature_audit_includes_geo(self):
        ev = ApprovalHistoryEntry.objects.create(
            process=self.process,
            actor=self.user,
            action=HistoryAction.APPROVED_STEP,
            new_status=ProcessStatus.APPROVED,
            payload={
                'signature_evidence': {
                    'signature_hash_sha256': 'b' * 64,
                    'signed_snapshot': {
                        'signer_name': 'Victor Teste',
                        'geo_location': {
                            'latitude': -23.55052,
                            'longitude': -46.633308,
                            'address': 'Av. Paulista, São Paulo, SP',
                            'maps_url': 'https://www.google.com/maps?q=-23.55052,-46.633308',
                        },
                        'geo_label': 'Av. Paulista, São Paulo, SP',
                    },
                }
            },
        )
        audit = build_final_signature_audit(ev)
        self.assertIsNotNone(audit)
        assert audit is not None
        self.assertIn('Av. Paulista', audit['geo_label'])
        self.assertIn('google.com/maps', audit['geo_maps_url'])
        self.assertEqual(audit['signed_by'], 'Victor Teste')
