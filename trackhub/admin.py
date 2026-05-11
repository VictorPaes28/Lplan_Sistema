from django.contrib import admin

from .models import (
    AnexoComentario,
    AnexoEtapa,
    AnexoPendencia,
    AssinaturaEtapa,
    ComentarioPendencia,
    EtapaPendencia,
    NotificacaoPendencia,
    Pendencia,
)


class EtapaInline(admin.TabularInline):
    model = EtapaPendencia
    extra = 0


@admin.register(Pendencia)
class PendenciaAdmin(admin.ModelAdmin):
    list_display = [
        "titulo",
        "obra",
        "tipo",
        "status",
        "prioridade",
        "prazo",
        "criado_por",
        "created_at",
    ]
    list_filter = ["status", "tipo", "prioridade", "obra"]
    search_fields = ["titulo", "descricao"]
    inlines = [EtapaInline]


@admin.register(EtapaPendencia)
class EtapaAdmin(admin.ModelAdmin):
    list_display = [
        "titulo",
        "pendencia",
        "ordem",
        "status",
        "responsavel_interno",
        "prazo",
    ]
    list_filter = ["status"]


@admin.register(NotificacaoPendencia)
class NotificacaoAdmin(admin.ModelAdmin):
    list_display = [
        "etapa",
        "enviado_por",
        "canal",
        "destinatario_nome",
        "enviado_em",
    ]
    list_filter = ["canal"]


@admin.register(ComentarioPendencia)
class ComentarioAdmin(admin.ModelAdmin):
    list_display = ["pendencia", "autor", "created_at"]


@admin.register(AssinaturaEtapa)
class AssinaturaEtapaAdmin(admin.ModelAdmin):
    list_display = ["etapa", "assinado_por", "assinado_em"]


@admin.register(AnexoPendencia)
class AnexoAdmin(admin.ModelAdmin):
    list_display = [
        "nome_original",
        "pendencia",
        "tipo",
        "enviado_por",
        "created_at",
    ]


@admin.register(AnexoComentario)
class AnexoComentarioAdmin(admin.ModelAdmin):
    list_display = ["nome_original", "comentario", "enviado_em"]


@admin.register(AnexoEtapa)
class AnexoEtapaAdmin(admin.ModelAdmin):
    list_display = ["nome_original", "etapa", "tipo", "enviado_por", "created_at"]
