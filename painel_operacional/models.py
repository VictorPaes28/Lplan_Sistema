from django.conf import settings
from django.db import models
from django.utils import timezone

from mapa_obras.models import Obra


class AmbienteTipo(models.TextChoices):
    MAPA_CONTROLE = "mapa_controle", "Mapa de Controle"
    SUPRIMENTOS = "suprimentos", "Painel de Suprimentos"
    APROVACOES = "aprovacoes", "Fila de Aprovações"
    CUSTOM = "custom", "Customizável"


class VersaoEstado(models.TextChoices):
    DRAFT = "draft", "Rascunho"
    PUBLISHED = "published", "Publicado"
    ARCHIVED = "archived", "Arquivado"


class AmbienteOperacional(models.Model):
    obra = models.ForeignKey(Obra, on_delete=models.CASCADE, related_name="ambientes_operacionais")
    nome = models.CharField(max_length=180)
    tipo = models.CharField(max_length=40, choices=AmbienteTipo.choices, default=AmbienteTipo.MAPA_CONTROLE)
    descricao = models.CharField(max_length=300, blank=True, default="")
    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ambientes_operacionais_criados",
    )
    ativo = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]
        verbose_name = "Ambiente operacional"
        verbose_name_plural = "Ambientes operacionais"

    def __str__(self):
        return f"{self.nome} ({self.obra.nome})"


class AmbienteVersao(models.Model):
    ambiente = models.ForeignKey(AmbienteOperacional, on_delete=models.CASCADE, related_name="versoes")
    numero = models.PositiveIntegerField(default=1)
    estado = models.CharField(max_length=20, choices=VersaoEstado.choices, default=VersaoEstado.DRAFT)
    layout = models.JSONField(default=dict, blank=True)
    metadados = models.JSONField(default=dict, blank=True)
    publicado_em = models.DateTimeField(null=True, blank=True)
    publicado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ambientes_versoes_publicadas",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-numero", "-updated_at"]
        verbose_name = "Versão de ambiente"
        verbose_name_plural = "Versões de ambiente"
        constraints = [
            models.UniqueConstraint(fields=["ambiente", "numero"], name="uniq_ambiente_versao_numero"),
        ]

    def __str__(self):
        return f"{self.ambiente.nome} v{self.numero} ({self.estado})"

    @classmethod
    def proximo_numero(cls, ambiente_id: int) -> int:
        ultimo = (
            cls.objects.filter(ambiente_id=ambiente_id)
            .order_by("-numero")
            .values_list("numero", flat=True)
            .first()
        )
        return (ultimo or 0) + 1


class AmbientePermissao(models.Model):
    PAPEL_VIEWER = "viewer"
    PAPEL_EDITOR = "editor"
    PAPEL_PUBLISHER = "publisher"
    PAPEL_ADMIN = "admin"
    PAPEL_CHOICES = (
        (PAPEL_VIEWER, "Visualizador"),
        (PAPEL_EDITOR, "Editor"),
        (PAPEL_PUBLISHER, "Publicador"),
        (PAPEL_ADMIN, "Administrador"),
    )

    ambiente = models.ForeignKey(AmbienteOperacional, on_delete=models.CASCADE, related_name="permissoes")
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="ambientes_permissoes",
    )
    papel = models.CharField(max_length=20, choices=PAPEL_CHOICES, default=PAPEL_VIEWER)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Permissão de ambiente"
        verbose_name_plural = "Permissões de ambiente"
        constraints = [
            models.UniqueConstraint(fields=["ambiente", "usuario"], name="uniq_ambiente_permissao_usuario"),
        ]

    def __str__(self):
        sujeito = self.usuario.username if self.usuario_id else "Sem usuário"
        return f"{self.ambiente.nome} - {sujeito} ({self.papel})"


class AmbienteHistorico(models.Model):
    ACAO_CRIAR = "criar_ambiente"
    ACAO_SALVAR = "salvar_rascunho"
    ACAO_PUBLICAR = "publicar_versao"
    ACAO_ARQUIVAR = "arquivar_versao"
    ACAO_CHOICES = (
        (ACAO_CRIAR, "Criar ambiente"),
        (ACAO_SALVAR, "Salvar rascunho"),
        (ACAO_PUBLICAR, "Publicar versão"),
        (ACAO_ARQUIVAR, "Arquivar versão"),
    )

    ambiente = models.ForeignKey(AmbienteOperacional, on_delete=models.CASCADE, related_name="historico")
    versao = models.ForeignKey(
        AmbienteVersao,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="eventos_historico",
    )
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ambientes_historico",
    )
    acao = models.CharField(max_length=40, choices=ACAO_CHOICES)
    detalhes = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Histórico de ambiente"
        verbose_name_plural = "Histórico de ambientes"

    def __str__(self):
        return f"{self.ambiente.nome}: {self.acao}"


