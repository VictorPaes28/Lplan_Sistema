from django.contrib import admin
from django.contrib.auth.models import Group
from django.db.models import Sum

from accounts.groups import GRUPOS

from .models import Comunicado, ComunicadoImagem, ComunicadoResposta, ComunicadoVisualizacao


class ComunicadoImagemInline(admin.TabularInline):
    model = ComunicadoImagem
    extra = 0
    max_num = 5


class ComunicadoVisualizacaoInline(admin.TabularInline):
    model = ComunicadoVisualizacao
    extra = 0
    readonly_fields = (
        'usuario',
        'primeira_visualizacao',
        'ultima_visualizacao',
        'total_visualizacoes',
        'fechou',
        'confirmou_leitura',
        'respondeu',
        'data_resposta',
        'status_final',
    )
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Comunicado)
class ComunicadoAdmin(admin.ModelAdmin):
    list_display = (
        'titulo',
        'tipo_conteudo',
        'ativo',
        'prioridade',
        'data_inicio',
        'data_fim',
        'total_visualizacoes_agregado',
    )
    list_filter = ('ativo', 'tipo_conteudo', 'prioridade', 'tipo_exibicao')
    search_fields = ('titulo', 'slug', 'titulo_visivel', 'descricao_interna')
    readonly_fields = ('criado_em', 'atualizado_em')
    filter_horizontal = ()
    inlines = (ComunicadoImagemInline, ComunicadoVisualizacaoInline)

    fieldsets = (
        (
            'Informações básicas',
            {
                'fields': (
                    'titulo',
                    'slug',
                    'descricao_interna',
                    'ativo',
                    'criado_por',
                    'criado_em',
                    'atualizado_em',
                    'tipo_conteudo',
                ),
            },
        ),
        (
            'Conteúdo',
            {
                'fields': (
                    'titulo_visivel',
                    'subtitulo',
                    'texto_principal',
                    'link_destino',
                    'texto_botao',
                    'destaque_visual',
                ),
            },
        ),
        (
            'Regras de exibição',
            {
                'fields': (
                    'tipo_exibicao',
                    'max_exibicoes_por_usuario',
                    'data_inicio',
                    'data_fim',
                    'dias_ativo',
                    'prioridade',
                ),
            },
        ),
        (
            'Público',
            {
                'fields': (
                    'publico_todos',
                    'publico_escopo_criterios',
                    'grupos_permitidos',
                    'usuarios_permitidos',
                    'obras_permitidas',
                    'grupos_excluidos',
                    'usuarios_excluidos',
                    'obras_excluidas',
                ),
            },
        ),
        (
            'Comportamento',
            {
                'fields': (
                    'pode_fechar',
                    'exige_confirmacao',
                    'exige_resposta',
                    'abrir_automaticamente',
                    'mostrar_apos_fechar',
                    'permitir_nao_mostrar_novamente',
                ),
            },
        ),
    )

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.annotate(_total_v=Sum('visualizacoes__total_visualizacoes'))

    @admin.display(description='Total de visualizações')
    def total_visualizacoes_agregado(self, obj):
        v = getattr(obj, '_total_v', None)
        return int(v) if v is not None else 0

    def get_readonly_fields(self, request, obj=None):
        ro = list(self.readonly_fields)
        if obj:
            ro.extend(('slug', 'criado_por'))
        return ro

    def save_model(self, request, obj, form, change):
        if not change:
            obj.criado_por = request.user
        super().save_model(request, obj, form, change)

    def formfield_for_manytomany(self, db_field, request, **kwargs):
        if db_field.name in ('grupos_permitidos', 'grupos_excluidos'):
            kwargs['queryset'] = Group.objects.filter(
                name__in=[
                    GRUPOS.ADMINISTRADOR,
                    GRUPOS.APROVADOR,
                    GRUPOS.SOLICITANTE,
                    GRUPOS.GERENTES,
                    GRUPOS.ENGENHARIA,
                ]
            ).order_by('name')
        return super().formfield_for_manytomany(db_field, request, **kwargs)


@admin.register(ComunicadoVisualizacao)
class ComunicadoVisualizacaoAdmin(admin.ModelAdmin):
    list_display = (
        'comunicado',
        'usuario',
        'primeira_visualizacao',
        'ultima_visualizacao',
        'total_visualizacoes',
        'status_final',
    )
    list_filter = ('status_final', 'fechou', 'confirmou_leitura', 'respondeu')
    search_fields = ('comunicado__titulo', 'usuario__username')
    readonly_fields = (
        'primeira_visualizacao',
        'ultima_visualizacao',
    )
    autocomplete_fields = ('comunicado', 'usuario')


@admin.register(ComunicadoResposta)
class ComunicadoRespostaAdmin(admin.ModelAdmin):
    list_display = ('comunicado', 'usuario', 'trecho_resposta', 'data_resposta')
    list_filter = ('comunicado',)
    search_fields = ('resposta', 'comunicado__titulo', 'usuario__username')
    readonly_fields = ('data_resposta',)
    autocomplete_fields = ('comunicado', 'usuario')

    @admin.display(description='Resposta')
    def trecho_resposta(self, obj):
        text = (obj.resposta or '').strip()
        return text[:80] + ('…' if len(text) > 80 else '')
