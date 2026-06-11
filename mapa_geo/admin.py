from django.contrib import admin

from .models import GeoFeature, GeoObraConfig, GeoProgressSnapshot


class GeoProgressSnapshotInline(admin.TabularInline):
    model = GeoProgressSnapshot
    extra = 0
    fields = ('snapshot_date', 'progress_pct', 'status', 'source', 'notes')
    ordering = ('-snapshot_date',)


@admin.register(GeoObraConfig)
class GeoObraConfigAdmin(admin.ModelAdmin):
    list_display = ('project', 'center_latitude', 'center_longitude', 'default_zoom', 'import_label', 'updated_at')
    search_fields = ('project__code', 'project__name', 'import_label')


@admin.register(GeoFeature)
class GeoFeatureAdmin(admin.ModelAdmin):
    list_display = (
        'project',
        'name',
        'geometry_type',
        'kind',
        'status',
        'progress_pct',
        'folder',
        'sort_order',
        'is_active',
    )
    list_filter = ('geometry_type', 'kind', 'status', 'project', 'is_active')
    search_fields = ('name', 'folder', 'external_key', 'project__code')
    inlines = [GeoProgressSnapshotInline]


@admin.register(GeoProgressSnapshot)
class GeoProgressSnapshotAdmin(admin.ModelAdmin):
    list_display = ('feature', 'snapshot_date', 'progress_pct', 'status', 'source', 'created_at')
    list_filter = ('status', 'source', 'snapshot_date')
    search_fields = ('feature__name', 'feature__project__code')
