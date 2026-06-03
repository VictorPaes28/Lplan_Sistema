"""
Bloqueia acesso a módulos integrados marcados como inativos no Painel do sistema.
Administradores do painel podem entrar para corrigir e reativar.
"""
from django.shortcuts import redirect
from django.urls import reverse

from accounts.modulos_integrados import modulo_esta_ativo, resolve_modulo_from_path
from accounts.painel_sistema_access import user_is_painel_sistema_admin


class ModuloIntegradoManutencaoMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        block = self._blocked_redirect(request)
        if block is not None:
            return block
        return self.get_response(request)

    def _blocked_redirect(self, request):
        user = getattr(request, 'user', None)
        if not user or not user.is_authenticated:
            return None
        if user_is_painel_sistema_admin(user):
            return None

        codigo = resolve_modulo_from_path(request.path)
        if not codigo or modulo_esta_ativo(codigo):
            return None

        unavailable = reverse('accounts:modulo_indisponivel', kwargs={'codigo': codigo})
        if request.path.startswith(unavailable):
            return None
        return redirect(unavailable)
