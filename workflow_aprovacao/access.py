"""
Regras de acesso à Central de Aprovações (grupos + permissões).
"""
from __future__ import annotations

from django.db.models import Q

from accounts.groups import (
    ADMINISTRADOR_GLOBAL_GROUP_NAMES,
    GRUPOS,
    usuario_tem_administracao_global_na_plataforma,
)
from workflow_aprovacao.models import (
    ApprovalHistoryEntry,
    ApprovalProcessParticipant,
    ApprovalStepParticipant,
    ParticipantRole,
    SubjectKind,
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


def user_can_view_workflow_geolocation(user) -> bool:
    """Localização registrada na assinatura — visível apenas para administradores da Central."""
    return user_can_configure_workflow(user)


def user_can_act_on_workflow_processes(user) -> bool:
    """Pode usar ações de aprovar/reprovar (ainda exige participação na alçada atual)."""
    if not user or not user.is_authenticated:
        return False
    if user.has_perm('workflow_aprovacao.act_on_approval_process'):
        return True
    return user.groups.filter(
        name__in=(
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


def user_is_process_participant(user, process) -> bool:
    """Participante em alguma alçada do fluxo (usuário ou grupo Django)."""
    if not user or not user.is_authenticated or not process or not process.flow_definition_id:
        return False
    group_ids = list(user.groups.values_list('pk', flat=True))
    roles = (ParticipantRole.APPROVER, ParticipantRole.OWNER, ParticipantRole.VIEWER)
    effective_user_q = Q(
        process=process,
        subject_kind=SubjectKind.USER,
        user=user,
        role__in=roles,
    )
    effective_group_q = Q()
    if group_ids:
        effective_group_q = Q(
            process=process,
            subject_kind=SubjectKind.DJANGO_GROUP,
            django_group_id__in=group_ids,
            role__in=roles,
        )
    if ApprovalProcessParticipant.objects.filter(effective_user_q | effective_group_q).exists():
        return True
    user_q = Q(
        step__flow_id=process.flow_definition_id,
        subject_kind=SubjectKind.USER,
        user=user,
        role__in=roles,
    )
    group_q = Q()
    if group_ids:
        group_q = Q(
            step__flow_id=process.flow_definition_id,
            subject_kind=SubjectKind.DJANGO_GROUP,
            django_group_id__in=group_ids,
            role__in=roles,
        )
    return ApprovalStepParticipant.objects.filter(user_q | group_q).exists()


def user_is_approver_on_current_step(user, process) -> bool:
    """Aprovador/responsável na alçada atual (regra usada na fila e nas ações)."""
    from workflow_aprovacao.services.step_access import user_can_decide_on_process

    return user_can_decide_on_process(user, process)


def user_can_view_process(user, process) -> bool:
    """
    Leitura de detalhe/anexos: admin configurador vê tudo; demais só se envolvidos no processo.
    """
    if not user or not user.is_authenticated or not process:
        return False
    if user.is_superuser or user_can_configure_workflow(user):
        return True
    if ApprovalHistoryEntry.objects.filter(process=process, actor=user).exists():
        return True
    if user_is_process_participant(user, process):
        return True
    return False


def user_can_see_central_monitoring_queue(user) -> bool:
    """Visão geral de processos aguardando (configurador da Central)."""
    return user_can_configure_workflow(user)
