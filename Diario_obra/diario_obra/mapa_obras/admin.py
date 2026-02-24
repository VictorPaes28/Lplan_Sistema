from django.contrib import admin
from .models import Obra, LocalObra


@admin.register(Obra)
class ObraAdmin(admin.ModelAdmin):
    list_display = ['codigo_sienge', 'nome', 'ativa', 'created_at']
    list_filter = ['ativa', 'created_at']
    search_fields = ['codigo_sienge', 'nome']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(LocalObra)
class LocalObraAdmin(admin.ModelAdmin):
    list_display = ['nome', 'obra', 'tipo', 'parent', 'created_at']
    list_filter = ['tipo', 'obra', 'created_at']
    search_fields = ['nome', 'obra__nome']
    readonly_fields = ['created_at', 'updated_at']

