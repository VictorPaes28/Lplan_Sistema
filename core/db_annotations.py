"""
Subconsultas correlacionadas para contagens — evitam JOIN cartesiano quando
vários Count() de relações diferentes são anotados no mesmo queryset.
"""
from __future__ import annotations

from django.db.models import Count, IntegerField, Model, OuterRef, Subquery
from django.db.models.functions import Coalesce


def correlated_count_subquery(
    model: type[Model],
    *,
    fk_field: str,
    outer_ref: str = 'pk',
    **filters,
) -> Subquery:
    """COUNT(*) correlacionado ao registro pai via OuterRef(outer_ref)."""
    flt = {fk_field: OuterRef(outer_ref), **filters}
    return Subquery(
        model.objects.filter(**flt)
        .values(fk_field)
        .annotate(_n=Count('id'))
        .values('_n')[:1],
        output_field=IntegerField(),
    )


def coalesced_correlated_count(
    model: type[Model],
    *,
    fk_field: str,
    outer_ref: str = 'pk',
    **filters,
):
    """Atalho: correlated_count_subquery + Coalesce(..., 0)."""
    return Coalesce(
        correlated_count_subquery(
            model,
            fk_field=fk_field,
            outer_ref=outer_ref,
            **filters,
        ),
        0,
    )
