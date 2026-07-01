from django.contrib import admin

from .models import (
    AdmissaoHistorico,
    CargoCatalogo,
    CargoRH,
    Colaborador,
    ContratoAdmissao,
    DecisaoPrazoContrato,
    DocumentoColaborador,
    EmpresaResponsavel,
    NotificacaoEnviada,
    ObraLocal,
    PapelFluxoAdmissao,
    PrazoContrato,
    TipoDocumento,
)


@admin.register(ObraLocal)
class ObraLocalAdmin(admin.ModelAdmin):
    search_fields = ('nome',)


@admin.register(CargoRH)
class CargoRHAdmin(admin.ModelAdmin):
    search_fields = ('nome',)


@admin.register(EmpresaResponsavel)
class EmpresaResponsavelAdmin(admin.ModelAdmin):
    search_fields = ('nome',)


@admin.register(PapelFluxoAdmissao)
class PapelFluxoAdmissaoAdmin(admin.ModelAdmin):
    list_display = ('titulo', 'codigo', 'etapa', 'ordem', 'atualizado_em')
    list_filter = ('etapa',)
    search_fields = ('titulo', 'codigo')
    filter_horizontal = ('usuarios',)
    readonly_fields = ('codigo', 'titulo', 'descricao', 'etapa', 'ordem', 'atualizado_em')


@admin.register(CargoCatalogo)
class CargoCatalogoAdmin(admin.ModelAdmin):
    search_fields = ('nome',)
    ordering = ('nome',)


@admin.register(TipoDocumento)
class TipoDocumentoAdmin(admin.ModelAdmin):
    list_display = ('nome', 'categoria', 'aplica_a', 'ativo', 'tem_validade', 'dias_validade', 'obrigatorio', 'ordem')
    list_filter = ('aplica_a', 'categoria', 'ativo', 'obrigatorio', 'tem_validade')
    filter_horizontal = ('cargos_aplicaveis', 'obras_aplicaveis')


class DocumentoColaboradorInline(admin.TabularInline):
    model = DocumentoColaborador
    extra = 0


class AdmissaoHistoricoInline(admin.TabularInline):
    model = AdmissaoHistorico
    extra = 0


@admin.register(Colaborador)
class ColaboradorAdmin(admin.ModelAdmin):
    list_display = ('nome', 'cpf', 'cargo', 'cargo_rh', 'status', 'data_admissao', 'etapa_admissao')
    list_filter = ('status', 'obras')
    search_fields = ('nome', 'cpf', 'cargo')
    filter_horizontal = ('obras',)
    inlines = [DocumentoColaboradorInline, AdmissaoHistoricoInline]


@admin.register(ContratoAdmissao)
class ContratoAdmissaoAdmin(admin.ModelAdmin):
    list_display = ['colaborador', 'status', 'criado_em', 'concluido_em']
    list_filter = ['status']
    readonly_fields = ['criado_em', 'concluido_em']


@admin.register(NotificacaoEnviada)
class NotificacaoEnviadaAdmin(admin.ModelAdmin):
    list_display = ('prazo_contrato', 'tipo_alerta', 'marco', 'data_envio')
    list_filter = ('tipo_alerta', 'data_envio')
    search_fields = ('prazo_contrato__colaborador__nome',)
    readonly_fields = ('prazo_contrato', 'tipo_alerta', 'marco', 'data_envio')


@admin.register(DecisaoPrazoContrato)
class DecisaoPrazoContratoAdmin(admin.ModelAdmin):
    list_display = ('colaborador', 'acao', 'usuario', 'registrado_em')
    list_filter = ('acao', 'registrado_em')
    search_fields = ('colaborador__nome', 'motivo')
    readonly_fields = ('prazo_contrato', 'colaborador', 'acao', 'usuario', 'motivo', 'observacoes', 'registrado_em')


@admin.register(PrazoContrato)
class PrazoContratoAdmin(admin.ModelAdmin):
    list_display = [
        'colaborador',
        'tipo',
        'data_inicio',
        'data_fim',
        'status',
        'renovacao_numero',
    ]
    list_filter = ['tipo', 'status']
