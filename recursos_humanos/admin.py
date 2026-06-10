from django.contrib import admin

from .models import AdmissaoHistorico, Colaborador, DocumentoColaborador, ObraLocal, TipoDocumento


@admin.register(ObraLocal)
class ObraLocalAdmin(admin.ModelAdmin):
    search_fields = ('nome',)


@admin.register(TipoDocumento)
class TipoDocumentoAdmin(admin.ModelAdmin):
    list_display = ('nome', 'aplica_a', 'tem_validade', 'dias_validade', 'obrigatorio', 'ordem')
    list_filter = ('aplica_a', 'obrigatorio', 'tem_validade')


class DocumentoColaboradorInline(admin.TabularInline):
    model = DocumentoColaborador
    extra = 0


class AdmissaoHistoricoInline(admin.TabularInline):
    model = AdmissaoHistorico
    extra = 0


@admin.register(Colaborador)
class ColaboradorAdmin(admin.ModelAdmin):
    list_display = ('nome', 'cpf', 'cargo', 'status', 'data_admissao', 'etapa_admissao')
    list_filter = ('status', 'obras')
    search_fields = ('nome', 'cpf', 'cargo')
    filter_horizontal = ('obras',)
    inlines = [DocumentoColaboradorInline, AdmissaoHistoricoInline]
