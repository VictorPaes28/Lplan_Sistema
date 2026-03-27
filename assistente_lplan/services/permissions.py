from dataclasses import dataclass

from accounts.groups import GRUPOS
from core.models import ProjectMember, ProjectOwner
from gestao_aprovacao.models import Approval, WorkOrder, WorkOrderPermission


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

