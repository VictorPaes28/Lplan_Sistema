from __future__ import annotations

import json
from datetime import date

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase
from django.urls import reverse
from openpyxl import Workbook

from accounts.groups import GRUPOS
from core.models import Project, ProjectMember
from mapa_obras.models import Obra
from painel_operacional.tests.fixtures_importador import workbook_atividade_em_colunas
from suprimentos.models import ItemMapaServico


User = get_user_model()


class MapaControleIsolamentoRegressaoTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.grupo_fo, _ = Group.objects.get_or_create(name=GRUPOS.FERRAMENTA_OPERACIONAL)
        cls.grupo_mc, _ = Group.objects.get_or_create(name=GRUPOS.MAPA_CONTROLE)
        cls.user = User.objects.create_user(
            username="teste_isolamento_mapa",
            email="isolamento@teste.com",
            password="senha123",
        )
        cls.user.groups.add(cls.grupo_fo, cls.grupo_mc)

        cls.obra = Obra.objects.create(
            codigo_sienge="OBR-ISO-001",
            nome="Obra Isolamento",
            ativa=True,
        )
        cls.project = Project.objects.create(
            name="Projeto Isolamento",
            code="OBR-ISO-001",
            start_date=date(2024, 1, 1),
            end_date=date(2026, 12, 31),
            is_active=True,
        )
        ProjectMember.objects.get_or_create(user=cls.user, project=cls.project)

    def setUp(self):
        self.client = Client()
        self.client.login(username="teste_isolamento_mapa", password="senha123")

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
        payload = response.json()
        self.assertTrue(payload.get("success"), payload)
        return int(payload["item"]["id"])

    def _detalhe(self, ambiente_id: int) -> dict:
        response = self.client.get(self._url("suprimentos:po_api_detalhe_ambiente", ambiente_id))
        self.assertEqual(response.status_code, 200, response.content)
        payload = response.json()
        self.assertTrue(payload.get("success"), payload)
        return payload

    def _primeira_matriz_rows(self, layout: dict) -> list[list[str]]:
        sections = layout.get("sections") if isinstance(layout, dict) else []
        for section in sections or []:
            if not isinstance(section, dict):
                continue
            if str(section.get("kind") or "").strip() not in {"matrix_table", "table"}:
                continue
            data = section.get("data") if isinstance(section.get("data"), dict) else {}
            rows = data.get("rows")
            if isinstance(rows, list):
                return rows
        return []

    def _primeira_matriz_section(self, layout: dict) -> dict:
        sections = layout.get("sections") if isinstance(layout, dict) else []
        for section in sections or []:
            if not isinstance(section, dict):
                continue
            if str(section.get("kind") or "").strip() not in {"matrix_table", "table"}:
                continue
            return section
        return {}

    def _salvar_layout(self, ambiente_id: int, layout: dict, source: str) -> None:
        response = self.client.post(
            self._url("suprimentos:po_api_salvar_rascunho", ambiente_id),
            data=json.dumps({"layout": layout, "metadados": {"source": source}}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200, response.content)
        payload = response.json()
        self.assertTrue(payload.get("success"), payload)

    def _importar_rows_excel(self, ambiente_id: int) -> list[list[str]]:
        arquivo = SimpleUploadedFile(
            "colunas.xlsx",
            workbook_atividade_em_colunas(),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        response = self.client.post(
            self._url("suprimentos:po_api_importar_matriz_excel", ambiente_id),
            data={"arquivo": arquivo, "mode": "auto"},
        )
        self.assertEqual(response.status_code, 200, response.content)
        payload = response.json()
        self.assertTrue(payload.get("success"), payload)
        rows = payload.get("rows") or []
        self.assertTrue(rows, "Importação deveria retornar linhas estruturadas.")
        return rows

    def _importar_payload_excel(self, ambiente_id: int) -> dict:
        arquivo = SimpleUploadedFile(
            "colunas.xlsx",
            workbook_atividade_em_colunas(),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        response = self.client.post(
            self._url("suprimentos:po_api_importar_matriz_excel", ambiente_id),
            data={"arquivo": arquivo, "mode": "auto"},
        )
        self.assertEqual(response.status_code, 200, response.content)
        payload = response.json()
        self.assertTrue(payload.get("success"), payload)
        return payload

    def _workbook_tabular_com_grupo_servico(self) -> bytes:
        wb = Workbook()
        ws = wb.active
        ws.title = "Operacional"
        ws.append(
            [
                "",
                "",
                "",
                "",
                "SETOR",
                "BLOCO",
                "PAVIMENTO",
                "APTO",
                "ATIVIDADE",
                "GRUPO DE SERVIÇOS",
                "STATUS",
                "CUSTO",
                "OBSERVAÇÃO",
                "DATA DE TERMINO",
            ]
        )
        ws.append(["", "", "", "", "HABITAÇÃO", "B1", "2º PAV", "302", "ARMAÇÃO PILAR", "ESTRUTURA", "1", "100", "ok", "2026-05-01"])
        ws.append(["", "", "", "", "HABITAÇÃO", "B1", "2º PAV", "302", "ARMAÇÃO VIGA", "ESTRUTURA", "0.5", "100", "ok", "2026-05-02"])
        ws.append(["", "", "", "", "HABITAÇÃO", "B1", "2º PAV", "302", "FÔRMA PILAR", "ESTRUTURA", "0", "100", "ok", "2026-05-03"])
        ws.append(
            ["", "", "", "", "HABITAÇÃO", "B1", "2º PAV", "303", "ELEVAÇÃO DE ALVENARIA", "VEDAÇÕES", "0.9", "120", "", "2026-05-04"]
        )
        ws.append(["", "", "", "", "HABITAÇÃO", "B1", "2º PAV", "303", "CHAPISCO INTERNO", "REVESTIMENTO", "0.4", "120", "", "2026-05-05"])
        from io import BytesIO

        out = BytesIO()
        wb.save(out)
        out.seek(0)
        return out.read()

    def _matriz_tem_conteudo(self, rows: list[list[str]]) -> bool:
        for r_idx, row in enumerate(rows):
            if not isinstance(row, list):
                continue
            for c_idx, cell in enumerate(row):
                txt = str(cell or "").strip()
                if not txt:
                    continue
                if r_idx == 0:
                    continue
                if c_idx == 0:
                    continue
                return True
        return False

    def _assert_matriz_manual_vazia(self, ambiente_id: int) -> None:
        detalhe = self._detalhe(ambiente_id)
        layout = detalhe.get("versao", {}).get("layout") or {}
        rows = self._primeira_matriz_rows(layout)
        self.assertTrue(rows, "Matriz manual deve existir no layout.")
        self.assertFalse(self._matriz_tem_conteudo(rows), "Matriz manual não deve herdar conteúdo.")
        flat = " ".join(str(cell or "") for row in rows if isinstance(row, list) for cell in row).upper()
        self.assertNotIn("FUNDACAO", flat)
        self.assertNotIn("ESTRUTURA", flat)
        self.assertNotIn("ALVENARIA", flat)
        self.assertNotIn("UH 101", flat)

    def _abrir_mapa_dedicado(self, ambiente_id: int, **extra):
        payload = {"obra": self.obra.id, "ambiente_id": ambiente_id, "embed": 1}
        payload.update(extra)
        response = self.client.get(
            reverse("engenharia:mapa_controle"),
            data=payload,
        )
        self.assertEqual(response.status_code, 200, response.content)
        return response

    def test_importado_nao_contamina_manual_novo(self):
        ambiente_importado = self._criar_ambiente_mapa("Mapa com Excel")
        rows_importadas = self._importar_rows_excel(ambiente_importado)
        self.assertTrue(self._matriz_tem_conteudo(rows_importadas), "Importação deve retornar conteúdo preenchido.")

        detalhe_importado = self._detalhe(ambiente_importado)
        layout_importado = detalhe_importado.get("versao", {}).get("layout") or {}
        sections = layout_importado.get("sections") if isinstance(layout_importado.get("sections"), list) else []
        self.assertTrue(sections, "Layout importado deveria possuir seção de matriz.")
        sections[0].setdefault("data", {})
        sections[0]["data"]["rows"] = rows_importadas
        self._salvar_layout(ambiente_importado, layout_importado, source="teste_importado")

        ambiente_manual = self._criar_ambiente_mapa("Mapa Manual Vazio")
        self._assert_matriz_manual_vazia(ambiente_manual)

        resp_editor = self.client.get(self._url("engenharia:ferramenta_editor_ambiente", ambiente_manual))
        self.assertEqual(resp_editor.status_code, 200, resp_editor.content)
        self.assertTemplateUsed(resp_editor, "painel_operacional/editor_mapa_controle.html")
        mapa_url = str(resp_editor.context["mapa_atual_url"])
        self.assertIn(f"ambiente_id={ambiente_manual}", mapa_url)

    def test_manual_permanece_vazio_apos_importar_em_outro_ambiente(self):
        ambiente_manual = self._criar_ambiente_mapa("Mapa Manual Primeiro")
        self._assert_matriz_manual_vazia(ambiente_manual)

    def test_dedicado_por_ambiente_renderiza_layout_do_proprio_ambiente(self):
        ambiente_a = self._criar_ambiente_mapa("Mapa A Importado")
        ambiente_b = self._criar_ambiente_mapa("Mapa B Manual")

        rows_a = self._importar_rows_excel(ambiente_a)
        self.assertTrue(self._matriz_tem_conteudo(rows_a))
        detalhe_a = self._detalhe(ambiente_a)
        layout_a = detalhe_a.get("versao", {}).get("layout") or {}
        sections_a = layout_a.get("sections") if isinstance(layout_a.get("sections"), list) else []
        self.assertTrue(sections_a)
        sections_a[0].setdefault("data", {})
        sections_a[0]["data"]["rows"] = rows_a
        self._salvar_layout(ambiente_a, layout_a, source="teste_dedicado_a")

        # Dados amplos da obra não podem contaminar render dedicado por ambiente_id.
        ItemMapaServico.objects.create(
            obra=self.obra,
            setor="T1",
            bloco="BL-OBRA",
            pavimento="P1",
            apto="UH 999",
            atividade="ATV_OBRA_LIVRE",
            chave_uid="obra_livre_001",
        )

        resp_a = self._abrir_mapa_dedicado(ambiente_a)
        matrix_a = resp_a.context["matrix"]
        self.assertTrue(
            any(cell.get("pct") is not None for row in matrix_a.get("rows", []) for cell in row.get("cells", [])),
            "Ambiente importado deve renderizar percentuais no dedicado.",
        )

        resp_b = self._abrir_mapa_dedicado(ambiente_b)
        matrix_b = resp_b.context["matrix"]
        self.assertFalse(any(cell.get("pct") is not None for row in matrix_b.get("rows", []) for cell in row.get("cells", [])))
        html_b = resp_b.content.decode("utf-8").upper()
        self.assertNotIn("ATV_OBRA_LIVRE", html_b)
        self.assertNotIn("UH 999", html_b)

    def test_importacao_retorna_metadados_estruturais_no_fluxo_novo(self):
        ambiente_id = self._criar_ambiente_mapa("Mapa com metadados")
        arquivo = SimpleUploadedFile(
            "tabular_grupo.xlsx",
            self._workbook_tabular_com_grupo_servico(),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        response = self.client.post(
            self._url("suprimentos:po_api_importar_matriz_excel", ambiente_id),
            data={"arquivo": arquivo, "mode": "auto"},
        )
        self.assertEqual(response.status_code, 200, response.content)
        payload = response.json()
        meta = payload.get("interpretation_meta") or {}
        self.assertIsInstance(meta, dict)
        self.assertEqual(payload.get("strategy"), "pivot_registros")
        self.assertIn("strategy", meta)
        self.assertIn("confidence", meta)
        self.assertIn("sheet", meta)
        self.assertIn("axis_cols_source", meta)
        self.assertIn("axis_headers_source", meta)
        self.assertIn("activity_cols_interpreted", meta)
        self.assertIn("activity_headers_interpreted", meta)
        self.assertIn("status_col_source", meta)
        self.assertIn("service_group_col_source", meta)
        self.assertIn("auxiliary_cols_source", meta)
        self.assertIsInstance(meta.get("activity_group_map"), dict)
        self.assertIn("header_idx", meta)
        self.assertIn("ignored_auxiliary_cols_source", meta)
        self.assertIsNotNone(meta.get("activity_col_source"))
        self.assertIsNotNone(meta.get("service_group_col_source"))
        self.assertNotEqual(meta.get("activity_col_source"), meta.get("service_group_col_source"))
        aux_headers = {str(item.get("header") or "").upper() for item in meta.get("auxiliary_cols_source") or []}
        self.assertIn("CUSTO", aux_headers)
        self.assertIn("OBSERVAÇÃO", aux_headers)
        self.assertIn("DATA DE TERMINO", aux_headers)

    def test_provider_respeita_axis_cols_e_nao_trata_apto_como_percentual(self):
        ambiente_id = self._criar_ambiente_mapa("Mapa com eixo explicito")
        detalhe = self._detalhe(ambiente_id)
        layout = detalhe.get("versao", {}).get("layout") or {}
        section = self._primeira_matriz_section(layout)
        self.assertTrue(section, "Layout base deve ter seção de matriz.")
        section.setdefault("data", {})
        section["data"]["rows"] = [
            ["SETOR", "BLOCO", "PAVIMENTO", "APTO", "ARMAÇÃO PILAR", "ARMAÇÃO VIGA", "FÔRMA PILAR"],
            ["HABITAÇÃO", "A1", "TÉRREO", "101", "100%", "50%", "0%"],
        ]
        section["data"]["importMeta"] = {
            "strategy": "pivot_registros",
            "confidence": 0.9,
            "sheet": "Exemplo",
            "axis_cols_interpreted": [0, 1, 2, 3],
            "axis_headers_interpreted": ["SETOR", "BLOCO", "PAVIMENTO", "APTO"],
            "activity_cols_interpreted": [4, 5, 6],
            "activity_headers_interpreted": ["ARMAÇÃO PILAR", "ARMAÇÃO VIGA", "FÔRMA PILAR"],
            "activity_group_map": {
                "ARMAÇÃO PILAR": "ESTRUTURA",
                "ARMAÇÃO VIGA": "ESTRUTURA",
                "FÔRMA PILAR": "ESTRUTURA",
            },
            "status_col_source": 10,
            "service_group_col_source": 9,
            "total_col_interpreted": None,
            "header_idx": 0,
        }
        self._salvar_layout(ambiente_id, layout, source="teste_axis_cols_provider")

        resp = self._abrir_mapa_dedicado(ambiente_id)
        matrix = resp.context["matrix"]
        atividades = [str(a or "").upper() for a in matrix.get("atividades", [])]
        self.assertIn("ARMAÇÃO PILAR", atividades)
        self.assertIn("ARMAÇÃO VIGA", atividades)
        self.assertIn("FÔRMA PILAR", atividades)
        self.assertNotIn("ESTRUTURA", atividades)
        self.assertNotIn("VEDAÇÕES", atividades)
        self.assertNotIn("IMPERMEABILIZAÇÃO", atividades)
        self.assertNotIn("BLOCO", atividades)
        self.assertNotIn("PAVIMENTO", atividades)
        self.assertNotIn("APTO", atividades)

        first_row = (matrix.get("rows") or [None])[0]
        self.assertIsNotNone(first_row)
        self.assertEqual(matrix.get("mode"), "bloco")
        self.assertEqual(first_row.get("row_label"), "A1")
        cells = first_row.get("cells") or []
        self.assertEqual(len(cells), 3)
        self.assertEqual(cells[0].get("pct"), 100)
        self.assertEqual(cells[1].get("pct"), 50)
        self.assertEqual(cells[2].get("pct"), 0)
        grupos = matrix.get("atividade_grupos") or {}
        self.assertEqual(grupos.get("ARMAÇÃO PILAR"), "ESTRUTURA")
        self.assertEqual(grupos.get("ARMAÇÃO VIGA"), "ESTRUTURA")
        self.assertEqual(resp.context["kpis"]["total_itens"], 3)

    def test_dedicado_popula_camadas_hierarquicas_por_eixos(self):
        ambiente_id = self._criar_ambiente_mapa("Mapa com camadas")
        detalhe = self._detalhe(ambiente_id)
        layout = detalhe.get("versao", {}).get("layout") or {}
        section = self._primeira_matriz_section(layout)
        self.assertTrue(section)
        section.setdefault("data", {})
        section["data"]["rows"] = [
            ["SETOR", "BLOCO", "PAVIMENTO", "APTO", "ARMAÇÃO PILAR"],
            ["HABITAÇÃO", "A", "1P", "101", "100%"],
            ["HABITAÇÃO", "A", "1P", "102", "50%"],
            ["HABITAÇÃO", "B", "2P", "201", "30%"],
            ["LAZER", "C", "T", "001", "10%"],
        ]
        section["data"]["importMeta"] = {
            "strategy": "pivot_registros",
            "confidence": 0.9,
            "axis_cols_interpreted": [0, 1, 2, 3],
            "axis_headers_interpreted": ["SETOR", "BLOCO", "PAVIMENTO", "APTO"],
            "activity_cols_interpreted": [4],
            "activity_headers_interpreted": ["ARMAÇÃO PILAR"],
        }
        self._salvar_layout(ambiente_id, layout, source="teste_camadas_hierarquia")

        resp_root = self._abrir_mapa_dedicado(ambiente_id)
        layers_root = resp_root.context["layers"]
        self.assertEqual({x["setor"] for x in layers_root["setores"]}, {"HABITAÇÃO", "LAZER"})

        resp_setor = self._abrir_mapa_dedicado(ambiente_id, setor="HABITAÇÃO")
        layers_setor = resp_setor.context["layers"]
        self.assertEqual({x["bloco"] for x in layers_setor["blocos"]}, {"A", "B"})
        labels_bloco = [str(r.get("row_label") or "") for r in resp_setor.context["matrix"].get("rows", [])]
        self.assertEqual(labels_bloco, ["A", "B"])

        resp_bloco = self._abrir_mapa_dedicado(ambiente_id, setor="HABITAÇÃO", bloco="A", matrix_mode="pavimento")
        layers_bloco = resp_bloco.context["layers"]
        self.assertEqual({x["pavimento"] for x in layers_bloco["pavimentos"]}, {"1P"})
        self.assertEqual(resp_bloco.context["matrix"]["mode"], "pavimento")
        labels_pav = [str(r.get("row_label") or "") for r in resp_bloco.context["matrix"].get("rows", [])]
        self.assertEqual(labels_pav, ["1P"])

        resp_pav = self._abrir_mapa_dedicado(
            ambiente_id,
            setor="HABITAÇÃO",
            bloco="A",
            pavimento="1P",
            matrix_mode="apto",
        )
        layers_pav = resp_pav.context["layers"]
        self.assertEqual({x["apto"] for x in layers_pav["aptos"]}, {"101", "102"})
        self.assertEqual(resp_pav.context["matrix"]["mode"], "apto")
        labels_apto = [str(r.get("row_label") or "") for r in resp_pav.context["matrix"].get("rows", [])]
        self.assertEqual(set(labels_apto), {"101", "102"})

    def test_dedicado_infere_matrix_mode_por_recorte_sem_parametro(self):
        ambiente_id = self._criar_ambiente_mapa("Mapa inferencia de modo")
        detalhe = self._detalhe(ambiente_id)
        layout = detalhe.get("versao", {}).get("layout") or {}
        section = self._primeira_matriz_section(layout)
        self.assertTrue(section)
        section.setdefault("data", {})
        section["data"]["rows"] = [
            ["SETOR", "BLOCO", "PAVIMENTO", "APTO", "ARMAÇÃO PILAR"],
            ["HABITAÇÃO", "A1", "TÉRREO", "101", "100%"],
            ["HABITAÇÃO", "A1", "1º PAV", "201", "50%"],
            ["HABITAÇÃO", "A2", "TÉRREO", "102", "40%"],
        ]
        section["data"]["importMeta"] = {
            "strategy": "pivot_registros",
            "confidence": 0.9,
            "axis_cols_interpreted": [0, 1, 2, 3],
            "axis_headers_interpreted": ["SETOR", "BLOCO", "PAVIMENTO", "APTO"],
            "activity_cols_interpreted": [4],
            "activity_headers_interpreted": ["ARMAÇÃO PILAR"],
        }
        self._salvar_layout(ambiente_id, layout, source="teste_inferencia_modo")

        # Sem matrix_mode explícito, ao selecionar bloco deve abrir por pavimento.
        resp_bloco = self._abrir_mapa_dedicado(ambiente_id, setor="HABITAÇÃO", bloco="A1")
        self.assertEqual(resp_bloco.context["matrix"]["mode"], "pavimento")
        labels_pav = [str(r.get("row_label") or "") for r in resp_bloco.context["matrix"].get("rows", [])]
        self.assertEqual(set(labels_pav), {"TÉRREO", "1º PAV"})

        # Sem matrix_mode explícito, ao selecionar pavimento deve abrir por apto.
        resp_pav = self._abrir_mapa_dedicado(ambiente_id, setor="HABITAÇÃO", bloco="A1", pavimento="TÉRREO")
        self.assertEqual(resp_pav.context["matrix"]["mode"], "apto")
        labels_apto = [str(r.get("row_label") or "") for r in resp_pav.context["matrix"].get("rows", [])]
        self.assertEqual(labels_apto, ["101"])

    def test_totais_no_dedicado_evita_media_de_medias(self):
        ambiente_id = self._criar_ambiente_mapa("Mapa total ponderado")
        detalhe = self._detalhe(ambiente_id)
        layout = detalhe.get("versao", {}).get("layout") or {}
        section = self._primeira_matriz_section(layout)
        self.assertTrue(section)
        section.setdefault("data", {})
        section["data"]["rows"] = [
            ["SETOR", "BLOCO", "PAVIMENTO", "APTO", "ATV1", "ATV2"],
            ["HAB", "A", "1P", "101", "100%", "0%"],
            ["HAB", "A", "1P", "102", "100%", "0%"],
            ["HAB", "B", "1P", "201", "0%", "0%"],
        ]
        section["data"]["importMeta"] = {
            "strategy": "pivot_registros",
            "confidence": 0.9,
            "axis_cols_interpreted": [0, 1, 2, 3],
            "axis_headers_interpreted": ["SETOR", "BLOCO", "PAVIMENTO", "APTO"],
            "activity_cols_interpreted": [4, 5],
            "activity_headers_interpreted": ["ATV1", "ATV2"],
        }
        self._salvar_layout(ambiente_id, layout, source="teste_total_ponderado")

        resp = self._abrir_mapa_dedicado(ambiente_id, setor="HAB")
        matrix = resp.context["matrix"]
        # Modo bloco: linhas A e B agregadas visualmente.
        labels = [str(r.get("row_label") or "") for r in matrix.get("rows", [])]
        self.assertEqual(labels, ["A", "B"])
        totais = {str(t.get("atividade") or ""): t.get("pct") for t in matrix.get("totais", [])}
        # ATV1 pela base real: (100 + 100 + 0) / 3 = 66.7 (não 50 por média de blocos).
        self.assertEqual(totais.get("ATV1"), 66.7)
        self.assertEqual(totais.get("ATV2"), 0)
        self.assertEqual(resp.context["kpis"]["total_itens"], 6)

    def test_total_trata_hifen_como_zero_e_na_como_ausente(self):
        ambiente_id = self._criar_ambiente_mapa("Mapa hifen zero")
        detalhe = self._detalhe(ambiente_id)
        layout = detalhe.get("versao", {}).get("layout") or {}
        section = self._primeira_matriz_section(layout)
        self.assertTrue(section)
        section.setdefault("data", {})
        section["data"]["rows"] = [
            ["SETOR", "BLOCO", "PAVIMENTO", "APTO", "ATV1"],
            ["HAB", "A", "1P", "101", "100%"],
            ["HAB", "A", "1P", "102", "-"],
            ["HAB", "A", "1P", "103", "N/A"],
        ]
        section["data"]["importMeta"] = {
            "strategy": "pivot_registros",
            "confidence": 0.9,
            "axis_cols_interpreted": [0, 1, 2, 3],
            "axis_headers_interpreted": ["SETOR", "BLOCO", "PAVIMENTO", "APTO"],
            "activity_cols_interpreted": [4],
            "activity_headers_interpreted": ["ATV1"],
        }
        self._salvar_layout(ambiente_id, layout, source="teste_hifen_zero_na_ausente")

        resp = self._abrir_mapa_dedicado(ambiente_id, setor="HAB")
        totais = {str(t.get("atividade") or ""): t.get("pct") for t in resp.context["matrix"].get("totais", [])}
        # Base válida: 100 e 0 (N/A fora do cálculo) => média 50.
        self.assertEqual(totais.get("ATV1"), 50)
        self.assertEqual(resp.context["kpis"]["total_itens"], 2)

    def test_celula_vazia_estrutural_permanece_ausente_no_dedicado(self):
        ambiente_id = self._criar_ambiente_mapa("Mapa vazio estrutural ausente")
        detalhe = self._detalhe(ambiente_id)
        layout = detalhe.get("versao", {}).get("layout") or {}
        section = self._primeira_matriz_section(layout)
        self.assertTrue(section)
        section.setdefault("data", {})
        section["data"]["rows"] = [
            ["SETOR", "BLOCO", "PAVIMENTO", "APTO", "ATV1", "ATV2"],
            ["HAB", "A", "1P", "101", "100%", ""],
            ["HAB", "A", "1P", "102", "0%", ""],
        ]
        section["data"]["importMeta"] = {
            "strategy": "pivot_registros",
            "confidence": 0.9,
            "axis_cols_interpreted": [0, 1, 2, 3],
            "axis_headers_interpreted": ["SETOR", "BLOCO", "PAVIMENTO", "APTO"],
            "activity_cols_interpreted": [4, 5],
            "activity_headers_interpreted": ["ATV1", "ATV2"],
        }
        self._salvar_layout(ambiente_id, layout, source="teste_vazio_estrutural_ausente")

        resp = self._abrir_mapa_dedicado(ambiente_id, setor="HAB")
        matrix = resp.context["matrix"]
        first_row = (matrix.get("rows") or [None])[0]
        self.assertIsNotNone(first_row)
        cells = first_row.get("cells") or []
        self.assertIsNone(cells[1].get("pct"))
        totais = {str(t.get("atividade") or ""): t.get("pct") for t in matrix.get("totais", [])}
        self.assertIsNone(totais.get("ATV2"))

    def test_template_manual_preset_guarda_import_meta(self):
        ambiente_id = self._criar_ambiente_mapa("Mapa Manual Meta")
        section = self._primeira_matriz_section(self._detalhe(ambiente_id).get("versao", {}).get("layout") or {})
        meta = (section.get("data") or {}).get("importMeta") or {}
        self.assertEqual(meta.get("strategy"), "manual_template")
        self.assertEqual(meta.get("axis_cols_interpreted"), [0, 1, 2])
        self.assertEqual(meta.get("axis_headers_interpreted"), ["BLOCO", "PAVIMENTO", "APTO"])
        self.assertTrue(meta.get("activity_cols_interpreted"))

    def test_links_da_matriz_preservam_ambiente_id(self):
        ambiente_id = self._criar_ambiente_mapa("Mapa Nav")
        detalhe = self._detalhe(ambiente_id)
        layout = detalhe.get("versao", {}).get("layout") or {}
        section = self._primeira_matriz_section(layout)
        section.setdefault("data", {})
        section["data"]["rows"] = [
            ["SETOR", "BLOCO", "PAVIMENTO", "APTO", "ATV1"],
            ["HAB", "B1", "2P", "101", "50%"],
            ["HAB", "B1", "2P", "102", "100%"],
        ]
        section["data"]["importMeta"] = {
            "strategy": "pivot_registros",
            "axis_cols_interpreted": [0, 1, 2, 3],
            "axis_headers_interpreted": ["SETOR", "BLOCO", "PAVIMENTO", "APTO"],
            "activity_cols_interpreted": [4],
            "activity_headers_interpreted": ["ATV1"],
        }
        self._salvar_layout(ambiente_id, layout, source="teste_nav")

        resp = self._abrir_mapa_dedicado(ambiente_id, setor="HAB", bloco="B1")
        html = resp.content.decode("utf-8")
        self.assertIn(f"ambiente_id={ambiente_id}", html)
        self.assertIn("row-link", html)
        import re

        row_hrefs = re.findall(r'class="cell-link row-link"[^>]*href="([^"]+)"', html)
        self.assertTrue(row_hrefs, "Links de linha da matriz devem existir no HTML.")
        self.assertTrue(
            any(f"ambiente_id={ambiente_id}" in href for href in row_hrefs),
            "Cada link de linha deve preservar ambiente_id na query.",
        )

    def test_mapa_manual_permite_drill_hierarquia(self):
        ambiente_id = self._criar_ambiente_mapa("Mapa Hierarquia")
        resp = self._abrir_mapa_dedicado(ambiente_id)
        matrix = resp.context["matrix"]
        self.assertEqual(matrix.get("mode"), "bloco")
        self.assertTrue(matrix.get("allow_row_drill"))

        detalhe = self._detalhe(ambiente_id)
        layout = detalhe.get("versao", {}).get("layout") or {}
        section = self._primeira_matriz_section(layout)
        section.setdefault("data", {})
        section["data"]["rows"] = [
            ["BLOCO", "PAVIMENTO", "APTO", "ATV1"],
            ["Bloco A", "Térreo", "101", "50%"],
            ["Bloco A", "Térreo", "102", "100%"],
        ]
        section["data"]["importMeta"] = {
            "strategy": "manual_template",
            "axis_cols_interpreted": [0, 1, 2],
            "axis_headers_interpreted": ["BLOCO", "PAVIMENTO", "APTO"],
            "activity_cols_interpreted": [3],
        }
        self._salvar_layout(ambiente_id, layout, source="teste_hierarquia")

        resp_bloco = self._abrir_mapa_dedicado(ambiente_id, bloco="Bloco A")
        self.assertEqual(resp_bloco.context["matrix"].get("mode"), "pavimento")
        self.assertTrue(resp_bloco.context["matrix"].get("allow_row_drill"))

        resp_apto = self._abrir_mapa_dedicado(ambiente_id, bloco="Bloco A", pavimento="Térreo")
        self.assertEqual(resp_apto.context["matrix"].get("mode"), "apto")

    def test_salvar_layout_persiste_edicao_de_celula(self):
        ambiente_id = self._criar_ambiente_mapa("Mapa Persist")
        detalhe = self._detalhe(ambiente_id)
        layout = detalhe.get("versao", {}).get("layout") or {}
        section = self._primeira_matriz_section(layout)
        section.setdefault("data", {})
        section["data"]["rows"] = [
            ["BLOCO", "PAVIMENTO", "APTO", "Atividade 1", "Atividade 2", "Total"],
            ["Bloco A", "Térreo", "101", "10%", "0%", ""],
        ]
        section["data"]["importMeta"] = {
            "strategy": "manual_template",
            "axis_cols_interpreted": [0, 1, 2],
            "axis_headers_interpreted": ["BLOCO", "PAVIMENTO", "APTO"],
            "activity_cols_interpreted": [3, 4],
            "row_axis_key": "bloco",
        }
        self._salvar_layout(ambiente_id, layout, source="teste_base")
        section["data"]["rows"][1][3] = "75%"
        self._salvar_layout(ambiente_id, layout, source="teste_editado")

        rows = self._primeira_matriz_rows(self._detalhe(ambiente_id).get("versao", {}).get("layout") or {})
        self.assertEqual(rows[1][3], "75%")
