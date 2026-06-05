from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase
from django.urls import reverse

from gestao_aprovacao.models import Approval, Attachment, Empresa, Obra, WorkOrder
from gestao_aprovacao.services.attachment_versions import (
    assign_new_attachment_version,
    attachment_pode_excluir,
    build_attachment_display_groups,
    mark_submission_attachments_recusados,
    ordered_attachments_for_consolidation,
)


class AttachmentReprovacaoFlowTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('solic', password='x', email='s@t.com')
        self.aprovador = User.objects.create_user('apr', password='x', email='a@t.com')
        self.empresa = Empresa.objects.create(codigo='E1', nome='Empresa 1')
        self.obra = Obra.objects.create(codigo='O1', nome='Obra 1', empresa=self.empresa)
        self.workorder = WorkOrder.objects.create(
            obra=self.obra,
            codigo='P-001',
            nome_credor='Fornecedor',
            tipo_solicitacao='contrato',
            status='pendente',
            criado_por=self.user,
        )

    def _attach(self, name='doc.pdf', *, versao=0, recusado=False):
        content = SimpleUploadedFile(name, b'%PDF-1.4 test', content_type='application/pdf')
        return Attachment.objects.create(
            work_order=self.workorder,
            arquivo=content,
            nome=name,
            enviado_por=self.user,
            versao_reaprovacao=versao,
            recusado=recusado,
        )

    def test_reprovacao_marca_anexos_como_recusados(self):
        original = self._attach('original.pdf')
        self.workorder.status = 'reprovado'
        self.workorder.save(update_fields=['status'])
        mark_submission_attachments_recusados(self.workorder)

        original.refresh_from_db()
        self.assertTrue(original.recusado)
        self.assertEqual(ordered_attachments_for_consolidation(self.workorder), [])

    def test_novos_anexos_corrigidos_ficam_separados_e_entram_no_pdf(self):
        self._attach('recusado.pdf', recusado=True)
        corrigido = self._attach('corrigido.pdf', versao=1)

        grupos = build_attachment_display_groups(self.workorder)
        self.assertEqual(grupos['modo'], 'reprovacao')
        keys = [g['key'] for g in grupos['grupos']]
        self.assertIn('historico', keys)
        self.assertIn('corrigidos', keys)

        pdf_anexos = ordered_attachments_for_consolidation(self.workorder)
        self.assertEqual(len(pdf_anexos), 1)
        self.assertEqual(pdf_anexos[0].pk, corrigido.pk)

    def test_assign_new_attachment_version_apos_reprovacao(self):
        self._attach('v0.pdf', recusado=True)
        self.workorder.status = 'reprovado'
        self.workorder.save(update_fields=['status'])

        self.assertEqual(assign_new_attachment_version(self.workorder), 1)

        self._attach('v1a.pdf', versao=1)
        self.assertEqual(assign_new_attachment_version(self.workorder), 1)

    def test_anexo_recusado_nao_pode_ser_excluido(self):
        recusado = self._attach('hist.pdf', recusado=True)
        self.assertFalse(attachment_pode_excluir(recusado))

    def test_edit_reenvio_aceita_varios_anexos_no_mesmo_post(self):
        self._attach('recusado.pdf', recusado=True)
        self.workorder.status = 'reprovado'
        self.workorder.save(update_fields=['status'])

        client = Client()
        client.force_login(self.user)
        f1 = SimpleUploadedFile('corr1.pdf', b'%PDF-1.4 a', content_type='application/pdf')
        f2 = SimpleUploadedFile('corr2.pdf', b'%PDF-1.4 b', content_type='application/pdf')
        response = client.post(
            reverse('gestao:edit_workorder', args=[self.workorder.pk]),
            {
                'obra': self.obra.pk,
                'codigo': self.workorder.codigo,
                'nome_credor': self.workorder.nome_credor,
                'tipo_solicitacao': self.workorder.tipo_solicitacao,
                'status': 'reprovado',
                'anexos': [f1, f2],
            },
        )
        self.assertEqual(response.status_code, 302)
        self.workorder.refresh_from_db()
        self.assertEqual(self.workorder.status, 'reaprovacao')
        self.assertEqual(
            Attachment.objects.filter(work_order=self.workorder, recusado=False).count(),
            2,
        )

    def test_mark_on_reject_via_approval_flow(self):
        self._attach('submissao.pdf')
        Approval.objects.create(
            work_order=self.workorder,
            aprovado_por=self.aprovador,
            decisao='reprovado',
            comentario='Faltou item',
        )
        self.workorder.status = 'reprovado'
        self.workorder.save(update_fields=['status'])
        mark_submission_attachments_recusados(self.workorder)

        self.assertEqual(
            Attachment.objects.filter(work_order=self.workorder, recusado=True).count(),
            1,
        )
        self.assertEqual(assign_new_attachment_version(self.workorder), 1)

    def test_upload_redireciona_para_edicao_quando_criador(self):
        self.workorder.status = 'reprovado'
        self.workorder.save(update_fields=['status'])

        client = Client()
        client.force_login(self.user)
        response = client.get(reverse('gestao:upload_attachment', args=[self.workorder.pk]))
        self.assertEqual(response.status_code, 302)
        self.assertIn('editar', response.url)
        self.assertIn('#anexos-pedido', response.url)
