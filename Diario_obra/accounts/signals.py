"""
Sinais do app accounts.
Registra cada login em UserLoginLog para análise de desempenho.
"""

from django.contrib.auth.signals import user_logged_in
from django.dispatch import receiver

from .models import UserLoginLog


@receiver(user_logged_in)
def log_user_login(sender, request, user, **kwargs):
    """Cria um registro em UserLoginLog a cada login."""
    try:
        UserLoginLog.objects.create(user=user)
    except Exception:
        pass  # Não quebrar o login em caso de falha (ex.: migração pendente)
