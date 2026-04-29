"""
Ingestão Sienge → Central de Aprovações (fase 1: só receber dados).

Escopo explícito: contratos de suprimentos e medições de contrato (supply-contracts).
Não usa pedidos de compra (PC), solicitações de compra (SC), notas fiscais de compra,
nem mapa de suprimentos — só o que alimenta aprovação de contrato/medición na Central.

Fontes na API pública Sienge (contrato de suprimentos):
  - GET /v1/supply-contracts/all → categoria ``contrato``
  - GET /v1/supply-contracts/measurements/all → categoria ``medicao``.

A categoria das medições segue ``SIENGE_CENTRAL_MEASUREMENT_CATEGORY_CODE`` (por defeito ``medicao``).

Resolução de obra (chaves já existentes no Lplan):

  - Primeiro: ``contractNumber`` da linha (lista ``/all`` ou medições) casado com o índice
    ``Project`` / obras Gestão / Mapa (``code``, ``contract_number``, ``sienge_codigos_alternativos``,
    ``codigo_sienge``, alternativos).
  - Depois: campos de obra na própria linha (ex.: ``buildingCode``) se existirem.
  - Por fim: ``GET /v1/supply-contracts/buildings`` (documentId + contractNumber) — o **número do
    contrato** no Sienge costuma ser diferente do **código da obra**; as obras do contrato trazem
    os códigos que batem com o cadastro (ex. 224, 260).

Não cria obras; só associa a ``Project`` já existente.
"""
from __future__ import annotations

import re
from typing import Any, Dict, Optional, TYPE_CHECKING

from django.conf import settings

from core.models import Project
from workflow_aprovacao.exceptions import NoFlowConfigurationError, UnsupportedPolicyError
from workflow_aprovacao.models import (
    ApprovalConfigBlockReason,
    ApprovalProcess,
    ProcessCategory,
    SyncStatus,
)
from workflow_aprovacao.services.backlog import upsert_inbound_backlog
from workflow_aprovacao.services.engine import ApprovalEngine
from workflow_aprovacao.services.sienge_display import humanize_sienge_field_value

if TYPE_CHECKING:
    from django.contrib.auth.models import AbstractUser

    from workflow_aprovacao.services.sienge_api import SiengeCentralApiClient

CENTRAL_CATEGORY_CODES = frozenset({'contrato', 'medicao'})

# Campos permitidos no snapshot JSON do processo (evita gravar segredos ou blobs).
_SIENGE_SNAPSHOT_KEY_DENY = frozenset(
    {'password', 'token', 'secret', 'authorization', 'credential', 'bearer'}
)


def sienge_row_public_snapshot(row: Optional[Dict[str, Any]], *, max_keys: int = 48) -> Dict[str, Any]:
    """Subconjunto do payload Sienge seguro para ``ApprovalProcess.external_payload``."""
    if not row or not isinstance(row, dict):
        return {}
    out: Dict[str, Any] = {}
    for k, v in row.items():
        if not isinstance(k, str) or k.startswith('_'):
            continue
        lk = k.lower()
        if any(d in lk for d in _SIENGE_SNAPSHOT_KEY_DENY):
            continue
        if v is None or v == '':
            continue
        if isinstance(v, (dict, list)) and len(str(v)) > 4000:
            continue
        out[k] = v
        if len(out) >= max_keys:
            break
    return out


