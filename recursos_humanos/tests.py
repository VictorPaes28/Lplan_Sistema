from datetime import date, timedelta

from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from accounts.groups import GRUPOS
from django.contrib.auth.models import Group, User

from gestao_aprovacao.models import Obra

from recursos_humanos.models import (
    CargoRH,
    Colaborador,
    ContratoAdmissao,
    DocumentoColaborador,
    ObraLocal,
    TipoDocumento,
)
from recursos_humanos.services.alerts import gerar_alertas


def _criar_obra_local(nome, codigo):
    gestao = Obra.objects.create(codigo=codigo, nome=nome, ativo=True)
    return ObraLocal.objects.create(nome=nome, gestao_obra=gestao)


def _assinatura_aprovacao_teste() -> str:
    return 'data:image/png;base64,' + ('A' * 500)


def _dados_requisicao(obra_local, cargo_rh_id, aprovador_pk=None, **extra):
    obra_valor = extra.pop('obra', obra_local.pk)
    dados = {
        'nome': 'Novo Colab',
        'cpf': '888.888.888-88',
        'email': 'novo@example.com',
        'telefone': '81999998888',
        'cargo': 'Eletricista',
        'cargo_rh': cargo_rh_id,
        'obra': obra_valor,
        'tipo_contrato': 'CLT',
        'salario': 'R$ 3.500',
        'data_inicio': timezone.localdate().isoformat(),
        'motivo': 'Nova contratação',
        'observacoes': '',
    }
    dados.update(extra)
    if 'aprovadores' not in dados and aprovador_pk is not None:
        dados['aprovadores'] = [aprovador_pk]
    return dados


def _portal_autenticar_sessao(client, token):
    session = client.session
    session['rh_portal_auth'] = {token: timezone.now().isoformat()}
    session.save()


