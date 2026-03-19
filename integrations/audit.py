from typing import Any

from .models import IntegrationEventLog


def start_event_log(*, event_type: str, provider: str, source: str, payload: dict[str, Any], actor_id: int | None, correlation_id: str) -> IntegrationEventLog:
    return IntegrationEventLog.objects.create(
        event_type=event_type,
        provider=provider,
        source=source,
        payload=payload or {},
        actor_id=actor_id,
        correlation_id=correlation_id or "",
    )


def mark_event_success(log: IntegrationEventLog, response: dict[str, Any], latency_ms: int | None = None):
    log.status = IntegrationEventLog.STATUS_SUCCESS
    log.response = response or {}
    log.latency_ms = latency_ms
    log.error_message = ""
    log.save(update_fields=["status", "response", "latency_ms", "error_message", "updated_at"])


def mark_event_error(log: IntegrationEventLog, error: str, response: dict[str, Any] | None = None, latency_ms: int | None = None):
    log.status = IntegrationEventLog.STATUS_FAILED
    log.error_message = error or "Erro desconhecido"
    log.response = response or {}
    log.latency_ms = latency_ms
    log.save(update_fields=["status", "error_message", "response", "latency_ms", "updated_at"])

