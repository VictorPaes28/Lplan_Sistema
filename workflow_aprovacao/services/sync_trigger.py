from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from django.conf import settings
from django.core.cache import cache
from django.utils import timezone

from workflow_aprovacao.models import SiengeCentralSyncState
from workflow_aprovacao.services.sienge_measurement_sync import sync_sienge_central_inbound

logger = logging.getLogger(__name__)

_SYNC_LOCK_KEY = 'workflow_aprovacao:sienge_sync_lock'


def _coerce_int(raw: Any, default: int) -> int:
    try:
        return int(raw)
    except (TypeError, ValueError):
        return default


def _cooldown_window() -> timedelta:
    hours = _coerce_int(getattr(settings, 'SIENGE_CENTRAL_WEB_SYNC_COOLDOWN_HOURS', 2), 2)
    return timedelta(hours=max(0, hours))


def _sync_lock_seconds() -> int:
    value = _coerce_int(getattr(settings, 'SIENGE_CENTRAL_WEB_SYNC_LOCK_SECONDS', 45 * 60), 45 * 60)
    return max(60, value)


def _sync_max_rows(*, force: bool) -> int:
    if force:
        value = _coerce_int(
            getattr(settings, 'SIENGE_CENTRAL_WEB_SYNC_FORCE_MAX_ROWS', 2000),
            2000,
        )
    else:
        value = _coerce_int(getattr(settings, 'SIENGE_CENTRAL_WEB_SYNC_MAX_ROWS', 800), 800)
    return max(1, min(value, 5000))


def trigger_sienge_sync_if_due(*, initiated_by=None, force: bool = False) -> dict[str, Any]:
    """
    Executa sync Sienge→Central quando necessário.

    Retornos:
      - status=ok
      - status=skipped_cooldown
      - status=skipped_running
      - status=error
    """
    state = SiengeCentralSyncState.get_singleton()
    now = timezone.now()
    cooldown = _cooldown_window()

    if not force and state.last_run_at and (now - state.last_run_at) < cooldown:
        return {
            'status': 'skipped_cooldown',
            'last_run_at': state.last_run_at,
            'cooldown_seconds': int(cooldown.total_seconds()),
        }

    lock_seconds = _sync_lock_seconds()
    lock_payload = f'{now.isoformat()}:{getattr(initiated_by, "pk", "anon")}'
    acquired = cache.add(_SYNC_LOCK_KEY, lock_payload, timeout=lock_seconds)
    if not acquired:
        return {'status': 'skipped_running'}

    try:
        stats = sync_sienge_central_inbound(
            initiated_by=initiated_by,
            max_rows=_sync_max_rows(force=force),
            any_status=False,
            dry_run=False,
            include_contracts=True,
            include_measurements=True,
        )
        state.last_run_at = timezone.now()
        state.last_ok = True
        state.last_stats = stats if isinstance(stats, dict) else {'raw': str(stats)}
        state.last_error = ''
        state.save(update_fields=['last_run_at', 'last_ok', 'last_stats', 'last_error'])
        return {'status': 'ok', 'stats': state.last_stats, 'last_run_at': state.last_run_at}
    except Exception as exc:
        logger.exception('Falha no sync Sienge disparado via Central')
        state.last_run_at = timezone.now()
        state.last_ok = False
        state.last_stats = {}
        state.last_error = str(exc)[:4000]
        state.save(update_fields=['last_run_at', 'last_ok', 'last_stats', 'last_error'])
        return {'status': 'error', 'error': state.last_error, 'last_run_at': state.last_run_at}
    finally:
        cache.delete(_SYNC_LOCK_KEY)


def maybe_trigger_sienge_sync_on_page_open(request) -> None:
    """
    Gatilho silencioso para páginas GET da Central.
    """
    if request.method not in ('GET', 'HEAD'):
        return
    trigger_sienge_sync_if_due(initiated_by=request.user, force=False)
