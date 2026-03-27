from assistente_lplan.schemas import AssistantResponse
from gestao_aprovacao.models import Approval, WorkOrder
from .messages import MessageCatalog


class AprovacoesAssistantService:
    def __init__(self, user, scope):
        self.user = user
        self.scope = scope

    def listar_aprovacoes_pendentes(self, entities: dict) -> AssistantResponse:
        qs = (
            self._work_orders_scope()
            .filter(status="pendente")
            .select_related("obra", "criado_por")
            .order_by("-created_at")
        )

        pending_count = qs.count()
        rows = []
        for wo in list(qs[:30]):
            rows.append(
                {
                    "pedido": wo.codigo,
                    "obra": wo.obra.nome if wo.obra else "-",
                    "solicitante": (wo.criado_por.get_full_name() or wo.criado_por.username) if wo.criado_por else "-",
                    "tipo": wo.tipo_solicitacao,
                    "data": wo.created_at.strftime("%d/%m/%Y"),
                }
            )

        if pending_count == 0:
            msg = MessageCatalog.resolve("assistant.aprovacoes.pending_empty", {"domain": "aprovacoes"})
            return AssistantResponse(
                summary=msg["text"],
                badges=["Sem dados suficientes", "Aprovacao"],
                alerts=[{"level": "info", "message": msg["next_steps"][0]}],
                raw_data={"message_code": msg["code"], "message_kind": msg["kind"]},
            )

        return AssistantResponse(
            summary=f"Existem {pending_count} aprovacoes pendentes no seu escopo.",
            cards=[{"title": "Pendentes", "value": str(pending_count), "tone": "warning"}],
            table={
                "caption": "Pedidos aguardando aprovacao",
                "columns": ["pedido", "obra", "solicitante", "tipo", "data"],
                "rows": rows,
            },
            badges=["GestControll", "Aprovacao"],
            actions=[{"label": "Abrir pedidos", "url": "/gestao/pedidos/", "style": "primary"}],
            links=[{"label": "GestControll - Pedidos", "url": "/gestao/pedidos/"}],
        )

    def solicitacoes_reprovadas(self, entities: dict) -> AssistantResponse:
        scoped_orders = self._work_orders_scope()
        qs = (
            Approval.objects.select_related("work_order", "work_order__obra", "aprovado_por")
            .filter(decisao="reprovado", work_order__in=scoped_orders)
            .order_by("-created_at")
        )
        rows = []
        for item in list(qs[:30]):
            rows.append(
                {
                    "pedido": item.work_order.codigo if item.work_order else "-",
                    "obra": item.work_order.obra.nome if item.work_order and item.work_order.obra else "-",
                    "aprovador": (item.aprovado_por.get_full_name() or item.aprovado_por.username)
                    if item.aprovado_por
                    else "-",
                    "data": item.created_at.strftime("%d/%m/%Y %H:%M"),
                    "motivo": (item.comentario or "")[:120],
                }
            )

        if not rows:
            msg = MessageCatalog.resolve("assistant.aprovacoes.rejected_empty", {"domain": "aprovacoes"})
            return AssistantResponse(
                summary=msg["text"],
                badges=["Sem dados suficientes", "Reprovacao"],
                alerts=[{"level": "info", "message": msg["next_steps"][0]}],
                raw_data={"message_code": msg["code"], "message_kind": msg["kind"]},
            )

        return AssistantResponse(
            summary=f"Foram localizadas {len(rows)} reprovacoes recentes.",
            cards=[{"title": "Reprovacoes recentes", "value": str(len(rows)), "tone": "danger"}],
            table={
                "caption": "Solicitacoes reprovadas",
                "columns": ["pedido", "obra", "aprovador", "data", "motivo"],
                "rows": rows,
            },
            badges=["GestControll", "Reprovacao"],
            actions=[{"label": "Analisar pedidos", "url": "/gestao/pedidos/", "style": "secondary"}],
            links=[{"label": "GestControll - Pedidos", "url": "/gestao/"}],
        )

    def _work_orders_scope(self):
        qs = WorkOrder.objects.all()
        if self.scope.role == "admin":
            return qs
        if self.scope.role == "aprovador":
            return qs.filter(obra_id__in=self.scope.aprovador_obra_ids).distinct()
        return qs.filter(criado_por=self.user).distinct()

