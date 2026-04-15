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
    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True,
        verbose_name='IP',
    )
    user_agent = models.CharField(
        max_length=256,
        blank=True,
        verbose_name='User-Agent',
    )

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


class UserSignupRequest(models.Model):
    """Solicitação de novo usuário com aprovação manual."""

    STATUS_PENDENTE = 'pendente'
    STATUS_APROVADO = 'aprovado'
    STATUS_REJEITADO = 'rejeitado'
    STATUS_CHOICES = [
        (STATUS_PENDENTE, 'Pendente'),
        (STATUS_APROVADO, 'Aprovado'),
        (STATUS_REJEITADO, 'Rejeitado'),
    ]

    ORIGEM_AUTO = 'auto'
    ORIGEM_INTERNO = 'interno'
    ORIGEM_CHOICES = [
        (ORIGEM_AUTO, 'Auto cadastro'),
        (ORIGEM_INTERNO, 'Cadastro interno'),
    ]

    full_name = models.CharField(max_length=255, verbose_name='Nome completo')
    email = models.EmailField(db_index=True, verbose_name='E-mail')
    username_suggestion = models.CharField(
        max_length=150,
        blank=True,
        verbose_name='Sugestão de usuário',
    )
    requested_groups = models.JSONField(default=list, blank=True, verbose_name='Grupos solicitados')
    requested_project_ids = models.JSONField(default=list, blank=True, verbose_name='Projetos solicitados')
    notes = models.TextField(blank=True, verbose_name='Observações')

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_PENDENTE,
        db_index=True,
        verbose_name='Status',
    )
    origem = models.CharField(
        max_length=20,
        choices=ORIGEM_CHOICES,
        default=ORIGEM_AUTO,
        db_index=True,
        verbose_name='Origem da solicitação',
    )

    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='signup_requests_created',
        verbose_name='Solicitado por',
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='signup_requests_approved',
        verbose_name='Aprovado por',
    )
    approved_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='signup_request_origin',
        verbose_name='Usuário criado',
    )
    approved_at = models.DateTimeField(null=True, blank=True, verbose_name='Aprovado em')
    rejected_at = models.DateTimeField(null=True, blank=True, verbose_name='Rejeitado em')
    rejection_reason = models.TextField(blank=True, verbose_name='Motivo da rejeição')
    created_at = models.DateTimeField(auto_now_add=True, db_index=True, verbose_name='Criado em')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Atualizado em')

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Solicitação de cadastro'
        verbose_name_plural = 'Solicitações de cadastro'
        indexes = [
            models.Index(fields=['status', '-created_at']),
            models.Index(fields=['email', 'status']),
        ]

    def __str__(self):
        return f"{self.full_name} ({self.email}) - {self.status}"
