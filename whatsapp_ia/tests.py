import json
from datetime import date, timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from core.models import Project
from mapa_geo.models import GeoFeature
from mapa_obras.models import Obra
from recursos_humanos.models import (
    Colaborador,
    ConfiguracaoAlertasRH,
    DocumentoColaborador,
    TipoDocumento,
)
from whatsapp_ia.ia_functions import (
    _CAMPOS_SENSIVEIS_RH,
    comparar_progresso_mapa_datas,
    consultar_colaboradores_ativos,
    consultar_documentos_vencendo,
    consultar_resumo_mapa_obra,
    consultar_resumo_rh,
    executar_funcao,
    listar_elementos_mapa_obra,
    panorama_mapas_obras,
)
from whatsapp_ia.models import IaPermissaoConsulta, UsuarioWhatsApp


def _criar_usuario_wa(permissao_kwargs=None, suffix=''):
    username = f'wa_user{suffix}'
    telefone = f'+558199999{suffix or "0001"}'[:20]
    user = User.objects.create_user(username, password='test')
    wa = UsuarioWhatsApp.objects.create(
        telefone=telefone,
        usuario=user,
        ativo=True,
    )
    defaults = {
        'pode_consultar_mapa_geo': False,
        'pode_consultar_rh': False,
    }
    if permissao_kwargs:
        defaults.update(permissao_kwargs)
    IaPermissaoConsulta.objects.create(usuario=wa, **defaults)
    return wa


def _criar_obra_com_project(nome='Obra Mapa Teste', codigo='OBR-MAP'):
    project = Project.objects.create(
        name=nome,
        code=codigo,
        is_active=True,
        start_date=date(2025, 1, 1),
        end_date=date(2026, 12, 31),
    )
    obra = Obra.objects.create(
        codigo_sienge=codigo,
        nome=nome,
        ativa=True,
        project=project,
    )
    return project, obra


class PermissaoModulosWhatsAppTests(TestCase):
    def setUp(self):
        self.project, self.obra = _criar_obra_com_project()
        self.wa_sem = _criar_usuario_wa(suffix='01')
        self.wa_mapa = _criar_usuario_wa(
            {'pode_consultar_mapa_geo': True}, suffix='02',
        )
        self.wa_rh = _criar_usuario_wa(
            {'pode_consultar_rh': True}, suffix='03',
        )

    def test_mapa_sem_permissao_retorna_erro(self):
        resultado = json.loads(
            consultar_resumo_mapa_obra(
                obra_nome='Obra Mapa Teste',
                usuario_wa=self.wa_sem,
            )
        )
        self.assertEqual(resultado, {'erro': 'sem permissão'})

    def test_rh_sem_permissao_retorna_erro(self):
        resultado = json.loads(consultar_resumo_rh(usuario_wa=self.wa_sem))
        self.assertEqual(resultado, {'erro': 'sem permissão'})

    def test_executar_funcao_propaga_permissao(self):
        resultado = json.loads(
            executar_funcao(
                'panorama_mapas_obras',
                {},
                usuario_wa=self.wa_sem,
            )
        )
        self.assertEqual(resultado, {'erro': 'sem permissão'})


class MapaGeoWhatsAppTests(TestCase):
    def setUp(self):
        self.project, self.obra = _criar_obra_com_project()
        self.wa = _criar_usuario_wa(
            {'pode_consultar_mapa_geo': True}, suffix='10',
        )
        GeoFeature.objects.create(
            project=self.project,
            name='Trecho A',
            folder='Trecho 01',
            geometry_type='LineString',
            geometry={
                'type': 'LineString',
                'coordinates': [[-35.0, -8.0, 0], [-35.1, -8.1, 0]],
            },
            kind='segment',
            status='in_progress',
            progress_pct='45.00',
            is_active=True,
        )

    def test_consultar_resumo_mapa_obra_estrutura(self):
        resultado = json.loads(
            consultar_resumo_mapa_obra(
                obra_nome='Obra Mapa Teste',
                usuario_wa=self.wa,
            )
        )
        self.assertEqual(resultado['obra'], 'Obra Mapa Teste')
        self.assertIn('total', resultado)
        self.assertIn('linhas', resultado)
        self.assertIn('pontos', resultado)
        self.assertIn('areas', resultado)
        self.assertIn('progresso_geral_pct', resultado)
        self.assertIn('marcadores_gps', resultado)
        self.assertIn('vinculos_eap', resultado)
        self.assertIn('ultima_data_diario', resultado)
        self.assertGreaterEqual(resultado['total'], 1)

    def test_listar_elementos_mapa_obra(self):
        resultado = json.loads(
            listar_elementos_mapa_obra(
                obra_nome='Obra Mapa Teste',
                usuario_wa=self.wa,
            )
        )
        self.assertGreaterEqual(resultado['total'], 1)
        self.assertEqual(resultado['elementos'][0]['nome'], 'Trecho A')

    def test_panorama_mapas_obras(self):
        resultado = json.loads(panorama_mapas_obras(usuario_wa=self.wa))
        self.assertGreaterEqual(resultado['total_obras'], 1)
        self.assertTrue(any(o['nome'] == 'Obra Mapa Teste' for o in resultado['obras']))

    def test_comparar_progresso_mapa_datas(self):
        hoje = timezone.localdate()
        ontem = hoje - timedelta(days=1)
        resultado = json.loads(
            comparar_progresso_mapa_datas(
                obra_nome='Obra Mapa Teste',
                data_inicio=str(ontem),
                data_fim=str(hoje),
                usuario_wa=self.wa,
            )
        )
        self.assertIn('avancaram', resultado)
        self.assertIn('estagnados', resultado)
        self.assertIn('regrediram', resultado)


