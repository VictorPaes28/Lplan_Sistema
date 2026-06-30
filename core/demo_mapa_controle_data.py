"""
Matriz demo compartilhada: AmbienteOperacional (layout JSON) e ItemMapaServico.

Gera volume e variedade realistas para mapa dedicado e BI da Obra.
"""

from __future__ import annotations

import random
from decimal import Decimal
from typing import Iterator

ATIVIDADES_MAPA = [
    "Fundações / estrutura",
    "Alvenaria de vedação",
    "Instalações elétricas",
    "Instalações hidráulicas",
    "Esquadrias",
    "Revestimento cerâmico",
    "Revestimento de parede",
    "Forro de gesso",
    "Pintura interna",
    "Acabamento geral",
    "Elevador / montagem",
]

BLOCOS_EDIFICIO = ["A", "B", "C", "D"]
PAVIMENTOS_EDIFICIO = ["TÉRREO", "1", "2", "3", "4", "COBERTURA"]

COLUMN_GROUPS = [
    {"label": "Estrutura", "cols": [0, 1]},
    {"label": "Instalações", "cols": [2, 3]},
    {"label": "Acabamentos", "cols": [4, 5, 6, 7, 8, 9]},
    {"label": "Montagem", "cols": [10]},
]


def aptos_por_pavimento(pav: str) -> list[str]:
    if pav == "TÉRREO":
        return ["101", "102", "103", "104"]
    if pav == "COBERTURA":
        return ["501", "502"]
    if pav == "SUBSOLO":
        return ["G1", "G2", "G3", "G4"]
    try:
        n = int(pav)
        base = n * 100
        return [str(base + i) for i in range(1, 5)]
    except ValueError:
        return ["U1", "U2"]


def iter_unidades_demo() -> Iterator[tuple[str, str, str, str]]:
    """(setor, bloco, pavimento, apto) — uma linha da matriz."""
    for bloco in BLOCOS_EDIFICIO:
        for pav in PAVIMENTOS_EDIFICIO:
            for apto in aptos_por_pavimento(pav):
                yield ("EDIFÍCIO", bloco, pav, apto)

    for apto in aptos_por_pavimento("SUBSOLO"):
        yield ("GARAGEM", "G", "SUBSOLO", apto)

    for unidade in ["LOBBY", "SALÃO DE FESTAS", "PISCINA", "CHURRASQUEIRA", "PLAYGROUND"]:
        yield ("ÁREA COMUM", "AC", "TÉRREO", unidade)


def _cell_seed(obra_id: int, setor: str, bloco: str, pav: str, apto: str, act_idx: int) -> int:
    parts = (obra_id, setor, bloco, pav, apto, act_idx)
    h = 0
    for p in parts:
        h = (h * 1315423911 + hash(p)) & 0xFFFFFFFF
    return h


def pct_celula_demo(
    obra_id: int,
    setor: str,
    bloco: str,
    pav: str,
    apto: str,
    act_idx: int,
) -> str:
    """Percentual 0–100, vazio ou '-' (sem dado)."""
    rng = random.Random(_cell_seed(obra_id, setor, bloco, pav, apto, act_idx))

    if rng.random() < 0.04:
        return "-" if rng.random() < 0.55 else ""

    bloco_delta = {"A": 0, "B": 6, "C": -4, "D": 10, "G": 18, "AC": -8}.get(bloco, 0)
    pav_delta = {
        "SUBSOLO": 35,
        "TÉRREO": 28,
        "1": 22,
        "2": 16,
        "3": 8,
        "4": 2,
        "COBERTURA": -6,
    }.get(pav, 10)
    setor_delta = {"EDIFÍCIO": 0, "GARAGEM": 12, "ÁREA COMUM": -12}.get(setor, 0)
    obra_delta = (obra_id % 11) * 3

    # Serviços anteriores tendem a estar mais avançados
    act_delta = max(-10, 38 - act_idx * 5)

    val = 12 + obra_delta + bloco_delta + pav_delta + setor_delta + act_delta
    val += rng.randint(-18, 18)

    # Alguns aptos “atrasados” ou “adiantados”
    apto_hash = hash((bloco, pav, apto)) % 7
    if apto_hash == 0:
        val -= 22
    elif apto_hash == 1:
        val += 15

    val = max(0, min(100, val))
    val = round(val / 5) * 5
    return str(int(val))


def pct_celula_decimal(
    obra_id: int,
    setor: str,
    bloco: str,
    pav: str,
    apto: str,
    act_idx: int,
) -> Decimal:
    raw = pct_celula_demo(obra_id, setor, bloco, pav, apto, act_idx)
    if raw in ("", "-"):
        return Decimal("0")
    return Decimal(str(round(float(raw) / 100, 3)))


def status_from_pct(pct: Decimal) -> tuple[str, Decimal]:
    if pct >= Decimal("1"):
        return "Concluído", Decimal("1.000")
    if pct >= Decimal("0.75"):
        return "Em execução", pct
    if pct >= Decimal("0.40"):
        return "Em execução", pct
    if pct >= Decimal("0.15"):
        return "Parcial", pct
    if pct > Decimal("0"):
        return "Aguardando material", pct
    return "Não iniciado", Decimal("0")


def build_mapa_controle_layout(obra_id: int) -> dict:
    from painel_operacional.views import _mapa_controle_weights

    header = ["SETOR", "BLOCO", "PAVIMENTO", "APTO"] + ATIVIDADES_MAPA + ["Total"]
    rows = [header]

    for setor, bloco, pav, apto in iter_unidades_demo():
        row = [setor, bloco, pav, apto]
        pcts: list[float] = []
        for j, _act in enumerate(ATIVIDADES_MAPA):
            val = pct_celula_demo(obra_id, setor, bloco, pav, apto, j)
            row.append(val)
            if val not in ("", "-"):
                try:
                    pcts.append(float(val))
                except ValueError:
                    pass
        total = round(sum(pcts) / len(pcts), 1) if pcts else ""
        row.append(str(total) if total != "" else "")
        rows.append(row)

    axis_start = 4
    activity_cols = list(range(axis_start, axis_start + len(ATIVIDADES_MAPA)))
    weights = _mapa_controle_weights(rows, totals_row_auto=True)
    import_meta = {
        "strategy": "manual_template",
        "axis_cols_interpreted": [0, 1, 2, 3],
        "axis_headers_interpreted": ["SETOR", "BLOCO", "PAVIMENTO", "APTO"],
        "activity_cols_interpreted": activity_cols,
        "activity_headers_interpreted": ATIVIDADES_MAPA[:],
        "row_axis_key": "bloco",
    }
    row_count = len(rows) - 1
    return {
        "title": "Mapa de Controle",
        "sections": [
            {
                "id": "matriz",
                "kind": "matrix_table",
                "title": "Matriz de Controle",
                "x": 80,
                "y": 80,
                "width": 920,
                "height": min(1200, 120 + row_count * 22),
                "layer": {},
                "data": {
                    "mapaControleTemplate": True,
                    "headerBandCount": 1,
                    "heatmap": True,
                    "totalsColumnAuto": True,
                    "totalsRowAuto": True,
                    "verticalHeaders": True,
                    "columnGroups": COLUMN_GROUPS,
                    "rows": rows,
                    "colWeights": weights["colWeights"],
                    "rowWeights": weights["rowWeights"],
                    "importMeta": import_meta,
                },
            },
        ],
    }


def count_unidades_demo() -> int:
    return sum(1 for _ in iter_unidades_demo())