def _portal_autenticar_pin(client, colab, pin):
    url = reverse('recursos_humanos:portal', args=[colab.token_portal])
    return client.post(url, {
        'acao': 'autenticar_portal',
        'portal_pin': pin,
        'declaracao_identidade': 'on',
    })


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
        ontem = timezone.localdate() - timedelta(days=1)
        DocumentoColaborador.objects.create(
            colaborador=self.colab_desligado,
            tipo=self.tipo,
            status=DocumentoColaborador.Status.RECEBIDO,
            vencimento=ontem,
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

    def test_alerta_documento_abre_modal_na_aba_documentos(self):
        future = timezone.localdate() + timedelta(days=20)
        doc = DocumentoColaborador.objects.create(
            colaborador=self.colab_ativo,
            tipo=self.tipo,
            status=DocumentoColaborador.Status.RECEBIDO,
            vencimento=future,
        )
        alertas = [
            a for a in gerar_alertas()
            if a.colaborador_id == self.colab_ativo.pk and a.acao == 'Agendar'
        ]
        self.assertEqual(len(alertas), 1)
        self.assertIn('abrir_colaborador_tab=documentos', alertas[0].url)
        self.assertIn(f'abrir_colaborador_doc={doc.pk}', alertas[0].url)

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


class ConfiguracaoAlertasTests(TestCase):
    def setUp(self):
        grupo, _ = Group.objects.get_or_create(name=GRUPOS.RECURSOS_HUMANOS)
        self.user = User.objects.create_user(
            'rh_config',
            password='test',
            email='rh_config@example.com',
            is_staff=True,
        )
        self.user.groups.add(grupo)
        self.tipo = TipoDocumento.objects.create(nome='ASO Teste', tem_validade=True, ordem=1)
        self.colab = Colaborador.objects.create(
            nome='Config Teste',
            cpf='777.777.777-77',
            cargo='Pedreiro',
            status=Colaborador.Status.ATIVO,
        )

    def test_singleton_criado_com_defaults(self):
        from recursos_humanos.models import ConfiguracaoAlertasRH
        from recursos_humanos.services.alertas_config import obter_configuracao_alertas

        ConfiguracaoAlertasRH.objects.all().delete()
        config = obter_configuracao_alertas()
        self.assertEqual(config.pk, 1)
        self.assertEqual(config.dias_antecedencia_documentos, 30)
        self.assertEqual(config.dias_renotificar_vencidos, 7)
        self.assertTrue(config.notificar_email)
        self.assertTrue(config.notificar_sistema)

    def test_antecedencia_configuravel(self):
        from recursos_humanos.models import ConfiguracaoAlertasRH

        config = ConfiguracaoAlertasRH.get_solo()
        config.dias_antecedencia_documentos = 10
        config.save()

        tipo_b = TipoDocumento.objects.create(nome='NR Teste', tem_validade=True, ordem=2)
        DocumentoColaborador.objects.create(
            colaborador=self.colab,
            tipo=self.tipo,
            status=DocumentoColaborador.Status.RECEBIDO,
            vencimento=timezone.localdate() + timedelta(days=20),
        )
        DocumentoColaborador.objects.create(
            colaborador=self.colab,
            tipo=tipo_b,
            status=DocumentoColaborador.Status.RECEBIDO,
            vencimento=timezone.localdate() + timedelta(days=5),
        )
        alertas = [a for a in gerar_alertas() if a.colaborador_id == self.colab.pk]
        self.assertEqual(len(alertas), 1)
        self.assertEqual(alertas[0].dias_restantes, 5)

    @override_settings(
        EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
        CACHES={'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}},
    )
    def test_envia_email_agrupado_para_responsavel(self):
        from django.core import mail
        from django.core.cache import cache

        from recursos_humanos.models import ConfiguracaoAlertasRH
        from recursos_humanos.services.alertas_email import enviar_emails_alertas_diarios

        cache.clear()
        config = ConfiguracaoAlertasRH.get_solo()
        config.notificar_email = True
        config.save()
        config.responsaveis.set([self.user])

        DocumentoColaborador.objects.create(
            colaborador=self.colab,
            tipo=self.tipo,
            status=DocumentoColaborador.Status.RECEBIDO,
            vencimento=timezone.localdate() + timedelta(days=5),
        )
        alertas = gerar_alertas()
        enviados = enviar_emails_alertas_diarios(alertas)

        self.assertEqual(enviados, 1)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ['rh_config@example.com'])
        self.assertIn('Config Teste', mail.outbox[0].body)

    @override_settings(
        EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
        CACHES={'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}},
    )
    def test_nao_envia_email_quando_desativado(self):
        from django.core import mail
        from django.core.cache import cache

        from recursos_humanos.models import ConfiguracaoAlertasRH
        from recursos_humanos.services.alertas_email import enviar_emails_alertas_diarios

        cache.clear()
        config = ConfiguracaoAlertasRH.get_solo()
        config.notificar_email = False
        config.save()
        config.responsaveis.set([self.user])

        DocumentoColaborador.objects.create(
            colaborador=self.colab,
            tipo=self.tipo,
            status=DocumentoColaborador.Status.RECEBIDO,
            vencimento=timezone.localdate() + timedelta(days=5),
        )
        enviar_emails_alertas_diarios(gerar_alertas())
        self.assertEqual(len(mail.outbox), 0)

    def test_view_configuracao_salva_campos(self):
        staff = User.objects.create_user(
            'staff_alertas',
            password='test',
            email='staff@example.com',
            is_staff=True,
        )
        self.client.force_login(self.user)
        url = reverse('recursos_humanos:alertas_configurar')
        resp = self.client.post(url, {
            'dias_antecedencia_documentos': '15',
            'dias_renotificar_vencidos': '3',
            'notificar_email': 'on',
            'responsaveis': [str(staff.pk)],
        })
        self.assertEqual(resp.status_code, 302)

        from recursos_humanos.models import ConfiguracaoAlertasRH

        config = ConfiguracaoAlertasRH.get_solo()
        self.assertEqual(config.dias_antecedencia_documentos, 15)
        self.assertEqual(config.dias_renotificar_vencidos, 3)
        self.assertTrue(config.notificar_email)
        self.assertFalse(config.notificar_sistema)
        self.assertEqual(list(config.responsaveis.values_list('pk', flat=True)), [staff.pk])


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
        self.assertContains(resp, 'Conferência de documentos')

    def test_admissao_etapa2_nao_mostra_botoes_envio_portal(self):
        self.colab.requisicao_aprovada_gestor = True
        self.colab.email = 'adm@example.com'
        self.colab.gerar_token_portal()
        self.colab.save()
        self.client.force_login(self.user)
        resp = self.client.get(
            reverse('recursos_humanos:admissao'),
            {'id': self.colab.pk, 'ver_etapa': 2},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertNotContains(resp, 'Copiar link')
        self.assertNotContains(resp, 'Solicitar pendências')
        self.assertContains(resp, 'Conferência de documentos')

    def test_etapa1_nao_mostra_conferencia_docs(self):
        self.colab.etapa_admissao = 1
        self.colab.requisicao_aprovada_gestor = False
        self.colab.save(update_fields=['etapa_admissao', 'requisicao_aprovada_gestor'])
        self.client.force_login(self.user)
        resp = self.client.get(reverse('recursos_humanos:admissao'), {'id': self.colab.pk})
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'ETAPA 1')
        self.assertNotContains(resp, 'ETAPA 2 › Conferência de docs')


class AdmissaoFluxoFiltrosTests(TestCase):
    def setUp(self):
        grupo, _ = Group.objects.get_or_create(name=GRUPOS.RECURSOS_HUMANOS)
        self.rh = User.objects.create_user('rh_filtro', password='test')
        self.rh.groups.add(grupo)
        self.gestor = User.objects.create_user('gestor_filtro', password='test')
        self.gestor.groups.add(grupo)
        self.criador = User.objects.create_user('criador_filtro', password='test')
        self.criador.groups.add(grupo)

        self.pendente_gestor = Colaborador.objects.create(
            nome='Pendente Gestor',
            cpf='101.101.101-10',
            cargo='Pedreiro',
            status=Colaborador.Status.EM_ADMISSAO,
            etapa_admissao=1,
            gestor_aprovador_user=self.gestor,
            gestor_aprovador='Gestor Filtro',
        )
        self.pendente_gestor.aprovadores_requisicao.add(self.gestor)

        self.etapa2 = Colaborador.objects.create(
            nome='Etapa Dois',
            cpf='202.202.202-20',
            cargo='Servente',
            status=Colaborador.Status.EM_ADMISSAO,
            etapa_admissao=2,
            requisicao_aprovada_gestor=True,
            requisicao_criada_por=self.criador,
        )
        tipo = TipoDocumento.objects.create(nome='RG Filtro', ordem=1)
        DocumentoColaborador.objects.create(
            colaborador=self.etapa2,
            tipo=tipo,
            status=DocumentoColaborador.Status.PENDENTE,
        )

        self.reprovada = Colaborador.objects.create(
            nome='Reprovada',
            cpf='303.303.303-30',
            cargo='Auxiliar',
            status=Colaborador.Status.EM_ADMISSAO,
            etapa_admissao=1,
            requisicao_reprovada=True,
            requisicao_motivo_reprovacao='Ajustar salário',
        )

    def test_filtro_minha_aprovacao_gestor(self):
        self.client.force_login(self.gestor)
        url = reverse('recursos_humanos:admissao')
        resp = self.client.get(url, {'filtro': 'minha_aprovacao'})
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Pendente Gestor')
        self.assertNotContains(resp, 'Etapa Dois')
        self.assertContains(resp, 'Minha aprovação')

    def test_filtro_em_andamento(self):
        self.client.force_login(self.rh)
        resp = self.client.get(reverse('recursos_humanos:admissao'), {'filtro': 'em_andamento'})
        self.assertContains(resp, 'Pendente Gestor')
        self.assertContains(resp, 'Etapa Dois')
        self.assertContains(resp, 'Reprovada')

    def test_filtro_reprovadas(self):
        self.client.force_login(self.rh)
        resp = self.client.get(reverse('recursos_humanos:admissao'), {'filtro': 'reprovadas'})
        self.assertContains(resp, 'Reprovada')
        self.assertNotContains(resp, 'Pendente Gestor')

    def test_filtro_minhas(self):
        self.client.force_login(self.criador)
        resp = self.client.get(reverse('recursos_humanos:admissao'), {'filtro': 'minhas'})
        self.assertContains(resp, 'Etapa Dois')
        self.assertNotContains(resp, 'Pendente Gestor')

    def test_padrao_gestor_com_aprovacao_pendente(self):
        self.client.force_login(self.gestor)
        resp = self.client.get(reverse('recursos_humanos:admissao'))
        self.assertContains(resp, 'Pendente Gestor')
        self.assertNotContains(resp, 'Etapa Dois')


class AdmissaoWriteTests(TestCase):
    def setUp(self):
        grupo, _ = Group.objects.get_or_create(name=GRUPOS.RECURSOS_HUMANOS)
        self.user = User.objects.create_user('rh_write', password='test')
        self.user.groups.add(grupo)
        self.obra = _criar_obra_local('Obra Write', 'OW1')
        self.cargo_rh = CargoRH.objects.create(nome='Eletricista')
        self.tipo_obr = TipoDocumento.objects.create(nome='Doc Obrig', ordem=1, obrigatorio=True)
        self.tipo_opt = TipoDocumento.objects.create(nome='Doc Opt', ordem=2, obrigatorio=False)

    def test_form_clt_indeterminado_aceita_prazo_vazio(self):
        from recursos_humanos.forms import NovaRequisicaoForm

        dados = _dados_requisicao(
            self.obra, self.cargo_rh.pk, self.user.pk,
            obra=[self.obra.pk],
            prazo_duracao_dias='',
        )
        form = NovaRequisicaoForm(dados)
        self.assertTrue(form.is_valid(), form.errors)

    def test_form_clt_ignora_prazo_manual_na_requisicao(self):
        from recursos_humanos.forms import NovaRequisicaoForm

        dados = _dados_requisicao(
            self.obra, self.cargo_rh.pk, self.user.pk,
            obra=[self.obra.pk],
            prazo_duracao_dias='365',
        )
        form = NovaRequisicaoForm(dados)
        self.assertTrue(form.is_valid(), form.errors)
        self.assertFalse(form.tem_prazo())
        self.assertIsNone(form.get_tipo_prazo())

    def test_form_estagio_rejeita_acima_do_limite(self):
        from recursos_humanos.forms import NovaRequisicaoForm

        dados = _dados_requisicao(
            self.obra, self.cargo_rh.pk, self.user.pk,
            obra=[self.obra.pk],
            tipo_contrato='Estágio',
            prazo_duracao_dias='800',
        )
        form = NovaRequisicaoForm(dados)
        self.assertFalse(form.is_valid())
        self.assertIn('prazo_duracao_dias', form.errors)

    @override_settings(
        EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
        DEFAULT_FROM_EMAIL='rh@lplan.test',
    )
    def test_criar_requisicao_aguarda_aprovacao_etapa_1(self):
        from django.core import mail

        self.client.force_login(self.user)
        self.client.post(reverse('recursos_humanos:admissao_nova'), _dados_requisicao(
            self.obra, self.cargo_rh.pk, self.user.pk,
            nome='Notif Gestor', cpf='111.222.333-44', email='notif@example.com',
            telefone='81911112222',
        ))
        colab = Colaborador.objects.get(cpf='111.222.333-44')
        self.assertEqual(colab.etapa_admissao, 1)
        self.assertFalse(colab.requisicao_aprovada_gestor)
        self.assertEqual(colab.documentos.count(), 0)
        self.assertFalse(colab.token_portal)
        self.assertEqual(len(mail.outbox), 0)
        self.assertIn(self.user, colab.aprovadores_requisicao.all())

    @override_settings(
        EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
        DEFAULT_FROM_EMAIL='rh@lplan.test',
    )
    def test_criar_requisicao_via_post(self):
        self.client.force_login(self.user)
        resp = self.client.post(reverse('recursos_humanos:admissao_nova'), _dados_requisicao(
            self.obra, self.cargo_rh.pk, self.user.pk,
            nome='Novo Colab', cpf='888.888.888-88', email='novo@example.com',
            telefone='81999998888', observacoes='Teste',
        ))
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

    def test_requisicao_salva_deslocamento_origem_destino(self):
        self.client.force_login(self.user)
        self.client.post(reverse('recursos_humanos:admissao_nova'), _dados_requisicao(
            self.obra, self.cargo_rh.pk, self.user.pk,
            cpf='777.888.999-00',
            deslocamento_origem='Recife/PE',
            deslocamento_destino='Maceió/AL',
        ))
        colab = Colaborador.objects.get(cpf='777.888.999-00')
        self.assertEqual(colab.deslocamento_origem, 'Recife/PE')
        self.assertEqual(colab.deslocamento_destino, 'Maceió/AL')

    def test_requisicao_salva_reembolsos(self):
        import json

        self.client.force_login(self.user)
        reembolsos = [
            {'titulo': 'Passagem', 'descricao': 'Recife → Maceió', 'valor': '850,00'},
            {'titulo': 'Hospedagem', 'descricao': '3 diárias', 'valor': '600'},
        ]
        self.client.post(reverse('recursos_humanos:admissao_nova'), _dados_requisicao(
            self.obra, self.cargo_rh.pk, self.user.pk,
            cpf='666.555.444-33',
            reembolsos_json=json.dumps(reembolsos),
        ))
        colab = Colaborador.objects.get(cpf='666.555.444-33')
        self.assertEqual(len(colab.reembolsos), 2)
        self.assertEqual(colab.reembolsos[0]['titulo'], 'Passagem')
        self.assertEqual(colab.reembolsos[0]['descricao'], 'Recife → Maceió')
        self.assertEqual(colab.reembolsos[0]['valor'], '850,00')
        self.assertEqual(colab.reembolsos[1]['titulo'], 'Hospedagem')
        self.assertEqual(colab.reembolsos[1]['valor'], '600,00')

    def test_requisicao_salva_dados_candidato_opcionais(self):
        self.client.force_login(self.user)
        self.client.post(reverse('recursos_humanos:admissao_nova'), _dados_requisicao(
            self.obra, self.cargo_rh.pk, self.user.pk,
            cpf='222.333.444-55',
            rg='12.345.678-9',
            data_nascimento='1990-05-15',
            pis='123.45678.90-1',
            endereco='Rua A, 100 — Recife/PE',
            dados_bancarios='Banco X — ag 1234 — cc 56789-0',
            escolaridade='Ensino médio completo',
            tamanho_camisa='G',
            tamanho_bota='42',
            empresa='LPLAN',
        ))
        colab = Colaborador.objects.get(cpf='222.333.444-55')
        self.assertEqual(colab.rg, '12.345.678-9')
        self.assertEqual(colab.data_nascimento.isoformat(), '1990-05-15')
        self.assertEqual(colab.pis, '123.45678.90-1')
        self.assertEqual(colab.endereco, 'Rua A, 100 — Recife/PE')
        self.assertEqual(colab.dados_bancarios, 'Banco X — ag 1234 — cc 56789-0')
        self.assertEqual(colab.escolaridade, 'Ensino médio completo')
        self.assertEqual(colab.tamanho_camisa, 'G')
        self.assertEqual(colab.tamanho_bota, '42')
        self.assertEqual(colab.empresa, 'LPLAN')

    @override_settings(
        EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
        DEFAULT_FROM_EMAIL='rh@lplan.test',
    )
    def test_superuser_pode_corrigir_requisicao_reprovada(self):
        superuser = User.objects.create_superuser('admin_super', 'admin@lplan.test', 'test')
        self.client.force_login(superuser)
        self.client.post(reverse('recursos_humanos:admissao_nova'), _dados_requisicao(
            self.obra, self.cargo_rh.pk, superuser.pk,
            nome='Super Corrigir', cpf='333.333.333-33', email='super@example.com',
            telefone='81933332222',
        ))
        colab = Colaborador.objects.get(cpf='333.333.333-33')
        self.assertIn(superuser, colab.aprovadores_requisicao.all())
        colab.etapa_admissao = 1
        colab.requisicao_aprovada_gestor = False
        colab.requisicao_reprovada = True
        colab.requisicao_motivo_reprovacao = 'Teste'
        colab.save(update_fields=[
            'etapa_admissao', 'requisicao_aprovada_gestor',
            'requisicao_reprovada', 'requisicao_motivo_reprovacao', 'atualizado_em',
        ])
        resp = self.client.get(reverse('recursos_humanos:admissao'), {'id': colab.pk})
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Corrigir e reenviar requisição')

    def test_reprovar_requisicao_gestor(self):
        self.user.email = 'rh.criador@example.com'
        self.user.save(update_fields=['email'])
        colab = Colaborador.objects.create(
            nome='Reprovado Teste',
            cpf='555.555.555-55',
            email='reprovado@example.com',
            telefone='81966665555',
            cargo='Eletricista',
            cargo_rh=self.cargo_rh,
            status=Colaborador.Status.EM_ADMISSAO,
            etapa_admissao=1,
            gestor_aprovador_user=self.user,
            gestor_aprovador=self.user.get_full_name() or self.user.username,
            requisicao_criada_por=self.user,
        )
        colab.obras.add(self.obra)
        colab.aprovadores_requisicao.add(self.user)
        self.client.force_login(self.user)
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
    def test_corrigir_requisicao_reenvia_para_aprovacao(self):
        self.user.email = 'rh.criador2@example.com'
        self.user.save(update_fields=['email'])
        self.client.force_login(self.user)
        self.client.post(reverse('recursos_humanos:admissao_nova'), _dados_requisicao(
            self.obra, self.cargo_rh.pk, self.user.pk,
            nome='Corrigir Teste', cpf='444.444.444-44', email='corrigir@example.com',
            telefone='81955554444',
        ))
        colab = Colaborador.objects.get(cpf='444.444.444-44')
        colab.etapa_admissao = 1
        colab.requisicao_aprovada_gestor = False
        colab.requisicao_reprovada = True
        colab.requisicao_motivo_reprovacao = 'Ajustar salário'
        colab.save(update_fields=[
            'etapa_admissao', 'requisicao_aprovada_gestor',
            'requisicao_reprovada', 'requisicao_motivo_reprovacao', 'atualizado_em',
        ])
        resp = self.client.post(reverse('recursos_humanos:admissao_atualizar_requisicao', args=[colab.pk]), _dados_requisicao(
            self.obra, self.cargo_rh.pk, self.user.pk,
            nome='Corrigir Teste', cpf='444.444.444-44', email='corrigir@example.com',
            telefone='81955554444', salario='R$ 4.000', observacoes='Salário ajustado',
        ))
        self.assertEqual(resp.status_code, 302)
        colab.refresh_from_db()
        self.assertFalse(colab.requisicao_reprovada)
        self.assertFalse(colab.requisicao_aprovada_gestor)
        self.assertEqual(colab.etapa_admissao, 1)
        self.assertEqual(colab.salario, '4.000,00')
        self.assertEqual(colab.requisicao_motivo_reprovacao, '')
        self.assertEqual(colab.documentos.count(), 0)

    @override_settings(
        EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
        DEFAULT_FROM_EMAIL='rh@lplan.test',
        RH_ENVIO_PORTAL_CANDIDATO_ATIVO=True,
    )
    def test_aprovar_requisicao_gestor_legado_etapa_1(self):
        from django.core import mail

        colab = Colaborador.objects.create(
            nome='Gestor Aprova',
            cpf='666.666.666-66',
            email='gestor.aprova@example.com',
            telefone='81988887777',
            cargo='Eletricista',
            cargo_rh=self.cargo_rh,
            status=Colaborador.Status.EM_ADMISSAO,
            etapa_admissao=1,
            gestor_aprovador_user=self.user,
            gestor_aprovador=self.user.get_full_name() or self.user.username,
        )
        colab.obras.add(self.obra)
        colab.aprovadores_requisicao.add(self.user)
        self.client.force_login(self.user)
        url = reverse('recursos_humanos:admissao_acao', args=[colab.pk])
        resp = self.client.post(url, {
            'acao': 'aprovar_requisicao',
            'signature_data': _assinatura_aprovacao_teste(),
        })
        self.assertEqual(resp.status_code, 302)
        colab.refresh_from_db()
        self.assertTrue(colab.requisicao_aprovada_gestor)
        self.assertEqual(colab.requisicao_aprovada_por_id, self.user.pk)
        self.assertTrue(colab.requisicao_aprovacao_assinatura.startswith('data:image/png;base64,'))
        self.assertIsNotNone(colab.requisicao_aprovada_em)
        self.assertEqual(colab.etapa_admissao, 2)
        self.assertGreater(colab.documentos.count(), 0)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ['gestor.aprova@example.com'])
        self.assertIn(colab.token_portal, mail.outbox[0].body)

    def test_aprovar_requisicao_exige_assinatura(self):
        colab = Colaborador.objects.create(
            nome='Sem Assinatura',
            cpf='555.555.555-55',
            email='sem.sig@example.com',
            cargo='Eletricista',
            cargo_rh=self.cargo_rh,
            status=Colaborador.Status.EM_ADMISSAO,
            etapa_admissao=1,
        )
        colab.obras.add(self.obra)
        colab.aprovadores_requisicao.add(self.user)
        self.client.force_login(self.user)
        url = reverse('recursos_humanos:admissao_acao', args=[colab.pk])
        resp = self.client.post(url, {'acao': 'aprovar_requisicao'})
        self.assertEqual(resp.status_code, 302)
        colab.refresh_from_db()
        self.assertFalse(colab.requisicao_aprovada_gestor)
        self.assertEqual(colab.etapa_admissao, 1)

    def test_criar_requisicao_sem_email_opcional(self):
        self.client.force_login(self.user)
        self.client.post(reverse('recursos_humanos:admissao_nova'), _dados_requisicao(
            self.obra, self.cargo_rh.pk, self.user.pk,
            cpf='999.000.111-22', email='',
        ))
        colab = Colaborador.objects.get(cpf='999.000.111-22')
        self.assertEqual(colab.email, '')

    def test_criar_requisicao_multiplas_obras(self):
        obra2 = _criar_obra_local('Obra Write 2', 'OW2')
        self.client.force_login(self.user)
        resp = self.client.post(reverse('recursos_humanos:admissao_nova'), _dados_requisicao(
            self.obra, self.cargo_rh.pk, self.user.pk,
            nome='Novo Multi Obra', cpf='777.777.777-77', email='multi@example.com',
            telefone='81977776666', obra=[self.obra.pk, obra2.pk],
        ))
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
            colaborador=colab, tipo=self.tipo_opt, status=DocumentoColaborador.Status.RECEBIDO,
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

        ContratoAdmissao.objects.create(
            colaborador=colab,
            status=ContratoAdmissao.Status.CONCLUIDO,
            concluido_em=timezone.now(),
            data_admissao_oficial=timezone.localdate(),
        )
        from recursos_humanos.services.admissao_actions import registrar_historico

        registrar_historico(
            colab, 4, 'Contrato enviado para assinatura no ZapSign', 'Teste',
        )
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

    def test_documentos_config_criar_com_campos_estendidos(self):
        from recursos_humanos.models import CargoRH

        cargo = CargoRH.objects.create(nome='Eletricista Modal')
        self.client.force_login(self.user)
        resp = self.client.post(reverse('recursos_humanos:documentos_config'), {
            'acao': 'criar',
            'nome': 'NR-10 Modal',
            'categoria': 'treinamentos',
            'instrucoes_portal': 'Envie certificado em PDF',
            'aplica_a': 'por_cargo',
            'cargo_context': str(cargo.pk),
            'tem_validade': 'on',
            'dias_validade': 730,
            'obrigatorio': 'on',
            'ativo': 'on',
        })
        self.assertEqual(resp.status_code, 302)
        tipo = TipoDocumento.objects.get(nome='NR-10 Modal')
        self.assertEqual(tipo.categoria, 'treinamentos')
        self.assertEqual(tipo.instrucoes_portal, 'Envie certificado em PDF')
        self.assertTrue(tipo.ativo)
        self.assertGreater(tipo.ordem, 0)
        self.assertTrue(tipo.cargos_aplicaveis.filter(pk=cargo.pk).exists())

    def test_documentos_config_criar_por_cargo_com_multiplos_cargos(self):
        from recursos_humanos.models import CargoRH

        c1 = CargoRH.objects.create(nome='Pedreiro Modal')
        c2 = CargoRH.objects.create(nome='Servente Modal')
        self.client.force_login(self.user)
        resp = self.client.post(reverse('recursos_humanos:documentos_config'), {
            'acao': 'criar',
            'nome': 'NR-35 Multi',
            'aplica_a': 'por_cargo',
            'cargos_aplicaveis': [str(c1.pk), str(c2.pk)],
            'obrigatorio': 'on',
        })
        self.assertEqual(resp.status_code, 302)
        tipo = TipoDocumento.objects.get(nome='NR-35 Multi')
        self.assertEqual(tipo.aplica_a, 'por_cargo')
        self.assertEqual(tipo.cargos_aplicaveis.count(), 2)

    def test_tipo_inativo_nao_instancia_em_admissao(self):
        from recursos_humanos.services.admissao_actions import instanciar_documentos

        TipoDocumento.objects.create(
            nome='Doc Inativo Teste',
            aplica_a='todos',
            ativo=False,
            ordem=99,
        )
        colab = Colaborador.objects.create(
            nome='Sem Doc Inativo',
            cpf='303.303.303-30',
            cargo='Auxiliar',
            status=Colaborador.Status.EM_ADMISSAO,
            etapa_admissao=2,
            requisicao_aprovada_gestor=True,
        )
        criados = instanciar_documentos(colab)
        self.assertGreater(criados, 0)
        self.assertFalse(colab.documentos.filter(tipo__nome='Doc Inativo Teste').exists())
        self.assertTrue(colab.documentos.filter(tipo=self.tipo_obr).exists())

    def test_categoria_tipo_usada_nos_grupos(self):
        from recursos_humanos.services.admissao import montar_grupos_documentos

        tipo = TipoDocumento.objects.create(
            nome='Custom Treinamento',
            categoria='treinamentos',
            ordem=50,
        )
        colab = Colaborador.objects.create(
            nome='Grupo Cat',
            cpf='405.405.405-40',
            cargo='Pedreiro',
            status=Colaborador.Status.EM_ADMISSAO,
            etapa_admissao=2,
        )
        DocumentoColaborador.objects.create(
            colaborador=colab,
            tipo=tipo,
            status=DocumentoColaborador.Status.FALTANDO,
        )
        grupos = montar_grupos_documentos(colab)
        trein = next(g for g in grupos if g.id == 'treinamentos')
        self.assertEqual(trein.docs[0].nome, 'Custom Treinamento')
        self.assertEqual(trein.docs[0].instrucoes_portal, '')

    def test_documentos_hub_salvar_cargo(self):
        from recursos_humanos.models import CargoRH

        cargo = CargoRH.objects.create(nome='Eletricista Hub')
        tipo = TipoDocumento.objects.create(
            nome='NR-10 Hub',
            aplica_a='por_cargo',
            obrigatorio=True,
            ordem=60,
        )
        self.client.force_login(self.user)
        resp = self.client.post(reverse('recursos_humanos:documentos_config'), {
            'acao': 'salvar_cargo',
            'painel': 'cargo',
            'cargo_id': cargo.pk,
            'tipo_cargo': [str(tipo.pk)],
        })
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(tipo.cargos_aplicaveis.filter(pk=cargo.pk).exists())

    def test_documentos_hub_preview_json(self):
        from recursos_humanos.models import CargoRH

        cargo = CargoRH.objects.create(nome='Pedreiro Hub')
        self.client.force_login(self.user)
        resp = self.client.get(
            reverse('recursos_humanos:documentos_config_preview'),
            {'cargo': cargo.pk},
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn('total', data)
        self.assertGreaterEqual(data['total'], 1)

    def test_cargos_redireciona_para_documentos(self):
        self.client.force_login(self.user)
        resp = self.client.get(reverse('recursos_humanos:cargos'))
        self.assertEqual(resp.status_code, 302)
        self.assertIn('painel=cargo', resp.url)

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
        _portal_autenticar_sessao(self.client, colab.token_portal)
        url = reverse('recursos_humanos:portal', args=[colab.token_portal])
        resp = self.client.post(url, {
            'acao': 'submeter_portal',
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

    @override_settings(
        EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
        DEFAULT_FROM_EMAIL='rh@lplan.test',
    )
    def test_gestor_nao_aprovador_nao_aprova_requisicao(self):
        gestor = User.objects.create_user('gestor_only', password='test')
        self.client.force_login(self.user)
        self.client.post(reverse('recursos_humanos:admissao_nova'), _dados_requisicao(
            self.obra, self.cargo_rh.pk, self.user.pk,
            nome='Aprova Gestor', cpf='404.404.404-40', email='gestor.only@example.com',
            telefone='81940404040',
        ))
        colab = Colaborador.objects.get(cpf='404.404.404-40')
        self.assertEqual(colab.etapa_admissao, 1)
        self.assertFalse(colab.requisicao_aprovada_gestor)
        self.client.logout()
        self.client.force_login(gestor)
        url = reverse('recursos_humanos:gestor_aprovar_requisicao', args=[colab.pk])
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 302)

    def test_criar_requisicao_salva_aprovadores_selecionados(self):
        outro_usuario = User.objects.create_user('outro_rh', password='test')
        self.client.force_login(self.user)
        resp = self.client.post(reverse('recursos_humanos:admissao_nova'), _dados_requisicao(
            self.obra, self.cargo_rh.pk, outro_usuario.pk,
            nome='Gestor Logado', cpf='808.808.808-80', email='livre@example.com',
            telefone='81980808080',
        ))
        self.assertEqual(resp.status_code, 302)
        colab = Colaborador.objects.get(cpf='808.808.808-80')
        self.assertIn(outro_usuario, colab.aprovadores_requisicao.all())
        self.assertNotIn(self.user, colab.aprovadores_requisicao.all())

    def test_concluir_admissao_exige_contrato_assinado(self):
        colab = Colaborador.objects.create(
            nome='Sem Contrato',
            cpf='909.909.909-90',
            cargo='Pedreiro',
            status=Colaborador.Status.EM_ADMISSAO,
            etapa_admissao=4,
        )
        self.client.force_login(self.user)
        url = reverse('recursos_humanos:admissao_acao', args=[colab.pk])
        resp = self.client.post(url, {'acao': 'concluir'})
        self.assertEqual(resp.status_code, 302)
        colab.refresh_from_db()
        self.assertEqual(colab.etapa_admissao, 4)
        self.assertEqual(colab.status, Colaborador.Status.EM_ADMISSAO)

    def test_avancar_etapa_1_bloqueado(self):
        colab = Colaborador.objects.create(
            nome='Etapa 1',
            cpf='101.010.101-01',
            cargo='Pedreiro',
            status=Colaborador.Status.EM_ADMISSAO,
            etapa_admissao=1,
            requisicao_aprovada_gestor=True,
        )
        self.client.force_login(self.user)
        url = reverse('recursos_humanos:admissao_acao', args=[colab.pk])
        resp = self.client.post(url, {'acao': 'avancar'})
        self.assertEqual(resp.status_code, 302)
        colab.refresh_from_db()
        self.assertEqual(colab.etapa_admissao, 1)

    def test_admissao_concluida_permanece_no_fluxo(self):
        from unittest.mock import patch

        colab = Colaborador.objects.create(
            nome='Concluido Fluxo',
            cpf='505.505.505-50',
            cargo='Pedreiro',
            status=Colaborador.Status.ATIVO,
            etapa_admissao=5,
            data_admissao=timezone.localdate(),
        )
        tipo = TipoDocumento.objects.create(nome='Doc OK', ordem=99, obrigatorio=True)
        DocumentoColaborador.objects.create(
            colaborador=colab,
            tipo=tipo,
            status=DocumentoColaborador.Status.RECEBIDO,
        )
        self.client.force_login(self.user)
        with patch('recursos_humanos.views.instanciar_documentos'):
            resp = self.client.get(reverse('recursos_humanos:admissao'), {'id': colab.pk})
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Concluido Fluxo')
        self.assertContains(resp, 'Admissão concluída')


class SolicitarReenvioDocumentoTests(TestCase):
    def setUp(self):
        grupo, _ = Group.objects.get_or_create(name=GRUPOS.RECURSOS_HUMANOS)
        self.user = User.objects.create_user('rh_reenvio', password='test')
        self.user.groups.add(grupo)
        self.tipo = TipoDocumento.objects.create(
            nome='ASO Reenvio',
            tem_validade=True,
            dias_validade=365,
            ordem=1,
        )
        self.colab = Colaborador.objects.create(
            nome='Colab Reenvio',
            cpf='707.707.707-70',
            email='reenvio@example.com',
            cargo='Pedreiro',
            status=Colaborador.Status.ATIVO,
        )
        self.colab.gerar_token_portal(dias=30)
        self.doc = DocumentoColaborador.objects.create(
            colaborador=self.colab,
            tipo=self.tipo,
            status=DocumentoColaborador.Status.RECEBIDO,
            data_emissao=date(2024, 1, 1),
            vencimento=timezone.localdate() - timedelta(days=5),
        )

    @override_settings(
        EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
        RH_ENVIO_PORTAL_CANDIDATO_ATIVO=True,
    )
    def test_solicitar_reenvio_mantem_arquivo_e_envia_email(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        from django.core import mail
        from recursos_humanos.services.documentos import solicitar_reenvio_documento

        self.doc.arquivo.save('aso.pdf', SimpleUploadedFile('aso.pdf', b'pdf'), save=True)
        ok, _ = solicitar_reenvio_documento(self.doc, self.user)
        self.assertTrue(ok)
        self.doc.refresh_from_db()
        self.assertEqual(self.doc.status, DocumentoColaborador.Status.RECEBIDO)
        self.assertTrue(self.doc.reenvio_solicitado)
        self.assertTrue(self.doc.arquivo)
        self.assertIsNotNone(self.doc.vencimento)
        self.assertEqual(len(mail.outbox), 1)

    @override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
    def test_view_solicitar_reenvio_redireciona_com_modal(self):
        self.client.force_login(self.user)
        url = reverse(
            'recursos_humanos:documento_solicitar_reenvio',
            kwargs={'pk': self.colab.pk, 'doc_pk': self.doc.pk},
        )
        resp = self.client.post(url)
        self.assertEqual(resp.status_code, 302)
        self.assertIn('abrir_colaborador=' + str(self.colab.pk), resp.url)
        self.doc.refresh_from_db()
        self.assertTrue(self.doc.reenvio_solicitado)

    def test_etapa_fluxo_pendente_vai_para_coleta(self):
        from recursos_humanos.services.documentos import etapa_fluxo_efetiva

        self.colab.etapa_admissao = 5
        self.colab.save(update_fields=['etapa_admissao'])
        self.doc.status = DocumentoColaborador.Status.PENDENTE
        self.doc.save(update_fields=['status'])
        self.assertEqual(etapa_fluxo_efetiva(self.colab), 2)

    def test_etapa_1_com_docs_nao_pula_para_coleta(self):
        from recursos_humanos.services.documentos import etapa_fluxo_efetiva

        self.colab.status = Colaborador.Status.EM_ADMISSAO
        self.colab.etapa_admissao = 1
        self.colab.requisicao_aprovada_gestor = False
        self.colab.save(update_fields=['status', 'etapa_admissao', 'requisicao_aprovada_gestor'])
        self.assertEqual(etapa_fluxo_efetiva(self.colab), 1)

    def test_documento_faltando_obrigatorio_impede_admissao_concluida(self):
        from recursos_humanos.services.admissao_actions import colaborador_admissao_concluida

        self.tipo.obrigatorio = True
        self.tipo.save(update_fields=['obrigatorio'])
        self.doc.status = DocumentoColaborador.Status.FALTANDO
        self.doc.observacao = 'Rejeitado pelo RH'
        self.doc.save(update_fields=['status', 'observacao'])
        self.colab.etapa_admissao = 5
        self.colab.save(update_fields=['etapa_admissao'])
        self.assertFalse(colaborador_admissao_concluida(self.colab))

    def test_pendencia_documento_impede_admissao_concluida(self):
        from recursos_humanos.services.admissao_actions import colaborador_admissao_concluida

        self.colab.etapa_admissao = 5
        self.colab.save(update_fields=['etapa_admissao'])
        self.assertFalse(colaborador_admissao_concluida(self.colab))

    def test_portal_ativo_com_token_acessa_upload(self):
        self.doc.reenvio_solicitado = True
        self.doc.save(update_fields=['reenvio_solicitado'])
        _portal_autenticar_sessao(self.client, self.colab.token_portal)
        url = reverse('recursos_humanos:portal', args=[self.colab.token_portal])
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'ASO Reenvio')
        self.assertContains(resp, 'Enviar tudo')
        self.assertContains(resp, 'portal-doc-upload')


class EnviarLembreteColetaTests(TestCase):
    def setUp(self):
        grupo, _ = Group.objects.get_or_create(name=GRUPOS.RECURSOS_HUMANOS)
        self.user = User.objects.create_user('rh_lembrete', password='test')
        self.user.groups.add(grupo)
        self.tipo_cnh = TipoDocumento.objects.create(
            nome='CNH',
            tem_validade=True,
            dias_validade=365,
            ordem=1,
            obrigatorio=True,
        )
        self.tipo_rg = TipoDocumento.objects.create(
            nome='Carteira de Identidade',
            ordem=2,
            obrigatorio=True,
        )
        self.colab = Colaborador.objects.create(
            nome='Felipe',
            cpf='909.909.909-90',
            email='felipe@example.com',
            cargo='Pedreiro',
            status=Colaborador.Status.EM_ADMISSAO,
            etapa_admissao=2,
            requisicao_aprovada_gestor=True,
        )
        self.colab.gerar_token_portal(dias=30)
        DocumentoColaborador.objects.create(
            colaborador=self.colab,
            tipo=self.tipo_cnh,
            status=DocumentoColaborador.Status.FALTANDO,
        )
        DocumentoColaborador.objects.create(
            colaborador=self.colab,
            tipo=self.tipo_rg,
            status=DocumentoColaborador.Status.FALTANDO,
        )

    @override_settings(
        EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
        RH_ENVIO_PORTAL_CANDIDATO_ATIVO=True,
    )
    def test_enviar_lembrete_manda_email_com_documentos_pendentes(self):
        from django.core import mail
        from recursos_humanos.services.admissao_actions import enviar_lembrete_coleta_documentos

        ok, msg = enviar_lembrete_coleta_documentos(self.colab, self.user)
        self.assertTrue(ok)
        self.assertIn('felipe@example.com', msg)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('CNH', mail.outbox[0].body)
        self.assertIn('Carteira de Identidade', mail.outbox[0].body)
        self.assertIn(self.colab.token_portal, mail.outbox[0].body)

    @override_settings(
        EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
        RH_ENVIO_PORTAL_CANDIDATO_ATIVO=True,
    )
    def test_view_enviar_lembrete_via_admissao_acao(self):
        from django.core import mail

        self.client.force_login(self.user)
        url = reverse('recursos_humanos:admissao_acao', args=[self.colab.pk])
        resp = self.client.post(url, {'acao': 'enviar_lembrete'})
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ['felipe@example.com'])

    def test_lembrete_falha_sem_documentos_pendentes(self):
        from recursos_humanos.services.admissao_actions import enviar_lembrete_coleta_documentos

        self.colab.documentos.update(status=DocumentoColaborador.Status.RECEBIDO)
        self.colab.rg = '1234567'
        self.colab.data_nascimento = date(1990, 1, 1)
        self.colab.endereco = 'Rua Teste'
        self.colab.dados_bancarios = 'Banco 123'
        self.colab.escolaridade = 'Médio'
        self.colab.tamanho_camisa = 'M'
        self.colab.tamanho_bota = '40'
        self.colab.save()
        ok, msg = enviar_lembrete_coleta_documentos(self.colab, self.user)
        self.assertFalse(ok)
        self.assertIn('faltando', msg.lower())


class SolicitarPendenciasColetaTests(TestCase):
    def setUp(self):
        grupo, _ = Group.objects.get_or_create(name=GRUPOS.RECURSOS_HUMANOS)
        self.user = User.objects.create_user('rh_pendencias', password='test')
        self.user.groups.add(grupo)
        self.tipo = TipoDocumento.objects.create(
            nome='RG Digital',
            ordem=1,
            obrigatorio=True,
        )
        self.tipo_vencido = TipoDocumento.objects.create(
            nome='ASO Vencido',
            tem_validade=True,
            dias_validade=365,
            ordem=2,
            obrigatorio=True,
        )
        self.colab = Colaborador.objects.create(
            nome='Marina',
            cpf='808.808.808-80',
            email='marina@example.com',
            cargo='Servente',
            status=Colaborador.Status.EM_ADMISSAO,
            etapa_admissao=2,
            requisicao_aprovada_gestor=True,
        )
        self.colab.gerar_token_portal(dias=30)
        DocumentoColaborador.objects.create(
            colaborador=self.colab,
            tipo=self.tipo,
            status=DocumentoColaborador.Status.FALTANDO,
            observacao='Foto ilegível',
        )
        DocumentoColaborador.objects.create(
            colaborador=self.colab,
            tipo=self.tipo_vencido,
            status=DocumentoColaborador.Status.RECEBIDO,
            vencimento=timezone.localdate() - timedelta(days=3),
        )

    def test_analisar_pendencias_inclui_documento_opcional_faltando(self):
        from recursos_humanos.services.documentos import analisar_pendencias_coleta

        tipo_opt = TipoDocumento.objects.create(nome='Doc Opcional', ordem=9, obrigatorio=False)
        DocumentoColaborador.objects.create(
            colaborador=self.colab,
            tipo=tipo_opt,
            status=DocumentoColaborador.Status.FALTANDO,
        )
        labels = [p['label'] for p in analisar_pendencias_coleta(self.colab)]
        self.assertIn('Doc Opcional', labels)

    def test_etapa2_sem_flag_aprovacao_nao_mostra_botao_pendencias(self):
        self.colab.requisicao_aprovada_gestor = False
        self.colab.save(update_fields=['requisicao_aprovada_gestor', 'atualizado_em'])
        self.client.force_login(self.user)
        resp = self.client.get(
            reverse('recursos_humanos:admissao'),
            {'id': self.colab.pk, 'ver_etapa': 2},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertNotContains(resp, 'Solicitar pendências')

    def test_analisar_pendencias_ignora_documento_vencido(self):
        from recursos_humanos.services.documentos import analisar_pendencias_coleta

        pendencias = analisar_pendencias_coleta(self.colab)
        labels = [p['label'] for p in pendencias]
        self.assertIn('RG Digital', labels)
        self.assertNotIn('ASO Vencido', labels)

    def test_analisar_pendencias_inclui_dados_faltantes(self):
        from recursos_humanos.services.documentos import analisar_pendencias_coleta

        pendencias = analisar_pendencias_coleta(self.colab)
        tipos = {p['tipo'] for p in pendencias}
        self.assertIn('dado', tipos)
        self.assertIn('documento', tipos)

    @override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
    def test_solicitar_pendencias_sem_envio_nao_manda_email(self):
        from django.core import mail
        from recursos_humanos.services.admissao_actions import solicitar_pendencias_colaborador

        ok, msg = solicitar_pendencias_colaborador(self.colab, self.user)
        self.assertTrue(ok)
        self.assertIn('registradas', msg.lower())
        self.assertEqual(len(mail.outbox), 0)

    @override_settings(
        EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
        RH_ENVIO_PORTAL_CANDIDATO_ATIVO=True,
    )
    def test_solicitar_pendencias_envia_email_com_lista(self):
        from django.core import mail
        from recursos_humanos.services.admissao_actions import solicitar_pendencias_colaborador

        ok, msg = solicitar_pendencias_colaborador(self.colab, self.user)
        self.assertTrue(ok)
        self.assertIn('marina@example.com', msg)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('RG Digital', mail.outbox[0].body)
        self.assertIn('Código de acesso ao portal:', mail.outbox[0].body)
        self.assertNotIn('enviado anteriormente', mail.outbox[0].body)
        self.assertNotIn('ASO Vencido', mail.outbox[0].body)

    @override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
    def test_solicitar_pendencias_marca_coleta_solicitada(self):
        from recursos_humanos.services.admissao_actions import solicitar_pendencias_colaborador

        solicitar_pendencias_colaborador(self.colab, self.user)
        doc_rg = self.colab.documentos.get(tipo=self.tipo)
        doc_aso = self.colab.documentos.get(tipo=self.tipo_vencido)
        self.assertTrue(doc_rg.coleta_solicitada)
        self.assertFalse(doc_aso.coleta_solicitada)
        self.assertTrue(self.colab.dados_coleta_solicitada)

    def test_pode_solicitar_pendencias_com_apenas_telefone(self):
        from recursos_humanos.services.documentos import pode_solicitar_pendencias_coleta

        self.colab.email = ''
        self.colab.telefone = '81988887777'
        self.colab.save(update_fields=['email', 'telefone'])
        self.assertTrue(pode_solicitar_pendencias_coleta(self.colab, self.user))

    @override_settings(
        EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
        RH_ENVIO_PORTAL_CANDIDATO_ATIVO=True,
    )
    def test_view_solicitar_pendencias_no_perfil(self):
        from django.core import mail

        self.client.force_login(self.user)
        url = reverse('recursos_humanos:colaborador_solicitar_pendencias', args=[self.colab.pk])
        resp = self.client.post(url)
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(len(mail.outbox), 1)

    @override_settings(
        EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
        RH_ENVIO_PORTAL_CANDIDATO_ATIVO=True,
    )
    def test_solicitar_correcao_dados_envia_notificacao(self):
        from django.core import mail
        from recursos_humanos.services.admissao_actions import solicitar_correcao_dados_portal

        self.colab.rg = '11.111.111-1'
        self.colab.data_nascimento = date(1990, 1, 1)
        self.colab.endereco = 'Rua X'
        self.colab.dados_bancarios = 'Banco'
        self.colab.escolaridade = 'Médio'
        self.colab.tamanho_camisa = 'M'
        self.colab.tamanho_bota = '40'
        self.colab.save()
        ok, _ = solicitar_correcao_dados_portal(self.colab, self.user, motivo='Corrigir endereço')
        self.assertTrue(ok)
        self.colab.refresh_from_db()
        self.assertTrue(self.colab.dados_coleta_solicitada)
        self.assertEqual(len(mail.outbox), 1)

    def test_admissao_mostra_dados_portal_na_etapa_2(self):
        self.colab.rg = '11.111.111-1'
        self.colab.data_nascimento = date(1990, 1, 1)
        self.colab.endereco = 'Rua X'
        self.colab.dados_bancarios = 'Banco'
        self.colab.escolaridade = 'Médio'
        self.colab.tamanho_camisa = 'M'
        self.colab.tamanho_bota = '40'
        self.colab.save()
        self.client.force_login(self.user)
        resp = self.client.get(
            reverse('recursos_humanos:admissao'),
            {'id': self.colab.pk, 'ver_etapa': 2},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Dados pessoais do portal')
        self.assertNotContains(resp, 'Solicitar correção dos dados')
        self.assertContains(resp, '11.111.111-1')


class PortalModoRestritoTests(TestCase):
    def setUp(self):
        self.tipo_aso = TipoDocumento.objects.create(
            nome='ASO Restrito',
            tem_validade=True,
            dias_validade=365,
            ordem=1,
            obrigatorio=True,
        )
        self.tipo_cnh = TipoDocumento.objects.create(
            nome='CNH Restrito',
            ordem=2,
            obrigatorio=True,
        )
        self.colab = Colaborador.objects.create(
            nome='Paulo Restrito',
            cpf='606.606.606-60',
            email='paulo@example.com',
            cargo='Pedreiro',
            status=Colaborador.Status.ATIVO,
        )
        self.colab.gerar_token_portal(dias=30)
        self.doc_aso = DocumentoColaborador.objects.create(
            colaborador=self.colab,
            tipo=self.tipo_aso,
            status=DocumentoColaborador.Status.RECEBIDO,
            vencimento=timezone.localdate() - timedelta(days=2),
            reenvio_solicitado=True,
        )
        self.doc_cnh = DocumentoColaborador.objects.create(
            colaborador=self.colab,
            tipo=self.tipo_cnh,
            status=DocumentoColaborador.Status.FALTANDO,
        )

    def test_apenas_documento_com_reenvio_solicitado_pode_enviar(self):
        from recursos_humanos.services.documentos import documento_permite_envio_portal

        self.assertTrue(documento_permite_envio_portal(self.doc_aso, self.colab))
        self.assertFalse(documento_permite_envio_portal(self.doc_cnh, self.colab))

    def test_portal_html_mostra_envio_somente_no_documento_liberado(self):
        _portal_autenticar_sessao(self.client, self.colab.token_portal)
        url = reverse('recursos_humanos:portal', args=[self.colab.token_portal])
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Documentos já recebidos pelo RH')
        self.assertContains(resp, 'Itens solicitados pelo RH')
        self.assertContains(resp, 'portal-doc-upload--com-emissao')
        self.assertContains(resp, 'ASO Restrito')
        self.assertNotContains(resp, 'CNH Restrito')

    def test_portal_envio_parcial_preserva_documentos_validos(self):
        from django.core.files.uploadedfile import SimpleUploadedFile

        from recursos_humanos.forms import PORTAL_UPLOAD_MAX_BYTES

        self.doc_cnh.reenvio_solicitado = True
        self.doc_cnh.save(update_fields=['reenvio_solicitado'])
        _portal_autenticar_sessao(self.client, self.colab.token_portal)
        url = reverse('recursos_humanos:portal', args=[self.colab.token_portal])
        ok = SimpleUploadedFile('aso.pdf', b'%PDF ok', content_type='application/pdf')
        grande = SimpleUploadedFile(
            'cnh.pdf',
            b'0' * (PORTAL_UPLOAD_MAX_BYTES + 1),
            content_type='application/pdf',
        )
        resp = self.client.post(url, {
            'acao': 'submeter_portal',
            f'doc_emissao_{self.doc_aso.pk}': timezone.localdate().isoformat(),
            f'doc_{self.doc_aso.pk}': ok,
            f'doc_{self.doc_cnh.pk}': grande,
        })
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp.url, url)
        self.doc_aso.refresh_from_db()
        self.doc_cnh.refresh_from_db()
        self.assertTrue(self.doc_aso.arquivo)
        self.assertFalse(self.doc_cnh.arquivo)
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'CNH Restrito')
        self.assertNotContains(resp, f'name="doc_{self.doc_aso.pk}"')
        self.assertContains(resp, f'name="doc_{self.doc_cnh.pk}"')

    def test_marcar_pendencias_acumula_solicitacoes(self):
        from recursos_humanos.services.documentos import marcar_pendencias_solicitadas_portal

        marcar_pendencias_solicitadas_portal(self.colab, [
            {'tipo': 'documento', 'label': 'ASO Restrito', 'detalhe': 'vencido'},
        ])
        self.doc_aso.refresh_from_db()
        self.assertTrue(self.doc_aso.coleta_solicitada)
        marcar_pendencias_solicitadas_portal(self.colab, [
            {'tipo': 'documento', 'label': 'CNH Restrito', 'detalhe': 'faltando'},
        ])
        self.doc_aso.refresh_from_db()
        self.doc_cnh.refresh_from_db()
        self.assertTrue(self.doc_aso.coleta_solicitada)
        self.assertTrue(self.doc_cnh.coleta_solicitada)


class PortalAdmissaoRestritoTests(TestCase):
    def setUp(self):
        self.tipo_rejeitado = TipoDocumento.objects.create(
            nome='RG Rejeitado',
            ordem=1,
            obrigatorio=True,
        )
        self.tipo_faltando = TipoDocumento.objects.create(
            nome='ASO Faltando',
            ordem=2,
            obrigatorio=True,
        )
        self.tipo_ok = TipoDocumento.objects.create(
            nome='CPF OK',
            ordem=3,
            obrigatorio=True,
        )
        self.colab = Colaborador.objects.create(
            nome='Candidato Admissao',
            cpf='707.707.707-70',
            email='cand@example.com',
            cargo='Pedreiro',
            status=Colaborador.Status.EM_ADMISSAO,
            etapa_admissao=2,
            requisicao_aprovada_gestor=True,
            rg='12.345.678-9',
            data_nascimento=date(1992, 5, 10),
            endereco='Rua A, 100',
            dados_bancarios='Banco 123',
            escolaridade='Ensino médio completo',
            tamanho_camisa='M',
            tamanho_bota='40',
        )
        self.colab.gerar_token_portal(dias=30)
        self.doc_rejeitado = DocumentoColaborador.objects.create(
            colaborador=self.colab,
            tipo=self.tipo_rejeitado,
            status=DocumentoColaborador.Status.FALTANDO,
            observacao='Foto ilegível',
            coleta_solicitada=True,
        )
        self.doc_faltando = DocumentoColaborador.objects.create(
            colaborador=self.colab,
            tipo=self.tipo_faltando,
            status=DocumentoColaborador.Status.FALTANDO,
        )
        DocumentoColaborador.objects.create(
            colaborador=self.colab,
            tipo=self.tipo_ok,
            status=DocumentoColaborador.Status.RECEBIDO,
        )

    def test_rejeicao_mantem_outros_documentos_pendentes_visiveis(self):
        from recursos_humanos.services.documentos import documentos_para_exibicao_portal

        visiveis = documentos_para_exibicao_portal(self.colab)
        nomes = {doc.tipo.nome for doc in visiveis}
        self.assertIn('RG Rejeitado', nomes)
        self.assertIn('ASO Faltando', nomes)
        self.assertNotIn('CPF OK', nomes)

    def test_portal_html_mostra_docs_pendentes_apos_rejeicao(self):
        _portal_autenticar_sessao(self.client, self.colab.token_portal)
        url = reverse('recursos_humanos:portal', args=[self.colab.token_portal])
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'RG Rejeitado')
        self.assertContains(resp, 'ASO Faltando')
        self.assertNotContains(resp, 'CPF OK')

    def test_dados_pessoais_visiveis_em_modo_restrito_admissao(self):
        from recursos_humanos.services.documentos import dados_visivel_no_portal

        self.assertTrue(dados_visivel_no_portal(self.colab))
        _portal_autenticar_sessao(self.client, self.colab.token_portal)
        url = reverse('recursos_humanos:portal', args=[self.colab.token_portal])
        resp = self.client.get(url)
        self.assertContains(resp, 'Seus dados pessoais')
        self.assertContains(resp, '12.345.678-9')


class PortalTokenSegurancaTests(TestCase):
    def setUp(self):
        grupo, _ = Group.objects.get_or_create(name=GRUPOS.RECURSOS_HUMANOS)
        self.user = User.objects.create_user('rh_portal_token', password='test')
        self.user.groups.add(grupo)
        self.tipo = TipoDocumento.objects.create(nome='RG Token', ordem=1, obrigatorio=True)
        self.colab = Colaborador.objects.create(
            nome='Token Portal',
            cpf='919.919.919-91',
            cargo='Pedreiro',
            email='token@example.com',
            telefone='81991919191',
            status=Colaborador.Status.EM_ADMISSAO,
            etapa_admissao=2,
            requisicao_aprovada_gestor=True,
            rg='123',
            data_nascimento=timezone.localdate().replace(year=1990),
            endereco='Rua A',
            dados_bancarios='Banco',
            escolaridade='Médio',
            tamanho_camisa='M',
            tamanho_bota='40',
        )
        self.colab.gerar_token_portal()
        self.token_antigo = self.colab.token_portal
        self.doc = DocumentoColaborador.objects.create(
            colaborador=self.colab,
            tipo=self.tipo,
            status=DocumentoColaborador.Status.FALTANDO,
        )

    @override_settings(
        EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
        RH_ENVIO_PORTAL_CANDIDATO_ATIVO=True,
    )
    def test_solicitar_pendencias_mantem_token_dentro_do_prazo(self):
        import re

        from django.core import mail
        from recursos_humanos.services.admissao_actions import solicitar_pendencias_colaborador
        from recursos_humanos.services.portal_auth import verificar_pin_portal

        ok, _ = solicitar_pendencias_colaborador(self.colab, self.user)
        self.assertTrue(ok)
        self.colab.refresh_from_db()
        self.assertEqual(self.colab.token_portal, self.token_antigo)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('Código de acesso ao portal:', mail.outbox[0].body)
        match = re.search(r'Código de acesso ao portal: (\d{6})', mail.outbox[0].body)
        self.assertIsNotNone(match)
        self.assertTrue(verificar_pin_portal(self.colab, match.group(1)))

        _portal_autenticar_sessao(self.client, self.token_antigo)
        resp = self.client.get(reverse('recursos_humanos:portal', args=[self.token_antigo]))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Token Portal')

    def test_solicitar_pendencias_renova_token_expirado(self):
        from datetime import timedelta

        from recursos_humanos.services.admissao_actions import solicitar_pendencias_colaborador

        self.colab.token_portal_expira = timezone.now() - timedelta(hours=1)
        self.colab.save(update_fields=['token_portal_expira'])

        ok, _ = solicitar_pendencias_colaborador(self.colab, self.user)
        self.assertTrue(ok)
        self.colab.refresh_from_db()
        self.assertNotEqual(self.colab.token_portal, self.token_antigo)

        resp_antigo = self.client.get(reverse('recursos_humanos:portal', args=[self.token_antigo]))
        self.assertEqual(resp_antigo.status_code, 200)
        self.assertContains(resp_antigo, 'não é mais válido')

        _portal_autenticar_sessao(self.client, self.colab.token_portal)
        resp_novo = self.client.get(reverse('recursos_humanos:portal', args=[self.colab.token_portal]))
        self.assertEqual(resp_novo.status_code, 200)
        self.assertContains(resp_novo, 'Token Portal')

    def test_portal_modo_confirmacao_quando_nada_pendente_em_modo_restrito(self):
        from recursos_humanos.services.admissao_actions import solicitar_pendencias_colaborador

        self.doc.status = DocumentoColaborador.Status.RECEBIDO
        self.doc.save(update_fields=['status'])
        solicitar_pendencias_colaborador(self.colab, self.user)
        self.colab.refresh_from_db()

        _portal_autenticar_sessao(self.client, self.colab.token_portal)
        resp = self.client.get(reverse('recursos_humanos:portal', args=[self.colab.token_portal]))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Envio concluído por enquanto')
        self.assertNotContains(resp, 'enctype="multipart/form-data"')

    def test_primeiro_acesso_com_pendencias_nao_entra_em_confirmacao(self):
        _portal_autenticar_sessao(self.client, self.colab.token_portal)
        resp = self.client.get(reverse('recursos_humanos:portal', args=[self.colab.token_portal]))
        self.assertEqual(resp.status_code, 200)
        self.assertNotContains(resp, 'Envio concluído por enquanto')
        self.assertContains(resp, 'enctype="multipart/form-data"')


class PortalNotificacoesTests(TestCase):
    def test_whatsapp_pendencias_inclui_lista(self):
        from recursos_humanos.services.notificacoes import _montar_texto_whatsapp_portal

        pendencias = [
            {'tipo': 'dado', 'label': 'RG', 'detalhe': ''},
            {'tipo': 'documento', 'label': 'CNH', 'detalhe': 'não enviado'},
        ]
        msg = _montar_texto_whatsapp_portal(
            'Maria',
            'https://exemplo/rh/portal/token/',
            modo='pendencias',
            pendencias_coleta=pendencias,
        )
        self.assertIn('RG', msg)
        self.assertIn('CNH', msg)
        self.assertIn('não enviado', msg)

    def test_whatsapp_inclui_pin_quando_informado(self):
        from recursos_humanos.services.notificacoes import _montar_texto_whatsapp_portal

        msg = _montar_texto_whatsapp_portal(
            'Maria',
            'https://exemplo/rh/portal/token/',
            modo='inicial',
            pendencias_coleta=[{'tipo': 'documento', 'label': 'RG', 'detalhe': ''}],
            portal_pin='123456',
        )
        self.assertIn('123456', msg)
        self.assertIn('Código de acesso', msg)


class PortalPinTests(TestCase):
    def setUp(self):
        self.colab = Colaborador.objects.create(
            nome='Pin Portal',
            cpf='515.515.515-51',
            email='pin@example.com',
            cargo='Pedreiro',
            status=Colaborador.Status.EM_ADMISSAO,
            etapa_admissao=2,
            requisicao_aprovada_gestor=True,
        )
        self.token, self.pin = self.colab.gerar_token_portal(dias=30)
        TipoDocumento.objects.create(nome='RG Pin', ordem=1, obrigatorio=True)
        DocumentoColaborador.objects.create(
            colaborador=self.colab,
            tipo=TipoDocumento.objects.get(nome='RG Pin'),
            status=DocumentoColaborador.Status.FALTANDO,
        )

    def test_portal_exige_pin_antes_do_formulario(self):
        url = reverse('recursos_humanos:portal', args=[self.token])
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Código de acesso')
        self.assertNotContains(resp, 'enctype="multipart/form-data"')

    def test_portal_pin_correto_libera_formulario(self):
        url = reverse('recursos_humanos:portal', args=[self.token])
        resp = _portal_autenticar_pin(self.client, self.colab, self.pin)
        self.assertEqual(resp.status_code, 302)
        resp = self.client.get(url)
        self.assertContains(resp, 'enctype="multipart/form-data"')

    def test_portal_pin_incorreto_mantem_bloqueio(self):
        url = reverse('recursos_humanos:portal', args=[self.token])
        resp = self.client.post(url, {
            'acao': 'autenticar_portal',
            'portal_pin': '000000',
            'declaracao_identidade': 'on',
        })
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Código de acesso incorreto')
        self.assertNotContains(resp, 'enctype="multipart/form-data"')

    def test_portal_pin_expira_apos_10_minutos(self):
        url = reverse('recursos_humanos:portal', args=[self.token])
        _portal_autenticar_pin(self.client, self.colab, self.pin)
        session = self.client.session
        session['rh_portal_auth'] = {
            self.token: (timezone.now() - timedelta(minutes=11)).isoformat(),
        }
        session.save()
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Código de acesso')
        self.assertContains(resp, '10 minutos')
        self.assertNotContains(resp, 'enctype="multipart/form-data"')

    def test_portal_pin_valido_dentro_de_10_minutos(self):
        url = reverse('recursos_humanos:portal', args=[self.token])
        _portal_autenticar_pin(self.client, self.colab, self.pin)
        session = self.client.session
        session['rh_portal_auth'] = {
            self.token: (timezone.now() - timedelta(minutes=9)).isoformat(),
        }
        session.save()
        resp = self.client.get(url)
        self.assertContains(resp, 'enctype="multipart/form-data"')

    def test_portal_envio_documento_com_validade_exige_data_emissao(self):
        from django.core.files.uploadedfile import SimpleUploadedFile

        tipo_aso = TipoDocumento.objects.create(
            nome='ASO Portal',
            ordem=2,
            obrigatorio=True,
            tem_validade=True,
            dias_validade=365,
        )
        doc = DocumentoColaborador.objects.create(
            colaborador=self.colab,
            tipo=tipo_aso,
            status=DocumentoColaborador.Status.FALTANDO,
        )
        _portal_autenticar_pin(self.client, self.colab, self.pin)
        url = reverse('recursos_humanos:portal', args=[self.token])
        arquivo = SimpleUploadedFile('aso.pdf', b'%PDF ok', content_type='application/pdf')
        resp = self.client.post(url, {
            'acao': 'submeter_portal',
            f'doc_{doc.pk}': arquivo,
        })
        self.assertEqual(resp.status_code, 200)
        doc.refresh_from_db()
        self.assertFalse(doc.arquivo)

        resp = self.client.post(url, {
            'acao': 'submeter_portal',
            f'doc_{doc.pk}': SimpleUploadedFile('aso.pdf', b'%PDF ok', content_type='application/pdf'),
            f'doc_emissao_{doc.pk}': '2026-01-15',
        })
        self.assertEqual(resp.status_code, 302)
        doc.refresh_from_db()
        self.assertTrue(doc.arquivo)
        self.assertEqual(str(doc.data_emissao), '2026-01-15')
        self.assertIsNotNone(doc.vencimento)

    @override_settings(
        EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
        RH_ENVIO_PORTAL_CANDIDATO_ATIVO=True,
    )
    def test_email_admissao_inclui_pin(self):
        from django.core import mail
        from recursos_humanos.services.notificacoes import enviar_link_portal_email

        enviar_link_portal_email(
            self.colab.email,
            self.colab.nome,
            self.token,
            primeiro_acesso=True,
            pendencias_coleta=[{'tipo': 'documento', 'label': 'RG Pin', 'detalhe': ''}],
            portal_pin=self.pin,
        )
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn(self.pin, mail.outbox[0].body)


class PrazoContratoEncerrarTests(TestCase):
    def setUp(self):
        grupo, _ = Group.objects.get_or_create(name=GRUPOS.RECURSOS_HUMANOS)
        self.user = User.objects.create_user('rh_prazo', password='test')
        self.user.groups.add(grupo)
        self.colab = Colaborador.objects.create(
            nome='Felipe Prazo',
            cpf='808.808.808-80',
            cargo='Engenheiro',
            status=Colaborador.Status.ATIVO,
        )
        from recursos_humanos.models import AdmissaoHistorico, PrazoContrato

        self.PrazoContrato = PrazoContrato
        self.AdmissaoHistorico = AdmissaoHistorico
        hoje = timezone.localdate()
        self.prazo = PrazoContrato.objects.create(
            colaborador=self.colab,
            tipo=PrazoContrato.Tipo.DETERMINADO,
            data_inicio=hoje,
            data_fim=hoje + timedelta(days=365),
            status=PrazoContrato.Status.ATIVO,
        )
        self.url_decisao = reverse(
            'recursos_humanos:prazo_contrato_decisao',
            kwargs={'pk': self.prazo.pk},
        )
        self.url_reativar = reverse(
            'recursos_humanos:prazo_contrato_reativar',
            kwargs={'pk': self.prazo.pk},
        )
        self.url_json = reverse(
            'recursos_humanos:colaborador_json',
            kwargs={'pk': self.colab.pk},
        )

    def _post_decisao(self, **data):
        self.client.force_login(self.user)
        payload = {'acao': 'encerrar', **data}
        return self.client.post(
            self.url_decisao,
            payload,
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )

    def test_encerrar_sem_motivo_retorna_erro(self):
        resp = self._post_decisao(motivo='')
        self.assertEqual(resp.status_code, 400)
        self.prazo.refresh_from_db()
        self.colab.refresh_from_db()
        self.assertEqual(self.prazo.status, self.PrazoContrato.Status.ATIVO)
        self.assertEqual(self.colab.status, Colaborador.Status.ATIVO)

    def test_encerrar_com_motivo_desliga_e_registra_historico(self):
        motivo = 'Fim do projeto contratado'
        resp = self._post_decisao(motivo=motivo)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data['ok'])

        self.prazo.refresh_from_db()
        self.colab.refresh_from_db()
        self.assertEqual(self.prazo.status, self.PrazoContrato.Status.ENCERRADO)
        self.assertEqual(self.prazo.observacoes, motivo)
        self.assertEqual(self.colab.status, Colaborador.Status.DESLIGADO)

        historico = self.AdmissaoHistorico.objects.filter(colaborador=self.colab)
        self.assertEqual(historico.count(), 1)
        self.assertIn('encerrado', historico.first().descricao.lower())
        self.assertIn('desligado', historico.first().descricao.lower())
        self.assertIn(motivo, historico.first().descricao)

    def test_perfil_json_prazo_ativo_nao_exibe_reativar(self):
        self.client.force_login(self.user)
        resp = self.client.get(self.url_json)
        self.assertEqual(resp.status_code, 200)
        payload = resp.json()['prazo_contrato']
        self.assertFalse(payload['encerrado'])
        self.assertFalse(payload['pode_reativar'])
        self.assertIsNone(payload['url_reativar'])
        self.assertTrue(payload['pode_decidir'])

    def test_perfil_json_exibe_prazo_convertido(self):
        from recursos_humanos.services.prazo_contrato import executar_acao_prazo

        executar_acao_prazo(self.prazo, 'converter', self.user)
        self.client.force_login(self.user)
        resp = self.client.get(self.url_json)
        self.assertEqual(resp.status_code, 200)
        payload = resp.json()['prazo_contrato']
        self.assertTrue(payload['convertido'])
        self.assertEqual(payload['status'], 'convertido')
        self.assertFalse(payload['pode_decidir'])
        self.assertFalse(payload['pode_reativar'])
        self.assertFalse(payload['exibir_decidir'])
        self.assertFalse(payload['exibir_reativar'])
        self.assertEqual(payload['data_fim'], 'Indeterminado')
        self.assertTrue(payload['data_fim_indeterminado'])

    def test_decisao_json_rejeita_prazo_convertido(self):
        from recursos_humanos.services.prazo_contrato import executar_acao_prazo

        executar_acao_prazo(self.prazo, 'converter', self.user)
        self.client.force_login(self.user)
        url = reverse('recursos_humanos:prazo_contrato_decisao_json', args=[self.prazo.pk])
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 404)

    def test_perfil_json_exibe_prazo_encerrado_com_motivo(self):
        from recursos_humanos.services.prazo_contrato import executar_acao_prazo

        executar_acao_prazo(
            self.prazo,
            'encerrar',
            self.user,
            motivo='Motivo de teste para encerramento',
        )
        self.client.force_login(self.user)
        resp = self.client.get(self.url_json)
        self.assertEqual(resp.status_code, 200)
        payload = resp.json()
        self.assertTrue(payload['prazo_contrato']['encerrado'])
        self.assertEqual(
            payload['prazo_contrato']['motivo_encerramento'],
            'Motivo de teste para encerramento',
        )
        self.assertFalse(payload['prazo_contrato']['pode_decidir'])
        self.assertTrue(payload['prazo_contrato']['pode_reativar'])
        self.assertIsNotNone(payload['prazo_contrato']['url_reativar'])

    def test_renovar_mantem_prazo_ativo_no_perfil(self):
        from recursos_humanos.services.prazo_contrato import executar_acao_prazo

        nova_fim = timezone.localdate() + timedelta(days=400)
        ok, _ = executar_acao_prazo(
            self.prazo,
            'renovar',
            self.user,
            nova_data_fim=nova_fim,
        )
        self.assertTrue(ok)
        self.client.force_login(self.user)
        resp = self.client.get(self.url_json)
        payload = resp.json()['prazo_contrato']
        self.assertTrue(payload['pode_decidir'])
        self.assertFalse(payload.get('convertido'))
        self.assertEqual(payload['data_fim'], nova_fim.strftime('%d/%m/%Y'))

    def test_reativar_volta_contrato_e_colaborador_para_ativo(self):
        from recursos_humanos.services.prazo_contrato import executar_acao_prazo

        executar_acao_prazo(
            self.prazo,
            'encerrar',
            self.user,
            motivo='Encerramento temporário para teste',
        )
        self.client.force_login(self.user)
        resp = self.client.post(
            self.url_reativar,
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()['ok'])

        self.prazo.refresh_from_db()
        self.colab.refresh_from_db()
        self.assertEqual(self.prazo.status, self.PrazoContrato.Status.ATIVO)
        self.assertIsNone(self.prazo.finalizado_em)
        self.assertEqual(self.colab.status, Colaborador.Status.ATIVO)

        reativacao = self.AdmissaoHistorico.objects.filter(
            colaborador=self.colab,
            descricao__icontains='reativado',
        )
        self.assertEqual(reativacao.count(), 1)


