"""
Ingestão Sienge → Central de Aprovações (fase 1: só receber dados).

Escopo explícito: contratos de suprimentos e medições de contrato (supply-contracts).
Não usa pedidos de compra (PC), solicitações de compra (SC), notas fiscais de compra,
nem mapa de suprimentos — só o que alimenta aprovação de contrato/medición na Central.

Fontes na API pública Sienge (contrato de suprimentos):
  - GET /v1/supply-contracts/all → categoria ``contrato``
  - GET /v1/supply-contracts/measurements/all → categoria ``medicao`` (BM = mesma linha operacional)

A categoria das medições pode ser ``medicao`` ou ``bm`` via ``SIENGE_CENTRAL_MEASUREMENT_CATEGORY_CODE``.

Resolução de obra: o ``contractNumber`` do Sienge é casado com obras **já existentes** por, por ordem:
  ``Project.contract_number``, ``Project.code``, tokens em ``Project.sienge_codigos_alternativos``,
  ``gestao_aprovacao.Obra.codigo`` (com ``project``), ``mapa_obras.Obra`` (código Sienge + alternativos).

Não altera cadastro de obras; só usa o que já está na base.
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

if TYPE_CHECKING:
    from django.contrib.auth.models import AbstractUser

    from workflow_aprovacao.services.sienge_api import SiengeCentralApiClient

CENTRAL_CATEGORY_CODES = frozenset({'contrato', 'bm', 'medicao'})


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


def resolve_project_for_sienge_row(
    row: Dict[str, Any],
    lookup: Optional[Dict[str, Project]] = None,
) -> Optional[Project]:
    cn = str(row.get('contractNumber', '')).strip()
    if not cn:
        return None
    key = cn.lower()
    if lookup is not None:
        return lookup.get(key)
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
        ApprovalEngine.start(
            project=project,
            category=category,
            initiated_by=initiated_by,
            title=title[:300],
            summary=summary[:2000],
            external_id=external_id,
            external_entity_type=entity_type,
            sync_status=SyncStatus.NOT_APPLICABLE,
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

        project = resolve_project_for_sienge_row(row, lookup)
        if not project:
            stats['skipped_no_project'] += 1
            continue

        doc = str(row.get('documentId', '') or '').strip()
        num = str(row.get('contractNumber', '') or '').strip()
        title = f'Sienge — contrato {doc} {num}'[:300]
        summary_lines = [
            f'status: {row.get("status")}',
            f'statusApproval: {row.get("statusApproval")}',
            f'isAuthorized: {row.get("isAuthorized")}',
            f'Empresa: {row.get("companyName") or row.get("companyId")}',
            f'Fornecedor: {row.get("supplierName") or row.get("supplierId")}',
        ]
        summary = '\n'.join(str(x) for x in summary_lines if x)

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
    Medições ``/measurements/all`` → uma categoria na Central (BM = mesma coisa: ``medicao`` por defeito).

    ``category_code``: se None, usa ``SIENGE_CENTRAL_MEASUREMENT_CATEGORY_CODE`` (default ``medicao``).
    """
    from workflow_aprovacao.services.sienge_api import SiengeCentralApiClient

    api = client or SiengeCentralApiClient()
    stats = _empty_stats()
    cap = _cap_max_rows(max_rows)
    lookup = build_sienge_project_lookup()
    if category_code:
        code = category_code.strip().lower()
        if code not in CENTRAL_CATEGORY_CODES:
            raise ValueError(f'Categoria inválida: {code!r}')
        category = _category_or_raise(code)
    else:
        code = (
            getattr(settings, 'SIENGE_CENTRAL_MEASUREMENT_CATEGORY_CODE', 'medicao') or 'medicao'
        ).strip().lower()
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

        project = resolve_project_for_sienge_row(row, lookup)
        if not project:
            stats['skipped_no_project'] += 1
            continue

        doc = str(row.get('documentId', '') or '').strip()
        num = str(row.get('contractNumber', '') or '').strip()
        mn_disp = row.get('measurementNumber', '')
        title = f'Sienge — medição · contrato {doc} {num} · nº {mn_disp}'[:300]
        summary_lines = [
            f'buildingId: {row.get("buildingId")}',
            f'Responsável: {row.get("responsibleName") or row.get("responsibleId") or ""}',
            f'statusApproval: {row.get("statusApproval")}',
            f'authorized: {row.get("authorized")}',
        ]
        if row.get('notes'):
            summary_lines.append(str(row.get('notes')))
        summary = '\n'.join(summary_lines)

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
