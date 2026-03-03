"""
Django Admin configuration para Diário de Obra V2.0.
"""
from django.contrib import admin
from treebeard.admin import TreeAdmin
from treebeard.forms import movenodeform_factory
from .models import (
    Project,
    ProjectMember,
    ProjectOwner,
    ProjectDiaryRecipient,
    Activity,
    ConstructionDiary,
    DiaryImage,
    DailyWorkLog,
    Labor,
    LaborCategory,
    LaborCargo,
    DiaryLaborEntry,
    EquipmentCategory,
    StandardEquipment,
    Equipment,
    DiaryComment,
    DiaryEditLog,
    DiaryView,
    DiarySignature,
    DiaryVideo,
    DiaryAttachment,
    Notification,
    OccurrenceTag,
    DiaryOccurrence,
)


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    """Admin para modelo Project."""
    list_display = ['code', 'name', 'start_date', 'end_date', 'is_active', 'created_at']
    list_filter = ['is_active', 'start_date', 'end_date']
    search_fields = ['code', 'name', 'description']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(ProjectMember)
class ProjectMemberAdmin(admin.ModelAdmin):
    """Vínculo usuário–obra: define a quais obras cada usuário tem acesso no Diário."""
    list_display = ['user', 'project', 'project_code']
    list_filter = ['project']
    search_fields = ['user__username', 'user__email', 'project__code', 'project__name']
    autocomplete_fields = ['user', 'project']

    def project_code(self, obj):
        return obj.project.code if obj.project_id else '-'
    project_code.short_description = 'Código obra'


@admin.register(ProjectDiaryRecipient)
class ProjectDiaryRecipientAdmin(admin.ModelAdmin):
    """E-mails que recebem o diário da obra todo dia (também configurável em Central → Obras → E-mails do diário)."""
    list_display = ['email', 'project', 'nome']
    list_filter = ['project']
    search_fields = ['email', 'nome', 'project__code', 'project__name']
    autocomplete_fields = ['project']


@admin.register(ProjectOwner)
class ProjectOwnerAdmin(admin.ModelAdmin):
    """Dono da obra (cliente): usuário com acesso restrito só às obras que possui. Pode comentar no diário em 24h."""
    list_display = ['user', 'project', 'project_code']
    list_filter = ['project']
    search_fields = ['user__username', 'user__email', 'project__code', 'project__name']
    autocomplete_fields = ['user', 'project']

    def project_code(self, obj):
        return obj.project.code if obj.project_id else '-'
    project_code.short_description = 'Código obra'


@admin.register(Activity)
class ActivityAdmin(TreeAdmin):
    """Admin para modelo Activity com suporte a árvore hierárquica."""
    form = movenodeform_factory(Activity)
    list_display = ['code', 'name', 'project', 'status', 'weight', 'planned_start', 'planned_end']
    list_filter = ['project', 'status', 'planned_start']
    search_fields = ['code', 'name', 'description']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(ConstructionDiary)
class ConstructionDiaryAdmin(admin.ModelAdmin):
    """Admin para modelo ConstructionDiary."""
    list_display = ['project', 'date', 'status', 'created_by', 'reviewed_by', 'approved_at', 'sent_to_owner_at', 'created_at']
    list_filter = ['status', 'date', 'project']
    search_fields = ['project__code', 'project__name', 'general_notes']
    readonly_fields = ['created_at', 'updated_at', 'approved_at', 'sent_to_owner_at']
    date_hierarchy = 'date'


@admin.register(DiaryImage)
class DiaryImageAdmin(admin.ModelAdmin):
    """Admin para modelo DiaryImage."""
    list_display = ['diary', 'caption', 'is_approved_for_report', 'uploaded_at']
    list_filter = ['is_approved_for_report', 'uploaded_at', 'diary__project']
    search_fields = ['caption', 'diary__project__code']
    readonly_fields = ['uploaded_at']


@admin.register(DailyWorkLog)
class DailyWorkLogAdmin(admin.ModelAdmin):
    """Admin para modelo DailyWorkLog."""
    list_display = ['activity', 'diary', 'percentage_executed_today', 'accumulated_progress_snapshot', 'created_at']
    list_filter = ['diary__date', 'diary__project', 'activity__status']
    search_fields = ['activity__code', 'activity__name', 'notes']
    readonly_fields = ['created_at', 'updated_at']
    filter_horizontal = ['resources_labor']
    # resources_equipment usa through=DailyWorkLogEquipment (com quantity), não pode estar em filter_horizontal


@admin.register(Labor)
class LaborAdmin(admin.ModelAdmin):
    """Admin para modelo Labor."""
    list_display = ['name', 'role', 'hourly_rate', 'is_active']
    list_filter = ['is_active', 'role']
    search_fields = ['name', 'role']


@admin.register(LaborCategory)
class LaborCategoryAdmin(admin.ModelAdmin):
    """Categorias de mão de obra (Indireta, Direta, Terceirizada)."""
    list_display = ['slug', 'name', 'order']
    ordering = ['order', 'slug']


@admin.register(LaborCargo)
class LaborCargoAdmin(admin.ModelAdmin):
    """Cargos padrão por categoria."""
    list_display = ['name', 'category', 'order']
    list_filter = ['category']
    search_fields = ['name', 'category__name']
    ordering = ['category', 'order', 'name']


