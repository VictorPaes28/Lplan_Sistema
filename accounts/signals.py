"""
Sinais do app accounts.
Registra cada login em UserLoginLog para análise de desempenho.
"""

from django.contrib.auth.signals import user_logged_in
from django.dispatch import receiver

from audit.recording import get_request_client_meta

from .models import UserLoginLog


@receiver(user_logged_in)
def log_user_login(sender, request, user, **kwargs):
    """Cria um registro em UserLoginLog a cada login."""
    try:
        ip, ua = get_request_client_meta(request)
        UserLoginLog.objects.create(user=user, ip_address=ip, user_agent=ua)
    except Exception:
        pass  # Não quebrar o login em caso de falha (ex.: migração pendente)


@receiver(user_logged_in)
def reset_comunicados_sempre_fechou(sender, request, user, **kwargs):
    """
    Comunicados com exibição "Sempre" reabrem após novo login.
    Na mesma sessão, fechou=True continua a esconder (evita modal em loop a cada poll).
    """
    try:
        from comunicados.models import ComunicadoVisualizacao, StatusFinalVisualizacao, TipoExibicao

        ComunicadoVisualizacao.objects.filter(
            usuario=user,
            comunicado__tipo_exibicao=TipoExibicao.SEMPRE,
        ).exclude(status_final=StatusFinalVisualizacao.IGNORADO).update(fechou=False)
    except Exception:
        pass
