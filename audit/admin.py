from django.contrib import admin

from audit.models import AuditEvent, AuditRetentionPolicy


@admin.register(AuditEvent)
class AuditEventAdmin(admin.ModelAdmin):
    list_display = ('created_at', 'action_code', 'module', 'actor', 'subject_user', 'summary')
    list_filter = ('module', 'action_code')
    search_fields = ('summary', 'actor__username', 'subject_user__username', 'action_code')
    readonly_fields = (
        'created_at',
        'actor',
        'subject_user',
        'action_code',
        'module',
        'summary',
        'payload',
        'ip_address',
        'user_agent',
    )
    date_hierarchy = 'created_at'

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(AuditRetentionPolicy)
class AuditRetentionPolicyAdmin(admin.ModelAdmin):
    list_display = ('key', 'retention_days', 'updated_at')
