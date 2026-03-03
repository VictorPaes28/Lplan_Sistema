from django.contrib import admin
from django.utils.safestring import mark_safe
from .models import Empresa, Obra, WorkOrder, Approval, Attachment, StatusHistory, WorkOrderPermission, UserEmpresa, UserProfile, Notificacao, Comment, Lembrete, TagErro, EmailLog


@admin.register(Obra)
class ObraAdmin(admin.ModelAdmin):
    """
    Configuração do admin para Obra.
    """
    
    list_display = [
        'codigo',
        'nome',
        'ativo',
        'created_at',
    ]
    
    list_filter = [
        'ativo',
        'created_at',
    ]
    
    search_fields = [
        'codigo',
        'nome',
        'descricao',
    ]
    
    fieldsets = (
        ('Informações Básicas', {
            'fields': ('empresa', 'codigo', 'nome', 'descricao', 'ativo')
        }),
        ('Contatos', {
            'fields': ('email_obra',)
        }),
        ('Datas', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    readonly_fields = [
        'created_at',
        'updated_at',
    ]


@admin.register(WorkOrder)
class WorkOrderAdmin(admin.ModelAdmin):
    """
    Configuração do admin para WorkOrder.
    Permite gerenciar pedidos de obra pelo painel administrativo do Django.
    """
    
    list_display = [
        'codigo',
        'obra',
        'nome_credor',
        'tipo_solicitacao',
        'status',
        'criado_por',
        'data_envio',
        'created_at',
    ]
    
    list_filter = [
        'status',
        'marcado_para_deletar',
        'tipo_solicitacao',
        'obra',
        'created_at',
        'data_envio',
        'criado_por',
    ]
    
    search_fields = [
        'codigo',
        'nome_credor',
        'observacoes',
        'obra__codigo',
        'obra__nome',
    ]
    
    readonly_fields = [
        'created_at',
        'updated_at',
        'data_envio',
        'marcado_para_deletar_por',
        'marcado_para_deletar_em',
    ]
    
    fieldsets = (
        ('Informações Básicas', {
            'fields': ('obra', 'codigo', 'status', 'tipo_solicitacao')
        }),
        ('Credor e Solicitação', {
            'fields': ('nome_credor', 'observacoes')
        }),
        ('Campos Opcionais', {
            'fields': ('valor_estimado', 'prazo_estimado', 'local'),
            'classes': ('collapse',)
        }),
        ('Controle', {
            'fields': ('criado_por', 'data_envio', 'data_aprovacao')
        }),
        ('🗑️ Exclusão pelo Admin', {
            'fields': (
                'marcado_para_deletar',
                'marcado_para_deletar_por',
                'marcado_para_deletar_em'
            ),
            'description': (
                '<div style="background-color: #fff3cd; border-left: 4px solid #ffc107; padding: 12px 15px; margin: 10px 0; border-radius: 4px;">'
                '<strong style="color: #856404; display: block; margin-bottom: 5px;">⚠️ Atenção:</strong>'
                '<p style="color: #856404; margin: 0; font-size: 13px; line-height: 1.5;">'
                'Esta funcionalidade é exclusiva para <strong>superusers</strong>. '
                'Apenas pedidos com status <strong>"Aprovado"</strong> podem ser marcados para exclusão. '
                'Após marcar, use a action "DELETAR permanentemente pedidos marcados" para remover do sistema. '
                '<strong style="color: #dc3545;">Esta ação é irreversível!</strong>'
                '</p>'
                '</div>'
            )
        }),
        ('Datas', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    date_hierarchy = 'created_at'
    
    actions = ['marcar_para_deletar', 'desmarcar_para_deletar', 'deletar_pedidos_marcados']
    
    def get_readonly_fields(self, request, obj=None):
        """
        Torna campos readonly conforme necessário.
        """
        readonly = list(self.readonly_fields)
        if obj:  # Se já existe (editando)
            readonly.append('codigo')
        # Se não for superuser, tornar campos de exclusão readonly
        if not request.user.is_superuser:
            readonly.extend(['marcado_para_deletar', 'marcado_para_deletar_por', 'marcado_para_deletar_em'])
        return readonly
    
    def get_queryset(self, request):
        """
        Filtra o queryset para mostrar apenas pedidos aprovados quando necessário.
        """
        qs = super().get_queryset(request)
        # Se não for superuser, não mostra nada especial
        if not request.user.is_superuser:
            return qs
        return qs
    
    def marcar_para_deletar(self, request, queryset):
        """
        Action para marcar pedidos aprovados selecionados para deletar.
        """
        from django.utils import timezone
        
        # Filtrar apenas pedidos aprovados
        pedidos_aprovados = queryset.filter(status='aprovado')
        count = 0
        
        for pedido in pedidos_aprovados:
            pedido.marcado_para_deletar = True
            pedido.marcado_para_deletar_por = request.user
            pedido.marcado_para_deletar_em = timezone.now()
            pedido.save()
            count += 1
        
        if count > 0:
            self.message_user(
                request,
                f'{count} pedido(s) aprovado(s) marcado(s) para deletar com sucesso.',
                level='SUCCESS'
            )
        else:
            self.message_user(
                request,
                'Nenhum pedido aprovado foi selecionado. Apenas pedidos com status "aprovado" podem ser marcados para deletar.',
                level='WARNING'
            )
    marcar_para_deletar.short_description = 'Marcar pedidos aprovados selecionados para deletar'
    
    def desmarcar_para_deletar(self, request, queryset):
        """
        Action para desmarcar pedidos selecionados.
        """
        pedidos_marcados = queryset.filter(marcado_para_deletar=True)
        count = pedidos_marcados.update(
            marcado_para_deletar=False,
            marcado_para_deletar_por=None,
            marcado_para_deletar_em=None
        )
        
        if count > 0:
            self.message_user(
                request,
                f'{count} pedido(s) desmarcado(s) com sucesso.',
                level='SUCCESS'
            )
        else:
            self.message_user(
                request,
                'Nenhum pedido marcado foi selecionado.',
                level='WARNING'
            )
    desmarcar_para_deletar.short_description = 'Desmarcar pedidos selecionados'
    
    def deletar_pedidos_marcados(self, request, queryset):
        """
        Action para deletar permanentemente os pedidos marcados para deletar.
        """
        from django.utils import timezone
        
        # Filtrar apenas pedidos marcados para deletar e aprovados
        pedidos_marcados = queryset.filter(marcado_para_deletar=True, status='aprovado')
        count = pedidos_marcados.count()
        
        if count == 0:
            self.message_user(
                request,
                'Nenhum pedido aprovado marcado para deletar foi selecionado.',
                level='WARNING'
            )
            return
        
        # Deletar os pedidos
        pedidos_deletados = []
        for pedido in pedidos_marcados:
            codigo = pedido.codigo
            pedidos_deletados.append(codigo)
            pedido.delete()
        
        self.message_user(
            request,
            f'{count} pedido(s) deletado(s) permanentemente do sistema: {", ".join(pedidos_deletados)}',
            level='SUCCESS'
        )
    deletar_pedidos_marcados.short_description = '⚠️ DELETAR permanentemente pedidos marcados (IRREVERSÍVEL)'
    
    def get_actions(self, request):
        """
        Mostra actions apenas para superusers.
        """
        actions = super().get_actions(request)
        if not request.user.is_superuser:
            # Remover actions de exclusão para não-superusers
            if 'marcar_para_deletar' in actions:
                del actions['marcar_para_deletar']
            if 'desmarcar_para_deletar' in actions:
                del actions['desmarcar_para_deletar']
            if 'deletar_pedidos_marcados' in actions:
                del actions['deletar_pedidos_marcados']
        return actions
    


@admin.register(Approval)
class ApprovalAdmin(admin.ModelAdmin):
    """
    Configuração do admin para Approval.
    Permite visualizar o histórico de aprovações.
    """
    
    list_display = [
        'work_order',
        'decisao',
        'aprovado_por',
        'get_tags_display',
        'created_at',
    ]
    
    list_filter = [
        'decisao',
        'created_at',
        'aprovado_por',
        'tags_erro',
    ]
    
    search_fields = [
        'work_order__codigo',
        'work_order__nome_credor',
        'aprovado_por__username',
        'comentario',
        'tags_erro__nome',
    ]
    
    readonly_fields = [
        'work_order',
        'aprovado_por',
        'decisao',
        'comentario',
        'tags_erro',
        'created_at',
    ]
    
    fieldsets = (
        ('Informações da Aprovação', {
            'fields': ('work_order', 'aprovado_por', 'decisao', 'comentario')
        }),
        ('Tags de Erro (se reprovado)', {
            'fields': ('tags_erro',),
            'classes': ('collapse',)
        }),
        ('Data', {
            'fields': ('created_at',)
        }),
    )
    
    date_hierarchy = 'created_at'
    
    def get_tags_display(self, obj):
        """Exibe as tags de erro associadas."""
        if obj.decisao == 'reprovado' and obj.tags_erro.exists():
            tags = ', '.join([tag.nome for tag in obj.tags_erro.all()])
            return tags[:50] + '...' if len(tags) > 50 else tags
        return '-'
    get_tags_display.short_description = 'Tags de Erro'
    
    def has_add_permission(self, request):
        """Aprovações só devem ser criadas via views, não pelo admin."""
        return False


@admin.register(Attachment)
class AttachmentAdmin(admin.ModelAdmin):
    """
    Configuração do admin para Attachment.
    Permite gerenciar anexos pelo painel administrativo.
    """
    
    list_display = [
        'work_order',
        'get_nome_display',
        'enviado_por',
        'get_tamanho_display',
        'created_at',
    ]
    
    list_filter = [
        'created_at',
        'enviado_por',
    ]
    
    search_fields = [
        'work_order__codigo',
        'work_order__nome_credor',
        'nome',
        'enviado_por__username',
        'descricao',
    ]
    
    readonly_fields = [
        'work_order',
        'arquivo',
        'enviado_por',
        'created_at',
    ]
    
    fieldsets = (
        ('Informações do Anexo', {
            'fields': ('work_order', 'arquivo', 'nome', 'descricao')
        }),
        ('Controle', {
            'fields': ('enviado_por', 'created_at')
        }),
    )
    
    date_hierarchy = 'created_at'


@admin.register(StatusHistory)
class StatusHistoryAdmin(admin.ModelAdmin):
    """
    Configuração do admin para StatusHistory.
    Permite visualizar o histórico de mudanças de status.
    """
    
    list_display = [
        'work_order',
        'status_anterior',
        'status_novo',
        'alterado_por',
        'created_at',
    ]
    
    list_filter = [
        'status_novo',
        'created_at',
        'alterado_por',
    ]
    
    search_fields = [
        'work_order__codigo',
        'work_order__nome_credor',
        'alterado_por__username',
        'observacao',
    ]
    
    readonly_fields = [
        'work_order',
        'status_anterior',
        'status_novo',
        'alterado_por',
        'observacao',
        'created_at',
    ]
    
    fieldsets = (
        ('Informações da Mudança', {
            'fields': ('work_order', 'status_anterior', 'status_novo', 'observacao')
        }),
        ('Controle', {
            'fields': ('alterado_por', 'created_at')
        }),
    )
    
    date_hierarchy = 'created_at'
    
    def has_add_permission(self, request):
        """Histórico só deve ser criado via views, não pelo admin."""
        return False


@admin.register(Empresa)
class EmpresaAdmin(admin.ModelAdmin):
    """
    Configuração do admin para Empresa.
    """
    
    list_display = [
        'codigo',
        'nome',
        'responsavel',
        'ativo',
        'created_at',
    ]
    
    list_filter = [
        'ativo',
        'created_at',
    ]
    
    search_fields = [
        'codigo',
        'nome',
        'razao_social',
        'cnpj',
    ]
    
    fieldsets = (
        ('Informações Básicas', {
            'fields': ('codigo', 'nome', 'razao_social', 'cnpj', 'ativo')
        }),
        ('Contatos', {
            'fields': ('email', 'telefone')
        }),
        ('Responsável', {
            'fields': ('responsavel',)
        }),
        ('Datas', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    readonly_fields = [
        'created_at',
        'updated_at',
    ]


@admin.register(WorkOrderPermission)
class WorkOrderPermissionAdmin(admin.ModelAdmin):
    """
    Configuração do admin para WorkOrderPermission.
    """
    
    list_display = [
        'obra',
        'usuario',
        'tipo_permissao',
        'ativo',
        'created_at',
    ]
    
    list_filter = [
        'tipo_permissao',
        'ativo',
        'obra__empresa',
        'created_at',
    ]
    
    search_fields = [
        'obra__codigo',
        'obra__nome',
        'usuario__username',
        'usuario__email',
    ]
    
    readonly_fields = [
        'created_at',
        'updated_at',
    ]


@admin.register(UserEmpresa)
class UserEmpresaAdmin(admin.ModelAdmin):
    """
    Configuração do admin para UserEmpresa.
    """
    
    list_display = [
        'usuario',
        'empresa',
        'ativo',
        'created_at',
    ]
    
    list_filter = [
        'ativo',
        'empresa',
        'created_at',
    ]
    
    search_fields = [
        'usuario__username',
        'usuario__email',
        'empresa__codigo',
        'empresa__nome',
    ]
    
    readonly_fields = [
        'created_at',
    ]


@admin.register(Notificacao)
class NotificacaoAdmin(admin.ModelAdmin):
    """
    Configuração do admin para Notificacao.
    """
    
    list_display = [
        'usuario',
        'tipo',
        'titulo',
        'lida',
        'created_at',
    ]
    
    list_filter = [
        'tipo',
        'lida',
        'created_at',
    ]
    
    search_fields = [
        'usuario__username',
        'usuario__email',
        'titulo',
        'mensagem',
        'work_order__codigo',
    ]
    
    readonly_fields = [
        'created_at',
    ]
    
    fieldsets = (
        ('Informações Básicas', {
            'fields': ('usuario', 'tipo', 'titulo', 'mensagem')
        }),
        ('Relacionamentos', {
            'fields': ('work_order',)
        }),
        ('Status', {
            'fields': ('lida',)
        }),
        ('Data', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )
    
    date_hierarchy = 'created_at'


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    """
    Configuração do admin para UserProfile.
    """
    
    list_display = [
        'usuario',
        'get_foto_preview',
        'created_at',
        'updated_at',
    ]
    
    list_filter = [
        'created_at',
        'updated_at',
    ]
    
    search_fields = [
        'usuario__username',
        'usuario__email',
        'usuario__first_name',
        'usuario__last_name',
    ]
    
    readonly_fields = [
        'created_at',
        'updated_at',
    ]
    
    fieldsets = (
        ('Usuário', {
            'fields': ('usuario',)
        }),
        ('Foto de Perfil', {
            'fields': ('foto_perfil',)
        }),
        ('Datas', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_foto_preview(self, obj):
        """Exibe uma miniatura da foto de perfil no admin."""
        if obj.foto_perfil:
            return f'<img src="{obj.foto_perfil.url}" style="width: 50px; height: 50px; border-radius: 50%; object-fit: cover;" />'
        return 'Sem foto'
    get_foto_preview.allow_tags = True
    get_foto_preview.short_description = 'Foto'


@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    """
    Configuração do admin para Comment.
    """
    
    list_display = [
        'work_order',
        'autor',
        'texto_preview',
        'created_at',
    ]
    
    list_filter = [
        'created_at',
        'work_order__status',
    ]
    
    search_fields = [
        'work_order__codigo',
        'work_order__nome_credor',
        'autor__username',
        'autor__email',
        'texto',
    ]
    
    readonly_fields = [
        'work_order',
        'autor',
        'texto',
        'created_at',
        'updated_at',
    ]
    
    fieldsets = (
        ('Informações do Comentário', {
            'fields': ('work_order', 'autor', 'texto')
        }),
        ('Datas', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    date_hierarchy = 'created_at'
    
    def texto_preview(self, obj):
        """Exibe uma prévia do texto do comentário."""
        if obj.texto:
            return obj.texto[:100] + '...' if len(obj.texto) > 100 else obj.texto
        return '-'
    texto_preview.short_description = 'Comentário'


@admin.register(Lembrete)
class LembreteAdmin(admin.ModelAdmin):
    """
    Configuração do admin para Lembrete.
    """
    
    list_display = [
        'work_order',
        'enviado_para',
        'tipo',
        'dias_pendente',
        'enviado_em',
    ]
    
    list_filter = [
        'tipo',
        'enviado_em',
        'work_order__status',
    ]
    
    search_fields = [
        'work_order__codigo',
        'work_order__nome_credor',
        'enviado_para__username',
        'enviado_para__email',
    ]
    
    readonly_fields = [
        'work_order',
        'enviado_para',
        'tipo',
        'dias_pendente',
        'enviado_em',
    ]
    
    fieldsets = (
        ('Informações do Lembrete', {
            'fields': ('work_order', 'enviado_para', 'tipo', 'dias_pendente')
        }),
        ('Data', {
            'fields': ('enviado_em',),
            'classes': ('collapse',)
        }),
    )
    
    date_hierarchy = 'enviado_em'
    
    def has_add_permission(self, request):
        """Lembretes só devem ser criados via management command, não pelo admin."""
        return False


@admin.register(TagErro)
class TagErroAdmin(admin.ModelAdmin):
    """
    Configuração do admin para TagErro.
    Permite gerenciar tags/motivos de erro por tipo de solicitação.
    """
    
    list_display = [
        'nome',
        'tipo_solicitacao',
        'ativo',
        'ordem',
        'created_at',
    ]
    
    list_filter = [
        'tipo_solicitacao',
        'ativo',
        'created_at',
    ]
    
    search_fields = [
        'nome',
        'descricao',
    ]
    
    fieldsets = (
        ('Informações Básicas', {
            'fields': ('nome', 'tipo_solicitacao', 'descricao', 'ativo', 'ordem')
        }),
        ('Datas', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    readonly_fields = [
        'created_at',
        'updated_at',
    ]
    
    ordering = ['tipo_solicitacao', 'ordem', 'nome']


@admin.register(EmailLog)
class EmailLogAdmin(admin.ModelAdmin):
    """
    Configuração do admin para EmailLog.
    Permite visualizar e gerenciar logs de email.
    """
    
    list_display = [
        'status_badge',
        'tipo_email',
        'assunto_preview',
        'destinatarios_preview',
        'work_order',
        'tentativas',
        'criado_em',
        'enviado_em',
    ]
    
    list_filter = [
        'status',
        'tipo_email',
        'criado_em',
        'tentativas',
    ]
    
    search_fields = [
        'assunto',
        'destinatarios',
        'work_order__codigo',
        'mensagem_erro',
    ]
    
    readonly_fields = [
        'tipo_email',
        'work_order',
        'destinatarios',
        'assunto',
        'status',
        'mensagem_erro',
        'tentativas',
        'enviado_em',
        'criado_em',
        'atualizado_em',
    ]
    
    fieldsets = (
        ('Informações do Email', {
            'fields': ('tipo_email', 'work_order', 'assunto', 'destinatarios')
        }),
        ('Status', {
            'fields': ('status', 'tentativas', 'enviado_em')
        }),
        ('Erro (se falhou)', {
            'fields': ('mensagem_erro',),
            'classes': ('collapse',)
        }),
        ('Datas', {
            'fields': ('criado_em', 'atualizado_em'),
            'classes': ('collapse',)
        }),
    )
    
    date_hierarchy = 'criado_em'
    
    ordering = ['-criado_em']
    
    def status_badge(self, obj):
        """Exibe o status com badge colorido."""
        if obj.status == 'enviado':
            return '<span style="color: green; font-weight: bold;">✓ Enviado</span>'
        elif obj.status == 'falhou':
            return '<span style="color: red; font-weight: bold;">✗ Falhou</span>'
        else:
            return '<span style="color: orange; font-weight: bold;">⏳ Pendente</span>'
    status_badge.allow_tags = True
    status_badge.short_description = 'Status'
    
    def assunto_preview(self, obj):
        """Exibe uma prévia do assunto."""
        if obj.assunto:
            return obj.assunto[:50] + '...' if len(obj.assunto) > 50 else obj.assunto
        return '-'
    assunto_preview.short_description = 'Assunto'
    
    def destinatarios_preview(self, obj):
        """Exibe uma prévia dos destinatários."""
        if obj.destinatarios:
            return obj.destinatarios[:50] + '...' if len(obj.destinatarios) > 50 else obj.destinatarios
        return '-'
    destinatarios_preview.short_description = 'Destinatários'
    
    def has_add_permission(self, request):
        """Logs de email só devem ser criados via sistema, não pelo admin."""
        return False