def _human_contract_lines(row: Dict[str, Any]) -> list[str]:
    lines: list[str] = []
    specs: list[tuple[str | None, str, Any]] = [
        (None, 'Documento / contrato', f"{row.get('documentId', '')} {row.get('contractNumber', '')}".strip()),
        ('status', 'Situação', row.get('status')),
        ('statusApproval', 'Autorização (campo)', row.get('statusApproval')),
        ('isAuthorized', 'Autorizado no Sienge', row.get('isAuthorized')),
        ('companyName', 'Empresa', row.get('companyName') or row.get('companyId')),
        ('supplierName', 'Fornecedor', row.get('supplierName') or row.get('supplierId')),
        ('contractObject', 'Objeto', row.get('contractObject') or row.get('object') or row.get('description')),
        ('notes', 'Observações', row.get('notes')),
        ('startDate', 'Início', row.get('startDate') or row.get('contractStartDate')),
        ('endDate', 'Término', row.get('endDate') or row.get('contractEndDate')),
        ('totalValue', 'Valor', row.get('totalValue') or row.get('totalContractValue')),
    ]
    for field_key, label, raw in specs:
        if raw is None or (isinstance(raw, str) and not raw.strip()):
            continue
        display = humanize_sienge_field_value(field_key, raw)
        if display:
            lines.append(f'{label}: {display}')
    return lines


def _human_measurement_lines(row: Dict[str, Any]) -> list[str]:
    lines: list[str] = []
    specs: list[tuple[str | None, str, Any]] = [
        (None, 'Documento / contrato', f"{row.get('documentId', '')} {row.get('contractNumber', '')}".strip()),
        ('buildingId', 'Obra Sienge (buildingId)', row.get('buildingId')),
        ('measurementNumber', 'Nº medição', row.get('measurementNumber')),
        ('statusApproval', 'Situação aprovação', row.get('statusApproval')),
        ('authorized', 'Autorizado', row.get('authorized')),
        ('responsibleName', 'Responsável', row.get('responsibleName') or row.get('responsibleId')),
        ('notes', 'Observações', row.get('notes')),
    ]
    for field_key, label, raw in specs:
        if raw is None or (isinstance(raw, str) and not raw.strip()):
            continue
        display = humanize_sienge_field_value(field_key, raw)
        if display:
            lines.append(f'{label}: {display}')
    return lines


def measurement_external_id(row: Dict[str, Any]) -> str:
    parts = [
        str(row.get('documentId', '')).strip(),
        str(row.get('contractNumber', '')).strip(),
        str(row.get('buildingId', '')).strip(),
        str(row.get('measurementNumber', '')).strip(),
    ]
    return 'm|' + '|'.join(parts)


def contract_external_id(row: Dict[str, Any]) -> str:
    parts = [
        str(row.get('documentId', '')).strip(),
        str(row.get('contractNumber', '')).strip(),
    ]
    return 'c|' + '|'.join(parts)


def _tokenize_codigos_field(raw: str) -> set[str]:
    out: set[str] = set()
    for part in re.split(r'[\s,;\n]+', (raw or '').strip()):
        t = part.strip().lower()
        if t:
            out.add(t)
    return out


def build_sienge_project_lookup() -> Dict[str, Project]:
    """
    Índice ``contractNumber`` Sienge (normalizado minúsculas) → ``Project``.

    Usa obras já registadas (Project + Gestão + Mapa), sem criar nada novo.
    """
    lookup: Dict[str, Project] = {}
    for p in Project.objects.filter(is_active=True).only(
        'id', 'code', 'contract_number', 'sienge_codigos_alternativos'
    ):
        keys: set[str] = set()
        if p.contract_number:
            keys.add(str(p.contract_number).strip().lower())
        if p.code:
            keys.add(str(p.code).strip().lower())
        keys |= _tokenize_codigos_field(getattr(p, 'sienge_codigos_alternativos', '') or '')
        for k in keys:
            lookup[k] = p

    try:
        from gestao_aprovacao.models import Obra

        for obra in Obra.objects.filter(project__isnull=False).select_related('project'):
            c = (obra.codigo or '').strip().lower()
            if c and obra.project_id:
                lookup[c] = obra.project
    except Exception:
        pass

    try:
        from mapa_obras.models import Obra as ObraMapa

        for mo in ObraMapa.objects.filter(project__isnull=False, ativa=True).select_related('project'):
            for k in mo.chaves_sienge_busca_importacao():
                t = str(k).strip().lower()
                if t:
                    lookup[t] = mo.project
    except Exception:
        pass

    return lookup


