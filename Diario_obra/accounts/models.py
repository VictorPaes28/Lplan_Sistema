"""
Accounts app - Autenticação e Grupos

Modelos:
- User: padrão Django (django.contrib.auth.models.User).
- UserLoginLog: registro de cada login para análise de desempenho e uso.
"""

from django.db import models
from django.conf import settings


class UserLoginLog(models.Model):
    """Registro de cada login no sistema. Usado para métricas de uso e desempenho."""
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='login_logs',
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Registro de login'
        verbose_name_plural = 'Registros de login'
        indexes = [
            models.Index(fields=['created_at']),
            models.Index(fields=['user', 'created_at']),
        ]

    def __str__(self):
        return f"{self.user.username} em {self.created_at}"
