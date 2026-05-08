"""Filtros para exibir resumos Sienge com texto legível na fila e noutros templates."""
from __future__ import annotations

from django import template

from workflow_aprovacao.services.sienge_display import beautify_stored_summary_for_display

register = template.Library()

_SIENGE_TYPES = frozenset({'sienge_supply_contract', 'sienge_supply_contract_measurement'})


@register.filter
def resumo_sienge_legivel(process) -> str:
    """
    Converte o ``summary`` com chaves técnicas (``status:``) para o mesmo texto
    usado no detalhe do processo. Processos não-Sienge: devolve o resumo inalterado.
    """
    if not process or not getattr(process, 'summary', None):
        return ''
    s = str(process.summary).strip()
    if not s:
        return ''
    et = getattr(process, 'external_entity_type', None) or ''
    if et in _SIENGE_TYPES:
        return beautify_stored_summary_for_display(s)
    return s