class SemanticaIndicador(models.Model):
    DOMINIO_CONTROLE = "controle"
    DOMINIO_SUPRIMENTOS = "suprimentos"
    DOMINIO_APROVACAO = "aprovacao"
    DOMINIO_DIARIO = "diario"
    DOMINIO_CHOICES = (
        (DOMINIO_CONTROLE, "Controle de obra"),
        (DOMINIO_SUPRIMENTOS, "Suprimentos"),
        (DOMINIO_APROVACAO, "Aprovação"),
        (DOMINIO_DIARIO, "Diário de obra"),
    )

    nome_canonico = models.CharField(max_length=120, unique=True)
    descricao_operacional = models.CharField(max_length=280)
    dominio = models.CharField(max_length=30, choices=DOMINIO_CHOICES, default=DOMINIO_CONTROLE)
    origem_dado = models.CharField(max_length=180, blank=True, default="")
    formula_regra = models.TextField(blank=True, default="")
    granularidade = models.CharField(max_length=120, blank=True, default="")
    limites_faixas = models.CharField(max_length=180, blank=True, default="")
    caveats = models.TextField(blank=True, default="")
    ativo = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["dominio", "nome_canonico"]
        verbose_name = "Indicador semântico"
        verbose_name_plural = "Indicadores semânticos"

    def __str__(self):
        return f"{self.nome_canonico} ({self.dominio})"


class ElementoTipo(models.TextChoices):
    BLOCK = "block", "Bloco"
    TABLE = "table", "Tabela"
    GROUP = "group", "Grupo"
    AREA = "area", "Área"
    KPI = "kpi", "KPI"


class AmbienteElemento(models.Model):
    ambiente = models.ForeignKey(AmbienteOperacional, on_delete=models.CASCADE, related_name="elementos")
    versao = models.ForeignKey(
        AmbienteVersao,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="elementos",
    )
    chave_externa = models.CharField(max_length=120, blank=True, default="")
    titulo = models.CharField(max_length=180, blank=True, default="")
    tipo = models.CharField(max_length=20, choices=ElementoTipo.choices, default=ElementoTipo.BLOCK)
    x = models.IntegerField(default=0)
    y = models.IntegerField(default=0)
    width = models.IntegerField(default=320)
    height = models.IntegerField(default=180)
    z_index = models.IntegerField(default=0)
    camada = models.JSONField(default=dict, blank=True)
    dados = models.JSONField(default=dict, blank=True)
    ativo = models.BooleanField(default=True)
    origem_layout = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Elemento de ambiente"
        verbose_name_plural = "Elementos de ambiente"
        ordering = ["z_index", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["ambiente", "chave_externa"],
                condition=~models.Q(chave_externa=""),
                name="uniq_ambiente_elemento_chave_externa",
            ),
        ]

    def __str__(self):
        return f"{self.ambiente.nome} - {self.titulo or self.tipo}"


class AmbienteCelula(models.Model):
    elemento = models.ForeignKey(AmbienteElemento, on_delete=models.CASCADE, related_name="celulas")
    linha_idx = models.PositiveIntegerField(default=0)
    coluna_idx = models.PositiveIntegerField(default=0)
    valor = models.TextField(blank=True, default="")
    tipo = models.CharField(max_length=40, blank=True, default="texto")
    estilo = models.JSONField(default=dict, blank=True)
    origem = models.JSONField(default=dict, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Célula de ambiente"
        verbose_name_plural = "Células de ambiente"
        ordering = ["linha_idx", "coluna_idx"]
        constraints = [
            models.UniqueConstraint(
                fields=["elemento", "linha_idx", "coluna_idx"],
                name="uniq_ambiente_celula_posicao",
            ),
        ]

    def __str__(self):
        return f"{self.elemento_id} [{self.linha_idx},{self.coluna_idx}]"

