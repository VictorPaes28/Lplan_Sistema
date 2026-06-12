from datetime import date

from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from accounts.groups import GRUPOS
from django.contrib.auth.models import Group, User

from gestao_aprovacao.models import Obra

from recursos_humanos.models import Colaborador, DocumentoColaborador, ObraLocal, TipoDocumento
from recursos_humanos.services.alerts import gerar_alertas


def _criar_obra_local(nome, codigo):
    gestao = Obra.objects.create(codigo=codigo, nome=nome, ativo=True)
    return ObraLocal.objects.create(nome=nome, gestao_obra=gestao)


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
        self.obra = _criar_obra_local('Obra Write', 'OW1')
        self.tipo_obr = TipoDocumento.objects.create(nome='Doc Obrig', ordem=1, obrigatorio=True)
        self.tipo_opt = TipoDocumento.objects.create(nome='Doc Opt', ordem=2, obrigatorio=False)

    def test_criar_requisicao_notifica_gestor_sino(self):
        from core.models import Notification

        self.client.force_login(self.user)
        self.client.post(reverse('recursos_humanos:admissao_nova'), {
            'nome': 'Notif Gestor',
            'cpf': '111.222.333-44',
            'email': 'notif@example.com',
            'telefone': '81911112222',
            'cargo': 'Eletricista',
            'obra': self.obra.pk,
            'tipo_contrato': 'CLT',
            'salario': 'R$ 3.500',
            'data_inicio': timezone.localdate().isoformat(),
            'gestor_id': self.user.pk,
            'motivo': 'Nova contratação',
            'observacoes': '',
        })
        self.assertTrue(
            Notification.objects.filter(
                user=self.user,
                notification_type='rh_requisicao_pendente',
            ).exists()
        )

    def test_criar_requisicao_via_post(self):
        self.client.force_login(self.user)
        resp = self.client.post(reverse('recursos_humanos:admissao_nova'), {
            'nome': 'Novo Colab',
            'cpf': '888.888.888-88',
            'email': 'novo@example.com',
            'telefone': '81999998888',
            'cargo': 'Eletricista',
            'obra': self.obra.pk,
            'tipo_contrato': 'CLT',
            'salario': 'R$ 3.500',
            'data_inicio': timezone.localdate().isoformat(),
            'gestor_id': self.user.pk,
            'motivo': 'Nova contratação',
            'observacoes': 'Teste',
        })
        self.assertEqual(resp.status_code, 302)
        colab = Colaborador.objects.get(cpf='888.888.888-88')
        self.assertEqual(colab.etapa_admissao, 1)
        self.assertFalse(colab.requisicao_aprovada_gestor)
        self.assertEqual(colab.gestor_aprovador_user_id, self.user.pk)
        self.assertEqual(colab.obras.count(), 1)
        self.assertIn(self.obra, colab.obras.all())
        self.assertEqual(colab.email, 'novo@example.com')
        self.assertEqual(colab.telefone, '81999998888')
        self.assertEqual(colab.documentos.count(), 0)

    @override_settings(
        EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
        DEFAULT_FROM_EMAIL='rh@lplan.test',
    )
    def test_superuser_pode_corrigir_requisicao_reprovada(self):
        superuser = User.objects.create_superuser('admin_super', 'admin@lplan.test', 'test')
        self.client.force_login(superuser)
        self.client.post(reverse('recursos_humanos:admissao_nova'), {
            'nome': 'Super Corrigir',
            'cpf': '333.333.333-33',
            'email': 'super@example.com',
            'telefone': '81933332222',
            'cargo': 'Eletricista',
            'obra': self.obra.pk,
            'tipo_contrato': 'CLT',
            'salario': 'R$ 3.500',
            'data_inicio': timezone.localdate().isoformat(),
            'gestor_id': self.user.pk,
            'motivo': 'Nova contratação',
            'observacoes': '',
        })
        colab = Colaborador.objects.get(cpf='333.333.333-33')
        colab.requisicao_reprovada = True
        colab.requisicao_motivo_reprovacao = 'Teste'
        colab.save(update_fields=['requisicao_reprovada', 'requisicao_motivo_reprovacao', 'atualizado_em'])
        resp = self.client.get(reverse('recursos_humanos:admissao'), {'id': colab.pk})
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Corrigir e reenviar requisição')

    def test_reprovar_requisicao_gestor(self):
        self.user.email = 'rh.criador@example.com'
        self.user.save(update_fields=['email'])
        self.client.force_login(self.user)
        self.client.post(reverse('recursos_humanos:admissao_nova'), {
            'nome': 'Reprovado Teste',
            'cpf': '555.555.555-55',
            'email': 'reprovado@example.com',
            'telefone': '81966665555',
            'cargo': 'Eletricista',
            'obra': self.obra.pk,
            'tipo_contrato': 'CLT',
            'salario': 'R$ 3.500',
            'data_inicio': timezone.localdate().isoformat(),
            'gestor_id': self.user.pk,
            'motivo': 'Nova contratação',
            'observacoes': '',
        })
        colab = Colaborador.objects.get(cpf='555.555.555-55')
        self.assertEqual(colab.requisicao_criada_por_id, self.user.pk)
        url = reverse('recursos_humanos:admissao_acao', args=[colab.pk])
        resp = self.client.post(url, {'acao': 'reprovar_requisicao', 'motivo': 'Salário acima do teto'})
        self.assertEqual(resp.status_code, 302)
        colab.refresh_from_db()
        self.assertTrue(colab.requisicao_reprovada)
        self.assertEqual(colab.requisicao_motivo_reprovacao, 'Salário acima do teto')
        self.assertFalse(colab.requisicao_aprovada_gestor)

    @override_settings(
        EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
        DEFAULT_FROM_EMAIL='rh@lplan.test',
    )
    def test_corrigir_requisicao_reenvia_ao_gestor(self):
        self.user.email = 'rh.criador2@example.com'
        self.user.save(update_fields=['email'])
        self.client.force_login(self.user)
        self.client.post(reverse('recursos_humanos:admissao_nova'), {
            'nome': 'Corrigir Teste',
            'cpf': '444.444.444-44',
            'email': 'corrigir@example.com',
            'telefone': '81955554444',
            'cargo': 'Eletricista',
            'obra': self.obra.pk,
            'tipo_contrato': 'CLT',
            'salario': 'R$ 3.500',
            'data_inicio': timezone.localdate().isoformat(),
            'gestor_id': self.user.pk,
            'motivo': 'Nova contratação',
            'observacoes': '',
        })
        colab = Colaborador.objects.get(cpf='444.444.444-44')
        self.client.post(reverse('recursos_humanos:admissao_acao', args=[colab.pk]), {
            'acao': 'reprovar_requisicao',
            'motivo': 'Ajustar salário',
        })
        colab.refresh_from_db()
        resp = self.client.post(reverse('recursos_humanos:admissao_atualizar_requisicao', args=[colab.pk]), {
            'nome': 'Corrigir Teste',
            'cpf': '444.444.444-44',
            'email': 'corrigir@example.com',
            'telefone': '81955554444',
            'cargo': 'Eletricista',
            'obra': self.obra.pk,
            'tipo_contrato': 'CLT',
            'salario': 'R$ 4.000',
            'data_inicio': timezone.localdate().isoformat(),
            'gestor_id': self.user.pk,
            'motivo': 'Nova contratação',
            'observacoes': 'Salário ajustado',
        })
        self.assertEqual(resp.status_code, 302)
        colab.refresh_from_db()
        self.assertFalse(colab.requisicao_reprovada)
        self.assertEqual(colab.salario, '4.000,00')
        self.assertEqual(colab.requisicao_motivo_reprovacao, '')

    @override_settings(
        EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
        DEFAULT_FROM_EMAIL='rh@lplan.test',
    )
    def test_aprovar_requisicao_gestor_inicia_coleta(self):
        from django.core import mail

        self.client.force_login(self.user)
        self.client.post(reverse('recursos_humanos:admissao_nova'), {
            'nome': 'Gestor Aprova',
            'cpf': '666.666.666-66',
            'email': 'gestor.aprova@example.com',
            'telefone': '81988887777',
            'cargo': 'Eletricista',
            'obra': self.obra.pk,
            'tipo_contrato': 'CLT',
            'salario': 'R$ 3.500',
            'data_inicio': timezone.localdate().isoformat(),
            'gestor_id': self.user.pk,
            'motivo': 'Nova contratação',
            'observacoes': '',
        })
        colab = Colaborador.objects.get(cpf='666.666.666-66')
        url = reverse('recursos_humanos:admissao_acao', args=[colab.pk])
        resp = self.client.post(url, {'acao': 'aprovar_requisicao'})
        self.assertEqual(resp.status_code, 302)
        colab.refresh_from_db()
        self.assertTrue(colab.requisicao_aprovada_gestor)
        self.assertEqual(colab.etapa_admissao, 2)
        self.assertEqual(colab.documentos.count(), TipoDocumento.objects.count())
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ['gestor.aprova@example.com'])
        self.assertIn(colab.token_portal, mail.outbox[0].body)

    def test_criar_requisicao_multiplas_obras(self):
        obra2 = _criar_obra_local('Obra Write 2', 'OW2')
        self.client.force_login(self.user)
        resp = self.client.post(reverse('recursos_humanos:admissao_nova'), {
            'nome': 'Novo Multi Obra',
            'cpf': '777.777.777-77',
            'email': 'multi@example.com',
            'telefone': '81977776666',
            'cargo': 'Eletricista',
            'obra': [self.obra.pk, obra2.pk],
            'tipo_contrato': 'CLT',
            'salario': 'R$ 3.500',
            'data_inicio': timezone.localdate().isoformat(),
            'gestor_id': self.user.pk,
            'motivo': 'Nova contratação',
            'observacoes': '',
        })
        self.assertEqual(resp.status_code, 302)
        colab = Colaborador.objects.get(cpf='777.777.777-77')
        self.assertEqual(colab.obras.count(), 2)

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
        })
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(TipoDocumento.objects.filter(nome='Novo Tipo Teste').exists())

    def test_criar_tipo_sincroniza_admissao_em_andamento(self):
        colab = Colaborador.objects.create(
            nome='Sync Admissao',
            cpf='202.202.202-20',
            cargo='Engenheiro Civil',
            status=Colaborador.Status.EM_ADMISSAO,
            etapa_admissao=2,
            requisicao_aprovada_gestor=True,
        )
        self.assertEqual(colab.documentos.count(), 0)

        self.client.force_login(self.user)
        self.client.post(reverse('recursos_humanos:documentos_config'), {
            'acao': 'criar',
            'nome': 'Doc Sync Todos',
            'aplica_a': 'todos',
            'obrigatorio': 'on',
        })
        colab.refresh_from_db()
        self.assertEqual(colab.documentos.filter(tipo__nome='Doc Sync Todos').count(), 1)

    def test_portal_salvar_dados_candidato(self):
        colab = Colaborador.objects.create(
            nome='Portal Dados',
            cpf='404.404.404-40',
            cargo='Pedreiro',
            status=Colaborador.Status.EM_ADMISSAO,
            etapa_admissao=2,
            requisicao_aprovada_gestor=True,
        )
        colab.gerar_token_portal(dias=30)
        url = reverse('recursos_humanos:portal', args=[colab.token_portal])
        resp = self.client.post(url, {
            'acao': 'salvar_dados',
            'rg': '1.234.567',
            'data_nascimento': '1990-05-15',
            'pis': '12345678901',
            'endereco': 'Rua Teste, 100 — Recife/PE',
            'dados_bancarios': 'Banco 001, Ag 1234, CC 56789-0',
            'escolaridade': 'Ensino médio completo',
            'tamanho_camisa': 'M',
            'tamanho_bota': '40',
        })
        self.assertEqual(resp.status_code, 302)
        colab.refresh_from_db()
        self.assertEqual(colab.rg, '1.234.567')
        self.assertEqual(colab.escolaridade, 'Ensino médio completo')
        self.assertEqual(colab.tamanho_camisa, 'M')
        self.assertTrue(
            colab.historico_admissao.filter(
                descricao__icontains='Dados pessoais atualizados',
            ).exists()
        )

    def test_admissao_view_sincroniza_documentos_ao_abrir(self):
        from recursos_humanos.models import CargoRH

        cargo_eng = CargoRH.objects.create(nome='Engenheiro')
        tipo_cargo = TipoDocumento.objects.create(
            nome='CNH Sync',
            aplica_a='por_cargo',
            obrigatorio=True,
            ordem=50,
        )
        tipo_cargo.cargos_aplicaveis.add(cargo_eng)
        colab = Colaborador.objects.create(
            nome='Sync View',
            cpf='303.303.303-30',
            cargo='Engenheiro Civil',
            cargo_rh=cargo_eng,
            status=Colaborador.Status.EM_ADMISSAO,
            etapa_admissao=2,
            requisicao_aprovada_gestor=True,
        )
        self.assertEqual(colab.documentos.count(), 0)

        self.client.force_login(self.user)
        resp = self.client.get(reverse('recursos_humanos:admissao'), {'id': colab.pk})
        self.assertEqual(resp.status_code, 200)
        colab.refresh_from_db()
        self.assertEqual(colab.documentos.filter(tipo__nome='CNH Sync').count(), 1)
        self.assertEqual(colab.documentos.filter(tipo__nome='Doc Obrig').count(), 1)
