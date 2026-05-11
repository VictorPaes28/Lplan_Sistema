from __future__ import annotations

from typing import Any

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from workflow_aprovacao.models import (
    ApprovalHistoryEntry,
    ApprovalIntegrationOutbox,
    HistoryAction,
    OutboxStatus,
    SyncStatus,
)


def _is_true(value: Any, *, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in ('1', 'true', 'yes', 'on')


def _shadow_mode_enabled() -> bool:
    return _is_true(getattr(settings, 'SIENGE_OUTBOUND_SHADOW_MODE', True), default=True)


def _outbound_enabled() -> bool:
    return _is_true(getattr(settings, 'SIENGE_OUTBOUND_ENABLED', False), default=False)


@transaction.atomic
def dispatch_outbox_entry_now(*, outbox_id: int, actor=None, force: bool = False) -> dict[str, Any]:
    """
    Dispara um item da outbox para integração.

    Nesta fase, o envio real para Sienge pode ficar desligado por configuração.
    Se shadow mode estiver ligado, marca como enviado (simulado) para validar o fluxo.
    """
    entry = (
        ApprovalIntegrationOutbox.objects.select_for_update()
        .select_related('process')
        .get(pk=outbox_id)
    )
    process = entry.process

    if entry.status == OutboxStatus.SENT and not force:
        return {'status': 'skipped_sent', 'message': 'Item já enviado anteriormente.'}

    process.sync_status = SyncStatus.IN_PROGRESS
    process.save(update_fields=['sync_status', 'updated_at'])

    entry.attempts = int(entry.attempts or 0) + 1

    shadow_mode = _shadow_mode_enabled()
    outbound_enabled = _outbound_enabled()

    if not outbound_enabled and not shadow_mode:
        msg = 'Envio ao Sienge está desativado por configuração (SIENGE_OUTBOUND_ENABLED=false).'
        entry.status = OutboxStatus.FAILED
        entry.last_error = msg
        entry.save(update_fields=['attempts', 'status', 'last_error'])
        process.sync_status = SyncStatus.FAILED
        process.last_sync_at = timezone.now()
        process.last_sync_error = msg
        process.save(update_fields=['sync_status', 'last_sync_at', 'last_sync_error', 'updated_at'])
        return {'status': 'error', 'message': msg}

    now = timezone.now()
    dispatch_info = {
        'mode': 'shadow' if shadow_mode else 'real',
        'dispatched_at': now.isoformat(),
        'dispatched_by_user_id': getattr(actor, 'pk', None),
    }

    payload = dict(entry.payload or {})
    payload['dispatch'] = dispatch_info

    entry.payload = payload
    entry.status = OutboxStatus.SENT
    entry.sent_at = now
    entry.last_error = ''
    entry.save(update_fields=['attempts', 'payload', 'status', 'sent_at', 'last_error'])

    process.sync_status = SyncStatus.SYNCED
    process.last_sync_at = now
    process.last_sync_error = ''
    process.save(update_fields=['sync_status', 'last_sync_at', 'last_sync_error', 'updated_at'])

    ApprovalHistoryEntry.objects.create(
        process=process,
        step=process.current_step,
        step_sequence_snapshot=process.current_step.sequence if process.current_step else None,
        actor=actor,
        action=HistoryAction.SYNC_EVENT,
        comment='Retorno para integração marcado como enviado (modo shadow).'
        if shadow_mode
        else 'Retorno para integração enviado ao Sienge.',
        previous_status=process.status,
        new_status=process.status,
        payload={'outbox_id': entry.pk, 'dispatch': dispatch_info},
    )
    return {'status': 'ok', 'mode': dispatch_info['mode']}
