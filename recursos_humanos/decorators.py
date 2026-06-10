from accounts.decorators import require_group
from accounts.groups import GRUPOS


def require_rh(view_func):
    """Acesso ao módulo DP / Recursos Humanos."""
    return require_group(GRUPOS.RECURSOS_HUMANOS)(view_func)
