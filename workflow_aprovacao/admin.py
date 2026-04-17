from django.contrib import admin

from workflow_aprovacao.models import (
    ApprovalFlowDefinition,
    ApprovalHistoryEntry,
    ApprovalIntegrationOutbox,
    ApprovalProcess,
    ApprovalStep,
    ApprovalStepParticipant,
    ProcessCategory,
)


class ApprovalStepParticipantInline(admin.TabularInline):
    model = ApprovalStepParticipant
    extra = 0
    raw_id_fields = ('user', 'django_group')


@admin.register(ApprovalFlowDefinition)
class ApprovalFlowDefinitionAdmin(admin.ModelAdmin):
    list_display = ('project', 'category', 'is_active', 'updated_at')
    list_filter = ('is_active', 'category')
    search_fields = ('project__code', 'project__name')
    raw_id_fields = ('project', 'category')


@admin.register(ApprovalStep)
class ApprovalStepAdmin(admin.ModelAdmin):
    list_display = ('flow', 'sequence', 'name', 'is_active', 'approval_policy')
    list_filter = ('is_active', 'approval_policy')
    search_fields = ('name', 'flow__project__code')
    inlines = [ApprovalStepParticipantInline]


@admin.register(ProcessCategory)
class ProcessCategoryAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'is_active', 'sort_order')
    list_filter = ('is_active',)
    search_fields = ('code', 'name')


@admin.register(ApprovalProcess)
class ApprovalProcessAdmin(admin.ModelAdmin):
    list_display = ('id', 'project', 'category', 'status', 'current_step', 'created_at')
    list_filter = ('status', 'category', 'sync_status')
    search_fields = ('title', 'project__code', 'external_id')
    readonly_fields = ('created_at', 'updated_at')
    raw_id_fields = ('project', 'category', 'flow_definition', 'current_step', 'initiated_by')


@admin.register(ApprovalHistoryEntry)
class ApprovalHistoryEntryAdmin(admin.ModelAdmin):
    list_display = ('process', 'action', 'actor', 'step_sequence_snapshot', 'created_at')
    list_filter = ('action',)
    search_fields = ('process__id', 'comment')
    readonly_fields = ('created_at',)


@admin.register(ApprovalIntegrationOutbox)
class ApprovalIntegrationOutboxAdmin(admin.ModelAdmin):
    list_display = ('id', 'process', 'event_type', 'status', 'attempts', 'created_at', 'sent_at')
    list_filter = ('status', 'event_type')
    readonly_fields = ('created_at',)
