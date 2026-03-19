import logging
import time
import uuid
from typing import Any

from django.db import transaction

from integrations.audit import mark_event_error, mark_event_success, start_event_log
from integrations.base import IntegrationContext
from integrations.providers import ERPProvider, OperationsProvider, PowerBIProvider, SharePointProvider, SignatureProvider, TeamsProvider

logger = logging.getLogger(__name__)

PROVIDERS = [
    TeamsProvider(),
    PowerBIProvider(),
    SharePointProvider(),
    SignatureProvider(),
    OperationsProvider(),
    ERPProvider(),
]


def dispatch_integration_event(
    *,
    event_type: str,
    payload: dict[str, Any],
    source: str = "app",
    actor_id: int | None = None,
    correlation_id: str | None = None,
) -> list[dict[str, Any]]:
    correlation_id = correlation_id or uuid.uuid4().hex
    context = IntegrationContext(
        event_type=event_type,
        source=source,
        actor_id=actor_id,
        correlation_id=correlation_id,
    )
    results: list[dict[str, Any]] = []
    for provider in PROVIDERS:
        if not provider.is_enabled():
            continue
        log = start_event_log(
            event_type=event_type,
            provider=provider.provider_name,
            source=source,
            payload=payload,
            actor_id=actor_id,
            correlation_id=correlation_id,
        )
        started = time.monotonic()
        try:
            response = provider.handle_event(context, payload)
            elapsed = int((time.monotonic() - started) * 1000)
            mark_event_success(log, response=response, latency_ms=elapsed)
            results.append({"provider": provider.provider_name, "ok": True, "response": response})
        except Exception as exc:
            logger.exception("Falha na integracao %s para evento %s", provider.provider_name, event_type)
            elapsed = int((time.monotonic() - started) * 1000)
            mark_event_error(log, error=str(exc), latency_ms=elapsed)
            results.append({"provider": provider.provider_name, "ok": False, "error": str(exc)})
    return results


def dispatch_event_on_commit(
    *,
    event_type: str,
    payload: dict[str, Any],
    source: str = "app",
    actor_id: int | None = None,
):
    from integrations.tasks import dispatch_event_task

    def _enqueue():
        dispatch_event_task.delay(
            event_type=event_type,
            payload=payload,
            source=source,
            actor_id=actor_id,
        )

    transaction.on_commit(_enqueue)

