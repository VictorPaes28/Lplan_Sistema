"""
Resolução padronizada de contexto de obra (mapa_obras.Obra) + frente para módulos satélite.

Uso recomendado em qualquer módulo novo:

    from mapa_obras.contexto_obra import resolve_obra_context

    ctx = resolve_obra_context(request, allow_post=True)
    context = {
        ...
        **ctx.to_template_context(),
    }

Parâmetros de URL:
- ``?obra=<id>`` — obra ativa (sessão ``obra_id``)
- ``?front=<id>`` — frente ativa quando a obra tem frentes (sessão ``front_by_project_id``)
- ``?front=0`` — visão consolidada da obra (somente admin/staff)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from core.contexto_frente import (
    FrenteContext,
    clear_session_front_for_project,
    resolve_frente_context,
)
from mapa_obras.models import Obra
from mapa_obras.views import _get_obras_for_user, _user_can_access_obra


@dataclass
class ModuloObraContext:
    obras: Any
    obra: Obra | None = None
    frente: FrenteContext = field(default_factory=FrenteContext)

    @property
    def project(self):
        obra = self.obra
        return getattr(obra, 'project', None) if obra else None

    def to_template_context(self) -> dict[str, Any]:
        data = {
            'obras': self.obras,
            'obra_selecionada': self.obra,
            'obra_atual': self.obra,
            'ctx_obra': self.obra,
        }
        data.update(self.frente.to_template_context())
        return data

    def __iter__(self):
        """Compatibilidade: ``obras, obra = resolve_obra_context(request)``."""
        yield self.obras
        yield self.obra


def resolve_obra_context(request, *, allow_post=False, with_front=True) -> ModuloObraContext:
    """
    Resolve obra no padrão único:
    1) querystring (?obra=)
    2) POST (quando allow_post=True)
    3) sessão (obra_id)
    4) primeira obra permitida

    Com ``with_front=True``, também resolve frente do projeto vinculado à obra.
    """
    obras = _get_obras_for_user(request)
    obra = None
    previous_project_id = None
    previous_obra_id = request.session.get('obra_id')
    if previous_obra_id:
        try:
            previous_obra = Obra.objects.filter(pk=int(previous_obra_id)).only('project_id').first()
            previous_project_id = getattr(previous_obra, 'project_id', None)
        except (TypeError, ValueError):
            previous_project_id = None

    obra_param = request.GET.get('obra')
    if not obra_param and allow_post:
        obra_param = request.POST.get('obra')

    if obra_param:
        try:
            obra = Obra.objects.get(id=int(obra_param), ativa=True)
            if not _user_can_access_obra(request, obra):
                obra = None
        except (Obra.DoesNotExist, ValueError, TypeError):
            obra = None

    if not obra:
        obra_sessao_id = request.session.get('obra_id')
        if obra_sessao_id:
            try:
                obra = Obra.objects.get(id=int(obra_sessao_id), ativa=True)
                if not _user_can_access_obra(request, obra):
                    obra = None
            except (Obra.DoesNotExist, ValueError, TypeError):
                obra = None

    if not obra:
        obra = obras.first()

    if obra:
        request.session['obra_id'] = obra.id
        request.session.modified = True
        if with_front and previous_project_id and obra.project_id != previous_project_id:
            clear_session_front_for_project(request, previous_project_id)

    frente_ctx = FrenteContext()
    if with_front and obra and obra.project_id:
        frente_ctx = resolve_frente_context(
            request,
            obra.project,
            allow_post=allow_post,
            user=request.user,
        )

    return ModuloObraContext(obras=obras, obra=obra, frente=frente_ctx)
