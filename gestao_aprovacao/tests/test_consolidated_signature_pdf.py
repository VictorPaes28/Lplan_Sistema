import io

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from reportlab.pdfgen import canvas

from gestao_aprovacao.models import Attachment, Empresa, Obra, WorkOrder
from gestao_aprovacao.services.consolidated_signature_pdf import (
    NoAttachmentsError,
    UnsupportedAttachmentsError,
    build_consolidated_signature_pdf,
    consolidation_precheck,
    ordered_attachments_for_consolidation,
)

_VALID_SIG = 'data:image/png;base64,' + ('x' * 600)


def _minimal_pdf_bytes(text: str = 'p') -> bytes:
    buf = io.BytesIO()
    c = canvas.Canvas(buf)
    c.drawString(72, 720, text)
    c.showPage()
    c.save()
    return buf.getvalue()


class ConsolidatedSignaturePdfTests(TestCase):
    def setUp(self):
        self.empresa = Empresa.objects.create(nome='E1', codigo='E1')
        self.obra = Obra.objects.create(
            empresa=self.empresa,
            codigo='O1',
            nome='Obra teste',
        )
        self.user = User.objects.create_user('aprov', password='x')
        self.workorder = WorkOrder.objects.create(
            obra=self.obra,
            codigo='PED-001',
            nome_credor='Credor',
            tipo_solicitacao='contrato',
            status='pendente',
            criado_por=self.user,
        )

    def test_precheck_sem_anexos(self):
        pre = consolidation_precheck(self.workorder)
        self.assertFalse(pre['ok'])
        self.assertEqual(pre['reason'], 'no_attachments')

    def test_precheck_bloqueia_docx(self):
        Attachment.objects.create(
            work_order=self.workorder,
            arquivo=SimpleUploadedFile('a.docx', b'd', content_type='application/msword'),
            nome='a.docx',
            enviado_por=self.user,
        )
        pre = consolidation_precheck(self.workorder)
        self.assertFalse(pre['ok'])
        self.assertEqual(pre['reason'], 'unsupported')

    def test_merge_dois_pdfs_com_assinatura(self):
        for idx, label in enumerate(('A', 'B'), start=1):
            Attachment.objects.create(
                work_order=self.workorder,
                arquivo=SimpleUploadedFile(
                    f'parte{idx}.pdf',
                    _minimal_pdf_bytes(label),
                    content_type='application/pdf',
                ),
                nome=f'parte{idx}.pdf',
                enviado_por=self.user,
            )

        ordered = ordered_attachments_for_consolidation(self.workorder)
        self.assertEqual(len(ordered), 2)
        self.assertEqual(ordered[0].nome, 'parte1.pdf')

        pdf = build_consolidated_signature_pdf(
            work_order=self.workorder,
            signature_data=_VALID_SIG,
            signer_name='Aprovador Teste',
        )
        self.assertTrue(pdf.startswith(b'%PDF'))
        self.assertGreater(len(pdf), 800)

    def test_sem_anexos_levanta_erro(self):
        with self.assertRaises(NoAttachmentsError):
            build_consolidated_signature_pdf(
                work_order=self.workorder,
                signature_data=_VALID_SIG,
                signer_name='X',
            )

    def test_docx_levanta_erro_claro(self):
        Attachment.objects.create(
            work_order=self.workorder,
            arquivo=SimpleUploadedFile('planilha.xlsx', b'd', content_type='application/vnd.ms-excel'),
            nome='planilha.xlsx',
            enviado_por=self.user,
        )
        with self.assertRaises(UnsupportedAttachmentsError) as ctx:
            build_consolidated_signature_pdf(
                work_order=self.workorder,
                signature_data=_VALID_SIG,
                signer_name='X',
            )
        self.assertIn('planilha.xlsx', ctx.exception.filenames)
