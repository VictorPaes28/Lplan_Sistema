from dataclasses import dataclass

from accounts.groups import GRUPOS, usuario_tem_acesso_mapa_geografico
from core.models import ProjectMember, ProjectOwner
from gestao_aprovacao.models import Approval, WorkOrder, WorkOrderPermission
from gestao_aprovacao.utils import is_aprovador, is_responsavel_empresa
from trackhub.decorators import user_has_trackhub_access

from assistente_lplan.services.intents import (
    INTENT_ADMISSOES_EM_ANDAMENTO,
    INTENT_ALERTAS_MAPA_GEOGRAFICO,
    INTENT_CONSULTAR_PENDENCIAS_TRACKHUB,
    INTENT_CONSULTAR_RESTRICOES_OBRA,
    INTENT_DESEMPENHO_EQUIPE_GEST,
    INTENT_DOCUMENTOS_VENCENDO_RH,
    INTENT_FILA_ATRASO_APROVACOES,
    INTENT_ITENS_ATRASADOS_SUPRIMENTOS,
    INTENT_LISTAR_AMBIENTES_OPERACIONAIS,
    INTENT_LISTAR_FRENTES_OBRA,
    INTENT_MARCADORES_GPS_RDO,
    INTENT_PANORAMA_MAPA_CONTROLE,
    INTENT_PANORAMA_PIPELINE_SUPRIMENTOS,
    INTENT_PANORAMA_SUPRIMENTOS_GERAL,
    INTENT_PEDIDOS_POR_FRENTE,
    INTENT_PENDENCIAS_VENCIDAS_TRACKHUB,
    INTENT_PRAZOS_CONTRATO_RH,
    INTENT_RESUMO_ALERTAS_RH,
    INTENT_RESUMO_FILA_TRACKHUB,
    INTENT_RESUMO_MAPA_GEOGRAFICO,
    INTENT_RESTRICOES_CRITICAS_ESCOPO,
    INTENT_RESTRICOES_POR_RESPONSAVEL,
)

MODULE_SUPRIMENTOS = "suprimentos"
MODULE_CONTROLE = "controle"
MODULE_APROVACOES = "aprovacoes"
MODULE_MAPA_GEO = "mapa_geo"
MODULE_TRACKHUB = "trackhub"
MODULE_IMPEDIMENTOS = "impedimentos"
MODULE_RH = "rh"

INTENTS_MODULE_PERMISSION: dict[str, str | None] = {
    INTENT_PANORAMA_PIPELINE_SUPRIMENTOS: MODULE_SUPRIMENTOS,
    INTENT_ITENS_ATRASADOS_SUPRIMENTOS: MODULE_SUPRIMENTOS,
    INTENT_PANORAMA_SUPRIMENTOS_GERAL: MODULE_SUPRIMENTOS,
    INTENT_PANORAMA_MAPA_CONTROLE: MODULE_CONTROLE,
    INTENT_LISTAR_AMBIENTES_OPERACIONAIS: MODULE_CONTROLE,
    INTENT_FILA_ATRASO_APROVACOES: MODULE_APROVACOES,
    INTENT_DESEMPENHO_EQUIPE_GEST: MODULE_APROVACOES,
    INTENT_LISTAR_FRENTES_OBRA: MODULE_APROVACOES,
    INTENT_PEDIDOS_POR_FRENTE: MODULE_APROVACOES,
    INTENT_RESUMO_MAPA_GEOGRAFICO: MODULE_MAPA_GEO,
    INTENT_ALERTAS_MAPA_GEOGRAFICO: MODULE_MAPA_GEO,
    INTENT_MARCADORES_GPS_RDO: MODULE_MAPA_GEO,
    INTENT_CONSULTAR_PENDENCIAS_TRACKHUB: MODULE_TRACKHUB,
    INTENT_PENDENCIAS_VENCIDAS_TRACKHUB: MODULE_TRACKHUB,
    INTENT_RESUMO_FILA_TRACKHUB: MODULE_TRACKHUB,
    INTENT_CONSULTAR_RESTRICOES_OBRA: MODULE_IMPEDIMENTOS,
    INTENT_RESTRICOES_CRITICAS_ESCOPO: MODULE_IMPEDIMENTOS,
    INTENT_RESTRICOES_POR_RESPONSAVEL: MODULE_IMPEDIMENTOS,
    INTENT_RESUMO_ALERTAS_RH: MODULE_RH,
    INTENT_ADMISSOES_EM_ANDAMENTO: MODULE_RH,
    INTENT_DOCUMENTOS_VENCENDO_RH: MODULE_RH,
    INTENT_PRAZOS_CONTRATO_RH: MODULE_RH,
}


@dataclass
class UserScope:
    role: str
    project_ids: list[int]
    project_codes: list[str]
    gestao_obra_ids: list[int]
    aprovador_obra_ids: list[int]


