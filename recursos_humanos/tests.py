from datetime import date

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.groups import GRUPOS
from django.contrib.auth.models import Group, User

from recursos_humanos.models import Colaborador, DocumentoColaborador, ObraLocal, TipoDocumento
from recursos_humanos.services.alerts import gerar_alertas


class AlertasRHTests(TestCase):
    def setUp(self):
        grupo, _ = Group.objects.get_or_create(name=GRUPOS.RECURSOS_HUMANOS)
        self.user = User.objects.create_user('rh_tester', password='test')
        self.user.groups.add(grupo)
        self.obra = ObraLocal.objects.create(nome='Obra Teste')
        self.tipo = TipoDocumento.objects.create(nome='ASO Teste', tem_validade=True, ordem=1)
        self.colab_ativo = Colaborador.objects.create(
            nome='Ativo Teste',
            cpf='111.111.111-11',
            cargo='Pedreiro',
            status=Colaborador.Status.ATIVO,
        )
        self.colab_desligado = Colaborador.objects.create(
            nome='Desligado Teste',
            cpf='222.222.222-22',
            cargo='Servente',
            status=Colaborador.Status.DESLIGADO,
        )

    def test_vencido_desligado_aparece_em_alertas(self):
        DocumentoColaborador.objects.create(
            colaborador=self.colab_desligado,
            tipo=self.tipo,
            status=DocumentoColaborador.Status.RECEBIDO,
            vencimento=date(2020, 1, 1),
        )
        tipos = {a.tipo for a in gerar_alertas() if a.colaborador_id == self.colab_desligado.pk}
        self.assertIn('Documento vencido', tipos)

    def test_proximo_prazo_inclui_vencido(self):
        DocumentoColaborador.objects.create(
            colaborador=self.colab_ativo,
            tipo=self.tipo,
            status=DocumentoColaborador.Status.RECEBIDO,
            vencimento=date(2020, 1, 1),
        )
        self.assertEqual(self.colab_ativo.proximo_prazo(), date(2020, 1, 1))
        self.assertLess(self.colab_ativo.dias_proximo_prazo(), 0)

    def test_admissao_etapa_3_gera_alerta_mesmo_com_docs_ok(self):
        colab = Colaborador.objects.create(
            nome='Ricardo Teste',
            cpf='333.333.333-33',
            cargo='Servente',
            status=Colaborador.Status.EM_ADMISSAO,
            etapa_admissao=3,
            data_admissao=timezone.localdate(),
        )
        alertas_adm = [a for a in gerar_alertas() if a.colaborador_id == colab.pk]
        self.assertEqual(len(alertas_adm), 1)
        self.assertIn('aprovação', alertas_adm[0].detalhe.lower())
        self.assertIn(f'id={colab.pk}', alertas_adm[0].url)


class ColaboradoresListTests(TestCase):
    def setUp(self):
        grupo, _ = Group.objects.get_or_create(name=GRUPOS.RECURSOS_HUMANOS)
        self.user = User.objects.create_user('rh_list', password='test')
        self.user.groups.add(grupo)
        self.obra_a = ObraLocal.objects.create(nome='Obra A')
        self.obra_b = ObraLocal.objects.create(nome='Obra B')
        c1 = Colaborador.objects.create(nome='Alpha', cpf='444.444.444-44', cargo='A', status='ativo')
        c2 = Colaborador.objects.create(nome='Beta', cpf='555.555.555-55', cargo='B', status='desligado')
        c1.obras.add(self.obra_a)
        c2.obras.add(self.obra_b)

    def test_filtro_status_e_obra_combinados(self):
        self.client.force_login(self.user)
        url = reverse('recursos_humanos:colaboradores')
        resp = self.client.get(url, {'status': 'ativo', 'obra': self.obra_a.pk})
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Alpha')
        self.assertNotContains(resp, 'Beta')


class AdmissaoServiceTests(TestCase):
    def setUp(self):
        self.tipo_rg = TipoDocumento.objects.create(nome='RG', ordem=1)
        self.tipo_aso = TipoDocumento.objects.create(nome='ASO – Atestado de Saúde Ocupacional', ordem=11)
        self.tipo_nr = TipoDocumento.objects.create(nome='NR-35 – Trabalho em Altura', ordem=12, aplica_a='por_cargo')
        self.colab = Colaborador.objects.create(
            nome='Fernanda Teste',
            cpf='666.666.666-66',
            cargo='Auxiliar',
            status=Colaborador.Status.EM_ADMISSAO,
            etapa_admissao=2,
            data_admissao=timezone.localdate(),
        )

    def test_montar_grupos_documentos(self):
        from recursos_humanos.services.admissao import montar_grupos_documentos, resumo_documentos

        DocumentoColaborador.objects.create(
            colaborador=self.colab, tipo=self.tipo_rg, status=DocumentoColaborador.Status.RECEBIDO
        )
        DocumentoColaborador.objects.create(
            colaborador=self.colab, tipo=self.tipo_aso, status=DocumentoColaborador.Status.FALTANDO
        )
        DocumentoColaborador.objects.create(
            colaborador=self.colab, tipo=self.tipo_nr, status=DocumentoColaborador.Status.FALTANDO
        )
        grupos = montar_grupos_documentos(self.colab)
        ids = {g.id for g in grupos}
        self.assertIn('pessoais', ids)
        self.assertIn('saude', ids)
        self.assertIn('treinamentos', ids)
        resumo = resumo_documentos(grupos)
        self.assertEqual(resumo['total'], 3)
        self.assertEqual(resumo['recebidos'], 1)