class ColaboradorDesligarTests(TestCase):
    def setUp(self):
        grupo, _ = Group.objects.get_or_create(name=GRUPOS.RECURSOS_HUMANOS)
        self.user = User.objects.create_user('rh_deslig', password='test')
        self.user.groups.add(grupo)
        self.colab = Colaborador.objects.create(
            nome='Desligar Teste',
            cpf='909.909.909-90',
            cargo='Auxiliar',
            status=Colaborador.Status.ATIVO,
        )
        self.url = reverse(
            'recursos_humanos:colaborador_desligar',
            kwargs={'pk': self.colab.pk},
        )

    def test_desligar_com_motivo_registra_historico(self):
        from recursos_humanos.models import AdmissaoHistorico

        self.client.force_login(self.user)
        resp = self.client.post(
            self.url,
            {
                'data_desligamento': timezone.localdate().isoformat(),
                'motivo': 'Pedido de demissão do colaborador',
            },
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        self.assertEqual(resp.status_code, 200)
        self.colab.refresh_from_db()
        self.assertEqual(self.colab.status, Colaborador.Status.DESLIGADO)
        self.assertEqual(AdmissaoHistorico.objects.filter(colaborador=self.colab).count(), 1)


class PapeisFluxoTests(TestCase):
    def setUp(self):
        grupo, _ = Group.objects.get_or_create(name=GRUPOS.RECURSOS_HUMANOS)
        self.rh = User.objects.create_user('rh_papel', password='test')
        self.rh.groups.add(grupo)
        self.outro_rh = User.objects.create_user('rh_outro', password='test')
        self.outro_rh.groups.add(grupo)
        self.obra = _criar_obra_local('Obra Papel', 'OP1')
        self.cargo_rh = CargoRH.objects.create(nome='Pintor')
        from recursos_humanos.models import PapelFluxoAdmissao
        from recursos_humanos.services.papeis_fluxo import garantir_papeis_padrao

        garantir_papeis_padrao()
        self.papel_validacao = PapelFluxoAdmissao.objects.get(
            codigo=PapelFluxoAdmissao.Codigo.VALIDACAO_FINAL,
        )
        self.papel_validacao.usuarios.set([self.rh])

    def test_tela_papeis_fluxo_carrega(self):
        self.client.force_login(self.rh)
        resp = self.client.get(reverse('recursos_humanos:papeis_fluxo'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Papéis do fluxo')
        self.assertContains(resp, 'Responsável pela admissão')
        self.assertContains(resp, 'qualquer RH pode atuar nesta etapa')
        self.assertContains(resp, 'rh-papel-fluxo-grid')

    def test_salvar_responsaveis_papel(self):
        self.client.force_login(self.rh)
        resp = self.client.post(reverse('recursos_humanos:papeis_fluxo'), {
            f'{self.papel_validacao.codigo}-usuarios': [str(self.rh.pk), str(self.outro_rh.pk)],
            'conferencia_docs-usuarios': [],
            'requisicao-usuarios': [],
            'contrato-usuarios': [],
        })
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(self.papel_validacao.usuarios.count(), 2)

    def test_usuario_sem_rh_nao_aprova_validacao(self):
        sem_rh = User.objects.create_user('sem_rh_validacao', password='test')
        colab = Colaborador.objects.create(
            nome='Papel Bloqueio',
            cpf='121.121.121-12',
            cargo='Servente',
            status=Colaborador.Status.EM_ADMISSAO,
            etapa_admissao=3,
        )
        colab.obras.add(self.obra)
        self.client.force_login(sem_rh)
        url = reverse('recursos_humanos:admissao_acao', args=[colab.pk])
        resp = self.client.post(url, {'acao': 'aprovar'})
        self.assertEqual(resp.status_code, 302)
        colab.refresh_from_db()
        self.assertEqual(colab.etapa_admissao, 3)

    def test_usuario_rh_aprova_validacao(self):
        colab = Colaborador.objects.create(
            nome='Papel OK',
            cpf='131.131.131-13',
            cargo='Servente',
            status=Colaborador.Status.EM_ADMISSAO,
            etapa_admissao=3,
        )
        colab.obras.add(self.obra)
        self.client.force_login(self.rh)
        url = reverse('recursos_humanos:admissao_acao', args=[colab.pk])
        resp = self.client.post(url, {'acao': 'aprovar'})
        self.assertEqual(resp.status_code, 302)
        colab.refresh_from_db()
        self.assertEqual(colab.etapa_admissao, 4)

    def test_colaborador_ativo_nao_restringe_aprovacao_documento(self):
        from django.core.files.uploadedfile import SimpleUploadedFile

        from recursos_humanos.models import PapelFluxoAdmissao
        from recursos_humanos.services.admissao_actions import aprovar_documento_arquivo

        papel_conf = PapelFluxoAdmissao.objects.get(
            codigo=PapelFluxoAdmissao.Codigo.CONFERENCIA_DOCS,
        )
        papel_conf.usuarios.set([self.rh])

        colab = Colaborador.objects.create(
            nome='Ativo Docs',
            cpf='141.141.141-14',
            cargo='Pedreiro',
            status=Colaborador.Status.ATIVO,
        )
        tipo = TipoDocumento.objects.create(nome='Doc Ativo', ordem=99)
        doc = DocumentoColaborador.objects.create(
            colaborador=colab,
            tipo=tipo,
            status=DocumentoColaborador.Status.PENDENTE,
        )
        doc.arquivo.save('aso.pdf', SimpleUploadedFile('aso.pdf', b'pdf'), save=True)

        ok, _ = aprovar_documento_arquivo(doc, self.outro_rh)
        self.assertTrue(ok)


class FluxoLacunasCorrigidasTests(TestCase):
    def setUp(self):
        grupo, _ = Group.objects.get_or_create(name=GRUPOS.RECURSOS_HUMANOS)
        self.rh = User.objects.create_user('rh_lacuna', password='test')
        self.rh.groups.add(grupo)
        self.obra = _criar_obra_local('Obra Lacuna', 'OL1')
        self.tipo = TipoDocumento.objects.create(
            nome='ASO Lacuna', ordem=1, obrigatorio=True, tem_validade=True, dias_validade=365,
        )

    def test_doc_vencido_impede_avancar_etapa(self):
        colab = Colaborador.objects.create(
            nome='Vencido Avançar',
            cpf='151.151.151-15',
            cargo='Pedreiro',
            status=Colaborador.Status.EM_ADMISSAO,
            etapa_admissao=2,
            requisicao_aprovada_gestor=True,
        )
        ontem = timezone.localdate() - timedelta(days=1)
        DocumentoColaborador.objects.create(
            colaborador=colab,
            tipo=self.tipo,
            status=DocumentoColaborador.Status.RECEBIDO,
            vencimento=ontem,
        )
        self.client.force_login(self.rh)
        url = reverse('recursos_humanos:admissao_acao', args=[colab.pk])
        resp = self.client.post(url, {'acao': 'avancar'})
        self.assertEqual(resp.status_code, 302)
        colab.refresh_from_db()
        self.assertEqual(colab.etapa_admissao, 2)

    def test_concluir_exige_data_admissao_oficial(self):
        colab = Colaborador.objects.create(
            nome='Data Admissao Obrig',
            cpf='161.161.161-16',
            cargo='Pedreiro',
            status=Colaborador.Status.EM_ADMISSAO,
            etapa_admissao=4,
        )
        ContratoAdmissao.objects.create(
            colaborador=colab,
            status=ContratoAdmissao.Status.CONCLUIDO,
            concluido_em=timezone.now(),
        )
        self.client.force_login(self.rh)
        url = reverse('recursos_humanos:admissao_acao', args=[colab.pk])
        resp = self.client.post(url, {'acao': 'concluir'})
        self.assertEqual(resp.status_code, 302)
        colab.refresh_from_db()
        self.assertEqual(colab.etapa_admissao, 4)

        contrato = colab.contrato_admissao
        contrato.data_admissao_oficial = timezone.localdate()
        contrato.save(update_fields=['data_admissao_oficial'])
        from recursos_humanos.services.admissao_actions import registrar_historico

        registrar_historico(
            colab, 4, 'Contrato enviado para assinatura no ZapSign', 'Teste',
        )
        resp = self.client.post(url, {'acao': 'concluir'})
        colab.refresh_from_db()
        self.assertEqual(colab.status, Colaborador.Status.ATIVO)
        self.assertEqual(colab.etapa_admissao, 5)

    def test_portal_bloqueado_apos_validacao_sem_pendencia(self):
        colab = Colaborador.objects.create(
            nome='Portal Bloq',
            cpf='171.171.171-17',
            cargo='Pedreiro',
            status=Colaborador.Status.EM_ADMISSAO,
            etapa_admissao=3,
            requisicao_aprovada_gestor=True,
        )
        colab.gerar_token_portal(dias=30)
        DocumentoColaborador.objects.create(
            colaborador=colab,
            tipo=self.tipo,
            status=DocumentoColaborador.Status.RECEBIDO,
        )
        _portal_autenticar_sessao(self.client, colab.token_portal)
        url = reverse('recursos_humanos:portal_upload', args=[colab.token_portal, colab.documentos.first().pk])
        from django.core.files.uploadedfile import SimpleUploadedFile

        self.client.post(url, {
            'arquivo': SimpleUploadedFile('novo.pdf', b'pdf', content_type='application/pdf'),
        })
        colab.documentos.first().refresh_from_db()
        self.assertEqual(colab.documentos.first().status, DocumentoColaborador.Status.RECEBIDO)

    def test_devolver_notifica_papel_conferencia(self):
        from core.models import Notification
        from recursos_humanos.models import PapelFluxoAdmissao
        from recursos_humanos.services.papeis_fluxo import garantir_papeis_padrao

        garantir_papeis_padrao()
        papel = PapelFluxoAdmissao.objects.get(codigo=PapelFluxoAdmissao.Codigo.CONFERENCIA_DOCS)
        papel.usuarios.set([self.rh])

        colab = Colaborador.objects.create(
            nome='Devolver Notif',
            cpf='181.181.181-18',
            cargo='Pedreiro',
            status=Colaborador.Status.EM_ADMISSAO,
            etapa_admissao=3,
            requisicao_criada_por=self.rh,
        )
        self.client.force_login(self.rh)
        url = reverse('recursos_humanos:admissao_acao', args=[colab.pk])
        self.client.post(url, {'acao': 'devolver', 'motivo': 'Falta comprovante'})
        self.assertTrue(
            Notification.objects.filter(
                user=self.rh,
                notification_type='rh_devolucao_docs',
            ).exists()
        )

    def test_qualquer_rh_pode_conferir_documento_na_admissao(self):
        from recursos_humanos.models import PapelFluxoAdmissao
        from recursos_humanos.services.papeis_fluxo import garantir_papeis_padrao

        garantir_papeis_padrao()
        outro = User.objects.create_user('rh_sem_papel', password='test')
        outro.groups.add(Group.objects.get(name=GRUPOS.RECURSOS_HUMANOS))
        papel = PapelFluxoAdmissao.objects.get(codigo=PapelFluxoAdmissao.Codigo.CONFERENCIA_DOCS)
        papel.usuarios.set([self.rh])

        colab = Colaborador.objects.create(
            nome='Pend Etapa 3',
            cpf='191.191.191-19',
            cargo='Pedreiro',
            status=Colaborador.Status.EM_ADMISSAO,
            etapa_admissao=3,
            requisicao_aprovada_gestor=True,
            requisicao_criada_por=self.rh,
        )
        doc = DocumentoColaborador.objects.create(
            colaborador=colab,
            tipo=self.tipo,
            status=DocumentoColaborador.Status.PENDENTE,
        )
        from django.core.files.uploadedfile import SimpleUploadedFile

        doc.arquivo.save('x.pdf', SimpleUploadedFile('x.pdf', b'x'), save=True)
        self.client.force_login(outro)
        url = reverse('recursos_humanos:documento_aprovar', args=[doc.pk])
        resp = self.client.post(url, {
            'next': reverse('recursos_humanos:admissao'),
            'data_emissao': timezone.localdate().isoformat(),
        })
        self.assertEqual(resp.status_code, 302)
        doc.refresh_from_db()
        self.assertEqual(doc.status, DocumentoColaborador.Status.RECEBIDO)

    def test_documento_rejeitar_com_observacao(self):
        from django.core.files.uploadedfile import SimpleUploadedFile

        colab = Colaborador.objects.create(
            nome='Rejeitar Doc',
            cpf='201.201.201-20',
            cargo='Pedreiro',
            status=Colaborador.Status.EM_ADMISSAO,
            etapa_admissao=2,
            requisicao_aprovada_gestor=True,
        )
        doc = DocumentoColaborador.objects.create(
            colaborador=colab,
            tipo=self.tipo,
            status=DocumentoColaborador.Status.PENDENTE,
        )
        doc.arquivo.save('rg.pdf', SimpleUploadedFile('rg.pdf', b'pdf'), save=True)
        self.client.force_login(self.rh)
        url = reverse('recursos_humanos:documento_rejeitar', args=[doc.pk])
        resp = self.client.post(url, {
            'observacao': 'Foto ilegível, envie novamente.',
            'next': f'{reverse("recursos_humanos:admissao")}?id={colab.pk}&ver_etapa=2',
        })
        self.assertEqual(resp.status_code, 302)
        doc.refresh_from_db()
        self.assertEqual(doc.status, DocumentoColaborador.Status.FALTANDO)
        self.assertEqual(doc.observacao, 'Foto ilegível, envie novamente.')
        self.assertFalse(doc.arquivo)

    def test_documento_aprovar_ajax_retorna_json(self):
        from django.core.files.uploadedfile import SimpleUploadedFile

        colab = Colaborador.objects.create(
            nome='Ajax Aprovar',
            cpf='211.211.211-21',
            cargo='Pedreiro',
            status=Colaborador.Status.EM_ADMISSAO,
            etapa_admissao=2,
            requisicao_aprovada_gestor=True,
        )
        doc = DocumentoColaborador.objects.create(
            colaborador=colab,
            tipo=self.tipo,
            status=DocumentoColaborador.Status.PENDENTE,
        )
        doc.arquivo.save('doc.pdf', SimpleUploadedFile('doc.pdf', b'pdf'), save=True)
        self.client.force_login(self.rh)
        url = reverse('recursos_humanos:documento_aprovar', args=[doc.pk])
        resp = self.client.post(
            url,
            {
                'next': f'{reverse("recursos_humanos:admissao")}?id={colab.pk}&ver_etapa=2',
                'data_emissao': timezone.localdate().isoformat(),
            },
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data['ok'])
        self.assertIn('doc', data)
        self.assertEqual(data['doc']['doc_id'], doc.pk)
        self.assertEqual(data['doc']['status'], 'ok')
        doc.refresh_from_db()
        self.assertEqual(doc.status, DocumentoColaborador.Status.RECEBIDO)

    def test_documento_upload_ajax_retorna_json(self):
        from django.core.files.uploadedfile import SimpleUploadedFile

        colab = Colaborador.objects.create(
            nome='Ajax Upload',
            cpf='231.231.231-31',
            cargo='Pedreiro',
            status=Colaborador.Status.EM_ADMISSAO,
            etapa_admissao=2,
            requisicao_aprovada_gestor=True,
        )
        doc = DocumentoColaborador.objects.create(
            colaborador=colab,
            tipo=self.tipo,
            status=DocumentoColaborador.Status.FALTANDO,
        )
        self.client.force_login(self.rh)
        url = reverse('recursos_humanos:documento_upload', args=[doc.pk])
        resp = self.client.post(
            url,
            {
                'next': f'{reverse("recursos_humanos:admissao")}?id={colab.pk}&ver_etapa=2',
                'data_emissao': timezone.localdate().isoformat(),
                'arquivo': SimpleUploadedFile('aso.pdf', b'pdf', content_type='application/pdf'),
            },
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data['ok'])
        self.assertIn('doc', data)
        self.assertEqual(data['doc']['doc_id'], doc.pk)
        self.assertEqual(data['doc']['status'], 'ok')
        self.assertTrue(data['doc']['tem_arquivo'])
        doc.refresh_from_db()
        self.assertEqual(doc.status, DocumentoColaborador.Status.RECEBIDO)

    def test_documento_rejeitar_ajax_retorna_json(self):
        from django.core.files.uploadedfile import SimpleUploadedFile

        colab = Colaborador.objects.create(
            nome='Ajax Rejeitar',
            cpf='221.221.221-22',
            cargo='Pedreiro',
            status=Colaborador.Status.EM_ADMISSAO,
            etapa_admissao=2,
            requisicao_aprovada_gestor=True,
        )
        doc = DocumentoColaborador.objects.create(
            colaborador=colab,
            tipo=self.tipo,
            status=DocumentoColaborador.Status.PENDENTE,
        )
        doc.arquivo.save('rg.pdf', SimpleUploadedFile('rg.pdf', b'pdf'), save=True)
        self.client.force_login(self.rh)
        url = reverse('recursos_humanos:documento_rejeitar', args=[doc.pk])
        resp = self.client.post(
            url,
            {
                'observacao': 'Documento cortado.',
                'next': f'{reverse("recursos_humanos:admissao")}?id={colab.pk}&ver_etapa=2',
            },
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data['ok'])
        self.assertEqual(data['doc']['status'], 'missing')
        doc.refresh_from_db()
        self.assertEqual(doc.status, DocumentoColaborador.Status.FALTANDO)


class StatusColaboradorExibicaoTests(TestCase):
    def test_admissao_etapa_2_mostra_conferencia_docs(self):
        from recursos_humanos.services.status_colaborador import status_exibicao_colaborador

        colab = Colaborador.objects.create(
            nome='Candidato',
            cpf='151.151.151-15',
            cargo='Servente',
            status=Colaborador.Status.EM_ADMISSAO,
            etapa_admissao=2,
            requisicao_aprovada_gestor=True,
        )
        ex = status_exibicao_colaborador(colab)
        self.assertEqual(ex.label, 'Conferência de docs')
        self.assertEqual(ex.tone, 'adm-docs')

    def test_admissao_requisicao_pendente_legado(self):
        from recursos_humanos.services.status_colaborador import status_exibicao_colaborador

        colab = Colaborador.objects.create(
            nome='Novo',
            cpf='161.161.161-16',
            cargo='Auxiliar',
            status=Colaborador.Status.EM_ADMISSAO,
            etapa_admissao=1,
        )
        ex = status_exibicao_colaborador(colab)
        self.assertEqual(ex.label, 'Requisição pendente')
        self.assertEqual(ex.tone, 'adm-requisicao')

    def test_contratado_com_docs_pendentes(self):
        from recursos_humanos.services.status_colaborador import status_exibicao_colaborador

        colab = Colaborador.objects.create(
            nome='Contratado',
            cpf='171.171.171-17',
            cargo='Pedreiro',
            status=Colaborador.Status.ATIVO,
        )
        ex = status_exibicao_colaborador(colab, docs_recebidos=9, docs_total=12)
        self.assertEqual(ex.label, 'Em exercício')
        self.assertIn('9/12', ex.hint)
        self.assertIn('pendente', ex.hint.lower())
        self.assertEqual(ex.tone, 'contratado-pendente')

    def test_desligado_mostra_vinculo_encerrado(self):
        from recursos_humanos.services.status_colaborador import status_exibicao_colaborador

        colab = Colaborador.objects.create(
            nome='Ex',
            cpf='181.181.181-18',
            cargo='Engenheira',
            status=Colaborador.Status.DESLIGADO,
        )
        ex = status_exibicao_colaborador(colab)
        self.assertEqual(ex.label, 'Desligado')
        self.assertEqual(ex.hint, 'Vínculo encerrado')


class ListaColaboradoresPendenciasTests(TestCase):
    def test_lista_dois_vencimentos_ordenados(self):
        from recursos_humanos.services.lista_colaboradores import listar_pendencias_colaborador

        hoje = timezone.localdate()
        colab = Colaborador.objects.create(
            nome='Marcos',
            cpf='191.191.191-19',
            cargo='Mestre',
            status=Colaborador.Status.ATIVO,
        )
        tipo_aso = TipoDocumento.objects.create(nome='ASO', ordem=1, tem_validade=True)
        tipo_nr = TipoDocumento.objects.create(nome='NR-35', ordem=2, tem_validade=True)
        DocumentoColaborador.objects.create(
            colaborador=colab,
            tipo=tipo_aso,
            status=DocumentoColaborador.Status.RECEBIDO,
            vencimento=hoje + timedelta(days=5),
        )
        DocumentoColaborador.objects.create(
            colaborador=colab,
            tipo=tipo_nr,
            status=DocumentoColaborador.Status.RECEBIDO,
            vencimento=hoje - timedelta(days=1),
        )
        docs = list(colab.documentos.select_related('tipo'))
        pendencias = listar_pendencias_colaborador(colab, docs=docs)
        self.assertGreaterEqual(len(pendencias), 2)
        labels = [p.label for p in pendencias]
        self.assertTrue(any('NR-35' in label for label in labels))

    def test_ativo_mostra_pendencia_dossie_faltando(self):
        from recursos_humanos.services.lista_colaboradores import listar_pendencias_colaborador

        colab = Colaborador.objects.create(
            nome='Luís',
            cpf='212.212.212-21',
            cargo='Armador',
            status=Colaborador.Status.ATIVO,
        )
        tipo_rg = TipoDocumento.objects.create(nome='RG', ordem=1)
        tipo_ctps = TipoDocumento.objects.create(nome='CTPS', ordem=2)
        DocumentoColaborador.objects.create(
            colaborador=colab,
            tipo=tipo_rg,
            status=DocumentoColaborador.Status.RECEBIDO,
        )
        DocumentoColaborador.objects.create(
            colaborador=colab,
            tipo=tipo_ctps,
            status=DocumentoColaborador.Status.FALTANDO,
        )
        docs = list(colab.documentos.select_related('tipo'))
        pendencias = listar_pendencias_colaborador(colab, docs=docs)
        self.assertTrue(any('Dossiê' in p.label for p in pendencias))

    def test_admissao_mostra_docs_pendentes_com_nomes(self):
        from recursos_humanos.services.lista_colaboradores import listar_pendencias_colaborador

        colab = Colaborador.objects.create(
            nome='Fernanda',
            cpf='201.201.201-20',
            cargo='Auxiliar',
            status=Colaborador.Status.EM_ADMISSAO,
            etapa_admissao=2,
            requisicao_aprovada_gestor=True,
        )
        tipo = TipoDocumento.objects.create(nome='RG', ordem=1)
        DocumentoColaborador.objects.create(
            colaborador=colab,
            tipo=tipo,
            status=DocumentoColaborador.Status.FALTANDO,
        )
        docs = list(colab.documentos.select_related('tipo'))
        pendencias = listar_pendencias_colaborador(colab, docs=docs)
        self.assertTrue(any('falta' in p.label for p in pendencias))

    def test_resumo_documentos_em_admissao(self):
        from recursos_humanos.services.lista_colaboradores import resumo_documentos_lista

        colab = Colaborador.objects.create(
            nome='Ricardo',
            cpf='211.211.211-21',
            cargo='Servente',
            status=Colaborador.Status.EM_ADMISSAO,
            etapa_admissao=2,
        )
        t1 = TipoDocumento.objects.create(nome='CPF', ordem=1)
        t2 = TipoDocumento.objects.create(nome='CTPS', ordem=2)
        DocumentoColaborador.objects.create(
            colaborador=colab, tipo=t1, status=DocumentoColaborador.Status.RECEBIDO,
        )
        DocumentoColaborador.objects.create(
            colaborador=colab, tipo=t2, status=DocumentoColaborador.Status.FALTANDO,
        )
        docs = list(colab.documentos.select_related('tipo'))
        resumo = resumo_documentos_lista(colab, docs=docs, recebidos=1, total=2)
        self.assertEqual(resumo.fracao, '1/2')
        self.assertEqual(resumo.pendentes_count, 1)


class ContratoPdfTests(TestCase):
    def test_gerar_pdf_contrato_formato_e_conteudo(self):
        from recursos_humanos.services.contrato import gerar_pdf_contrato

        colab = Colaborador.objects.create(
            nome='Maria Contrato PDF',
            cpf='311.311.311-31',
            cargo='Engenheira Civil',
            salario='R$ 8.500,00',
            tipo_contrato='CLT',
            status=Colaborador.Status.EM_ADMISSAO,
            etapa_admissao=4,
            data_admissao=timezone.localdate(),
        )
        pdf = gerar_pdf_contrato(colab)
        self.assertTrue(pdf.startswith(b'%PDF'))
        self.assertGreater(len(pdf), 1500)

    def test_view_contrato_gerar_retorna_pdf(self):
        colab = Colaborador.objects.create(
            nome='João Contrato',
            cpf='321.321.321-32',
            cargo='Pedreiro',
            status=Colaborador.Status.EM_ADMISSAO,
            etapa_admissao=4,
        )
        grupo, _ = Group.objects.get_or_create(name=GRUPOS.RECURSOS_HUMANOS)
        user = User.objects.create_user('rh_contrato_pdf', password='test')
        user.groups.add(grupo)
        self.client.force_login(user)
        url = reverse('recursos_humanos:contrato_gerar', args=[colab.pk])
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp['Content-Type'], 'application/pdf')
        pdf_bytes = b''.join(resp.streaming_content)
        self.assertTrue(pdf_bytes.startswith(b'%PDF'))

    def test_colaborador_json_inclui_contrato_assinado(self):
        from django.core.files.base import ContentFile

        colab = Colaborador.objects.create(
            nome='Ana Contrato JSON',
            cpf='331.331.331-31',
            cargo='Analista',
            status=Colaborador.Status.ATIVO,
        )
        contrato = ContratoAdmissao.objects.create(
            colaborador=colab,
            status=ContratoAdmissao.Status.CONCLUIDO,
            concluido_em=timezone.now(),
            data_admissao_oficial=timezone.localdate(),
        )
        contrato.pdf_contrato.save(
            'contrato_assinado_teste.pdf',
            ContentFile(b'%PDF-1.4 contrato teste'),
            save=True,
        )
        grupo, _ = Group.objects.get_or_create(name=GRUPOS.RECURSOS_HUMANOS)
        user = User.objects.create_user('rh_contrato_json', password='test')
        user.groups.add(grupo)
        self.client.force_login(user)
        url = reverse('recursos_humanos:colaborador_json', args=[colab.pk])
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        contratos = [
            d for d in data['documentos']
            if d.get('es_contrato_admissao')
        ]
        self.assertEqual(len(contratos), 1)
        self.assertIn('Contrato de trabalho assinado', contratos[0]['nome'])
        self.assertTrue(contratos[0]['url_arquivo'])
