import json
from datetime import date, timedelta

from django.contrib.auth.models import Group, User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.groups import GRUPOS
from core.models import ConstructionDiary, Project, ProjectMember
from gestao_aprovacao.models import Obra, WorkOrder, WorkOrderPermission
from mapa_obras.models import Obra as MapaObra
from suprimentos.models import Insumo, ItemMapa

from .models import AssistantQuestionLog, AssistantResponseLog
from .models import AssistantEntityAlias, AssistantGuidedRule, AssistantLearningFeedback
from .services.parser import RuleBasedIntentParser
from .services.radar_obra_service import RadarObraService


class RuleBasedIntentParserTests(TestCase):
    def test_detecta_intencao_localizar_insumo(self):
        result = RuleBasedIntentParser().parse("Onde esta o cimento do bloco C?")
        self.assertEqual(result.intent, "localizar_insumo")
        self.assertEqual(result.entities.get("bloco"), "c")
        self.assertEqual(result.entities.get("insumo"), "cimento")
        self.assertGreaterEqual(result.confidence, 0.45)

    def test_nao_classifica_por_regra_generica_como(self):
        result = RuleBasedIntentParser().parse("Como estao as coisas?")
        self.assertEqual(result.intent, "fallback")

    def test_detecta_resumo_para_pergunta_generica_de_rdo(self):
        result = RuleBasedIntentParser().parse("como esta o rdo?")
        self.assertEqual(result.intent, "resumo_obra")
        self.assertGreaterEqual(result.confidence, 0.45)

    def test_detecta_status_usuario_como_nome_esta(self):
        result = RuleBasedIntentParser().parse("como luiz esta?")
        self.assertEqual(result.intent, "status_usuario")
        self.assertEqual(result.entities.get("usuario"), "luiz")

    def test_ignora_obra_atual_como_entidade_especifica(self):
        result = RuleBasedIntentParser().parse("Resuma a situacao da obra atual")
        self.assertEqual(result.intent, "resumo_obra")
        self.assertNotIn("obra", result.entities)

    def test_tolerancia_a_erro_digitacao_em_intencao(self):
        result = RuleBasedIntentParser().parse("Quais aprovacoees pendenets?")
        self.assertEqual(result.intent, "listar_aprovacoes_pendentes")

    def test_tolerancia_a_erro_digitacao_em_entidades_basicas(self):
        result = RuleBasedIntentParser().parse("Onde esta o simento do bloko C?")
        self.assertEqual(result.intent, "localizar_insumo")
        self.assertEqual(result.entities.get("insumo"), "cimento")
        self.assertEqual(result.entities.get("bloco"), "c")


