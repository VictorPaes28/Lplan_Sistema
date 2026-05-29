"""
Modelos da camada transversal de comunicação (e-mail / notificação interna).
"""
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class TipoComunicacao(models.Model):
    """Catálogo de tipos de comunicação do sistema."""

    CATEGORIA_CHOICES = [
        ('critico', 'Crítico'),
        ('operacional_acao', 'Operacional — ação'),
        ('operacional_acompanhamento', 'Operacional — acompanhamento'),
        ('informativo', 'Informativo'),
        ('auditoria_log', 'Auditoria / log'),
    ]

    CRITICIDADE_CHOICES = [
        ('critico', 'Crítico'),
        ('operacional', 'Operacional'),
        ('informativo', 'Informativo'),
    ]

    codigo = models.CharField(
        max_length=120,
        unique=True,
        verbose_name='Código',
        help_text='Identificador estável (ex.: gestcontroll.pedido_aprovado.copia_administrativa)',
    )
    nome = models.CharField(max_length=200, verbose_name='Nome')
    modulo = models.CharField(max_length=60, verbose_name='Módulo', db_index=True)
    descricao = models.TextField(blank=True, verbose_name='Descrição')
    categoria = models.CharField(max_length=40, choices=CATEGORIA_CHOICES, verbose_name='Categoria')
    criticidade = models.CharField(max_length=20, choices=CRITICIDADE_CHOICES, verbose_name='Criticidade')

    email_padrao = models.BooleanField(default=True, verbose_name='E-mail ativo por padrão')
    interno_padrao = models.BooleanField(default=False, verbose_name='Notificação interna por padrão')
    resumo_padrao = models.BooleanField(default=False, verbose_name='Resumo por padrão')

    permite_usuario_desativar_email = models.BooleanField(
        default=False,
        verbose_name='Usuário pode desativar e-mail',
    )
    permite_admin_desativar_email = models.BooleanField(
        default=True,
        verbose_name='Admin pode desativar e-mail',
    )
    permite_usuario_alterar_interno = models.BooleanField(
        default=False,
        verbose_name='Usuário pode alterar notificação interna',
    )
    permite_resumo = models.BooleanField(default=False, verbose_name='Permite resumo diário/semanal')
    obrigatorio = models.BooleanField(
        default=False,
        verbose_name='Obrigatório',
        help_text='Se marcado, e-mail não pode ser bloqueado por preferência.',
    )
    ativo = models.BooleanField(default=True, verbose_name='Ativo')
    ordem = models.PositiveSmallIntegerField(default=0, verbose_name='Ordem de exibição')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Tipo de comunicação'
        verbose_name_plural = 'Tipos de comunicação'
        ordering = ['modulo', 'ordem', 'nome']

    def __str__(self):
        return self.nome

    @property
    def modulo_label(self):
        from core.comunicacao_constants import MODULO_LABELS
        return MODULO_LABELS.get(self.modulo, self.modulo)


class PreferenciaComunicacao(models.Model):
    """Preferência por usuário ou e-mail livre."""

    tipo = models.ForeignKey(
        TipoComunicacao,
        on_delete=models.CASCADE,
        related_name='preferencias',
        verbose_name='Tipo',
    )
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='preferencias_comunicacao',
        verbose_name='Usuário',
    )
    email = models.EmailField(
        blank=True,
        default='',
        verbose_name='E-mail (sem usuário)',
        help_text='Para destinatários que não são usuários do sistema.',
    )

    email_ativo = models.BooleanField(null=True, blank=True, verbose_name='E-mail imediato')
    interno_ativo = models.BooleanField(null=True, blank=True, verbose_name='Notificação interna')
    resumo_ativo = models.BooleanField(null=True, blank=True, verbose_name='Resumo')
    herdar_padrao = models.BooleanField(
        default=True,
        verbose_name='Herdar padrão',
        help_text='Se marcado, usa padrão do tipo/grupo (comportamento atual).',
    )
    bloqueado_por_admin = models.BooleanField(
        default=False,
        verbose_name='Bloqueado por admin',
    )
    observacao = models.CharField(max_length=500, blank=True, default='', verbose_name='Observação')

    atualizado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='preferencias_comunicacao_atualizadas',
        verbose_name='Atualizado por',
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Preferência de comunicação'
        verbose_name_plural = 'Preferências de comunicação'
        constraints = [
            models.UniqueConstraint(
                fields=['tipo', 'usuario'],
                condition=models.Q(usuario__isnull=False),
                name='core_prefcom_unique_tipo_usuario',
            ),
            models.UniqueConstraint(
                fields=['tipo', 'email'],
                condition=models.Q(email__gt=''),
                name='core_prefcom_unique_tipo_email',
            ),
        ]
        indexes = [
            models.Index(fields=['email']),
            models.Index(fields=['tipo', 'usuario']),
        ]

    def __str__(self):
        alvo = self.usuario.username if self.usuario_id else self.email
        return f'{alvo} — {self.tipo.codigo}'

    def clean(self):
        if not self.usuario_id and not (self.email or '').strip():
            raise ValidationError('Informe um usuário ou um endereço de e-mail.')
        if self.usuario_id and (self.email or '').strip():
            raise ValidationError('Use usuário OU e-mail livre, não ambos na mesma preferência.')

    def save(self, *args, **kwargs):
        if self.email:
            self.email = self.email.strip().lower()
        self.full_clean()
        super().save(*args, **kwargs)