class AssistantPermissionService:
    def __init__(self, user):
        self.user = user

    def build_scope(self) -> UserScope:
        if self.user.is_staff or self.user.is_superuser:
            return UserScope(role="admin", project_ids=[], project_codes=[], gestao_obra_ids=[], aprovador_obra_ids=[])

        member_project_ids = list(
            ProjectMember.objects.filter(user=self.user).values_list("project_id", flat=True)
        )
        owner_project_ids = list(
            ProjectOwner.objects.filter(user=self.user).values_list("project_id", flat=True)
        )
        project_ids = sorted(set(member_project_ids + owner_project_ids))

        from core.models import Project

        project_codes = list(Project.objects.filter(id__in=project_ids).values_list("code", flat=True))

        gestao_obra_ids = list(
            WorkOrderPermission.objects.filter(usuario=self.user, ativo=True).values_list("obra_id", flat=True)
        )
        aprovador_obra_ids = list(
            WorkOrderPermission.objects.filter(usuario=self.user, tipo_permissao="aprovador", ativo=True).values_list(
                "obra_id", flat=True
            )
        )

        role = "aprovador" if self.user.groups.filter(name=GRUPOS.APROVADOR).exists() else "engenheiro"
        return UserScope(
            role=role,
            project_ids=project_ids,
            project_codes=project_codes,
            gestao_obra_ids=sorted(set(gestao_obra_ids)),
            aprovador_obra_ids=sorted(set(aprovador_obra_ids)),
        )

    def can_access_project_id(self, project_id: int, scope: UserScope) -> bool:
        if scope.role == "admin":
            return True
        return project_id in set(scope.project_ids)

    def can_access_obra_id(self, obra_id: int, scope: UserScope) -> bool:
        if scope.role == "admin":
            return True
        return obra_id in set(scope.gestao_obra_ids) or obra_id in set(scope.aprovador_obra_ids)

    def allowed_user_ids_for_visibility(self, scope: UserScope) -> set[int]:
        """
        Define quais usuários podem ter métricas consultadas por este usuário.
        Regra segura:
        - admin: todos
        - não-admin: ele mesmo + usuários que compartilham a MESMA obra/projeto no escopo
        """
        if scope.role == "admin":
            from django.contrib.auth.models import User

            return set(User.objects.values_list("id", flat=True))

        allowed = {self.user.id}
        if scope.project_ids:
            allowed.update(ProjectMember.objects.filter(project_id__in=scope.project_ids).values_list("user_id", flat=True))
            allowed.update(ProjectOwner.objects.filter(project_id__in=scope.project_ids).values_list("user_id", flat=True))

        obra_scope = set(scope.gestao_obra_ids) | set(scope.aprovador_obra_ids)
        if obra_scope:
            allowed.update(
                WorkOrderPermission.objects.filter(obra_id__in=obra_scope, ativo=True).values_list(
                    "usuario_id", flat=True
                )
            )
            allowed.update(
                WorkOrder.objects.filter(obra_id__in=obra_scope)
                .exclude(criado_por_id__isnull=True)
                .values_list("criado_por_id", flat=True)
            )
            allowed.update(
                Approval.objects.filter(work_order__obra_id__in=obra_scope)
                .exclude(aprovado_por_id__isnull=True)
                .values_list("aprovado_por_id", flat=True)
            )
        return set(allowed)

    def can_access_module(self, module: str) -> bool:
        user = self.user
        if user.is_staff or user.is_superuser:
            return True
        gs = set(user.groups.values_list("name", flat=True))
        if module == MODULE_SUPRIMENTOS:
            return GRUPOS.ENGENHARIA in gs or GRUPOS.BI_DA_OBRA in gs
        if module == MODULE_CONTROLE:
            return (
                GRUPOS.MAPA_CONTROLE in gs
                or GRUPOS.FERRAMENTA_OPERACIONAL in gs
                or GRUPOS.BI_DA_OBRA in gs
            )
        if module == MODULE_APROVACOES:
            return bool(
                gs
                & {
                    GRUPOS.APROVADOR,
                    GRUPOS.SOLICITANTE,
                    GRUPOS.RESPONSAVEL_EMPRESA,
                    GRUPOS.ADMINISTRADOR,
                }
            )
        if module == MODULE_MAPA_GEO:
            return usuario_tem_acesso_mapa_geografico(user)
        if module == MODULE_TRACKHUB:
            return user_has_trackhub_access(user)
        if module == MODULE_IMPEDIMENTOS:
            return GRUPOS.GESTAO_IMPEDIMENTOS in gs
        if module == MODULE_RH:
            return GRUPOS.RECURSOS_HUMANOS in gs
        return True

    def can_run_intent(self, intent: str) -> bool:
        module = INTENTS_MODULE_PERMISSION.get(intent)
        if not module:
            return True
        if intent == INTENT_FILA_ATRASO_APROVACOES:
            return self.can_access_module(module) and (
                is_aprovador(self.user) or self.user.is_staff or self.user.is_superuser
            )
        if intent == INTENT_DESEMPENHO_EQUIPE_GEST:
            return self.can_access_module(module) and (
                is_responsavel_empresa(self.user)
                or self.user.is_staff
                or self.user.is_superuser
                or self.user.groups.filter(name=GRUPOS.ADMINISTRADOR).exists()
            )
        return self.can_access_module(module)

    def module_label(self, module: str) -> str:
        labels = {
            MODULE_SUPRIMENTOS: "Mapa de Suprimentos",
            MODULE_CONTROLE: "Mapa de Controle / Ferramenta Operacional",
            MODULE_APROVACOES: "GestControll",
            MODULE_MAPA_GEO: "Mapa Geografico",
            MODULE_TRACKHUB: "TrackHub",
            MODULE_IMPEDIMENTOS: "Restricoes (Impeditivos)",
            MODULE_RH: "Recursos Humanos",
        }
        return labels.get(module, module)