class RecursosHumanosWhatsAppTests(TestCase):
    def setUp(self):
        self.wa = _criar_usuario_wa(
            {'pode_consultar_rh': True}, suffix='20',
        )
        self.tipo = TipoDocumento.objects.create(
            nome='ASO WA',
            tem_validade=True,
            ordem=1,
        )
        config = ConfiguracaoAlertasRH.get_solo()
        config.dias_antecedencia_documentos = 15
        config.save()

        self.colab = Colaborador.objects.create(
            nome='João Silva',
            cpf='123.456.789-00',
            cargo='Pedreiro',
            salario='3500.00',
            dados_bancarios='Banco X ag 123',
            email='joao@example.com',
            telefone='81999990000',
            status=Colaborador.Status.ATIVO,
        )
        self.vencimento = timezone.localdate() + timedelta(days=10)
        DocumentoColaborador.objects.create(
            colaborador=self.colab,
            tipo=self.tipo,
            status=DocumentoColaborador.Status.RECEBIDO,
            vencimento=self.vencimento,
        )

    def test_consultar_resumo_rh_estrutura(self):
        resultado = json.loads(consultar_resumo_rh(usuario_wa=self.wa))
        self.assertIn('colaboradores', resultado)
        self.assertIn('ativos', resultado['colaboradores'])
        self.assertIn('em_admissao', resultado['colaboradores'])
        self.assertIn('desligados', resultado['colaboradores'])
        self.assertIn('alertas', resultado)
        self.assertIn('criticos', resultado['alertas'])
        self.assertGreaterEqual(resultado['colaboradores']['ativos'], 1)

    def test_consultar_documentos_vencendo_respeita_config(self):
        resultado = json.loads(consultar_documentos_vencendo(usuario_wa=self.wa))
        self.assertEqual(resultado['dias_janela'], 15)
        self.assertGreaterEqual(resultado['total'], 1)
        nomes = [d['colaborador_nome'] for d in resultado['documentos']]
        self.assertIn('João Silva', nomes)

    def test_consultar_documentos_vencendo_dias_customizado(self):
        resultado = json.loads(
            consultar_documentos_vencendo(dias=7, usuario_wa=self.wa)
        )
        self.assertEqual(resultado['dias_janela'], 7)

    def _coletar_chaves_recursivo(self, obj, chaves=None):
        if chaves is None:
            chaves = set()
        if isinstance(obj, dict):
            for k, v in obj.items():
                chaves.add(k)
                self._coletar_chaves_recursivo(v, chaves)
        elif isinstance(obj, list):
            for item in obj:
                self._coletar_chaves_recursivo(item, chaves)
        return chaves

    def test_lgpd_nenhuma_funcao_rh_expoe_dados_sensiveis(self):
        funcoes_rh = [
            ('consultar_resumo_rh', {}),
            ('consultar_colaboradores_ativos', {}),
            ('consultar_admissoes_em_andamento', {}),
            ('consultar_documentos_vencendo', {'dias': 15}),
            ('consultar_documentos_vencidos', {}),
            ('consultar_prazos_contrato_vencendo', {}),
            ('consultar_contratos_pendentes_assinatura', {}),
            ('consultar_alertas_rh_criticos', {}),
        ]
        for nome, args in funcoes_rh:
            with self.subTest(funcao=nome):
                raw = executar_funcao(nome, args, usuario_wa=self.wa)
                payload = json.loads(raw)
                self.assertNotIn('erro', payload, msg=nome)
                chaves = self._coletar_chaves_recursivo(payload)
                expostos = chaves & _CAMPOS_SENSIVEIS_RH
                self.assertEqual(
                    expostos,
                    set(),
                    msg=f'{nome} expôs campos sensíveis: {expostos}',
                )
                texto = raw.lower()
                self.assertNotIn('123.456.789', texto)
                self.assertNotIn('3500.00', texto)
                self.assertNotIn('banco x', texto)

    def test_colaboradores_ativos_nao_inclui_cpf(self):
        resultado = json.loads(
            consultar_colaboradores_ativos(usuario_wa=self.wa)
        )
        self.assertGreaterEqual(resultado['total'], 1)
        colab = resultado['colaboradores'][0]
        self.assertEqual(colab['nome'], 'João Silva')
        self.assertNotIn('cpf', colab)
        self.assertNotIn('salario', colab)
