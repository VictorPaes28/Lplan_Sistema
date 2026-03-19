from django.utils import timezone

from integrations import config
from integrations.base import BaseIntegrationProvider, IntegrationContext
from integrations.models import OperationsSyncRecord


class OperationsProvider(BaseIntegrationProvider):
    provider_name = "operations"

    def is_enabled(self) -> bool:
        return config.INTEGRATIONS_ENABLED and config.OPERATIONS_ENABLED

    def handle_event(self, context: IntegrationContext, payload: dict) -> dict:
        records = []
        if payload.get("ponto"):
            rec = OperationsSyncRecord.objects.create(
                sync_type=OperationsSyncRecord.TYPE_PONTO,
                reference_type=payload.get("reference_type", ""),
                reference_id=payload.get("reference_id") or None,
                status="synced",
                request_payload=payload.get("ponto", {}),
                response_payload={"api_url": config.PONTO_API_URL},
                synced_at=timezone.now(),
            )
            records.append(rec.id)
        if payload.get("geo"):
            rec = OperationsSyncRecord.objects.create(
                sync_type=OperationsSyncRecord.TYPE_GEO,
                reference_type=payload.get("reference_type", ""),
                reference_id=payload.get("reference_id") or None,
                status="synced",
                request_payload=payload.get("geo", {}),
                response_payload={"provider": config.GEO_PROVIDER},
                synced_at=timezone.now(),
            )
            records.append(rec.id)
        return {"records": records}

