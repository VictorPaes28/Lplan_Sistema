from django.contrib import admin
from .models import Insumo, ItemMapa, NotaFiscalEntrada, AlocacaoRecebimento, RecebimentoObra


@admin.register(Insumo)
class InsumoAdmin(admin.ModelAdmin):
    """
    Admin simplificado para Insumos.
    Insumos são importados do Sienge - apenas código, descrição e unidade.
    """
    list_display = ['codigo_sienge', 'descricao', 'unidade', 'ativo', 'updated_at']
    list_filter = ['ativo', 'created_at']
    search_fields = ['codigo_sienge', 'descricao']
    readonly_fields = ['created_at', 'updated_at']
    list_editable = ['ativo']
    
    fieldsets = (
        ('Dados do Sienge', {
            'fields': ('codigo_sienge', 'descricao', 'unidade'),
            'description': 'Estes campos são importados do CSV do Sienge.'
        }),
        ('Controle', {
            'fields': ('ativo', 'observacoes')
        }),
        ('Auditoria', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(ItemMapa)
class ItemMapaAdmin(admin.ModelAdmin):
    list_display = [
        'obra', 'categoria', 'insumo', 'prioridade', 'quantidade_planejada',
        'numero_sc', 'numero_pc', 'quantidade_recebida', 'status_etapa', 'is_atrasado'
    ]
    list_filter = [
        'obra', 'categoria', 'prioridade', 'nao_aplica', 'criado_em'
    ]
    search_fields = [
        'insumo__codigo_sienge', 'insumo__descricao', 'numero_sc', 'numero_pc',
        'empresa_fornecedora', 'responsavel'
    ]
    readonly_fields = ['criado_em', 'atualizado_em']
    fieldsets = (
        ('Classificação', {
            'fields': ('obra', 'categoria', 'prioridade', 'nao_aplica')
        }),
        ('Planejamento (Engenharia)', {
            'fields': (
                'insumo', 'descricao_override', 'local_aplicacao', 'responsavel',
                'prazo_necessidade', 'quantidade_planejada', 'observacao_eng'
            )
        }),
        ('Realizado (Sienge)', {
            'fields': (
                'numero_sc', 'data_sc', 'numero_pc', 'data_pc',
                'empresa_fornecedora', 'prazo_recebimento',
                'quantidade_recebida', 'saldo_a_entregar', 'status_sienge_raw'
            )
        }),
        ('Auditoria', {
            'fields': ('criado_por', 'criado_em', 'atualizado_em'),
            'classes': ('collapse',)
        }),
    )


@admin.register(NotaFiscalEntrada)
class NotaFiscalEntradaAdmin(admin.ModelAdmin):
    list_display = ['numero_nf', 'obra', 'insumo', 'numero_pc', 'data_entrada', 'quantidade']
    list_filter = ['obra', 'data_entrada', 'created_at']
    search_fields = ['numero_nf', 'numero_pc', 'insumo__descricao', 'obra__nome']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(RecebimentoObra)
class RecebimentoObraAdmin(admin.ModelAdmin):
    list_display = [
        'obra', 'numero_sc', 'insumo', 'numero_pc', 
        'quantidade_solicitada', 'quantidade_recebida', 'saldo_a_entregar',
        'status_recebimento', 'updated_at'
    ]
    list_filter = ['obra', 'updated_at', 'created_at']
    search_fields = ['numero_sc', 'numero_pc', 'insumo__descricao', 'obra__nome', 'empresa_fornecedora']
    readonly_fields = ['created_at', 'updated_at']
    fieldsets = (
        ('Identificação', {
            'fields': ('obra', 'numero_sc', 'insumo')
        }),
        ('Pedido de Compra', {
            'fields': ('numero_pc', 'data_pc', 'empresa_fornecedora', 'prazo_recebimento')
        }),
        ('Quantidades', {
            'fields': ('quantidade_solicitada', 'quantidade_recebida', 'saldo_a_entregar')
        }),
        ('Nota Fiscal', {
            'fields': ('numero_nf', 'data_nf'),
            'classes': ('collapse',)
        }),
        ('Auditoria', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(AlocacaoRecebimento)
class AlocacaoRecebimentoAdmin(admin.ModelAdmin):
    list_display = [
        'obra', 'local_aplicacao', 'insumo', 'quantidade_alocada', 
        'recebimento', 'item_mapa', 'data_alocacao', 'criado_por'
    ]
    list_filter = ['obra', 'data_alocacao', 'local_aplicacao']
    search_fields = ['obra__nome', 'local_aplicacao__nome', 'insumo__descricao', 'observacao']
    readonly_fields = ['data_alocacao']
    fieldsets = (
        ('Identificação', {
            'fields': ('obra', 'insumo', 'local_aplicacao')
        }),
        ('Vínculos', {
            'fields': ('recebimento', 'item_mapa', 'referencia_nf')
        }),
        ('Alocação', {
            'fields': ('quantidade_alocada', 'observacao')
        }),
        ('Auditoria', {
            'fields': ('criado_por', 'data_alocacao'),
            'classes': ('collapse',)
        }),
    )
