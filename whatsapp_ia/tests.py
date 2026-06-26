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
from whatsapp_ia.briefing import gerar_briefing_operacional, invalidar_cache_briefing
from whatsapp_ia.ia_service import (
    _montar_historico_conversa,
    _montar_messages_openai,
    _texto_usuario_de_log,
)
from whatsapp_ia.models import IaMensagemLog
from whatsapp_ia.prompts import montar_system_prompt
from whatsapp_ia.ia_functions import (
    _CAMPOS_SENSIVEIS_RH,
    _classificar_volume_suprimentos,
    _get_escopo_obras,
    _get_escopo_trackhub,
    _situacao_rdo_periodo,
    comparar_progresso_mapa_datas,
    consultar_colaboradores_ativos,
    consultar_documentos_vencendo,
    consultar_frequencia_rdos,
    consultar_panorama_mapa_controle,
    consultar_panorama_suprimentos,
    consultar_pendencias_trackhub,
    consultar_pendencias_por_responsavel,
    consultar_resumo_mapa_obra,
    consultar_resumo_rh,
    consultar_situacao_geral_obras,
    consultar_situacao_rdo_obra,
    consultar_usuarios,
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
        self.assertIn('total_elementos', resultado)
        self.assertIn('linhas', resultado)
        self.assertIn('pontos', resultado)
        self.assertIn('areas', resultado)
        self.assertIn('progresso_geral_pct', resultado)
        self.assertIn('marcadores_gps', resultado)
        self.assertIn('vinculos_eap', resultado['_meta'])
        self.assertIn('ultima_data_diario', resultado)
        self.assertGreaterEqual(resultado['total_elementos'], 1)

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
        colab = next(
            c for c in resultado['colaboradores'] if c['nome'] == 'João Silva'
        )
        self.assertNotIn('cpf', colab)
        self.assertNotIn('salario', colab)


class BriefingOperacionalTests(TestCase):
    def setUp(self):
        self.project, self.obra = _criar_obra_com_project(
            nome='Obra Briefing',
            codigo='OBR-BRF',
        )
        self.wa = _criar_usuario_wa(suffix='30')
        invalidar_cache_briefing(self.wa)

    def test_gerar_briefing_estrutura(self):
        briefing = gerar_briefing_operacional(
            usuario_wa=self.wa, use_cache=False,
        )
        self.assertIn('data_referencia', briefing)
        self.assertIn('escopo', briefing)
        self.assertIn('alertas', briefing)
        self.assertIn('obras_sem_alertas', briefing)
        self.assertIn('rdos_atrasados', briefing['alertas'])
        self.assertIn('pedidos_criticos', briefing['alertas'])
        self.assertIn('restricoes_abertas', briefing['alertas'])
        self.assertIn('pendencias_vencidas', briefing['alertas'])
        self.assertIn('Obra Briefing', briefing['escopo']['obras'])

    def test_montar_system_prompt_inclui_briefing(self):
        briefing = gerar_briefing_operacional(
            usuario_wa=self.wa, use_cache=False,
        )
        prompt = montar_system_prompt(briefing)
        self.assertIn('BRIEFING OPERACIONAL', prompt)
        self.assertIn('CICLO DE RACIOCÍNIO OBRIGATÓRIO', prompt)
        self.assertIn('Obra Briefing', prompt)

    def test_briefing_usa_cache(self):
        invalidar_cache_briefing(self.wa)
        b1 = gerar_briefing_operacional(usuario_wa=self.wa, use_cache=True)
        b2 = gerar_briefing_operacional(usuario_wa=self.wa, use_cache=True)
        self.assertEqual(b1, b2)


class HistoricoConversaWhatsAppTests(TestCase):
    def setUp(self):
        self.wa = _criar_usuario_wa(suffix='40')

    def _payload_webhook(self, texto: str) -> str:
        return json.dumps({
            'entry': [{
                'changes': [{
                    'value': {
                        'messages': [{
                            'from': '5581999990040',
                            'type': 'text',
                            'text': {'body': texto},
                        }],
                    },
                }],
            }],
        }, ensure_ascii=False)

    def test_extrair_texto_de_json_webhook(self):
        texto = _texto_usuario_de_log(self._payload_webhook('Olá, obras ativas'))
        self.assertEqual(texto, 'Olá, obras ativas')

    def test_extrair_texto_puro_legado(self):
        self.assertEqual(_texto_usuario_de_log('mensagem antiga'), 'mensagem antiga')

    def test_historico_ordem_cronologica_e_exclusoes(self):
        IaMensagemLog.objects.create(
            usuario=self.wa,
            telefone=self.wa.telefone,
            mensagem_recebida=self._payload_webhook('primeira'),
            resposta_enviada='resposta 1',
            status='ok',
        )
        IaMensagemLog.objects.create(
            usuario=self.wa,
            telefone=self.wa.telefone,
            mensagem_recebida=self._payload_webhook('segunda'),
            resposta_enviada='resposta 2',
            status='ok',
        )
        IaMensagemLog.objects.create(
            usuario=self.wa,
            telefone=self.wa.telefone,
            mensagem_recebida=self._payload_webhook('ignorada'),
            resposta_enviada='',
            status='ok',
        )
        IaMensagemLog.objects.create(
            usuario=self.wa,
            telefone=self.wa.telefone,
            mensagem_recebida=self._payload_webhook('nao auth'),
            resposta_enviada='bloqueado',
            status='nao_autorizado',
        )

        historico = _montar_historico_conversa(self.wa)
        self.assertEqual(len(historico), 4)
        self.assertEqual(historico[0]['content'], 'primeira')
        self.assertEqual(historico[1]['content'], 'resposta 1')
        self.assertEqual(historico[2]['content'], 'segunda')
        self.assertEqual(historico[3]['content'], 'resposta 2')

    def test_montar_messages_com_historico(self):
        IaMensagemLog.objects.create(
            usuario=self.wa,
            telefone=self.wa.telefone,
            mensagem_recebida=self._payload_webhook('antes'),
            resposta_enviada='resposta antes',
            status='ok',
        )
        msgs = _montar_messages_openai(
            'system test',
            'agora',
            usuario_wa=self.wa,
        )
        self.assertEqual(msgs[0], {'role': 'system', 'content': 'system test'})
        self.assertEqual(msgs[1]['role'], 'user')
        self.assertEqual(msgs[1]['content'], 'antes')
        self.assertEqual(msgs[2]['role'], 'assistant')
        self.assertEqual(msgs[-1], {'role': 'user', 'content': 'agora'})


class RdoTrackHubWhatsAppTests(TestCase):
    def setUp(self):
        self.wa = _criar_usuario_wa(suffix='50')
        self.project, self.obra = _criar_obra_com_project(
            nome='Obra RDO Teste',
            codigo='OBR-RDO',
        )
        self.obra_sede = Obra.objects.create(
            codigo_sienge='SEDE',
            nome='Sede',
            ativa=True,
        )
        self.user_resp = User.objects.create_user(
            'cleiton', password='test', first_name='Cleiton',
        )

    def test_classificar_volume_suprimentos_baixo(self):
        vol = _classificar_volume_suprimentos(5)
        self.assertEqual(vol['_meta']['classificacao'], 'baixo')
        self.assertIn('volume baixo', vol['descricao'])
        self.assertNotIn('não é alto volume', vol['descricao'])

    def test_classificar_volume_sem_cadastro_alerta(self):
        vol = _classificar_volume_suprimentos(0)
        self.assertTrue(vol['_meta']['sem_itens'])

    def test_escopo_trackhub_inclui_sede(self):
        th = list(_get_escopo_trackhub(self.wa).values_list('nome', flat=True))
        oper = list(_get_escopo_obras(self.wa).values_list('nome', flat=True))
        self.assertIn('Sede', th)
        self.assertNotIn('Sede', oper)

    def test_situacao_rdo_periodo_breakdown(self):
        from core.models import ConstructionDiary, DiaryNoReportDay

        hoje = timezone.localdate()
        ConstructionDiary.objects.create(
            project=self.project,
            date=hoje - timedelta(days=1),
            status='AP',
        )
        ConstructionDiary.objects.create(
            project=self.project,
            date=hoje - timedelta(days=2),
            status='AG',
        )
        ConstructionDiary.objects.create(
            project=self.project,
            date=hoje - timedelta(days=3),
            status='SP',
        )
        DiaryNoReportDay.objects.create(
            project=self.project,
            date=hoje - timedelta(days=4),
            reason='FE',
        )

        sit = _situacao_rdo_periodo(self.project, front_id='todas', dias_analise=90)
        self.assertEqual(sit['total_rdos'], 3)
        self.assertEqual(sit['aprovados'], 1)
        self.assertEqual(sit['pendentes_aprovacao'], 1)
        self.assertEqual(sit['rascunhos'], 1)
        self.assertEqual(sit['dias_com_falta'], 1)

    def test_consultar_situacao_rdo_obra_alerta(self):
        from core.models import ConstructionDiary

        hoje = timezone.localdate()
        ConstructionDiary.objects.create(
            project=self.project,
            date=hoje - timedelta(days=10),
            status='AP',
        )

        resultado = json.loads(
            consultar_situacao_rdo_obra(
                obra_nome='Obra RDO Teste',
                usuario_wa=self.wa,
            )
        )
        self.assertEqual(resultado['obra'], 'Obra RDO Teste')
        seg = resultado['segmentos'][0]
        seg_meta = seg.get('_meta', {})
        self.assertTrue(seg_meta.get('sem_rdo_recente'))
        self.assertIn('alerta', seg)
        self.assertEqual(seg_meta.get('nivel'), 'atencao')
        self.assertEqual(seg_meta.get('tipo'), 'sem_rdo_recente')
        texto = json.dumps(resultado)
        self.assertNotIn('OBRIGATÓRIO ALERTAR', texto)
        self.assertNotIn('SITUAÇÃO CRÍTICA', texto)
        self.assertNotIn('(limite', texto)

    def test_frequencia_rdos_sem_texto_interno(self):
        resultado = json.loads(consultar_frequencia_rdos(usuario_wa=self.wa))
        texto = json.dumps(resultado)
        self.assertNotIn('OBRIGATÓRIO ALERTAR', texto)
        self.assertNotIn('SITUAÇÃO CRÍTICA', texto)
        self.assertNotIn('(limite', texto)
        self.assertNotIn('parametros', texto)
        self.assertNotIn('dias_sem_rdo_alerta', texto)
        self.assertNotIn('lacunas_acima_limite', texto)

    def test_panorama_mapa_controle_sem_media_agregada(self):
        resultado = json.loads(consultar_panorama_mapa_controle(usuario_wa=self.wa))
        self.assertNotIn('nota', resultado)
        for obra in resultado['obras']:
            self.assertIn('mapas', obra)
            self.assertNotIn('percentual_conclusao_medio', obra)
            self.assertNotIn('nota', obra)
            if obra['total_mapas'] > 1:
                self.assertTrue(obra.get('_meta', {}).get('multiplos_mapas'))
            if obra['total_mapas'] == 1:
                self.assertIn('percentual_conclusao', obra)

    def test_situacao_geral_mapa_controle_lista_individual(self):
        resultado = json.loads(consultar_situacao_geral_obras(usuario_wa=self.wa))
        mapa = resultado['mapa_controle']
        self.assertNotIn('nota', mapa)
        self.assertIn('obras', mapa)
        for obra in mapa['obras']:
            self.assertIn('mapas', obra)
            self.assertNotIn('percentual_conclusao_medio', obra)
            self.assertNotIn('nota', obra)

    def test_trackhub_contagem_inclui_sede_e_vencidas(self):
        from trackhub.models import Pendencia

        hoje = timezone.localdate()
        Pendencia.objects.create(
            obra=self.obra,
            titulo='Pendência obra',
            prazo=hoje - timedelta(days=5),
            status='aberta',
            responsavel_interno=self.user_resp,
        )
        Pendencia.objects.create(
            obra=self.obra_sede,
            titulo='Pendência sede vencida',
            prazo=hoje - timedelta(days=3),
            status='aberta',
        )
        Pendencia.objects.create(
            obra=self.obra_sede,
            titulo='Pendência sede aberta',
            prazo=hoje + timedelta(days=5),
            status='aberta',
        )

        resultado = json.loads(consultar_pendencias_trackhub(usuario_wa=self.wa))
        self.assertTrue(resultado['inclui_sede'])
        self.assertEqual(resultado['totais']['vencidas'], 2)
        self.assertEqual(resultado['totais']['abertas'], 3)

        nomes = {o['obra'] for o in resultado['obras']}
        self.assertIn('Sede', nomes)
        self.assertIn('Obra RDO Teste', nomes)

        sede = next(o for o in resultado['obras'] if o['obra'] == 'Sede')
        self.assertEqual(sede['total_abertas'], 2)
        self.assertEqual(sede['vencidas'], 1)

    def test_trackhub_responsaveis_atrasados(self):
        from trackhub.models import Pendencia

        hoje = timezone.localdate()
        Pendencia.objects.create(
            obra=self.obra,
            titulo='Atrasada Cleiton',
            prazo=hoje - timedelta(days=12),
            status='aberta',
            responsavel_interno=self.user_resp,
        )

        resultado = json.loads(
            consultar_pendencias_trackhub(
                obra_nome='Obra RDO Teste',
                usuario_wa=self.wa,
            )
        )
        obra = resultado['obras'][0]
        self.assertGreater(len(obra['responsaveis_atrasados']), 0)
        self.assertEqual(obra['responsaveis_atrasados'][0]['maior_atraso_dias'], 12)

    def test_consultar_usuarios_sem_campo_texto_responsavel(self):
        from core.models import ProjectMember

        self.project.responsible = 'Cleiton Silva'
        self.project.save(update_fields=['responsible'])

        ProjectMember.objects.create(project=self.project, user=self.user_resp)

        resultado = json.loads(
            consultar_usuarios(usuario_nome='Cleiton', usuario_wa=self.wa)
        )
        perfil = resultado['usuarios'][0]
        self.assertIn('Obra RDO Teste', perfil['obras_vinculadas'])
        self.assertIn('pedidos_aguardando_aprovacao', perfil)
        self.assertNotIn('obras_como_responsavel', perfil)
        self.assertNotIn('nota_obras_vinculadas', perfil)

    def test_pendencias_por_responsavel_separa_papel(self):
        from trackhub.models import EtapaPendencia, Pendencia

        hoje = timezone.localdate()
        pend = Pendencia.objects.create(
            obra=self.obra,
            titulo='Pendência com etapa',
            prazo=hoje - timedelta(days=2),
            status='aberta',
            responsavel_interno=self.user_resp,
        )
        EtapaPendencia.objects.create(
            pendencia=pend,
            ordem=1,
            titulo='Etapa 1',
            status='pendente',
            prazo=hoje - timedelta(days=1),
            responsavel_interno=self.user_resp,
        )

        resultado = json.loads(
            consultar_pendencias_por_responsavel(
                responsavel_nome='Cleiton',
                usuario_wa=self.wa,
            )
        )
        self.assertIn('pendencias_como_dono', resultado)
        self.assertIn('pendencias_como_responsavel_etapa', resultado)
        self.assertGreater(resultado['total_como_dono'], 0)
        self.assertGreater(resultado['total_como_responsavel_etapa'], 0)
        self.assertNotIn('nota', resultado)

    def test_situacao_geral_obras_modulos(self):
        resultado = json.loads(consultar_situacao_geral_obras(usuario_wa=self.wa))
        self.assertEqual(
            resultado['modulos'],
            [
                'rdos', 'pedidos', 'restricoes', 'suprimentos',
                'mapa_controle', 'trackhub',
            ],
        )
        self.assertIn('detalhe', resultado['rdos'])
        self.assertIn('resumo_obras_ok', resultado)
        self.assertIn('obras', resultado['trackhub'])
        self.assertTrue(resultado['trackhub']['inclui_sede'])

    def test_situacao_geral_restricoes_por_obra_completas(self):
        resultado = json.loads(consultar_situacao_geral_obras(usuario_wa=self.wa))
        restricoes = resultado['restricoes']
        self.assertIn('total_abertas', restricoes)
        self.assertIn('total_vencidas', restricoes)
        self.assertIn('total_criticas_altas', restricoes)
        self.assertIn('obras', restricoes)
        for obra in restricoes['obras']:
            self.assertIn('abertas', obra)
            self.assertIn('vencidas', obra)
            self.assertIn('criticas_altas', obra)

    def test_situacao_geral_trackhub_inclui_sede(self):
        from trackhub.models import Pendencia

        hoje = timezone.localdate()
        Pendencia.objects.create(
            obra=self.obra_sede,
            titulo='Pendência sede panorama',
            prazo=hoje - timedelta(days=2),
            status='aberta',
        )

        resultado = json.loads(consultar_situacao_geral_obras(usuario_wa=self.wa))
        nomes = {o['obra'] for o in resultado['trackhub']['obras']}
        self.assertIn('Sede', nomes)
        sede = next(o for o in resultado['trackhub']['obras'] if o['obra'] == 'Sede')
        self.assertGreaterEqual(sede['total_abertas'], 1)

    def test_situacao_geral_resumo_todas_com_alerta(self):
        resultado = json.loads(consultar_situacao_geral_obras(usuario_wa=self.wa))
        resumo = resultado['resumo_obras_ok']
        self.assertTrue(resumo['todas_obras_com_alerta'])
        self.assertEqual(resumo['total_sem_alertas'], 0)
        self.assertIn('⚠️ Todas as obras', resumo['mensagem'])
        self.assertNotIn('✅', resumo['mensagem'])

    def test_situacao_geral_resumo_obras_sem_alerta(self):
        from unittest.mock import patch

        with patch(
            'whatsapp_ia.ia_functions._obras_com_alerta_panorama',
            return_value=set(),
        ):
            resultado = json.loads(
                consultar_situacao_geral_obras(usuario_wa=self.wa),
            )
        resumo = resultado['resumo_obras_ok']
        self.assertFalse(resumo['todas_obras_com_alerta'])
        self.assertGreater(resumo['total_sem_alertas'], 0)
        self.assertIn('✅', resumo['mensagem'])
        self.assertNotIn('⚠️ Todas as obras', resumo['mensagem'])

    def test_frequencia_rdos_inclui_situacao_periodo(self):
        resultado = json.loads(consultar_frequencia_rdos(usuario_wa=self.wa))
        obra = next(
            o for o in resultado['obras'] if o['obra'] == 'Obra RDO Teste'
        )
        seg = obra['segmentos'][0]
        self.assertIn('situacao_periodo', seg)
        self.assertIn('total_rdos', seg['situacao_periodo'])


_IDENTIFICADORES_TECNICOS_PROIBIDOS = (
    '(limite',
    'dias_sem_rdo_alerta',
    'parametros',
    'nota_',
    'lacunas_acima_limite',
    'sem_sc',
    'sem_pc',
    'alerta_sem_cadastro',
    'dias_aprovacao_alerta',
    'dias_antecedencia_documentos',
    'volume_descricao',
    'não assuma',
    'nunca agregue',
    'nunca só criticidade',
    'como_responsavel_pendencia =',
)


class AntiVazamentoTextoInternoTests(TestCase):
    """Garante que retornos das funções não contenham texto interno vazável."""

    @classmethod
    def setUpTestData(cls):
        cls.wa = _criar_usuario_wa(suffix='leak')

    def _assert_sem_vazamentos(self, texto: str):
        texto_lower = texto.lower()
        for proibido in _IDENTIFICADORES_TECNICOS_PROIBIDOS:
            with self.subTest(proibido=proibido):
                self.assertNotIn(proibido.lower(), texto_lower)

    def test_funcoes_principais_sem_vazamento(self):
        consultas = [
            (consultar_frequencia_rdos, {'usuario_wa': self.wa}),
            (consultar_panorama_suprimentos, {'usuario_wa': self.wa}),
            (consultar_panorama_mapa_controle, {'usuario_wa': self.wa}),
            (consultar_situacao_geral_obras, {'usuario_wa': self.wa}),
            (consultar_resumo_rh, {'usuario_wa': _criar_usuario_wa(
                {'pode_consultar_rh': True}, suffix='rh',
            )}),
        ]
        for func, kwargs in consultas:
            with self.subTest(func=func.__name__):
                self._assert_sem_vazamentos(func(**kwargs))

    def test_prompt_contem_regra_proibido(self):
        briefing = gerar_briefing_operacional(usuario_wa=self.wa, use_cache=False)
        prompt = montar_system_prompt(briefing)
        self.assertIn('PROIBIDO expor ao usuário', prompt)
        self.assertIn('dias_sem_rdo_alerta', prompt)
        self.assertIn('_meta', prompt)
