from django.conf import settings
from django.db import models


class AuditEvent(models.Model):
    """
    Evento de auditoria genérico (governança, segurança, rastreabilidade administrativa).
    Não substitui o histórico de negócio (ex.: Approval); complementa ações administrativas
    e alterações de escopo que não teriam linha do tempo própria.
    """

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='audit_events_as_actor',
        verbose_name='Quem executou',
    )
    subject_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='audit_events_as_subject',
        verbose_name='Usuário alvo',
        help_text='Preenchido quando a ação incide sobre um usuário (cadastro, permissões, etc.).',
    )
    action_code = models.CharField(
        max_length=80,
        db_index=True,
        verbose_name='Código da ação',
    )
    module = models.CharField(
        max_length=32,
        default='gestao',
        db_index=True,
        verbose_name='Módulo',
        help_text='Ex.: gestao, accounts, core.',
    )
    summary = models.CharField(max_length=500, verbose_name='Resumo')
    payload = models.JSONField(default=dict, blank=True, verbose_name='Detalhes (JSON)')
    ip_address = models.GenericIPAddressField(null=True, blank=True, verbose_name='IP')
    user_agent = models.CharField(max_length=256, blank=True, verbose_name='User-Agent')

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Evento de auditoria'
        verbose_name_plural = 'Eventos de auditoria'
        indexes = [
            models.Index(fields=['subject_user', '-created_at']),
            models.Index(fields=['actor', '-created_at']),
            models.Index(fields=['action_code', '-created_at']),
            models.Index(fields=['module', '-created_at']),
        ]

    def __str__(self):
        return f'{self.action_code} @ {self.created_at:%Y-%m-%d %H:%M}'


class AuditRetentionPolicy(models.Model):
    """
    Reservado para política de retenção/expurgo futuro (Fase 3).
    Tabela mínima hoje permite documentar intenção sem lógica ativa obrigatória.
    """

    key = models.CharField(max_length=64, unique=True)
    description = models.TextField(blank=True)
    retention_days = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text='Dias de retenção sugeridos; None = indefinido / manual.',
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Política de retenção (auditoria)'
        verbose_name_plural = 'Políticas de retenção (auditoria)'

    def __str__(self):
        return self.key