class AdmissaoViewTests(TestCase):
    def setUp(self):
        grupo, _ = Group.objects.get_or_create(name=GRUPOS.RECURSOS_HUMANOS)
        self.user = User.objects.create_user('rh_adm', password='test')
        self.user.groups.add(grupo)
        self.colab = Colaborador.objects.create(
            nome='Admissao View',
            cpf='777.777.777-77',
            cargo='Servente',
            status=Colaborador.Status.EM_ADMISSAO,
            etapa_admissao=2,
        )
        tipo = TipoDocumento.objects.create(nome='CPF', ordem=2)
        DocumentoColaborador.objects.create(
            colaborador=self.colab,
            tipo=tipo,
            status=DocumentoColaborador.Status.RECEBIDO,
        )

    def test_admissao_mostra_grupos_etapa_2(self):
        self.client.force_login(self.user)
        resp = self.client.get(reverse('recursos_humanos:admissao'), {'id': self.colab.pk})
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Documentos Pessoais')
        self.assertContains(resp, 'Coleta de documentos')


class AdmissaoWriteTests(TestCase):
    def setUp(self):
        grupo, _ = Group.objects.get_or_create(name=GRUPOS.RECURSOS_HUMANOS)
        self.user = User.objects.create_user('rh_write', password='test')
        self.user.groups.add(grupo)
        self.obra = ObraLocal.objects.create(nome='Obra Write')
        self.tipo_obr = TipoDocumento.objects.create(nome='Doc Obrig', ordem=1, obrigatorio=True)
        self.tipo_opt = TipoDocumento.objects.create(nome='Doc Opt', ordem=2, obrigatorio=False)

    def test_criar_requisicao_via_post(self):
        self.client.force_login(self.user)
        resp = self.client.post(reverse('recursos_humanos:admissao_nova'), {
            'nome': 'Novo Colab',
            'cpf': '888.888.888-88',
            'cargo': 'Eletricista',
            'obra': self.obra.pk,
            'tipo_contrato': 'CLT',
            'salario': 'R$ 3.500',
            'data_inicio': timezone.localdate().isoformat(),
            'gestor': 'Ger. Silva',
            'motivo': 'Nova contratação',
            'observacoes': 'Teste',
        })
        self.assertEqual(resp.status_code, 302)
        colab = Colaborador.objects.get(cpf='888.888.888-88')
        self.assertEqual(colab.etapa_admissao, 2)
        self.assertEqual(colab.documentos.count(), TipoDocumento.objects.count())

    def test_fluxo_aprovacao_admissao(self):
        colab = Colaborador.objects.create(
            nome='Fluxo Teste',
            cpf='999.999.999-99',
            cargo='Pedreiro',
            status=Colaborador.Status.EM_ADMISSAO,
            etapa_admissao=2,
        )
        colab.obras.add(self.obra)
        DocumentoColaborador.objects.create(
            colaborador=colab, tipo=self.tipo_obr, status=DocumentoColaborador.Status.RECEBIDO,
        )
        DocumentoColaborador.objects.create(
            colaborador=colab, tipo=self.tipo_opt, status=DocumentoColaborador.Status.FALTANDO,
        )
        self.client.force_login(self.user)
        url = reverse('recursos_humanos:admissao_acao', args=[colab.pk])

        resp = self.client.post(url, {'acao': 'avancar'})
        self.assertEqual(resp.status_code, 302)
        colab.refresh_from_db()
        self.assertEqual(colab.etapa_admissao, 3)

        resp = self.client.post(url, {'acao': 'aprovar'})
        colab.refresh_from_db()
        self.assertEqual(colab.etapa_admissao, 4)

        resp = self.client.post(url, {'acao': 'concluir'})
        colab.refresh_from_db()
        self.assertEqual(colab.status, Colaborador.Status.ATIVO)
        self.assertEqual(colab.etapa_admissao, 5)

    def test_documento_status_post(self):
        colab = Colaborador.objects.create(
            nome='Doc Status', cpf='101.101.101-10', cargo='A', status='ativo',
        )
        doc = DocumentoColaborador.objects.create(
            colaborador=colab, tipo=self.tipo_obr, status=DocumentoColaborador.Status.FALTANDO,
        )
        self.client.force_login(self.user)
        url = reverse('recursos_humanos:documento_status', args=[doc.pk])
        resp = self.client.post(url, {
            'status': DocumentoColaborador.Status.RECEBIDO,
            'observacao': 'OK',
            'next': reverse('recursos_humanos:colaborador_detalhe', args=[colab.pk]),
        })
        self.assertEqual(resp.status_code, 302)
        doc.refresh_from_db()
        self.assertEqual(doc.status, DocumentoColaborador.Status.RECEBIDO)

    def test_documentos_config_criar_tipo(self):
        self.client.force_login(self.user)
        resp = self.client.post(reverse('recursos_humanos:documentos_config'), {
            'acao': 'criar',
            'nome': 'Novo Tipo Teste',
            'aplica_a': 'todos',
            'tem_validade': 'on',
            'dias_validade': 365,
            'obrigatorio': 'on',
            'ordem': 99,
        })
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(TipoDocumento.objects.filter(nome='Novo Tipo Teste').exists())
