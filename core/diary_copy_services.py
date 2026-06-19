"""
Serialização de dados do RDO para a funcionalidade «Copiar do relatório anterior».

Garante que a cópia use as mesmas fontes que o detalhe/PDF (DiaryLaborEntry + fallback M2M).
"""
from __future__ import annotations

from typing import Any

GEN_MAO_OBRA_EQUIP_CODE = 'GEN-MAO-OBRA-EQUIP'


def _is_gen_mao_obra_equip_worklog(wl) -> bool:
    activity = getattr(wl, 'activity', None)
    return getattr(activity, 'code', '') == GEN_MAO_OBRA_EQUIP_CODE


def serialize_work_logs_for_copy(diary) -> list[dict[str, Any]]:
    """Atividades do diário fonte (exclui worklog genérico de MO/equipamentos)."""
    rows: list[dict[str, Any]] = []
    for wl in diary.work_logs.select_related('activity').all():
        if _is_gen_mao_obra_equip_worklog(wl):
            continue
        activity = getattr(wl, 'activity', None)
        desc = (activity.name if activity else '').strip()
        if not desc:
            continue
        rows.append({
            'activity_description': desc,
            'work_stage': getattr(wl, 'work_stage', 'AN') or 'AN',
            'percentage_executed_today': str(wl.percentage_executed_today or 0),
            'accumulated_progress_snapshot': str(wl.accumulated_progress_snapshot or 0),
            'location': wl.location or '',
            'notes': wl.notes or '',
        })
    return rows


def serialize_occurrences_for_copy(diary) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for occ in diary.occurrences.prefetch_related('tags').all():
        desc = (occ.description or '').strip()
        if not desc:
            continue
        tag_pks = list(occ.tags.values_list('pk', flat=True))
        rows.append({
            'description': desc,
            'tags': tag_pks,
            'tag_ids': tag_pks,
        })
    return rows


def serialize_labor_entries_for_copy(diary, project) -> list[dict[str, Any]]:
    """
    Lista plana para ``existing_diary_labor`` / ``diary_labor_data``.
    Alinha com detalhe HTML: DiaryLaborEntry + fallback M2M por categoria vazia.
    """
    from core.project_labor_catalog import enrich_existing_diary_labor
    from core.utils.diary_labor import (
        build_labor_entries_by_category,
        merge_labor_entries_m2m_fallback_for_html,
    )

    by_cat = build_labor_entries_by_category(diary)
    if by_cat is None:
        by_cat = {'indireta': [], 'direta': [], 'terceirizada': []}
    merged = merge_labor_entries_m2m_fallback_for_html(by_cat, diary) or by_cat

    items: list[dict[str, Any]] = []
    for slug in ('indireta', 'direta'):
        for row in merged.get(slug) or []:
            qty = int(row.get('quantity') or 0)
            if qty <= 0:
                continue
            name = (row.get('cargo_name') or '').strip()
            if not name:
                continue
            items.append({
                'cargo_name': name,
                'quantity': qty,
                'company': '',
                'category_slug': slug,
            })

    for block in merged.get('terceirizada') or []:
        company = (block.get('company') or '').strip()
        if company == '(Sem empresa)':
            company = ''
        for row in block.get('items') or []:
            qty = int(row.get('quantity') or 0)
            if qty <= 0:
                continue
            name = (row.get('cargo_name') or '').strip()
            if not name:
                continue
            items.append({
                'cargo_name': name,
                'quantity': qty,
                'company': company,
                'category_slug': 'terceirizada',
            })

    if project and items:
        return enrich_existing_diary_labor(project, items)
    return items
