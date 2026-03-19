from django.contrib import admin

from .models import (
    ExternalDocument,
    IntegrationCommandLog,
    IntegrationEventLog,
    OperationsSyncRecord,
    SignatureRequest,
)


@admin.register(IntegrationEventLog)
class IntegrationEventLogAdmin(admin.ModelAdmin):
    list_display = ("created_at", "event_type", "provider", "status", "source", "latency_ms")
    list_filter = ("provider", "status", "event_type", "source")
    search_fields = ("event_type", "correlation_id", "error_message")
    readonly_fields = ("created_at", "updated_at")


@admin.register(IntegrationCommandLog)
class IntegrationCommandLogAdmin(admin.ModelAdmin):
    list_display = ("created_at", "source", "command_name", "external_user_email", "success")
    list_filter = ("source", "success", "command_name")
    search_fields = ("command_text", "external_user_id", "external_user_email")
    readonly_fields = ("created_at",)


@admin.register(ExternalDocument)
class ExternalDocumentAdmin(admin.ModelAdmin):
    list_display = ("created_at", "provider", "reference_type", "reference_id", "file_name", "version_label")
    list_filter = ("provider", "reference_type")
    search_fields = ("file_name", "external_id", "reference_type")


@admin.register(SignatureRequest)
class SignatureRequestAdmin(admin.ModelAdmin):
    list_display = ("created_at", "provider", "reference_type", "reference_id", "signer_email", "status")
    list_filter = ("provider", "status")
    search_fields = ("signer_email", "external_request_id", "reference_type")


@admin.register(OperationsSyncRecord)
class OperationsSyncRecordAdmin(admin.ModelAdmin):
    list_display = ("created_at", "sync_type", "status", "reference_type", "reference_id", "synced_at")
    list_filter = ("sync_type", "status")
    search_fields = ("reference_type", "error_message")

