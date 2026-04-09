"""
Testes do serviço e da API **Análise da Obra**.

Rodar: python manage.py test suprimentos.tests.test_analise_obra -v 2
"""

from datetime import date
from decimal import Decimal

from django.contrib.auth.models import Group
from django.test import Client, TestCase
from django.urls import reverse

from mapa_obras.models import Obra

from core.models import Project, ProjectMember
from suprimentos.models import ItemMapaServico
from suprimentos.services.analise_obra_service import (
    AnaliseObraFilters,
    AnaliseObraPeriodo,
    AnaliseObraService,
)


class TestAnaliseObraService(TestCase):
    def setUp(self):
        self.obra = Obra.objects.create(codigo_sienge="TST-ANL", nome="Obra Análise", ativa=True)
        ItemMapaServico.objects.create(
            obra=self.obra,
            chave_uid="k1",
            atividade="Armação",
            bloco="B1",
            pavimento="3",
            status_percentual=Decimal("0.25"),
        )
        ItemMapaServico.objects.create(
            obra=self.obra,
            chave_uid="k2",
            atividade="Concreto",
            bloco="B1",
            pavimento="3",
            status_percentual=Decimal("0.80"),
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
        self.assertEqual(out["controle"]["origem"], "mapa_controle_execucao")
        self.assertEqual(out["suprimentos"]["origem"], "mapa_suprimentos")
        self.assertIn("celulas", out["heatmap"])

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

    def test_filtro_status_servico_considera_percentual_0_100_e_0_1(self):
        ItemMapaServico.objects.create(
            obra=self.obra,
            chave_uid="k3",
            atividade="Pintura",
            bloco="B2",
            pavimento="1",
            status_percentual=Decimal("100"),
        )
        p = AnaliseObraPeriodo(data_inicio=date(2025, 1, 1), data_fim=date(2025, 12, 31))

        svc_andamento = AnaliseObraService(self.obra, periodo=p, filtros=AnaliseObraFilters(status_servico="em_andamento"))
        out_andamento = svc_andamento.build_payload()
        self.assertEqual(out_andamento["controle"]["kpis"]["total_itens"], 2)

        svc_concluido = AnaliseObraService(self.obra, periodo=p, filtros=AnaliseObraFilters(status_servico="concluido"))
        out_concluido = svc_concluido.build_payload()
        self.assertEqual(out_concluido["controle"]["kpis"]["total_itens"], 1)

    def test_status_texto_andando_parado_gera_avanco_e_em_andamento(self):
        ItemMapaServico.objects.create(
            obra=self.obra,
            chave_uid="k4",
            atividade="Instalação",
            bloco="D",
            pavimento="2",
            status_percentual=None,
            status_texto="Andando / parado",
        )
        p = AnaliseObraPeriodo(data_inicio=date(2025, 1, 1), data_fim=date(2025, 12, 31))
        out = AnaliseObraService(self.obra, periodo=p).build_payload()
        self.assertGreater(out["controle"]["kpis"]["em_andamento"], 0)
        blocos = out["controle"]["blocos_mais_atrasados"]
        self.assertTrue(any(b["bloco"] == "D" and b["percentual_medio"] > 0 for b in blocos))

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
        Group.objects.get_or_create(name="Mapa de Suprimentos")

    def setUp(self):
        from django.contrib.auth import get_user_model

        User = get_user_model()
        self.client = Client()
        self.user = User.objects.create_user(username="u_analise", password="senha123")
        g = Group.objects.get(name="Mapa de Suprimentos")
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
        self.client.login(username="u_analise", password="senha123")
        url = (
            reverse("suprimentos:analise_obra_drilldown_api")
            + f"?obra={self.obra.id}&bloco=B1&pavimento=1"
        )
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json().get("success"))

