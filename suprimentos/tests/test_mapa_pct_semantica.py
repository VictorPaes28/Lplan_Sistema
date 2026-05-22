"""Semântica de células de percentual (vazio, 0%, N/A)."""

from __future__ import annotations

import unittest

from suprimentos.services.mapa_controle_viewmodel import (
    _cell_pct_for_average,
    _is_pct_not_applicable,
    _parse_pct_loose,
)


class MapaPctSemanticaTests(unittest.TestCase):
    def test_vazio_e_zero(self):
        self.assertEqual(_cell_pct_for_average(""), 0)
        self.assertEqual(_cell_pct_for_average("   "), 0)
        self.assertEqual(_parse_pct_loose(""), 0)

    def test_hifen_nao_aplicavel(self):
        self.assertIsNone(_cell_pct_for_average("-"))
        self.assertIsNone(_cell_pct_for_average("--"))
        self.assertTrue(_is_pct_not_applicable("-"))
        self.assertIsNone(_parse_pct_loose("-"))

    def test_zero_e_cem_entram(self):
        self.assertEqual(_cell_pct_for_average("0"), 0)
        self.assertEqual(_cell_pct_for_average("0%"), 0)
        self.assertEqual(_cell_pct_for_average("100%"), 100)

    def test_invalido_tratado_como_zero(self):
        self.assertEqual(_cell_pct_for_average("abc"), 0)


if __name__ == "__main__":
    unittest.main()
