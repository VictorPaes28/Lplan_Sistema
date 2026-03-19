from typing import Any

from integrations import config
from integrations.base import BaseIntegrationProvider, IntegrationContext
from integrations.models import ExternalDocument


class SharePointProvider(BaseIntegrationProvider):
    provider_name = "sharepoint"

    def is_enabled(self) -> bool:
        return config.INTEGRATIONS_ENABLED and config.SHAREPOINT_ENABLED

    def handle_event(self, context: IntegrationContext, payload: dict[str, Any]) -> dict[str, Any]:
        reference_id = int(payload.get("reference_id", 0) or 0)
        file_name = payload.get("file_name", "")
        if reference_id <= 0 or not file_name:
            return {"skipped": True, "reason": "payload_without_document"}
        # Estrutura pronta para upload real via Microsoft Graph /drives/{id}/items.
        document = ExternalDocument.objects.create(
            reference_type=payload.get("reference_type", "generic"),
            reference_id=reference_id,
            file_name=file_name,
            external_id=payload.get("external_id", f"sp:{context.correlation_id}"),
            external_url=payload.get("external_url", ""),
            version_label=payload.get("version_label", "v1"),
            metadata={
                "site_id": config.SHAREPOINT_SITE_ID,
                "drive_id": config.SHAREPOINT_DRIVE_ID,
                "event_type": context.event_type,
            },
        )
        return {"external_document_id": document.id, "provider": self.provider_name}

