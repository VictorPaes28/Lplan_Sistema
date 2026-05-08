from django.contrib import admin

from .models import (
    AmbienteCelula,
    AmbienteElemento,
    AmbienteHistorico,
    AmbienteOperacional,
    AmbientePermissao,
    AmbienteVersao,
    SemanticaIndicador,
)


class AmbienteVersaoInline(admin.TabularInline):
    model = AmbienteVersao
    extra = 0
    readonly_fields = ("numero", "estado", "publicado_em", "publicado_por", "created_at", "updated_at")
    fields = ("numero", "estado", "publicado_em", "publicado_por", "created_at", "updated_at")


@admin.register(AmbienteOperacional)
class AmbienteOperacionalAdmin(admin.ModelAdmin):
    list_display = ("nome", "tipo", "obra", "ativo", "updated_at")
    list_filter = ("tipo", "ativo", "obra")
    search_fields = ("nome", "descricao", "obra__nome")
    inlines = [AmbienteVersaoInline]


@admin.register(AmbienteVersao)
class AmbienteVersaoAdmin(admin.ModelAdmin):
    list_display = ("ambiente", "numero", "estado", "publicado_em", "updated_at")
    list_filter = ("estado", "ambiente__tipo")
    search_fields = ("ambiente__nome", "ambiente__obra__nome")


@admin.register(AmbientePermissao)
class AmbientePermissaoAdmin(admin.ModelAdmin):
    list_display = ("ambiente", "usuario", "papel", "created_at")
    list_filter = ("papel", "ambiente__tipo")
    search_fields = ("ambiente__nome", "usuario__username", "usuario__first_name", "usuario__last_name")


@admin.register(AmbienteHistorico)
class AmbienteHistoricoAdmin(admin.ModelAdmin):
    list_display = ("ambiente", "acao", "usuario", "created_at")
    list_filter = ("acao",)
    search_fields = ("ambiente__nome", "usuario__username")


@admin.register(SemanticaIndicador)
class SemanticaIndicadorAdmin(admin.ModelAdmin):
    list_display = ("nome_canonico", "dominio", "ativo", "updated_at")
    list_filter = ("dominio", "ativo")
    search_fields = ("nome_canonico", "descricao_operacional", "origem_dado")


@admin.register(AmbienteElemento)
class AmbienteElementoAdmin(admin.ModelAdmin):
    list_display = ("id", "ambiente", "titulo", "tipo", "x", "y", "width", "height", "z_index", "ativo")
    list_filter = ("tipo", "ativo", "ambiente__tipo")
    search_fields = ("titulo", "chave_externa", "ambiente__nome")


@admin.register(AmbienteCelula)
class AmbienteCelulaAdmin(admin.ModelAdmin):
    list_display = ("id", "elemento", "linha_idx", "coluna_idx", "tipo", "updated_at")
    list_filter = ("tipo",)
    search_fields = ("valor", "elemento__titulo")

