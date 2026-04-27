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

from comunicados.metrics import get_eligible_user_ids
from django.core.files.uploadedfile import SimpleUploadedFile

from comunicados.forms import ComunicadoForm
from comunicados.models import (
    Comunicado,
    ComunicadoImagem,
    ComunicadoVisualizacao,
    DestaqueVisual,
    PublicoEscopoCriterios,
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
        # SEMPRE: mesmo com "mostrar após fechar", não reabre na mesma sessão — só após novo login.
        self.assertNotIn(c.pk, [x.pk for x in listar_comunicados_pendentes(self.u_plain)])

    def test_mostrar_apos_fechar_reabre_outros_tipos_na_mesma_sessao(self):
        c = self._novo_com(
            tipo_exibicao=TipoExibicao.X_VEZES,
            max_exibicoes_por_usuario=5,
            mostrar_apos_fechar=True,
        )
        ComunicadoVisualizacao.objects.create(
            comunicado=c,
            usuario=self.u_plain,
            fechou=True,
            total_visualizacoes=1,
        )
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

    def test_imagem_exige_confirmacao_confirmado_nao_pendente(self):
        c = self._novo_com(
            tipo_conteudo=TipoConteudo.IMAGEM,
            tipo_exibicao=TipoExibicao.SEMPRE,
            exige_confirmacao=True,
        )
        ComunicadoVisualizacao.objects.create(
            comunicado=c,
            usuario=self.u_plain,
            confirmou_leitura=True,
            total_visualizacoes=1,
        )
        self.assertNotIn(c.pk, [x.pk for x in listar_comunicados_pendentes(self.u_plain)])

    def test_texto_exige_confirmacao_confirmado_nao_pendente(self):
        """Após 'Sim, já li' (API confirmou), não voltar a listar com exibição SEMPRE (evita loop no modal)."""
        c = self._novo_com(
            tipo_conteudo=TipoConteudo.TEXTO,
            tipo_exibicao=TipoExibicao.SEMPRE,
            exige_confirmacao=True,
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

    def test_comunicado_imagem_relacao(self):
        c = self._novo_com(tipo_conteudo=TipoConteudo.IMAGEM)
        png = SimpleUploadedFile('t.png', b'\x89PNG\r\n\x1a\n', content_type='image/png')
        ComunicadoImagem.objects.create(comunicado=c, arquivo=png, ordem=0)
        self.assertEqual(c.imagens.count(), 1)

    def _post_comunicado_form(self, c: Comunicado, extra: dict) -> ComunicadoForm:
        d = {
            'titulo': c.titulo,
            'descricao_interna': c.descricao_interna or '',
            'ativo': 'on',
            'tipo_conteudo': c.tipo_conteudo,
            'titulo_visivel': c.titulo_visivel or 'Vis',
            'subtitulo': c.subtitulo or '',
            'texto_principal': c.texto_principal or 'T',
            'link_destino': c.link_destino or '',
            'texto_botao': c.texto_botao or '',
            'destaque_visual': c.destaque_visual,
            'tipo_exibicao': c.tipo_exibicao,
            'max_exibicoes_por_usuario': '',
            'data_inicio': '',
            'data_fim': '',
            'dias_ativo': '',
            'prioridade': c.prioridade,
            'publico_todos': 'on',
            'publico_escopo_criterios': c.publico_escopo_criterios,
            'pode_fechar': '',
            'exige_confirmacao': '',
            'exige_resposta': '',
            'abrir_automaticamente': 'on' if c.abrir_automaticamente else '',
            'mostrar_apos_fechar': '',
            'permitir_nao_mostrar_novamente': '',
        }
        d.update(extra)
        return ComunicadoForm(d, instance=c)

    def test_form_resposta_obrigatoria_nao_cola_com_pode_fechar(self):
        c = self._novo_com(tipo_conteudo=TipoConteudo.FORMULARIO)
        f = self._post_comunicado_form(
            c,
            {
                'pode_fechar': 'on',
                'exige_resposta': 'on',
            },
        )
        self.assertFalse(f.is_valid())
        self.assertIn('exige_resposta', f.errors)

    def test_form_resposta_obrigatoria_nao_cola_com_nao_mostrar_novamente(self):
        c = self._novo_com(tipo_conteudo=TipoConteudo.FORMULARIO, destaque_visual=DestaqueVisual.PADRAO)
        f = self._post_comunicado_form(
            c,
            {
                'permitir_nao_mostrar_novamente': 'on',
                'exige_resposta': 'on',
                'pode_fechar': '',
            },
        )
        self.assertFalse(f.is_valid())
        self.assertIn('exige_resposta', f.errors)

    def test_form_resposta_obrigatoria_ok_se_sem_conflito(self):
        c = self._novo_com(tipo_conteudo=TipoConteudo.FORMULARIO)
        f = self._post_comunicado_form(
            c,
            {
                'pode_fechar': '',
                'exige_resposta': 'on',
            },
        )
        self.assertTrue(f.is_valid(), f.errors)


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
