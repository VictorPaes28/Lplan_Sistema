from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone

from mapa_obras.models import Obra


class Pendencia(models.Model):
    TIPO_CHOICES = [
        ("financeiro", "Financeiro"),
        ("operacional", "Operacional"),
        ("documento", "Documento"),
        ("tarefa", "Tarefa"),
        ("outro", "Outro"),
    ]
    STATUS_CHOICES = [
        ("aberta", "Aberta"),
        ("em_andamento", "Em andamento"),
        ("aguardando", "Aguardando"),
        ("concluida", "Concluída"),
        ("cancelada", "Cancelada"),
    ]
    PRIORIDADE_CHOICES = [
        ("urgente", "Urgente"),
        ("alta", "Alta"),
        ("normal", "Normal"),
        ("baixa", "Baixa"),
    ]
    ORIGEM_CHOICES = [
        ("manual", "Manual"),
        ("sienge", "Sienge"),  # preparado para o futuro
    ]

    obra = models.ForeignKey(Obra, on_delete=models.CASCADE, related_name="pendencias")
    titulo = models.CharField(max_length=200)
    descricao = models.TextField(blank=True)
    tipo = models.CharField(max_length=100, choices=TIPO_CHOICES, default="outro")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="aberta")
    prioridade = models.CharField(max_length=10, choices=PRIORIDADE_CHOICES, default="normal")
    prazo = models.DateField(null=True, blank=True)
    # Série recorrente à qual esta pendência pertence (template de etapas em PendenciaRecorrente.etapas_snapshot).
    recorrencia_serie = models.ForeignKey(
        "PendenciaRecorrente",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="pendencias_serie",
    )
    origem = models.CharField(max_length=10, choices=ORIGEM_CHOICES, default="manual")
    criado_por = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, related_name="pendencias_criadas"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Pendência"
        verbose_name_plural = "Pendências"

    def __str__(self):
        return f"{self.titulo} — {self.obra.nome}"

    @property
    def status_normalizado(self) -> str:
        return (self.status or "").strip().lower()

    @property
    def encerrada_na_fila(self) -> bool:
        """Concluída ou cancelada (fila e estilo de prazo)."""
        return self.status_normalizado in ("concluida", "cancelada")

    @property
    def esta_vencida(self):
        hoje = timezone.localdate()
        return (
            self.prazo
            and self.prazo < hoje
            and not self.encerrada_na_fila
        )

    @property
    def etapa_atual(self):
        return self.etapas.filter(status="pendente").order_by("ordem").first()


class AtividadePendencia(models.Model):
    """Histórico de alterações e eventos da pendência (TrackHub)."""

    TIPO_CRIACAO = "criacao"
    TIPO_TITULO = "titulo"
    TIPO_DESCRICAO = "descricao"
    TIPO_STATUS = "status"
    TIPO_PRIORIDADE = "prioridade"
    TIPO_PRAZO = "prazo"
    TIPO_TIPO = "tipo"
    TIPO_ETAPA = "etapa"
    TIPO_COMENTARIO = "comentario"
    TIPO_ARQUIVO = "arquivo"
    TIPO_GERAL = "geral"

    TIPO_CHOICES = [
        (TIPO_CRIACAO, "Criação"),
        (TIPO_TITULO, "Título"),
        (TIPO_DESCRICAO, "Descrição"),
        (TIPO_STATUS, "Status"),
        (TIPO_PRIORIDADE, "Prioridade"),
        (TIPO_PRAZO, "Prazo"),
        (TIPO_TIPO, "Tipo"),
        (TIPO_ETAPA, "Etapa"),
        (TIPO_COMENTARIO, "Comentário"),
        (TIPO_ARQUIVO, "Arquivo"),
        (TIPO_GERAL, "Geral"),
    ]

    pendencia = models.ForeignKey(
        Pendencia,
        on_delete=models.CASCADE,
        related_name="atividades",
    )
    usuario = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="atividades_pendencia_trackhub",
    )
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES, default=TIPO_GERAL)
    descricao = models.TextField()
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-criado_em"]
        verbose_name = "Atividade da pendência"
        verbose_name_plural = "Atividades da pendência"

    def __str__(self):
        return f"{self.pendencia_id} — {self.descricao[:50]}"


