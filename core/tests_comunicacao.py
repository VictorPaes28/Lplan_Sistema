"""
Testes da camada transversal de comunicação (router + views).
"""
from django.contrib.auth.models import Group, User
from django.test import TestCase, override_settings
from django.urls import reverse

from accounts.groups import GRUPOS
from core.comunicacao_constants import (
    TIPO_GESTCONTROLL_COPIA_ADMIN,
    TIPO_GESTCONTROLL_NOVO_PEDIDO,
    TIPO_RDO_CLIENTE,
    TIPO_SISTEMA_RESET_SENHA,
)
from core.comunicacao_models import (
    LogDecisaoComunicacao,
    PadraoComunicacaoGrupo,
    PreferenciaComunicacao,
    TipoComunicacao,
)
from core.comunicacao_router import ComunicacaoPreferenciasService


def _seed_tipo_copia_admin():
    return TipoComunicacao.objects.update_or_create(
        codigo=TIPO_GESTCONTROLL_COPIA_ADMIN,
        defaults={
            'nome': 'Cópia administrativa — pedido aprovado',
            'modulo': 'gestcontroll',
            'descricao': 'Teste',
            'categoria': 'informativo',
            'criticidade': 'informativo',
            'email_padrao': True,
            'permite_usuario_desativar_email': True,
            'permite_admin_desativar_email': True,
            'permite_resumo': True,
            'obrigatorio': False,
            'ordem': 10,
        },
    )[0]


def _seed_tipo_novo_pedido():
    return TipoComunicacao.objects.update_or_create(
        codigo=TIPO_GESTCONTROLL_NOVO_PEDIDO,
        defaults={
            'nome': 'Novo pedido — aprovador',
            'modulo': 'gestcontroll',
            'descricao': 'Teste',
            'categoria': 'operacional_acao',
            'criticidade': 'operacional',
            'email_padrao': True,
            'permite_usuario_desativar_email': True,
            'permite_admin_desativar_email': True,
            'obrigatorio': False,
            'ordem': 30,
        },
    )[0]


