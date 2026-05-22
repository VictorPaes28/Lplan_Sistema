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


def is_apto_und_manual_entry_layer(query: dict, dom_mode: str = "") -> bool:
    """Espelha isAptoUndManualEntryLayer no JS (edição manual de %)."""
    setor = (query.get("setor") or "").strip()
    if _norm_setor(setor) == "AREA COMUM":
        return False
    mode = resolve_row_axis_from_query(query, dom_mode)
    if mode != "apto":
        return False
    if not (query.get("bloco") or "").strip():
        return False
    if not (query.get("pavimento") or "").strip():
        return False
    return True


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


def row_matches_parent_scope(
    row: list[str],
    axis_map: dict[str, int],
    page_filters: dict[str, str],
    row_axis_key: str,
) -> bool:
    """Espelha rowMatchesParentScope no JS (layout esparso no recorte UND)."""
    ctx = {
        "setor": (page_filters.get("setor") or "").strip(),
        "bloco": (page_filters.get("bloco") or "").strip(),
        "pavimento": (page_filters.get("pavimento") or "").strip(),
        "level": row_axis_key or "apto",
    }
    parent_f = parent_filters_for_level(ctx)
    for key, value in parent_f.items():
        idx = axis_map.get(key)
        if idx is None:
            continue
        row_val = str(row[idx] or "").strip()
        if not row_val:
            continue
        if row_val != str(value).strip():
            return False
    return True


def apply_percent_patch_to_layout_row(
    rows: list[list[str]],
    *,
    page_filters: dict[str, str],
    row_label: str,
    col_index: int,
    text: str,
    row_axis_key: str = "apto",
) -> bool:
    """Espelha applyCellTextToLayoutRows para patch de % (rótulo + escopo pai)."""
    axis_map = build_axis_map()
    level_idx = axis_map.get(row_axis_key, axis_map["apto"])
    want = row_label.strip()
    for row in rows[1:]:
        if not row_matches_parent_scope(row, axis_map, page_filters, row_axis_key):
            continue
        if str(row[level_idx] or "").strip() != want:
            continue
        while len(row) <= col_index:
            row.append("")
        row[col_index] = text
        return True
    return False


def parent_filters_for_level(context: dict) -> dict[str, str]:
    f = {}
    if context.get("setor"):
        f["setor"] = context["setor"]
    if context.get("level") in ("pavimento", "apto") and context.get("bloco"):
        f["bloco"] = context["bloco"]
    if context.get("level") == "apto" and context.get("pavimento"):
        f["pavimento"] = context["pavimento"]
    return f


def new_canonical_row(header_len: int, context: dict, label: str) -> list[str]:
    axis_map = build_axis_map()
    row = [""] * header_len
    for key in ("setor", "bloco", "pavimento", "apto"):
        idx = axis_map.get(key)
        val = context.get(key)
        if idx is not None and val:
            row[idx] = val
    level_idx = axis_map.get(context.get("level"))
    if level_idx is not None:
        row[level_idx] = label
    return row


