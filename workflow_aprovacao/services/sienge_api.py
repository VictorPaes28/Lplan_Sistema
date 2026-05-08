"""
Cliente HTTP mínimo para a Central de Aprovações falar com o Sienge.

Não reutiliza suprimentos/mapa: só credenciais e URL já definidas em settings.
"""
from __future__ import annotations

import base64
from typing import Any, Dict, Iterator, List, Optional, Tuple

import requests
from django.conf import settings

# Chaves comuns em respostas diferentes da API Sienge para o mesmo conceito.
_ATTACHMENT_ID_KEYS: Tuple[str, ...] = (
    'attachmentId',
    'contractAttachmentNumber',
    'id',
    'attachmentNumber',
    'attachmentSeqId',
    'sequence',
    'seq',
    'fileId',
    'supplyContractAttachmentId',
    'attachmentID',
)
_ATTACHMENT_NAME_KEYS: Tuple[str, ...] = (
    'fileName',
    'name',
    'file_name',
    'originalFilename',
    'originalFileName',
    'title',
    'description',
    'fileDescription',
)


def _safe_int(v: Any) -> Optional[int]:
    if v is None or v is False:
        return None
    if isinstance(v, bool):
        return int(v)
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def normalize_supply_contract_attachment_row(raw: Dict[str, Any]) -> Dict[str, Any]:
    """
    Metadado de anexo num formato estável para templates e validação de download.

    Retorna: attachment_id (int|None), file_name (str), raw (cópia superficial).
    """
    aid: Optional[int] = None
    for k in _ATTACHMENT_ID_KEYS:
        if k in raw:
            aid = _safe_int(raw.get(k))
            if aid is not None:
                break
    fname = ''
    for k in _ATTACHMENT_NAME_KEYS:
        val = raw.get(k)
        if val is not None and str(val).strip():
            fname = str(val).strip()[:240]
            break
    default_name = f'Anexo #{aid}' if aid is not None else 'Anexo'
    display_name = fname or default_name
    out: Dict[str, Any] = {
        'attachment_id': aid,
        'file_name': display_name,
        'fileName': display_name,
        'raw': dict(raw),
    }
    # Compat: templates antigos usavam ``att.attachmentId|default:att.id`` (o ``id`` da API
    # pode não existir — o Django resolve ambos os ramos e quebrava com VariableDoesNotExist).
    if aid is not None:
        out['attachmentId'] = aid
        out['id'] = aid
    return out


def attachment_id_from_normalized_row(row: Dict[str, Any]) -> Optional[int]:
    """Resolve o ID numérico para download a partir de uma linha de ``normalize_supply_contract_attachment_row``."""
    got = _safe_int(row.get('attachment_id'))
    if got is not None:
        return got
    raw = row.get('raw')
    if isinstance(raw, dict):
        for k in _ATTACHMENT_ID_KEYS:
            got = _safe_int(raw.get(k))
            if got is not None:
                return got
    return None


def _flatten_attachment_dicts(data: Any, *, _depth: int = 0) -> List[dict]:
    """Extrai lista de dicts de vários formatos de envelope JSON (até profundidade limitada)."""
    if _depth > 5 or data is None:
        return []
    if isinstance(data, list):
        return [x for x in data if isinstance(x, dict)]
    if not isinstance(data, dict):
        return []
    out: List[dict] = []
    for key in ('results', 'data', 'attachments', 'items', 'content', 'rows', 'values'):
        inner = data.get(key)
        if isinstance(inner, list):
            for x in inner:
                if isinstance(x, dict):
                    out.append(x)
            if out:
                return out
        if isinstance(inner, dict):
            nested = _flatten_attachment_dicts(inner, _depth=_depth + 1)
            if nested:
                return nested
    return []


