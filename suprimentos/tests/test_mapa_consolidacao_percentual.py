"""Consolidação de percentuais no Mapa de Controle dedicado (AmbienteProvider)."""

from __future__ import annotations

import json
from datetime import date

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import Client, TestCase
from django.urls import reverse

from accounts.groups import GRUPOS
from core.models import Project, ProjectMember
from mapa_obras.models import Obra


User = get_user_model()


class MapaConsolidacaoPercentualTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.grupo_fo, _ = Group.objects.get_or_create(name=GRUPOS.FERRAMENTA_OPERACIONAL)
        cls.grupo_mc, _ = Group.objects.get_or_create(name=GRUPOS.MAPA_CONTROLE)
        cls.user = User.objects.create_user(
            username="teste_consolidacao_mapa",
            email="consolidacao@teste.com",
            password="senha123",
        )
        cls.user.groups.add(cls.grupo_fo, cls.grupo_mc)
        cls.obra = Obra.objects.create(
            codigo_sienge="OBR-CONS-001",
            nome="Obra Consolidacao",
            ativa=True,
        )
        cls.project = Project.objects.create(
            name="Projeto Consolidacao",
            code="OBR-CONS-001",
            start_date=date(2024, 1, 1),
            end_date=date(2026, 12, 31),
            is_active=True,
        )
        ProjectMember.objects.get_or_create(user=cls.user, project=cls.project)

    def setUp(self):
        self.client = Client()
        self.client.login(username="teste_consolidacao_mapa", password="senha123")

    def _url(self, name: str, *args) -> str:
        base = reverse(name, args=args if args else None)
        sep = "&" if "?" in base else "?"
        return f"{base}{sep}obra={self.obra.id}"

    def _criar_ambiente_mapa(self, nome: str) -> int:
        response = self.client.post(
            self._url("suprimentos:po_api_criar_ambiente"),
            data=json.dumps({"nome": nome, "tipo": "mapa_controle"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200, response.content)
        return int(response.json()["item"]["id"])

    def _detalhe(self, ambiente_id: int) -> dict:
        response = self.client.get(self._url("suprimentos:po_api_detalhe_ambiente", ambiente_id))
        self.assertEqual(response.status_code, 200, response.content)
        return response.json()

    def _primeira_matriz_section(self, layout: dict) -> dict:
        for section in layout.get("sections") or []:
            if str(section.get("kind") or "").strip() in {"matrix_table", "table"}:
                return section
        return {}

    def _salvar_layout(self, ambiente_id: int, layout: dict) -> None:
        response = self.client.post(
            self._url("suprimentos:po_api_salvar_rascunho", ambiente_id),
            data=json.dumps({"layout": layout, "metadados": {}}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200, response.content)
        self.assertTrue(response.json().get("success"), response.content)

    def _abrir_mapa(self, ambiente_id: int, **extra):
        payload = {"obra": self.obra.id, "ambiente_id": ambiente_id, "embed": 1}
        payload.update(extra)
        response = self.client.get(reverse("engenharia:mapa_controle"), data=payload)
        self.assertEqual(response.status_code, 200, response.content)
        return response

    def _aplicar_layout_manual(self, ambiente_id: int, body_rows: list[list[str]]) -> None:
        detalhe = self._detalhe(ambiente_id)
        layout = detalhe.get("versao", {}).get("layout") or detalhe.get("draft", {}).get("layout") or {}
        section = self._primeira_matriz_section(layout)
        self.assertTrue(section, "Seção matriz ausente.")
        section.setdefault("data", {})
        section["data"]["rows"] = [
            ["BLOCO", "PAVIMENTO", "APTO", "Atividade 1", "Total"],
            *body_rows,
        ]
        section["data"]["importMeta"] = {
            "strategy": "manual_template",
            "axis_cols_interpreted": [0, 1, 2],
            "axis_headers_interpreted": ["BLOCO", "PAVIMENTO", "APTO"],
            "activity_cols_interpreted": [3],
            "activity_headers_interpreted": ["Atividade 1"],
            "row_axis_key": "bloco",
        }
        self._salvar_layout(ambiente_id, layout)

    def test_pavimento_consolida_media_das_unidades(self):
        ambiente_id = self._criar_ambiente_mapa("Pavimento media UND")
        self._aplicar_layout_manual(
            ambiente_id,
            [
                ["Bloco A", "Pavimento 01", "UND 101", "100%", ""],
                ["Bloco A", "Pavimento 01", "UND 102", "0%", ""],
            ],
        )
        resp = self._abrir_mapa(ambiente_id, bloco="Bloco A")
        matrix = resp.context["matrix"]
        self.assertEqual(matrix.get("mode"), "pavimento")
        pav = next(r for r in matrix["rows"] if r.get("row_label") == "Pavimento 01")
        self.assertEqual(pav["cells"][0]["pct"], 50)
        self.assertEqual(pav["total"], 50)
        self.assertEqual(matrix["totais"][0]["pct"], 50)

    def test_pavimento_sem_lancamento_mostra_zero_nao_hifen(self):
        """Pavimento com UND mas sem % nas colunas → 0%, não traço N/A em toda a linha."""
        ambiente_id = self._criar_ambiente_mapa("Pav vazio")
        detalhe = self._detalhe(ambiente_id)
        layout = detalhe.get("versao", {}).get("layout") or detalhe.get("draft", {}).get("layout") or {}
        section = self._primeira_matriz_section(layout)
        section.setdefault("data", {})
        section["data"]["rows"] = [
            ["BLOCO", "PAVIMENTO", "APTO", "Atividade 9", "Total"],
            ["teste", "pavimento teste", "U1", "", ""],
            ["teste", "pavimento teste2", "U2", "17,5%", ""],
        ]
        section["data"]["importMeta"] = {
            "strategy": "manual_template",
            "axis_cols_interpreted": [0, 1, 2],
            "axis_headers_interpreted": ["BLOCO", "PAVIMENTO", "APTO"],
            "activity_cols_interpreted": [3],
            "activity_headers_interpreted": ["Atividade 9"],
            "row_axis_key": "bloco",
        }
        self._salvar_layout(ambiente_id, layout)
        resp = self._abrir_mapa(ambiente_id, bloco="teste")
        pav1 = next(r for r in resp.context["matrix"]["rows"] if r.get("row_label") == "pavimento teste")
        self.assertEqual(pav1["cells"][0]["pct"], 0)
        self.assertNotEqual(pav1["cells"][0]["pct"], None)

    def test_bloco_consolida_media_dos_pavimentos_nao_apto_plano(self):
        """Bloco = média dos pavimentos (0% e 17,5% → 8,8%), não média plana de todos os aptos."""
        ambiente_id = self._criar_ambiente_mapa("Bloco via pav")
        detalhe = self._detalhe(ambiente_id)
        layout = detalhe.get("versao", {}).get("layout") or detalhe.get("draft", {}).get("layout") or {}
        section = self._primeira_matriz_section(layout)
        section.setdefault("data", {})
        act_cols = list(range(3, 13))
        headers = ["Atividade " + str(i + 1) for i in range(len(act_cols))]
        section["data"]["rows"] = [
            ["BLOCO", "PAVIMENTO", "APTO", *headers, "Total"],
            ["teste", "pavimento teste", "U1", *([""] * 8 + ["0%"] + [""] * 1), ""],
            ["teste", "pavimento teste2", "U2", *([""] * 8 + ["17,5%"] + [""] * 1), ""],
        ]
        section["data"]["importMeta"] = {
            "strategy": "manual_template",
            "axis_cols_interpreted": [0, 1, 2],
            "axis_headers_interpreted": ["BLOCO", "PAVIMENTO", "APTO"],
            "activity_cols_interpreted": act_cols,
            "activity_headers_interpreted": headers,
            "row_axis_key": "bloco",
        }
        self._salvar_layout(ambiente_id, layout)
        resp_pav = self._abrir_mapa(ambiente_id, bloco="teste")
        totais_pav = {t["atividade"]: t["pct"] for t in resp_pav.context["matrix"]["totais"]}
        self.assertAlmostEqual(float(totais_pav["Atividade 9"]), 8.75, places=2)
        resp_bloco = self._abrir_mapa(ambiente_id)
        bloco = next(r for r in resp_bloco.context["matrix"]["rows"] if r.get("row_label") == "teste")
        cell9 = next(c for c in bloco["cells"] if c.get("atividade") == "Atividade 9")
        self.assertAlmostEqual(float(cell9["pct"]), 8.8, places=1)

    def test_bloco_consolida_media_direta_de_todas_unidades(self):
        """Com vários pavimentos, média por pavimento coincide com média global de UNDs neste caso."""
        ambiente_id = self._criar_ambiente_mapa("Bloco media UND")
        self._aplicar_layout_manual(
            ambiente_id,
            [
                ["Bloco A", "Pavimento 01", "UND 101", "100%", ""],
                ["Bloco A", "Pavimento 01", "UND 102", "0%", ""],
                ["Bloco A", "Pavimento 02", "UND 201", "100%", ""],
                ["Bloco A", "Pavimento 02", "UND 202", "100%", ""],
            ],
        )
        resp = self._abrir_mapa(ambiente_id)
        matrix = resp.context["matrix"]
        self.assertEqual(matrix.get("mode"), "bloco")
        bloco = next(r for r in matrix["rows"] if r.get("row_label") == "Bloco A")
        self.assertEqual(bloco["cells"][0]["pct"], 75)
        self.assertEqual(bloco["total"], 75)

    def test_linha_estrutural_sem_apto_nao_entra_na_consolidacao(self):
        ambiente_id = self._criar_ambiente_mapa("Ignora estrutural")
        self._aplicar_layout_manual(
            ambiente_id,
            [
                ["Bloco A", "Pavimento 01", "", "90%", ""],
                ["Bloco A", "Pavimento 01", "UND 101", "0%", ""],
            ],
        )
        resp = self._abrir_mapa(ambiente_id, bloco="Bloco A")
        matrix = resp.context["matrix"]
        pav = next(r for r in matrix["rows"] if r.get("row_label") == "Pavimento 01")
        self.assertEqual(pav["cells"][0]["pct"], 0)
        self.assertEqual(pav["total"], 0)

    def test_celula_vazia_conta_como_zero_na_media(self):
        ambiente_id = self._criar_ambiente_mapa("Vazio zero")
        self._aplicar_layout_manual(
            ambiente_id,
            [
                ["Bloco A", "Pavimento 01", "UND 101", "100%", ""],
                ["Bloco A", "Pavimento 01", "UND 102", "", ""],
            ],
        )
        resp = self._abrir_mapa(ambiente_id, bloco="Bloco A")
        pav = next(r for r in resp.context["matrix"]["rows"] if r.get("row_label") == "Pavimento 01")
        self.assertEqual(pav["cells"][0]["pct"], 50)
        self.assertEqual(pav["total"], 50)

    def test_hifen_nao_aplicavel_fora_do_denominador(self):
        ambiente_id = self._criar_ambiente_mapa("Hifen NA")
        self._aplicar_layout_manual(
            ambiente_id,
            [
                ["Bloco A", "Pavimento 01", "UND 101", "100%", ""],
                ["Bloco A", "Pavimento 01", "UND 102", "-", ""],
            ],
        )
        resp = self._abrir_mapa(ambiente_id, bloco="Bloco A")
        pav = next(r for r in resp.context["matrix"]["rows"] if r.get("row_label") == "Pavimento 01")
        self.assertEqual(pav["cells"][0]["pct"], 100)
        self.assertEqual(pav["total"], 100)

    def test_misto_100_zero_hifen(self):
        ambiente_id = self._criar_ambiente_mapa("Misto NA")
        self._aplicar_layout_manual(
            ambiente_id,
            [
                ["Bloco A", "Pavimento 01", "UND 101", "100%", ""],
                ["Bloco A", "Pavimento 01", "UND 102", "0%", ""],
                ["Bloco A", "Pavimento 01", "UND 103", "-", ""],
            ],
        )
        resp = self._abrir_mapa(ambiente_id, bloco="Bloco A")
        pav = next(r for r in resp.context["matrix"]["rows"] if r.get("row_label") == "Pavimento 01")
        self.assertEqual(pav["cells"][0]["pct"], 50)
        self.assertEqual(pav["total"], 50)

    def test_todas_unidades_hifen_total_indeterminado(self):
        ambiente_id = self._criar_ambiente_mapa("So hifen")
        self._aplicar_layout_manual(
            ambiente_id,
            [
                ["Bloco A", "Pavimento 01", "UND 101", "-", ""],
                ["Bloco A", "Pavimento 01", "UND 102", "-", ""],
            ],
        )
        resp = self._abrir_mapa(ambiente_id, bloco="Bloco A")
        pav = next(r for r in resp.context["matrix"]["rows"] if r.get("row_label") == "Pavimento 01")
        self.assertIsNone(pav["cells"][0]["pct"])
        self.assertIsNone(pav["total"])

    def test_bloco_estrutural_sem_filhos_aparece_na_raiz(self):
        ambiente_id = self._criar_ambiente_mapa("Bloco estrutural raiz")
        self._aplicar_layout_manual(ambiente_id, [["Bloco Teste", "", "", "", ""]])
        resp = self._abrir_mapa(ambiente_id)
        matrix = resp.context["matrix"]
        self.assertEqual(matrix.get("mode"), "bloco")
        bloco = next((r for r in matrix["rows"] if r.get("row_label") == "Bloco Teste"), None)
        self.assertIsNotNone(bloco, "Bloco estrutural deve aparecer na raiz.")
        self.assertEqual(bloco["cells"][0]["pct"], 0)
        self.assertEqual(bloco["total"], 0)

    def test_pavimento_estrutural_sem_apto_aparece_no_bloco(self):
        ambiente_id = self._criar_ambiente_mapa("Pavimento estrutural")
        self._aplicar_layout_manual(
            ambiente_id,
            [
                ["Bloco A", "Pavimento 01", "", "", ""],
            ],
        )
        resp = self._abrir_mapa(ambiente_id, bloco="Bloco A")
        matrix = resp.context["matrix"]
        self.assertEqual(matrix.get("mode"), "pavimento")
        pav = next((r for r in matrix["rows"] if r.get("row_label") == "Pavimento 01"), None)
        self.assertIsNotNone(pav, "Pavimento estrutural deve aparecer dentro do bloco.")
        self.assertEqual(pav["cells"][0]["pct"], 0)
        self.assertEqual(pav["total"], 0)

    def test_camada_bloco_progresso_nao_multiplica_por_cem(self):
        ambiente_id = self._criar_ambiente_mapa("Progresso camada")
        self._aplicar_layout_manual(
            ambiente_id,
            [
                ["Bloco A", "Pavimento 01", "UND 101", "50%", ""],
            ],
        )
        resp = self._abrir_mapa(ambiente_id)
        bloco_layer = next(b for b in resp.context["layers"]["blocos"] if b.get("bloco") == "Bloco A")
        self.assertEqual(bloco_layer["progresso"], 50.0)

    def test_total_geral_na_ultima_coluna_nao_na_primeira_atividade(self):
        """Total geral (média dos lançamentos) fica no canto direito, não na coluna Atividade 1."""
        ambiente_id = self._criar_ambiente_mapa("Total geral coluna")
        detalhe = self._detalhe(ambiente_id)
        layout = detalhe.get("versao", {}).get("layout") or detalhe.get("draft", {}).get("layout") or {}
        section = self._primeira_matriz_section(layout)
        section.setdefault("data", {})
        section["data"]["rows"] = [
            ["BLOCO", "PAVIMENTO", "APTO", "Atividade 1", "Atividade 6", "Atividade 8", "Total"],
            ["B", "P1", "101", "", "", "", ""],
            ["B", "P1", "102", "", "", "10%", ""],
            ["B", "P1", "104", "", "20%", "50%", ""],
        ]
        section["data"]["importMeta"] = {
            "strategy": "manual_template",
            "axis_cols_interpreted": [0, 1, 2],
            "axis_headers_interpreted": ["BLOCO", "PAVIMENTO", "APTO"],
            "activity_cols_interpreted": [3, 4, 5],
            "activity_headers_interpreted": ["Atividade 1", "Atividade 6", "Atividade 8"],
            "row_axis_key": "bloco",
        }
        self._salvar_layout(ambiente_id, layout)
        resp = self._abrir_mapa(ambiente_id, bloco="B", pavimento="P1")
        matrix = resp.context["matrix"]
        totais = {t["atividade"]: t["pct"] for t in matrix["totais"]}
        self.assertEqual(totais.get("Atividade 1"), 0)
        self.assertAlmostEqual(float(totais["Atividade 6"]), 6.67, places=2)
        self.assertAlmostEqual(float(totais["Atividade 8"]), 20.0, places=2)
        self.assertAlmostEqual(float(matrix["total_geral"]), 8.89, places=2)

    def test_total_linha_inclui_zeros_exibidos_na_media(self):
        """0% exibido nas demais colunas/linhas entra na média dos totais."""
        ambiente_id = self._criar_ambiente_mapa("Total sem diluir")
        detalhe = self._detalhe(ambiente_id)
        layout = detalhe.get("versao", {}).get("layout") or detalhe.get("draft", {}).get("layout") or {}
        section = self._primeira_matriz_section(layout)
        section.setdefault("data", {})
        section["data"]["rows"] = [
            ["BLOCO", "PAVIMENTO", "APTO", "Atividade 1", "Atividade 9", "Total"],
            ["teste", "pavimento teste2", "apt teste101", "", "", ""],
            ["teste", "pavimento teste2", "apt teste102", "", "", ""],
            ["teste", "pavimento teste2", "apt teste103", "", "50%", ""],
            ["teste", "pavimento teste2", "apt teste 105", "", "20%", ""],
        ]
        section["data"]["importMeta"] = {
            "strategy": "manual_template",
            "axis_cols_interpreted": [0, 1, 2],
            "axis_headers_interpreted": ["BLOCO", "PAVIMENTO", "APTO"],
            "activity_cols_interpreted": [3, 4],
            "activity_headers_interpreted": ["Atividade 1", "Atividade 9"],
            "row_axis_key": "bloco",
        }
        self._salvar_layout(ambiente_id, layout)
        resp = self._abrir_mapa(ambiente_id, bloco="teste", pavimento="pavimento teste2")
        rows = {r["row_label"]: r for r in resp.context["matrix"]["rows"]}
        self.assertAlmostEqual(float(rows["apt teste103"]["total"]), 25.0, places=2)
        self.assertAlmostEqual(float(rows["apt teste 105"]["total"]), 10.0, places=2)
        totais = {t["atividade"]: t["pct"] for t in resp.context["matrix"]["totais"]}
        self.assertEqual(totais.get("Atividade 1"), 0)
        self.assertAlmostEqual(float(totais["Atividade 9"]), 17.5, places=2)

    def test_total_linha_media_inclui_colunas_com_zero_exibido(self):
        """Total da linha: média de todas as atividades visíveis (0% + 50% + 0% → 16,67%)."""
        ambiente_id = self._criar_ambiente_mapa("Total linha vazias")
        detalhe = self._detalhe(ambiente_id)
        layout = detalhe.get("versao", {}).get("layout") or detalhe.get("draft", {}).get("layout") or {}
        section = self._primeira_matriz_section(layout)
        section.setdefault("data", {})
        section["data"]["rows"] = [
            ["BLOCO", "PAVIMENTO", "APTO", "Atividade 1", "Atividade 2", "Atividade 3", "Total"],
            ["Bloco A", "Pavimento 01", "U1", "", "50%", "", ""],
        ]
        section["data"]["importMeta"] = {
            "strategy": "manual_template",
            "axis_cols_interpreted": [0, 1, 2],
            "axis_headers_interpreted": ["BLOCO", "PAVIMENTO", "APTO"],
            "activity_cols_interpreted": [3, 4, 5],
            "activity_headers_interpreted": ["Atividade 1", "Atividade 2", "Atividade 3"],
            "row_axis_key": "bloco",
        }
        self._salvar_layout(ambiente_id, layout)
        resp = self._abrir_mapa(ambiente_id, bloco="Bloco A", pavimento="Pavimento 01")
        row = next(r for r in resp.context["matrix"]["rows"] if r.get("row_label") == "U1")
        self.assertEqual(row["cells"][1]["pct"], 50)
        self.assertAlmostEqual(float(row["total"]), 16.67, places=2)

    def test_rodape_coluna_media_linhas_exibidas_inclui_zero(self):
        """Total da coluna = média dos pavimentos na grade (50+0+0)/3, não só células com % > 0."""
        ambiente_id = self._criar_ambiente_mapa("Rodape coluna zero")
        detalhe = self._detalhe(ambiente_id)
        layout = detalhe.get("versao", {}).get("layout") or detalhe.get("draft", {}).get("layout") or {}
        section = self._primeira_matriz_section(layout)
        section.setdefault("data", {})
        section["data"]["rows"] = [
            ["BLOCO", "PAVIMENTO", "APTO", "Atividade 1", "Atividade 2", "Total"],
            ["Bloco A", "pavimento 1", "U1", "", "50%", ""],
            ["Bloco A", "pavimento 2", "U2", "", "0%", ""],
            ["Bloco A", "pavimento 3", "U3", "", "0%", ""],
        ]
        section["data"]["importMeta"] = {
            "strategy": "manual_template",
            "axis_cols_interpreted": [0, 1, 2],
            "axis_headers_interpreted": ["BLOCO", "PAVIMENTO", "APTO"],
            "activity_cols_interpreted": [3, 4],
            "activity_headers_interpreted": ["Atividade 1", "Atividade 2"],
            "row_axis_key": "bloco",
        }
        self._salvar_layout(ambiente_id, layout)
        resp = self._abrir_mapa(ambiente_id, bloco="Bloco A")
        matrix = resp.context["matrix"]
        self.assertEqual(matrix.get("mode"), "pavimento")
        rows = {r["row_label"]: r for r in matrix["rows"]}
        self.assertEqual(rows["pavimento 1"]["cells"][1]["pct"], 50)
        self.assertEqual(rows["pavimento 2"]["cells"][1]["pct"], 0)
        self.assertEqual(rows["pavimento 3"]["cells"][1]["pct"], 0)
        totais = {t["atividade"]: t["pct"] for t in matrix["totais"]}
        self.assertAlmostEqual(float(totais["Atividade 2"]), 16.67, places=2)

    def test_apto_filtro_consolida_linhas_servico_mesmo_total_pavimento(self):
        """Chip/filtro de unidade: várias linhas-fonte → uma linha; Total igual à visão do pavimento."""
        ambiente_id = self._criar_ambiente_mapa("Detalhe UND")
        self._aplicar_layout_manual(
            ambiente_id,
            [
                ["Bloco A", "Pavimento 01", "Linha 1", "100%", ""],
                ["Bloco A", "Pavimento 01", "Linha 1", "0%", ""],
                ["Bloco A", "Pavimento 01", "apt 2", "100%", ""],
            ],
        )
        resp_pav = self._abrir_mapa(ambiente_id, bloco="Bloco A", pavimento="Pavimento 01")
        linha1_pav = next(
            r for r in resp_pav.context["matrix"]["rows"] if r.get("row_label") == "Linha 1"
        )
        resp_det = self._abrir_mapa(
            ambiente_id,
            bloco="Bloco A",
            pavimento="Pavimento 01",
            apto="Linha 1",
        )
        matrix = resp_det.context["matrix"]
        self.assertTrue(matrix.get("unit_detail_view"))
        self.assertEqual(len(matrix["rows"]), 1)
        self.assertEqual(matrix["rows"][0]["row_label"], "Linha 1")
        self.assertEqual(matrix["rows"][0]["total"], linha1_pav["total"])
        self.assertEqual(matrix["rows"][0]["cells"][0]["pct"], linha1_pav["cells"][0]["pct"])

    def test_linha_placeholder_nao_e_drillavel(self):
        ambiente_id = self._criar_ambiente_mapa("Placeholder drill")
        self._aplicar_layout_manual(
            ambiente_id,
            [["teste", "pavimento teste", "Linha 1", "0%", ""]],
        )
        resp = self._abrir_mapa(ambiente_id, bloco="teste", pavimento="pavimento teste")
        row = next(r for r in resp.context["matrix"]["rows"] if r.get("row_label") == "Linha 1")
        self.assertFalse(row.get("row_drillable"))

    def test_chip_unidade_lista_linha_estrutural_com_zero_pct(self):
        ambiente_id = self._criar_ambiente_mapa("Chip UND")
        self._aplicar_layout_manual(
            ambiente_id,
            [
                ["teste", "pavimento teste", "Linha 1", "0%", ""],
            ],
        )
        resp = self._abrir_mapa(ambiente_id, bloco="teste", pavimento="pavimento teste")
        matrix = resp.context["matrix"]
        self.assertEqual(matrix.get("mode"), "apto")
        self.assertTrue(
            any(r.get("row_label") == "Linha 1" for r in matrix.get("rows") or []),
            "Unidade deve aparecer na matriz.",
        )
        aptos = [a.get("apto") for a in resp.context["layers"]["aptos"]]
        self.assertIn("Linha 1", aptos)

    def test_chip_pavimento_estrutural_sem_unidade(self):
        ambiente_id = self._criar_ambiente_mapa("Chip pav estrutural")
        self._aplicar_layout_manual(
            ambiente_id,
            [
                ["teste", "Pavimento 01", "", "", ""],
            ],
        )
        resp = self._abrir_mapa(ambiente_id, bloco="teste")
        pavs = [p.get("pavimento") for p in resp.context["layers"]["pavimentos"]]
        self.assertIn("Pavimento 01", pavs)

    def test_varias_linhas_mesmo_apto_media_na_coluna_do_pavimento(self):
        """Várias linhas de serviço do mesmo apto na mesma coluna → média no pavimento."""
        ambiente_id = self._criar_ambiente_mapa("Multi linha apto")
        self._aplicar_layout_manual(
            ambiente_id,
            [
                ["Bloco A", "Pavimento 01", "UND 101", "100%", ""],
                ["Bloco A", "Pavimento 01", "UND 101", "0%", ""],
                ["Bloco A", "Pavimento 01", "UND 102", "100%", ""],
            ],
        )
        resp = self._abrir_mapa(ambiente_id, bloco="Bloco A")
        pav = next(r for r in resp.context["matrix"]["rows"] if r.get("row_label") == "Pavimento 01")
        self.assertAlmostEqual(float(pav["cells"][0]["pct"]), 66.7, places=1)
        self.assertAlmostEqual(float(pav["total"]), 66.7, places=1)

    def test_linha_continuacao_sem_apto_herda_e_entra_na_media(self):
        ambiente_id = self._criar_ambiente_mapa("Continuacao apto")
        self._aplicar_layout_manual(
            ambiente_id,
            [
                ["Bloco A", "Pavimento 01", "UND 101", "100%", ""],
                ["Bloco A", "Pavimento 01", "", "0%", ""],
            ],
        )
        resp = self._abrir_mapa(ambiente_id, bloco="Bloco A")
        pav = next(r for r in resp.context["matrix"]["rows"] if r.get("row_label") == "Pavimento 01")
        self.assertEqual(pav["cells"][0]["pct"], 50)
        self.assertEqual(pav["total"], 50)

    def test_total_linha_ignora_coluna_total_errada_do_layout(self):
        ambiente_id = self._criar_ambiente_mapa("Total layout errado")
        det = self._detalhe(ambiente_id)
        layout = (det.get("versao", {}) or det.get("draft", {}) or {}).get("layout") or {}
        section = self._primeira_matriz_section(layout)
        self.assertTrue(section, "Seção matriz ausente.")
        section.setdefault("data", {})
        section["data"]["rows"] = [
            ["BLOCO", "PAVIMENTO", "APTO", "Atividade 1", "Atividade 2", "Total"],
            ["Bloco A", "Pavimento 01", "UND 101", "100%", "0%", "99%"],
            ["Bloco A", "Pavimento 01", "UND 102", "0%", "100%", "1%"],
        ]
        section["data"]["importMeta"] = {
            "strategy": "manual_template",
            "axis_cols_interpreted": [0, 1, 2],
            "axis_headers_interpreted": ["BLOCO", "PAVIMENTO", "APTO"],
            "activity_cols_interpreted": [3, 4],
            "activity_headers_interpreted": ["Atividade 1", "Atividade 2"],
            "row_axis_key": "bloco",
        }
        self._salvar_layout(ambiente_id, layout)
        resp = self._abrir_mapa(ambiente_id, bloco="Bloco A")
        pav = next(r for r in resp.context["matrix"]["rows"] if r.get("row_label") == "Pavimento 01")
        self.assertEqual(pav["cells"][0]["pct"], 50)
        self.assertEqual(pav["cells"][1]["pct"], 50)
        self.assertEqual(pav["total"], 50)

    def test_chip_unidade_com_hifen_continua_listada(self):
        ambiente_id = self._criar_ambiente_mapa("Chip UND hifen")
        self._aplicar_layout_manual(
            ambiente_id,
            [
                ["B1", "P1", "UND 101", "-", ""],
            ],
        )
        resp = self._abrir_mapa(ambiente_id, bloco="B1", pavimento="P1")
        aptos = [a.get("apto") for a in resp.context["layers"]["aptos"]]
        self.assertIn("UND 101", aptos)
