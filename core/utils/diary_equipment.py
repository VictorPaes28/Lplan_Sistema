"""
Agregação de equipamentos por diário — fonte única para formulário e PDF.

Regra (igual em todo o sistema):
- Se existir qualquer linha em DailyWorkLogEquipment para o diário → soma apenas
  `quantity` dessa tabela, por `equipment_id` (ordem: primeira ocorrência por work_log, id do through).
- Caso contrário (diários só com M2M antigo) → +1 por vínculo work_log↔equipamento,
  ordem pela primeira ocorrência na ordem explícita dos work_logs (atividade, pk).
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from core.models import ConstructionDiary


def aggregate_equipment_for_diary(
    diary: 'ConstructionDiary',
    work_logs_ordered: Optional[List] = None,
) -> Tuple[List[Dict[str, Any]], int]:
    """
    Retorna (rows, total_geral).

    Cada row: ``equipment_id`` (int), ``equipment`` (instância Equipment), ``quantity`` (int).
    """
    from core.models import DailyWorkLogEquipment

    order_eids: List[int] = []
    by_id: Dict[int, Dict[str, Any]] = {}

    through_qs = DailyWorkLogEquipment.objects.filter(
        work_log__diary=diary
    ).select_related('equipment').order_by('work_log_id', 'pk')

    if through_qs.exists():
        for row in through_qs:
            eq = row.equipment
            if eq is None:
                continue
            eid = row.equipment_id
            if eid not in by_id:
                by_id[eid] = {'equipment': eq, 'quantity': 0}
                order_eids.append(eid)
            by_id[eid]['quantity'] += row.quantity
    else:
        if work_logs_ordered is not None:
            wls = work_logs_ordered
        else:
            wls = list(
                diary.work_logs.select_related('activity').order_by(
                    'activity__code', 'activity__name', 'pk'
                )
            )
        for wl in wls:
            for eq in wl.resources_equipment.all():
                if eq is None:
                    continue
                eid = getattr(eq, 'pk', None)
                if eid is None:
                    continue
                if eid not in by_id:
                    by_id[eid] = {'equipment': eq, 'quantity': 0}
                    order_eids.append(eid)
                by_id[eid]['quantity'] += 1

    rows: List[Dict[str, Any]] = []
    for eid in order_eids:
        b = by_id[eid]
        eq = b['equipment']
        q = b['quantity']
        rows.append({
            'equipment_id': eid,
            'equipment': eq,
            'quantity': q,
        })
    total = sum(r['quantity'] for r in rows)
    return rows, total