def _http_response_looks_like_file(r: requests.Response) -> bool:
    if r.status_code != 200:
        return False
    ct = (r.headers.get('content-type') or '').lower().split(';')[0].strip()
    if 'json' in ct:
        return False
    raw = r.content[:512] if r.content else b''
    if raw.startswith(b'{') or raw.startswith(b'['):
        return False
    return True


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

    def iter_supply_contract_measurements_full_scan(
        self,
        *,
        page_size: int = 50,
        max_total_rows: Optional[int] = None,
    ) -> Iterator[dict]:
        """GET /v1/supply-contracts/measurements/all até esgotar (ou ``max_total_rows``)."""
        offset = 0
        yielded = 0
        while max_total_rows is None or yielded < max_total_rows:
            limit = page_size
            if max_total_rows is not None:
                limit = min(page_size, max_total_rows - yielded)
            if limit <= 0:
                break
            rows = self.fetch_measurements_all_page(limit=limit, offset=offset)
            if not rows:
                break
            for row in rows:
                yield row
                yielded += 1
                if max_total_rows is not None and yielded >= max_total_rows:
                    return
            offset += len(rows)
            if len(rows) < limit:
                break

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

    def fetch_supply_contract_buildings(self, *, document_id: str, contract_number: str) -> List[dict]:
        """
        Obras ligadas ao contrato (códigos reais da obra costumam vir aqui, não em ``contractNumber``).

        GET /v1/supply-contracts/buildings?documentId=&contractNumber=
        """
        doc = (document_id or '').strip()
        num = str(contract_number).strip() if contract_number is not None else ''
        if not doc or not num:
            return []
        try:
            data = self.get_json(
                '/v1/supply-contracts/buildings',
                {'documentId': doc, 'contractNumber': num},
            )
        except Exception:
            return []
        rows = data.get('results')
        if isinstance(rows, list):
            return [r for r in rows if isinstance(r, dict)]
        if isinstance(data, list):
            return [r for r in data if isinstance(r, dict)]
        return []

    def fetch_supply_contract_attachments_index(
        self, *, document_id: str, contract_number: str
    ) -> List[dict]:
        """GET /v1/supply-contracts/attachments/all — metadados de anexos do contrato."""
        doc = (document_id or '').strip()
        num = str(contract_number).strip() if contract_number is not None else ''
        if not doc or not num:
            return []
        try:
            data = self.get_json(
                '/v1/supply-contracts/attachments/all',
                {'documentId': doc, 'contractNumber': num},
            )
        except Exception:
            return []
        rows = _flatten_attachment_dicts(data)
        if not rows and isinstance(data, dict):

            def _looks_attachment(d: dict) -> bool:
                return any(k in d for k in _ATTACHMENT_ID_KEYS)

            rows = [r for r in data.values() if isinstance(r, dict) and _looks_attachment(r)]
        return [normalize_supply_contract_attachment_row(r) for r in rows if isinstance(r, dict)]

    def download_supply_contract_attachment(
        self,
        *,
        document_id: str,
        contract_number: str,
        attachment_id: Optional[int] = None,
        max_bytes: int = 15 * 1024 * 1024,
    ) -> tuple[bytes, str, str]:
        """
        GET /v1/supply-contracts/attachments — ficheiro binário (PDF, etc.).

        Retorna (content, content_type, filename_sugerido).
        """
        doc = (document_id or '').strip()
        num = str(contract_number).strip() if contract_number is not None else ''
        if not doc or not num:
            raise ValueError('documentId e contractNumber são obrigatórios.')
        base: Dict[str, Any] = {'documentId': doc, 'contractNumber': num}
        r: requests.Response | None = None
        if attachment_id is None:
            r = self.get_http_response('/v1/supply-contracts/attachments', base)
        else:
            aid = int(attachment_id)
            for extra in (
                {'attachmentId': aid},
                {'contractAttachmentNumber': aid},
                {'id': aid},
                {'attachmentNumber': aid},
                {'attachmentSeqId': aid},
            ):
                rr = self.get_http_response('/v1/supply-contracts/attachments', {**base, **extra})
                if rr.status_code == 200 and _http_response_looks_like_file(rr):
                    r = rr
                    break
            if r is None:
                rr = self.get_http_response(
                    '/v1/supply-contracts/attachments', {**base, 'attachmentId': aid}
                )
                if rr.status_code == 200:
                    r = rr
        if r is None or r.status_code != 200:
            code = r.status_code if r is not None else '—'
            raise RuntimeError(f'Sienge attachments HTTP {code}')
        if not _http_response_looks_like_file(r):
            raise RuntimeError('Sienge devolveu JSON ou corpo inválido em vez do ficheiro.')
        raw = r.content or b''
        if len(raw) > max_bytes:
            raise RuntimeError('Anexo excede o limite de tamanho permitido.')
        ctype = (r.headers.get('content-type') or 'application/octet-stream').split(';')[0].strip()
        fname = 'sienge_anexo'
        cd = r.headers.get('Content-Disposition') or ''
        if 'filename=' in cd:
            part = cd.split('filename=')[-1].strip().strip('"').split(';')[0].strip()
            if part:
                fname = part[:200]
        return raw, ctype, fname

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

    def iter_supply_contracts_full_scan(
        self,
        *,
        page_size: int = 50,
        max_total_rows: Optional[int] = None,
    ) -> Iterator[dict]:
        """
        Percorre GET /v1/supply-contracts/all até a API não devolver mais linhas.

        ``max_total_rows`` (opcional) corta após N linhas (proteção em ambientes enormes).
        """
        offset = 0
        yielded = 0
        while max_total_rows is None or yielded < max_total_rows:
            limit = page_size
            if max_total_rows is not None:
                limit = min(page_size, max_total_rows - yielded)
            if limit <= 0:
                break
            rows = self.fetch_supply_contracts_all_page(limit=limit, offset=offset)
            if not rows:
                break
            for row in rows:
                yield row
                yielded += 1
                if max_total_rows is not None and yielded >= max_total_rows:
                    return
            offset += len(rows)
            if len(rows) < limit:
                break
