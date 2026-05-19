from django.test import SimpleTestCase

from workflow_aprovacao.services.gestao_display import gestao_snapshot_attachments_for_ui


class GestaoSnapshotAttachmentsUiTests(SimpleTestCase):
    def test_infere_extensao_e_meta(self):
        items = gestao_snapshot_attachments_for_ui(
            [
                {
                    'nome': 'contrato_assinado.pdf',
                    'url': 'https://example.com/a.pdf',
                    'extensao': '',
                    'tamanho': '1.25 MB',
                    'uploaded_at': '2026-05-18T16:20:00+00:00',
                    'enviado_por': 'victor',
                }
            ]
        )
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]['extensao'], 'PDF')
        self.assertEqual(items[0]['icon_class'], 'fa-file-pdf')
        self.assertIn('PDF', items[0]['meta'])
        self.assertIn('1.25 MB', items[0]['meta'])