class EtapaPendencia(models.Model):
    STATUS_CHOICES = [
        ("pendente", "Pendente"),
        ("concluida", "Concluída"),
    ]

    pendencia = models.ForeignKey(
        Pendencia, on_delete=models.CASCADE, related_name="etapas"
    )
    titulo = models.CharField(max_length=200)
    ordem = models.PositiveIntegerField(default=0)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="pendente")

    # Responsável interno (usuário do sistema)
    responsavel_interno = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="etapas_responsavel",
    )

    prazo = models.DateField(null=True, blank=True)
    concluida_em = models.DateTimeField(null=True, blank=True)
    concluida_por = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="etapas_concluidas",
    )
    observacao = models.TextField(blank=True)
    requer_assinatura = models.BooleanField(default=False)

    class Meta:
        ordering = ["ordem"]
        verbose_name = "Etapa"
        verbose_name_plural = "Etapas"

    def __str__(self):
        return f"{self.titulo} — {self.pendencia.titulo}"

    @property
    def responsavel_nome(self):
        if self.responsavel_interno:
            return (
                self.responsavel_interno.get_full_name()
                or self.responsavel_interno.username
            )
        return "—"

    @property
    def responsavel_whatsapp(self):
        u = self.responsavel_interno
        if not u:
            return ""
        from gestao_aprovacao.models import UserProfile

        tel = UserProfile.objects.filter(usuario_id=u.pk).values_list(
            "telefone", flat=True
        ).first()
        return (tel or "").strip()

    @property
    def responsavel_email(self):
        if self.responsavel_interno:
            return (self.responsavel_interno.email or "").strip()
        return ""

    @property
    def esta_vencida(self):
        from datetime import date

        return self.prazo and self.prazo < date.today() and self.status == "pendente"


class NotificacaoPendencia(models.Model):
    CANAL_CHOICES = [
        ("whatsapp", "WhatsApp"),
        ("email", "E-mail"),
    ]

    etapa = models.ForeignKey(
        EtapaPendencia, on_delete=models.CASCADE, related_name="notificacoes"
    )
    enviado_por = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, related_name="notificacoes_enviadas"
    )
    canal = models.CharField(max_length=10, choices=CANAL_CHOICES)
    destinatario_nome = models.CharField(max_length=200)
    destinatario_contato = models.CharField(max_length=200)  # número ou email
    mensagem = models.TextField()
    enviado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-enviado_em"]
        verbose_name = "Notificação"
        verbose_name_plural = "Notificações"


class ComentarioPendencia(models.Model):
    pendencia = models.ForeignKey(
        Pendencia, on_delete=models.CASCADE, related_name="comentarios"
    )
    autor = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    texto = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]
        verbose_name = "Comentário"
        verbose_name_plural = "Comentários"


class AssinaturaEtapa(models.Model):
    etapa = models.OneToOneField(
        EtapaPendencia, on_delete=models.CASCADE, related_name="assinatura"
    )
    signature_data = models.TextField(blank=True)
    assinado_por = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assinaturas_trackhub",
    )
    assinado_em = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Assinatura de Etapa"
        verbose_name_plural = "Assinaturas de Etapas"


class AnexoPendencia(models.Model):
    TIPO_CHOICES = [
        ("imagem", "Imagem"),
        ("documento", "Documento"),
        ("outro", "Outro"),
    ]

    pendencia = models.ForeignKey(
        Pendencia, on_delete=models.CASCADE, related_name="anexos"
    )
    arquivo = models.FileField(
        upload_to="trackhub/anexos/%Y/%m/",
        verbose_name="Arquivo",
    )
    nome_original = models.CharField(max_length=255)
    tipo = models.CharField(max_length=10, choices=TIPO_CHOICES, default="outro")
    tamanho = models.PositiveIntegerField(default=0)
    enviado_por = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name="anexos_trackhub",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]
        verbose_name = "Anexo"
        verbose_name_plural = "Anexos"

    @property
    def eh_imagem(self):
        parts = (self.nome_original or "").lower().rsplit(".", 1)
        if len(parts) < 2:
            return False
        ext = parts[-1]
        return ext in {"jpg", "jpeg", "png", "gif", "webp"}

    @property
    def tamanho_formatado(self):
        if self.tamanho < 1024:
            return f"{self.tamanho} B"
        if self.tamanho < 1024 * 1024:
            return f"{self.tamanho // 1024} KB"
        return f"{self.tamanho // (1024 * 1024)} MB"

    def __str__(self):
        return f"{self.nome_original} — {self.pendencia.titulo}"


class AnexoComentario(models.Model):
    comentario = models.ForeignKey(
        ComentarioPendencia,
        on_delete=models.CASCADE,
        related_name="anexos",
    )
    arquivo = models.FileField(upload_to="trackhub/comentarios/%Y/%m/")
    nome_original = models.CharField(max_length=255)
    tamanho = models.PositiveIntegerField(default=0)
    enviado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["enviado_em"]
        verbose_name = "Anexo de comentário"
        verbose_name_plural = "Anexos de comentários"

    @property
    def eh_imagem(self):
        parts = (self.nome_original or "").lower().rsplit(".", 1)
        if len(parts) < 2:
            return False
        return parts[-1] in {"jpg", "jpeg", "png", "gif", "webp"}

    def __str__(self):
        return self.nome_original


