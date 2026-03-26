"""
Agregação de equipamentos por diário — fonte única para formulário e PDF.

Regra (igual em todo o sistema):
- Se existir qualquer linha em DailyWorkLogEquipment para o diário → consolida por
  `equipment_id` usando o MAIOR `quantity` encontrado no dia (não soma entre work_logs).
  Isso evita supercontagem quando o mesmo equipamento é associado a várias atividades.
- Caso contrário (diários só com M2M antigo) → quantidade 1 por equipamento único do dia,
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
            qty = int(row.quantity or 0)
            if eid not in by_id:
                by_id[eid] = {'equipment': eq, 'quantity': qty}
                order_eids.append(eid)
            else:
                # Lógica de diário: mesmo equipamento em vários serviços conta uma vez
                # com a maior quantidade usada no dia.
                if qty > by_id[eid]['quantity']:
                    by_id[eid]['quantity'] = qty
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
                    by_id[eid] = {'equipment': eq, 'quantity': 1}
                    order_eids.append(eid)

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
