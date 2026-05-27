"""
Testes do BI da Obra com fonte AmbienteVersao.layout (mapa de controle por ambiente).

Rodar: python manage.py test suprimentos.tests.test_analise_obra_ambiente -v 2
"""

from datetime import date, timedelta

from django.test import TestCase
from django.utils import timezone

from mapa_obras.models import Obra
from painel_operacional.models import AmbienteOperacional, AmbienteTipo, AmbienteVersao, VersaoEstado
from suprimentos.services.analise_obra_service import (
    AnaliseObraPeriodo,
    AnaliseObraService,
    MENSAGEM_CONTROLE_SEM_MAPA,
)


def _layout_from_rows(rows: list[list]) -> dict:
    return {
        "sections": [
            {
                "id": "matriz",
                "kind": "matrix_table",
                "data": {"rows": rows, "mapaControleTemplate": True},
            }
        ]
    }


def _criar_ambiente_mapa(
    obra: Obra,
    rows: list[list],
    *,
    nome: str = "Mapa controle BI",
    replace_existing: bool = False,
) -> AmbienteOperacional:
    if replace_existing:
        AmbienteOperacional.objects.filter(
            obra=obra,
            tipo=AmbienteTipo.MAPA_CONTROLE,
            ativo=True,
        ).update(ativo=False)
    ambiente = AmbienteOperacional.objects.create(
        obra=obra,
        nome=nome,
        tipo=AmbienteTipo.MAPA_CONTROLE,
        ativo=True,
    )
    AmbienteVersao.objects.create(
        ambiente=ambiente,
        numero=1,
        estado=VersaoEstado.DRAFT,
        layout=_layout_from_rows(rows),
    )
    return ambiente


