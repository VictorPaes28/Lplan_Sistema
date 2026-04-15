import re

from django.db import models
from django.core.validators import MinLengthValidator


class Obra(models.Model):
    """Obra/Local onde os suprimentos são aplicados."""
    project = models.OneToOneField(
        'core.Project',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='obra_mapa',
        help_text=(
            'Projeto canónico do Diário de Obra. Preenchido pela sincronização ao guardar o projeto; '
            'mantém o vínculo explícito além do código Sienge.'
        ),
    )
    codigo_sienge = models.CharField(
        max_length=50,
        unique=True,
        db_index=True,
        validators=[MinLengthValidator(1)],
        help_text="Código único da obra no Sienge"
    )
    codigos_sienge_alternativos = models.TextField(
        blank=True,
        help_text=(
            "Outros códigos do Sienge que identificam a mesma obra (ex.: MAPA exporta 42 e o cadastro principal é 242). "
            "Separar por vírgula, ponto e vírgula ou quebra de linha."
        ),
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

    def chaves_sienge_busca_importacao(self):
        """
        Conjunto de strings que devem resolver para esta obra na importação MAPA_CONTROLE
        (código principal + alternativos, com variantes numéricas comuns).
        """
        keys = set()

        def expand(s):
            s = (s or "").strip()
            if not s:
                return
            keys.add(s)
            if s.isdigit():
                n = str(int(s))
                keys.add(n)
                for width in (4, 5):
                    keys.add(n.zfill(width))

        expand(self.codigo_sienge)
        raw = (self.codigos_sienge_alternativos or "").strip()
        if raw:
            for part in re.split(r"[,;\n]+", raw):
                expand(part.strip())
        return keys


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