class ComunicacaoRouterTests(TestCase):
    def setUp(self):
        self.svc = ComunicacaoPreferenciasService()
        self.tipo_copia = _seed_tipo_copia_admin()
        _seed_tipo_novo_pedido()
        self.user = User.objects.create_user(
            username='cleiton',
            email='cleiton@lplan.com.br',
            password='test-pass-1234',
        )

    def test_sem_preferencia_envia_como_hoje(self):
        d = self.svc.pode_enviar_email(
            'cleiton@lplan.com.br',
            TIPO_GESTCONTROLL_COPIA_ADMIN,
            usuario=self.user,
            registrar=False,
        )
        self.assertTrue(d.enviar)
        self.assertEqual(d.motivo, 'padrao_envio')

    def test_preferencia_usuario_desativa_copia_admin(self):
        self.svc.salvar_preferencia_usuario(
            usuario=self.user,
            tipo=self.tipo_copia,
            modo='sem_email',
            atualizado_por=self.user,
        )
        d = self.svc.pode_enviar_email(
            'cleiton@lplan.com.br',
            TIPO_GESTCONTROLL_COPIA_ADMIN,
            usuario=self.user,
            registrar=True,
        )
        self.assertFalse(d.enviar)
        self.assertEqual(d.motivo, 'preferencia_usuario_desativada')
        self.assertTrue(
            LogDecisaoComunicacao.objects.filter(
                email='cleiton@lplan.com.br',
                decisao='bloquear',
            ).exists()
        )

    def test_email_livre_desativado(self):
        self.svc.salvar_preferencia_email_livre(
            email='luiz@lplan.com.br',
            tipo=self.tipo_copia,
            email_ativo=False,
        )
        filtrados = self.svc.filtrar_destinatarios_email(
            ['luiz@lplan.com.br', 'outro@lplan.com.br'],
            TIPO_GESTCONTROLL_COPIA_ADMIN,
        )
        self.assertNotIn('luiz@lplan.com.br', filtrados)
        self.assertIn('outro@lplan.com.br', filtrados)

    def test_tipo_obrigatorio_nunca_bloqueia(self):
        d = self.svc._resolver_decisao_email(
            'user@lplan.com.br',
            TIPO_SISTEMA_RESET_SENHA,
        )
        self.assertTrue(d.enviar)
        self.assertEqual(d.motivo, 'tipo_obrigatorio')

    def test_novo_pedido_pode_ser_bloqueado_por_preferencia(self):
        self.svc.salvar_preferencia_usuario(
            usuario=self.user,
            tipo=TipoComunicacao.objects.get(codigo=TIPO_GESTCONTROLL_NOVO_PEDIDO),
            modo='sem_email',
        )
        d = self.svc.pode_enviar_email(
            'cleiton@lplan.com.br',
            TIPO_GESTCONTROLL_NOVO_PEDIDO,
            usuario=self.user,
            registrar=False,
        )
        self.assertFalse(d.enviar)

    def test_router_nao_aplicavel_retorna_todos(self):
        filtrados = self.svc.filtrar_destinatarios_email(
            ['a@x.com', 'b@x.com'],
            'gestcontroll.novo_pedido.aprovador',
        )
        self.assertEqual(filtrados, ['a@x.com', 'b@x.com'])

    def test_resumo_diario_rejeitado_no_backend(self):
        with self.assertRaises(ValueError):
            self.svc.salvar_preferencia_usuario(
                usuario=self.user,
                tipo=self.tipo_copia,
                modo='resumo',
            )

    def test_alias_interno_normalizado_para_sem_email(self):
        self.svc.salvar_preferencia_usuario(
            usuario=self.user,
            tipo=self.tipo_copia,
            modo='interno',
        )
        pref = PreferenciaComunicacao.objects.get(usuario=self.user, tipo=self.tipo_copia)
        self.assertFalse(pref.email_ativo)
        self.assertFalse(pref.resumo_ativo)

    def test_email_livre_normaliza_maiusculas_espacos(self):
        self.svc.salvar_preferencia_email_livre(
            email='  LUIZ@Lplan.COM.BR  ',
            tipo=self.tipo_copia,
            email_ativo=False,
        )
        filtrados = self.svc.filtrar_destinatarios_email(
            ['luiz@lplan.com.br'],
            TIPO_GESTCONTROLL_COPIA_ADMIN,
        )
        self.assertEqual(filtrados, [])

    def test_tipo_nunca_desligar_nao_pode_desativar_via_usuario(self):
        tipo_reset = TipoComunicacao.objects.update_or_create(
            codigo=TIPO_SISTEMA_RESET_SENHA,
            defaults={
                'nome': 'Reset',
                'modulo': 'sistema',
                'categoria': 'critico',
                'criticidade': 'critico',
                'obrigatorio': True,
                'permite_usuario_desativar_email': True,
            },
        )[0]
        with self.assertRaises(ValueError):
            self.svc.salvar_preferencia_usuario(
                usuario=self.user,
                tipo=tipo_reset,
                modo='sem_email',
            )


