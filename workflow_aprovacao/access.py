"""
Regras de acesso à Central de Aprovações (grupos + permissões).
"""
from __future__ import annotations

from accounts.groups import GRUPOS


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
    return bool(
        g
        & {
            GRUPOS.CENTRAL_APROVACOES_ADMIN,
            GRUPOS.CENTRAL_APROVACOES_APROVADOR,
            GRUPOS.CENTRAL_APROVACOES_EXTERNO,
        }
    )


def user_can_configure_workflow(user) -> bool:
    """Configurar fluxos, alçadas e participantes."""
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    if user.has_perm('workflow_aprovacao.configure_approval_flows'):
        return True
    return user.groups.filter(name=GRUPOS.CENTRAL_APROVACOES_ADMIN).exists()


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


def user_should_use_minimal_workflow_shell(user) -> bool:
    """
    UI reduzida: usuário só com perfil Central (sem Diário/Gestão/Mapa/Painel).
    Evita expor atalhos para outros sistemas na própria página do módulo.
    """
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser or user.is_staff:
        return False
    if not user_in_any_workflow_group(user):
        return False
    from accounts.painel_sistema_access import user_is_painel_sistema_admin

    g = _user_groups_set(user)
    has_other = bool(
        g
        & {
            GRUPOS.ADMINISTRADOR,
            GRUPOS.RESPONSAVEL_EMPRESA,
            GRUPOS.APROVADOR,
            GRUPOS.SOLICITANTE,
            GRUPOS.GERENTES,
            GRUPOS.ENGENHARIA,
        }
    )
    if has_other:
        return False
    if user_is_painel_sistema_admin(user):
        return False
    return True
