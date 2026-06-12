"""
Metas de tempo (SLA) para decisão de aprovação por tipo de solicitação.
Usado em desempenho da equipe e demais indicadores de fluxo.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any

from .models import WorkOrder

SLA_HORAS_PADRAO = 24

# Metas em horas úteis de análise — contratos exigem mais tempo de leitura/validação.
SLA_HORAS_POR_TIPO: dict[str, int] = {
    'contrato': 72,
    'validacao_contrato': 72,
    'medicao': 24,
    'ordem_servico': 24,
    'mapa_cotacao': 48,
}

TIPO_SLA_ORDEM = [
    'contrato',
    'validacao_contrato',
    'medicao',
    'ordem_servico',
    'mapa_cotacao',
]


def sla_horas_tipo(tipo_solicitacao: str | None) -> int:
    if not tipo_solicitacao:
        return SLA_HORAS_PADRAO
    return SLA_HORAS_POR_TIPO.get(tipo_solicitacao, SLA_HORAS_PADRAO)


def label_tipo_solicitacao(tipo_solicitacao: str) -> str:
    for code, label in WorkOrder.TIPO_SOLICITACAO_CHOICES:
        if code == tipo_solicitacao:
            return label
    return tipo_solicitacao or 'Outros'


def sla_metas_resumo() -> list[dict[str, Any]]:
    return [
        {
            'tipo': tipo,
            'label': label_tipo_solicitacao(tipo),
            'sla_horas': sla_horas_tipo(tipo),
        }
        for tipo in TIPO_SLA_ORDEM
    ]


def metricas_decisao_tempos(tempos_com_tipo: list[tuple[float, str]]) -> dict[str, Any]:
    """
    Calcula tempo médio geral, % fora do SLA (por categoria) e detalhamento por tipo.
    tempos_com_tipo: lista de (horas, tipo_solicitacao).
    """
    if not tempos_com_tipo:
        return {
            'tempo_medio_horas': None,
            'pct_fora_sla': 0,
            'pct_acima_critico': 0,
            'risco_relativo': 0,
            'por_categoria': [],
        }

    n = len(tempos_com_tipo)
    tempo_medio = sum(t for t, _ in tempos_com_tipo) / n

    fora_sla = 0
    acima_critico = 0
    risco_soma = 0.0
    for tempo, tipo in tempos_com_tipo:
        sla = sla_horas_tipo(tipo)
        if tempo > sla:
            fora_sla += 1
        if tempo > sla * 1.5:
            acima_critico += 1
        risco_soma += min(1.0, tempo / sla)

    by_tipo: dict[str, list[float]] = defaultdict(list)
    for tempo, tipo in tempos_com_tipo:
        by_tipo[tipo or ''].append(tempo)

    por_categoria: list[dict[str, Any]] = []
    tipos_ordenados = [t for t in TIPO_SLA_ORDEM if t in by_tipo]
    tipos_ordenados.extend(sorted(t for t in by_tipo if t not in TIPO_SLA_ORDEM))

    for tipo in tipos_ordenados:
        temps = by_tipo[tipo]
        total = len(temps)
        media = sum(temps) / total
        sla = sla_horas_tipo(tipo)
        fora = sum(1 for t in temps if t > sla)
        por_categoria.append({
            'tipo': tipo,
            'label': label_tipo_solicitacao(tipo),
            'total_decisoes': total,
            'tempo_medio_horas': round(media, 2),
            'sla_horas': sla,
            'pct_fora_sla': round(fora / total * 100, 1) if total else 0,
            'dentro_sla': media <= sla,
        })

    return {
        'tempo_medio_horas': round(tempo_medio, 2),
        'pct_fora_sla': round(fora_sla / n * 100, 1),
        'pct_acima_critico': round(acima_critico / n * 100, 1),
        'risco_relativo': risco_soma / n,
        'por_categoria': por_categoria,
    }
