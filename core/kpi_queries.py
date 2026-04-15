"""
Consultas canônicas para KPIs por obra (ver docs/KPI_CONTRATOS_LPLAN.md).

Objetivo: um único lugar para contagens usadas em BI, assistente e radar,
evitando divergência entre telas. Refatore gradualmente os serviços para importar daqui.
"""
from __future__ import annotations

from decimal import Decimal

from django.db.models import DecimalField, Sum, Value
from django.db.models.functions import Coalesce

from core.models import ConstructionDiary, DiaryStatus, Project
from gestao_aprovacao.models import WorkOrder
from mapa_obras.models import Obra as MapaObra
from suprimentos.models import ItemMapa


def count_pedidos_pendentes(project: Project) -> int:
    """Pedidos com status 'pendente' ligados à obra via obra.project."""
    return WorkOrder.objects.filter(obra__project=project, status="pendente").count()


def count_diarios_nao_aprovados(project: Project) -> int:
    """Diários que ainda não atingiram status APROVADO (fluxo amplo: rascunho, revisão, etc.)."""
    return ConstructionDiary.objects.filter(project=project).exclude(status=DiaryStatus.APROVADO).count()


def count_diarios_aguardando_gestor(project: Project) -> int:
    """Subconjunto: somente aguardando aprovação do gestor (lista de relatórios)."""
    return ConstructionDiary.objects.filter(
        project=project,
        status=DiaryStatus.AGUARDANDO_APROVACAO_GESTOR,
    ).count()


def mapa_obra_for_project(project: Project) -> MapaObra | None:
    """Obra do mapa para o projeto: preferir FK ``obra_mapa``; fallback código Sienge."""
    o = MapaObra.objects.filter(project_id=project.pk, ativa=True).first()
    if o:
        return o
    return MapaObra.objects.filter(codigo_sienge=project.code, ativa=True).first()


def queryset_itens_sem_alocacao_efetiva(project: Project):
    """
    Itens planejados com quantidade > 0 e soma de alocações <= 0.
    Alinhado a `RadarObraService._calc_suprimentos` (não usar apenas alocacoes__isnull).
    """
    mapa_obra = mapa_obra_for_project(project)
    if not mapa_obra:
        return ItemMapa.objects.none()
    return (
        ItemMapa.objects.filter(obra=mapa_obra, quantidade_planejada__gt=0)
        .annotate(
            total_alocado=Coalesce(
                Sum("alocacoes__quantidade_alocada"),
                Value(Decimal("0.00")),
                output_field=DecimalField(max_digits=14, decimal_places=2),
            )
        )
        .filter(total_alocado__lte=0)
    )


def count_itens_sem_alocacao_efetiva(project: Project) -> int:
    return queryset_itens_sem_alocacao_efetiva(project).count()
