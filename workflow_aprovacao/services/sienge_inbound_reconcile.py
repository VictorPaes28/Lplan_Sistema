"""
Quando o Sienge já autorizou contrato/medición mas a Central ainda tem processo em
``awaiting_step``, alinha o estado para **approved** sem gravar envio na outbox —
o Sienge já reflete a decisão.
"""
from __future__ import annotations

from typing import Any, Dict

from django.db import transaction
from django.utils import timezone

from workflow_aprovacao.models import ApprovalHistoryEntry, ApprovalProcess, HistoryAction, ProcessStatus, SyncStatus


def _snapshot(row: dict) -> dict:
    from workflow_aprovacao.services.sienge_measurement_sync import sienge_row_public_snapshot

    return sienge_row_public_snapshot(row)


def _sienge_inbound_types() -> tuple[str, ...]:
    return ('sienge_supply_contract', 'sienge_supply_contract_measurement')


@transaction.atomic
def reconcile_existing_sienge_process_row(
    *,
    process: ApprovalProcess,
    source_row: Dict[str, Any],
    sienge_authorization_done: bool,
    dry_run: bool,
) -> str:
    """
    Retorno:
      - ``noop``: nada a fazer (Sienge ainda pendente ou tipo inválido).
      - ``dry_run_close``: em dry-run teria fechado ou atualizado snapshot.
      - ``closed``: processo passou a approved + histórico SYNC_EVENT.
      - ``snapshot_updated``: apenas ``external_payload`` / ``last_sync_at`` (processo já terminal approved).
      - ``skipped_terminal``: reprovado/cancelado/etc. — não alterar.
    """
    et = (process.external_entity_type or '').strip()
    if et not in _sienge_inbound_types():
        return 'noop'

    if process.status in (ProcessStatus.REJECTED, ProcessStatus.CANCELLED):
        return 'skipped_terminal'

    if not sienge_authorization_done:
        return 'noop'

    if process.status == ProcessStatus.APPROVED:
        return _maybe_refresh_snapshot(process, source_row, dry_run=dry_run)

    if process.status != ProcessStatus.AWAITING_STEP:
        return 'skipped_terminal'

    if dry_run:
        return 'dry_run_close'

    snap = _snapshot(source_row or {})
    prev = process.status
    process.status = ProcessStatus.APPROVED
    process.current_step = None
    process.external_payload = snap
    process.sync_status = SyncStatus.SYNCED
    process.last_sync_at = timezone.now()
    process.last_sync_error = ''
    process.save(
        update_fields=[
            'status',
            'current_step',
            'external_payload',
            'sync_status',
            'last_sync_at',
            'last_sync_error',
            'updated_at',
        ]
    )

    ApprovalHistoryEntry.objects.create(
        process=process,
        step=None,
        step_sequence_snapshot=None,
        actor=None,
        action=HistoryAction.SYNC_EVENT,
        comment=(
            'Encerrado automaticamente: registo já autorizado no Sienge '
            'na sincronização (reconciliação inbound).'
        ),
        previous_status=prev,
        new_status=process.status,
        payload={
            'reason': 'sienge_already_authorized',
            'external_entity_type': et,
            'external_id': process.external_id or '',
        },
    )
    return 'closed'


def _maybe_refresh_snapshot(process: ApprovalProcess, source_row: Dict[str, Any], *, dry_run: bool) -> str:
    snap = _snapshot(source_row or {})
    if snap == (process.external_payload or {}):
        return 'noop'
    if dry_run:
        return 'dry_run_close'
    process.external_payload = snap
    process.last_sync_at = timezone.now()
    process.save(update_fields=['external_payload', 'last_sync_at', 'updated_at'])
    return 'snapshot_updated'
