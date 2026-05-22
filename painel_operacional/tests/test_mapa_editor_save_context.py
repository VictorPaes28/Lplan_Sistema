"""Validação da lógica de contexto ao salvar o editor de mapa (espelha editar_mapa_controle.js)."""

from __future__ import annotations

import unittest
from urllib.parse import urlencode

from suprimentos.views_controle import _resolve_matrix_mode


def _norm_setor(setor: str) -> str:
    import unicodedata

    raw = unicodedata.normalize("NFD", str(setor or ""))
    return "".join(c for c in raw if unicodedata.category(c) != "Mn").strip().upper()


def resolve_row_axis_from_query(query: dict, dom_mode: str = "") -> str:
    """Espelha resolveMatrixMode + inferRowAxisKeyFromPage no JS."""
    scope = {
        "requestedMode": (query.get("matrix_mode") or dom_mode or "").strip().lower(),
        "setor": (query.get("setor") or "").strip(),
        "bloco": (query.get("bloco") or "").strip(),
        "pavimento": (query.get("pavimento") or "").strip(),
        "apto": (query.get("apto") or "").strip(),
    }
    selected = {
        "setor": scope["setor"],
        "bloco": scope["bloco"],
        "pavimento": scope["pavimento"],
        "apto": scope["apto"],
    }
    py_mode = _resolve_matrix_mode(scope["requestedMode"], selected)
    return py_mode


def build_axis_map() -> dict[str, int]:
    return {"setor": 0, "bloco": 1, "pavimento": 2, "apto": 3}


def build_export_row(
    *,
    filters: dict[str, str],
    row_axis_key: str,
    row_label: str,
    col_count: int = 5,
) -> list[str]:
    """Espelha exportTableBodyRows (uma linha visível)."""
    axis_map = build_axis_map()
    row = [""] * col_count
    for key in ("setor", "bloco", "pavimento", "apto"):
        idx = axis_map.get(key)
        if idx is not None and filters.get(key):
            row[idx] = filters[key]
    axis_idx = axis_map.get(row_axis_key)
    if axis_idx is not None:
        row[axis_idx] = row_label
    return row


def row_matches_filters(row: list[str], axis_map: dict[str, int], filters: dict[str, str]) -> bool:
    for key, value in filters.items():
        if not value:
            continue
        idx = axis_map.get(key)
        if idx is None:
            continue
        if str(row[idx] or "").strip() != str(value).strip():
            return False
    return True


def replace_layout_rows_scoped(
    all_rows: list[list[str]],
    exported: list[list[str]],
    filters: dict[str, str],
) -> list[list[str]]:
    """Espelha replaceLayoutRowsFromTableExport com recorte ativo."""
    axis_map = build_axis_map()
    header = all_rows[0]
    has_scoped = any(
        filters.get(k) and axis_map.get(k) is not None for k in ("setor", "bloco", "pavimento", "apto")
    )
    if not has_scoped:
        return [header, *exported]
    kept = [
        row
        for row in all_rows[1:]
        if isinstance(row, list) and not row_matches_filters(row, axis_map, filters)
    ]
    return [header, *kept, *exported]


class MapaEditorSaveContextTests(unittest.TestCase):
    def test_1_raiz_cria_bloco(self):
        q = {"obra": "6", "ambiente_id": "5"}
        mode = resolve_row_axis_from_query(q)
        self.assertEqual(mode, "bloco")
        row = build_export_row(filters={}, row_axis_key=mode, row_label="teste")
        self.assertEqual(row[1], "teste")
        self.assertEqual(row[2], "")
        self.assertEqual(row[3], "")

    def test_2_dentro_bloco_cria_pavimento_filho(self):
        q = {"obra": "6", "ambiente_id": "5", "bloco": "teste"}
        mode = resolve_row_axis_from_query(q)
        self.assertEqual(mode, "pavimento")
        row = build_export_row(
            filters={"bloco": "teste"},
            row_axis_key=mode,
            row_label="1P",
        )
        self.assertEqual(row[1], "teste")
        self.assertEqual(row[2], "1P")
        self.assertEqual(row[3], "")

    def test_3_terceiro_nivel_cria_apto(self):
        q = {"obra": "6", "bloco": "teste", "pavimento": "1P"}
        mode = resolve_row_axis_from_query(q)
        self.assertEqual(mode, "apto")
        row = build_export_row(
            filters={"bloco": "teste", "pavimento": "1P"},
            row_axis_key=mode,
            row_label="101",
        )
        self.assertEqual(row[1], "teste")
        self.assertEqual(row[2], "1P")
        self.assertEqual(row[3], "101")

    def test_drill_sem_matrix_mode_na_url_igual_backend(self):
        """Link row-link sem matrix_mode deve inferir pavimento, não bloco."""
        q = {"setor": "HAB", "bloco": "B1"}
        self.assertEqual(resolve_row_axis_from_query(q), "pavimento")
        self.assertEqual(
            _resolve_matrix_mode("", {"setor": "HAB", "bloco": "B1", "pavimento": "", "apto": ""}),
            "pavimento",
        )

    def test_matrix_mode_bloco_com_bloco_no_recorte_vira_pavimento(self):
        """Pill 'Por bloco' ativo dentro de um bloco ainda grava pavimento (área comum / recorte)."""
        q = {"setor": "ÁREA COMUM", "bloco": "A", "matrix_mode": "bloco"}
        self.assertEqual(resolve_row_axis_from_query(q), "pavimento")

    def test_6_merge_preserva_outras_camadas(self):
        header = ["SETOR", "BLOCO", "PAVIMENTO", "APTO", "ATV"]
        existing = [
            header,
            ["HAB", "teste", "1P", "101", "50%"],
            ["HAB", "outro", "2P", "201", "30%"],
        ]
        exported = [
            build_export_row(
                filters={"bloco": "teste"},
                row_axis_key="pavimento",
                row_label="TERREO",
            )
        ]
        merged = replace_layout_rows_scoped(
            existing,
            exported,
            filters={"bloco": "teste"},
        )
        blocos = {r[1] for r in merged[1:]}
        self.assertIn("outro", blocos)
        self.assertIn("teste", blocos)
        teste_rows = [r for r in merged[1:] if r[1] == "teste"]
        self.assertEqual(len(teste_rows), 1)
        self.assertEqual(teste_rows[0][2], "TERREO")

    def test_page_key_por_url_distinto(self):
        """Rascunhos por página usam pathname+search (camadas diferentes)."""
        k_root = f"/engenharia/mapa-controle/?{urlencode({'obra': 6})}"
        k_bloco = f"/engenharia/mapa-controle/?{urlencode({'obra': 6, 'bloco': 'teste'})}"
        self.assertNotEqual(k_root, k_bloco)
        self.assertEqual(resolve_row_axis_from_query({"obra": "6"}), "bloco")
        self.assertEqual(resolve_row_axis_from_query({"obra": "6", "bloco": "teste"}), "pavimento")

    def test_fluxo_inline_e_toolbar_mesmo_eixo(self):
        """+ inline e + Linha usam applyInsertRow + mesmo export no save."""
        for label in ("via_inline", "via_toolbar"):
            row = build_export_row(
                filters={"bloco": "teste"},
                row_axis_key="pavimento",
                row_label=label,
            )
            self.assertEqual(row[1], "teste")
            self.assertEqual(row[2], label)


if __name__ == "__main__":
    unittest.main()
