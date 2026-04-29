"""Apresentação humana de dados Sienge na Central (rótulos, ordem, valores) — sem credenciais."""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

# Ordem sugerida para leitura antes de assinar (chaves típicas da API pública).
_CONTRACT_FIRST_KEYS: Tuple[str, ...] = (
    'documentId',
    'contractNumber',
    'status',
    'statusApproval',
    'isAuthorized',
    'companyName',
    'companyId',
    'supplierName',
    'supplierId',
    'contractObject',
    'object',
    'description',
    'totalValue',
    'totalContractValue',
    'startDate',
    'contractStartDate',
    'endDate',
    'contractEndDate',
    'notes',
)
_MEASUREMENT_FIRST_KEYS: Tuple[str, ...] = (
    'documentId',
    'contractNumber',
    'buildingId',
    'buildingCode',
    'measurementNumber',
    'statusApproval',
    'authorized',
    'responsibleName',
    'responsibleId',
    'notes',
    'measurementDate',
    'totalValue',
)

_KEY_LABELS_PT: Dict[str, str] = {
    'documentId': 'Documento',
    'contractNumber': 'Nº contrato',
    'buildingId': 'Obra (ID Sienge)',
    'buildingCode': 'Código obra',
    'measurementNumber': 'Nº medição',
    'status': 'Situação contrato',
    'statusApproval': 'Situação aprovação',
    'isAuthorized': 'Autorizado (contrato)',
    'authorized': 'Autorizado (medição)',
    'companyName': 'Empresa',
    'companyId': 'Empresa (ID)',
    'supplierName': 'Fornecedor',
    'supplierId': 'Fornecedor (ID)',
    'contractObject': 'Objeto',
    'object': 'Objeto',
    'description': 'Descrição',
    'totalValue': 'Valor',
    'totalContractValue': 'Valor contrato',
    'startDate': 'Início',
    'contractStartDate': 'Início contrato',
    'endDate': 'Término',
    'contractEndDate': 'Término contrato',
    'notes': 'Observações',
    'responsibleName': 'Responsável',
    'responsibleId': 'Responsável (ID)',
    'measurementDate': 'Data medição',
}

_BOOL_FIELD_KEYS = frozenset({'isAuthorized', 'authorized'})

# Valores frequentes na API pública (normalmente em inglês / MAIÚSCULAS).
_STATUS_APPROVAL_PT: Dict[str, str] = {
    'DISAPPROVED': 'Não aprovado',
    'APPROVED': 'Aprovado',
    'PENDING': 'Pendente',
    'WAITING': 'Em espera',
    'DRAFT': 'Rascunho',
    'REJECTED': 'Rejeitado',
    'CANCELLED': 'Cancelado',
    'IN_ANALYSIS': 'Em análise',
    'UNDER_ANALYSIS': 'Em análise',
    'APPROVED_WITH_RESERVATIONS': 'Aprovado com ressalvas',
}

_CONTRACT_STATUS_PT: Dict[str, str] = {
    'PENDING': 'Pendente',
    'ACTIVE': 'Ativo',
    'CLOSED': 'Encerrado',
    'CANCELLED': 'Cancelado',
    'DRAFT': 'Rascunho',
    'EXPIRED': 'Expirado',
    'SUSPENDED': 'Suspenso',
}


def _label_for_key(key: str) -> str:
    if key in _KEY_LABELS_PT:
        return _KEY_LABELS_PT[key]
    out: list[str] = []
    buf = ''
    for ch in key:
        if ch.isupper() and buf:
            out.append(buf.lower())
            buf = ch.lower()
        else:
            buf += ch
    if buf:
        out.append(buf)
    return ' '.join(out).strip() or key


def _bool_from_value(value: Any) -> Optional[bool]:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)) and value in (0, 1):
        return bool(value)
    if isinstance(value, str):
        s = value.strip().lower()
        if s in ('true', 't', 'yes', 'y', 'sim', 's', '1'):
            return True
        if s in ('false', 'f', 'no', 'n', 'nao', 'não', '0'):
            return False
    return None


def humanize_sienge_field_value(field_key: Optional[str], value: Any) -> str:
    """
    Converte valores crus da API para texto legível em português (resumo, tabela, PDFs futuros).

    ``field_key`` None: devolve o valor como texto (ex.: linha composta documento+contrato).
    """
    if value is None:
        return ''
    if isinstance(value, str) and not value.strip():
        return ''
    if field_key is None:
        return str(value).strip()

    if field_key in _BOOL_FIELD_KEYS:
        b = _bool_from_value(value)
        if b is not None:
            return 'Sim' if b else 'Não'

    if isinstance(value, bool):
        return 'Sim' if value else 'Não'

    if not isinstance(value, str):
        return str(value).strip()

    raw = value.strip()
    upper = raw.upper()

    if field_key == 'statusApproval':
        return _STATUS_APPROVAL_PT.get(upper, raw)
    if field_key == 'status':
        return _CONTRACT_STATUS_PT.get(upper, raw)

    return raw


