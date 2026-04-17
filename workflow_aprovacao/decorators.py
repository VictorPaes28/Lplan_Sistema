from functools import wraps

from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
def workflow_login_required(view_fn):
    return login_required(view_fn, login_url='/accounts/login/')


def require_workflow_module_access(view_fn):
    """Apenas quem pertence ao módulo (grupos Central ou superuser)."""

    @wraps(view_fn)
    @workflow_login_required
    def _wrapped(request, *args, **kwargs):
        from workflow_aprovacao.access import user_in_any_workflow_group

        if not user_in_any_workflow_group(request.user):
            return HttpResponseForbidden('Sem acesso à Central de Aprovações.')
        return view_fn(request, *args, **kwargs)

    return _wrapped


def require_workflow_configure(view_fn):
    """Configuração de fluxos."""

    @wraps(view_fn)
    @workflow_login_required
    def _wrapped(request, *args, **kwargs):
        from workflow_aprovacao.access import user_can_configure_workflow

        if not user_can_configure_workflow(request.user):
            return HttpResponseForbidden('Sem permissão para configurar fluxos.')
        return view_fn(request, *args, **kwargs)

    return _wrapped


def require_workflow_act(view_fn):
    """Ações de aprovar/reprovar (além de checagem por etapa no serviço)."""

    @wraps(view_fn)
    @workflow_login_required
    def _wrapped(request, *args, **kwargs):
        from workflow_aprovacao.access import user_can_act_on_workflow_processes

        if not user_can_act_on_workflow_processes(request.user):
            return HttpResponseForbidden('Sem permissão para aprovar ou reprovar.')
        return view_fn(request, *args, **kwargs)

    return _wrapped
