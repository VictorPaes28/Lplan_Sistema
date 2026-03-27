from datetime import timedelta

from django.contrib.auth.models import User
from django.db.models import Q
from django.utils import timezone

from accounts.models import UserLoginLog
from assistente_lplan.schemas import AssistantResponse
from core.models import ConstructionDiary
from gestao_aprovacao.models import Approval, WorkOrder
from .messages import MessageCatalog


class UsuariosAssistantService:
    def __init__(self, user, scope, permission_service):
        self.user = user
        self.scope = scope
        self.permission_service = permission_service

    def status_usuario(self, entities: dict) -> AssistantResponse:
        target = self._resolve_user(entities)
        if target is False:
            msg = MessageCatalog.resolve("assistant.usuarios.out_of_scope", {"domain": "usuarios"})
            return AssistantResponse(
                summary=msg["text"],
                alerts=[{"level": "error", "message": msg["next_steps"][0]}],
                raw_data={"message_code": msg["code"], "message_kind": msg["kind"]},
            )
        if not target:
            msg = MessageCatalog.resolve("assistant.usuarios.not_identified", {"domain": "usuarios"})
            return AssistantResponse(
                summary=msg["text"],
                alerts=[{"level": "warning", "message": msg["next_steps"][0]}],
                raw_data={"message_code": msg["code"], "message_kind": msg["kind"]},
            )

        since = timezone.now() - timedelta(days=30)
        diaries = ConstructionDiary.objects.filter(created_by=target, created_at__gte=since).count()
        pedidos = WorkOrder.objects.filter(criado_por=target, created_at__gte=since).count()
        aprovacoes = Approval.objects.filter(aprovado_por=target, created_at__gte=since).count()
        logins = UserLoginLog.objects.filter(user=target, created_at__gte=since).count()

        if diaries == 0 and pedidos == 0 and aprovacoes == 0 and logins == 0:
            name = target.get_full_name() or target.username
            msg = MessageCatalog.resolve("assistant.usuarios.empty_30d", {"domain": "usuarios", "usuario": name})
            return AssistantResponse(
                summary=msg["text"],
                badges=["Sem dados suficientes"],
                alerts=[{"level": "info", "message": msg["next_steps"][0]}],
                raw_data={"message_code": msg["code"], "message_kind": msg["kind"]},
            )

        name = target.get_full_name() or target.username
        timeline = [
            {"date": "30 dias", "label": "Logins", "value": str(logins)},
            {"date": "30 dias", "label": "Diarios criados", "value": str(diaries)},
            {"date": "30 dias", "label": "Pedidos criados", "value": str(pedidos)},
            {"date": "30 dias", "label": "Aprovacoes", "value": str(aprovacoes)},
        ]
        badges = ["Usuario", "Ultimos 30 dias", "Ativo" if (logins + diaries + pedidos + aprovacoes) > 3 else "Baixa atividade"]

        return AssistantResponse(
            summary=f"Status operacional de {name} nos ultimos 30 dias.",
            cards=[
                {"title": "Logins", "value": str(logins), "tone": "info"},
                {"title": "Diarios", "value": str(diaries), "tone": "secondary"},
                {"title": "Pedidos", "value": str(pedidos), "tone": "secondary"},
            ],
            timeline=timeline,
            badges=badges,
            actions=[{"label": "Ver desempenho", "url": "/gestao/desempenho-equipe/", "style": "secondary"}],
            links=[{"label": "GestControll - Desempenho", "url": "/gestao/desempenho-equipe/"}],
            raw_data={"user_id": target.id},
        )

    def _resolve_user(self, entities: dict):
        term = (entities.get("usuario") or "").strip()
        if not term:
            return self.user

        if self.scope.role == "admin":
            return User.objects.filter(
                Q(username__icontains=term)
                | Q(first_name__icontains=term)
                | Q(last_name__icontains=term)
                | Q(email__icontains=term)
            ).first()

        allowed_ids = self.permission_service.allowed_user_ids_for_visibility(self.scope)
        user = (
            User.objects.filter(id__in=allowed_ids)
            .filter(
                Q(username__icontains=term)
                | Q(first_name__icontains=term)
                | Q(last_name__icontains=term)
                | Q(email__icontains=term)
            )
            .first()
        )
        if user:
            return user
        return False

