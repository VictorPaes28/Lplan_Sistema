"""Normalização de anexos e apresentação de payload Sienge."""
from __future__ import annotations

from unittest.mock import MagicMock

from django.test import SimpleTestCase

from workflow_aprovacao.services.sienge_api import (
    SiengeCentralApiClient,
    _flatten_attachment_dicts,
    _http_response_looks_like_file,
    attachment_id_from_normalized_row,
    normalize_supply_contract_attachment_row,
)
from workflow_aprovacao.services.sienge_display import beautify_stored_summary_for_display, sienge_payload_display_rows


class SiengeAttachmentNormalizeTests(SimpleTestCase):
    def test_normalize_prefers_attachment_id(self):
        row = {'attachmentId': 12, 'fileName': 'contrato.pdf'}
        n = normalize_supply_contract_attachment_row(row)
        self.assertEqual(n['attachment_id'], 12)
        self.assertEqual(n['file_name'], 'contrato.pdf')

    def test_normalize_alternate_id_keys(self):
        for key in ('id', 'attachmentNumber', 'supplyContractAttachmentId', 'contractAttachmentNumber'):
            n = normalize_supply_contract_attachment_row({key: 99, 'name': 'x.pdf'})
            self.assertEqual(n['attachment_id'], 99, msg=key)

    def test_normalize_sienge_contract_attachment_shape(self):
        """Formato real observado na API (sem attachmentId / id)."""
        row = {
            'documentId': 'CT  ',
            'contractNumber': '210',
            'contractAttachmentNumber': 1,
            'name': 'contrato.pdf',
            'description': 'ALOJAMENTO 02',
        }
        n = normalize_supply_contract_attachment_row(row)
        self.assertEqual(n['attachment_id'], 1)
        self.assertEqual(n['file_name'], 'contrato.pdf')

    def test_attachment_id_from_row_uses_raw_fallback(self):
        n = {
            'attachment_id': None,
            'file_name': 'x',
            'raw': {'supplyContractAttachmentId': 7},
        }
        self.assertEqual(attachment_id_from_normalized_row(n), 7)


class SiengeFlattenTests(SimpleTestCase):
    def test_flatten_results(self):
        data = {'results': [{'id': 1}, {'id': 2}]}
        self.assertEqual(len(_flatten_attachment_dicts(data)), 2)

    def test_flatten_nested_data_attachments(self):
        data = {'data': {'attachments': [{'attachmentId': 3}]}}
        self.assertEqual(len(_flatten_attachment_dicts(data)), 1)


class SiengeDownloadHeuristicTests(SimpleTestCase):
    def test_rejects_json_content_type(self):
        r = MagicMock()
        r.status_code = 200
        r.headers = {'content-type': 'application/json'}
        r.content = b'{}'
        self.assertFalse(_http_response_looks_like_file(r))

    def test_accepts_pdf(self):
        r = MagicMock()
        r.status_code = 200
        r.headers = {'content-type': 'application/pdf'}
        r.content = b'%PDF-1.4'
        self.assertTrue(_http_response_looks_like_file(r))


class SiengeDisplayRowsTests(SimpleTestCase):
    def test_contract_order_and_labels(self):
        payload = {
            'contractNumber': '55',
            'documentId': 'DOC',
            'supplierName': 'ACME',
            'extraField': 'z',
        }
        rows = sienge_payload_display_rows(
            payload, external_entity_type='sienge_supply_contract', max_rows=20
        )
        labels = [r['label'] for r in rows]
        self.assertIn('Nº contrato', labels)
        self.assertIn('Fornecedor', labels)
        self.assertLess(labels.index('Documento'), labels.index('Nº contrato'))

    def test_status_approval_translated(self):
        rows = sienge_payload_display_rows(
            {'statusApproval': 'DISAPPROVED', 'isAuthorized': False},
            external_entity_type='sienge_supply_contract',
        )
        by_label = {r['label']: r['value'] for r in rows}
        self.assertEqual(by_label.get('Situação aprovação'), 'Não aprovado')
        self.assertEqual(by_label.get('Autorizado (contrato)'), 'Não')

    def test_beautify_legacy_resumo_tech_keys(self):
        raw = (
            "status: PENDING\n"
            "statusApproval: DISAPPROVED\n"
            "isAuthorized: False\n"
            "Empresa: MARGHOT BOUTIQUE HOTEL LAGE LTDA\n"
            "Fornecedor: João Carlos Almeida do Nascimento"
        )
        out = beautify_stored_summary_for_display(raw)
        self.assertNotIn('status:', out)
        self.assertNotIn('statusApproval', out)
        self.assertNotIn('isAuthorized', out)
        self.assertIn('Situação contrato: Pendente', out)
        self.assertIn('Situação aprovação: Não aprovado', out)
        self.assertIn('Autorizado (contrato): Não', out)
        self.assertIn('MARGHOT BOUTIQUE', out)
        self.assertIn('João Carlos', out)


class SiengeClientDownloadRetryTests(SimpleTestCase):
    def test_download_tries_alternate_params(self):
        client = SiengeCentralApiClient(base_url='https://example.com/public/api')

        def fake_get(path, params=None):
            r = MagicMock()
            if params.get('attachmentId') == 5:
                r.status_code = 404
                r.headers = {}
                r.content = b''
            elif params.get('id') == 5:
                r.status_code = 200
                r.headers = {'content-type': 'application/pdf'}
                r.content = b'%PDF-1.1 fake'
            else:
                r.status_code = 404
                r.headers = {}
                r.content = b''
            return r

        client.get_http_response = fake_get  # type: ignore[method-assign]
        raw, ctype, _fname = client.download_supply_contract_attachment(
            document_id='D1', contract_number='1', attachment_id=5, max_bytes=1024
        )
        self.assertTrue(raw.startswith(b'%PDF'))
        self.assertIn('pdf', ctype.lower())
