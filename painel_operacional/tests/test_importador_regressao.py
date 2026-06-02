from __future__ import annotations

from io import BytesIO

from django.test import SimpleTestCase

from painel_operacional.tests.fixtures_importador import (
    workbook_atividade_em_colunas,
    workbook_baixa_confianca,
    workbook_edificio_residencial,
    workbook_grande_com_atividades_apos_linha_2500,
    workbook_multiabas_operacional_nome_nao_padrao,
    workbook_resort_multieixo,
    workbook_tabular_colunas_reordenadas,
    workbook_tabular_com_coluna_apartamento,
    workbook_tabular_sem_grupo_com_auxiliares,
)
from painel_operacional.views import _interpret_import_rows, _parse_percent_value, _read_excel_rows


def _as_uploaded(bytes_payload: bytes, name: str = "arquivo.xlsx"):
    f = BytesIO(bytes_payload)
    f.name = name
    return f


class ImportadorInteligenteRegressaoTests(SimpleTestCase):
    """Biblioteca de regressão para planilhas heterogêneas de obras."""

    def test_auto_escolhe_aba_operacional_no_caso_residencial(self):
        arquivo = _as_uploaded(workbook_edificio_residencial(), "edificio.xlsx")
        rows, sheet, diag = _read_excel_rows(arquivo, sheet_name="")
        self.assertEqual(sheet, "DADOS")
        self.assertEqual(diag.get("selected_sheet"), "DADOS")
        self.assertGreater(len(rows), 3)

    def test_pivot_registros_com_eixo_dinamico_resort(self):
        arquivo = _as_uploaded(workbook_resort_multieixo(), "resort.xlsx")
        rows, _sheet, _diag = _read_excel_rows(arquivo, sheet_name="")
        out, strategy, report = _interpret_import_rows(rows, mode="auto")
        self.assertEqual(strategy, "pivot_registros")
        self.assertGreaterEqual(report.get("confidence", 0), 0.85)
        self.assertTrue(out and out[0])
        # Camadas devem vir estruturadas em colunas (não concatenadas por "/").
        header_tokens = [str(x).upper() for x in out[0][:4]]
        self.assertIn("TORRE", header_tokens)
        self.assertIn("ALA", header_tokens)

    def test_detecta_estrategia_atividade_em_colunas(self):
        arquivo = _as_uploaded(workbook_atividade_em_colunas(), "colunar.xlsx")
        rows, _sheet, _diag = _read_excel_rows(arquivo, sheet_name="")
        out, strategy, report = _interpret_import_rows(rows, mode="auto")
        self.assertEqual(strategy, "pivot_atividade_colunas")
        self.assertGreaterEqual(report.get("confidence", 0), 0.70)
        self.assertEqual(out[0][0], "Unidade / eixo")
        self.assertIn("FUNDACAO", [c.upper() for c in out[0]])

    def test_modo_raw_preserva_matriz_bruta(self):
        arquivo = _as_uploaded(workbook_edificio_residencial(), "raw.xlsx")
        rows, _sheet, _diag = _read_excel_rows(arquivo, sheet_name="DADOS")
        out, strategy, report = _interpret_import_rows(rows, mode="raw")
        self.assertEqual(strategy, "forcado_bruto")
        self.assertEqual(report.get("confidence"), 1.0)
        self.assertEqual(out, rows)

    def test_modo_pivot_sem_confianca_retorna_erro_de_estrategia(self):
        arquivo = _as_uploaded(workbook_baixa_confianca(), "baixa.xlsx")
        rows, _sheet, _diag = _read_excel_rows(arquivo, sheet_name="")
        out, strategy, report = _interpret_import_rows(rows, mode="pivot")
        self.assertEqual(strategy, "pivot_sem_confianca")
        self.assertEqual(out, [])
        self.assertIn("pivot", report.get("reason", "").lower())

    def test_modo_auto_baixa_confianca_faz_fallback_bruto(self):
        arquivo = _as_uploaded(workbook_baixa_confianca(), "baixa_auto.xlsx")
        rows, _sheet, _diag = _read_excel_rows(arquivo, sheet_name="")
        out, strategy, report = _interpret_import_rows(rows, mode="auto")
        self.assertEqual(strategy, "fallback_bruto")
        self.assertEqual(out, rows)
        self.assertGreaterEqual(float(report.get("confidence") or 0), 0.3)

    def test_csv_com_bom_e_delimitador_ponto_virgula(self):
        payload = (
            "\ufeffATIVIDADE;UH 101;UH 102\n"
            "FUNDACAO;100%;95%\n"
            "ESTRUTURA;80%;72%\n"
            "ALVENARIA;25%;18%\n"
        ).encode("utf-8")
        arquivo = _as_uploaded(payload, "colunas.csv")
        rows, sheet, diag = _read_excel_rows(arquivo, sheet_name="")
        self.assertEqual(sheet, "CSV")
        self.assertEqual(diag.get("selected_sheet"), "CSV")
        self.assertEqual(diag.get("sheet_mode"), "csv")
        self.assertEqual(diag.get("encoding"), "utf-8-sig")
        out, strategy, report = _interpret_import_rows(rows, mode="auto")
        self.assertEqual(strategy, "pivot_atividade_colunas")
        self.assertGreaterEqual(report.get("confidence", 0), 0.70)
        self.assertEqual(out[0][0], "Unidade / eixo")
        self.assertIn("FUNDACAO", [c.upper() for c in out[0]])

    def test_arquivo_xls_legado_retorna_erro_claro(self):
        arquivo = _as_uploaded(b"conteudo-xls", "legado.xls")
        with self.assertRaisesMessage(ValueError, ".xls antigo"):
            _read_excel_rows(arquivo, sheet_name="")

    def test_parse_percent_suporta_formato_en_us(self):
        self.assertEqual(_parse_percent_value("1,234.56"), 100.0)
        self.assertEqual(_parse_percent_value("12,34"), 12.34)

    def test_auto_escolhe_aba_operacional_sem_nome_fixo(self):
        arquivo = _as_uploaded(workbook_multiabas_operacional_nome_nao_padrao(), "multi.xlsx")
        rows, sheet, diag = _read_excel_rows(arquivo, sheet_name="")
        self.assertEqual(sheet, "BASE_UNIDADES")
        self.assertEqual(diag.get("selected_sheet"), "BASE_UNIDADES")
        out, strategy, report = _interpret_import_rows(rows, mode="auto")
        self.assertEqual(strategy, "pivot_registros")
        self.assertGreaterEqual(float(report.get("confidence") or 0), 0.85)
        self.assertIn("REGIAO", [str(c).upper() for c in out[0][:4]])

    def test_tabular_sem_grupo_mantem_atividade_e_status(self):
        arquivo = _as_uploaded(workbook_tabular_sem_grupo_com_auxiliares(), "sem_grupo.xlsx")
        rows, _sheet, _diag = _read_excel_rows(arquivo, sheet_name="")
        out, strategy, report = _interpret_import_rows(rows, mode="auto")
        self.assertEqual(strategy, "pivot_registros")
        self.assertGreaterEqual(float(report.get("confidence") or 0), 0.80)
        header = [str(c).upper() for c in out[0]]
        self.assertIn("CHAPISCO INTERNO", header)
        self.assertIn("EMBOÇO INTERNO", header)
        self.assertNotIn("CUSTO", header)
        self.assertNotIn("DATA DE TERMINO", header)

    def test_tabular_reordenado_detecta_atividade_mesmo_fora_posicao_padrao(self):
        arquivo = _as_uploaded(workbook_tabular_colunas_reordenadas(), "reordenado.xlsx")
        rows, _sheet, _diag = _read_excel_rows(arquivo, sheet_name="")
        out, strategy, report = _interpret_import_rows(rows, mode="auto")
        self.assertEqual(strategy, "pivot_registros")
        self.assertGreaterEqual(float(report.get("confidence") or 0), 0.80)
        header = [str(c).upper() for c in out[0]]
        self.assertGreaterEqual(len(header), 6)
        atividades = header[4:]
        self.assertIn("CONCRETO PILAR", atividades)
        self.assertIn("FÔRMA PILAR", atividades)
        self.assertNotIn("ESTRUTURA", atividades)

    def test_nao_trunca_atividades_que_aparecem_apos_linha_2500(self):
        arquivo = _as_uploaded(workbook_grande_com_atividades_apos_linha_2500(), "grande.xlsx")
        rows, _sheet, _diag = _read_excel_rows(arquivo, sheet_name="")
        out, strategy, report = _interpret_import_rows(rows, mode="auto")
        self.assertEqual(strategy, "pivot_registros")
        self.assertGreaterEqual(float(report.get("confidence") or 0), 0.80)
        header = [str(c).upper() for c in out[0]]
        self.assertIn("ATV_BASE_1", header)
        self.assertIn("ATV_EXTRA_1", header)
        self.assertIn("ATV_EXTRA_5", header)

    def test_coluna_apartamento_entra_no_eixo_und(self):
        arquivo = _as_uploaded(workbook_tabular_com_coluna_apartamento(), "dbg.xlsx")
        rows, _sheet, _diag = _read_excel_rows(arquivo, sheet_name="DADOS")
        out, strategy, report = _interpret_import_rows(rows, mode="auto")
        self.assertEqual(strategy, "pivot_registros")
        header = [str(c).upper() for c in out[0][:4]]
        self.assertEqual(header[:3], ["BLOCO", "PAVIMENTO", "APARTAMENTO"])
        labels = {str(r[2]) for r in out[1:] if len(r) > 2}
        self.assertIn("101", labels)
        self.assertIn("102", labels)
        self.assertIn("201", labels)

