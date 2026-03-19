from integrations.services import dispatch_event_on_commit


def handle_teams_webhook(payload: dict, actor_id: int | None = None):
    dispatch_event_on_commit(
        event_type="teams_webhook_received",
        source="teams_webhook",
        actor_id=actor_id,
        payload={"title": "Webhook Teams recebido", "details": str(payload)[:500]},
    )


def handle_signature_webhook(payload: dict, actor_id: int | None = None):
    dispatch_event_on_commit(
        event_type="signature_webhook_received",
        source="signature_webhook",
        actor_id=actor_id,
        payload={"title": "Webhook assinatura recebido", "details": str(payload)[:500]},
    )

