import logging
from typing import Any

import requests

from integrations import config
from integrations.base import BaseIntegrationProvider, IntegrationContext

logger = logging.getLogger(__name__)


class TeamsProvider(BaseIntegrationProvider):
    provider_name = "teams"

    def is_enabled(self) -> bool:
        return config.INTEGRATIONS_ENABLED and config.TEAMS_ENABLED and bool(config.AZURE_TENANT_ID and config.AZURE_CLIENT_ID and config.AZURE_CLIENT_SECRET)

    def _get_app_token(self) -> str:
        token_url = f"https://login.microsoftonline.com/{config.AZURE_TENANT_ID}/oauth2/v2.0/token"
        payload = {
            "client_id": config.AZURE_CLIENT_ID,
            "client_secret": config.AZURE_CLIENT_SECRET,
            "scope": "https://graph.microsoft.com/.default",
            "grant_type": "client_credentials",
        }
        response = requests.post(token_url, data=payload, timeout=20)
        response.raise_for_status()
        data = response.json()
        return data["access_token"]

    def _post_channel_message(self, text: str) -> dict[str, Any]:
        token = self._get_app_token()
        url = f"https://graph.microsoft.com/v1.0/teams/{config.TEAMS_TEAM_ID}/channels/{config.TEAMS_CHANNEL_ID}/messages"
        payload = {"body": {"contentType": "html", "content": text}}
        response = requests.post(url, headers={"Authorization": f"Bearer {token}"}, json=payload, timeout=20)
        response.raise_for_status()
        return response.json()

    def handle_event(self, context: IntegrationContext, payload: dict[str, Any]) -> dict[str, Any]:
        if not self.is_enabled():
            return {"skipped": True, "reason": "teams_disabled"}
        message = payload.get("message")
        if not message:
            message = self._build_default_message(context.event_type, payload)
        result = self._post_channel_message(message)
        logger.info("Mensagem enviada ao Teams para evento %s", context.event_type)
        return {"message_id": result.get("id"), "channel_id": config.TEAMS_CHANNEL_ID}

    def _build_default_message(self, event_type: str, payload: dict[str, Any]) -> str:
        title = payload.get("title") or event_type.replace("_", " ").title()
        details = payload.get("details") or ""
        link = payload.get("link") or ""
        parts = [f"<b>{config.TEAMS_DEFAULT_MESSAGE_PREFIX} {title}</b>"]
        if details:
            parts.append(f"<div>{details}</div>")
        if link:
            parts.append(f'<div><a href="{link}">Abrir no sistema</a></div>')
        return "".join(parts)

