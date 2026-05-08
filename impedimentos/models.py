from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class StatusImpedimento(models.Model):
    obra = models.ForeignKey(
        "gestao_aprovacao.Obra",
        on_delete=models.CASCADE,
        related_name="status_impedimentos",
    )
    nome = models.CharField(max_length=100)
    cor = models.CharField(max_length=20, help_text="Cor em hexadecimal, ex: #3B82F6")
    ordem = models.PositiveIntegerField()
    is_default = models.BooleanField(default=False)

    class Meta:
        unique_together = [["obra", "nome"]]
        ordering = ["obra", "ordem"]

    def __str__(self):
        return f"{self.obra_id} - {self.nome}"


class CategoriaImpedimento(models.Model):
    obra = models.ForeignKey(
        "gestao_aprovacao.Obra",
        on_delete=models.CASCADE,
        related_name="categorias_impedimento",
    )
    nome = models.CharField(max_length=100)
    cor = models.CharField(max_length=20, default="#6B7280")
    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="categorias_impedimento_criadas",
    )
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [["obra", "nome"]]
        ordering = ["nome"]
        verbose_name = "Categoria de restrição"
        verbose_name_plural = "Categorias de restrições"

    def __str__(self):
        return f"{self.obra_id} - {self.nome}"


class Impedimento(models.Model):
    PRIORIDADE_BAIXA = "BAIXA"
    PRIORIDADE_NORMAL = "NORMAL"
    PRIORIDADE_ALTA = "ALTA"
    PRIORIDADE_CRITICA = "CRITICA"
    PRIORIDADE_CHOICES = [
        (PRIORIDADE_BAIXA, "Baixa"),
        (PRIORIDADE_NORMAL, "Normal"),
        (PRIORIDADE_ALTA, "Alta"),
        (PRIORIDADE_CRITICA, "Crítica"),
    ]

    obra = models.ForeignKey(
        "gestao_aprovacao.Obra",
        on_delete=models.CASCADE,
        related_name="impedimentos",
    )
    parent = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="subtarefas",
    )
    titulo = models.CharField(max_length=255)
    descricao = models.TextField(blank=True, null=True)
    status = models.ForeignKey(
        StatusImpedimento,
        on_delete=models.PROTECT,
        related_name="impedimentos",
    )
    responsaveis = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        blank=True,
        related_name="impedimentos_responsavel",
    )
    categorias = models.ManyToManyField(
        "CategoriaImpedimento",
        blank=True,
        related_name="impedimentos",
    )
    prazo = models.DateField(blank=True, null=True)
    prioridade = models.CharField(
        max_length=10,
        choices=PRIORIDADE_CHOICES,
        default=PRIORIDADE_NORMAL,
    )
    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="impedimentos_criados",
    )
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)
    ultima_conclusao_em = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Data/hora da última vez que a restrição entrou no status de conclusão da obra.",
    )

    class Meta:
        ordering = ["-criado_em"]
        indexes = [
            models.Index(fields=["obra"]),
            models.Index(fields=["status"]),
            models.Index(fields=["parent"]),
        ]

    def clean(self):
        super().clean()
        if self.parent_id:
            parent = self.parent
            if parent.pk == self.pk:
                raise ValidationError({"parent": "Uma restrição não pode ser pai de si mesma."})
            if self.obra_id and parent.obra_id != self.obra_id:
                raise ValidationError({"parent": "A subtarefa deve pertencer à mesma obra do pai."})
            # Raiz → subtarefa → sub-subtarefa: não criar filho de um item já em nível 2
            if parent.parent_id is not None and parent.parent.parent_id is not None:
                raise ValidationError({"parent": "Máximo 2 níveis de subtarefas."})

    def __str__(self):
        return self.titulo


class ImagemImpedimento(models.Model):
    impedimento = models.ForeignKey(
        Impedimento,
        on_delete=models.CASCADE,
        related_name="imagens",
    )
    imagem = models.ImageField(upload_to="impedimentos/imagens/%Y/%m/%d/")
    legenda = models.CharField(max_length=255, blank=True, default="")
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["uploaded_at"]

    def __str__(self):
        return self.legenda or f"Imagem {self.pk}"


class ArquivoImpedimento(models.Model):
    impedimento = models.ForeignKey(
        Impedimento,
        on_delete=models.CASCADE,
        related_name="arquivos",
    )
    arquivo = models.FileField(upload_to="impedimentos/arquivos/%Y/%m/%d/")
    nome_original = models.CharField(max_length=255, blank=True, default="")
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["uploaded_at"]

    def __str__(self):
        return self.nome_original or f"Arquivo {self.pk}"


class AtividadeImpedimento(models.Model):
    """Histórico de alterações e eventos da restrição."""

    impedimento = models.ForeignKey(
        Impedimento,
        on_delete=models.CASCADE,
        related_name="atividades",
    )
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="atividades_impedimento_registradas",
    )
    tipo = models.CharField(max_length=32, default="geral")
    descricao = models.TextField()
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-criado_em"]

    def __str__(self):
        return f"{self.impedimento_id} — {self.descricao[:50]}"


class ComentarioImpedimento(models.Model):
    impedimento = models.ForeignKey(
        Impedimento,
        on_delete=models.CASCADE,
        related_name="comentarios",
    )
    autor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="comentarios_impedimento",
    )
    texto = models.TextField()
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["criado_em"]

    def __str__(self):
        return f"{self.autor_id} - {self.impedimento_id}"