class ComunicacaoViewsTests(TestCase):
    def setUp(self):
        self.tipo_copia = _seed_tipo_copia_admin()
        _seed_tipo_novo_pedido()
        self.user = User.objects.create_user(
            username='comum',
            email='comum@lplan.com.br',
            password='test-pass-1234',
        )
        self.admin = User.objects.create_user(
            username='administrador',
            email='admin@lplan.com.br',
            password='test-pass-1234',
            is_superuser=True,
        )
        Group.objects.get_or_create(name=GRUPOS.ADMINISTRADOR)

    def test_usuario_acessa_proprias_preferencias(self):
        self.client.login(username='comum', password='test-pass-1234')
        r = self.client.get(reverse('perfil_comunicacao'))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Meus e-mails')

    def test_usuario_nao_acessa_admin_hub(self):
        self.client.login(username='comum', password='test-pass-1234')
        r = self.client.get(reverse('admin_comunicacao_hub'))
        self.assertEqual(r.status_code, 403)

    def test_usuario_nao_acessa_urls_admin_comunicacao(self):
        self.client.login(username='comum', password='test-pass-1234')
        for name in (
            'admin_comunicacao_hub',
            'admin_comunicacao_tipos',
            'admin_comunicacao_preferencias',
            'admin_comunicacao_decisoes',
            'admin_comunicacao_padroes_grupo',
        ):
            with self.subTest(url=name):
                self.assertEqual(self.client.get(reverse(name)).status_code, 403)

    def test_admin_acessa_hub(self):
        self.client.login(username='administrador', password='test-pass-1234')
        r = self.client.get(reverse('admin_comunicacao_hub'))
        self.assertEqual(r.status_code, 200)

    def test_usuario_salva_preferencia_desativar_copia(self):
        self.client.login(username='comum', password='test-pass-1234')
        r = self.client.post(reverse('perfil_comunicacao'), {
            'tipo_id': self.tipo_copia.pk,
        })
        self.assertEqual(r.status_code, 302)
        pref = PreferenciaComunicacao.objects.get(usuario=self.user, tipo=self.tipo_copia)
        self.assertFalse(pref.email_ativo)
        self.assertFalse(pref.resumo_ativo)

    def test_usuario_nao_altera_tipo_obrigatorio_via_post(self):
        tipo_obrig = TipoComunicacao.objects.update_or_create(
            codigo=TIPO_SISTEMA_RESET_SENHA,
            defaults={
                'nome': 'Reset',
                'modulo': 'sistema',
                'categoria': 'critico',
                'criticidade': 'critico',
                'obrigatorio': True,
                'permite_usuario_desativar_email': False,
                'ativo': True,
            },
        )[0]
        self.client.login(username='comum', password='test-pass-1234')
        r = self.client.post(reverse('perfil_comunicacao'), {
            'tipo_id': tipo_obrig.pk,
            'modo': 'sem_email',
        })
        self.assertEqual(r.status_code, 404)
        self.assertFalse(
            PreferenciaComunicacao.objects.filter(usuario=self.user, tipo=tipo_obrig).exists()
        )

    def test_usuario_nao_ativa_resumo_diario_via_post(self):
        self.client.login(username='comum', password='test-pass-1234')
        r = self.client.post(reverse('perfil_comunicacao'), {
            'tipo_id': self.tipo_copia.pk,
            'modo': 'resumo',
        })
        self.assertEqual(r.status_code, 302)
        pref = PreferenciaComunicacao.objects.filter(usuario=self.user, tipo=self.tipo_copia).first()
        self.assertTrue(pref is None or not pref.resumo_ativo)

    def test_perfil_exibe_interruptor(self):
        self.client.login(username='comum', password='test-pass-1234')
        r = self.client.get(reverse('perfil_comunicacao'))
        self.assertContains(r, 'com-switch')

    def test_admin_salva_preferencia_email_livre(self):
        self.client.login(username='administrador', password='test-pass-1234')
        r = self.client.post(reverse('admin_comunicacao_preferencias'), {
            'action': 'email_livre',
            'email': 'fixo@lplan.com.br',
            'tipo_id': self.tipo_copia.pk,
        })
        self.assertEqual(r.status_code, 302)
        self.assertTrue(
            PreferenciaComunicacao.objects.filter(
                email='fixo@lplan.com.br',
                tipo=self.tipo_copia,
                email_ativo=False,
            ).exists()
        )


