from django.contrib import admin

from whatsapp_ia.models import IaErroLog, IaMensagemLog, IaPermissaoConsulta, UsuarioWhatsApp


@admin.register(UsuarioWhatsApp)
class UsuarioWhatsAppAdmin(admin.ModelAdmin):
    list_display = ('telefone', 'usuario', 'ativo', 'criado_em')
    list_filter = ('ativo', 'criado_em')
    search_fields = ('telefone', 'usuario__username', 'usuario__email')
    readonly_fields = ('criado_em',)
    raw_id_fields = ('usuario',)


@admin.register(IaMensagemLog)
class IaMensagemLogAdmin(admin.ModelAdmin):
    list_display = (
        'criado_em',
        'telefone',
        'usuario',
        'intencao_detectada',
        'funcao_chamada',
        'status',
    )
    list_filter = ('status', 'intencao_detectada', 'funcao_chamada')
    search_fields = ('telefone', 'mensagem_recebida', 'resposta_enviada')
    readonly_fields = (
        'usuario',
        'telefone',
        'mensagem_recebida',
        'intencao_detectada',
        'funcao_chamada',
        'resposta_enviada',
        'status',
        'criado_em',
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(IaErroLog)
class IaErroLogAdmin(admin.ModelAdmin):
    list_display = ('criado_em', 'usuario', 'erro_resumo')
    search_fields = ('erro', 'payload_resumido', 'usuario__telefone')
    readonly_fields = ('usuario', 'erro', 'payload_resumido', 'criado_em')

    @admin.display(description='Erro')
    def erro_resumo(self, obj):
        return obj.erro[:120] + '…' if len(obj.erro) > 120 else obj.erro

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(IaPermissaoConsulta)
class IaPermissaoConsultaAdmin(admin.ModelAdmin):
    list_display = (
        'usuario',
        'pode_consultar_rdo',
        'pode_consultar_pedidos',
        'pode_receber_pdf',
        'obras_count',
    )
    list_filter = (
        'pode_consultar_rdo',
        'pode_consultar_pedidos',
        'pode_receber_pdf',
    )
    search_fields = ('usuario__telefone', 'usuario__usuario__username')
    filter_horizontal = ('obras_autorizadas',)
    raw_id_fields = ('usuario',)

    @admin.display(description='Obras autorizadas')
    def obras_count(self, obj):
        count = obj.obras_autorizadas.count()
        return 'Todas' if count == 0 else count