def apply_create_row_delta(all_rows: list[list[str]], context: dict, label: str) -> list[list[str]]:
    """Espelha applyCreateRowToLayout (delta no layout canônico, sem tbody)."""
    axis_map = build_axis_map()
    header = all_rows[0]
    parent_f = parent_filters_for_level(context)
    level_idx = axis_map.get(context.get("level"))
    if level_idx is None:
        return all_rows
    for row in all_rows[1:]:
        if not isinstance(row, list):
            continue
        if parent_f and not row_matches_filters(row, axis_map, parent_f):
            continue
        if str(row[level_idx] or "").strip() == label:
            return all_rows
    return [header, *all_rows[1:], new_canonical_row(len(header), context, label)]


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

    def test_matrix_mode_bloco_com_bloco_habitacao_vira_pavimento(self):
        """Drill com matrix_mode=bloco na URL não pode gravar filho no eixo BLOCO."""
        q = {"setor": "HAB", "bloco": "Bloco Teste", "matrix_mode": "bloco"}
        self.assertEqual(resolve_row_axis_from_query(q), "pavimento")
        self.assertEqual(
            _resolve_matrix_mode(
                "bloco",
                {"setor": "HAB", "bloco": "Bloco Teste", "pavimento": "", "apto": ""},
            ),
            "pavimento",
        )

    def test_6_create_row_delta_preserva_outras_camadas(self):
        header = ["SETOR", "BLOCO", "PAVIMENTO", "APTO", "ATV"]
        existing = [
            header,
            ["HAB", "teste", "1P", "101", "50"],
            ["HAB", "outro", "2P", "201", "30"],
        ]
        merged = apply_create_row_delta(
            existing,
            {
                "setor": "HAB",
                "bloco": "teste",
                "pavimento": "",
                "level": "pavimento",
            },
            "TERREO",
        )
        blocos = {r[1] for r in merged[1:]}
        self.assertIn("outro", blocos)
        self.assertIn("teste", blocos)
        self.assertEqual(len([r for r in merged[1:] if r[1] == "outro"]), 1)
        terreo = [r for r in merged[1:] if r[1] == "teste" and r[2] == "TERREO"]
        self.assertEqual(len(terreo), 1)
        self.assertEqual(terreo[0][3], "")

    def test_create_bloco_na_raiz_append_sem_apagar_filhos(self):
        header = ["SETOR", "BLOCO", "PAVIMENTO", "APTO", "ATV"]
        existing = [
            header,
            ["HAB", "Bloco A", "P1", "101", ""],
            ["HAB", "Bloco B", "X", "201", ""],
        ]
        merged = apply_create_row_delta(
            existing,
            {"setor": "HAB", "bloco": "", "pavimento": "", "level": "bloco"},
            "Bloco C",
        )
        self.assertEqual(len(merged), 4)
        self.assertEqual(merged[3][1], "Bloco C")
        self.assertEqual(merged[1][2], "P1")

    def test_page_key_por_url_distinto(self):
        """Rascunhos por página usam pathname+search (camadas diferentes)."""
        k_root = f"/engenharia/mapa-controle/?{urlencode({'obra': 6})}"
        k_bloco = f"/engenharia/mapa-controle/?{urlencode({'obra': 6, 'bloco': 'teste'})}"
        self.assertNotEqual(k_root, k_bloco)
        self.assertEqual(resolve_row_axis_from_query({"obra": "6"}), "bloco")
        self.assertEqual(resolve_row_axis_from_query({"obra": "6", "bloco": "teste"}), "pavimento")

    def test_fluxo_toolbar_insert_mesmo_eixo(self):
        """+ Linha na toolbar registra create_row com contexto de pavimento."""
        ctx = {"setor": "", "bloco": "teste", "pavimento": "", "level": "pavimento"}
        for label in ("via_toolbar_a", "via_toolbar_b"):
            row = new_canonical_row(5, ctx, label)
            self.assertEqual(row[1], "teste")
            self.assertEqual(row[2], label)

    def test_edicao_percentual_somente_apto_und(self):
        self.assertFalse(is_apto_und_manual_entry_layer({"obra": "6"}))
        self.assertFalse(
            is_apto_und_manual_entry_layer({"obra": "6", "setor": "HAB", "bloco": "B1"})
        )
        self.assertTrue(
            is_apto_und_manual_entry_layer(
                {"obra": "6", "setor": "HAB", "bloco": "B1", "pavimento": "1P"}
            )
        )

    def test_area_comum_nunca_edita_percentual(self):
        self.assertFalse(
            is_apto_und_manual_entry_layer(
                {"setor": "ÁREA COMUM", "bloco": "A", "pavimento": "TÉRREO"}
            )
        )
        self.assertFalse(
            is_apto_und_manual_entry_layer(
                {"setor": "AREA COMUM", "bloco": "A"},
                dom_mode="pavimento",
            )
        )

    def test_pill_por_unidade_sem_pavimento_nao_edita(self):
        self.assertFalse(
            is_apto_und_manual_entry_layer(
                {"setor": "HAB", "bloco": "B1", "matrix_mode": "apto"},
            )
        )

    def test_percent_patch_em_linha_esparso_no_recorte_und(self):
        """Layout só com APTO na linha ainda recebe % quando URL tem bloco+pavimento."""
        header = ["SETOR", "BLOCO", "PAVIMENTO", "APTO", "ATV1"]
        rows = [
            header,
            ["", "", "", "101", "0%"],
            ["", "", "", "102", ""],
        ]
        page_filters = {"setor": "HAB", "bloco": "B1", "pavimento": "1P"}
        self.assertFalse(row_matches_filters(rows[1], build_axis_map(), page_filters))
        self.assertTrue(row_matches_parent_scope(rows[1], build_axis_map(), page_filters, "apto"))
        ok = apply_percent_patch_to_layout_row(
            rows,
            page_filters=page_filters,
            row_label="101",
            col_index=4,
            text="10%",
        )
        self.assertTrue(ok)
        self.assertEqual(rows[1][4], "10%")


if __name__ == "__main__":
    unittest.main()
