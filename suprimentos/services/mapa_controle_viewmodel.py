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


def _parse_pct_loose(value):
    raw = str(value or "").strip()
    if not raw:
        return None
    token = _norm_token(raw)
    # Semântica operacional: "-" representa pendência/não iniciado (0%).
    if token in {"-", "--"}:
        return 0
    # Valores explícitos de N/A permanecem fora do denominador.
    if token in {"N/A", "NA", "N A", "NAO SE APLICA", "NÃO SE APLICA"}:
        return None
    had_percent = "%" in raw
    raw = raw.replace("%", "").replace(",", ".").strip()
    try:
        num = float(raw)
    except (TypeError, ValueError):
        return None
    if not had_percent and -1.0 <= num <= 1.0:
        num *= 100.0
    num = max(0.0, min(100.0, num))
    if abs(num - round(num)) < 0.01:
        return int(round(num))
    return round(num, 1)


def _fmt_pct(value):
    try:
        num = float(value)
    except (TypeError, ValueError):
        return ""
    if abs(num - round(num)) < 0.01:
        return f"{int(round(num))}%"
    return f"{round(num, 1)}%"


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
        elif ("APTO" in token or "UNIDADE" in token or "LOCAL" in token) and "apto" not in axis_map:
            axis_map["apto"] = col
            used.add(col)
    leftovers = [col for col, _ in pairs if col not in used]
    for key in keys:
        if key in axis_map:
            continue
        if leftovers:
            axis_map[key] = leftovers.pop(0)
    return axis_map


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
        body_rows = rows_layout[1:] if len(rows_layout) > 1 else []
        axis_map = _extract_axis_map_from_meta(matrix_meta)
        axis_cols = [idx for idx in axis_map.values() if isinstance(idx, int)]
        axis_cols = sorted(set(axis_cols))

        activity_cols = matrix_meta.get("activity_cols_interpreted") if isinstance(matrix_meta.get("activity_cols_interpreted"), list) else []
        activity_cols = [c for c in activity_cols if isinstance(c, int)]
        if not activity_cols and header:
            activity_cols = [idx for idx in range(len(header)) if idx not in axis_cols]

        quick_find = str(selected.get("quick_find") or "").strip()
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

        def _row_matches_axes(row_vals: list) -> bool:
            for key in ("setor", "bloco", "pavimento", "apto"):
                wanted = str(selected.get(key) or "").strip()
                if not wanted:
                    continue
                idx = axis_map.get(key)
                if not isinstance(idx, int):
                    continue
                current = str(row_vals[idx] if idx < len(row_vals) else "").strip()
                if current != wanted:
                    return False
            return True

        search_filter = str(selected.get("search") or "").strip().lower()
        status_filter = str(selected.get("status") or "").strip()
        filtered_body = []
        for row in body_rows:
            if not isinstance(row, list):
                continue
            if not _row_matches_axes(row):
                continue
            if search_filter:
                row_blob = " ".join(str(v or "") for v in row).lower()
                if search_filter not in row_blob:
                    continue
            filtered_body.append(row)

        def _distinct_axis_values(rows_src: list[list], axis_key: str, prefilter: dict | None = None):
            idx = axis_map.get(axis_key)
            if not isinstance(idx, int):
                return []
            values = []
            seen = set()
            for row in rows_src:
                if not isinstance(row, list):
                    continue
                if prefilter:
                    ok = True
                    for k, v in prefilter.items():
                        i2 = axis_map.get(k)
                        if not isinstance(i2, int):
                            continue
                        cur = str(row[i2] if i2 < len(row) else "").strip()
                        if cur != str(v or "").strip():
                            ok = False
                            break
                    if not ok:
                        continue
                val = str(row[idx] if idx < len(row) else "").strip()
                if val in seen:
                    continue
                seen.add(val)
                values.append(val)
            return values

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

        def _layer_rows_with_stats(axis_key: str, prefilter: dict | None = None):
            idx = axis_map.get(axis_key)
            if not isinstance(idx, int):
                return []
            values = _distinct_axis_values(body_rows, axis_key, prefilter)
            rows = []
            for v in values:
                rows_match = []
                for row in body_rows:
                    if not isinstance(row, list):
                        continue
                    if prefilter:
                        ok = True
                        for k, pv in prefilter.items():
                            i2 = axis_map.get(k)
                            if not isinstance(i2, int):
                                continue
                            cur = str(row[i2] if i2 < len(row) else "").strip()
                            if cur != str(pv or "").strip():
                                ok = False
                                break
                        if not ok:
                            continue
                    cur_axis = str(row[idx] if idx < len(row) else "").strip()
                    if cur_axis == str(v or "").strip():
                        rows_match.append(row)

                values_pct = []
                for row in rows_match:
                    for col_idx, _lbl in activity_labels:
                        if col_idx >= len(row):
                            continue
                        pct = _parse_pct_loose(row[col_idx])
                        if pct is not None:
                            values_pct.append(float(pct))

                total = len(rows_match)
                progresso = round((sum(values_pct) / len(values_pct)) * 100, 2) if values_pct else 0.0
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
        # Isso evita cenários inconsistentes quando a navegação mistura chips e links da matriz.
        if str(selected.get("apto") or "").strip():
            row_mode_requested = "apto"
        elif str(selected.get("pavimento") or "").strip():
            row_mode_requested = "apto"
        elif str(selected.get("bloco") or "").strip():
            row_mode_requested = "pavimento"
        else:
            row_mode_requested = "bloco"
        if row_mode_requested == "apto" and not str(selected.get("pavimento") or "").strip():
            row_mode_requested = "pavimento" if str(selected.get("bloco") or "").strip() else "bloco"
        if row_mode_requested == "pavimento" and not str(selected.get("bloco") or "").strip():
            row_mode_requested = "bloco"

        row_axis_key = "bloco" if row_mode_requested == "bloco" else ("pavimento" if row_mode_requested == "pavimento" else "apto")
        row_axis_col = axis_map.get(row_axis_key)
        if not isinstance(row_axis_col, int):
            row_axis_col = axis_cols[0] if axis_cols else 0

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

        # Base numérica para totais/KPIs: sempre parte das células do recorte efetivo
        # (após filtros), antes de eventual agregação visual por camada.
        activity_value_buckets = {label: [] for _idx, label in activity_labels}
        for row in processed_rows:
            for col_idx, label in activity_labels:
                if col_idx >= len(row):
                    continue
                raw_val = row[col_idx]
                pct = _parse_pct_loose(raw_val)
                if pct is None:
                    continue
                activity_value_buckets[label].append(float(pct))

        if row_mode_requested in {"bloco", "pavimento"} and isinstance(row_axis_col, int):
            grouped = {}
            for row in processed_rows:
                key = str(row[row_axis_col] if row_axis_col < len(row) else "").strip()
                if not key:
                    key = "Sem valor"
                if key not in grouped:
                    grouped[key] = {col_idx: [] for col_idx, _ in activity_labels}
                for col_idx, _label in activity_labels:
                    if col_idx >= len(row):
                        continue
                    pct = _parse_pct_loose(row[col_idx])
                    if pct is not None:
                        grouped[key][col_idx].append(float(pct))

            aggregated_rows = []
            for key, by_col in grouped.items():
                out = [""] * len(header)
                out[row_axis_col] = key
                for col_idx, _label in activity_labels:
                    values = by_col.get(col_idx) or []
                    if not values:
                        continue
                    avg = sum(values) / len(values)
                    out[col_idx] = _fmt_pct(avg)
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
        matrix["header_first_col"] = {
            "bloco": "Bloco",
            "pavimento": "Pavimento",
            "apto": "Apto / und.",
        }.get(row_mode_requested, matrix.get("header_first_col"))

        # Densificação controlada no dedicado:
        # célula vazia estrutural ("") passa a 0%; N/A segue fora.
        dense_zero_enabled = str(matrix_meta.get("strategy") or "").strip() in {
            "pivot_registros",
            "pivot_atividade_colunas",
            "matriz_detectada",
        }
        if dense_zero_enabled:
            for row in matrix.get("rows") or []:
                for cell in row.get("cells") or []:
                    if cell.get("pct") is not None:
                        continue
                    raw_token = _norm_token(cell.get("raw"))
                    if raw_token in {"-", "--"}:
                        cell["pct"] = 0

        # Recalcula totais/KPIs por base real de células (evita média de médias).
        totais_reais = []
        all_values = []
        for _idx, label in activity_labels:
            vals = activity_value_buckets.get(label) or []
            if not vals:
                totais_reais.append({"atividade": label, "pct": None})
                continue
            avg = sum(vals) / len(vals)
            pct = int(round(avg)) if abs(avg - round(avg)) < 0.01 else round(avg, 1)
            totais_reais.append({"atividade": label, "pct": pct})
            all_values.extend(vals)
        matrix["totais"] = totais_reais

        rows_matrix = matrix.get("rows") or []
        for row in rows_matrix:
            vals = [float(c.get("pct")) for c in (row.get("cells") or []) if c.get("pct") is not None]
            if vals:
                avg = sum(vals) / len(vals)
                row["total"] = int(round(avg)) if abs(avg - round(avg)) < 0.01 else round(avg, 1)
            else:
                row["total"] = None

        if all_values:
            media = sum(all_values) / len(all_values)
            media_fmt = int(round(media)) if abs(media - round(media)) < 0.01 else round(media, 1)
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
            "caminho": f"Ambiente dedicado — {ambiente.nome}",
            "status_filtro": "Dados do ambiente",
            "modo_grade_label": "Bloco × atividade",
            "n_grade_linhas": len(matrix.get("rows") or []),
            "n_grade_cols": len(matrix.get("atividades") or []),
            "cnt_setores": len(layers["setores"]),
            "cnt_blocos_camada": len(layers["blocos"]),
            "cnt_pavs_camada": len(layers["pavimentos"]),
            "cnt_unids_camada": len(layers["aptos"]),
        }
        matrix_stable_qs = urlencode(
            {
                "status": selected["status"],
                "search": selected["search"],
                "quick": selected["quick_find"],
                "atividade": selected["atividade"],
                "matrix_mode": row_mode_requested,
                "ambiente_id": ambiente.id,
            }
        )
        base_qs = {
            "obra": obra.id,
            "ambiente_id": ambiente.id,
            "status": selected["status"],
            "search": selected["search"],
            "quick": selected["quick_find"],
            "atividade": selected["atividade"],
            "matrix_mode": row_mode_requested,
        }
        root_qs = urlencode({k: v for k, v in base_qs.items() if str(v or "").strip()})

        breadcrumbs = []
        if str(selected.get("setor") or "").strip():
            breadcrumbs.append({"label": str(selected["setor"]), "url": f"?{urlencode({'obra': obra.id, 'ambiente_id': ambiente.id, 'setor': selected['setor']})}"})
        if str(selected.get("bloco") or "").strip():
            breadcrumbs.append(
                {
                    "label": str(selected["bloco"]),
                    "url": f"?{urlencode({'obra': obra.id, 'ambiente_id': ambiente.id, 'setor': selected.get('setor',''), 'bloco': selected['bloco']})}",
                }
            )
        if str(selected.get("pavimento") or "").strip():
            breadcrumbs.append(
                {
                    "label": str(selected["pavimento"]),
                    "url": f"?{urlencode({'obra': obra.id, 'ambiente_id': ambiente.id, 'setor': selected.get('setor',''), 'bloco': selected.get('bloco',''), 'pavimento': selected['pavimento']})}",
                }
            )
        if str(selected.get("apto") or "").strip():
            breadcrumbs.append(
                {
                    "label": str(selected["apto"]),
                    "url": f"?{urlencode({'obra': obra.id, 'ambiente_id': ambiente.id, 'setor': selected.get('setor',''), 'bloco': selected.get('bloco',''), 'pavimento': selected.get('pavimento',''), 'apto': selected['apto']})}",
                }
            )
        layer_nav = {
            "has_scope": bool(breadcrumbs),
            "depth": len(breadcrumbs),
            "root_url": f"?{root_qs}" if root_qs else "?",
            "prev_url": f"?{root_qs}" if root_qs else "?",
            "current_path": f"Ambiente: {ambiente.nome}",
            "breadcrumbs": breadcrumbs,
        }
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
            "coluna_filtrada_aviso": None,
            "macro_pulse": None,
            "matrix_stable_qs": matrix_stable_qs,
            "is_area_comum": False,
            "layer_nav": layer_nav,
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
            matrix_stable_qs = urlencode(
                {
                    "status": selected["status"],
                    "search": selected["search"],
                    "quick": selected["quick_find"],
                    "atividade": selected["atividade"],
                }
            )

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
        }