class AssistantEndpointTests(TestCase):
    def setUp(self):
        self.eng1 = User.objects.create_user(username="eng1", password="123456", first_name="Eng")
        self.eng2 = User.objects.create_user(username="eng2", password="123456", first_name="Outro")
        self.aprovador = User.objects.create_user(username="aprovador", password="123456", first_name="Aprov")
        self.admin = User.objects.create_user(username="admin", password="123456", is_staff=True, is_superuser=True)

        group, _ = Group.objects.get_or_create(name=GRUPOS.APROVADOR)
        self.aprovador.groups.add(group)

        self.project_1 = Project.objects.create(
            name="Obra Alfa",
            code="ALFA",
            start_date=date(2026, 1, 1),
            end_date=date(2026, 12, 31),
            is_active=True,
        )
        self.project_2 = Project.objects.create(
            name="Obra Beta",
            code="BETA",
            start_date=date(2026, 1, 1),
            end_date=date(2026, 12, 31),
            is_active=True,
        )
        ProjectMember.objects.create(user=self.eng1, project=self.project_1)
        ProjectMember.objects.create(user=self.eng2, project=self.project_2)

        self.obra_1 = Obra.objects.create(project=self.project_1, codigo="OA1", nome="Obra A1", ativo=True)
        self.obra_2 = Obra.objects.create(project=self.project_2, codigo="OB1", nome="Obra B1", ativo=True)

        WorkOrder.objects.create(
            obra=self.obra_1,
            codigo="PED-A1",
            nome_credor="Fornecedor A",
            tipo_solicitacao="contrato",
            status="pendente",
            criado_por=self.eng1,
        )
        WorkOrder.objects.create(
            obra=self.obra_2,
            codigo="PED-B1",
            nome_credor="Fornecedor B",
            tipo_solicitacao="contrato",
            status="pendente",
            criado_por=self.eng2,
        )

        WorkOrderPermission.objects.create(obra=self.obra_1, usuario=self.aprovador, tipo_permissao="aprovador", ativo=True)

        self.mapa_obra_1 = MapaObra.objects.create(codigo_sienge="ALFA", nome="Mapa ALFA", ativa=True)
        self.insumo_1 = Insumo.objects.create(codigo_sienge="INS-1", descricao="Cimento CP II", unidade="SC")
        ItemMapa.objects.create(
            obra=self.mapa_obra_1,
            insumo=self.insumo_1,
            quantidade_planejada=10,
            prazo_necessidade=timezone.now().date() + timedelta(days=2),
            prioridade="ALTA",
        )

        ConstructionDiary.objects.create(
            project=self.project_1,
            date=timezone.now().date(),
            created_by=self.eng1,
            stoppages="Paralisacao por falta de material",
            imminent_risks="Risco de atraso",
        )

    def test_endpoint_retorna_payload_estruturado(self):
        self.client.login(username="eng1", password="123456")
        response = self.client.post(
            reverse("assistente_lplan:perguntar"),
            data=json.dumps({"pergunta": "quais aprovacoes estao pendentes?"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        for key in ("summary", "cards", "table", "badges", "timeline", "alerts", "actions", "links", "raw_data"):
            self.assertIn(key, payload)
        self.assertEqual(AssistantQuestionLog.objects.count(), 1)
        self.assertEqual(AssistantResponseLog.objects.count(), 1)

    def test_bloqueia_consulta_de_outro_usuario_fora_do_escopo(self):
        self.client.login(username="eng1", password="123456")
        response = self.client.post(
            reverse("assistente_lplan:perguntar"),
            data=json.dumps({"pergunta": "Como eng2 esta nos ultimos 30 dias?"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("fora do seu escopo", payload.get("summary", "").lower())
        self.assertNotIn("user_id", payload.get("raw_data", {}))

    def test_bloqueia_acesso_a_obra_fora_do_escopo(self):
        self.client.login(username="eng1", password="123456")
        response = self.client.post(
            reverse("assistente_lplan:perguntar"),
            data=json.dumps({"pergunta": "Resuma a situacao da obra BETA"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("dados insuficientes", payload.get("summary", "").lower())

    def test_aprovador_ve_apenas_aprovacoes_do_escopo_permitido(self):
        self.client.login(username="aprovador", password="123456")
        response = self.client.post(
            reverse("assistente_lplan:perguntar"),
            data=json.dumps({"pergunta": "Quais aprovacoes estao pendentes?"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload.get("cards", [])[0].get("value"), "1")
        self.assertEqual(payload.get("table", {}).get("rows", [])[0].get("obra"), "Obra A1")

    def test_retorna_mensagem_clara_em_duvida_de_interpretacao(self):
        self.client.login(username="eng1", password="123456")
        response = self.client.post(
            reverse("assistente_lplan:perguntar"),
            data=json.dumps({"pergunta": "como esta?"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("nao consegui interpretar", payload.get("summary", "").lower())
        self.assertIn("Interpretacao ambigua", payload.get("badges", []))
        self.assertEqual(payload.get("raw_data", {}).get("message_code"), "assistant.intent.ambiguous_summary")
        primaries = [a for a in payload.get("actions", []) if a.get("is_primary") is True]
        self.assertEqual(len(primaries), 1)

    def test_payload_erro_json_invalido_tem_message_code(self):
        self.client.login(username="eng1", password="123456")
        response = self.client.post(
            reverse("assistente_lplan:perguntar"),
            data="{",
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        payload = response.json()
        self.assertEqual(payload.get("message_code"), "assistant.api.invalid_json")

    def test_define_uma_acao_principal_por_resposta(self):
        self.client.login(username="aprovador", password="123456")
        response = self.client.post(
            reverse("assistente_lplan:perguntar"),
            data=json.dumps({"pergunta": "Quais aprovacoes estao pendentes?"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        actions = response.json().get("actions", [])
        self.assertGreaterEqual(len(actions), 1)
        primaries = [a for a in actions if a.get("is_primary") is True]
        self.assertEqual(len(primaries), 1)
        self.assertEqual(primaries[0].get("style"), "primary")

    def test_radar_integrado_em_resumo_obra(self):
        self.client.login(username="eng1", password="123456")
        response = self.client.post(
            reverse("assistente_lplan:perguntar"),
            data=json.dumps({"pergunta": "Resuma a situacao da obra ALFA"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("radar_score", payload)
        self.assertIn("risk_level", payload)
        self.assertIn("trend", payload)
        self.assertIn("causes", payload)
        self.assertIn("recommended_action", payload)
        self.assertTrue(isinstance(payload.get("radar_score"), int))
        self.assertGreaterEqual(len(payload.get("secondary_actions", [])), 1)

    def test_registra_feedback_guiado(self):
        self.client.login(username="eng1", password="123456")
        ask = self.client.post(
            reverse("assistente_lplan:perguntar"),
            data=json.dumps({"pergunta": "Quais aprovacoes estao pendentes?"}),
            content_type="application/json",
        )
        self.assertEqual(ask.status_code, 200)
        question_log_id = ask.json().get("question_log_id")
        self.assertTrue(question_log_id)

        feedback = self.client.post(
            reverse("assistente_lplan:feedback"),
            data=json.dumps(
                {
                    "question_log_id": question_log_id,
                    "helpful": False,
                    "corrected_intent": "resumo_obra",
                    "corrected_entities": {"obra": "ALFA"},
                    "note": "Era para resumir a obra.",
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(feedback.status_code, 200)
        self.assertEqual(AssistantLearningFeedback.objects.count(), 1)
        self.assertEqual(AssistantGuidedRule.objects.count(), 1)

    def test_parser_aplica_alias_aprovado(self):
        AssistantEntityAlias.objects.create(
            entity_type="insumo",
            alias_text="cp2",
            canonical_value="cimento cp ii",
            status=AssistantEntityAlias.STATUS_APPROVED,
        )
        result = RuleBasedIntentParser().parse("Onde esta o cp2 do bloco C?")
        self.assertEqual(result.entities.get("insumo"), "cimento cp ii")

    def test_historico_persiste_apos_reabrir_tela(self):
        self.client.login(username="eng1", password="123456")
        ask = self.client.post(
            reverse("assistente_lplan:perguntar"),
            data=json.dumps({"pergunta": "Quais aprovacoes estao pendentes?"}),
            content_type="application/json",
        )
        self.assertEqual(ask.status_code, 200)

        session = self.client.session
        if "assistente_lplan_history" in session:
            del session["assistente_lplan_history"]
            session.save()

        home = self.client.get(reverse("assistente_lplan:home"))
        self.assertEqual(home.status_code, 200)
        self.assertContains(home, "Quais aprovacoes estao pendentes?")


class RadarObraServiceTests(TestCase):
    def test_classificacao_risco(self):
        self.assertEqual(RadarObraService.classify_risk(10), "BAIXO")
        self.assertEqual(RadarObraService.classify_risk(45), "MEDIO")
        self.assertEqual(RadarObraService.classify_risk(80), "ALTO")

    def test_tendencia(self):
        self.assertEqual(RadarObraService.determine_trend(20, 10, 12), "Piorando")
        self.assertEqual(RadarObraService.determine_trend(6, 10, 12), "Melhorando")
        self.assertEqual(RadarObraService.determine_trend(10, 10, 12), "Estavel")

