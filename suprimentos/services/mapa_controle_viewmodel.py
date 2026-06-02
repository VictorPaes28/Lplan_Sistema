from __future__ import annotations

from urllib.parse import urlencode

from django.db.models import Q

from suprimentos.models import ImportacaoMapaServico, ItemMapaServico, ItemMapaServicoStatusRef


def _norm_token(value: object) -> str:
    return str(value or "").strip().upper()


def _status_bucket_from_pct(value):
    try:
        v = float(value)
    except (TypeError, ValueError):
        return "nao_iniciado"
    if v >= 99.5:
        return "concluido"
    if v <= 0:
        return "nao_iniciado"
    return "em_andamento"


def _matches_status_filter(value, status_filter: str) -> bool:
    if not status_filter:
        return True
    return _status_bucket_from_pct(value) == status_filter


_PCT_NA_TOKENS = frozenset(
    {
        "-",
        "--",
        "N/A",
        "NA",
        "N A",
        "NAO SE APLICA",
        "NÃO SE APLICA",
    }
)


def _is_pct_not_applicable(value) -> bool:
    raw = str(value or "").strip()
    if not raw:
        return False
    return _norm_token(raw) in _PCT_NA_TOKENS


def _cell_pct_for_average(value):
    """
    Percentual para média consolidada.
    - vazio → 0 (entra no denominador);
    - \"-\" / N/A → None (não entra);
    - número → valor 0–100;
    - inválido → 0 (não quebra).
    """
    raw = str(value or "").strip()
    if not raw:
        return 0
    token = _norm_token(raw)
    if token in _PCT_NA_TOKENS:
        return None
    had_percent = "%" in raw
    normalized = raw.replace("%", "").replace(",", ".").strip()
    try:
        num = float(normalized)
    except (TypeError, ValueError):
        return 0
    if not had_percent and -1.0 <= num <= 1.0:
        num *= 100.0
    num = max(0.0, min(100.0, num))
    if abs(num - round(num)) < 0.01:
        return int(round(num))
    return round(num, 1)


def _parse_pct_loose(value):
    """Parse para exibição/status; None apenas quando N/A explícito (\"-\")."""
    if _is_pct_not_applicable(value):
        return None
    return _cell_pct_for_average(value)


def _fmt_pct(value):
    try:
        num = float(value)
    except (TypeError, ValueError):
        return ""
    if abs(num - round(num)) < 0.01:
        return f"{int(round(num))}%"
    return f"{round(num, 1)}%"


def _is_total_header_label(value: str) -> bool:
    token = _norm_token(value)
    if not token:
        return False
    return token == "TOTAL" or token == "TOTAL GERAL" or token.startswith("TOTAL")


def _norm_key_setor(value: object) -> str:
    import unicodedata

    raw = unicodedata.normalize("NFD", str(value or ""))
    raw = "".join(c for c in raw if unicodedata.category(c) != "Mn")
    return raw.strip().upper()


def _setor_e_area_comum(setor: str) -> bool:
    if not (setor or "").strip():
        return False
    return _norm_key_setor(setor) == "AREA COMUM"


def _is_placeholder_matrix_label(value: object) -> bool:
    token = str(value or "").strip().lower().rstrip(".")
    return token == "sem dados para matriz"


def _avg_pct_total(values: list[float]) -> float | None:
    """Média para Total da linha / rodapé — sempre 2 casas decimais."""
    if not values:
        return None
    return round(sum(values) / len(values), 2)


def _avg_pct_display(values: list[float]) -> float | None:
    return _avg_pct_total(values)


def _append_pct_for_average(bucket: list[float], value) -> None:
    pct = _cell_pct_for_average(value)
    if pct is not None:
        bucket.append(float(pct))


def _append_pct_for_classic_average(bucket: list[float], value) -> None:
    """
    Média clássica do mapa:
    - "-" conta como 0;
    - N/A explícito não entra no denominador;
    - vazio não entra;
    - número entra em 0..100.
    """
    raw = str(value or "").strip()
    if not raw:
        return
    token = _norm_token(raw)
    if token in {"-", "--"}:
        bucket.append(0.0)
        return
    if token in {"N/A", "NA", "N A", "NAO SE APLICA", "NÃO SE APLICA"}:
        return
    pct = _cell_pct_for_average(value)
    if pct is not None:
        bucket.append(float(pct))


def _append_pct_for_context_average(
    bucket: list[float],
    value,
    *,
    treat_empty_as_zero: bool = False,
) -> None:
    """
    Agregação contextual para média:
    - modo clássico padrão: vazio não entra;
    - em template manual: vazio/missing entra como 0 para manter denominador das atividades.
    """
    raw = str(value or "").strip()
    if not raw:
        if treat_empty_as_zero:
            bucket.append(0.0)
        return
    _append_pct_for_classic_average(bucket, value)


def _valid_axis_label(value: object) -> bool:
    val = str(value or "").strip()
    return bool(val) and not _is_placeholder_matrix_label(val)


def _is_percent_source_row(row: list, axis_map: dict, *, is_area_comum: bool, is_manual_flat: bool) -> bool:
    """Linhas-fonte de % (UND/APTO em Habitação; pavimento em Área Comum). Só para cálculo, não para listar eixo."""
    if not isinstance(row, list):
        return False
    apto_idx = axis_map.get("apto")
    if isinstance(apto_idx, int):
        apto_val = str(row[apto_idx] if apto_idx < len(row) else "").strip()
        if _is_placeholder_matrix_label(apto_val):
            return False
        if apto_val:
            return True
        pav_idx = axis_map.get("pavimento")
        bloco_idx = axis_map.get("bloco")
        pav_val = str(row[pav_idx] if isinstance(pav_idx, int) and pav_idx < len(row) else "").strip()
        bloco_val = str(row[bloco_idx] if isinstance(bloco_idx, int) and bloco_idx < len(row) else "").strip()
        if pav_val and not _is_placeholder_matrix_label(pav_val):
            return _row_has_non_axis_cell_data(row, axis_map)
        if bloco_val and not pav_val and not _is_placeholder_matrix_label(bloco_val):
            # Importação / planilha com % direto no bloco (sem pavimento/UND preenchidos).
            return _row_has_non_axis_cell_data(row, axis_map)
        return False
    pav_idx = axis_map.get("pavimento")
    bloco_idx = axis_map.get("bloco")
    pav_val = str(row[pav_idx] if isinstance(pav_idx, int) and pav_idx < len(row) else "").strip()
    bloco_val = str(row[bloco_idx] if isinstance(bloco_idx, int) and bloco_idx < len(row) else "").strip()

    # Layout sem coluna APTO (ex.: import BLOCO + PAVIMENTO).
    if isinstance(pav_idx, int):
        if _is_placeholder_matrix_label(pav_val):
            return False
        if pav_val:
            if is_area_comum:
                return True
            return _row_has_non_axis_cell_data(row, axis_map)
    if is_manual_flat and isinstance(bloco_idx, int):
        if _is_placeholder_matrix_label(bloco_val):
            return False
        return bool(bloco_val) and _row_has_non_axis_cell_data(row, axis_map)
    if isinstance(bloco_idx, int) and bloco_val and not pav_val and not _is_placeholder_matrix_label(bloco_val):
        return _row_has_non_axis_cell_data(row, axis_map)
    return False


def _matrix_row_is_visible_unit(row: list, row_axis_col: int, activity_col_indices: list[int]) -> bool:
    """Exibe só unidades com nome no eixo ou com % lançado (evita slots vazios do preset antigo)."""
    if not isinstance(row, list):
        return False
    if isinstance(row_axis_col, int) and 0 <= row_axis_col < len(row):
        if str(row[row_axis_col] or "").strip():
            return True
    for idx in activity_col_indices:
        if isinstance(idx, int) and idx < len(row) and str(row[idx] or "").strip():
            return True
    return False


def _apply_preferred_axis_order(keys: list[str], preferred: list | None) -> list[str]:
    """Mantém ordem gravada no layout (editor) quando existir; demais chaves no fim."""
    if not preferred or not isinstance(preferred, list):
        return keys
    seen = set(keys)
    ordered: list[str] = []
    for raw in preferred:
        val = str(raw or "").strip()
        if not val or val not in seen or val in ordered:
            continue
        ordered.append(val)
    for val in keys:
        if val not in ordered:
            ordered.append(val)
    return ordered


def _distinct_structural_axis_keys(rows: list[list], row_axis_col: int) -> list[str]:
    """Valores do eixo exibido na camada atual (bloco/pavimento/apto), inclusive linhas só estruturais."""
    keys: list[str] = []
    seen: set[str] = set()
    for row in rows:
        if not isinstance(row, list):
            continue
        val = str(row[row_axis_col] if row_axis_col < len(row) else "").strip()
        if not _valid_axis_label(val) or val in seen:
            continue
        seen.add(val)
        keys.append(val)
    return keys


def _matrix_display_prefilter(filter_selected: dict, row_axis_key: str) -> dict[str, str]:
    """Recorte hierárquico dos eixos-pai para listar chaves estruturais na grade."""
    out: dict[str, str] = {}
    for key in ("setor", "bloco", "pavimento", "apto"):
        if key == row_axis_key:
            break
        val = str(filter_selected.get(key) or "").strip()
        if val:
            out[key] = val
    return out


def _merge_matrix_axis_keys(
    *,
    body_rows: list[list],
    processed_rows: list[list],
    axis_map: dict,
    row_axis_key: str,
    row_axis_col: int,
    prefilter: dict[str, str] | None,
    row_order_pref: list | None,
) -> list[str]:
    """
    Chaves do eixo na grade consolidada (camada bloco/pavimento/apto).
    Inclui linhas estruturais do layout sem apto e sem % — mesma regra dos chips de camada
    e da ordem gravada no editor (row_order_*).
    """
    keys_body = _distinct_structural_axis_values(body_rows, axis_map, row_axis_key, prefilter)
    keys_proc = _distinct_structural_axis_keys(processed_rows, row_axis_col)
    seen: set[str] = set()
    merged: list[str] = []
    for k in keys_body + keys_proc:
        if k in seen:
            continue
        seen.add(k)
        merged.append(k)
    if isinstance(row_order_pref, list):
        for raw in row_order_pref:
            val = str(raw or "").strip()
            if not val or not _valid_axis_label(val) or val in seen:
                continue
            seen.add(val)
            merged.append(val)
    return _apply_preferred_axis_order(merged, row_order_pref)


def _clean_layer_prefilter(prefilter: dict | None) -> dict[str, str]:
    """Remove chaves vazias do recorte (evita setor=None invalidar linhas do layout)."""
    if not isinstance(prefilter, dict):
        return {}
    return {
        k: str(v or "").strip()
        for k, v in prefilter.items()
        if str(v or "").strip()
    }


def _row_matches_layer_prefilter(row: list, axis_map: dict, prefilter: dict | None) -> bool:
    """
    Recorte pai para chips/facets.
    Célula vazia no eixo não invalida a linha (layout esparso no recorte de UND).
    """
    pf = _clean_layer_prefilter(prefilter)
    if not pf:
        return True
    for key, wanted in pf.items():
        idx = axis_map.get(key)
        if not isinstance(idx, int):
            continue
        cur = str(row[idx] if idx < len(row) else "").strip()
        if not cur:
            continue
        if cur != wanted:
            return False
    return True


