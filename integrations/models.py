from django.conf import settings
from django.db import models


class IntegrationEventLog(models.Model):
    STATUS_PENDING = "pending"
    STATUS_SUCCESS = "success"
    STATUS_FAILED = "failed"
    STATUS_CHOICES = [
        (STATUS_PENDING, "Pendente"),
        (STATUS_SUCCESS, "Sucesso"),
        (STATUS_FAILED, "Falha"),
    ]

    event_type = models.CharField(max_length=120, db_index=True)
    source = models.CharField(max_length=120, db_index=True, blank=True)
    provider = models.CharField(max_length=80, db_index=True, blank=True)
    correlation_id = models.CharField(max_length=64, blank=True, db_index=True)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="integration_events",
    )
    payload = models.JSONField(default=dict, blank=True)
    response = models.JSONField(default=dict, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING, db_index=True)
    error_message = models.TextField(blank=True)
    latency_ms = models.IntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["provider", "status", "-created_at"]),
            models.Index(fields=["event_type", "-created_at"]),
        ]

    def __str__(self):
        return f"{self.event_type} [{self.provider}] - {self.status}"


class IntegrationCommandLog(models.Model):
    source = models.CharField(max_length=40, default="teams")
    command_text = models.CharField(max_length=500, blank=True)
    command_name = models.CharField(max_length=80, blank=True, db_index=True)
    external_user_id = models.CharField(max_length=120, blank=True, db_index=True)
    external_user_email = models.EmailField(blank=True)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="integration_commands",
    )
    request_payload = models.JSONField(default=dict, blank=True)
    response_payload = models.JSONField(default=dict, blank=True)
    success = models.BooleanField(default=False, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.source}:{self.command_name or 'unknown'}"


class ExternalDocument(models.Model):
    PROVIDER_SHAREPOINT = "sharepoint"
    PROVIDER_CHOICES = [(PROVIDER_SHAREPOINT, "SharePoint/OneDrive")]

    provider = models.CharField(max_length=40, choices=PROVIDER_CHOICES, default=PROVIDER_SHAREPOINT)
    reference_type = models.CharField(max_length=80, db_index=True)  # workorder, diary, project
    reference_id = models.PositiveIntegerField(db_index=True)
    file_name = models.CharField(max_length=255)
    external_id = models.CharField(max_length=255, db_index=True)
    external_url = models.URLField(blank=True)
    version_label = models.CharField(max_length=50, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [models.Index(fields=["reference_type", "reference_id", "provider"])]
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.provider}:{self.file_name}"


class SignatureRequest(models.Model):
    STATUS_DRAFT = "draft"
    STATUS_SENT = "sent"
    STATUS_SIGNED = "signed"
    STATUS_DECLINED = "declined"
    STATUS_EXPIRED = "expired"
    STATUS_CHOICES = [
        (STATUS_DRAFT, "Rascunho"),
        (STATUS_SENT, "Enviado"),
        (STATUS_SIGNED, "Assinado"),
        (STATUS_DECLINED, "Recusado"),
        (STATUS_EXPIRED, "Expirado"),
    ]

    provider = models.CharField(max_length=40, default="clicksign")
    reference_type = models.CharField(max_length=80, db_index=True)
    reference_id = models.PositiveIntegerField(db_index=True)
    signer_name = models.CharField(max_length=255)
    signer_email = models.EmailField()
    external_request_id = models.CharField(max_length=255, blank=True, db_index=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_DRAFT, db_index=True)
    signed_at = models.DateTimeField(null=True, blank=True)
    raw_payload = models.JSONField(default=dict, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="signature_requests_created",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["provider", "status", "-created_at"])]

    def __str__(self):
        return f"{self.provider}:{self.reference_type}:{self.reference_id}"


class OperationsSyncRecord(models.Model):
    TYPE_PONTO = "ponto"
    TYPE_ERP = "erp"
    TYPE_GEO = "geo"
    TYPE_CHOICES = [
        (TYPE_PONTO, "Ponto"),
        (TYPE_ERP, "ERP"),
        (TYPE_GEO, "GEO"),
    ]

    sync_type = models.CharField(max_length=20, choices=TYPE_CHOICES, db_index=True)
    reference_type = models.CharField(max_length=80, blank=True)
    reference_id = models.PositiveIntegerField(null=True, blank=True)
    status = models.CharField(max_length=20, default="pending", db_index=True)
    request_payload = models.JSONField(default=dict, blank=True)
    response_payload = models.JSONField(default=dict, blank=True)
    error_message = models.TextField(blank=True)
    synced_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.sync_type}:{self.status}"

