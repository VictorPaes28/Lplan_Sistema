"""
Fila administrativa: registos que não puderam iniciar processo (sem fluxo, etc.).
"""
from __future__ import annotations

import json
from typing import Any, Dict, Optional

from django.db import transaction
from django.utils import timezone

from workflow_aprovacao.models import (
    ApprovalConfigBacklog,
    ApprovalConfigBacklogStatus,
    ApprovalConfigBlockReason,
    ApprovalProcess,
    ProcessCategory,
)
from workflow_aprovacao.services.engine import ApprovalEngine


def _json_safe_payload(data: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if not data:
        return {}
    try:
        json.dumps(data, default=str)
        return dict(data)
    except (TypeError, ValueError):
        return {'_note': 'payload original não serializável; omitido'}


@transaction.atomic
def upsert_inbound_backlog(
    *,
    project,
    category: ProcessCategory,
    external_system: str,
    external_id: str,
    external_entity_type: str,
    title: str,
    summary: str,
    source_payload: Optional[Dict[str, Any]] = None,
    block_reason: str = ApprovalConfigBlockReason.NO_FLOW,
    last_error_message: str = '',
) -> ApprovalConfigBacklog:
    """
    Cria ou atualiza entrada na fila de configuração (ex.: novo sync Sienge sem fluxo).
    """
    safe = _json_safe_payload(source_payload)
    qs = ApprovalConfigBacklog.objects.select_for_update().filter(
        external_system=external_system,
        external_id=external_id,
    )
    row = qs.first()
    if not row:
        return ApprovalConfigBacklog.objects.create(
            status=ApprovalConfigBacklogStatus.PENDING,
            block_reason=block_reason,
            project=project,
            category=category,
            external_system=external_system,
            external_id=external_id,
            external_entity_type=external_entity_type or '',
            title=title[:300],
            summary=summary[:2000],
            source_payload=safe,
            last_error_message=(last_error_message or '')[:4000],
            hit_count=1,
        )

    row.hit_count += 1
    row.title = title[:300]
    row.summary = summary[:2000]
    row.source_payload = safe
    row.block_reason = block_reason
    row.last_error_message = (last_error_message or '')[:4000]
    row.category = category
    row.project = project
    row.external_entity_type = external_entity_type or ''

    if row.status == ApprovalConfigBacklogStatus.RESOLVED:
        row.status = ApprovalConfigBacklogStatus.PENDING
        row.resolved_at = None
        row.resolved_by = None
        row.linked_process = None

    row.save(
        update_fields=[
            'hit_count',
            'title',
            'summary',
            'source_payload',
            'block_reason',
            'last_error_message',
            'category',
            'project',
            'external_entity_type',
            'status',
            'resolved_at',
            'resolved_by',
            'linked_process',
            'updated_at',
        ]
    )
    return row


@transaction.atomic
def mark_backlog_resolved_for_process(process: ApprovalProcess) -> None:
    """Após criar processo com sucesso, fecha pendência com o mesmo external_id."""
    ext = (process.external_id or '').strip()
    if not ext:
        return
    sysname = (process.external_system or 'sienge').strip() or 'sienge'
    ApprovalConfigBacklog.objects.filter(
        external_system=sysname,
        external_id=ext,
        status=ApprovalConfigBacklogStatus.PENDING,
    ).update(
        status=ApprovalConfigBacklogStatus.RESOLVED,
        resolved_at=timezone.now(),
        linked_process=process,
        resolved_by_id=process.initiated_by_id,
    )


def try_start_from_backlog(
    backlog: ApprovalConfigBacklog,
    *,
    initiated_by,
):
    """
    Tenta ApprovalEngine.start com os dados guardados.
    Retorna (processo | None, mensagem_erro).
    """
    if backlog.status != ApprovalConfigBacklogStatus.PENDING:
        return None, 'Esta pendência não está aguardando ação.'

    if ApprovalProcess.objects.filter(
        external_system=backlog.external_system,
        external_id=backlog.external_id,
    ).exists():
        return None, 'Já existe processo com este identificador externo.'

    try:
        process = ApprovalEngine.start(
            project=backlog.project,
            category=backlog.category,
            initiated_by=initiated_by,
            title=backlog.title,
            summary=backlog.summary,
            external_id=backlog.external_id,
            external_entity_type=backlog.external_entity_type,
        )
    except Exception as exc:
        return None, str(exc)

    backlog.refresh_from_db()
    return process, ''


@transaction.atomic
def dismiss_backlog(backlog: ApprovalConfigBacklog, *, user, note: str = '') -> None:
    backlog.status = ApprovalConfigBacklogStatus.DISMISSED
    backlog.dismiss_note = (note or '')[:2000]
    backlog.resolved_by = user
    backlog.resolved_at = timezone.now()
    backlog.save(update_fields=['status', 'dismiss_note', 'resolved_by', 'resolved_at', 'updated_at'])


@transaction.atomic
def reopen_backlog(backlog: ApprovalConfigBacklog) -> None:
    backlog.status = ApprovalConfigBacklogStatus.PENDING
    backlog.dismiss_note = ''
    backlog.resolved_at = None
    backlog.resolved_by = None
    backlog.linked_process = None
    backlog.save(
        update_fields=[
            'status',
            'dismiss_note',
            'resolved_at',
            'resolved_by',
            'linked_process',
            'updated_at',
        ]
    )
