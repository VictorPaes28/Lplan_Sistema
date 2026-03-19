from django.utils import timezone

from integrations import config
from integrations.base import BaseIntegrationProvider, IntegrationContext
from integrations.models import OperationsSyncRecord


class ERPProvider(BaseIntegrationProvider):
    provider_name = "erp"

    def is_enabled(self) -> bool:
        return config.INTEGRATIONS_ENABLED and bool(config.ERP_API_URL and config.ERP_API_TOKEN)

    def handle_event(self, context: IntegrationContext, payload: dict) -> dict:
        if context.event_type not in {"workorder_status_aprovado", "workorder_status_reprovado", "erp_finance_sync"}:
            return {"skipped": True, "reason": "event_not_mapped"}
        rec = OperationsSyncRecord.objects.create(
            sync_type=OperationsSyncRecord.TYPE_ERP,
            reference_type=payload.get("reference_type", ""),
            reference_id=payload.get("reference_id") or None,
            status="synced",
            request_payload=payload,
            response_payload={"erp_url": config.ERP_API_URL, "event_type": context.event_type},
            synced_at=timezone.now(),
        )
        return {"erp_sync_record_id": rec.id}

