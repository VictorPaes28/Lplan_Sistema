"""Testes do BI da Obra (serviço, snapshots, API e página)."""

from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth.models import Group, User
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from accounts.groups import GRUPOS
from core.models import Project, ProjectMember
from mapa_obras.models import Obra
from suprimentos.models import BiObraKpiSnapshot
from suprimentos.services.analise_obra_service import (
    AnaliseObraPeriodo,
    AnaliseObraService,
    _parse_layout_rows_semantic,
)


@override_settings(MAPA_SUPRIMENTOS_MANUAL=True)
class TestAnaliseObraService(TestCase):
    def setUp(self):
        self.project = Project.objects.create(
            name="Obra BI Teste",
            code="BI-TEST",
            is_active=True,
            start_date=date(2025, 1, 1),
            end_date=date(2026, 12, 31),
        )
        self.obra = Obra.objects.create(
            codigo_sienge="BI-TEST",
            nome="Obra BI Teste",
            ativa=True,
            project=self.project,
        )
        self.periodo = AnaliseObraPeriodo(
            data_inicio=date(2025, 6, 1),
            data_fim=date(2025, 6, 30),
        )
        self.user = User.objects.create_user("biuser", "bi@test.com", "secret")
        ProjectMember.objects.create(project=self.project, user=self.user)
        Group.objects.get_or_create(name=GRUPOS.BI_DA_OBRA)
        self.user.groups.add(Group.objects.get(name=GRUPOS.BI_DA_OBRA))
        self.client.force_login(self.user)
        session = self.client.session
        session["obra_id"] = self.obra.id
        session.save()

    def _service(self):
        return AnaliseObraService(self.obra, periodo=self.periodo)

    def test_shell_payload_meta_fields(self):
        payload = self._service().build_shell_payload()
        meta = payload["meta"]
        self.assertEqual(meta["obra_id"], self.obra.id)
        self.assertIn("gestao_obra_id", meta)
        self.assertIn("sparklines", meta)
        self.assertIn("acoes_prioritarias", meta)
        self.assertIn("hero_drawer", meta)
        self.assertIn("avanco", meta["hero_drawer"])
        self.assertEqual(len(meta["sparklines"]["avanco"]), 7)

    def test_record_kpi_snapshot_cria_registro(self):
        svc = self._service()
        controle = {"kpis": {"percentual_medio": 33.3}}
        restricoes = {"kpis": {"total_aberto": 2}}
        gestcontroll = {"kpis": {"pendentes_count": 1, "pendentes_valor": 0}}
        diario = {"vinculo_projeto": True, "rdos_resumo": {"pendentes_rdos_count": 0}}
        svc._record_kpi_snapshot(
            project=self.project,
            controle=controle,
            restricoes=restricoes,
            gestcontroll=gestcontroll,
            diario=diario,
        )
        snap = BiObraKpiSnapshot.objects.get(obra=self.obra, data=timezone.localdate())
        self.assertEqual(float(snap.avanco_fisico_pct), 33.3)
        self.assertEqual(snap.restricoes_abertas, 2)

    def test_sparklines_usam_snapshots(self):
        hoje = timezone.localdate()
        for i in range(7):
            d = hoje - timedelta(days=6 - i)
            BiObraKpiSnapshot.objects.create(
                obra=self.obra,
                data=d,
                avanco_fisico_pct=Decimal(str(10 + i * 5)),
                restricoes_abertas=i,
                pendentes_gestcontroll=0,
                rdos_pendentes=0,
                ocorrencias_dia=i,
            )
        svc = AnaliseObraService(
            self.obra,
            periodo=AnaliseObraPeriodo(data_inicio=hoje - timedelta(days=30), data_fim=hoje),
        )
        lines = svc._build_sparklines_hero(
            self.project,
            {"kpis": {"percentual_medio": 40}},
            {"kpis": {"total_aberto": 0}},
            {"kpis": {"pendentes_count": 0}},
            {"vinculo_projeto": True, "rdos_resumo": {}},
        )
        self.assertEqual(lines["avanco"][0], 10.0)
        self.assertEqual(lines["avanco"][-1], 40.0)

    def test_parse_layout_respeita_activity_cols_nao_contiguas(self):
        """Colunas movidas/inseridas: índices vêm do importMeta, não do intervalo posicional."""
        layout = {
            "sections": [
                {
                    "kind": "matrix_table",
                    "data": {
                        "rows": [
                            ["BLOCO", "PAVIMENTO", "APTO", "Alvenaria", "Vazio", "Revest", "Total"],
                            ["A", "1", "101", "50", "", "80", ""],
                        ],
                        "importMeta": {
                            "axis_cols_interpreted": [0, 1, 2],
                            "axis_headers_interpreted": ["BLOCO", "PAVIMENTO", "APTO"],
                            "activity_cols_interpreted": [3, 5],
                        },
                    },
                }
            ],
        }
        rows = _parse_layout_rows_semantic(layout)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["atividades"].get("Alvenaria"), "50")
        self.assertEqual(rows[0]["atividades"].get("Revest"), "80")
        self.assertNotIn("Vazio", rows[0]["atividades"])

    def test_parse_layout_forward_fill_apos_movimentacao_linhas(self):
        """Linhas de continuação herdam bloco/pav/apto após reorder no editor."""
        layout = {
            "sections": [
                {
                    "kind": "matrix_table",
                    "data": {
                        "rows": [
                            ["BLOCO", "PAVIMENTO", "APTO", "Serviço", "Total"],
                            ["A", "1", "101", "50", ""],
                            ["", "", "", "60", ""],
                        ],
                        "importMeta": {
                            "axis_cols_interpreted": [0, 1, 2],
                            "activity_cols_interpreted": [3],
                        },
                    },
                }
            ],
        }
        rows = _parse_layout_rows_semantic(layout)
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[1]["apto"], "101")
        self.assertEqual(rows[1]["atividades"].get("Serviço"), "60")

    def test_analise_obra_page_ok(self):
        url = reverse("engenharia:analise_obra")
        r = self.client.get(url, {"obra": self.obra.id})
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "BI da Obra")
        self.assertContains(r, "Mais filtros")
        self.assertContains(r, "Todas as obras")

    def test_analise_obra_portfolio_ok(self):
        BiObraKpiSnapshot.objects.create(
            obra=self.obra,
            data=timezone.localdate(),
            avanco_fisico_pct=Decimal("42.5"),
            restricoes_abertas=1,
            pendentes_gestcontroll=0,
            rdos_pendentes=0,
            ocorrencias_dia=0,
        )
        url = reverse("engenharia:analise_obra_portfolio")
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Portfólio de obras")
        self.assertContains(r, "Obra BI Teste")
        self.assertContains(r, "bi-portfolio-card")
        self.assertContains(r, "Execução")
        self.assertContains(r, "Resolver agora")
        self.assertContains(r, "bi-btn-resolver")
        self.assertContains(r, "status=atrasados")
        self.assertContains(r, "mobile-app-header")
        self.assertContains(r, "filtro-periodo-preset")
        self.assertContains(r, "TrackHub")

    def test_analise_obra_portfolio_periodo_60(self):
        url = reverse("engenharia:analise_obra_portfolio")
        r = self.client.get(url, {"periodo": "60"})
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'value="60" selected')

    def test_analise_obra_portfolio_somente_alerta(self):
        url = reverse("engenharia:analise_obra_portfolio")
        r = self.client.get(url, {"somente_alerta": "1"})
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Portfólio de obras")
        self.assertContains(r, "bi-portfolio-card")

    def test_analise_obra_resumo_ok(self):
        url = reverse("engenharia:analise_obra_resumo")
        r = self.client.get(url, {"obra": self.obra.id})
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Resumo BI")

    def test_analise_obra_api_meta(self):
        url = reverse("suprimentos:analise_obra_api")
        r = self.client.get(url, {"obra": self.obra.id, "secao": "meta"})
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertTrue(data.get("success"))
        self.assertIn("gestao_obra_id", data["data"]["meta"])

    def test_analise_obra_api_heatmap(self):
        url = reverse("suprimentos:analise_obra_api")
        r = self.client.get(url, {"obra": self.obra.id, "secao": "heatmap"})
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertTrue(data.get("success"))
        self.assertIn("heatmap", data["data"])

    def test_periodo_preset_30_dias(self):
        from suprimentos.views_analise_obra import _effective_periodo_analise

        hoje = timezone.localdate()
        ini, fim = _effective_periodo_analise(
            type("R", (), {"GET": {"periodo": "30"}})(),
            self.obra,
        )
        self.assertEqual(fim, hoje)
        self.assertEqual((fim - ini).days, 30)

    def test_periodo_preset_todos(self):
        from suprimentos.views_analise_obra import _effective_periodo_analise

        req = type("R", (), {"GET": {"periodo": "todos"}})()
        ini, fim = _effective_periodo_analise(req, self.obra)
        self.assertEqual(ini, self.project.start_date)
        self.assertEqual(fim, timezone.localdate())