class AnexoEtapa(models.Model):
    etapa = models.ForeignKey(
        EtapaPendencia,
        on_delete=models.CASCADE,
        related_name="arquivos",
    )
    arquivo = models.FileField(upload_to="trackhub/etapas/%Y/%m/")
    nome_original = models.CharField(max_length=255)
    tipo = models.CharField(
        max_length=10,
        choices=AnexoPendencia.TIPO_CHOICES,
        default="outro",
    )
    tamanho = models.PositiveIntegerField(default=0)
    enviado_por = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name="anexos_etapa_trackhub",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]
        verbose_name = "Anexo de etapa"
        verbose_name_plural = "Anexos de etapas"

    @property
    def eh_imagem(self):
        parts = (self.nome_original or "").lower().rsplit(".", 1)
        if len(parts) < 2:
            return False
        return parts[-1] in {"jpg", "jpeg", "png", "gif", "webp"}

    def __str__(self):
        return f"{self.nome_original} — {self.etapa.titulo}"


class NotificacaoPrazoTrackHub(models.Model):
    """Controle de lembretes de prazo enviados para evitar duplicidade."""

    ALVO_CHOICES = [
        ("pendencia", "Pendência"),
        ("etapa", "Etapa"),
    ]

    alvo_tipo = models.CharField(max_length=20, choices=ALVO_CHOICES)
    alvo_id = models.PositiveIntegerField()
    usuario = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="trackhub_notificacoes_prazo",
    )
    janela_horas = models.PositiveIntegerField()
    referencia_prazo = models.DateTimeField()
    enviado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-enviado_em"]
        unique_together = (
            "alvo_tipo",
            "alvo_id",
            "usuario",
            "janela_horas",
            "referencia_prazo",
        )
        verbose_name = "Lembrete de prazo TrackHub"
        verbose_name_plural = "Lembretes de prazo TrackHub"

    def __str__(self):
        return f"{self.alvo_tipo}:{self.alvo_id} → {self.usuario_id} ({self.janela_horas}h)"


class PendenciaRecorrente(models.Model):
    """Modelo de pendência recorrente (snapshot + próxima execução agendada)."""

    REGRA_NONE = "none"
    REGRA_DAILY = "daily"
    REGRA_WEEKDAYS = "weekdays"
    REGRA_WEEKLY = "weekly"
    REGRA_MONTHLY = "monthly"
    REGRA_YEARLY = "yearly"
    REGRA_CHOICES = [
        (REGRA_NONE, "Não se repete"),
        (REGRA_DAILY, "Diariamente"),
        (REGRA_WEEKDAYS, "Dias da semana"),
        (REGRA_WEEKLY, "Semanal"),
        (REGRA_MONTHLY, "Mensal"),
        (REGRA_YEARLY, "Anual"),
    ]

    obra = models.ForeignKey(
        Obra,
        on_delete=models.CASCADE,
        related_name="pendencias_recorrentes",
    )
    criado_por = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="pendencias_recorrentes_criadas",
    )
    titulo = models.CharField(max_length=200)
    descricao = models.TextField(blank=True)
    tipo = models.CharField(max_length=20, choices=Pendencia.TIPO_CHOICES, default="outro")
    prioridade = models.CharField(
        max_length=10, choices=Pendencia.PRIORIDADE_CHOICES, default="normal"
    )
    # Dias a somar à data de cada execução para obter o prazo da pendência (null = sem prazo)
    prazo_offset_dias = models.IntegerField(null=True, blank=True)
    # Prazo e data de criação da pendência original (para prazo das ocorrências = dia_exec + (prazo_orig - data_cri_orig))
    prazo_original = models.DateField(null=True, blank=True)
    data_criacao_original = models.DateField(null=True, blank=True)

    regra = models.CharField(max_length=20, choices=REGRA_CHOICES, default=REGRA_NONE)
    dia_semana = models.SmallIntegerField(
        null=True,
        blank=True,
        help_text="0=segunda … 6=domingo (Python weekday)",
    )
    dia_mes = models.SmallIntegerField(null=True, blank=True)
    mes = models.SmallIntegerField(null=True, blank=True)
    # Múltiplos: dias_semana [0..6], dias_mes [1..31], datas_ano [{"m":5,"d":14}, ...]
    parametros_json = models.JSONField(default=dict, blank=True)

    etapas_snapshot = models.JSONField(default=list)
    proxima_execucao = models.DateField()
    ativo = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["proxima_execucao"]
        verbose_name = "Pendência recorrente"
        verbose_name_plural = "Pendências recorrentes"

    def __str__(self):
        return f"{self.titulo} ({self.get_regra_display()}) — {self.obra_id}"


class TipoCustom(models.Model):
    nome = models.CharField(max_length=100, unique=True)
    criado_por = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, related_name="tipos_custom_criados"
    )
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["nome"]
        verbose_name = "Tipo customizado"
        verbose_name_plural = "Tipos customizados"

    def __str__(self):
        return self.nome
