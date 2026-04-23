"""
Cliente HTTP mínimo para a Central de Aprovações falar com o Sienge.

Não reutiliza suprimentos/mapa: só credenciais e URL já definidas em settings.
"""
from __future__ import annotations

import base64
from typing import Any, Dict, Iterator, List, Optional

import requests
from django.conf import settings


class SiengeCentralApiClient:
    """GET JSON na API pública Sienge (Basic Auth)."""

    def __init__(
        self,
        *,
        base_url: str = '',
        client_id: str = '',
        client_secret: str = '',
        username: str = '',
        password: str = '',
        auth_mode: str = '',
    ):
        self.base_url = (base_url or getattr(settings, 'SIENGE_API_BASE_URL', '') or '').rstrip('/')
        self.client_id = (client_id or getattr(settings, 'SIENGE_API_CLIENT_ID', '') or '').strip()
        self.client_secret = (client_secret or getattr(settings, 'SIENGE_API_CLIENT_SECRET', '') or '').strip()
        self.username = (username or getattr(settings, 'SIENGE_API_USERNAME', '') or '').strip()
        self.password = (password or getattr(settings, 'SIENGE_API_PASSWORD', '') or '').strip()
        self.auth_mode = (auth_mode or getattr(settings, 'SIENGE_API_AUTH_MODE', 'basic') or 'basic').strip().lower()

    def _basic_pair(self) -> tuple[str, str]:
        user = self.username or self.client_id
        pwd = self.password or self.client_secret
        return user, pwd

    def _headers(self) -> dict[str, str]:
        user, pwd = self._basic_pair()
        if not user or not pwd:
            raise RuntimeError(
                'Credenciais Sienge ausentes: defina SIENGE_API_CLIENT_ID/SECRET '
                'ou SIENGE_API_USERNAME/PASSWORD no .env.'
            )
        token = base64.b64encode(f'{user}:{pwd}'.encode('utf-8')).decode('ascii')
        return {
            'Authorization': f'Basic {token}',
            'Accept': 'application/json',
        }

    def _join_url(self, path: str) -> str:
        base = self.base_url.rstrip('/')
        if not path.startswith('/'):
            path = '/' + path
        if base.endswith('/public/api') and path.startswith('/public/api'):
            path = path[len('/public/api') :] or '/'
            if not path.startswith('/'):
                path = '/' + path
        if base.endswith('/public/api') and path.startswith('/api/v1'):
            path = '/v1' + path[len('/api/v1') :]
        return base + path

    def get_http_response(self, path: str, params: Optional[Dict[str, Any]] = None):
        """GET sem raise automático (para scripts de diagnóstico)."""
        if not self.base_url:
            raise RuntimeError('SIENGE_API_BASE_URL vazio.')
        url = self._join_url(path)
        return requests.get(url, headers=self._headers(), params=params or {}, timeout=40)

    def get_json(self, path: str, params: Optional[Dict[str, Any]] = None) -> dict:
        if not self.base_url:
            raise RuntimeError('SIENGE_API_BASE_URL vazio.')
        r = self.get_http_response(path, params)
        r.raise_for_status()
        return r.json()

    def fetch_measurements_all_page(self, *, limit: int = 25, offset: int = 0) -> List[dict]:
        data = self.get_json(
            '/v1/supply-contracts/measurements/all',
            {'limit': limit, 'offset': offset},
        )
        rows = data.get('results')
        if not isinstance(rows, list):
            return []
        return rows

    def iter_supply_contract_measurements(self, *, page_size: int = 25, max_rows: int = 100) -> Iterator[dict]:
        offset = 0
        while offset < max_rows:
            chunk = min(page_size, max_rows - offset)
            rows = self.fetch_measurements_all_page(limit=chunk, offset=offset)
            if not rows:
                break
            for row in rows:
                yield row
            if len(rows) < chunk:
                break
            offset += len(rows)

    def fetch_supply_contracts_all_page(self, *, limit: int = 25, offset: int = 0) -> List[dict]:
        """Lista contratos de suprimentos (Sienge)."""
        data = self.get_json(
            '/v1/supply-contracts/all',
            {'limit': limit, 'offset': offset},
        )
        rows = data.get('results')
        if not isinstance(rows, list):
            return []
        return rows

    def iter_supply_contracts_all(self, *, page_size: int = 25, max_rows: int = 100) -> Iterator[dict]:
        offset = 0
        while offset < max_rows:
            chunk = min(page_size, max_rows - offset)
            rows = self.fetch_supply_contracts_all_page(limit=chunk, offset=offset)
            if not rows:
                break
            for row in rows:
                yield row
            if len(rows) < chunk:
                break
            offset += len(rows)
