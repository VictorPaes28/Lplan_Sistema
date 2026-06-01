from __future__ import annotations

import json
import logging
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from django.conf import settings

logger = logging.getLogger(__name__)

_NOMINATIM_REVERSE = 'https://nominatim.openstreetmap.org/reverse'
_USER_AGENT = getattr(
    settings,
    'LPLAN_HTTP_USER_AGENT',
    'LplanCentral/1.0 (geolocation; contact@lplan.com.br)',
)


def google_maps_url(*, latitude: float, longitude: float) -> str:
    return f'https://www.google.com/maps?q={latitude},{longitude}'


def _format_nominatim_address(payload: dict[str, Any]) -> str:
    addr = payload.get('address')
    if not isinstance(addr, dict):
        return (payload.get('display_name') or '').strip()[:240]

    street_parts: list[str] = []
    road = (addr.get('road') or addr.get('pedestrian') or addr.get('footway') or '').strip()
    house = (addr.get('house_number') or '').strip()
    if road and house:
        street_parts.append(f'{road}, {house}')
    elif road:
        street_parts.append(road)

    area_keys = (
        'suburb',
        'neighbourhood',
        'city_district',
        'district',
        'city',
        'town',
        'village',
        'municipality',
    )
    area_parts: list[str] = []
    for key in area_keys:
        val = (addr.get(key) or '').strip()
        if val and val not in area_parts:
            area_parts.append(val)

    state = (addr.get('state') or '').strip()
    if state and state not in area_parts:
        area_parts.append(state)

    parts = street_parts + area_parts
    if parts:
        return ', '.join(parts[:6])[:240]
    return (payload.get('display_name') or '').strip()[:240]


def reverse_geocode(*, latitude: float, longitude: float) -> dict[str, str]:
    """
    Converte coordenadas em endereço legível (Nominatim / OpenStreetMap).
    Retorna dict vazio se o serviço estiver indisponível.
    """
    params = urllib.parse.urlencode(
        {
            'lat': f'{latitude:.6f}',
            'lon': f'{longitude:.6f}',
            'format': 'json',
            'addressdetails': '1',
            'zoom': '18',
        }
    )
    url = f'{_NOMINATIM_REVERSE}?{params}'
    req = urllib.request.Request(url, headers={'User-Agent': _USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            payload = json.loads(resp.read().decode('utf-8'))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, ValueError) as exc:
        logger.warning('reverse_geocode_failed lat=%s lon=%s err=%s', latitude, longitude, exc)
        return {}

    if not isinstance(payload, dict):
        return {}

    address = _format_nominatim_address(payload)
    if not address:
        return {'maps_url': google_maps_url(latitude=latitude, longitude=longitude)}

    return {
        'address': address,
        'maps_url': google_maps_url(latitude=latitude, longitude=longitude),
    }


def enrich_geolocation(geo: dict[str, Any]) -> dict[str, Any]:
    """Preenche endereço e link do Maps quando ainda não existirem."""
    if not geo:
        return geo
    lat = geo.get('latitude')
    lng = geo.get('longitude')
    if lat is None or lng is None:
        return geo
    try:
        lat_f = float(lat)
        lng_f = float(lng)
    except (TypeError, ValueError):
        return geo

    if not geo.get('maps_url'):
        geo['maps_url'] = google_maps_url(latitude=lat_f, longitude=lng_f)

    if (geo.get('address') or '').strip():
        return geo

    resolved = reverse_geocode(latitude=lat_f, longitude=lng_f)
    if resolved.get('address'):
        geo['address'] = resolved['address']
    if resolved.get('maps_url'):
        geo['maps_url'] = resolved['maps_url']
    return geo
