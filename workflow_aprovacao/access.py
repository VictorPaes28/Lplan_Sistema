"""
Regras de acesso à Central de Aprovações (grupos + permissões).
"""
from __future__ import annotations

from accounts.groups import (
    ADMINISTRADOR_GLOBAL_GROUP_NAMES,
    GRUPOS,
    usuario_tem_administracao_global_na_plataforma,
)


def _user_groups_set(user):
    if not user or not user.is_authenticated:
        return frozenset()
    return frozenset(user.groups.values_list('name', flat=True))


def user_in_any_workflow_group(user) -> bool:
    """Pode abrir o módulo /aprovacoes/ (painel mínimo)."""
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    g = _user_groups_set(user)
    workflow_groups = {
        *ADMINISTRADOR_GLOBAL_GROUP_NAMES,
        GRUPOS.CENTRAL_APROVACOES_ADMIN,
        GRUPOS.CENTRAL_APROVACOES_APROVADOR,
        GRUPOS.CENTRAL_APROVACOES_EXTERNO,
    }
    return bool(g & workflow_groups)


def user_can_configure_workflow(user) -> bool:
    """Configurar fluxos, alçadas e participantes."""
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    if user.has_perm('workflow_aprovacao.configure_approval_flows'):
        return True
    return usuario_tem_administracao_global_na_plataforma(user)


def user_can_act_on_workflow_processes(user) -> bool:
    """Pode aprovar/reprovar quando for participante da alçada."""
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    if user.has_perm('workflow_aprovacao.act_on_approval_process'):
        return True
    return user.groups.filter(
        name__in=(
            *ADMINISTRADOR_GLOBAL_GROUP_NAMES,
            GRUPOS.CENTRAL_APROVACOES_ADMIN,
            GRUPOS.CENTRAL_APROVACOES_APROVADOR,
            GRUPOS.CENTRAL_APROVACOES_EXTERNO,
        )
    ).exists()


def user_is_external_workflow_profile(user) -> bool:
    """Perfil voltado a terceiros (grupo Externo)."""
    if not user or not user.is_authenticated:
        return False
    return user.groups.filter(name=GRUPOS.CENTRAL_APROVACOES_EXTERNO).exists()


def _workflow_group_names():
    """Nomes dos grupos que abrem apenas o módulo Central de Aprovações (/aprovacoes/)."""
    return frozenset(
        (
            *ADMINISTRADOR_GLOBAL_GROUP_NAMES,
            GRUPOS.CENTRAL_APROVACOES_ADMIN,
            GRUPOS.CENTRAL_APROVACOES_APROVADOR,
            GRUPOS.CENTRAL_APROVACOES_EXTERNO,
        )
    )


def user_should_use_minimal_workflow_shell(user) -> bool:
    """
    UI reduzida: usuário com **somente** papéis típicos da Central de Aprovações (/aprovacoes/),
    sem administrador global nem outros módulos relevantes (Diário, GestControll, TrackHub, …).
    """
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser or user.is_staff:
        return False
    if not user_in_any_workflow_group(user):
        return False
    from accounts.painel_sistema_access import user_is_painel_sistema_admin

    g = _user_groups_set(user)
    if g - _workflow_group_names():
        return False
    if user_is_painel_sistema_admin(user):
        return False
    return True