def _lookup_sienge_key(lookup: Dict[str, Project], raw: Any) -> Optional[Project]:
    """Casa uma string ou número Sienge com o índice (minúsculas + variantes numéricas)."""
    if raw is None:
        return None
    s = str(raw).strip()
    if not s:
        return None
    candidates = [s.lower()]
    if s.isdigit():
        n = str(int(s))
        candidates.extend([n, n.zfill(4), n.zfill(5)])
    for c in candidates:
        p = lookup.get(c.lower())
        if p:
            return p
    return None


def _candidate_strings_from_building_dict(b: Dict[str, Any]) -> list[str]:
    out: list[str] = []
    for key in (
        'code',
        'buildingCode',
        'constructionWorkCode',
        'workCode',
        'buildingSiteCode',
        'installationCode',
        'buildingId',
        'id',
    ):
        v = b.get(key)
        if v is None or v == '':
            continue
        s = str(v).strip()
        if s:
            out.append(s)
    return out


def resolve_project_for_sienge_row(
    row: Dict[str, Any],
    lookup: Optional[Dict[str, Project]] = None,
    client: Optional['SiengeCentralApiClient'] = None,
) -> Optional[Project]:
    """
    Resolve ``Project`` a partir de uma linha Sienge (contrato ou medição).

    ``client`` opcional: se a linha só tiver ``contractNumber`` de contrato, tenta-se
    ``/supply-contracts/buildings`` para obter códigos de obra.
    """
    if lookup is None:
        lookup = build_sienge_project_lookup()

    cn = str(row.get('contractNumber', '')).strip()
    if not cn:
        return None

    p = _lookup_sienge_key(lookup, cn)
    if p:
        return p

    for fld in ('buildingCode', 'constructionWorkCode', 'workCode', 'buildingSiteCode'):
        p = _lookup_sienge_key(lookup, row.get(fld))
        if p:
            return p

    p = _lookup_sienge_key(lookup, row.get('buildingId'))
    if p:
        return p

    buildings_inline = row.get('buildings')
    if isinstance(buildings_inline, list):
        bid = row.get('buildingId')

        def _prio(b: Any) -> tuple:
            if not isinstance(b, dict):
                return (2, 0)
            if bid is None:
                return (1, 0)
            return (0 if str(b.get('buildingId')) == str(bid) else 1, 0)

        for b in sorted(buildings_inline, key=_prio):
            if isinstance(b, dict):
                for s in _candidate_strings_from_building_dict(b):
                    p = _lookup_sienge_key(lookup, s)
                    if p:
                        return p

    doc = str(row.get('documentId', '') or '').strip()
    if client and doc:
        try:
            rows_b = client.fetch_supply_contract_buildings(document_id=doc, contract_number=cn)
        except Exception:
            rows_b = []
        bid = row.get('buildingId')

        def _prio_api(b: Any) -> tuple:
            if not isinstance(b, dict):
                return (2, 0)
            if bid is None:
                return (1, 0)
            return (0 if str(b.get('buildingId')) == str(bid) else 1, 0)

        for b in sorted(rows_b, key=_prio_api):
            for s in _candidate_strings_from_building_dict(b):
                p = _lookup_sienge_key(lookup, s)
                if p:
                    return p

    p = Project.objects.filter(contract_number=cn).first()
    if p:
        return p
    return Project.objects.filter(contract_number__iexact=cn).first()


def measurement_pending_sienge_authorization(row: Dict[str, Any]) -> bool:
    """
    Pendente no Sienge = ainda não autorizado.

    Não exige escolha manual: percorremos a API e importamos tudo onde ``authorized``
    não é explicitamente ``True`` (inclui ``False`` e omissão, conforme payload).
    """
    return row.get('authorized') is not True


def contract_pending_sienge_authorization(row: Dict[str, Any]) -> bool:
    """Pendente = contrato ainda não autorizado (``isAuthorized`` não é ``True``)."""
    return row.get('isAuthorized') is not True


def _category_or_raise(code: str) -> ProcessCategory:
    c = ProcessCategory.objects.filter(code=code, is_active=True).first()
    if not c:
        raise RuntimeError(f'Categoria de processo {code!r} inexistente ou inativa.')
    return c


