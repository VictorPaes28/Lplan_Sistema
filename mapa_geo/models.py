from decimal import Decimal

from django.db import models
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator


class GeoObraConfig(models.Model):
    """Configuração do mapa geográfico por projeto."""

    project = models.OneToOneField(
        'core.Project',
        on_delete=models.CASCADE,
        related_name='geo_config',
        verbose_name='Projeto',
    )
    center_latitude = models.DecimalField(
        max_digits=10,
        decimal_places=7,
        null=True,
        blank=True,
        verbose_name='Latitude central',
    )
    center_longitude = models.DecimalField(
        max_digits=10,
        decimal_places=7,
        null=True,
        blank=True,
        verbose_name='Longitude central',
    )
    default_zoom = models.PositiveSmallIntegerField(default=10, verbose_name='Zoom padrão')
    import_label = models.CharField(
        max_length=200,
        blank=True,
        verbose_name='Fonte dos dados',
        help_text='Ex.: KMZ IRU TIM 01-06-26',
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Configuração geo da obra'
        verbose_name_plural = 'Configurações geo das obras'

    def __str__(self):
        return f'Geo — {self.project.code}'


class GeoFeature(models.Model):
    """Elemento geográfico (ponto, linha ou polígono) vinculado a um projeto."""

    GEOMETRY_TYPES = [
        ('Point', 'Ponto'),
        ('LineString', 'Linha'),
        ('Polygon', 'Polígono'),
    ]
    STATUS_CHOICES = [
        ('planned', 'Planejado'),
        ('in_progress', 'Em andamento'),
        ('completed', 'Concluído'),
        ('blocked', 'Bloqueado'),
        ('vistoria', 'Vistoria'),
    ]
    KIND_CHOICES = [
        ('segment', 'Trecho de rota'),
        ('point', 'Ponto geral'),
        ('obstacle', 'Obstáculo'),
        ('vistoria', 'Vistoria'),
        ('caixa', 'Caixa / infra'),
        ('area', 'Área'),
        ('other', 'Outro'),
    ]

    project = models.ForeignKey(
        'core.Project',
        on_delete=models.CASCADE,
        related_name='geo_features',
        verbose_name='Projeto',
    )
    activity = models.ForeignKey(
        'core.Activity',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='geo_features',
        verbose_name='Atividade EAP',
    )
    diary = models.ForeignKey(
        'core.ConstructionDiary',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='geo_features',
        verbose_name='Diário de obra',
        help_text='Preenchido automaticamente para marcadores GPS de RDO',
    )
    external_key = models.CharField(
        max_length=120,
        blank=True,
        db_index=True,
        help_text='Chave estável para reimportação (nome + pasta + tipo)',
    )
    name = models.CharField(max_length=255, blank=True, verbose_name='Nome')
    folder = models.CharField(max_length=500, blank=True, verbose_name='Pasta / trecho')
    description = models.TextField(blank=True, verbose_name='Descrição')
    geometry_type = models.CharField(max_length=20, choices=GEOMETRY_TYPES, db_index=True)
    geometry = models.JSONField(
        help_text='Geometria GeoJSON (coordinates apenas, sem wrapper Feature)',
    )
    latitude = models.DecimalField(
        max_digits=10,
        decimal_places=7,
        null=True,
        blank=True,
        help_text='Centro/representativo para pontos e busca rápida',
    )
    longitude = models.DecimalField(
        max_digits=10,
        decimal_places=7,
        null=True,
        blank=True,
    )
    kind = models.CharField(max_length=20, choices=KIND_CHOICES, default='other', db_index=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='planned', db_index=True)
    progress_pct = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0')), MaxValueValidator(Decimal('100'))],
        verbose_name='Progresso (%)',
    )
    sort_order = models.PositiveIntegerField(default=0, help_text='Ordem ao longo da rota (linhas)')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Elemento geográfico'
        verbose_name_plural = 'Elementos geográficos'
        ordering = ['project', 'sort_order', 'geometry_type', 'name']
        indexes = [
            models.Index(fields=['project', 'geometry_type']),
            models.Index(fields=['project', 'kind']),
            models.Index(fields=['project', 'external_key']),
        ]
        # Removida UniqueConstraint condicional (project, external_key) — MariaDB (W036).
        # Unicidade só quando external_key preenchida: validate_unique().

    def validate_unique(self, exclude=None):
        super().validate_unique(exclude=exclude)
        ext = (self.external_key or '').strip()
        if not ext or not self.project_id:
            return
        qs = GeoFeature.objects.filter(project_id=self.project_id, external_key=ext)
        if self.pk:
            qs = qs.exclude(pk=self.pk)
        if qs.exists():
            raise ValidationError(
                {
                    'external_key': (
                        'Já existe um elemento neste projeto com esta chave externa.'
                    ),
                },
            )

    def __str__(self):
        label = self.name or self.external_key or f'#{self.pk}'
        return f'{self.project.code} — {label}'


class GeoProgressSnapshot(models.Model):
    """Histórico de progresso de um elemento em uma data (mapa evolutivo)."""

    feature = models.ForeignKey(
        GeoFeature,
        on_delete=models.CASCADE,
        related_name='snapshots',
        verbose_name='Elemento',
    )
    snapshot_date = models.DateField(db_index=True, verbose_name='Data')
    progress_pct = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0')), MaxValueValidator(Decimal('100'))],
    )
    status = models.CharField(
        max_length=20,
        choices=GeoFeature.STATUS_CHOICES,
        default='planned',
    )
    source = models.CharField(
        max_length=40,
        default='manual',
        help_text='manual | import | diario | sync',
    )
    notes = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Snapshot de progresso geo'
        verbose_name_plural = 'Snapshots de progresso geo'
        ordering = ['-snapshot_date', 'feature_id']
        constraints = [
            models.UniqueConstraint(
                fields=['feature', 'snapshot_date'],
                name='mapa_geo_unique_snapshot_per_feature_date',
            ),
        ]

    def __str__(self):
        return f'{self.feature} @ {self.snapshot_date:%d/%m/%Y} ({self.progress_pct}%)'