class TestAnaliseObraAmbienteLayout(TestCase):
    def setUp(self):
        self.obra = Obra.objects.create(codigo_sienge="AMB-BI-001", nome="Obra Ambiente BI", ativa=True)
        self.header = ["BLOCO", "PAVIMENTO", "APTO", "Armação", "Concreto", "Total"]
        self.rows = [
            self.header,
            ["B1", "1", "101", "25%", "80%", "40"],
            ["B1", "1", "102", "100%", "100%", "100"],
            ["B2", "2", "201", "0%", "0%", "0"],
        ]
        _criar_ambiente_mapa(self.obra, self.rows)

    def test_obra_com_ambiente_retorna_dados_corretos(self):
        svc = AnaliseObraService(
            self.obra,
            periodo=AnaliseObraPeriodo(data_inicio=date(2025, 1, 1), data_fim=date(2025, 12, 31)),
        )
        controle = svc._build_controle()
        self.assertFalse(controle.get("sem_dados"))
        # 6 células de atividade (2 por apto × 3 aptos); Total do JSON é ignorado.
        self.assertEqual(controle["kpis"]["total_itens"], 6)
        self.assertAlmostEqual(controle["kpis"]["percentual_medio"], 50.83, places=1)
        self.assertEqual(controle["kpis"]["concluidos"], 2)
        self.assertEqual(controle["kpis"]["em_andamento"], 2)
        self.assertEqual(controle["kpis"]["nao_iniciados"], 2)
        self.assertTrue(controle["blocos_mais_atrasados"])
        piores = controle["blocos_mais_atrasados"][0]
        self.assertEqual(piores["bloco"], "B2")
        self.assertEqual(piores["percentual_medio"], 0.0)

    def test_obra_sem_ambiente_retorna_sem_dados(self):
        obra_vazia = Obra.objects.create(codigo_sienge="AMB-VAZIA", nome="Sem mapa", ativa=True)
        svc = AnaliseObraService(obra_vazia)
        controle = svc._build_controle()
        self.assertTrue(controle.get("sem_dados"))
        self.assertEqual(controle["mensagem"], MENSAGEM_CONTROLE_SEM_MAPA)
        self.assertIsNone(controle["kpis"]["percentual_medio"])
        payload = svc.build_payload()
        self.assertIn("suprimentos", payload)
        self.assertIn("diario", payload)

    def test_dois_ambientes_usa_mais_recente(self):
        rows_antigo = [
            self.header,
            ["BX", "9", "901", "", "", "10"],
        ]
        rows_novo = [
            self.header,
            ["BN", "3", "301", "", "", "90"],
        ]
        antigo = _criar_ambiente_mapa(self.obra, rows_antigo, nome="Mapa antigo")
        novo = _criar_ambiente_mapa(self.obra, rows_novo, nome="Mapa novo")
        AmbienteOperacional.objects.filter(pk=antigo.pk).update(
            updated_at=timezone.now() - timedelta(days=2)
        )
        AmbienteOperacional.objects.filter(pk=novo.pk).update(updated_at=timezone.now())

        svc = AnaliseObraService(self.obra)
        bundle = svc.controle_base_from_ambiente(self.obra)
        self.assertIsNotNone(bundle)
        self.assertEqual(bundle["ambiente_id"], novo.id)
        controle = svc._build_controle()
        blocos = {b["bloco"] for b in controle["blocos_mais_atrasados"]}
        self.assertIn("BN", blocos)
        self.assertNotIn("BX", blocos)

    def test_isolamento_obra_a_nao_ve_obra_b(self):
        obra_b = Obra.objects.create(codigo_sienge="AMB-B", nome="Obra B", ativa=True)
        _criar_ambiente_mapa(
            obra_b,
            [
                self.header,
                ["ZB", "1", "999", "", "", "99"],
            ],
            nome="Mapa só B",
        )

        svc_a = AnaliseObraService(self.obra)
        controle_a = svc_a._build_controle()
        blocos_a = {b["bloco"] for b in controle_a.get("blocos_mais_atrasados") or []}
        self.assertIn("B1", blocos_a)
        self.assertNotIn("ZB", blocos_a)

        svc_b = AnaliseObraService(obra_b)
        controle_b = svc_b._build_controle()
        self.assertEqual(controle_b["kpis"]["total_itens"], 2)
        self.assertAlmostEqual(controle_b["kpis"]["percentual_medio"], 0.0, places=1)

    def test_heatmap_e_drilldown_usam_layout(self):
        svc = AnaliseObraService(self.obra)
        heatmap = svc._build_heatmap()
        self.assertTrue(heatmap.get("celulas"))
        drill = svc.build_drill_down("B1", "1")
        self.assertGreaterEqual(drill["controle"]["total_linhas"], 1)
        self.assertAlmostEqual(drill["controle"]["percentual_medio_local"], 76.2, places=1)

    def test_percentual_medio_ignora_coluna_total_do_json(self):
        _criar_ambiente_mapa(
            self.obra,
            [
                self.header,
                ["Entregaguas", "1", "U1", "5%", "8%", "99"],
            ],
            nome="Mapa ignora total json",
            replace_existing=True,
        )
        svc = AnaliseObraService(self.obra)
        controle = svc._build_controle()
        self.assertAlmostEqual(controle["kpis"]["percentual_medio"], 6.5, places=1)
        self.assertEqual(controle["kpis"]["total_itens"], 2)

    def test_cache_stamp_muda_quando_ambiente_atualizado(self):
        svc = AnaliseObraService(self.obra)
        stamp1 = svc.controle_ambiente_cache_stamp()
        amb = AmbienteOperacional.objects.filter(obra=self.obra, tipo=AmbienteTipo.MAPA_CONTROLE).order_by(
            "-updated_at"
        ).first()
        AmbienteOperacional.objects.filter(pk=amb.pk).update(updated_at=timezone.now() + timedelta(seconds=5))
        svc2 = AnaliseObraService(self.obra)
        stamp2 = svc2.controle_ambiente_cache_stamp()
        self.assertNotEqual(stamp1, stamp2)
