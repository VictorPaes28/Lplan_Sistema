"""
Contexto canônico de frentes (ProjectFront) para todos os módulos LPLAN.

Regras alinhadas ao GestControll e ao Diário:
- Admin/staff/superuser: pode escolher frente específica ou visão consolidada (obra toda).
- Demais usuários: frentes permitidas via ProjectFrontMember; sem vínculo = todas as ativas.
- Obra/projeto sem frentes ativas: módulo opera como legado (sem recorte de frente).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from django.db.models import QuerySet

SESSION_FRONT_BY_PROJECT = 'front_by_project_id'
FRONT_OBRA_TODA = '0'


def usuario_e_admin_frente(user) -> bool:
    if not user or not getattr(user, 'is_authenticated', False):
        return False
    if getattr(user, 'is_superuser', False) or getattr(user, 'is_staff', False):
        return True
    try:
        from accounts.groups import GRUPOS, usuario_tem_administracao_global_na_plataforma

        if usuario_tem_administracao_global_na_plataforma(user):
            return True
        return user.groups.filter(name=GRUPOS.ADMINISTRADOR).exists()
    except Exception:
        return False


def frentes_ativas_disponiveis_para_project(project, user=None) -> QuerySet:
    from core.models import ProjectFront, ProjectFrontMember

    if not project:
        return ProjectFront.objects.none()

    base_qs = ProjectFront.objects.filter(
        project_id=project.pk,
        is_active=True,
    ).order_by('name')

    if user is None:
        return base_qs
    if usuario_e_admin_frente(user):
        return base_qs

    membership_qs = ProjectFrontMember.objects.filter(
        user=user,
        front__project_id=project.pk,
    )
    if not membership_qs.exists():
        return base_qs

    allowed_front_ids = membership_qs.filter(
        is_active=True,
        front__is_active=True,
    ).values_list('front_id', flat=True)
    return base_qs.filter(pk__in=allowed_front_ids)


def project_tem_frentes_ativas(project) -> bool:
    if not project:
        return False
    from core.models import ProjectFront

    return ProjectFront.objects.filter(project_id=project.pk, is_active=True).exists()


def _session_front_map(request) -> dict[str, str]:
    raw = request.session.get(SESSION_FRONT_BY_PROJECT) or {}
    if not isinstance(raw, dict):
        return {}
    return {str(k): str(v) for k, v in raw.items() if k is not None}


def _persist_session_front(request, project_id: int, front_query: str) -> None:
    session_map = _session_front_map(request)
    session_map[str(project_id)] = front_query
    request.session[SESSION_FRONT_BY_PROJECT] = session_map
    request.session.modified = True


def clear_session_front_for_project(request, project_id: int | None) -> None:
    if project_id is None:
        return
    session_map = _session_front_map(request)
    key = str(project_id)
    if key in session_map:
        session_map.pop(key, None)
        request.session[SESSION_FRONT_BY_PROJECT] = session_map
        request.session.modified = True


@dataclass
class FrenteContext:
    project: Any = None
    frentes_disponiveis: list[Any] = field(default_factory=list)
    frente_selecionada: Any | None = None
    tem_frentes_ativas: bool = False
    exibir_seletor_frente: bool = False
    admin_pode_obra_toda: bool = False
    front_query_value: str = ''
    visao_obra_toda: bool = False

    def to_template_context(self) -> dict[str, Any]:
        return {
            'frentes_disponiveis': self.frentes_disponiveis,
            'frente_selecionada': self.frente_selecionada,
            'tem_frentes_ativas': self.tem_frentes_ativas,
            'exibir_seletor_frente': self.exibir_seletor_frente,
            'admin_pode_obra_toda': self.admin_pode_obra_toda,
            'front_filter': self.front_query_value,
            'visao_obra_toda': self.visao_obra_toda,
        }


def resolve_frente_context(
    request,
    project,
    *,
    allow_post: bool = False,
    user=None,
) -> FrenteContext:
    user = user or getattr(request, 'user', None)
    ctx = FrenteContext(project=project)

    if not project:
        return ctx

    frentes_qs = frentes_ativas_disponiveis_para_project(project, user)
    frentes = list(frentes_qs)
    ctx.frentes_disponiveis = frentes
    ctx.tem_frentes_ativas = bool(frentes)
    ctx.exibir_seletor_frente = ctx.tem_frentes_ativas
    ctx.admin_pode_obra_toda = usuario_e_admin_frente(user)

    if not ctx.tem_frentes_ativas:
        return ctx

    param = (request.GET.get('front') or '').strip()
    if not param and allow_post:
        param = (request.POST.get('front') or '').strip()

    session_map = _session_front_map(request)
    session_raw = session_map.get(str(project.pk), '')

    selected = None
    front_q = ''

    def _pick_front(raw_value: str) -> bool:
        nonlocal selected, front_q
        if raw_value == FRONT_OBRA_TODA:
            if not ctx.admin_pode_obra_toda:
                return False
            selected = None
            front_q = FRONT_OBRA_TODA
            ctx.visao_obra_toda = True
            return True
        if not raw_value:
            return False
        try:
            fid = int(raw_value)
        except (TypeError, ValueError):
            return False
        match = next((f for f in frentes if f.pk == fid), None)
        if not match:
            return False
        selected = match
        front_q = str(match.pk)
        ctx.visao_obra_toda = False
        return True

    if param and _pick_front(param):
        pass
    elif session_raw and _pick_front(session_raw):
        pass
    elif not ctx.admin_pode_obra_toda and frentes:
        selected = frentes[0]
        front_q = str(selected.pk)
        ctx.visao_obra_toda = False

    _persist_session_front(request, project.pk, front_q)
    ctx.frente_selecionada = selected
    ctx.front_query_value = front_q
    return ctx


def filter_registros_by_frente_context(qs, frente_ctx: FrenteContext | None):
    """
    Recorta queryset com FK ``front_id`` conforme frente selecionada.

    Registros sem frente (``front_id`` nulo) são da obra inteira e permanecem
    visíveis em qualquer recorte de frente — não é necessário vinculá-los.
    """
    from django.db.models import Q

    if not frente_ctx or not frente_ctx.tem_frentes_ativas:
        return qs
    if frente_ctx.visao_obra_toda:
        return qs
    legado = Q(front_id__isnull=True)
    if frente_ctx.frente_selecionada:
        return qs.filter(legado | Q(front_id=frente_ctx.frente_selecionada.pk))
    allowed_ids = [f.pk for f in frente_ctx.frentes_disponiveis]
    if allowed_ids:
        return qs.filter(legado | Q(front_id__in=allowed_ids))
    return qs.none()


def registro_visivel_no_contexto_frente(registro, frente_ctx: FrenteContext | None) -> bool:
    """True se o registro (com ``front_id``) está visível no contexto de frente atual."""
    if not frente_ctx or not frente_ctx.tem_frentes_ativas:
        return True
    if frente_ctx.visao_obra_toda:
        return True
    front_id = getattr(registro, 'front_id', None)
    if not front_id:
        return True
    if frente_ctx.frente_selecionada:
        return front_id == frente_ctx.frente_selecionada.pk
    allowed_ids = {f.pk for f in frente_ctx.frentes_disponiveis}
    return front_id in allowed_ids


def front_para_novo_registro(frente_ctx: FrenteContext | None):
    """Retorna a frente a gravar em novo registro ou None (consolidado / legado)."""
    if not frente_ctx or not frente_ctx.tem_frentes_ativas:
        return None
    if frente_ctx.visao_obra_toda:
        return None
    return frente_ctx.frente_selecionada


def filter_diaries_by_frente_context(diaries_qs, frente_ctx: FrenteContext):
    """Recorta queryset de ConstructionDiary conforme frente selecionada."""
    return filter_registros_by_frente_context(diaries_qs, frente_ctx)


def append_front_query(params: dict[str, str], frente_ctx: FrenteContext | None) -> dict[str, str]:
    out = dict(params)
    if frente_ctx and frente_ctx.front_query_value:
        out['front'] = frente_ctx.front_query_value
    return out