def _distinct_structural_axis_values(
    rows_src: list[list],
    axis_map: dict,
    axis_key: str,
    prefilter: dict | None = None,
) -> list[str]:
    """Lista valores do eixo para chips — estrutural, sem exigir percentual lançado."""
    idx = axis_map.get(axis_key)
    if not isinstance(idx, int):
        return []
    pf = _clean_layer_prefilter(prefilter)
    keys: list[str] = []
    seen: set[str] = set()
    for row in rows_src:
        if not isinstance(row, list):
            continue
        if not _row_matches_layer_prefilter(row, axis_map, pf):
            continue
        val = str(row[idx] if idx < len(row) else "").strip()
        if not _valid_axis_label(val) or val in seen:
            continue
        seen.add(val)
        keys.append(val)
    return keys


def _row_has_non_axis_cell_data(row: list, axis_map: dict) -> bool:
    """True se há dado fora dos eixos hierárquicos (ex.: % em linha de continuação de importação)."""
    skip = {idx for idx in axis_map.values() if isinstance(idx, int)}
    for i, cell in enumerate(row):
        if i in skip:
            continue
        if str(cell or "").strip():
            return True
    return False


def _skip_hierarchy_forward_fill(
    key: str,
    *,
    structural_bloco_row: bool,
    structural_pavimento_row: bool,
    apto_at_start: str,
    pav_at_start: str,
    last: dict[str, str],
) -> bool:
    if structural_bloco_row and key in ("pavimento", "apto"):
        return True
    if structural_pavimento_row and key == "apto":
        return True
    # apto preenchido sem pavimento: após linha estrutural de pavimento last["apto"] foi zerado —
    # não preencher pavimento (evita grudar a2 de p1 no p2 recém-criado).
    if key == "pavimento" and apto_at_start and not pav_at_start and not last.get("apto"):
        return True
    return False


def _forward_fill_hierarchy_axes(rows: list[list], axis_map: dict) -> None:
    """
    Propaga setor/bloco/pavimento/apto para linhas de continuação (mesma unidade, várias linhas de serviço).
    Modifica as linhas in-place antes de filtrar ou consolidar percentuais.
    Linhas estruturais do editor (bloco ou pavimento sem filhos) não recebem forward-fill nos eixos vazios.
    """

    def _axis_at_start(row_vals: list, key: str) -> str:
        idx = axis_map.get(key)
        if not isinstance(idx, int):
            return ""
        return str(row_vals[idx] if idx < len(row_vals) else "").strip()

    chain = ["setor", "bloco", "pavimento", "apto"]
    last: dict[str, str] = {k: "" for k in chain}
    for row in rows:
        if not isinstance(row, list):
            continue
        bloco_at_start = _axis_at_start(row, "bloco")
        pav_at_start = _axis_at_start(row, "pavimento")
        apto_at_start = _axis_at_start(row, "apto")
        structural_bloco_row = bool(bloco_at_start and not pav_at_start and not apto_at_start)
        structural_pavimento_row = bool(
            pav_at_start
            and not apto_at_start
            and not _row_has_non_axis_cell_data(row, axis_map)
        )
        for key in chain:
            idx = axis_map.get(key)
            if not isinstance(idx, int):
                continue
            while len(row) <= idx:
                row.append("")
            val = str(row[idx] or "").strip()
            if val:
                if key == "setor" and val != last.get("setor"):
                    last["bloco"] = ""
                    last["pavimento"] = ""
                    last["apto"] = ""
                elif key == "bloco" and val != last.get("bloco"):
                    last["pavimento"] = ""
                    last["apto"] = ""
                elif key == "pavimento" and val != last.get("pavimento"):
                    last["apto"] = ""
                last[key] = val
            elif last.get(key):
                if _skip_hierarchy_forward_fill(
                    key,
                    structural_bloco_row=structural_bloco_row,
                    structural_pavimento_row=structural_pavimento_row,
                    apto_at_start=apto_at_start,
                    pav_at_start=pav_at_start,
                    last=last,
                ):
                    continue
                row[idx] = last[key]


def _pct_for_matrix_average(cell: dict) -> float | None:
    """
    Valor para média de totais (linha/coluna/geral).
    0% exibido na grade entra; N/A (\"-\") não entra; vazio exibido como 0% conta como zero.
    """
    if not isinstance(cell, dict):
        return None
    if _is_pct_not_applicable(cell.get("raw")):
        return None
    raw = str(cell.get("raw") or "").strip()
    if raw:
        val = _pct_from_display_cell(cell)
        return float(val) if val is not None else None
    pct = cell.get("pct")
    if pct is not None:
        return float(pct)
    return 0.0


_STABLE_CELL_COLOR_SEP = "\u001f"


def _stable_cell_color_key(
    *,
    bloco: str = "",
    pavimento: str = "",
    row_label: str = "",
    activity: str = "",
) -> str:
    """Chave estável das cores manuais (espelha editar_mapa_controle.js stableCellColorKey)."""
    return _STABLE_CELL_COLOR_SEP.join(
        [
            str(bloco or "").strip(),
            str(pavimento or "").strip(),
            str(row_label or "").strip(),
            str(activity or "").strip(),
        ]
    )


def _apply_matrix_cell_colors(
    matrix: dict,
    cell_colors: dict,
    *,
    bloco: str = "",
    pavimento: str = "",
) -> None:
    """Anexa manual_color nas células da grade para exibição fora do modo edição."""
    if not isinstance(matrix, dict) or not isinstance(cell_colors, dict) or not cell_colors:
        return
    bloco_s = str(bloco or "").strip()
    pav_s = str(pavimento or "").strip()
    for row in matrix.get("rows") or []:
        if not isinstance(row, dict):
            continue
        row_label = str(row.get("row_label") or row.get("row_key") or "").strip()
        for cell in row.get("cells") or []:
            if not isinstance(cell, dict):
                continue
            activity = str(cell.get("atividade") or "").strip()
            key = _stable_cell_color_key(
                bloco=bloco_s,
                pavimento=pav_s,
                row_label=row_label,
                activity=activity,
            )
            hex_color = cell_colors.get(key)
            if hex_color:
                cell["manual_color"] = str(hex_color).strip()


def _row_total_from_display_cells(matrix_row: dict) -> int | float | None:
    """Total da linha = média das atividades com lançamento exibido (alinha a _build_matrix_payload)."""
    row_vals: list[float] = []
    for cell in matrix_row.get("cells") or []:
        if not isinstance(cell, dict):
            continue
        raw = str(cell.get("raw") or "").strip()
        if not raw:
            continue
        val = _pct_from_display_cell(cell)
        if val is not None:
            row_vals.append(float(val))
    return _avg_pct_total(row_vals)


def _pct_from_display_cell(cell: dict) -> float | None:
    """Valor numérico da célula exibida (0% explícito entra; vazio/N/A não)."""
    if not isinstance(cell, dict):
        return None
    raw = str(cell.get("raw") or "").strip()
    if not raw:
        return None
    if _is_pct_not_applicable(raw):
        return None
    pct = cell.get("pct")
    if pct is not None:
        return float(pct)
    parsed = _cell_pct_for_average(cell.get("raw"))
    return float(parsed) if parsed is not None else None


def _pct_from_footer_cell(cell: dict) -> float | None:
    """Rodapé por coluna = média das linhas visíveis (0% exibido entra; N/A não)."""
    return _pct_for_matrix_average(cell)


def _footer_totals_from_matrix_display(
    matrix_rows: list,
    activity_labels: list[tuple[int, str]],
) -> tuple[list[dict], list[float]]:
    """
    Total da coluna (rodapé) = média das linhas exibidas na grade naquela coluna.
    Zero é dado válido; ausente/N/A não entra no denominador.
    """
    labels = [lbl for _idx, lbl in activity_labels]
    buckets: dict[str, list[float]] = {lbl: [] for lbl in labels}
    all_values: list[float] = []
    for row in matrix_rows:
        if not isinstance(row, dict):
            continue
        for cell in row.get("cells") or []:
            if not isinstance(cell, dict):
                continue
            label = str(cell.get("atividade") or "").strip()
            if label not in buckets:
                continue
            val = _pct_from_footer_cell(cell)
            if val is None:
                continue
            buckets[label].append(val)
            all_values.append(val)
    totais: list[dict] = []
    for label in labels:
        vals = buckets.get(label) or []
        if not vals:
            totais.append({"atividade": label, "pct": None})
            continue
        pct = _avg_pct_total(vals)
        totais.append({"atividade": label, "pct": pct})
    return totais, all_values


def _grand_total_from_matrix_rows(matrix_rows: list) -> float | None:
    """Total geral (canto inferior direito) = média de todas as células exibidas (0% entra)."""
    values: list[float] = []
    for row in matrix_rows:
        if not isinstance(row, dict):
            continue
        for cell in row.get("cells") or []:
            val = _pct_for_matrix_average(cell)
            if val is not None:
                values.append(val)
    return _avg_pct_total(values)


def _percent_rows_for_axis_key(percent_source_rows: list[list], row_axis_col: int, axis_key_value: str) -> list[list]:
    want = str(axis_key_value or "").strip()
    if not want:
        return []
    matched = []
    for row in percent_source_rows:
        if not isinstance(row, list):
            continue
        cur = str(row[row_axis_col] if row_axis_col < len(row) else "").strip()
        if cur == want:
            matched.append(row)
    return matched


def _consolidated_activity_cell_display(values: list[float], *, has_percent_units: bool) -> str:
    if values:
        avg = sum(values) / len(values)
        return _fmt_pct(avg)
    if has_percent_units:
        return "-"
    return "0%"


def _rows_share_single_apto(rows: list[list], axis_map: dict | None) -> bool:
    """Várias linhas-fonte do mesmo apto (continuação de serviço) — vazio na coluna não é 0%."""
    if not isinstance(axis_map, dict):
        return False
    apto_idx = axis_map.get("apto")
    if not isinstance(apto_idx, int):
        return False
    keys: set[str] = set()
    for row in rows:
        if not isinstance(row, list):
            continue
        keys.add(str(row[apto_idx] if apto_idx < len(row) else "").strip())
    keys.discard("")
    return len(keys) <= 1