@admin.register(DiaryLaborEntry)
class DiaryLaborEntryAdmin(admin.ModelAdmin):
    """Registro de mão de obra por cargo no diário."""
    list_display = ['diary', 'cargo', 'quantity', 'company']
    list_filter = ['diary__date', 'diary__project', 'cargo__category']
    search_fields = ['diary__project__code', 'cargo__name', 'company']
    raw_id_fields = ['diary', 'cargo']


@admin.register(EquipmentCategory)
class EquipmentCategoryAdmin(admin.ModelAdmin):
    """Categorias de equipamentos para o diário."""
    list_display = ['slug', 'name', 'order']
    ordering = ['order', 'slug']


@admin.register(StandardEquipment)
class StandardEquipmentAdmin(admin.ModelAdmin):
    """Equipamentos padrão por categoria."""
    list_display = ['name', 'category', 'order']
    list_filter = ['category']
    search_fields = ['name', 'category__name']
    ordering = ['category', 'order', 'name']


@admin.register(Equipment)
class EquipmentAdmin(admin.ModelAdmin):
    """Admin para modelo Equipment."""
    list_display = ['code', 'name', 'equipment_type', 'is_active']
    list_filter = ['is_active', 'equipment_type']
    search_fields = ['code', 'name', 'equipment_type']


@admin.register(DiaryComment)
class DiaryCommentAdmin(admin.ModelAdmin):
    """Comentários do dono da obra / LPLAN no diário (janela 24h)."""
    list_display = ['diary', 'author', 'created_at', 'text_preview']
    list_filter = ['diary__project', 'created_at']
    search_fields = ['text', 'author__username', 'diary__project__code']
    readonly_fields = ['created_at']

    def text_preview(self, obj):
        return (obj.text[:60] + '…') if obj.text and len(obj.text) > 60 else (obj.text or '')
    text_preview.short_description = 'Comentário'


@admin.register(DiaryEditLog)
class DiaryEditLogAdmin(admin.ModelAdmin):
    """Admin para modelo DiaryEditLog."""
    list_display = ['diary', 'edited_by', 'edited_at', 'field_name']
    list_filter = ['edited_at', 'diary__project']
    search_fields = ['diary__project__code', 'edited_by__username', 'notes']
    readonly_fields = ['edited_at']


@admin.register(DiaryView)
class DiaryViewAdmin(admin.ModelAdmin):
    """Admin para modelo DiaryView."""
    list_display = ['diary', 'viewed_by', 'viewed_at', 'ip_address']
    list_filter = ['viewed_at', 'diary__project']
    search_fields = ['diary__project__code', 'viewed_by__username']
    readonly_fields = ['viewed_at']


@admin.register(DiarySignature)
class DiarySignatureAdmin(admin.ModelAdmin):
    """Admin para modelo DiarySignature."""
    list_display = ['diary', 'signer', 'signature_type', 'signed_at']
    list_filter = ['signature_type', 'signed_at', 'diary__project']
    search_fields = ['diary__project__code', 'signer__username']
    readonly_fields = ['signed_at']


@admin.register(DiaryVideo)
class DiaryVideoAdmin(admin.ModelAdmin):
    """Admin para modelo DiaryVideo."""
    list_display = ['diary', 'caption', 'duration', 'is_approved_for_report', 'uploaded_at']
    list_filter = ['is_approved_for_report', 'uploaded_at']
    search_fields = ['caption', 'diary__project__name']
    readonly_fields = ['uploaded_at']


@admin.register(DiaryAttachment)
class DiaryAttachmentAdmin(admin.ModelAdmin):
    """Admin para modelo DiaryAttachment."""
    list_display = ['name', 'diary', 'file_type', 'file_size', 'uploaded_at']
    list_filter = ['file_type', 'uploaded_at']
    search_fields = ['name', 'description', 'diary__project__name']
    readonly_fields = ['uploaded_at', 'file_type', 'file_size']


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    """Admin para modelo Notification."""
    list_display = ['user', 'notification_type', 'title', 'is_read', 'created_at']
    list_filter = ['notification_type', 'is_read', 'created_at']
    search_fields = ['title', 'message', 'user__username']
    readonly_fields = ['created_at']


@admin.register(OccurrenceTag)
class OccurrenceTagAdmin(admin.ModelAdmin):
    """Admin para modelo OccurrenceTag."""
    list_display = ['name', 'color', 'is_active', 'created_at']
    list_filter = ['is_active', 'created_at']
    search_fields = ['name']
    readonly_fields = ['created_at']


@admin.register(DiaryOccurrence)
class DiaryOccurrenceAdmin(admin.ModelAdmin):
    """Admin para modelo DiaryOccurrence."""
    list_display = ['diary', 'description_short', 'created_by', 'created_at']
    list_filter = ['created_at', 'diary__project', 'diary__date']
    search_fields = ['description', 'diary__project__code']
    readonly_fields = ['created_at', 'updated_at']
    filter_horizontal = ['tags']
    
    def description_short(self, obj):
        return obj.description[:50] + '...' if len(obj.description) > 50 else obj.description
    description_short.short_description = 'Descrição'

