from django.conf import settings
from django.db import models
from django.utils.text import slugify


class TipoConteudo(models.TextChoices):
    TEXTO = 'TEXTO', 'Texto'
    IMAGEM = 'IMAGEM', 'Imagem'
    IMAGEM_LINK = 'IMAGEM_LINK', 'Imagem com link'
    FORMULARIO = 'FORMULARIO', 'Formulário'
    CONFIRMACAO = 'CONFIRMACAO', 'Confirmação'


class DestaqueVisual(models.TextChoices):
    PADRAO = 'PADRAO', 'Padrão'
    INFO = 'INFO', 'Informação'
    ALERTA = 'ALERTA', 'Alerta'
    CRITICO = 'CRITICO', 'Crítico'
    SUCESSO = 'SUCESSO', 'Sucesso'


class TipoExibicao(models.TextChoices):
    SEMPRE = 'SEMPRE', 'Sempre (toda vez que abrir)'
    UMA_VEZ = 'UMA_VEZ', 'Uma vez por usuário'
    UMA_VEZ_POR_DIA = 'UMA_VEZ_POR_DIA', 'Uma vez por dia'
    ATE_CONFIRMAR = 'ATE_CONFIRMAR', 'Até confirmar leitura'
    ATE_RESPONDER = 'ATE_RESPONDER', 'Até responder'
    X_VEZES = 'X_VEZES', 'Número máximo de exibições (por usuário)'
    X_DIAS = 'X_DIAS', 'Por dias (duração)'


class Prioridade(models.TextChoices):
    BAIXA = 'BAIXA', 'Baixa'
    NORMAL = 'NORMAL', 'Normal'
    ALTA = 'ALTA', 'Alta'
    CRITICA = 'CRITICA', 'Crítica'


class StatusFinalVisualizacao(models.TextChoices):
    PENDENTE = 'PENDENTE', 'Pendente'
    VISUALIZADO = 'VISUALIZADO', 'Visualizado'
    CONFIRMADO = 'CONFIRMADO', 'Confirmado'
    RESPONDIDO = 'RESPONDIDO', 'Respondido'
    IGNORADO = 'IGNORADO', 'Ignorado'


class PublicoEscopoCriterios(models.TextChoices):
    """Como combinar grupos, usuários e obras permitidos (quando o público não é “todos”)."""

    QUALQUER = 'QUALQUER', 'Qualquer critério (OU)'
    TODOS = 'TODOS', 'Todos os critérios (E)'


class PublicoRestricaoPerfil(models.TextChoices):
    """Filtro adicional por perfil Django, aplicado depois das regras de público e exclusões."""

    NENHUMA = 'NENHUMA', 'Sem restrição de perfil'
    APENAS_STAFF = 'APENAS_STAFF', 'Apenas staff'
    APENAS_SUPERUSER = 'APENAS_SUPERUSER', 'Apenas superusuários'