def _consolidated_display_for_column_rows(
    rows: list[list],
    col_idx: int,
    *,
    infer_zero_for_empty: bool = True,
    axis_map: dict | None = None,
) -> str:
    """
    Consolida uma coluna de atividade para um eixo (pavimento/bloco/UND).
    - vazio sem lançamento → 0% (camadas estruturais) ou vazio (UND na grade);
    - só \"-\" nas linhas-fonte → N/A (-);
    - com números → média.
    """
    if not rows:
        return "0%"
    if len(rows) == 1 and not infer_zero_for_empty:
        row = rows[0]
        if not isinstance(row, list):
            return ""
        raw_cell = row[col_idx] if col_idx < len(row) else ""
        if _is_pct_not_applicable(raw_cell):
            return "-"
        raw_txt = str(raw_cell or "").strip()
        if not raw_txt:
            return ""
        parsed = _parse_pct_loose(raw_cell)
        if parsed is not None:
            return _fmt_pct(parsed)
        return raw_txt
    bucket: list[float] = []
    saw_na = False
    saw_launch = False
    for row in rows:
        if not isinstance(row, list):
            continue
        raw_cell = row[col_idx] if col_idx < len(row) else ""
        if _is_pct_not_applicable(raw_cell):
            saw_na = True
            continue
        if str(raw_cell or "").strip():
            saw_launch = True
            _append_pct_for_average(bucket, raw_cell)
        elif infer_zero_for_empty and len(rows) > 1 and not _rows_share_single_apto(rows, axis_map):
            saw_launch = True
            bucket.append(0.0)
    if bucket:
        avg = sum(bucket) / len(bucket)
        return _fmt_pct(avg)
    if saw_na and not saw_launch:
        return "-"
    return "0%" if infer_zero_for_empty else ""


def _consolidated_column_across_apto_units(
    rows: list[list],
    col_idx: int,
    axis_map: dict,
    activity_col_indices: list[int],
    *,
    infer_zero_for_empty: bool = True,
) -> str:
    """
    Pavimento/bloco: média entre unidades (aptos), cada unidade consolida suas linhas de continuação.
    Ignora linhas sem apto no eixo; não trata vazio de continuação como 0% entre colunas.
    """
    apto_idx = axis_map.get("apto")
    if not isinstance(apto_idx, int):
        return _consolidated_display_for_column_rows(
            rows,
            col_idx,
            infer_zero_for_empty=infer_zero_for_empty,
            axis_map=axis_map,
        )
    by_apto: dict[str, list[list]] = {}
    for row in rows:
        if not isinstance(row, list):
            continue
        apto_key = str(row[apto_idx] if apto_idx < len(row) else "").strip()
        if not apto_key:
            continue
        by_apto.setdefault(apto_key, []).append(row)
    if not by_apto:
        return "0%" if infer_zero_for_empty else "-"
    unit_values: list[float] = []
    for unit_rows in by_apto.values():
        scoped = list(unit_rows)
        if len(scoped) > 1:
            scoped = _dedupe_percent_rows_drop_empty_siblings(
                scoped, axis_map, "apto", activity_col_indices
            )
        display = _consolidated_display_for_column_rows(
            scoped,
            col_idx,
            infer_zero_for_empty=False,
            axis_map=axis_map,
        )
        parsed = _parse_pct_loose(display)
        if parsed is not None:
            unit_values.append(float(parsed))
        elif str(display or "").strip() == "-":
            continue
        elif infer_zero_for_empty:
            unit_values.append(0.0)
    if not unit_values:
        return "-"
    return _fmt_pct(sum(unit_values) / len(unit_values))


def _rows_matching_axis_scope(
    percent_source_rows: list[list],
    axis_map: dict,
    scope: dict[str, str],
) -> list[list]:
    """Linhas-fonte que batem com recorte (ex.: bloco=teste e pavimento=pav1)."""
    matched = []
    for row in percent_source_rows:
        if not isinstance(row, list):
            continue
        ok = True
        for key, wanted in scope.items():
            want = str(wanted or "").strip()
            if not want:
                continue
            idx = axis_map.get(key)
            if not isinstance(idx, int):
                continue
            cur = str(row[idx] if idx < len(row) else "").strip()
            if cur != want:
                ok = False
                break
        if ok:
            matched.append(row)
    return matched


def _row_has_activity_launch(row: list, activity_col_indices: list[int]) -> bool:
    if not isinstance(row, list):
        return False
    for col_idx in activity_col_indices:
        if isinstance(col_idx, int) and col_idx < len(row) and str(row[col_idx] or "").strip():
            return True
    return False


def _dedupe_percent_rows_drop_empty_siblings(
    rows: list[list],
    axis_map: dict,
    group_axis_key: str,
    activity_col_indices: list[int],
) -> list[list]:
    """
    Mesmo apto com linha sem lançamento e linha com % → descarta a vazia antes da média.
    Várias linhas de serviço com lançamento no mesmo apto continuam todas na média.
    """
    idx = axis_map.get(group_axis_key)
    if not isinstance(idx, int) or len(rows) < 2:
        return rows
    groups: dict[str, list[list]] = {}
    for row in rows:
        if not isinstance(row, list):
            continue
        key = str(row[idx] if idx < len(row) else "").strip()
        if not key:
            continue
        groups.setdefault(key, []).append(row)
    if not groups:
        return rows
    out: list[list] = []
    for group in groups.values():
        if len(group) < 2:
            out.extend(group)
            continue
        with_launch = [r for r in group if _row_has_activity_launch(r, activity_col_indices)]
        without_launch = [r for r in group if r not in with_launch]
        if with_launch and without_launch:
            out.extend(with_launch)
        else:
            out.extend(group)
    return out if out else rows


def _column_bucket_for_row_set(
    rows: list[list],
    col_idx: int,
    *,
    axis_map: dict | None = None,
) -> list[float]:
    bucket: list[float] = []
    for row in rows:
        if not isinstance(row, list):
            continue
        raw_cell = row[col_idx] if col_idx < len(row) else ""
        if str(raw_cell or "").strip():
            _append_pct_for_average(bucket, raw_cell)
        elif len(rows) > 1 and not _rows_share_single_apto(rows, axis_map):
            bucket.append(0.0)
    return bucket


def _consolidated_pct_values_for_child_axis(
    percent_source_rows: list[list],
    axis_map: dict,
    parent_scope: dict[str, str],
    child_axis_key: str,
    col_idx: int,
    activity_col_indices: list[int],
) -> list[float]:
    """
    Um % consolidado por filho estrutural (ex.: cada pavimento do bloco).
    A camada bloco faz a média desses valores — alinhado ao que o usuário vê ao descer um nível.
    """
    child_idx = axis_map.get(child_axis_key)
    if not isinstance(child_idx, int):
        return []
    child_keys: list[str] = []
    seen: set[str] = set()
    for row in _rows_matching_axis_scope(percent_source_rows, axis_map, parent_scope):
        val = str(row[child_idx] if child_idx < len(row) else "").strip()
        if not val or val in seen:
            continue
        seen.add(val)
        child_keys.append(val)

    consolidated: list[float] = []
    for child_key in child_keys:
        scope = {**parent_scope, child_axis_key: child_key}
        child_rows = _rows_matching_axis_scope(percent_source_rows, axis_map, scope)
        if child_rows:
            child_rows = [list(r) for r in child_rows]
            _forward_fill_hierarchy_axes(child_rows, axis_map)
        if isinstance(axis_map.get("apto"), int):
            display = _consolidated_column_across_apto_units(
                child_rows,
                col_idx,
                axis_map,
                activity_col_indices,
                infer_zero_for_empty=False,
            )
        else:
            display = _consolidated_display_for_column_rows(
                child_rows, col_idx, axis_map=axis_map
            )
        pct = _parse_pct_loose(display)
        if pct is not None:
            consolidated.append(float(pct))
    return consolidated


def _extract_axis_map_from_meta(matrix_meta: dict) -> dict:
    meta = matrix_meta if isinstance(matrix_meta, dict) else {}
    cols = meta.get("axis_cols_interpreted") if isinstance(meta.get("axis_cols_interpreted"), list) else []
    headers = meta.get("axis_headers_interpreted") if isinstance(meta.get("axis_headers_interpreted"), list) else []
    pairs = []
    for idx, col in enumerate(cols):
        if not isinstance(col, int):
            continue
        label = str(headers[idx] if idx < len(headers) else "").strip()
        pairs.append((col, label))
    keys = ["setor", "bloco", "pavimento", "apto"]
    axis_map = {}
    used = set()
    for col, label in pairs:
        token = _norm_token(label)
        if ("SETOR" in token or "REGIAO" in token) and "setor" not in axis_map:
            axis_map["setor"] = col
            used.add(col)
        elif "BLOCO" in token and "bloco" not in axis_map:
            axis_map["bloco"] = col
            used.add(col)
        elif ("PAV" in token or "ANDAR" in token or "NIVEL" in token) and "pavimento" not in axis_map:
            axis_map["pavimento"] = col
            used.add(col)
        elif ("APTO" in token or "UNIDADE" in token or "LOCAL" in token or "APARTAMENT" in token) and "apto" not in axis_map:
            axis_map["apto"] = col
            used.add(col)
    return axis_map


def _header_is_axis_label(value: str) -> bool:
    token = _norm_token(value)
    if not token:
        return False
    if "SETOR" in token or "REGIAO" in token:
        return True
    if "BLOCO" in token or token == "LOCAL" or "TORRE" in token:
        return True
    if "PAV" in token or "ANDAR" in token or "NIVEL" in token:
        return True
    if "APTO" in token or "UNIDADE" in token or "APARTAMENT" in token:
        return True
    return False


def _supplement_axis_map_from_header(header: list, axis_map: dict) -> dict:
    out = dict(axis_map or {})
    for idx, raw in enumerate(header):
        label = str(raw or "").strip()
        if not label or _is_total_header_label(label):
            continue
        token = _norm_token(label)
        if ("SETOR" in token or "REGIAO" in token) and "setor" not in out:
            out["setor"] = idx
        elif ("BLOCO" in token or "LOCAL" in token or "TORRE" in token) and "bloco" not in out:
            out["bloco"] = idx
        elif ("PAV" in token or "ANDAR" in token or "NIVEL" in token) and "pavimento" not in out:
            out["pavimento"] = idx
        elif ("APTO" in token or "UNIDADE" in token or "APARTAMENT" in token) and "apto" not in out:
            out["apto"] = idx
    return out


def _resolve_activity_col_indices(header: list, matrix_meta: dict, axis_cols: list[int]) -> list[int]:
    axis_set = set(axis_cols or [])
    from_meta = matrix_meta.get("activity_cols_interpreted") if isinstance(matrix_meta.get("activity_cols_interpreted"), list) else []
    indices = [c for c in from_meta if isinstance(c, int) and 0 <= c < len(header) and c not in axis_set]
    cleaned = [i for i in indices if not _header_is_axis_label(str(header[i] or ""))]
    if cleaned:
        return cleaned
    return [
        idx
        for idx in range(len(header))
        if idx not in axis_set
        and not _is_total_header_label(header[idx])
        and not _header_is_axis_label(str(header[idx] or ""))
    ]


def _match_activity_labels(activity_labels: list[tuple[int, str]], wanted: str) -> list[tuple[int, str]]:
    needle = str(wanted or "").strip()
    if not needle:
        return activity_labels
    needle_norm = _norm_token(needle)
    exact = [
        (idx, lbl)
        for idx, lbl in activity_labels
        if _norm_token(lbl) == needle_norm or str(lbl).strip().lower() == needle.lower()
    ]
    if exact:
        return exact
    partial = [(idx, lbl) for idx, lbl in activity_labels if needle.lower() in str(lbl).strip().lower()]
    return partial if partial else activity_labels


