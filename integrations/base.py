from dataclasses import dataclass, field
from typing import Any


@dataclass
class IntegrationContext:
    event_type: str
    source: str
    actor_id: int | None = None
    correlation_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class BaseIntegrationProvider:
    provider_name = "base"

    def is_enabled(self) -> bool:
        return True

    def handle_event(self, context: IntegrationContext, payload: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError

