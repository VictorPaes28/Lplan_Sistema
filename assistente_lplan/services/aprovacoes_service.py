from assistente_lplan.services.obra_entity import obra_display_name, resolve_project_from_entities
from assistente_lplan.schemas import AssistantResponse
from core.contexto_frente import frentes_ativas_disponiveis_para_project
from core.models import Project
from gestao_aprovacao.models import Approval, WorkOrder, WorkOrderPermission
from gestao_aprovacao.services.home_dashboard import (
    collect_aprovador_fila_atraso,
    queryset_workorders_home_scope,
)
from gestao_aprovacao.utils import is_aprovador, is_responsavel_empresa
from django.utils import timezone
from .messages import MessageCatalog


class AprovacoesAssistantService:
    def __init__(self, user, scope):
        self.user = user
        self.scope = scope

    def _resolve_project(self, entities: dict):
        """Alinha ao Diario/Mapa: codigo, nome, sigla ou id de projeto."""
        return resolve_project_from_entities(entities, self.scope, allow_default=False)

    def listar_aprovacoes_pendentes(self, entities: dict) -> AssistantResponse:
        qs = (
            self._work_orders_scope()
            .filter(status="pendente")
            .select_related("obra", "criado_por")
            .order_by("-created_at")
        )

        project = self._resolve_project(entities)
        if project:
            qs = qs.filter(obra__project_id=project.id)

        pending_count = qs.count()
        rows = []
        for wo in list(qs[:30]):
            rows.append(
                {
                    "pedido": wo.codigo,
                    "obra": obra_display_name(wo.obra) if wo.obra else "-",
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

        scope_note = f" na obra {obra_display_name(project)}" if project else " no seu escopo"
        return AssistantResponse(
            summary=f"Existem {pending_count} aprovacoes pendentes{scope_note}.",
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
                    "obra": obra_display_name(item.work_order.obra) if item.work_order and item.work_order.obra else "-",
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

    def fila_atraso(self, entities: dict) -> AssistantResponse:
        if not is_aprovador(self.user) and self.scope.role != "admin":
            return AssistantResponse(
                summary="A fila em atraso e visivel para aprovadores do GestControll.",
                badges=["GestControll"],
                alerts=[{"level": "warning", "message": "Solicite perfil de aprovador ao gestor."}],
            )

        scoped = queryset_workorders_home_scope(self.user)
        project = self._resolve_project(entities)
        if project:
            scoped = scoped.filter(obra__project_id=project.id)

        pedidos = collect_aprovador_fila_atraso(self.user, scoped, limit=30)
        rows = []
        for p in pedidos:
            rows.append(
                {
                    "pedido": p.get("codigo", "-"),
                    "obra": obra_display_name({"name": p.get("obra_nome", "")})[:40] or "-",
                    "dias": str(p.get("dias_na_fila", 0)),
                    "solicitante": (p.get("solicitante") or "-")[:40],
                    "tipo": p.get("tipo_solicitacao_display", p.get("tipo_solicitacao", "-"))[:30],
                }
            )

        if not rows:
            scope_note = f" na obra {obra_display_name(project)}" if project else ""
            return AssistantResponse(
                summary=f"Nenhum pedido ha mais de 7 dias na fila de aprovacao{scope_note}.",
                badges=["GestControll", "Fila OK"],
                alerts=[{"level": "info", "message": "Fila de aprovacao em dia."}],
            )

        return AssistantResponse(
            summary=f"{len(rows)} pedido(s) ha mais de 7 dias aguardando aprovacao.",
            cards=[{"title": "Em atraso", "value": str(len(rows)), "tone": "danger"}],
            table={
                "caption": "Fila de aprovacao em atraso",
                "columns": ["pedido", "obra", "dias", "solicitante", "tipo"],
                "rows": rows,
            },
            badges=["GestControll", "Fila atraso"],
            alerts=[{"level": "error", "message": "Pedidos antigos na fila aumentam risco operacional."}],
            actions=[{"label": "Abrir Pedidos", "url": "/gestao/pedidos/", "style": "primary"}],
        )

    def desempenho_equipe(self, entities: dict) -> AssistantResponse:
        if not (
            is_responsavel_empresa(self.user)
            or self.scope.role == "admin"
            or self.user.groups.filter(name="Administrador").exists()
        ):
            return AssistantResponse(
                summary="Desempenho da equipe e visivel para responsavel da empresa ou administrador.",
                badges=["GestControll"],
            )

        project = self._resolve_project(entities)
        project_ids = self.scope.project_ids if self.scope.role != "admin" else None

        perm_qs = WorkOrderPermission.objects.filter(
            tipo_permissao="aprovador", ativo=True
        ).select_related("usuario", "obra")
        if project:
            perm_qs = perm_qs.filter(obra__project_id=project.id)
        elif project_ids:
            perm_qs = perm_qs.filter(obra__project_id__in=project_ids)

        hoje = timezone.localdate()
        inicio_mes = hoje.replace(day=1)
        rows = []
        seen_users = set()

        for perm in perm_qs[:80]:
            uid = perm.usuario_id
            if uid in seen_users:
                continue
            seen_users.add(uid)
            user = perm.usuario
            nome = user.get_full_name() or user.username
            obra_ids = set(
                WorkOrderPermission.objects.filter(
                    usuario_id=uid, tipo_permissao="aprovador", ativo=True
                ).values_list("obra_id", flat=True)
            )
            pendentes = WorkOrder.objects.filter(
                obra_id__in=obra_ids, status__in=["pendente", "reaprovacao"]
            ).count()
            aprovados_mes = Approval.objects.filter(
                aprovado_por_id=uid,
                decisao="aprovado",
                created_at__date__gte=inicio_mes,
            ).count()
            rows.append(
                {
                    "aprovador": nome[:40],
                    "pendentes": str(pendentes),
                    "aprovados_mes": str(aprovados_mes),
                }
            )
            if len(rows) >= 20:
                break

        if not rows:
            return AssistantResponse(
                summary="Nenhum aprovador encontrado no escopo consultado.",
                badges=["GestControll"],
            )

        return AssistantResponse(
            summary=f"Panorama de {len(rows)} aprovador(es) no GestControll.",
            table={
                "caption": "Desempenho aprovadores (pendentes agora / aprovados no mes)",
                "columns": ["aprovador", "pendentes", "aprovados_mes"],
                "rows": rows,
            },
            badges=["GestControll", "Desempenho"],
            actions=[{"label": "Abrir Desempenho", "url": "/gestao/desempenho-equipe/", "style": "primary"}],
        )

    def listar_frentes(self, entities: dict) -> AssistantResponse:
        project = self._resolve_project(entities)
        if not project:
            return AssistantResponse(
                summary="Informe a obra para listar frentes ativas.",
                badges=["GestControll", "Frentes"],
            )

        frentes = frentes_ativas_disponiveis_para_project(project)
        rows = []
        for front in frentes[:30]:
            pendentes = WorkOrder.objects.filter(obra__project_id=project.id, front_id=front.id).filter(
                status__in=["pendente", "reaprovacao"]
            ).count()
            rows.append(
                {
                    "frente": front.name[:50],
                    "ativa": "sim" if front.is_active else "nao",
                    "pedidos_pendentes": str(pendentes),
                }
            )

        if not rows:
            return AssistantResponse(
                summary=f"Obra {obra_display_name(project)}: nenhuma frente ativa cadastrada.",
                badges=["GestControll"],
            )

        return AssistantResponse(
            summary=f"{len(rows)} frente(s) ativa(s) na obra {obra_display_name(project)}.",
            table={
                "caption": "Frentes da obra",
                "columns": ["frente", "ativa", "pedidos_pendentes"],
                "rows": rows,
            },
            badges=["GestControll", "Frentes", obra_display_name(project)],
            actions=[{"label": "Abrir Pedidos", "url": "/gestao/pedidos/", "style": "primary"}],
        )

    def pedidos_por_frente(self, entities: dict) -> AssistantResponse:
        project = self._resolve_project(entities)
        frente_term = (entities.get("frente") or entities.get("obra") or "").strip()
        if not project:
            return AssistantResponse(
                summary="Informe a obra e a frente para listar pedidos.",
                badges=["GestControll"],
            )

        frentes = frentes_ativas_disponiveis_para_project(project)
        front = None
        if frente_term:
            front = frentes.filter(name__icontains=frente_term).first()
        if not front and entities.get("frente_id"):
            try:
                front = frentes.filter(pk=int(entities["frente_id"])).first()
            except (TypeError, ValueError):
                pass

        if not front:
            nomes = list(frentes.values_list("name", flat=True)[:10])
            return AssistantResponse(
                summary=f"Nao identifiquei a frente na obra {obra_display_name(project)}.",
                suggested_replies=[
                    f"Pedidos pendentes na frente {n} obra {obra_display_name(project)}" for n in nomes[:5]
                ],
                badges=["GestControll", "Frentes"],
            )

        qs = (
            self._work_orders_scope()
            .filter(obra__project_id=project.id, front_id=front.id)
            .select_related("criado_por")
            .order_by("-created_at")[:30]
        )
        rows = []
        for wo in qs:
            rows.append(
                {
                    "pedido": wo.codigo,
                    "status": wo.get_status_display(),
                    "solicitante": (wo.criado_por.get_full_name() or wo.criado_por.username) if wo.criado_por else "-",
                    "data": wo.created_at.strftime("%d/%m/%Y"),
                }
            )

        return AssistantResponse(
            summary=f"{len(rows)} pedido(s) na frente {front.name} (obra {obra_display_name(project)}).",
            table={
                "caption": f"Pedidos — frente {front.name}",
                "columns": ["pedido", "status", "solicitante", "data"],
                "rows": rows,
            },
            badges=["GestControll", front.name[:30]],
            actions=[{"label": "Abrir Pedidos", "url": "/gestao/pedidos/", "style": "primary"}],
        )