def _normalize_column_groups(raw_groups, available_labels: list[str]) -> list[dict]:
    if not isinstance(raw_groups, list):
        return []
    allowed = {str(lbl or "").strip() for lbl in available_labels if str(lbl or "").strip()}
    out = []
    seen_ids = set()
    for idx, item in enumerate(raw_groups):
        if not isinstance(item, dict):
            continue
        gid = str(item.get("id") or "").strip() or f"group_{idx + 1}"
        if gid in seen_ids:
            gid = f"{gid}_{idx + 1}"
        seen_ids.add(gid)
        name = str(item.get("name") or "").strip()
        if not name:
            continue
        cols = []
        seen_cols = set()
        for col in item.get("columns") if isinstance(item.get("columns"), list) else []:
            lbl = str(col or "").strip()
            if not lbl or lbl not in allowed or lbl in seen_cols:
                continue
            seen_cols.add(lbl)
            cols.append(lbl)
        out.append({"id": gid, "name": name[:120], "columns": cols})
    return out


def _extract_layout_column_groups(layout: dict, available_labels: list[str]) -> list[dict]:
    if not isinstance(layout, dict):
        return []
    sections = layout.get("sections")
    if not isinstance(sections, list):
        return []
    for section in sections:
        if not isinstance(section, dict):
            continue
        if str(section.get("kind") or "").strip() not in {"matrix_table", "table"}:
            continue
        data = section.get("data") if isinstance(section.get("data"), dict) else {}
        direct_groups = data.get("columnGroups")
        if isinstance(direct_groups, list):
            return _normalize_column_groups(direct_groups, available_labels)
        import_meta = data.get("importMeta") if isinstance(data.get("importMeta"), dict) else {}
        return _normalize_column_groups(import_meta.get("column_groups"), available_labels)
    return []


def _resolve_ambiente_matrix_mode(
    requested: str,
    selected: dict,
    *,
    is_area_comum: bool,
    has_apto_axis: bool = True,
) -> str:
    """Mantém a mesma semântica de camada do legado para o modo dedicado."""
    r = str(requested or "").strip().lower()
    if r not in {"bloco", "pavimento", "apto"}:
        r = ""

    setor = str(selected.get("setor") or "").strip()
    bloco = str(selected.get("bloco") or "").strip()
    pavimento = str(selected.get("pavimento") or "").strip()

    if is_area_comum:
        if r == "apto":
            r = "pavimento"
        if bloco:
            return "pavimento"
        if r == "pavimento" and not bloco:
            return "bloco"
        if r in {"pavimento", "bloco"}:
            return r
        return "bloco"

    # O recorte ativo manda na camada efetiva no modo dedicado.
    if bloco and pavimento:
        return "apto" if has_apto_axis else "pavimento"
    if bloco:
        return "pavimento"
    if r in {"apto", "pavimento", "bloco"}:
        return "bloco"
    if setor:
        return "bloco"
    return "bloco"