class Comunicado(models.Model):
    titulo = models.CharField(max_length=255, verbose_name='Título (interno)')
    slug = models.SlugField(
        max_length=255,
        unique=True,
        editable=True,
        blank=True,
        default='',
        verbose_name='Slug',
        help_text='Deixe em branco para gerar automaticamente a partir do título.',
    )
    descricao_interna = models.TextField(
        blank=True,
        null=True,
        verbose_name='Descrição interna',
        help_text='Visível apenas no admin.',
    )
    ativo = models.BooleanField(default=True, verbose_name='Ativo')
    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='comunicados_criados',
        verbose_name='Criado por',
    )
    criado_em = models.DateTimeField(auto_now_add=True, verbose_name='Criado em')
    atualizado_em = models.DateTimeField(auto_now=True, verbose_name='Atualizado em')

    tipo_conteudo = models.CharField(
        max_length=32,
        choices=TipoConteudo.choices,
        default=TipoConteudo.TEXTO,
        verbose_name='Tipo de conteúdo',
    )

    titulo_visivel = models.CharField(
        max_length=255,
        blank=True,
        default='',
        verbose_name='Título visível',
    )
    subtitulo = models.CharField(
        max_length=255,
        blank=True,
        default='',
        verbose_name='Subtítulo',
    )
    texto_principal = models.TextField(
        blank=True,
        default='',
        verbose_name='Texto principal',
    )
    imagem = models.ImageField(
        upload_to='comunicados/',
        blank=True,
        null=True,
        verbose_name='Imagem',
    )
    link_destino = models.URLField(
        blank=True,
        null=True,
        verbose_name='Link de destino',
    )
    texto_botao = models.CharField(
        max_length=120,
        blank=True,
        default='',
        verbose_name='Texto do botão',
    )
    destaque_visual = models.CharField(
        max_length=32,
        choices=DestaqueVisual.choices,
        default=DestaqueVisual.PADRAO,
        verbose_name='Destaque visual',
    )

    tipo_exibicao = models.CharField(
        max_length=32,
        choices=TipoExibicao.choices,
        default=TipoExibicao.SEMPRE,
        verbose_name='Tipo de exibição',
    )
    max_exibicoes_por_usuario = models.PositiveIntegerField(
        blank=True,
        null=True,
        verbose_name='Máx. exibições por usuário',
        help_text='Usado quando o tipo é “Número máximo de exibições”.',
    )
    data_inicio = models.DateTimeField(blank=True, null=True, verbose_name='Data de início')
    data_fim = models.DateTimeField(blank=True, null=True, verbose_name='Data de fim')
    dias_ativo = models.PositiveIntegerField(
        blank=True,
        null=True,
        verbose_name='Dias ativo',
        help_text='Usado quando o tipo é “Por dias (duração)”.',
    )
    prioridade = models.CharField(
        max_length=16,
        choices=Prioridade.choices,
        default=Prioridade.NORMAL,
        verbose_name='Prioridade',
    )

    publico_todos = models.BooleanField(default=True, verbose_name='Público: todos')
    publico_escopo_criterios = models.CharField(
        max_length=16,
        choices=PublicoEscopoCriterios.choices,
        default=PublicoEscopoCriterios.QUALQUER,
        verbose_name='Combinação dos critérios',
        help_text=(
            'Com público restrito: OU = basta grupo, usuário ou obra; '
            'E = tem de cumprir todos os tipos que estiverem preenchidos (ex.: grupo e obra).'
        ),
    )
    publico_restrito_perfil = models.CharField(
        max_length=20,
        choices=PublicoRestricaoPerfil.choices,
        default=PublicoRestricaoPerfil.NENHUMA,
        verbose_name='Restrição de perfil',
        help_text='Aplicado depois do público e das exclusões; útil para avisos só à equipa interna.',
    )
    grupos_permitidos = models.ManyToManyField(
        'auth.Group',
        blank=True,
        related_name='comunicados_grupos_permitidos',
        verbose_name='Grupos permitidos',
    )
    usuarios_permitidos = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        blank=True,
        related_name='comunicados_usuarios_permitidos',
        verbose_name='Usuários permitidos',
    )
    obras_permitidas = models.ManyToManyField(
        'gestao_aprovacao.Obra',
        blank=True,
        related_name='comunicados_obras',
        verbose_name='Obras permitidas',
    )
    grupos_excluidos = models.ManyToManyField(
        'auth.Group',
        blank=True,
        related_name='comunicados_grupos_excluidos',
        verbose_name='Grupos excluídos',
    )
    usuarios_excluidos = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        blank=True,
        related_name='comunicados_usuarios_excluidos',
        verbose_name='Usuários excluídos',
    )
    obras_excluidas = models.ManyToManyField(
        'gestao_aprovacao.Obra',
        blank=True,
        related_name='comunicados_obras_excluidas',
        verbose_name='Obras excluídas',
        help_text=(
            'Usuários vinculados a estes projetos (membro da obra) deixam de ver o comunicado. '
            'Só obras com projeto do Diário associado têm efeito.'
        ),
    )

    pode_fechar = models.BooleanField(default=True, verbose_name='Pode fechar')
    exige_confirmacao = models.BooleanField(default=False, verbose_name='Exige confirmação de leitura')
    exige_resposta = models.BooleanField(default=False, verbose_name='Exige resposta')
    bloquear_ate_acao = models.BooleanField(
        default=False,
        verbose_name='Bloquear até ação',
        help_text=(
            'Só aplica a conteúdos “Confirmação” ou “Formulário”: impede fechar até confirmar ou enviar resposta. '
            'Em texto/imagem puro não há ação obrigatória; use “Pode fechar” para bloquear o fecho de vez.'
        ),
    )
    abrir_automaticamente = models.BooleanField(default=True, verbose_name='Abrir automaticamente')
    mostrar_apos_fechar = models.BooleanField(default=False, verbose_name='Mostrar após fechar')
    permitir_nao_mostrar_novamente = models.BooleanField(
        default=False,
        verbose_name='Permitir “não mostrar novamente”',
    )

    class Meta:
        verbose_name = 'Comunicado'
        verbose_name_plural = 'Comunicados'
        ordering = ['-prioridade', '-criado_em']

    def __str__(self):
        return self.titulo

    def save(self, *args, **kwargs):
        if not self.slug and self.titulo:
            base = slugify(self.titulo)[:200] or 'comunicado'
            slug_candidate = base
            n = 2
            while Comunicado.objects.filter(slug=slug_candidate).exclude(pk=self.pk).exists():
                suffix = f'-{n}'
                slug_candidate = f'{base[: 200 - len(suffix)]}{suffix}'
                n += 1
            self.slug = slug_candidate
        super().save(*args, **kwargs)


