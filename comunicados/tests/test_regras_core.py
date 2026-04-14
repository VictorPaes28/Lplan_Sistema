"""
Cobertura das regras de público, exibição, pendentes e vistas do painel.
"""
from __future__ import annotations

from datetime import date, timedelta

from django.contrib.auth.models import Group, User
from django.contrib.auth.signals import user_logged_in
from django.test import Client, RequestFactory, TestCase
from django.urls import reverse
from django.utils import timezone

from core.models import Project, ProjectMember
from gestao_aprovacao.models import Obra

from comunicados.forms import ComunicadoForm
from comunicados.metrics import get_eligible_user_ids
from comunicados.models import (
    Comunicado,
    ComunicadoVisualizacao,
    PublicoEscopoCriterios,
    PublicoRestricaoPerfil,
    StatusFinalVisualizacao,
    TipoConteudo,
    TipoExibicao,
)
from comunicados.services import listar_comunicados_pendentes


class ComunicadosPendentesFixtures(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.creator = User.objects.create_user(username='criador_com', password='x', is_staff=True)
        cls.u_plain = User.objects.create_user(username='user_plain', password='x')
        cls.u_staff = User.objects.create_user(username='user_staff', password='x', is_staff=True)
        cls.u_super = User.objects.create_user(
            username='user_super', password='x', is_staff=True, is_superuser=True
        )

        cls.g_eng, _ = Group.objects.get_or_create(name='EngTestCom')
        cls.u_plain.groups.add(cls.g_eng)

        cls.project = Project.objects.create(
            name='Proj Com',
            code='PCOM',
            start_date=date(2026, 1, 1),
            end_date=date(2026, 12, 31),
            is_active=True,
        )
        ProjectMember.objects.create(user=cls.u_plain, project=cls.project)
        cls.obra = Obra.objects.create(
            project=cls.project,
            codigo='OC1',
            nome='Obra teste com',
            ativo=True,
        )

    def _novo_com(self, **kwargs) -> Comunicado:
        defaults = dict(
            titulo=f'aviso-{Comunicado.objects.count()}',
            criado_por=self.creator,
            ativo=True,
            abrir_automaticamente=True,
            tipo_conteudo=TipoConteudo.TEXTO,
            tipo_exibicao=TipoExibicao.SEMPRE,
            publico_todos=True,
            publico_escopo_criterios=PublicoEscopoCriterios.QUALQUER,
            publico_restrito_perfil=PublicoRestricaoPerfil.NENHUMA,
        )
        defaults.update(kwargs)
        c = Comunicado(**defaults)
        c.save()
        return c

    def test_publico_todos_aparece_para_utilizador(self):
        c = self._novo_com()
        ids = [x.pk for x in listar_comunicados_pendentes(self.u_plain)]
        self.assertIn(c.pk, ids)

    def test_inativo_nao_entra_em_pendentes(self):
        c = self._novo_com(ativo=False)
        ids = [x.pk for x in listar_comunicados_pendentes(self.u_plain)]
        self.assertNotIn(c.pk, ids)

    def test_data_fim_passada_nao_entra_candidatos(self):
        c = self._novo_com(data_fim=timezone.now() - timedelta(hours=1))
        ids = [x.pk for x in listar_comunicados_pendentes(self.u_plain)]
        self.assertNotIn(c.pk, ids)

    def test_data_inicio_futura_nao_entra_candidatos(self):
        c = self._novo_com(data_inicio=timezone.now() + timedelta(days=1))
        ids = [x.pk for x in listar_comunicados_pendentes(self.u_plain)]
        self.assertNotIn(c.pk, ids)

    def test_restrito_qualquer_grupo_membro_ve(self):
        c = self._novo_com(publico_todos=False)
        c.grupos_permitidos.add(self.g_eng)
        ids = [x.pk for x in listar_comunicados_pendentes(self.u_plain)]
        self.assertIn(c.pk, ids)

    def test_restrito_qualquer_grupo_nao_membro_nao_ve(self):
        c = self._novo_com(publico_todos=False)
        c.grupos_permitidos.add(self.g_eng)
        u_out = User.objects.create_user(username='out_grp', password='x')
        ids = [x.pk for x in listar_comunicados_pendentes(u_out)]
        self.assertNotIn(c.pk, ids)

    def test_restrito_todos_exige_grupo_e_obra(self):
        c = self._novo_com(
            publico_todos=False,
            publico_escopo_criterios=PublicoEscopoCriterios.TODOS,
        )
        c.grupos_permitidos.add(self.g_eng)
        c.obras_permitidas.add(self.obra)
        ids = [x.pk for x in listar_comunicados_pendentes(self.u_plain)]
        self.assertIn(c.pk, ids)

    def test_restrito_todos_so_grupo_sem_obra_nao_basta(self):
        g2, _ = Group.objects.get_or_create(name='OutroGrp')
        c = self._novo_com(
            publico_todos=False,
            publico_escopo_criterios=PublicoEscopoCriterios.TODOS,
        )
        c.grupos_permitidos.add(g2)
        c.obras_permitidas.add(self.obra)
        ids = [x.pk for x in listar_comunicados_pendentes(self.u_plain)]
        self.assertNotIn(c.pk, ids)

    def test_apenas_staff_exclui_nao_staff(self):
        c = self._novo_com(publico_restrito_perfil=PublicoRestricaoPerfil.APENAS_STAFF)
        self.assertNotIn(c.pk, [x.pk for x in listar_comunicados_pendentes(self.u_plain)])
        self.assertIn(c.pk, [x.pk for x in listar_comunicados_pendentes(self.u_staff)])

    def test_apenas_superuser(self):
        c = self._novo_com(publico_restrito_perfil=PublicoRestricaoPerfil.APENAS_SUPERUSER)
        self.assertNotIn(c.pk, [x.pk for x in listar_comunicados_pendentes(self.u_staff)])
        self.assertIn(c.pk, [x.pk for x in listar_comunicados_pendentes(self.u_super)])

    def test_obra_excluida_remove_membro_projeto(self):
        c = self._novo_com()
        c.obras_excluidas.add(self.obra)
        self.assertNotIn(c.pk, [x.pk for x in listar_comunicados_pendentes(self.u_plain)])

    def test_x_vezes_respeita_maximo(self):
        c = self._novo_com(
            tipo_exibicao=TipoExibicao.X_VEZES,
            max_exibicoes_por_usuario=2,
        )
        ComunicadoVisualizacao.objects.create(
            comunicado=c,
            usuario=self.u_plain,
            total_visualizacoes=2,
        )
        self.assertNotIn(c.pk, [x.pk for x in listar_comunicados_pendentes(self.u_plain)])

    def test_usuario_excluido_nao_ve(self):
        c = self._novo_com()
        c.usuarios_excluidos.add(self.u_plain)
        ids = [x.pk for x in listar_comunicados_pendentes(self.u_plain)]
        self.assertNotIn(c.pk, ids)

    def test_fechou_esconde_ate_mostrar_apos_fechar(self):
        c = self._novo_com(mostrar_apos_fechar=False)
        ComunicadoVisualizacao.objects.create(
            comunicado=c,
            usuario=self.u_plain,
            fechou=True,
            total_visualizacoes=1,
        )
        self.assertNotIn(c.pk, [x.pk for x in listar_comunicados_pendentes(self.u_plain)])

        c.mostrar_apos_fechar = True
        c.save()
        self.assertIn(c.pk, [x.pk for x in listar_comunicados_pendentes(self.u_plain)])

    def test_ignorado_nunca_pendente(self):
        c = self._novo_com()
        ComunicadoVisualizacao.objects.create(
            comunicado=c,
            usuario=self.u_plain,
            status_final=StatusFinalVisualizacao.IGNORADO,
            fechou=True,
            total_visualizacoes=1,
        )
        self.assertNotIn(c.pk, [x.pk for x in listar_comunicados_pendentes(self.u_plain)])

    def test_uma_vez_segunda_visita_nao_pendente(self):
        c = self._novo_com(tipo_exibicao=TipoExibicao.UMA_VEZ)
        ComunicadoVisualizacao.objects.create(
            comunicado=c,
            usuario=self.u_plain,
            total_visualizacoes=1,
        )
        self.assertNotIn(c.pk, [x.pk for x in listar_comunicados_pendentes(self.u_plain)])

    def test_formulario_respondido_nao_pendente(self):
        c = self._novo_com(
            tipo_conteudo=TipoConteudo.FORMULARIO,
            tipo_exibicao=TipoExibicao.SEMPRE,
        )
        ComunicadoVisualizacao.objects.create(
            comunicado=c,
            usuario=self.u_plain,
            respondeu=True,
            total_visualizacoes=1,
        )
        self.assertNotIn(c.pk, [x.pk for x in listar_comunicados_pendentes(self.u_plain)])

    def test_confirmacao_confirmada_nao_pendente(self):
        c = self._novo_com(
            tipo_conteudo=TipoConteudo.CONFIRMACAO,
            tipo_exibicao=TipoExibicao.SEMPRE,
        )
        ComunicadoVisualizacao.objects.create(
            comunicado=c,
            usuario=self.u_plain,
            confirmou_leitura=True,
            total_visualizacoes=1,
        )
        self.assertNotIn(c.pk, [x.pk for x in listar_comunicados_pendentes(self.u_plain)])

    def test_login_reseta_fechou_sempre(self):
        c = self._novo_com(tipo_exibicao=TipoExibicao.SEMPRE)
        ComunicadoVisualizacao.objects.create(
            comunicado=c,
            usuario=self.u_plain,
            fechou=True,
            total_visualizacoes=1,
        )
        self.assertNotIn(c.pk, [x.pk for x in listar_comunicados_pendentes(self.u_plain)])
        rf = RequestFactory()
        request = rf.get('/')
        user_logged_in.send(sender=User, request=request, user=self.u_plain)
        vis = ComunicadoVisualizacao.objects.get(comunicado=c, usuario=self.u_plain)
        self.assertFalse(vis.fechou)
        self.assertIn(c.pk, [x.pk for x in listar_comunicados_pendentes(self.u_plain)])

    def test_login_nao_reseta_se_ignorado(self):
        c = self._novo_com(tipo_exibicao=TipoExibicao.SEMPRE)
        ComunicadoVisualizacao.objects.create(
            comunicado=c,
            usuario=self.u_plain,
            fechou=True,
            status_final=StatusFinalVisualizacao.IGNORADO,
            total_visualizacoes=1,
        )
        rf = RequestFactory()
        request = rf.get('/')
        user_logged_in.send(sender=User, request=request, user=self.u_plain)
        vis = ComunicadoVisualizacao.objects.get(comunicado=c, usuario=self.u_plain)
        self.assertTrue(vis.fechou)

    def test_get_eligible_coerente_com_publico_todos(self):
        c = self._novo_com()
        el = get_eligible_user_ids(c)
        self.assertIn(self.u_plain.pk, el)

    def test_form_imagem_sem_ficheiro_erro(self):
        data = {
            'titulo': 'x',
            'ativo': True,
            'tipo_conteudo': TipoConteudo.IMAGEM,
            'tipo_exibicao': TipoExibicao.SEMPRE,
            'destaque_visual': 'PADRAO',
            'prioridade': 'NORMAL',
            'publico_todos': True,
            'publico_escopo_criterios': PublicoEscopoCriterios.QUALQUER,
            'publico_restrito_perfil': PublicoRestricaoPerfil.NENHUMA,
            'pode_fechar': True,
            'exige_confirmacao': False,
            'exige_resposta': False,
            'bloquear_ate_acao': False,
            'abrir_automaticamente': True,
            'mostrar_apos_fechar': False,
            'permitir_nao_mostrar_novamente': False,
        }
        f = ComunicadoForm(data=data)
        self.assertFalse(f.is_valid())
        self.assertIn('imagem', f.errors)


class ComunicadosEncerrarViewTests(TestCase):
    def setUp(self):
        self.creator = User.objects.create_user(username='adm_enc', password='pw', is_superuser=True)
        self.client = Client()
        self.client.login(username='adm_enc', password='pw')

    def test_encerrar_segunda_vez_nao_altera(self):
        agora = timezone.now()
        c = Comunicado.objects.create(
            titulo='enc2x',
            criado_por=self.creator,
            data_fim=agora - timedelta(hours=2),
        )
        old_fim = c.data_fim
        url = reverse('comunicados_painel_encerrar', args=[c.pk])
        self.client.post(url)
        c.refresh_from_db()
        self.assertEqual(c.data_fim, old_fim)


class ComunicadosApiRegistrarTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='api_u', password='pw')
        self.creator = User.objects.create_user(username='api_c', password='pw')
        self.com = Comunicado.objects.create(titulo='api', criado_por=self.creator)

    def test_registrar_visualizou(self):
        self.client.login(username='api_u', password='pw')
        url = reverse('api_comunicados_registrar')
        resp = self.client.post(
            url,
            data=f'{{"comunicado_id":{self.com.pk},"acao":"visualizou"}}',
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data.get('sucesso'))
        vis = ComunicadoVisualizacao.objects.get(comunicado=self.com, usuario=self.user)
        self.assertGreaterEqual(vis.total_visualizacoes, 1)
