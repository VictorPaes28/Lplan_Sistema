from typing import Any

from integrations import config
from integrations.base import BaseIntegrationProvider, IntegrationContext
from integrations.models import SignatureRequest


class SignatureProvider(BaseIntegrationProvider):
    provider_name = "signature"

    def is_enabled(self) -> bool:
        return config.INTEGRATIONS_ENABLED and config.SIGNATURE_ENABLED and bool(config.SIGNATURE_API_KEY)

    def handle_event(self, context: IntegrationContext, payload: dict[str, Any]) -> dict[str, Any]:
        signer_name = payload.get("signer_name", "Sem nome")
        signer_email = payload.get("signer_email", "")
        signature = SignatureRequest.objects.create(
            provider=config.SIGNATURE_PROVIDER,
            reference_type=payload.get("reference_type", "workorder"),
            reference_id=int(payload.get("reference_id", 0) or 0),
            signer_name=signer_name,
            signer_email=signer_email,
            status=SignatureRequest.STATUS_SENT,
            external_request_id=payload.get("external_request_id", f"sig:{context.correlation_id}"),
            raw_payload=payload,
            created_by_id=context.actor_id,
        )
        return {"signature_request_id": signature.id, "status": signature.status}

