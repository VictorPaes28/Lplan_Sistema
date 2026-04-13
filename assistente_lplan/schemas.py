from dataclasses import dataclass, field
from typing import Any


@dataclass
class AssistantCard:
    title: str
    value: str
    subtitle: str = ""
    tone: str = "info"


@dataclass
class AssistantAction:
    label: str
    url: str
    style: str = "primary"


@dataclass
class AssistantTable:
    columns: list[str] = field(default_factory=list)
    rows: list[dict[str, Any]] = field(default_factory=list)
    caption: str = ""


@dataclass
class AssistantResponse:
    summary: str
    radar_score: int | None = None
    risk_level: str = ""
    trend: str = ""
    causes: list[str] = field(default_factory=list)
    recommended_action: dict[str, Any] = field(default_factory=dict)
    secondary_actions: list[dict[str, Any]] = field(default_factory=list)
    cards: list[dict[str, Any]] = field(default_factory=list)
    table: dict[str, Any] = field(default_factory=dict)
    badges: list[str] = field(default_factory=list)
    timeline: list[dict[str, Any]] = field(default_factory=list)
    alerts: list[dict[str, str]] = field(default_factory=list)
    actions: list[dict[str, Any]] = field(default_factory=list)
    links: list[dict[str, str]] = field(default_factory=list)
    raw_data: dict[str, Any] = field(default_factory=dict)
    suggested_replies: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "summary": self.summary,
            "radar_score": self.radar_score,
            "risk_level": self.risk_level,
            "trend": self.trend,
            "causes": self.causes,
            "recommended_action": self.recommended_action,
            "secondary_actions": self.secondary_actions,
            "cards": self.cards,
            "table": self.table,
            "badges": self.badges,
            "timeline": self.timeline,
            "alerts": self.alerts,
            "actions": self.actions,
            "links": self.links,
            "raw_data": self.raw_data,
            "suggested_replies": self.suggested_replies,
        }
