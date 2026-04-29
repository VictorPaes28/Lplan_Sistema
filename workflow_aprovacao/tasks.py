"""
Tarefas Celery: ingestão periódica Sienge → Central de Aprovações.

Ative com SIENGE_CENTRAL_BEAT_ENABLED=true e processe com: celery -A lplan_central beat / worker.
"""
from __future__ import annotations

import logging

from celery import shared_task
from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)


@shared_task(bind=True, ignore_result=True)
def sync_sienge_central_periodic(self) -> None:
    """
    Lê contratos e medições pendentes no Sienge e cria/atualiza processos na Central.

    Respeita credenciais em settings; falha silenciosamente com log se API indisponível.
    """
    from workflow_aprovacao.models import SiengeCentralSyncState
    from workflow_aprovacao.services.sienge_measurement_sync import sync_sienge_central_inbound

    state = SiengeCentralSyncState.get_singleton()
    max_rows = int(getattr(settings, 'SIENGE_CENTRAL_PERIODIC_SYNC_MAX_ROWS', 20000) or 20000)

    try:
        stats = sync_sienge_central_inbound(
            initiated_by=None,
            max_rows=max_rows,
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
        logger.info('sync_sienge_central_periodic concluído: %s', stats)
    except Exception as exc:
        logger.exception('sync_sienge_central_periodic falhou')
        state.last_run_at = timezone.now()
        state.last_ok = False
        state.last_stats = {}
        state.last_error = str(exc)[:4000]
        state.save(update_fields=['last_run_at', 'last_ok', 'last_stats', 'last_error'])
