from __future__ import annotations

from django import template

from workflow_aprovacao.services.signing import history_geolocation_display, history_geolocation_label

register = template.Library()


@register.filter
def history_geo_label(entry) -> str:
    """Rótulo de localização registrado na evidência de assinatura do evento."""
    if not entry:
        return ''
    return history_geolocation_label(entry)


@register.filter
def history_geo_display(entry) -> dict:
    """Endereço, coordenadas e link do Maps para exibição na linha do tempo."""
    if not entry:
        return {}
    return history_geolocation_display(entry)
