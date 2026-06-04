from django.conf import settings
from django.db import models


class UsuarioWhatsApp(models.Model):
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='whatsapp_usuarios',
    )
    telefone = models.CharField(
        max_length=20,
        help_text='Formato E.164, ex.: +5581999999999',
    )
    ativo = models.BooleanField(default=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Usuário WhatsApp'
        verbose_name_plural = 'Usuários WhatsApp'
        ordering = ['-criado_em']

    def __str__(self):
        return f'{self.telefone} ({self.usuario or "sem usuário"})'


class IaMensagemLog(models.Model):
    usuario = models.ForeignKey(
        UsuarioWhatsApp,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='mensagens_log',
    )
    telefone = models.CharField(max_length=20)
    mensagem_recebida = models.TextField()
    intencao_detectada = models.CharField(max_length=100, blank=True)
    funcao_chamada = models.CharField(max_length=100, blank=True)
    resposta_enviada = models.TextField(blank=True)
    status = models.CharField(max_length=20, default='ok')
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Log de mensagem IA'
        verbose_name_plural = 'Logs de mensagens IA'
        ordering = ['-criado_em']

    def __str__(self):
        return f'{self.telefone} — {self.status} ({self.criado_em:%d/%m/%Y %H:%M})'


class IaErroLog(models.Model):
    usuario = models.ForeignKey(
        UsuarioWhatsApp,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='erros_log',
    )
    erro = models.TextField()
    payload_resumido = models.TextField(blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Log de erro IA'
        verbose_name_plural = 'Logs de erros IA'
        ordering = ['-criado_em']

    def __str__(self):
        return f'Erro {self.pk} — {self.criado_em:%d/%m/%Y %H:%M}'


class IaPermissaoConsulta(models.Model):
    usuario = models.OneToOneField(
        UsuarioWhatsApp,
        on_delete=models.CASCADE,
        related_name='permissoes_consulta',
    )
    pode_consultar_rdo = models.BooleanField(default=True)
    pode_consultar_pedidos = models.BooleanField(default=True)
    pode_receber_pdf = models.BooleanField(default=True)
    obras_autorizadas = models.ManyToManyField(
        'mapa_obras.Obra',
        blank=True,
        help_text='Vazio = acesso a todas as obras do usuário.',
    )

    class Meta:
        verbose_name = 'Permissão de consulta IA'
        verbose_name_plural = 'Permissões de consulta IA'

    def __str__(self):
        return f'Permissões — {self.usuario}'