class AmbienteProvider:
    """
    Provider do ViewModel dedicado por ambiente.
    Fonte de dados: layout/versionamento do ambiente operacional (não usa ItemMapaServico por obra).
    """

    def __init__(self, *, extract_first_matrix_rows_from_layout, build_matrix_payload_from_rows):
        self._extract_first_matrix_rows_from_layout = extract_first_matrix_rows_from_layout
        self._build_matrix_payload_from_rows = build_matrix_payload_from_rows

    def build(self, *, obra, selected: dict, ambiente_id: int):
        from painel_operacional.models import AmbienteOperacional, AmbienteTipo, VersaoEstado

        ambiente = (
            AmbienteOperacional.objects.filter(
                id=ambiente_id,
                ativo=True,
                tipo=AmbienteTipo.MAPA_CONTROLE,
                obra_id=getattr(obra, "id", None),
            )
            .only("id", "nome", "obra_id")
            .first()
        )
        if not ambiente:
            return None

        versao = ambiente.versoes.filter(estado=VersaoEstado.DRAFT).order_by("-numero").first()
        if not versao:
            versao = ambiente.versoes.filter(estado=VersaoEstado.PUBLISHED).order_by("-numero").first()
        extracted = self._extract_first_matrix_rows_from_layout(versao.layout if versao else {})
        if isinstance(extracted, tuple) and len(extracted) == 2:
            rows_layout, matrix_meta = extracted
        else:
            rows_layout, matrix_meta = extracted, {}
        matrix_meta = matrix_meta if isinstance(matrix_meta, dict) else {}
        if not rows_layout or not isinstance(rows_layout[0], list):
            rows_layout = []

        header = rows_layout[0] if rows_layout else []
        body_rows = [
            list(r) if isinstance(r, list) else [str(r or "")]
            for r in (rows_layout[1:] if len(rows_layout) > 1 else [])
        ]
        # Snapshot sem forward-fill para validar associação explícita de unidade (apto).
        body_rows_raw = [list(r) for r in body_rows]
        axis_map = _supplement_axis_map_from_header(header, _extract_axis_map_from_meta(matrix_meta))
        _forward_fill_hierarchy_axes(body_rows, axis_map)
        axis_cols = sorted({idx for idx in axis_map.values() if isinstance(idx, int)})

        activity_cols = _resolve_activity_col_indices(header, matrix_meta, axis_cols)

        is_manual_flat = len(axis_cols) <= 1
        has_apto_axis = isinstance(axis_map.get("apto"), int)
        pavimento_is_leaf = isinstance(axis_map.get("pavimento"), int) and not has_apto_axis
        strategy = str(matrix_meta.get("strategy") or "").strip().lower()
        treat_empty_as_zero = strategy == "manual_template"
        is_area_comum = _setor_e_area_comum(str(selected.get("setor") or ""))
        filter_selected = dict(selected)
        ativ_nav = str(filter_selected.get("atividade") or "").strip()
        coluna_filtrada_aviso = None

        quick_find = str(filter_selected.get("quick_find") or "").strip()
        if quick_find and not str(selected.get("apto") or "").strip():
            q = quick_find.lower()
            for row in body_rows:
                if not isinstance(row, list):
                    continue
                row_text = " ".join(str(v or "") for v in row).lower()
                if q not in row_text:
                    continue
                for key in ("setor", "bloco", "pavimento", "apto"):
                    idx = axis_map.get(key)
                    if isinstance(idx, int) and idx < len(row):
                        selected[key] = str(row[idx] or "").strip()
                break

        def _row_matches_axes(row_vals: list, sel: dict | None = None) -> bool:
            scope = sel if isinstance(sel, dict) else filter_selected
            for key in ("setor", "bloco", "pavimento", "apto"):
                wanted = str(scope.get(key) or "").strip()
                if not wanted:
                    continue
                idx = axis_map.get(key)
                if not isinstance(idx, int):
                    continue
                current = str(row_vals[idx] if idx < len(row_vals) else "").strip()
                if current != wanted:
                    return False
            return True

        search_filter_raw = str(filter_selected.get("search") or "").strip()
        search_filter = search_filter_raw.lower()
        status_filter = str(filter_selected.get("status") or "").strip()
        search_matches_any_activity = False
        if search_filter:
            for col_idx in activity_cols:
                header_lbl = str(header[col_idx] if col_idx < len(header) else "").strip().lower()
                if header_lbl and search_filter in header_lbl:
                    search_matches_any_activity = True
                    break
        filtered_body = []
        filtered_body_raw = []
        for idx, row in enumerate(body_rows):
            if not isinstance(row, list):
                continue
            if not _row_matches_axes(row):
                continue
            if search_filter:
                row_blob = " ".join(str(v or "") for v in row).lower()
                if search_filter not in row_blob and not search_matches_any_activity:
                    continue
            filtered_body.append(row)
            filtered_body_raw.append(body_rows_raw[idx] if idx < len(body_rows_raw) else list(row))

        layers = {"setores": [], "blocos": [], "pavimentos": [], "aptos": []}

        activity_labels = []
        for idx in activity_cols:
            if idx >= len(header):
                continue
            lbl = str(header[idx] or "").strip()
            if not lbl:
                continue
            activity_labels.append((idx, lbl))

        if not activity_labels:
            for idx in activity_cols:
                if idx < len(header):
                    lbl = str(header[idx] or "").strip() or f"Atividade {idx + 1}"
                    activity_labels.append((idx, lbl))

        all_activity_labels = [lbl for _idx, lbl in activity_labels]
        column_groups = _extract_layout_column_groups(versao.layout if versao else {}, all_activity_labels)
        selected_group_id = str(filter_selected.get("column_group") or "").strip()
        selected_group = next((g for g in column_groups if g.get("id") == selected_group_id), None)
        if selected_group and selected_group.get("columns"):
            wanted = {str(lbl or "").strip() for lbl in selected_group["columns"]}
            activity_labels = [(idx, lbl) for idx, lbl in activity_labels if str(lbl or "").strip() in wanted]

        if ativ_nav:
            narrowed = _match_activity_labels(activity_labels, ativ_nav)
            if narrowed:
                activity_labels = narrowed
                coluna_filtrada_aviso = ativ_nav
        elif search_filter:
            # Pesquisa universal: também considera nomes de colunas/atividades.
            narrowed_by_search = [
                (idx, lbl) for idx, lbl in activity_labels if search_filter in str(lbl or "").strip().lower()
            ]
            if narrowed_by_search:
                activity_labels = narrowed_by_search
                coluna_filtrada_aviso = search_filter_raw

        def _layer_rows_with_stats(axis_key: str, prefilter: dict | None = None):
            idx = axis_map.get(axis_key)
            if not isinstance(idx, int):
                return []
            pf = _clean_layer_prefilter(prefilter)
            # Com recorte na URL, mesma base da matriz; na raiz, todo o layout.
            list_src = filtered_body if pf else body_rows
            values = _distinct_structural_axis_values(list_src, axis_map, axis_key, pf)
            row_order_pref = matrix_meta.get(f"row_order_{axis_key}")
            values = _apply_preferred_axis_order(values, row_order_pref)
            rows = []
            for v in values:
                rows_match = []
                for row in body_rows:
                    if not isinstance(row, list):
                        continue
                    if not _row_matches_layer_prefilter(row, axis_map, pf):
                        continue
                    cur_axis = str(row[idx] if idx < len(row) else "").strip()
                    if cur_axis == str(v or "").strip():
                        rows_match.append(row)

                values_pct = []
                for row in rows_match:
                    if not _is_percent_source_row(
                        row, axis_map, is_area_comum=is_area_comum, is_manual_flat=is_manual_flat
                    ):
                        continue
                    for col_idx, _lbl in activity_labels:
                        raw_cell = row[col_idx] if col_idx < len(row) else ""
                        _append_pct_for_context_average(
                            values_pct,
                            raw_cell,
                            treat_empty_as_zero=treat_empty_as_zero,
                        )

                total = len(
                    [
                        r
                        for r in rows_match
                        if _is_percent_source_row(
                            r, axis_map, is_area_comum=is_area_comum, is_manual_flat=is_manual_flat
                        )
                    ]
                )
                progresso = round(sum(values_pct) / len(values_pct), 2) if values_pct else 0.0
                concluidos = sum(1 for p in values_pct if p >= 0.995)
                em_andamento = sum(1 for p in values_pct if 0 < p < 0.995)
                nao_iniciados = sum(1 for p in values_pct if p <= 0)
                rows.append(
                    {
                        axis_key: v,
                        "total": total,
                        "progresso": progresso,
                        "concluidos": concluidos,
                        "em_andamento": em_andamento,
                        "nao_iniciados": nao_iniciados,
                    }
                )
            return rows

        layers = {
            "setores": _layer_rows_with_stats("setor"),
            "blocos": _layer_rows_with_stats(
                "bloco",
                {"setor": selected.get("setor")} if str(selected.get("setor") or "").strip() else None,
            ),
            "pavimentos": _layer_rows_with_stats(
                "pavimento",
                {
                    "setor": selected.get("setor"),
                    "bloco": selected.get("bloco"),
                }
                if str(selected.get("bloco") or "").strip()
                else None,
            ),
            "aptos": _layer_rows_with_stats(
                "apto",
                {
                    "setor": selected.get("setor"),
                    "bloco": selected.get("bloco"),
                    "pavimento": selected.get("pavimento"),
                }
                if str(selected.get("pavimento") or "").strip()
                else None,
            ),
        }

        # No dedicado por ambiente, a grade acompanha a profundidade do recorte:
        # bloco selecionado -> grade por pavimento; pavimento selecionado -> grade por apto.
        row_mode_requested = _resolve_ambiente_matrix_mode(
            str(filter_selected.get("matrix_mode") or "").strip(),
            filter_selected,
            is_area_comum=is_area_comum,
            has_apto_axis=has_apto_axis,
        )
        if is_manual_flat:
            row_mode_requested = "bloco"
        # Filtro por coluna: na raiz (sem bloco/pavimento) lista todos os blocos × só essa atividade.
        if (
            ativ_nav
            and not str(filter_selected.get("apto") or "").strip()
            and not str(filter_selected.get("pavimento") or "").strip()
            and not str(filter_selected.get("bloco") or "").strip()
        ):
            row_mode_requested = "bloco"
        if not is_manual_flat:
            if row_mode_requested == "apto" and not str(filter_selected.get("pavimento") or "").strip():
                row_mode_requested = "pavimento" if str(filter_selected.get("bloco") or "").strip() else "bloco"
            if row_mode_requested == "pavimento" and not str(filter_selected.get("bloco") or "").strip():
                row_mode_requested = "bloco"

        row_axis_key = "bloco" if row_mode_requested == "bloco" else ("pavimento" if row_mode_requested == "pavimento" else "apto")
        row_axis_col = axis_map.get(row_axis_key)
        if not isinstance(row_axis_col, int):
            row_axis_col = axis_cols[0] if axis_cols else 0
        if ativ_nav and row_mode_requested == "bloco":
            bloco_col = axis_map.get("bloco")
            if isinstance(bloco_col, int):
                row_axis_col = bloco_col

        effective_rows = [header]

        processed_rows = []
        for row in filtered_body:
            out = list(row)
            has_matching_status = False
            for col_idx, _label in activity_labels:
                if col_idx >= len(out):
                    continue
                val = out[col_idx]
                # status filter aplicado sem excluir estrutura do recorte.
                if status_filter:
                    parsed = _parse_pct_loose(val)
                    if _matches_status_filter(parsed, status_filter):
                        has_matching_status = True
                    else:
                        out[col_idx] = ""
                else:
                    if _parse_pct_loose(val) is not None:
                        has_matching_status = True
            if status_filter and not has_matching_status:
                continue
            processed_rows.append(out)

        if row_mode_requested == "apto" and isinstance(row_axis_col, int):
            act_indices = [idx for idx, _ in activity_labels]
            explicit_unit_keys: set[str] = set()
            apto_idx = axis_map.get("apto")
            if isinstance(apto_idx, int):
                for raw_row in filtered_body_raw:
                    if not isinstance(raw_row, list):
                        continue
                    unit = str(raw_row[apto_idx] if apto_idx < len(raw_row) else "").strip()
                    if unit:
                        explicit_unit_keys.add(unit)
            visible = [
                row
                for row in processed_rows
                if _matrix_row_is_visible_unit(row, row_axis_col, act_indices)
            ]
            if explicit_unit_keys:
                visible = [
                    row
                    for row in visible
                    if str(row[row_axis_col] if row_axis_col < len(row) else "").strip() in explicit_unit_keys
                ]
            else:
                visible = []
            processed_rows = visible

        # Base numérica: só linhas com lançamento real (UND/APTO), nunca % consolidado em linha estrutural.
        percent_source_rows = [
            row
            for row in processed_rows
            if _is_percent_source_row(
                row, axis_map, is_area_comum=is_area_comum, is_manual_flat=is_manual_flat
            )
        ]

        apto_filter = str(filter_selected.get("apto") or "").strip()
        pavimento_filter = str(filter_selected.get("pavimento") or "").strip()
        # Recorte por unidade (chip): detalhe da UND — uma linha consolidada, mesma regra do pavimento.
        if (
            apto_filter
            and not is_manual_flat
            and row_mode_requested == "apto"
            and isinstance(row_axis_col, int)
        ):
            act_col_indices = [idx for idx, _ in activity_labels]
            unit_rows = _percent_rows_for_axis_key(percent_source_rows, row_axis_col, apto_filter)
            if isinstance(axis_map.get("apto"), int):
                unit_rows = _dedupe_percent_rows_drop_empty_siblings(
                    unit_rows, axis_map, "apto", act_col_indices
                )
            out = [""] * len(header)
            out[row_axis_col] = apto_filter
            for col_idx, _label in activity_labels:
                out[col_idx] = _consolidated_display_for_column_rows(
                    unit_rows, col_idx, axis_map=axis_map
                )
            processed_rows = [out]
        elif (
            pavimento_filter
            and pavimento_is_leaf
            and not is_manual_flat
            and row_mode_requested == "pavimento"
            and isinstance(row_axis_col, int)
            and not apto_filter
        ):
            # Import BLOCO + PAVIMENTO (sem UND): chip/linha abre detalhe do pavimento, não camada apto vazia.
            pav_rows = _percent_rows_for_axis_key(percent_source_rows, row_axis_col, pavimento_filter)
            out = [""] * len(header)
            out[row_axis_col] = pavimento_filter
            bloco_idx = axis_map.get("bloco")
            if isinstance(bloco_idx, int):
                out[bloco_idx] = str(filter_selected.get("bloco") or "").strip()
            for col_idx, _label in activity_labels:
                out[col_idx] = _consolidated_display_for_column_rows(
                    pav_rows, col_idx, axis_map=axis_map
                )
            processed_rows = [out]

        # Totais/KPIs: média simples de todas as células de atividade das unidades no recorte (Opção A).
        activity_value_buckets = {label: [] for _idx, label in activity_labels}
        for row in percent_source_rows:
            for col_idx, label in activity_labels:
                raw_cell = row[col_idx] if col_idx < len(row) else ""
                _append_pct_for_context_average(
                    activity_value_buckets[label],
                    raw_cell,
                    treat_empty_as_zero=treat_empty_as_zero,
                )

        if (
            not is_manual_flat
            and row_mode_requested in {"bloco", "pavimento", "apto"}
            and isinstance(row_axis_col, int)
            and not (row_mode_requested == "apto" and apto_filter)
            and not (row_mode_requested == "pavimento" and pavimento_filter and pavimento_is_leaf)
        ):
            # Exibição: eixos estruturais (bloco/pavimento/UND); várias linhas-fonte → uma linha por chave.
            row_order_pref = matrix_meta.get(f"row_order_{row_axis_key}")
            matrix_prefilter = _matrix_display_prefilter(filter_selected, row_axis_key)
            axis_keys = _merge_matrix_axis_keys(
                body_rows=body_rows,
                processed_rows=processed_rows,
                axis_map=axis_map,
                row_axis_key=row_axis_key,
                row_axis_col=row_axis_col,
                prefilter=matrix_prefilter or None,
                row_order_pref=row_order_pref if isinstance(row_order_pref, list) else None,
            )
            use_bloco_via_pavimentos = (
                row_mode_requested == "bloco"
                and isinstance(axis_map.get("pavimento"), int)
            )

            aggregated_rows = []
            act_col_indices = [idx for idx, _ in activity_labels]
            apto_idx = axis_map.get("apto")
            for key in axis_keys:
                key_rows = _percent_rows_for_axis_key(percent_source_rows, row_axis_col, key)
                structural_only = (
                    not any(
                        str(row[apto_idx] if apto_idx < len(row) else "").strip()
                        for row in key_rows
                    )
                    if isinstance(apto_idx, int)
                    else not key_rows
                )
                if key_rows:
                    key_rows = [list(r) for r in key_rows]
                    _forward_fill_hierarchy_axes(key_rows, axis_map)
                out = [""] * len(header)
                out[row_axis_col] = key
                for col_idx, _label in activity_labels:
                    if use_bloco_via_pavimentos:
                        values = _consolidated_pct_values_for_child_axis(
                            percent_source_rows,
                            axis_map,
                            {row_axis_key: key},
                            "pavimento",
                            col_idx,
                            act_col_indices,
                        )
                        if not values and key_rows:
                            out[col_idx] = _consolidated_display_for_column_rows(
                                key_rows,
                                col_idx,
                                infer_zero_for_empty=structural_only,
                                axis_map=axis_map,
                            )
                        else:
                            out[col_idx] = _consolidated_activity_cell_display(
                                values,
                                has_percent_units=bool(key_rows),
                            )
                    elif isinstance(axis_map.get("apto"), int):
                        out[col_idx] = _consolidated_column_across_apto_units(
                            key_rows,
                            col_idx,
                            axis_map,
                            act_col_indices,
                            infer_zero_for_empty=structural_only,
                        )
                    else:
                        out[col_idx] = _consolidated_display_for_column_rows(
                            key_rows,
                            col_idx,
                            infer_zero_for_empty=structural_only,
                            axis_map=axis_map,
                        )
                aggregated_rows.append(out)
            processed_rows = aggregated_rows

        effective_rows.extend(processed_rows)

        if len(effective_rows) <= 1:
            effective_rows = [header]

        row_meta = dict(matrix_meta)
        row_meta["activity_cols_interpreted"] = [idx for idx, _ in activity_labels]
        row_meta["activity_headers_interpreted"] = [lbl for _, lbl in activity_labels]
        row_meta["row_axis_cols_interpreted"] = [row_axis_col]
        matrix, kpis = self._build_matrix_payload_from_rows(effective_rows, row_meta)
        matrix["mode"] = row_mode_requested
        matrix["unit_detail_view"] = bool(
            (apto_filter and row_mode_requested == "apto")
            or (pavimento_filter and pavimento_is_leaf and row_mode_requested == "pavimento")
        )
        matrix["pavimento_leaf_drill"] = bool(
            pavimento_is_leaf and row_mode_requested == "pavimento" and not pavimento_filter
        )
        matrix["allow_row_drill"] = (
            (row_mode_requested == "bloco" and isinstance(axis_map.get("pavimento"), int))
            or (row_mode_requested == "pavimento" and isinstance(axis_map.get("apto"), int))
            or matrix["pavimento_leaf_drill"]
            or (
                row_mode_requested == "apto"
                and not apto_filter
                and isinstance(axis_map.get("apto"), int)
            )
        )
        matrix["drill_axis_key"] = (
            "pavimento"
            if row_mode_requested == "bloco"
            else ("apto" if row_mode_requested == "pavimento" and has_apto_axis else "")
        )
        matrix["header_first_col"] = {
            "bloco": "Bloco",
            "pavimento": "Pavimento",
            "apto": "Apto / und.",
        }.get(row_mode_requested, matrix.get("header_first_col"))

        # Rodapé/KPIs:
        # - manual_template: base na grade exibida (camada atual);
        # - pavimento (pivot etc.): média das linhas visíveis — igual ao que o bloco mostra por filho;
        # - bloco (demais estratégias): base-fonte para evitar média de médias em pivots.
        use_display_footer = (
            strategy == "manual_template" and row_mode_requested in {"bloco", "pavimento", "apto"}
        ) or (strategy != "manual_template" and row_mode_requested == "pavimento")
        if use_display_footer:
            totais_reais, all_values = _footer_totals_from_matrix_display(
                matrix.get("rows") or [], activity_labels
            )
        else:
            totais_reais = []
            all_values = []
            for _idx, label in activity_labels:
                vals = activity_value_buckets.get(label) or []
                if not vals:
                    totais_reais.append({"atividade": label, "pct": None})
                    continue
                pct = round(float(_avg_pct_total(vals) or 0.0), 1)
                totais_reais.append({"atividade": label, "pct": pct})
                all_values.extend(vals)
        matrix["totais"] = totais_reais
        matrix["total_geral"] = _avg_pct_total(all_values) if all_values else None

        totals_by_activity = {
            str(item.get("atividade") or ""): item.get("pct")
            for item in totais_reais
            if isinstance(item, dict)
        }
        rows_matrix = matrix.get("rows") or []
        for row in rows_matrix:
            for cell in row.get("cells") or []:
                raw_txt = str(cell.get("raw") or "").strip()
                atividade = str(cell.get("atividade") or "")
                explicit_zero = bool(raw_txt) and _parse_pct_loose(raw_txt) == 0
                if (
                    cell.get("pct") == 0
                    and not explicit_zero
                    and (not raw_txt or totals_by_activity.get(atividade) is None)
                ):
                    cell["pct"] = None
        for row in rows_matrix:
            group_key = str(row.get("row_key") or row.get("row_label") or "").strip()
            total_display = _row_total_from_display_cells(row)
            if (
                not is_manual_flat
                and row_mode_requested in {"bloco", "pavimento", "apto"}
                and isinstance(row_axis_col, int)
                and group_key
            ):
                if total_display is not None:
                    row["total"] = total_display
                elif not _percent_rows_for_axis_key(percent_source_rows, row_axis_col, group_key):
                    row["total"] = 0
                else:
                    row["total"] = None
            elif total_display is not None:
                row["total"] = total_display
            else:
                row["total"] = None

        if all_values:
            media_fmt = round(sum(all_values) / len(all_values), 2)
        else:
            media_fmt = 0.0
        kpis = {
            "total_itens": len(all_values),
            "percentual_medio": media_fmt,
            "concluidos": sum(1 for v in all_values if v >= 99.5),
            "em_andamento": sum(1 for v in all_values if 0 < v < 99.5),
            "nao_iniciados": sum(1 for v in all_values if v <= 0),
        }

        itens_atividade = []
        if str(selected.get("apto") or "").strip() or str(selected.get("pavimento") or "").strip():
            scoped_rows = []
            for row in filtered_body:
                if not isinstance(row, list):
                    continue
                ok = True
                for axis_key in ("setor", "bloco", "pavimento", "apto"):
                    sel_val = str(selected.get(axis_key) or "").strip()
                    if not sel_val:
                        continue
                    axis_idx = axis_map.get(axis_key)
                    cur = str(row[axis_idx] if isinstance(axis_idx, int) and axis_idx < len(row) else "").strip()
                    if cur != sel_val:
                        ok = False
                        break
                if ok:
                    scoped_rows.append(row)
            if scoped_rows:
                source_row = scoped_rows[0]
                for col_idx, lbl in activity_labels:
                    if col_idx >= len(source_row):
                        continue
                    raw = source_row[col_idx]
                    txt = str(raw or "").strip()
                    if not txt:
                        continue
                    pct = _parse_pct_loose(raw)
                    itens_atividade.append(
                        {
                            "atividade": lbl,
                            "status_texto": "",
                            "pct_display": round(float(pct), 2) if pct is not None else None,
                            "data_termino": None,
                        }
                    )

        matrix_context = {
            "obra_titulo": f"{obra.codigo_sienge} — {obra.nome}",
            "caminho": str(ambiente.nome or "").strip() or "Ambiente",
            "status_filtro": "",
            "modo_grade_label": "Bloco × atividade",
            "n_grade_linhas": len(matrix.get("rows") or []),
            "n_grade_cols": len(matrix.get("atividades") or []),
            "cnt_setores": len(layers["setores"]),
            "cnt_blocos_camada": len(layers["blocos"]),
            "cnt_pavs_camada": len(layers["pavimentos"]),
            "cnt_unids_camada": len(layers["aptos"]),
        }
        stable_params = {
            "matrix_mode": row_mode_requested,
            "ambiente_id": ambiente.id,
        }
        for stable_key in ("search", "atividade", "column_group"):
            stable_val = str(selected.get(stable_key) or "").strip()
            if stable_val:
                stable_params[stable_key] = stable_val
        matrix_stable_qs = urlencode(stable_params)
        matrix_stable_qs_apto = urlencode({**stable_params, "matrix_mode": "apto"})
        base_qs = {
            "obra": obra.id,
            "ambiente_id": ambiente.id,
            "search": selected["search"],
            "atividade": selected["atividade"],
            "column_group": selected.get("column_group") or "",
            "matrix_mode": row_mode_requested,
        }
        root_qs = urlencode({k: v for k, v in base_qs.items() if str(v or "").strip()})

        breadcrumbs = []
        if str(selected.get("setor") or "").strip():
            breadcrumbs.append(
                {
                    "label": str(selected["setor"]),
                    "url": f"?{urlencode({'obra': obra.id, 'ambiente_id': ambiente.id, 'setor': selected['setor'], 'matrix_mode': row_mode_requested, 'search': selected.get('search',''), 'atividade': selected.get('atividade',''), 'column_group': selected.get('column_group','')})}",
                }
            )
        if str(selected.get("bloco") or "").strip():
            breadcrumbs.append(
                {
                    "label": str(selected["bloco"]),
                    "url": f"?{urlencode({'obra': obra.id, 'ambiente_id': ambiente.id, 'setor': selected.get('setor',''), 'bloco': selected['bloco'], 'matrix_mode': row_mode_requested, 'search': selected.get('search',''), 'atividade': selected.get('atividade',''), 'column_group': selected.get('column_group','')})}",
                }
            )
        if str(selected.get("pavimento") or "").strip():
            breadcrumbs.append(
                {
                    "label": str(selected["pavimento"]),
                    "url": f"?{urlencode({'obra': obra.id, 'ambiente_id': ambiente.id, 'setor': selected.get('setor',''), 'bloco': selected.get('bloco',''), 'pavimento': selected['pavimento'], 'matrix_mode': row_mode_requested, 'search': selected.get('search',''), 'atividade': selected.get('atividade',''), 'column_group': selected.get('column_group','')})}",
                }
            )
        if str(selected.get("apto") or "").strip():
            breadcrumbs.append(
                {
                    "label": str(selected["apto"]),
                    "url": f"?{urlencode({'obra': obra.id, 'ambiente_id': ambiente.id, 'setor': selected.get('setor',''), 'bloco': selected.get('bloco',''), 'pavimento': selected.get('pavimento',''), 'apto': selected['apto'], 'matrix_mode': row_mode_requested, 'search': selected.get('search',''), 'atividade': selected.get('atividade',''), 'column_group': selected.get('column_group','')})}",
                }
            )
        prev_url = f"?{root_qs}" if root_qs else "?"
        if len(breadcrumbs) >= 2:
            prev_url = breadcrumbs[-2]["url"]
        elif len(breadcrumbs) == 1:
            prev_url = f"?{urlencode({'obra': obra.id, 'ambiente_id': ambiente.id})}"
        layer_nav = {
            "has_scope": bool(breadcrumbs),
            "depth": len(breadcrumbs),
            "root_url": f"?{root_qs}" if root_qs else "?",
            "prev_url": prev_url,
            "current_path": f"Ambiente: {ambiente.nome}",
            "breadcrumbs": breadcrumbs,
        }
        cell_colors_raw = matrix_meta.get("cellColors")
        cell_colors = cell_colors_raw if isinstance(cell_colors_raw, dict) else {}
        if cell_colors:
            _apply_matrix_cell_colors(
                matrix,
                cell_colors,
                bloco=str(selected.get("bloco") or "").strip(),
                pavimento=str(selected.get("pavimento") or "").strip(),
            )
        return {
            "selected": selected,
            "layers": layers,
            "itens_atividade": itens_atividade,
            "matrix": matrix,
            "kpis": kpis,
            "qualidade": {
                "sem_bloco": 0,
                "sem_pavimento": 0,
                "sem_apto": 0,
                "sem_status_percentual": 0,
                "sem_data_termino": 0,
            },
            "confiabilidade": {"score": 0.0, "nivel": "sem_dados", "nivel_display": "Sem dados"},
            "quick_match": None,
            "importacao_info": None,
            "focus_detail": None,
            "matrix_context": matrix_context,
            "coluna_filtrada_aviso": coluna_filtrada_aviso,
            "macro_pulse": None,
            "matrix_stable_qs": matrix_stable_qs,
            "matrix_stable_qs_apto": matrix_stable_qs_apto,
            "is_area_comum": is_area_comum,
            "layer_nav": layer_nav,
            "column_groups": column_groups,
            "matrix_all_atividades": all_activity_labels,
            "column_group_selected": selected_group_id,
            "matrix_cell_colors": cell_colors,
        }


