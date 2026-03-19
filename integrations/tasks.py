import logging

from celery import shared_task

from integrations.services import dispatch_integration_event

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=30)
def dispatch_event_task(self, event_type: str, payload: dict, source: str = "app", actor_id: int | None = None):
    try:
        return dispatch_integration_event(
            event_type=event_type,
            payload=payload or {},
            source=source,
            actor_id=actor_id,
        )
    except Exception as exc:
        logger.exception("Erro ao processar evento de integração %s", event_type)
        raise self.retry(exc=exc)


@shared_task
def powerbi_export_incremental_task():
    return dispatch_integration_event(
        event_type="powerbi_export_incremental",
        source="scheduler",
        payload={"title": "Exportacao incremental Power BI"},
    )


@shared_task
def sharepoint_sync_document_task(reference_type: str, reference_id: int, file_name: str):
    return dispatch_integration_event(
        event_type="sharepoint_document_sync",
        source="manual",
        payload={
            "reference_type": reference_type,
            "reference_id": reference_id,
            "file_name": file_name,
        },
    )


@shared_task
def signature_status_sync_task(signature_request_id: int):
    return dispatch_integration_event(
        event_type="signature_status_sync",
        source="scheduler",
        payload={
            "reference_type": "signature_request",
            "reference_id": signature_request_id,
        },
    )


@shared_task
def operations_sync_task(reference_type: str, reference_id: int):
    return dispatch_integration_event(
        event_type="operations_sync",
        source="scheduler",
        payload={
            "reference_type": reference_type,
            "reference_id": reference_id,
            "ponto": {"reference": f"{reference_type}:{reference_id}"},
            "geo": {"reference": f"{reference_type}:{reference_id}"},
        },
    )


@shared_task
def erp_finance_sync_task(reference_type: str, reference_id: int):
    return dispatch_integration_event(
        event_type="erp_finance_sync",
        source="scheduler",
        payload={
            "reference_type": reference_type,
            "reference_id": reference_id,
        },
    )

