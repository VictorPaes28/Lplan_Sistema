"""Itens de reembolso previstos na requisição de admissão."""
from __future__ import annotations

import json
import re
from decimal import Decimal, InvalidOperation

from recursos_humanos.services.admissao import formatar_salario_br

_MAX_ITENS = 20
_MAX_TITULO = 120
_MAX_DESCRICAO = 500


def _limpar_texto(valor, *, max_len: int) -> str:
    return (valor or '').strip()[:max_len]


def normalizar_valor_reembolso(valor) -> str:
    bruto = (valor or '').strip()
    if not bruto:
        return ''
    return formatar_salario_br(bruto)


def normalizar_item_reembolso(item: dict) -> dict | None:
    if not isinstance(item, dict):
        return None
    titulo = _limpar_texto(item.get('titulo'), max_len=_MAX_TITULO)
    descricao = _limpar_texto(item.get('descricao'), max_len=_MAX_DESCRICAO)
    valor = normalizar_valor_reembolso(item.get('valor'))
    if not titulo and not descricao and not valor:
        return None
    if not titulo:
        titulo = 'Reembolso'
    return {
        'titulo': titulo,
        'descricao': descricao,
        'valor': valor,
    }


def parse_reembolsos_json(raw) -> list[dict]:
    """Converte JSON (str ou list) em lista normalizada de reembolsos."""
    if raw is None or raw == '':
        return []
    if isinstance(raw, list):
        fonte = raw
    else:
        texto = str(raw).strip()
        if not texto or texto == '[]':
            return []
        try:
            fonte = json.loads(texto)
        except (TypeError, json.JSONDecodeError):
            return []
    if not isinstance(fonte, list):
        return []
    itens: list[dict] = []
    for entry in fonte[:_MAX_ITENS]:
        item = normalizar_item_reembolso(entry)
        if item:
            itens.append(item)
    return itens


def reembolsos_colaborador(colaborador) -> list[dict]:
    return parse_reembolsos_json(getattr(colaborador, 'reembolsos', None) or [])


def total_reembolsos(itens: list[dict]) -> str:
    total = Decimal('0')
    for item in itens:
        valor = (item.get('valor') or '').strip()
        if not valor:
            continue
        texto = valor.replace('.', '').replace(',', '.')
        try:
            total += Decimal(texto)
        except InvalidOperation:
            continue
    if total == 0:
        return ''
    return formatar_salario_br(str(total))


def reembolsos_para_contexto(colaborador) -> dict:
    itens = reembolsos_colaborador(colaborador)
    return {
        'itens': itens,
        'total': total_reembolsos(itens),
        'tem_itens': bool(itens),
    }