class LegacyObraProvider:
    """
    Provider do ViewModel legado por obra.
    Mantém a semântica atual do mapa legado (ItemMapaServico por obra) sem alterar visual.
    """

    def __init__(
        self,
        *,
        status_to_ratio,
        setor_e_area_comum,
        build_layers_navigation,
        resolve_matrix_mode,
        row_field_for_matrix_mode,
        build_matrix_grid,
        status_bucket_from_ratio,
        norm_key,
        mean_ratio_equal_weight_groups,
        mean_ratio_equal_weight_blocos_then_pavimento,
        build_confiabilidade_controle,
        macro_pulse,
    ):
        self._status_to_ratio = status_to_ratio
        self._setor_e_area_comum = setor_e_area_comum
        self._build_layers_navigation = build_layers_navigation
        self._resolve_matrix_mode = resolve_matrix_mode
        self._row_field_for_matrix_mode = row_field_for_matrix_mode
        self._build_matrix_grid = build_matrix_grid
        self._status_bucket_from_ratio = status_bucket_from_ratio
        self._norm_key = norm_key
        self._mean_ratio_equal_weight_groups = mean_ratio_equal_weight_groups
        self._mean_ratio_equal_weight_blocos_then_pavimento = mean_ratio_equal_weight_blocos_then_pavimento
        self._build_confiabilidade_controle = build_confiabilidade_controle
        self._macro_pulse = macro_pulse

    def build(self, *, request, obra, selected: dict, grid_pct_clicado):
        is_area_comum = False
        status_filter = selected["status"]
        layers = {"setores": [], "blocos": [], "pavimentos": [], "aptos": []}
        itens_atividade = []
        matrix = {"atividades": [], "rows": [], "totais": [], "mode": "bloco", "header_first_col": "Bloco"}
        kpis = {"total_itens": 0, "percentual_medio": 0.0, "concluidos": 0, "em_andamento": 0, "nao_iniciados": 0}
        qualidade = {
            "sem_bloco": 0,
            "sem_pavimento": 0,
            "sem_apto": 0,
            "sem_status_percentual": 0,
            "sem_data_termino": 0,
        }
        confiabilidade = {"score": 0.0, "nivel": "sem_dados", "nivel_display": "Sem dados"}
        quick_match = None
        importacao_info = None
        focus_detail = None
        matrix_context = None
        layer_nav = {
            "has_scope": False,
            "depth": 0,
            "root_url": "",
            "prev_url": "",
            "current_path": "Mapa geral",
            "breadcrumbs": [],
        }

        if obra:
            raw_qs = ItemMapaServico.objects.filter(obra=obra)
            base_qs = raw_qs
            latest_import = ImportacaoMapaServico.objects.filter(obra=obra).only(
                "created_at", "nome_arquivo", "total_linhas_lidas", "total_linhas_importadas", "aba_origem"
            ).first()
            if latest_import:
                importacao_info = {
                    "created_at": latest_import.created_at,
                    "nome_arquivo": latest_import.nome_arquivo,
                    "total_linhas_lidas": latest_import.total_linhas_lidas,
                    "total_linhas_importadas": latest_import.total_linhas_importadas,
                    "aba_origem": latest_import.aba_origem,
                }

            quick_find = selected["quick_find"]
            if quick_find and not selected["apto"]:
                quick_qs = base_qs.filter(
                    Q(setor__icontains=quick_find)
                    | Q(bloco__icontains=quick_find)
                    | Q(pavimento__icontains=quick_find)
                    | Q(apto__icontains=quick_find)
                    | Q(atividade__icontains=quick_find)
                    | Q(grupo_servicos__icontains=quick_find)
                )
                candidate = quick_qs.order_by("setor", "bloco", "pavimento", "apto", "atividade").first()
                if candidate:
                    selected["setor"] = candidate.setor or selected["setor"]
                    selected["bloco"] = candidate.bloco or selected["bloco"]
                    selected["pavimento"] = candidate.pavimento or selected["pavimento"]
                    selected["apto"] = candidate.apto or selected["apto"]
                    quick_match = {
                        "query": quick_find,
                        "setor": candidate.setor,
                        "bloco": candidate.bloco,
                        "pavimento": candidate.pavimento,
                        "apto": candidate.apto,
                        "atividade": candidate.atividade,
                    }

            is_area_comum = self._setor_e_area_comum(selected.get("setor") or "")
            if is_area_comum:
                selected["apto"] = ""

            if selected["search"]:
                s = selected["search"]
                base_qs = base_qs.filter(
                    Q(atividade__icontains=s)
                    | Q(grupo_servicos__icontains=s)
                    | Q(setor__icontains=s)
                    | Q(bloco__icontains=s)
                    | Q(pavimento__icontains=s)
                    | Q(apto__icontains=s)
                    | Q(status_texto__icontains=s)
                    | Q(observacao__icontains=s)
                )
            if selected["atividade"]:
                base_qs = base_qs.filter(atividade__icontains=selected["atividade"])

            if status_filter == "concluido":
                base_qs = base_qs.filter(Q(status_percentual__gte=1) | Q(status_texto__icontains="conclu"))
            elif status_filter == "em_andamento":
                base_qs = base_qs.filter(
                    Q(status_percentual__gt=0, status_percentual__lt=1)
                    | Q(status_texto__icontains="exec")
                    | Q(status_texto__icontains="parcial")
                )
            elif status_filter == "nao_iniciado":
                base_qs = base_qs.filter(
                    Q(status_percentual__lte=0)
                    | Q(status_texto__icontains="nao")
                    | Q(status_texto__icontains="não")
                    | Q(status_texto__icontains="pend")
                )

            active_scope_qs = base_qs
            if selected["setor"]:
                active_scope_qs = active_scope_qs.filter(setor=selected["setor"])
            if selected["bloco"]:
                active_scope_qs = active_scope_qs.filter(bloco=selected["bloco"])
            if selected["pavimento"]:
                active_scope_qs = active_scope_qs.filter(pavimento=selected["pavimento"])
            if selected["apto"]:
                active_scope_qs = active_scope_qs.filter(apto=selected["apto"])

            layers = self._build_layers_navigation(raw_qs, selected)

            matrix_scope = active_scope_qs
            matrix_mode = self._resolve_matrix_mode(request.GET.get("matrix_mode") or "", selected)
            row_field = self._row_field_for_matrix_mode(matrix_mode)
            rows_max = 80 if matrix_mode == "apto" else 60
            matrix = self._build_matrix_grid(matrix_scope, row_field, rows_max=rows_max)
            matrix["mode"] = matrix_mode
            matrix["row_field"] = row_field
            matrix["header_first_col"] = {
                "bloco": "Bloco",
                "pavimento": "Pavimento",
                "apto": "Apto / und.",
            }.get(matrix_mode, "Bloco")

            if selected["bloco"] and selected["atividade"]:
                focus_qs = raw_qs.filter(bloco=selected["bloco"], atividade__iexact=selected["atividade"])
                if selected["setor"]:
                    focus_qs = focus_qs.filter(setor=selected["setor"])
                if selected["pavimento"]:
                    focus_qs = focus_qs.filter(pavimento=selected["pavimento"])
                if selected["apto"]:
                    focus_qs = focus_qs.filter(apto=selected["apto"])
                if status_filter == "concluido":
                    focus_qs = focus_qs.filter(Q(status_percentual__gte=1) | Q(status_texto__icontains="conclu"))
                elif status_filter == "em_andamento":
                    focus_qs = focus_qs.filter(
                        Q(status_percentual__gt=0, status_percentual__lt=1)
                        | Q(status_texto__icontains="exec")
                        | Q(status_texto__icontains="parcial")
                    )
                elif status_filter == "nao_iniciado":
                    focus_qs = focus_qs.filter(
                        Q(status_percentual__lte=0)
                        | Q(status_texto__icontains="nao")
                        | Q(status_texto__icontains="não")
                        | Q(status_texto__icontains="pend")
                    )

                if is_area_comum:
                    pav_agg: dict[str, dict] = {}
                    ratio_values: list[float] = []
                    for item in focus_qs.only(
                        "pavimento", "status_texto", "status_percentual", "data_termino", "observacao"
                    ):
                        ratio = self._status_to_ratio(item)
                        if ratio is not None:
                            ratio_values.append(ratio)
                        pk = (item.pavimento or "-").strip() or "-"
                        if pk not in pav_agg:
                            pav_agg[pk] = {
                                "pavimento": pk,
                                "sum_ratio": 0.0,
                                "count_ratio": 0,
                                "status_texto": item.status_texto or "",
                                "data_termino": item.data_termino,
                                "observacao": (item.observacao or "")[:120],
                            }
                        if ratio is not None:
                            pav_agg[pk]["sum_ratio"] += ratio
                            pav_agg[pk]["count_ratio"] += 1

                    apto_rows = []
                    concluidos = 0
                    em_andamento = 0
                    nao_iniciados = 0
                    for _, data in pav_agg.items():
                        avg_ratio = data["sum_ratio"] / data["count_ratio"] if data["count_ratio"] > 0 else None
                        bucket = self._status_bucket_from_ratio(avg_ratio)
                        if bucket == "concluido":
                            concluidos += 1
                        elif bucket == "em_andamento":
                            em_andamento += 1
                        elif bucket == "nao_iniciado":
                            nao_iniciados += 1
                        apto_rows.append(
                            {
                                "apto": None,
                                "pavimento": data["pavimento"],
                                "pct": round((avg_ratio or 0) * 100) if avg_ratio is not None else None,
                                "status_bucket": bucket,
                                "status_texto": data["status_texto"] or "-",
                                "data_termino": data["data_termino"],
                                "observacao": data["observacao"] or "-",
                            }
                        )
                    apto_rows.sort(key=lambda r: (r["pct"] is None, r["pct"] if r["pct"] is not None else 999))
                    if (selected.get("pavimento") or "").strip():
                        media_pct = round((sum(ratio_values) / len(ratio_values)) * 100) if ratio_values else None
                    else:
                        inner_means_ac = [
                            data["sum_ratio"] / data["count_ratio"] for data in pav_agg.values() if data["count_ratio"] > 0
                        ]
                        media_pct = round(sum(inner_means_ac) / len(inner_means_ac) * 100) if inner_means_ac else None
                else:
                    apto_agg: dict[tuple[str, str], dict] = {}
                    ratio_values = []
                    by_pav_for_media: dict[str, list[float]] = {}
                    for item in focus_qs.only(
                        "apto", "pavimento", "status_texto", "status_percentual", "data_termino", "observacao"
                    ):
                        ratio = self._status_to_ratio(item)
                        if ratio is not None:
                            ratio_values.append(ratio)
                            pk = (str(item.pavimento or "").strip() or "-") or "-"
                            by_pav_for_media.setdefault(pk, []).append(ratio)
                        apto_key = ((item.apto or "SEM APTO").strip() or "SEM APTO", (item.pavimento or "-").strip() or "-")
                        if apto_key not in apto_agg:
                            apto_agg[apto_key] = {
                                "apto": apto_key[0],
                                "pavimento": apto_key[1],
                                "sum_ratio": 0.0,
                                "count_ratio": 0,
                                "status_texto": item.status_texto or "",
                                "data_termino": item.data_termino,
                                "observacao": (item.observacao or "")[:120],
                            }
                        if ratio is not None:
                            apto_agg[apto_key]["sum_ratio"] += ratio
                            apto_agg[apto_key]["count_ratio"] += 1

                    apto_rows = []
                    concluidos = 0
                    em_andamento = 0
                    nao_iniciados = 0
                    for _, data in apto_agg.items():
                        avg_ratio = data["sum_ratio"] / data["count_ratio"] if data["count_ratio"] > 0 else None
                        bucket = self._status_bucket_from_ratio(avg_ratio)
                        if bucket == "concluido":
                            concluidos += 1
                        elif bucket == "em_andamento":
                            em_andamento += 1
                        elif bucket == "nao_iniciado":
                            nao_iniciados += 1
                        apto_rows.append(
                            {
                                "apto": data["apto"],
                                "pavimento": data["pavimento"],
                                "pct": round((avg_ratio or 0) * 100) if avg_ratio is not None else None,
                                "status_bucket": bucket,
                                "status_texto": data["status_texto"] or "-",
                                "data_termino": data["data_termino"],
                                "observacao": data["observacao"] or "-",
                            }
                        )

                    apto_rows.sort(key=lambda r: (r["pct"] is None, r["pct"] if r["pct"] is not None else 999))
                    if (selected.get("pavimento") or "").strip():
                        media_pct = round((sum(ratio_values) / len(ratio_values)) * 100) if ratio_values else None
                    else:
                        inner_means_hab = [sum(vals) / len(vals) for vals in by_pav_for_media.values() if vals]
                        media_pct = round(sum(inner_means_hab) / len(inner_means_hab) * 100) if inner_means_hab else None
                status_ref = (
                    ItemMapaServicoStatusRef.objects.filter(
                        obra=obra,
                        atividade_chave=self._norm_key(selected["atividade"]),
                    )
                    .only("status_macro", "situacao", "prazo_execucao", "responsabilidade")
                    .first()
                )
                _recorte = []
                if selected["setor"]:
                    _recorte.append(f"Setor: {selected['setor']}")
                if selected["pavimento"]:
                    _recorte.append(f"Pavimento: {selected['pavimento']}")
                if selected["apto"]:
                    _recorte.append(f"Unidade: {selected['apto']}")
                focus_detail = {
                    "bloco": selected["bloco"],
                    "atividade": selected["atividade"],
                    "recorte_linha": " · ".join(_recorte),
                    "registros_linhas": focus_qs.count(),
                    "pct_na_grade": grid_pct_clicado,
                    "media_pct": media_pct,
                    "total_aptos": len(apto_rows),
                    "concluidos": concluidos,
                    "em_andamento": em_andamento,
                    "nao_iniciados": nao_iniciados,
                    "rows": apto_rows[:80],
                    "status_macro": status_ref.status_macro if status_ref else "",
                    "situacao": status_ref.situacao if status_ref else "",
                    "prazo_execucao": status_ref.prazo_execucao if status_ref else "",
                    "responsabilidade": status_ref.responsabilidade if status_ref else "",
                    "omitir_apto": is_area_comum,
                }

            scoped_qs = base_qs
            if selected["setor"]:
                scoped_qs = scoped_qs.filter(setor=selected["setor"])
            if selected["bloco"]:
                scoped_qs = scoped_qs.filter(bloco=selected["bloco"])
            if selected["pavimento"]:
                scoped_qs = scoped_qs.filter(pavimento=selected["pavimento"])
            if selected["apto"]:
                scoped_qs = scoped_qs.filter(apto=selected["apto"])
                itens_atividade = list(
                    scoped_qs.values(
                        "atividade",
                        "grupo_servicos",
                        "status_texto",
                        "status_percentual",
                        "observacao",
                        "custo",
                        "data_termino",
                    ).order_by("grupo_servicos", "atividade")
                )[:500]
                for row in itens_atividade:
                    pct = row.get("status_percentual")
                    if pct is None:
                        row["pct_display"] = None
                        continue
                    try:
                        pct_value = float(pct)
                    except (TypeError, ValueError):
                        row["pct_display"] = None
                        continue
                    if pct_value <= 1:
                        pct_value = pct_value * 100
                    row["pct_display"] = round(pct_value, 2)
            elif is_area_comum and selected["pavimento"]:
                itens_atividade = list(
                    scoped_qs.values(
                        "atividade",
                        "grupo_servicos",
                        "status_texto",
                        "status_percentual",
                        "observacao",
                        "custo",
                        "data_termino",
                    ).order_by("grupo_servicos", "atividade")
                )[:500]
                for row in itens_atividade:
                    pct = row.get("status_percentual")
                    if pct is None:
                        row["pct_display"] = None
                        continue
                    try:
                        pct_value = float(pct)
                    except (TypeError, ValueError):
                        row["pct_display"] = None
                        continue
                    if pct_value <= 1:
                        pct_value = pct_value * 100
                    row["pct_display"] = round(pct_value, 2)

            all_items = list(active_scope_qs.only("status_percentual", "status_texto"))
            total_itens = len(all_items)
            concluidos = 0
            em_andamento = 0
            nao_iniciados = 0
            soma_pct = 0.0
            pct_count = 0
            for item in all_items:
                status_txt = (item.status_texto or "").lower()
                if item.status_percentual is not None:
                    pct = float(item.status_percentual)
                    soma_pct += pct
                    pct_count += 1
                    if pct >= 1:
                        concluidos += 1
                    elif pct <= 0:
                        nao_iniciados += 1
                    else:
                        em_andamento += 1
                elif "conclu" in status_txt:
                    concluidos += 1
                elif "exec" in status_txt or "parcial" in status_txt:
                    em_andamento += 1
                else:
                    nao_iniciados += 1

            kpis = {
                "total_itens": total_itens,
                "percentual_medio": round((soma_pct / pct_count) * 100, 2) if pct_count else 0.0,
                "concluidos": concluidos,
                "em_andamento": em_andamento,
                "nao_iniciados": nao_iniciados,
            }
            if (
                (selected.get("atividade") or "").strip()
                and not (selected.get("pavimento") or "").strip()
                and not (selected.get("apto") or "").strip()
            ):
                if (selected.get("bloco") or "").strip():
                    hier_med = self._mean_ratio_equal_weight_groups(
                        list(active_scope_qs.only("pavimento", "status_percentual", "status_texto")),
                        lambda it: (str(getattr(it, "pavimento", None) or "").strip() or "SEM PAVIMENTO"),
                    )
                else:
                    hier_med = self._mean_ratio_equal_weight_blocos_then_pavimento(
                        list(active_scope_qs.only("bloco", "pavimento", "status_percentual", "status_texto"))
                    )
                if hier_med is not None:
                    kpis["percentual_medio"] = round(hier_med * 100, 2)
            qualidade = {
                "sem_bloco": active_scope_qs.filter(Q(bloco__isnull=True) | Q(bloco__exact="")).count(),
                "sem_pavimento": active_scope_qs.filter(Q(pavimento__isnull=True) | Q(pavimento__exact="")).count(),
                "sem_apto": active_scope_qs.filter(Q(apto__isnull=True) | Q(apto__exact="")).count(),
                "sem_status_percentual": active_scope_qs.filter(status_percentual__isnull=True).count(),
                "sem_data_termino": active_scope_qs.filter(data_termino__isnull=True).count(),
            }
            confiabilidade = self._build_confiabilidade_controle(kpis["total_itens"], qualidade)

            _st_lbl = {
                "": "Qualquer status",
                "concluido": "Só concluídos",
                "em_andamento": "Só em andamento",
                "nao_iniciado": "Só não iniciados",
            }
            _path_segs = []
            if selected["setor"]:
                _path_segs.append(f"Setor: {selected['setor']}")
            if selected["bloco"]:
                _path_segs.append(f"Bloco: {selected['bloco']}")
            if selected["pavimento"]:
                _path_segs.append(f"Pav.: {selected['pavimento']}")
            if selected["apto"]:
                _path_segs.append(f"Unid.: {selected['apto']}")
            if selected["atividade"]:
                _path_segs.append(f"Ativ. (coluna): {selected['atividade']}")
            _modo_grade = {
                "bloco": "Bloco × atividade",
                "pavimento": "Pavimento × atividade",
                "apto": "Unidade × atividade",
            }.get(matrix.get("mode", "bloco"), "Bloco × atividade")
            matrix_context = {
                "obra_titulo": f"{obra.codigo_sienge} — {obra.nome}",
                "caminho": " › ".join(_path_segs) if _path_segs else "Obra inteira — sem recorte de localização",
                "status_filtro": _st_lbl.get(selected["status"], selected["status"] or "Qualquer status"),
                "modo_grade_label": _modo_grade,
                "n_grade_linhas": len(matrix.get("rows") or []),
                "n_grade_cols": len(matrix.get("atividades") or []),
                "cnt_setores": len(layers["setores"]),
                "cnt_blocos_camada": len(layers["blocos"]) if layers["blocos"] else None,
                "cnt_pavs_camada": len(layers["pavimentos"]) if layers["pavimentos"] else None,
                "cnt_unids_camada": len(layers["aptos"]) if layers["aptos"] else None,
            }

        matrix_stable_qs = ""
        if obra:
            stable_params = {}
            if str(selected.get("atividade") or "").strip():
                stable_params["atividade"] = selected["atividade"]
            matrix_stable_qs = urlencode(stable_params)

            def _build_nav_url(params: dict) -> str:
                clean = {}
                for k, v in params.items():
                    txt = str(v or "").strip()
                    if txt:
                        clean[k] = txt
                qs = urlencode(clean)
                return f"?{qs}" if qs else "?"

            base_nav_params = {
                "obra": obra.id,
                "status": selected["status"],
                "search": selected["search"],
                "quick": selected["quick_find"],
                "matrix_mode": matrix.get("mode", "bloco"),
            }
            nav_levels = [("setor", "Setor"), ("bloco", "Bloco"), ("pavimento", "Pavimento")]
            if not is_area_comum:
                nav_levels.append(("apto", "Unidade"))
            nav_levels.append(("atividade", "Atividade"))

            active_levels = []
            for key, label in nav_levels:
                val = (selected.get(key) or "").strip()
                if val:
                    active_levels.append((key, label, val))

            if active_levels:
                layer_nav["has_scope"] = True
                layer_nav["depth"] = len(active_levels)
                layer_nav["root_url"] = _build_nav_url(base_nav_params)
                layer_nav["current_path"] = " > ".join(f"{label}: {value}" for _, label, value in active_levels)
                if len(active_levels) == 1:
                    layer_nav["prev_url"] = layer_nav["root_url"]
                else:
                    prev_params = dict(base_nav_params)
                    for key, _, value in active_levels[:-1]:
                        prev_params[key] = value
                    layer_nav["prev_url"] = _build_nav_url(prev_params)

                crumbs = []
                crumb_params = dict(base_nav_params)
                for key, label, value in active_levels:
                    crumb_params[key] = value
                    crumbs.append({"label": label, "value": value, "url": _build_nav_url(crumb_params)})
                layer_nav["breadcrumbs"] = crumbs
            else:
                layer_nav["root_url"] = _build_nav_url(base_nav_params)

        coluna_filtrada_aviso = None
        if obra and selected["atividade"] and not focus_detail:
            coluna_filtrada_aviso = selected["atividade"]

        macro_pulse = self._macro_pulse(kpis, confiabilidade, qualidade) if obra else None

        return {
            "selected": selected,
            "layers": layers,
            "itens_atividade": itens_atividade,
            "matrix": matrix,
            "kpis": kpis,
            "qualidade": qualidade,
            "confiabilidade": confiabilidade,
            "quick_match": quick_match,
            "importacao_info": importacao_info,
            "focus_detail": focus_detail,
            "matrix_context": matrix_context,
            "coluna_filtrada_aviso": coluna_filtrada_aviso,
            "macro_pulse": macro_pulse,
            "matrix_stable_qs": matrix_stable_qs,
            "is_area_comum": is_area_comum,
            "layer_nav": layer_nav,
            "column_groups": [],
            "matrix_all_atividades": matrix.get("atividades") or [],
            "column_group_selected": "",
        }