class ComunicadoVisualizacao(models.Model):
    comunicado = models.ForeignKey(
        Comunicado,
        on_delete=models.CASCADE,
        related_name='visualizacoes',
        verbose_name='Comunicado',
    )
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='comunicado_visualizacoes',
        verbose_name='Usuário',
    )
    primeira_visualizacao = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Primeira visualização',
    )
    ultima_visualizacao = models.DateTimeField(
        auto_now=True,
        verbose_name='Última visualização',
    )
    total_visualizacoes = models.PositiveIntegerField(default=0, verbose_name='Total de visualizações (usuário)')
    fechou = models.BooleanField(default=False, verbose_name='Fechou')
    confirmou_leitura = models.BooleanField(default=False, verbose_name='Confirmou leitura')
    respondeu = models.BooleanField(default=False, verbose_name='Respondeu')
    data_resposta = models.DateTimeField(blank=True, null=True, verbose_name='Data da resposta')
    status_final = models.CharField(
        max_length=16,
        choices=StatusFinalVisualizacao.choices,
        default=StatusFinalVisualizacao.PENDENTE,
        verbose_name='Status final',
    )

    class Meta:
        verbose_name = 'Visualização de comunicado'
        verbose_name_plural = 'Visualizações de comunicados'
        unique_together = [['comunicado', 'usuario']]
        ordering = ['-ultima_visualizacao']

    def __str__(self):
        return f'{self.comunicado} — {self.usuario}'


class ComunicadoResposta(models.Model):
    comunicado = models.ForeignKey(
        Comunicado,
        on_delete=models.CASCADE,
        related_name='respostas',
        verbose_name='Comunicado',
    )
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='comunicado_respostas',
        verbose_name='Usuário',
    )
    resposta = models.TextField(verbose_name='Resposta')
    data_resposta = models.DateTimeField(auto_now_add=True, verbose_name='Data da resposta')

    class Meta:
        verbose_name = 'Resposta ao comunicado'
        verbose_name_plural = 'Respostas aos comunicados'
        ordering = ['-data_resposta']

    def __str__(self):
        return f'Resposta de {self.usuario} em {self.comunicado}'
