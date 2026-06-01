"""
Testes do serviço e da API **Análise da Obra**.

Rodar: python manage.py test suprimentos.tests.test_analise_obra -v 2
"""

from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.groups import GRUPOS
from mapa_obras.models import Obra
from trackhub.models import EtapaPendencia, Pendencia

from core.models import Project, ProjectMember
from suprimentos.services import analise_obra_service as analise_obra_service_mod
from suprimentos.services.analise_obra_service import (
    AnaliseObraFilters,
    AnaliseObraPeriodo,
    AnaliseObraService,
    _classify_occurrence_severity,
)
from suprimentos.tests.test_analise_obra_ambiente import _criar_ambiente_mapa


class TestAnaliseObraService(TestCase):
    def setUp(self):
        self.obra = Obra.objects.create(codigo_sienge="TST-ANL", nome="Obra Análise", ativa=True)
        _criar_ambiente_mapa(
            self.obra,
            [
                ["BLOCO", "PAVIMENTO", "APTO", "Armação", "Concreto", "Total"],
                ["B1", "3", "U1", "25%", "80%", "52.5"],
            ],
        )

    def test_payload_contem_tres_origens_e_heatmap(self):
        p = AnaliseObraPeriodo(
            data_inicio=date(2025, 1, 1),
            data_fim=date(2025, 12, 31),
        )
        svc = AnaliseObraService(self.obra, periodo=p)
        out = svc.build_payload()
        self.assertIn("controle", out)
        self.assertIn("suprimentos", out)
        self.assertIn("diario", out)
        self.assertIn("heatmap", out)
        self.assertEqual(out["controle"]["origem"], "mapa_controle_ambiente")
        self.assertIn("ranking_progressao_meta", out["controle"])
        self.assertIn("progressao_eixos_completo", out["controle"])
        self.assertIn("progresso_blocos", out["controle"])
        self.assertIn("atividades_mais_criticas", out["controle"])
        c = out["controle"]
        self.assertGreaterEqual(
            len(c["progressao_eixos_completo"]),
            len(c["blocos_mais_atrasados"]),
        )
        self.assertGreaterEqual(len(c["progresso_blocos"]), len(c["blocos_mais_atrasados"]))
        self.assertTrue(c["atividades_mais_criticas"])
        self.assertEqual(out["suprimentos"]["origem"], "mapa_suprimentos")
        self.assertIn("celulas", out["heatmap"])

    def test_payload_trackhub_pendencias(self):
        User = get_user_model()
        user = User.objects.create_user(username="th_bi_test", password="x")
        hoje = date.today()
        p_vencida = Pendencia.objects.create(
            obra=self.obra,
            titulo="Licença vencida",
            status="aberta",
            tipo="documento",
            criado_por=user,
            prazo=hoje - timedelta(days=10),
        )
        p_andamento = Pendencia.objects.create(
            obra=self.obra,
            titulo="Pagamento fornecedor",
            status="em_andamento",
            tipo="financeiro",
            criado_por=user,
        )
        Pendencia.objects.create(
            obra=self.obra,
            titulo="Encerrada",
            status="concluida",
            tipo="tarefa",
            criado_por=user,
        )
        p_concluida_recente = Pendencia.objects.create(
            obra=self.obra,
            titulo="Concluída recente",
            status="concluida",
            tipo="operacional",
            criado_por=user,
        )
        Pendencia.objects.filter(pk=p_concluida_recente.pk).update(
            updated_at=timezone.now() - timedelta(days=5)
        )
        p_concluida_antiga = Pendencia.objects.create(
            obra=self.obra,
            titulo="Concluída antiga",
            status="concluida",
            tipo="documento",
            criado_por=user,
        )
        Pendencia.objects.filter(pk=p_concluida_antiga.pk).update(
            updated_at=timezone.now() - timedelta(days=45)
        )
        EtapaPendencia.objects.create(
            pendencia=p_vencida,
            titulo="Etapa 1",
            status="pendente",
            responsavel_interno=user,
            ordem=1,
        )
        EtapaPendencia.objects.create(
            pendencia=p_andamento,
            titulo="Etapa 2",
            status="pendente",
            responsavel_interno=user,
            ordem=1,
        )
        EtapaPendencia.objects.create(
            pendencia=p_andamento,
            titulo="Etapa concluída",
            status="concluida",
            ordem=2,
        )

        p = AnaliseObraPeriodo(data_inicio=date(2025, 1, 1), data_fim=date(2025, 12, 31))
        out = AnaliseObraService(self.obra, periodo=p).build_payload()
        self.assertIn("trackhub", out)
        th = out["trackhub"]
        self.assertEqual(th["resumo"]["total_aberto"], 2)
        self.assertEqual(th["resumo"]["vencidas"], 1)
        self.assertEqual(th["resumo"]["em_andamento"], 1)
        self.assertEqual(th["resumo"]["concluidas_30d"], 2)
        self.assertEqual(len(th["por_tipo"]), 2)
        self.assertEqual(th["por_tipo"][0]["total"], 1)
        self.assertEqual(th["responsaveis"][0]["total"], 2)
        self.assertEqual(len(th["mais_atrasadas"]), 1)
        self.assertEqual(th["mais_atrasadas"][0]["dias_atraso"], 10)

        sec = AnaliseObraService(self.obra, periodo=p).build_section("trackhub")
        self.assertIn("trackhub", sec)

    def test_filtro_bloco_reduz_itens(self):
        p = AnaliseObraPeriodo(data_inicio=date(2025, 1, 1), data_fim=date(2025, 12, 31))
        f = AnaliseObraFilters(bloco="B2")
        svc = AnaliseObraService(self.obra, periodo=p, filtros=f)
        out = svc.build_payload()
        self.assertEqual(out["controle"]["kpis"]["total_itens"], 0)

        f2 = AnaliseObraFilters(bloco="B1")
        svc2 = AnaliseObraService(self.obra, periodo=p, filtros=f2)
        out2 = svc2.build_payload()
        self.assertEqual(out2["controle"]["kpis"]["total_itens"], 2)
        self.assertAlmostEqual(out2["controle"]["kpis"]["percentual_medio"], 52.5, places=1)

    def test_filtro_status_servico_por_coluna_total(self):
        _criar_ambiente_mapa(
            self.obra,
            [
                ["BLOCO", "PAVIMENTO", "APTO", "Pintura", "Total"],
                ["B1", "3", "U1", "25%", "52.5"],
                ["B2", "1", "U2", "100%", "100"],
            ],
            nome="Mapa status filtro",
            replace_existing=True,
        )
        p = AnaliseObraPeriodo(data_inicio=date(2025, 1, 1), data_fim=date(2025, 12, 31))

        svc_andamento = AnaliseObraService(self.obra, periodo=p, filtros=AnaliseObraFilters(status_servico="em_andamento"))
        out_andamento = svc_andamento.build_payload()
        self.assertEqual(out_andamento["controle"]["kpis"]["total_itens"], 1)

        svc_concluido = AnaliseObraService(self.obra, periodo=p, filtros=AnaliseObraFilters(status_servico="concluido"))
        out_concluido = svc_concluido.build_payload()
        self.assertEqual(out_concluido["controle"]["kpis"]["total_itens"], 1)

    def test_apto_em_andamento_aparece_no_ranking(self):
        _criar_ambiente_mapa(
            self.obra,
            [
                ["BLOCO", "PAVIMENTO", "APTO", "Instalação", "Total"],
                ["D", "2", "U9", "50%", "50"],
            ],
            nome="Mapa em andamento",
            replace_existing=True,
        )
        p = AnaliseObraPeriodo(data_inicio=date(2025, 1, 1), data_fim=date(2025, 12, 31))
        out = AnaliseObraService(self.obra, periodo=p).build_payload()
        self.assertGreater(out["controle"]["kpis"]["em_andamento"], 0)
        blocos = out["controle"]["blocos_mais_atrasados"]
        self.assertTrue(any(b["bloco"] == "D" and b["percentual_medio"] > 0 for b in blocos))

    def test_blocos_mais_atrasados_usam_rotulo_mais_frequente(self):
        _criar_ambiente_mapa(
            self.obra,
            [
                ["BLOCO", "PAVIMENTO", "APTO", "Ativ", "Total"],
                ["d", "9", "A", "", "5"],
                ["d", "9", "B", "", "5"],
                ["D", "9", "C", "", "5"],
            ],
            nome="Mapa votos bloco",
            replace_existing=True,
        )
        p = AnaliseObraPeriodo(data_inicio=date(2025, 1, 1), data_fim=date(2025, 12, 31))
        out = AnaliseObraService(self.obra, periodo=p).build_payload()
        row = next((b for b in out["controle"]["blocos_mais_atrasados"] if b.get("bloco_norm") == "D"), None)
        self.assertIsNotNone(row)
        self.assertEqual(row["bloco"], "d")
        self.assertEqual(row["amostras"], 3)

    def test_dois_setores_mesmo_codigo_bloco_geram_duas_linhas_no_ranking(self):
        _criar_ambiente_mapa(
            self.obra,
            [
                ["SETOR", "BLOCO", "PAVIMENTO", "APTO", "Ativ", "Total"],
                ["Torre A", "D", "1", "101", "", "10"],
                ["Torre B", "D", "1", "102", "", "90"],
            ],
            nome="Mapa dois setores",
            replace_existing=True,
        )
        p = AnaliseObraPeriodo(data_inicio=date(2025, 1, 1), data_fim=date(2025, 12, 31))
        out = AnaliseObraService(self.obra, periodo=p).build_payload()
        self.assertEqual(out["controle"]["agrupamento_eixo"], "setor_bloco")
        atrasados = out["controle"]["blocos_mais_atrasados"]
        rotulos = {x["rotulo"] for x in atrasados}
        self.assertTrue(len([x for x in atrasados if x.get("bloco_norm") == "D"]) >= 2)
        self.assertGreaterEqual(len(rotulos.intersection({"Torre A · D", "Torre B · D"})), 2)

    def test_piores_diversificam_por_setor(self):
        """Com vários setores, o ranking não pode ser só o setor com mais blocos piores."""
        rows = [
            {"rotulo": "AC · A", "setor_norm": "AREA COMUM", "bloco_norm": "A", "percentual_medio": 1.0, "setor": "ÁREA COMUM", "bloco": "A", "amostras": 1},
            {"rotulo": "AC · B", "setor_norm": "AREA COMUM", "bloco_norm": "B", "percentual_medio": 1.1, "setor": "ÁREA COMUM", "bloco": "B", "amostras": 1},
            {"rotulo": "AC · C", "setor_norm": "AREA COMUM", "bloco_norm": "C", "percentual_medio": 1.2, "setor": "ÁREA COMUM", "bloco": "C", "amostras": 1},
            {"rotulo": "AC · D", "setor_norm": "AREA COMUM", "bloco_norm": "D", "percentual_medio": 1.3, "setor": "ÁREA COMUM", "bloco": "D", "amostras": 1},
            {"rotulo": "HAB · X", "setor_norm": "HABITACAO", "bloco_norm": "X", "percentual_medio": 8.0, "setor": "HABITAÇÃO", "bloco": "X", "amostras": 1},
        ]
        out = analise_obra_service_mod._diversificar_ranking_por_setor(
            rows,
            use_setor_grupo=True,
            max_total=8,
            max_por_setor=2,
            piores=True,
        )
        setores = {analise_obra_service_mod._quota_setor_key(r) for r in out}
        self.assertIn("AREA COMUM", setores)
        self.assertIn("HABITACAO", setores)

    def test_build_section_meta(self):
        svc = AnaliseObraService(self.obra)
        sec = svc.build_section("meta")
        self.assertIsNotNone(sec)
        self.assertIn("meta", sec)

    def test_drill_down_retorna_linhas(self):
        svc = AnaliseObraService(self.obra)
        d = svc.build_drill_down("B1", "3")
        self.assertTrue(d["controle"]["total_linhas"] >= 1)


