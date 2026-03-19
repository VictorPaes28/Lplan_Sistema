import datetime as dt
from typing import Any

from django.db.models import Count

from core.models import ConstructionDiary
from gestao_aprovacao.models import WorkOrder
from integrations import config
from integrations.base import BaseIntegrationProvider, IntegrationContext


class PowerBIProvider(BaseIntegrationProvider):
    provider_name = "powerbi"

    def is_enabled(self) -> bool:
        return config.INTEGRATIONS_ENABLED and config.POWERBI_ENABLED

    def handle_event(self, context: IntegrationContext, payload: dict[str, Any]) -> dict[str, Any]:
        # Placeholder de contrato de dados incremental.
        # O push real no dataset pode ser implementado via REST do Power BI.
        today = dt.date.today()
        pending_orders = WorkOrder.objects.filter(status__in=["pendente", "reaprovacao"]).count()
        approved_today = WorkOrder.objects.filter(status="aprovado", data_aprovacao__date=today).count()
        diaries_today = ConstructionDiary.objects.filter(date=today).count()
        by_status = dict(WorkOrder.objects.values_list("status").annotate(c=Count("id")))
        return {
            "workspace_id": config.POWERBI_WORKSPACE_ID,
            "dataset_id": config.POWERBI_DATASET_ID,
            "snapshot": {
                "date": str(today),
                "pending_orders": pending_orders,
                "approved_today": approved_today,
                "diaries_today": diaries_today,
                "by_status": by_status,
            },
            "event_type": context.event_type,
            "payload_ref": payload.get("id"),
        }