def _cap_max_rows(max_rows: Optional[int]) -> int:
    cap = max_rows
    if cap is None:
        cap = int(getattr(settings, 'SIENGE_CENTRAL_SYNC_MAX_ROWS', 2000) or 2000)
    return max(1, min(int(cap), 5000))


def _empty_stats() -> Dict[str, int]:
    return {
        'examined': 0,
        'would_create': 0,
        'created': 0,
        'skipped_not_pending': 0,
        'skipped_no_project': 0,
        'skipped_duplicate': 0,
        'errors_no_flow': 0,
        'errors_other': 0,
    }


def _try_create(
    *,
    project: Project,
    category: ProcessCategory,
    title: str,
    summary: str,
    external_id: str,
    entity_type: str,
    initiated_by: Optional['AbstractUser'],
    dry_run: bool,
    stats: Dict[str, int],
    source_row: Optional[Dict[str, Any]] = None,
) -> None:
    if ApprovalProcess.objects.filter(external_system='sienge', external_id=external_id).exists():
        stats['skipped_duplicate'] += 1
        return
    if dry_run:
        stats['would_create'] += 1
        return
    try:
        snap = sienge_row_public_snapshot(source_row or {})
        ApprovalEngine.start(
            project=project,
            category=category,
            initiated_by=initiated_by,
            title=title[:300],
            summary=summary[:2000],
            external_id=external_id,
            external_entity_type=entity_type,
            sync_status=SyncStatus.NOT_APPLICABLE,
            external_payload=snap,
        )
        stats['created'] += 1
    except NoFlowConfigurationError as exc:
        stats['errors_no_flow'] += 1
        upsert_inbound_backlog(
            project=project,
            category=category,
            external_system='sienge',
            external_id=external_id,
            external_entity_type=entity_type,
            title=title,
            summary=summary,
            source_payload=source_row,
            block_reason=ApprovalConfigBlockReason.NO_FLOW,
            last_error_message=str(exc),
        )
    except UnsupportedPolicyError as exc:
        stats['errors_other'] += 1
        upsert_inbound_backlog(
            project=project,
            category=category,
            external_system='sienge',
            external_id=external_id,
            external_entity_type=entity_type,
            title=title,
            summary=summary,
            source_payload=source_row,
            block_reason=ApprovalConfigBlockReason.UNSUPPORTED_POLICY,
            last_error_message=str(exc),
        )
    except Exception:
        stats['errors_other'] += 1


def sync_sienge_contracts_to_central(
    *,
    client: Optional['SiengeCentralApiClient'] = None,
    initiated_by: Optional['AbstractUser'] = None,
    max_rows: Optional[int] = None,
    any_status: bool = False,
    dry_run: bool = False,
) -> Dict[str, int]:
    """Contratos de suprimentos (lista ``/all``) → categoria ``contrato``."""
    from workflow_aprovacao.services.sienge_api import SiengeCentralApiClient

    api = client or SiengeCentralApiClient()
    category = _category_or_raise('contrato')
    stats = _empty_stats()
    cap = _cap_max_rows(max_rows)
    lookup = build_sienge_project_lookup()

    for row in api.iter_supply_contracts_all(page_size=25, max_rows=cap):
        stats['examined'] += 1
        if not any_status and not contract_pending_sienge_authorization(row):
            stats['skipped_not_pending'] += 1
            continue
        ext_id = contract_external_id(row)
        if len(ext_id) <= 2:
            stats['skipped_not_pending'] += 1
            continue

        project = resolve_project_for_sienge_row(row, lookup, client=api)
        if not project:
            stats['skipped_no_project'] += 1
            continue

        doc = str(row.get('documentId', '') or '').strip()
        num = str(row.get('contractNumber', '') or '').strip()
        title = f'Contrato Sienge {doc} {num} · {project.name}'[:300]
        human = '\n'.join(_human_contract_lines(row))
        summary = human.strip()[:2000] or title

        _try_create(
            project=project,
            category=category,
            title=title,
            summary=summary,
            external_id=ext_id,
            entity_type='sienge_supply_contract',
            initiated_by=initiated_by,
            dry_run=dry_run,
            stats=stats,
            source_row=row,
        )
    return stats