class PadraoGrupoComunicacaoTests(TestCase):
    def setUp(self):
        self.svc = ComunicacaoPreferenciasService()
        self.tipo_copia = _seed_tipo_copia_admin()
        _seed_tipo_novo_pedido()
        self.grupo_admin, _ = Group.objects.get_or_create(name=GRUPOS.ADMINISTRADOR)
        self.grupo_aprov, _ = Group.objects.get_or_create(name=GRUPOS.APROVADOR)
        self.user = User.objects.create_user(
            username='admin_user',
            email='admin.user@lplan.com.br',
            password='test-pass-1234',
        )
        self.user.groups.add(self.grupo_admin)
        self.admin = User.objects.create_user(
            username='super',
            email='super@lplan.com.br',
            password='test-pass-1234',
            is_superuser=True,
        )

    def test_padrao_grupo_desativa_copia_admin_informativo(self):
        self.svc.salvar_padrao_grupo(self.grupo_admin, self.tipo_copia, 'sem_email')
        d = self.svc.pode_enviar_email(
            'admin.user@lplan.com.br',
            TIPO_GESTCONTROLL_COPIA_ADMIN,
            usuario=self.user,
            registrar=False,
        )
        self.assertFalse(d.enviar)
        self.assertEqual(d.motivo, 'padrao_grupo_desativado')
        self.assertIn('Administrador', d.detalhe)

    def test_preferencia_individual_ativa_sobre_grupo_desativado(self):
        self.svc.salvar_padrao_grupo(self.grupo_admin, self.tipo_copia, 'sem_email')
        self.svc.salvar_preferencia_usuario(
            usuario=self.user,
            tipo=self.tipo_copia,
            modo='email',
        )
        d = self.svc.pode_enviar_email(
            'admin.user@lplan.com.br',
            TIPO_GESTCONTROLL_COPIA_ADMIN,
            usuario=self.user,
            registrar=False,
        )
        self.assertTrue(d.enviar)
        self.assertEqual(d.motivo, 'preferencia_usuario_ativa_sobre_grupo')

    def test_preferencia_individual_desativa_sobre_grupo_ativo(self):
        self.svc.salvar_padrao_grupo(self.grupo_admin, self.tipo_copia, 'email')
        self.svc.salvar_preferencia_usuario(
            usuario=self.user,
            tipo=self.tipo_copia,
            modo='sem_email',
        )
        d = self.svc.pode_enviar_email(
            'admin.user@lplan.com.br',
            TIPO_GESTCONTROLL_COPIA_ADMIN,
            usuario=self.user,
            registrar=False,
        )
        self.assertFalse(d.enviar)
        self.assertEqual(d.motivo, 'preferencia_usuario_desativada_sobre_grupo')

    def test_usuario_sem_padrao_grupo_mantem_envio(self):
        PadraoComunicacaoGrupo.objects.filter(tipo=self.tipo_copia).delete()
        d = self.svc.pode_enviar_email(
            'admin.user@lplan.com.br',
            TIPO_GESTCONTROLL_COPIA_ADMIN,
            usuario=self.user,
            registrar=False,
        )
        self.assertTrue(d.enviar)
        self.assertEqual(d.motivo, 'padrao_envio')

    def test_multiplos_grupos_informativo_qualquer_bloqueio_vence(self):
        self.svc.salvar_padrao_grupo(self.grupo_aprov, self.tipo_copia, 'email')
        self.svc.salvar_padrao_grupo(self.grupo_admin, self.tipo_copia, 'sem_email')
        self.user.groups.add(self.grupo_aprov)
        d = self.svc.pode_enviar_email(
            'admin.user@lplan.com.br',
            TIPO_GESTCONTROLL_COPIA_ADMIN,
            usuario=self.user,
            registrar=False,
        )
        self.assertFalse(d.enviar)

    def test_log_decisao_grupo_motivo_legivel(self):
        self.svc.salvar_padrao_grupo(self.grupo_admin, self.tipo_copia, 'sem_email')
        self.svc.pode_enviar_email(
            'admin.user@lplan.com.br',
            TIPO_GESTCONTROLL_COPIA_ADMIN,
            usuario=self.user,
            registrar=True,
        )
        log = LogDecisaoComunicacao.objects.filter(
            email='admin.user@lplan.com.br',
            decisao='bloquear',
        ).latest('created_at')
        self.assertIn('Administrador', log.motivo)

    def test_tipo_critico_nao_altera_padrao_grupo(self):
        tipo_reset = TipoComunicacao.objects.update_or_create(
            codigo=TIPO_SISTEMA_RESET_SENHA,
            defaults={
                'nome': 'Reset',
                'modulo': 'sistema',
                'categoria': 'critico',
                'criticidade': 'critico',
                'obrigatorio': True,
                'permite_admin_desativar_email': False,
            },
        )[0]
        with self.assertRaises(ValueError):
            self.svc.salvar_padrao_grupo(self.grupo_admin, tipo_reset, 'sem_email')

    def test_tipo_nunca_desligar_router_sempre_envia(self):
        TipoComunicacao.objects.update_or_create(
            codigo=TIPO_SISTEMA_RESET_SENHA,
            defaults={
                'nome': 'Reset',
                'modulo': 'sistema',
                'categoria': 'critico',
                'criticidade': 'critico',
                'obrigatorio': True,
                'ativo': True,
            },
        )
        d = self.svc._resolver_decisao_email('x@lplan.com.br', TIPO_SISTEMA_RESET_SENHA)
        self.assertTrue(d.enviar)
        self.assertEqual(d.motivo, 'tipo_obrigatorio')

    def test_tipo_fora_router_sem_efeito_filtro(self):
        filtrados = self.svc.filtrar_destinatarios_email(
            ['a@x.com'],
            TIPO_GESTCONTROLL_NOVO_PEDIDO,
        )
        self.assertEqual(filtrados, ['a@x.com'])

    def test_rdo_cliente_fora_logica_grupo_padrao(self):
        TipoComunicacao.objects.update_or_create(
            codigo=TIPO_RDO_CLIENTE,
            defaults={
                'nome': 'RDO cliente',
                'modulo': 'rdo',
                'categoria': 'critico',
                'criticidade': 'critico',
                'obrigatorio': True,
                'ativo': True,
            },
        )
        d = self.svc._resolver_decisao_email('cliente@x.com', TIPO_RDO_CLIENTE)
        self.assertTrue(d.enviar)
        self.assertEqual(d.motivo, 'tipo_obrigatorio')

    def test_admin_acessa_padroes_grupo(self):
        self.client.login(username='super', password='test-pass-1234')
        r = self.client.get(reverse('admin_comunicacao_padroes_grupo'))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Padrões por perfil')

    def test_comum_nao_acessa_padroes_grupo(self):
        comum = User.objects.create_user('c2', 'c2@lplan.com.br', 'test-pass-1234')
        self.client.login(username='c2', password='test-pass-1234')
        r = self.client.get(reverse('admin_comunicacao_padroes_grupo'))
        self.assertEqual(r.status_code, 403)

    def test_post_novo_pedido_padrao_grupo_configuravel(self):
        tipo = _seed_tipo_novo_pedido()
        self.client.login(username='super', password='test-pass-1234')
        r = self.client.post(
            reverse('admin_comunicacao_padroes_grupo') + f'?grupo={self.grupo_admin.pk}',
            {
                'grupo_id': self.grupo_admin.pk,
                'action': 'salvar',
                'tipo_id': tipo.pk,
                'modo': 'sem_email',
            },
        )
        self.assertEqual(r.status_code, 302)
        padrao = PadraoComunicacaoGrupo.objects.get(grupo=self.grupo_admin, tipo=tipo)
        self.assertFalse(padrao.email_ativo)


