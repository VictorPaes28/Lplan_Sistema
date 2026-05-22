"""Chips/filtros de camada no Mapa de Controle (eixo estrutural, não percentual)."""

from __future__ import annotations

import unittest

from suprimentos.services.mapa_controle_viewmodel import (
    _clean_layer_prefilter,
    _distinct_structural_axis_values,
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

    def test_placeholder_nunca_vira_chip(self):
        rows = [["HAB", "B1", "Sem dados para matriz", "UND 1", ""]]
        vals = _distinct_structural_axis_values(rows, _axis_map(), "pavimento", {"bloco": "B1"})
        self.assertEqual(vals, [])


if __name__ == "__main__":
    unittest.main()
