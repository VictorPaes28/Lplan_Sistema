from datetime import date, timedelta

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
        DocumentoColaborador.objects.create(
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

    def test_gestor_sem_rh_aprova_pela_tela_dedicada(self):
        gestor = User.objects.create_user('gestor_only', password='test')
        self.client.force_login(self.user)
        self.client.post(reverse('recursos_humanos:admissao_nova'), {
            'nome': 'Aprova Gestor',
            'cpf': '404.404.404-40',
            'email': 'gestor.only@example.com',
            'telefone': '81940404040',
            'cargo': 'Eletricista',
            'obra': self.obra.pk,
            'tipo_contrato': 'CLT',
            'salario': 'R$ 3.500',
            'data_inicio': timezone.localdate().isoformat(),
            'gestor_id': gestor.pk,
            'motivo': 'Nova contratação',
            'observacoes': '',
        })
        colab = Colaborador.objects.get(cpf='404.404.404-40')
        self.client.logout()
        self.client.force_login(gestor)
        url = reverse('recursos_humanos:gestor_aprovar_requisicao', args=[colab.pk])
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Aprovar requisição')
        resp = self.client.post(url, {'acao': 'aprovar_requisicao'})
        self.assertEqual(resp.status_code, 200)
        colab.refresh_from_db()
        self.assertTrue(colab.requisicao_aprovada_gestor)
        self.assertEqual(colab.etapa_admissao, 2)

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

    @override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
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
        url = reverse('recursos_humanos:portal', args=[self.colab.token_portal])
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'ASO Reenvio')


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

    @override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
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

    @override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
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
        ok, msg = enviar_lembrete_coleta_documentos(self.colab, self.user)
        self.assertFalse(ok)
        self.assertIn('pendentes', msg.lower())


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
        self.assertTrue(payload['pode_decidir'])
        self.assertFalse(payload['pode_reativar'])
        self.assertTrue(payload['exibir_decidir'])
        self.assertFalse(payload['exibir_reativar'])
        self.assertEqual(payload['data_fim'], 'Indeterminado')
        self.assertTrue(payload['data_fim_indeterminado'])

    def test_decisao_json_aceita_prazo_convertido(self):
        from recursos_humanos.services.prazo_contrato import executar_acao_prazo

        executar_acao_prazo(self.prazo, 'converter', self.user)
        self.client.force_login(self.user)
        url = reverse('recursos_humanos:prazo_contrato_decisao_json', args=[self.prazo.pk])
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['id'], self.prazo.pk)

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