def _fmt_field(key: str, v: Any) -> str:
    if v is None:
        return ''
    if isinstance(v, (dict, list)):
        s = str(v)
        if len(s) > 500:
            return s[:497] + '…'
        return s
    return humanize_sienge_field_value(key, v)


def sienge_payload_display_rows(
    payload: Dict[str, Any] | None,
    *,
    external_entity_type: str,
    max_rows: int = 36,
) -> List[Dict[str, str]]:
    """
    Lista de {label, value} para tabela legível (snapshot ``external_payload``).
    """
    if not payload or not isinstance(payload, dict):
        return []
    first = _MEASUREMENT_FIRST_KEYS if 'measurement' in external_entity_type else _CONTRACT_FIRST_KEYS
    used: set[str] = set()
    rows: List[Dict[str, str]] = []
    for k in first:
        if k not in payload:
            continue
        val = _fmt_field(k, payload.get(k))
        if not val:
            continue
        rows.append({'key': k, 'label': _label_for_key(k), 'value': val})
        used.add(k)
        if len(rows) >= max_rows:
            return rows
    for k, v in payload.items():
        if k in used or not isinstance(k, str):
            continue
        val = _fmt_field(k, v)
        if not val:
            continue
        rows.append({'key': k, 'label': _label_for_key(k), 'value': val})
        if len(rows) >= max_rows:
            break
    return rows


# Chaves técnicas gravadas no ``summary`` em versões antigas (cópia literal do Sienge).
_LEGACY_SUMMARY_EN_KEYS: Dict[str, str] = {
    'status': 'status',
    'statusApproval': 'statusApproval',
    'isAuthorized': 'isAuthorized',
    'authorized': 'authorized',
    'buildingId': 'buildingId',
    'measurementNumber': 'measurementNumber',
}
# Títulos já em português no resumo; só reformatamos o valor se ainda for código de API.
_PT_LINE_VALUE_RESUGGEST: Dict[str, str] = {
    'Autorização (campo)': 'statusApproval',
    'Situação': 'status',
    'Autorizado no Sienge': 'isAuthorized',
    'Autorizado': 'authorized',
    'Obra Sienge (buildingId)': 'buildingId',
    'Nº medição': 'measurementNumber',
    'Situação aprovação': 'statusApproval',
}


def _coerce_stored_value_for_field(field_key: str, raw: str) -> Any:
    t = (raw or '').strip()
    if t == '':
        return ''
    if field_key in _BOOL_FIELD_KEYS:
        b = _bool_from_value(t)
        if b is not None:
            return b
    if field_key in ('buildingId', 'measurementNumber'):
        if t.isdigit() or (t.startswith('-') and t[1:].isdigit()):
            return int(t)
    return t


def _value_still_looks_api_like(val: str) -> bool:
    t = (val or '').strip()
    if not t or len(t) > 64:
        return False
    if t.lower() in ('true', 'false'):
        return True
    if t in ('True', 'False'):
        return True
    u = t.upper()
    if u in _STATUS_APPROVAL_PT or u in _CONTRACT_STATUS_PT:
        return True
    if all(c.isupper() or c == '_' for c in t) and t.replace('_', '').isalnum() and len(t) >= 2:
        return True
    return False


def beautify_stored_summary_for_display(text: str) -> str:
    """
    Reescreve o ``ApprovalProcess.summary`` (texto multilinha) para o utilizador:
    chaves técnicas ``status:`` / ``statusApproval:`` → rótulos em português e valores legíveis.

    Não mexe em linhas já amigáveis (ex. ``Empresa: Nome Lda.``). Idempotente na prática.
    """
    if not (text and text.strip()):
        return (text or '').strip()
    out: List[str] = []
    for line in text.splitlines():
        t = line.strip()
        if not t or ':' not in t:
            out.append(t)
            continue
        left, _, right = t.partition(':')
        key_l = left.strip()
        val_r = right.strip()
        field = _LEGACY_SUMMARY_EN_KEYS.get(key_l)
        if field is not None and val_r != '':
            c = _coerce_stored_value_for_field(field, val_r)
            label = _KEY_LABELS_PT.get(field, key_l)
            out.append(f'{label}: {humanize_sienge_field_value(field, c)}')
            continue
        pfield = _PT_LINE_VALUE_RESUGGEST.get(key_l)
        if pfield is not None and val_r and _value_still_looks_api_like(val_r):
            c = _coerce_stored_value_for_field(pfield, val_r)
            out.append(f'{key_l}: {humanize_sienge_field_value(pfield, c)}')
        else:
            out.append(t)
    return '\n'.join(out)
