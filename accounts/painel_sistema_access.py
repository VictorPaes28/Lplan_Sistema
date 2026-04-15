"""
Acesso ao Painel do sistema (URLs em accounts: admin-central, locais-obras, análise, etc.).

Modelo:
  - Superuser: acesso técnico total (ex.: fornecedor/Lplan), inclui /admin/ Django se is_staff.
  - Grupo «Administrador»: administração operacional do cliente (obras, locais, métricas, …)
    sem necessidade de ser superuser nem is_staff.

O Django Admin (/admin/) continua a usar is_staff + permissões; isto é independente.
"""
from __future__ import annotations

from .groups import GRUPOS


def user_is_painel_sistema_admin(user) -> bool:
    """True se o utilizador pode abrir o Painel do sistema e rotas de administração associadas."""
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    return user.groups.filter(name=GRUPOS.ADMINISTRADOR).exists()


def user_can_view_audit_events(user) -> bool:
    """
    Lista de auditoria na Central: administradores do painel (ou superuser) ou
    Responsável Empresa (recorte por empresas sob sua responsabilidade).
    """
    if not user or not user.is_authenticated:
        return False
    if user_is_painel_sistema_admin(user):
        return True
    if not user.groups.filter(name=GRUPOS.RESPONSAVEL_EMPRESA).exists():
        return False
    from gestao_aprovacao.models import Empresa

    return Empresa.objects.filter(responsavel=user, ativo=True).exists()


def user_can_central_obras_diario_e_mapa(user) -> bool:
    """
    Obras do Diário (/projects/), locais do mapa e fluxos equivalentes ao antigo
    «Gerenciar obras» no admin-central: staff/superuser ou grupo Administrador.
    """
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser or user.is_staff:
        return True
    return user.groups.filter(name=GRUPOS.ADMINISTRADOR).exists()
