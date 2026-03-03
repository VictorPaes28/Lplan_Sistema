from django.db import models
from django.core.validators import MinLengthValidator


class Obra(models.Model):
    """Obra/Local onde os suprimentos são aplicados."""
    codigo_sienge = models.CharField(
        max_length=50,
        unique=True,
        db_index=True,
        validators=[MinLengthValidator(1)],
        help_text="Código único da obra no Sienge"
    )
    nome = models.CharField(max_length=200)
    ativa = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['nome']
        verbose_name = 'Obra'
        verbose_name_plural = 'Obras'

    def __str__(self):
        return f"{self.codigo_sienge} - {self.nome}"


class LocalObra(models.Model):
    """Hierarquia de locais dentro de uma obra (bloco/pavimento/apto/setor)."""
    TIPO_CHOICES = [
        ('BLOCO', 'Bloco'),
        ('PAVIMENTO', 'Pavimento'),
        ('APTO', 'Apartamento'),
        ('SETOR', 'Setor'),
        ('OUTRO', 'Outro'),
    ]

    obra = models.ForeignKey(Obra, on_delete=models.CASCADE, related_name='locais')
    nome = models.CharField(max_length=100)
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES, default='OUTRO')
    parent = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='children',
        help_text="Local pai (ex: Bloco A -> Pavimento 1)"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [['obra', 'nome', 'parent']]
        ordering = ['obra', 'tipo', 'nome']
        verbose_name = 'Local da Obra'
        verbose_name_plural = 'Locais da Obra'

    def __str__(self):
        if self.parent:
            return f"{self.obra.nome} - {self.parent.nome} - {self.nome}"
        return f"{self.obra.nome} - {self.nome}"
