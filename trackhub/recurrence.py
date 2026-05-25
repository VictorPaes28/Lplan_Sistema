"""Regras de recorrência para pendências TrackHub (próximas datas e rótulos em PT-BR)."""

from __future__ import annotations

import calendar
from datetime import date, timedelta

from dateutil.relativedelta import relativedelta

DIAS_SEMANA_PT = (
    "segunda-feira",
    "terça-feira",
    "quarta-feira",
    "quinta-feira",
    "sexta-feira",
    "sábado",
    "domingo",
)
DIAS_SEMANA_CURTO = ("seg", "ter", "qua", "qui", "sex", "sáb", "dom")
MESES_CURTO = (
    "",
    "jan",
    "fev",
    "mar",
    "abr",
    "mai",
    "jun",
    "jul",
    "ago",
    "set",
    "out",
    "nov",
    "dez",
)


def _norm_parametros(parametros: dict | None) -> dict:
    if not isinstance(parametros, dict):
        return {}
    return parametros


def _proxima_weekday_estrita_depois(ref: date, wd: int) -> date:
    """Primeira data > ref com weekday == wd (0=seg … 6=dom)."""
    wd = max(0, min(6, int(wd)))
    start = ref + timedelta(days=1)
    d = start
    for _ in range(14):
        if d.weekday() == wd:
            return d
        d += timedelta(days=1)
    return start + timedelta(days=7)


def _proximo_mensal_intervalo_depois(ref: date, dia_querido: int, interval_months: int = 1) -> date:
    """Próxima data > ref no dia desejado, avançando de interval_months em interval_months."""
    interval_months = max(1, int(interval_months))
    y, m = ref.year, ref.month
    ult = calendar.monthrange(y, m)[1]
    dom = min(int(dia_querido), ult)
    cand = date(y, m, dom)
    if cand > ref:
        return cand
    cur = date(y, m, 1) + relativedelta(months=interval_months)
    for _ in range(48):
        ult = calendar.monthrange(cur.year, cur.month)[1]
        dom = min(int(dia_querido), ult)
        cand = date(cur.year, cur.month, dom)
        if cand > ref:
            return cand
        cur = cur + relativedelta(months=interval_months)
    return ref + timedelta(days=31 * interval_months)


def _proximo_mensal_depois(ref: date, dia_querido: int) -> date:
    return _proximo_mensal_intervalo_depois(ref, dia_querido, 1)


def _proximo_anual_depois(ref: date, mes: int, dia: int) -> date:
    mes = max(1, min(12, int(mes)))
    y = ref.year
    ult = calendar.monthrange(y, mes)[1]
    dom = min(int(dia), ult)
    cand = date(y, mes, dom)
    if cand > ref:
        return cand
    y += 1
    for _ in range(8):
        ult = calendar.monthrange(y, mes)[1]
        dom = min(int(dia), ult)
        cand = date(y, mes, dom)
        if cand > ref:
            return cand
        y += 1
    return ref + timedelta(days=365)


def _dias_semana_from_param(p: dict, dia_semana_single: int | None) -> list[int]:
    raw = p.get("dias_semana")
    if isinstance(raw, list) and raw:
        out = sorted({max(0, min(6, int(x))) for x in raw if str(x).strip() != ""})
        return out if out else [0]
    if dia_semana_single is not None:
        return [max(0, min(6, int(dia_semana_single)))]
    return [0]


def _dias_mes_from_param(p: dict, dia_mes_single: int | None) -> list[int]:
    raw = p.get("dias_mes")
    if isinstance(raw, list) and raw:
        out = sorted({max(1, min(31, int(x))) for x in raw if str(x).strip() != ""})
        return out if out else [1]
    if dia_mes_single is not None:
        return [max(1, min(31, int(dia_mes_single)))]
    return [1]


def _datas_ano_from_param(p: dict, mes: int | None, dia_mes: int | None) -> list[tuple[int, int]]:
    raw = p.get("datas_ano")
    out: list[tuple[int, int]] = []
    if isinstance(raw, list) and raw:
        for item in raw:
            if not isinstance(item, dict):
                continue
            try:
                mm = max(1, min(12, int(item.get("m"))))
                dd = max(1, min(31, int(item.get("d"))))
                out.append((mm, dd))
            except (TypeError, ValueError):
                continue
        if out:
            return out
    if mes is not None and dia_mes is not None:
        return [(max(1, min(12, int(mes))), max(1, min(31, int(dia_mes))))]
    return [(1, 1)]