class PadraoComunicacaoGrupo(models.Model):
    """Padrão de comunicação por grupo Django (perfil)."""

    grupo = models.ForeignKey(
        'auth.Group',
        on_delete=models.CASCADE,
        related_name='padroes_comunicacao',
        verbose_name='Grupo',
    )
    tipo = models.ForeignKey(
        TipoComunicacao,
        on_delete=models.CASCADE,
        related_name='padroes_grupo',
        verbose_name='Tipo',
    )
    email_ativo = models.BooleanField(null=True, blank=True, verbose_name='E-mail')
    interno_ativo = models.BooleanField(null=True, blank=True, verbose_name='Interno')
    resumo_ativo = models.BooleanField(null=True, blank=True, verbose_name='Resumo')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Padrão de comunicação por grupo'
        verbose_name_plural = 'Padrões de comunicação por grupo'
        unique_together = [['grupo', 'tipo']]

    def __str__(self):
        return f'{self.grupo.name} — {self.tipo.codigo}'


class LogDecisaoComunicacao(models.Model):
    """Registro de decisão do router antes/durante envio."""

    CANAL_CHOICES = [
        ('email', 'E-mail'),
        ('interno', 'Notificação interna'),
        ('resumo', 'Resumo'),
    ]

    DECISAO_CHOICES = [
        ('enviar', 'Enviar'),
        ('bloquear', 'Bloquear'),
        ('resumo', 'Encaminhar para resumo'),
        ('interno', 'Somente interno'),
    ]

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='logs_decisao_comunicacao',
        verbose_name='Usuário',
    )
    email = models.EmailField(max_length=254, blank=True, default='', db_index=True)
    tipo = models.ForeignKey(
        TipoComunicacao,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='logs_decisao',
        verbose_name='Tipo',
    )
    tipo_codigo = models.CharField(max_length=120, blank=True, default='', db_index=True)
    modulo = models.CharField(max_length=60, blank=True, default='', db_index=True)
    canal = models.CharField(max_length=20, choices=CANAL_CHOICES, default='email')
    decisao = models.CharField(max_length=20, choices=DECISAO_CHOICES)
    motivo = models.CharField(max_length=120, verbose_name='Motivo')
    origem_destinatario = models.CharField(
        max_length=120,
        blank=True,
        default='',
        help_text='Ex.: aprovador, lista_fixa, env, preferencia_usuario',
    )
    objeto_tipo = models.CharField(max_length=80, blank=True, default='')
    objeto_id = models.CharField(max_length=64, blank=True, default='')
    contexto_json = models.JSONField(default=dict, blank=True)

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = 'Log de decisão de comunicação'
        verbose_name_plural = 'Logs de decisão de comunicação'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['-created_at', 'decisao']),
            models.Index(fields=['modulo', '-created_at']),
        ]

    def __str__(self):
        alvo = self.email or (self.usuario.username if self.usuario_id else '?')
        return f'{self.decisao} — {alvo} — {self.tipo_codigo or self.motivo}'