class TestAnaliseObraApi(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Group.objects.get_or_create(name=GRUPOS.BI_DA_OBRA)

    def setUp(self):
        from django.contrib.auth import get_user_model

        User = get_user_model()
        self.client = Client()
        self.user = User.objects.create_user(username="u_analise", password="senha123")
        g = Group.objects.get(name=GRUPOS.BI_DA_OBRA)
        self.user.groups.add(g)
        self.obra = Obra.objects.create(codigo_sienge="TST-API", nome="API", ativa=True)
        self.project = Project.objects.create(
            name="P",
            code="TST-API",
            start_date=date(2024, 1, 1),
            end_date=date(2026, 12, 31),
            is_active=True,
        )
        ProjectMember.objects.get_or_create(user=self.user, project=self.project)

    def test_api_requer_login(self):
        url = reverse("suprimentos:analise_obra_api") + f"?obra={self.obra.id}"
        r = self.client.get(url, HTTP_ACCEPT="application/json")
        self.assertEqual(r.status_code, 401)

    def test_api_200_com_acesso(self):
        self.client.login(username="u_analise", password="senha123")
        url = reverse("suprimentos:analise_obra_api") + f"?obra={self.obra.id}&secao=meta"
        r = self.client.get(url, HTTP_ACCEPT="application/json")
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertTrue(data.get("success"))
        self.assertIn("data", data)

    def test_drilldown_api(self):
        _criar_ambiente_mapa(
            self.obra,
            [
                ["BLOCO", "PAVIMENTO", "APTO", "Ativ", "Total"],
                ["B1", "1", "101", "", "40"],
            ],
            nome="Mapa drill API",
            replace_existing=True,
        )
        self.client.login(username="u_analise", password="senha123")
        url = (
            reverse("suprimentos:analise_obra_drilldown_api")
            + f"?obra={self.obra.id}&bloco=B1&pavimento=1"
        )
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json().get("success"))