def sync_sienge_measurements_to_central(
    *,
    client: Optional['SiengeCentralApiClient'] = None,
    initiated_by: Optional['AbstractUser'] = None,
    max_rows: Optional[int] = None,
    category_code: Optional[str] = None,
    any_status: bool = False,
    dry_run: bool = False,
) -> Dict[str, int]:
    """
    Medições ``/measurements/all`` → categoria ``medicao`` (ou a definida em settings).

    ``category_code``: se None, usa ``SIENGE_CENTRAL_MEASUREMENT_CATEGORY_CODE`` (default ``medicao``).
    """
    from workflow_aprovacao.services.sienge_api import SiengeCentralApiClient

    api = client or SiengeCentralApiClient()
    stats = _empty_stats()
    cap = _cap_max_rows(max_rows)
    lookup = build_sienge_project_lookup()
    if category_code:
        code = category_code.strip().lower()
        if code == 'bm':
            code = 'medicao'
        if code not in CENTRAL_CATEGORY_CODES:
            raise ValueError(f'Categoria inválida: {code!r}')
        category = _category_or_raise(code)
    else:
        code = (
            getattr(settings, 'SIENGE_CENTRAL_MEASUREMENT_CATEGORY_CODE', 'medicao') or 'medicao'
        ).strip().lower()
        if code == 'bm':
            code = 'medicao'
        if code not in CENTRAL_CATEGORY_CODES:
            raise ValueError(f'SIENGE_CENTRAL_MEASUREMENT_CATEGORY_CODE inválido: {code!r}')
        category = _category_or_raise(code)

    for row in api.iter_supply_contract_measurements(page_size=25, max_rows=cap):
        stats['examined'] += 1
        pending = any_status or measurement_pending_sienge_authorization(row)
        if not pending:
            stats['skipped_not_pending'] += 1
            continue

        ext_id = measurement_external_id(row)
        if len(ext_id) <= 2:
            stats['skipped_not_pending'] += 1
            continue

        project = resolve_project_for_sienge_row(row, lookup, client=api)
        if not project:
            stats['skipped_no_project'] += 1
            continue

        doc = str(row.get('documentId', '') or '').strip()
        num = str(row.get('contractNumber', '') or '').strip()
        mn_disp = row.get('measurementNumber', '')
        title = f'Medição Sienge {doc} {num} · nº {mn_disp} · {project.name}'[:300]
        human = '\n'.join(_human_measurement_lines(row))
        summary = human.strip()[:2000] or title

        _try_create(
            project=project,
            category=category,
            title=title,
            summary=summary,
            external_id=ext_id,
            entity_type='sienge_supply_contract_measurement',
            initiated_by=initiated_by,
            dry_run=dry_run,
            stats=stats,
            source_row=row,
        )
    return stats


def sync_sienge_central_inbound(
    *,
    client: Optional['SiengeCentralApiClient'] = None,
    initiated_by: Optional['AbstractUser'] = None,
    max_rows: Optional[int] = None,
    any_status: bool = False,
    dry_run: bool = False,
    include_contracts: bool = True,
    include_measurements: bool = True,
) -> Dict[str, Any]:
    """
    Passo 1: contratos + medições (mesma categoria configurável para medições).
    Retorna estatísticas por fonte.
    """
    out: Dict[str, Any] = {}
    if include_contracts:
        out['contracts'] = sync_sienge_contracts_to_central(
            client=client,
            initiated_by=initiated_by,
            max_rows=max_rows,
            any_status=any_status,
            dry_run=dry_run,
        )
    if include_measurements:
        out['measurements'] = sync_sienge_measurements_to_central(
            client=client,
            initiated_by=initiated_by,
            max_rows=max_rows,
            category_code=None,
            any_status=any_status,
            dry_run=dry_run,
        )
    return out
