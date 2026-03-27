from decimal import Decimal

from django.db.models import Q, Sum, Value
from django.db.models.functions import Coalesce

from assistente_lplan.schemas import AssistantResponse
from mapa_obras.models import Obra
from suprimentos.models import ItemMapa
from .messages import MessageCatalog


class SuprimentosAssistantService:
    def __init__(self, scope):
        self.scope = scope

    def localizar_insumo(self, entities: dict) -> AssistantResponse:
        term = (entities.get("insumo") or "").strip()
        bloco = (entities.get("bloco") or "").strip()
        if not term:
            msg = MessageCatalog.resolve("assistant.suprimentos.insumo_missing", {"domain": "suprimentos"})
            return AssistantResponse(
                summary=msg["text"],
                alerts=[
                    {
                        "level": "warning",
                        "message": msg["next_steps"][0],
                    }
                ],
                raw_data={"message_code": msg["code"], "message_kind": msg["kind"]},
            )

        obras_qs = self._obras_scope_qs()
        q = (
            ItemMapa.objects.select_related("obra", "insumo", "local_aplicacao")
            .filter(obra__in=obras_qs)
            .filter(
                Q(insumo__descricao__icontains=term)
                | Q(descricao_override__icontains=term)
                | Q(insumo__codigo_sienge__icontains=term)
            )
            .annotate(total_alocado=Coalesce(Sum("alocacoes__quantidade_alocada"), Value(Decimal("0"))))
        )
        if bloco:
            q = q.filter(Q(local_aplicacao__nome__icontains=bloco) | Q(local_aplicacao__tipo__icontains=bloco))

        rows = []
        for item in list(q[:20]):
            planejado = item.quantidade_planejada or Decimal("0")
            alocado = item.total_alocado or Decimal("0")
            rows.append(
                {
                    "obra": item.obra.nome if item.obra else "-",
                    "insumo": item.insumo.descricao if item.insumo else "-",
                    "local": (item.local_aplicacao.nome if item.local_aplicacao else "Sem local"),
                    "planejado": str(planejado),
                    "alocado": str(alocado),
                    "status": "OK" if alocado > 0 else "Sem alocacao",
                }
            )

        if not rows:
            msg = MessageCatalog.resolve(
                "assistant.suprimentos.insumo_not_found",
                {"domain": "suprimentos", "insumo": term},
            )
            return AssistantResponse(
                summary=msg["text"],
                alerts=[
                    {
                        "level": "warning",
                        "message": msg["next_steps"][0],
                    }
                ],
                badges=["Sem dados suficientes"],
                raw_data={"message_code": msg["code"], "message_kind": msg["kind"], "insumo": term},
            )

        return AssistantResponse(
            summary=f"Foram encontrados {len(rows)} registros para '{term}'.",
            cards=[{"title": "Registros", "value": str(len(rows)), "tone": "info"}],
            table={
                "caption": "Localizacao de insumos no mapa",
                "columns": ["obra", "insumo", "local", "planejado", "alocado", "status"],
                "rows": rows,
            },
            badges=["Suprimentos", "Localizacao"],
            actions=[{"label": "Abrir mapa", "url": "/engenharia/mapa/", "style": "primary"}],
            links=[{"label": "Mapa de Suprimentos", "url": "/engenharia/mapa/"}],
        )

    def itens_sem_alocacao(self, entities: dict) -> AssistantResponse:
        obras_qs = self._obras_scope_qs()
        qs = (
            ItemMapa.objects.select_related("obra", "insumo", "local_aplicacao")
            .filter(obra__in=obras_qs)
            .annotate(total_alocado=Coalesce(Sum("alocacoes__quantidade_alocada"), Value(Decimal("0"))))
            .filter(quantidade_planejada__gt=0, total_alocado__lte=0)
            .order_by("-prioridade", "prazo_necessidade")[:30]
        )
        rows = []
        for item in qs:
            rows.append(
                {
                    "obra": item.obra.nome if item.obra else "-",
                    "insumo": item.insumo.descricao if item.insumo else "-",
                    "local": item.local_aplicacao.nome if item.local_aplicacao else "Sem local",
                    "prioridade": item.prioridade,
                    "prazo": item.prazo_necessidade.strftime("%d/%m/%Y") if item.prazo_necessidade else "-",
                }
            )

        if not rows:
            msg = MessageCatalog.resolve("assistant.suprimentos.unallocated_empty", {"domain": "suprimentos"})
            return AssistantResponse(
                summary=msg["text"],
                badges=["Sem dados suficientes"],
                alerts=[{"level": "info", "message": msg["next_steps"][0]}],
                raw_data={"message_code": msg["code"], "message_kind": msg["kind"]},
            )

        return AssistantResponse(
            summary=f"{len(rows)} itens estao sem alocacao no escopo atual.",
            cards=[
                {"title": "Itens sem alocacao", "value": str(len(rows)), "tone": "danger"},
                {"title": "Obras afetadas", "value": str(len({r['obra'] for r in rows})), "tone": "warning"},
            ],
            table={
                "caption": "Itens planejados sem alocacao",
                "columns": ["obra", "insumo", "local", "prioridade", "prazo"],
                "rows": rows,
            },
            alerts=[{"level": "error", "message": "Itens sem alocacao podem travar execucao da obra."}],
            badges=["Suprimentos", "Risco de execucao"],
            actions=[{"label": "Revisar alocacoes", "url": "/engenharia/mapa/", "style": "primary"}],
            links=[{"label": "Tela do mapa", "url": "/engenharia/mapa/"}],
        )

    def _obras_scope_qs(self):
        qs = Obra.objects.filter(ativa=True)
        if self.scope.role == "admin":
            return qs
        if self.scope.project_codes:
            return qs.filter(codigo_sienge__in=self.scope.project_codes)
        return qs.none()