@override_settings(EMAIL_HOST_USER='test@lplan.com.br', EMAIL_HOST_PASSWORD='secret')
class EmailUtilsRouterIntegrationTests(TestCase):
    """Integração piloto: filtro na thread de aprovação."""

    def setUp(self):
        from gestao_aprovacao.models import Empresa, Obra, WorkOrder

        self.tipo_copia = _seed_tipo_copia_admin()
        self.aprovador = User.objects.create_user(
            username='aprov',
            email='aprov@lplan.com.br',
            password='x',
        )
        self.solicitante = User.objects.create_user(
            username='sol',
            email='sol@lplan.com.br',
            password='x',
        )
        self.admin_copy = 'copia@lplan.com.br'
        self.empresa = Empresa.objects.create(codigo='E1', nome='Empresa Teste')
        self.obra = Obra.objects.create(
            codigo='O1',
            nome='Obra Teste',
            empresa=self.empresa,
            ativo=True,
        )
        self.workorder = WorkOrder.objects.create(
            codigo='PED-001',
            obra=self.obra,
            criado_por=self.solicitante,
            nome_credor='Fornecedor',
            tipo_solicitacao='contrato',
            status='aprovado',
        )
        ComunicacaoPreferenciasService().salvar_preferencia_email_livre(
            email=self.admin_copy,
            tipo=self.tipo_copia,
            email_ativo=False,
        )

    def test_filtrar_destinatarios_admin_bloqueado_solicitante_mantido(self):
        from gestao_aprovacao.email_utils import _normalizar_destinatarios
        from core.comunicacao_router import ComunicacaoPreferenciasService
        from core.comunicacao_constants import TIPO_GESTCONTROLL_COPIA_ADMIN

        dest_solicitante = ['sol@lplan.com.br']
        dest_admin = [self.admin_copy]
        router = ComunicacaoPreferenciasService()
        dest_admin = router.filtrar_destinatarios_email(
            dest_admin,
            TIPO_GESTCONTROLL_COPIA_ADMIN,
            contexto={'objeto_id': self.workorder.pk},
        )
        destinatarios = _normalizar_destinatarios(dest_solicitante + dest_admin)
        self.assertIn('sol@lplan.com.br', destinatarios)
        self.assertNotIn(self.admin_copy, destinatarios)

    def test_solicitante_com_pref_bloqueada_continua_recebendo(self):
        from gestao_aprovacao.email_utils import _normalizar_destinatarios
        from core.comunicacao_router import ComunicacaoPreferenciasService
        from core.comunicacao_constants import TIPO_GESTCONTROLL_COPIA_ADMIN

        ComunicacaoPreferenciasService().salvar_preferencia_usuario(
            usuario=self.solicitante,
            tipo=self.tipo_copia,
            modo='sem_email',
        )
        dest_solicitante = ['sol@lplan.com.br']
        dest_admin = ['sol@lplan.com.br', self.admin_copy]
        dest_admin = [e for e in dest_admin if e.lower() not in {e.lower() for e in dest_solicitante}]
        dest_admin = ComunicacaoPreferenciasService().filtrar_destinatarios_email(
            dest_admin,
            TIPO_GESTCONTROLL_COPIA_ADMIN,
        )
        destinatarios = _normalizar_destinatarios(dest_solicitante + dest_admin)
        self.assertIn('sol@lplan.com.br', destinatarios)
