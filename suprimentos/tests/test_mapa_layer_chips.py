"""Chips/filtros de camada no Mapa de Controle (eixo estrutural, não percentual)."""

from __future__ import annotations

import unittest

from suprimentos.services.mapa_controle_viewmodel import (
    _clean_layer_prefilter,
    _distinct_structural_axis_values,
    _forward_fill_hierarchy_axes,
    _is_percent_source_row,
    _merge_matrix_axis_keys,
    _row_matches_layer_prefilter,
)


def _axis_map() -> dict[str, int]:
    return {"setor": 0, "bloco": 1, "pavimento": 2, "apto": 3}


class MapaLayerChipsHelpersTests(unittest.TestCase):
    def test_prefilter_ignora_chaves_vazias(self):
        raw = {"setor": "", "bloco": "teste", "pavimento": None}
        self.assertEqual(_clean_layer_prefilter(raw), {"bloco": "teste"})

    def test_layout_esparso_apto_entra_no_chip(self):
        rows = [
            ["", "", "", "Linha 1", "0%"],
            ["", "", "", "Linha 2", "-"],
        ]
        pf = {"bloco": "teste", "pavimento": "pavimento teste"}
        axis = _axis_map()
        # Layout esparso: setor vazio na linha não invalida recorte com setor na URL
        self.assertTrue(_row_matches_layer_prefilter(rows[0], axis, {"setor": "HAB"}))
        self.assertTrue(_row_matches_layer_prefilter(rows[0], axis, pf))
        vals = _distinct_structural_axis_values(rows, axis, "apto", pf)
        self.assertEqual(vals, ["Linha 1", "Linha 2"])

    def test_unidade_zero_pct_e_hifen_listadas(self):
        rows = [["HAB", "B1", "P1", "UND 101", "0%"], ["HAB", "B1", "P1", "UND 102", "-"]]
        vals = _distinct_structural_axis_values(
            rows,
            _axis_map(),
            "apto",
            {"bloco": "B1", "pavimento": "P1"},
        )
        self.assertEqual(vals, ["UND 101", "UND 102"])

    def test_pavimento_estrutural_sem_unidade_no_chip(self):
        rows = [
            ["HAB", "B1", "Pavimento 01", "", ""],
            ["HAB", "B1", "Pavimento 02", "UND 1", "0%"],
        ]
        vals = _distinct_structural_axis_values(rows, _axis_map(), "pavimento", {"bloco": "B1"})
        self.assertEqual(vals, ["Pavimento 01", "Pavimento 02"])

    def test_forward_fill_herda_apto_em_linha_de_continuacao(self):
        rows = [
            ["HAB", "B1", "P1", "101", "100%"],
            ["HAB", "B1", "P1", "", "0%"],
        ]
        axis = _axis_map()
        _forward_fill_hierarchy_axes(rows, axis)
        self.assertEqual(rows[1][3], "101")
        self.assertTrue(_is_percent_source_row(rows[1], axis, is_area_comum=False, is_manual_flat=False))

    def test_forward_fill_nao_preenche_filhos_em_linha_estrutural(self):
        axis = _axis_map()
        rows = [
            ["HAB", "B1", "P1", "101", "100%"],
            ["HAB", "B2", "", "", ""],
            ["HAB", "B1", "P2", "", ""],
        ]
        _forward_fill_hierarchy_axes(rows, axis)
        self.assertEqual(rows[1][2], "")
        self.assertEqual(rows[1][3], "")
        self.assertEqual(rows[2][3], "")

    def test_forward_fill_nao_gruda_apto_de_p1_no_pavimento_p2(self):
        """a2 de p1 não deve ganhar p2 só porque uma linha estrutural p2 veio antes."""
        axis = _axis_map()
        rows = [
            ["HAB", "B1", "P1", "a1", "75%"],
            ["HAB", "B1", "P1", "a2", "50%"],
            ["HAB", "B1", "P2", "", ""],
            ["HAB", "B1", "", "a2", "10%"],
        ]
        _forward_fill_hierarchy_axes(rows, axis)
        self.assertEqual(rows[3][2], "")

    def test_forward_fill_nova_unidade_mesmo_pavimento_sem_repetir_pav(self):
        axis = _axis_map()
        rows = [
            ["HAB", "B1", "P1", "a1", "75%"],
            ["HAB", "B1", "", "a2", "50%"],
        ]
        _forward_fill_hierarchy_axes(rows, axis)
        self.assertEqual(rows[1][2], "P1")

    def test_placeholder_nunca_vira_chip(self):
        rows = [["HAB", "B1", "Sem dados para matriz", "UND 1", ""]]
        vals = _distinct_structural_axis_values(rows, _axis_map(), "pavimento", {"bloco": "B1"})
        self.assertEqual(vals, [])

    def test_merge_matrix_axis_keys_inclui_bloco_estrutural_vazio(self):
        """Bloco só estrutural (sem apto/% ) deve aparecer na grade de visualização."""
        body = [
            ["HAB", "b1", "", "", ""],
            ["HAB", "b2", "p1", "101", "50%"],
            ["HAB", "b6", "", "", ""],
        ]
        processed = [body[0], body[1]]
        keys = _merge_matrix_axis_keys(
            body_rows=body,
            processed_rows=processed,
            axis_map=_axis_map(),
            row_axis_key="bloco",
            row_axis_col=1,
            prefilter=None,
            row_order_pref=None,
        )
        self.assertEqual(keys, ["b1", "b2", "b6"])

    def test_merge_matrix_axis_keys_respeita_row_order_orfa(self):
        body = [
            ["HAB", "b1", "", "", ""],
            ["HAB", "b5", "", "", ""],
        ]
        keys = _merge_matrix_axis_keys(
            body_rows=body,
            processed_rows=body,
            axis_map=_axis_map(),
            row_axis_key="bloco",
            row_axis_col=1,
            prefilter=None,
            row_order_pref=["b1", "b2", "b3", "b4", "b5", "b6"],
        )
        self.assertEqual(keys, ["b1", "b2", "b3", "b4", "b5", "b6"])


if __name__ == "__main__":
    unittest.main()
