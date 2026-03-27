from django.conf import settings
from django.db import models


class AssistantQuestionLog(models.Model):
    """Audita cada pergunta recebida pelo assistente."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="assistant_question_logs",
    )
    question = models.TextField(verbose_name="Pergunta")
    context = models.JSONField(default=dict, blank=True, verbose_name="Contexto informado")
    intent = models.CharField(max_length=120, blank=True, verbose_name="Intenção detectada")
    entities = models.JSONField(default=dict, blank=True, verbose_name="Entidades extraídas")
    domain = models.CharField(max_length=120, blank=True, verbose_name="Domínio acionado")
    used_llm = models.BooleanField(default=False, verbose_name="Usou IA na interpretação")
    success = models.BooleanField(default=True, verbose_name="Executou com sucesso")
    error_message = models.TextField(blank=True, verbose_name="Mensagem de erro")
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Log de pergunta do assistente"
        verbose_name_plural = "Logs de perguntas do assistente"
        indexes = [
            models.Index(fields=["user", "-created_at"]),
            models.Index(fields=["domain", "-created_at"]),
            models.Index(fields=["intent", "-created_at"]),
        ]

    def __str__(self):
        return f"{self.user} | {self.intent or 'sem-intencao'} | {self.created_at:%d/%m/%Y %H:%M}"


class AssistantResponseLog(models.Model):
    """Audita a resposta estruturada gerada para cada pergunta."""

    question_log = models.OneToOneField(
        AssistantQuestionLog,
        on_delete=models.CASCADE,
        related_name="response_log",
    )
    summary = models.CharField(max_length=400, blank=True, verbose_name="Resumo")
    response_payload = models.JSONField(default=dict, verbose_name="Payload estruturado")
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Log de resposta do assistente"
        verbose_name_plural = "Logs de respostas do assistente"
        indexes = [
            models.Index(fields=["-created_at"]),
        ]

    def __str__(self):
        return f"Resposta #{self.pk} para pergunta #{self.question_log_id}"


class AssistantLearningFeedback(models.Model):
    STATUS_PENDING = "pending"
    STATUS_REVIEWED = "reviewed"
    STATUS_CHOICES = [
        (STATUS_PENDING, "Pendente"),
        (STATUS_REVIEWED, "Revisado"),
    ]

    question_log = models.ForeignKey(
        AssistantQuestionLog,
        on_delete=models.CASCADE,
        related_name="learning_feedbacks",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="assistant_feedbacks",
    )
    helpful = models.BooleanField(verbose_name="Resposta ajudou?")
    corrected_intent = models.CharField(max_length=120, blank=True, verbose_name="Intenção corrigida")
    corrected_entities = models.JSONField(default=dict, blank=True, verbose_name="Entidades corrigidas")
    note = models.TextField(blank=True, verbose_name="Observação")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Feedback de aprendizado do assistente"
        verbose_name_plural = "Feedbacks de aprendizado do assistente"
        indexes = [
            models.Index(fields=["status", "-created_at"]),
            models.Index(fields=["question_log", "-created_at"]),
        ]

    def __str__(self):
        return f"Feedback #{self.pk} ({'ok' if self.helpful else 'ajuste'})"


class AssistantGuidedRule(models.Model):
    STATUS_PENDING = "pending"
    STATUS_APPROVED = "approved"
    STATUS_REJECTED = "rejected"
    STATUS_CHOICES = [
        (STATUS_PENDING, "Pendente"),
        (STATUS_APPROVED, "Aprovada"),
        (STATUS_REJECTED, "Rejeitada"),
    ]

    source_feedback = models.ForeignKey(
        AssistantLearningFeedback,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="suggested_rules",
    )
    trigger_text = models.CharField(max_length=240, verbose_name="Texto gatilho")
    intent = models.CharField(max_length=120, verbose_name="Intenção alvo")
    entities = models.JSONField(default=dict, blank=True, verbose_name="Entidades sugeridas")
    priority = models.PositiveSmallIntegerField(default=10, verbose_name="Prioridade")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assistant_rules_created",
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assistant_rules_approved",
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    approved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["priority", "-created_at"]
        verbose_name = "Regra guiada do assistente"
        verbose_name_plural = "Regras guiadas do assistente"
        indexes = [
            models.Index(fields=["status", "priority"]),
            models.Index(fields=["intent", "status"]),
        ]

    def __str__(self):
        return f"{self.trigger_text} -> {self.intent} ({self.status})"


class AssistantEntityAlias(models.Model):
    STATUS_PENDING = AssistantGuidedRule.STATUS_PENDING
    STATUS_APPROVED = AssistantGuidedRule.STATUS_APPROVED
    STATUS_REJECTED = AssistantGuidedRule.STATUS_REJECTED

    ENTITY_TYPES = [
        ("obra", "Obra"),
        ("insumo", "Insumo"),
        ("usuario", "Usuário"),
        ("local", "Local"),
    ]

    entity_type = models.CharField(max_length=30, choices=ENTITY_TYPES)
    alias_text = models.CharField(max_length=160, verbose_name="Alias informado")
    canonical_value = models.CharField(max_length=200, verbose_name="Valor canônico")
    status = models.CharField(
        max_length=20,
        choices=AssistantGuidedRule.STATUS_CHOICES,
        default=STATUS_PENDING,
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assistant_aliases_created",
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assistant_aliases_approved",
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    approved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["entity_type", "alias_text"]
        unique_together = [["entity_type", "alias_text"]]
        verbose_name = "Alias de entidade do assistente"
        verbose_name_plural = "Aliases de entidades do assistente"
        indexes = [
            models.Index(fields=["entity_type", "status"]),
            models.Index(fields=["alias_text", "status"]),
        ]

    def __str__(self):
        return f"{self.entity_type}: {self.alias_text} => {self.canonical_value}"