def proxima_data_estrita_depois(
    ref: date,
    regra: str,
    *,
    parametros: dict | None = None,
    dia_semana: int | None = None,
    dia_mes: int | None = None,
    mes: int | None = None,
) -> date:
    """
    Primeira data da série estritamente posterior a `ref`.
    `parametros` pode conter dias_semana, dias_mes, datas_ano (listas).
    Campos escalares dia_semana / dia_mes / mes são fallback (registros antigos).
    """
    if regra == "none":
        raise ValueError("regra não pode ser 'none'")

    p = _norm_parametros(parametros)
    start = ref + timedelta(days=1)

    if regra == "daily":
        return start

    if regra == "weekdays":
        d = start
        while d.weekday() >= 5:
            d += timedelta(days=1)
        return d

    if regra == "weekly":
        dias = _dias_semana_from_param(p, dia_semana)
        return min(_proxima_weekday_estrita_depois(ref, wd) for wd in dias)

    if regra == "monthly":
        dias = _dias_mes_from_param(p, dia_mes)
        return min(_proximo_mensal_depois(ref, d) for d in dias)

    if regra == "bimonthly":
        dias = _dias_mes_from_param(p, dia_mes)
        return min(_proximo_mensal_intervalo_depois(ref, d, 2) for d in dias)

    if regra == "quarterly":
        dias = _dias_mes_from_param(p, dia_mes)
        return min(_proximo_mensal_intervalo_depois(ref, d, 3) for d in dias)

    if regra == "semiannual":
        dias = _dias_mes_from_param(p, dia_mes)
        return min(_proximo_mensal_intervalo_depois(ref, d, 6) for d in dias)

    if regra == "yearly":
        pares = _datas_ano_from_param(p, mes, dia_mes)
        return min(_proximo_anual_depois(ref, mm, dd) for mm, dd in pares)

    raise ValueError(f"regra desconhecida: {regra}")


def rotulo_recorrencia(
    regra: str,
    *,
    parametros: dict | None = None,
    dia_semana: int | None = None,
    dia_mes: int | None = None,
    mes: int | None = None,
) -> str:
    p = _norm_parametros(parametros)
    if regra == "none" or not regra:
        return "Não se repete"
    if regra == "daily":
        return "Diariamente"
    if regra == "weekdays":
        return "Dias da semana (segunda a sexta)"
    if regra == "weekly":
        dias = _dias_semana_from_param(p, dia_semana)
        if len(dias) == 1:
            return f"Toda semana na {DIAS_SEMANA_PT[dias[0]]}"
        partes = [DIAS_SEMANA_CURTO[d] for d in dias]
        return "Semanal — " + ", ".join(partes)
    if regra == "monthly":
        dias = _dias_mes_from_param(p, dia_mes)
        if len(dias) == 1:
            return f"Todo mês no dia {dias[0]}"
        return "Todo mês nos dias " + ", ".join(str(d) for d in dias)
    if regra == "bimonthly":
        dias = _dias_mes_from_param(p, dia_mes)
        if len(dias) == 1:
            return f"Bimestral — dia {dias[0]}"
        return "Bimestral — dias " + ", ".join(str(d) for d in dias)
    if regra == "quarterly":
        dias = _dias_mes_from_param(p, dia_mes)
        if len(dias) == 1:
            return f"Trimestral — dia {dias[0]}"
        return "Trimestral — dias " + ", ".join(str(d) for d in dias)
    if regra == "semiannual":
        dias = _dias_mes_from_param(p, dia_mes)
        if len(dias) == 1:
            return f"Semestral — dia {dias[0]}"
        return "Semestral — dias " + ", ".join(str(d) for d in dias)
    if regra == "yearly":
        pares = _datas_ano_from_param(p, mes, dia_mes)
        if len(pares) == 1:
            mm, dd = pares[0]
            return f"Todo ano em {dd} de {MESES_CURTO[mm]}"
        partes = [f"{dd}/{MESES_CURTO[mm]}" for mm, dd in pares]
        return "Todo ano em " + ", ".join(partes)
    return regra


def legacy_scalar_fields_for_db(regra: str, parametros: dict | None) -> tuple[int | None, int | None, int | None]:
    """Primeiro dia_semana / dia_mes / mes para colunas legadas no banco."""
    p = _norm_parametros(parametros)
    if regra == "weekly":
        d = _dias_semana_from_param(p, None)
        return (d[0], None, None) if d else (None, None, None)
    if regra == "monthly":
        dm = _dias_mes_from_param(p, None)
        return (None, dm[0], None) if dm else (None, None, None)
    if regra in ("bimonthly", "quarterly", "semiannual"):
        dm = _dias_mes_from_param(p, None)
        return (None, dm[0], None) if dm else (None, None, None)
    if regra == "yearly":
        pairs = _datas_ano_from_param(p, None, None)
        if pairs:
            mm, dd = pairs[0]
            return (None, dd, mm)
    return (None, None, None)