class TestOccurrenceSeverityHeuristic(TestCase):
    """Heurística de gravidade das ocorrências do diário (Análise da Obra)."""

    def test_evitar_acidentes_nao_e_critico(self):
        txt = (
            "CHUVAS: terraplanagem paralisada; movimentação interrompida para evitar acidentes."
        )
        self.assertEqual(_classify_occurrence_severity(txt, []), "alta")

    def test_acidente_com_vitima_e_critico(self):
        self.assertEqual(
            _classify_occurrence_severity("Queda de andaime; houve vítima encaminhada ao hospital.", []),
            "critica",
        )

    def test_queda_de_energia_nao_e_critico_geometrico(self):
        self.assertEqual(
            _classify_occurrence_severity("Queda de energia no canteiro; equipamentos parados.", []),
            "alta",
        )

    def test_prevenacao_remove_e_cai_para_alta_com_parada(self):
        self.assertEqual(
            _classify_occurrence_severity("Obra parada. Prevenção de acidentes reforçada.", []),
            "alta",
        )

    def test_pendencia_e_media(self):
        self.assertEqual(
            _classify_occurrence_severity("Pendência de alinhamento com projeto arquitetônico.", []),
            "media",
        )

    def test_atraso_leve_e_media_nao_alta(self):
        self.assertEqual(
            _classify_occurrence_severity("Atraso leve na liberação do concreto.", []),
            "media",
        )

    def test_somente_chuva_sem_paralisacao_e_baixa(self):
        self.assertEqual(
            _classify_occurrence_severity("Periodo com chuva e umidade alta.", []),
            "baixa",
        )

    def test_chuva_com_paralisacao_e_alta(self):
        self.assertEqual(
            _classify_occurrence_severity("Chuva intensa; terraplanagem paralisada.", []),
            "alta",
        )

