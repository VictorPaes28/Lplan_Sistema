"""
Serviço para criar/atualizar atividades (work_logs) e ocorrências do diário a partir de JSON.
Usado pelo formulário do diário ao salvar via work_logs_json e occurrences_json no POST.
"""
import json
import logging
import time
from decimal import Decimal, InvalidOperation
from django.db import transaction, IntegrityError

from .models import (
    Activity,
    ActivityStatus,
    ConstructionDiary,
    DailyWorkLog,
    DiaryOccurrence,
    OccurrenceTag,
)

logger = logging.getLogger(__name__)


def _get_or_create_activity(project, activity_description):
    """
    Obtém ou cria uma Activity no projeto a partir da descrição.
    Replica a lógica de DailyWorkLogForm.save() para criação de Activity.
    """
    activity_description = (activity_description or '').strip()
    if not activity_description:
        return None
    try:
        activity = Activity.objects.get(project=project, name=activity_description)
        return activity
    except Activity.DoesNotExist:
        pass
    base_code = f'GEN-{activity_description[:20].upper().replace(" ", "-").replace("/", "-")}'
    code = base_code
    max_attempts = 5
    for attempt in range(max_attempts):
        try:
            existing = Activity.objects.filter(project=project, code=code).first()
            if existing:
                if attempt < max_attempts - 1:
                    code = f'{base_code}-{int(time.time()) % 10000}'
                    continue
                return existing
            activity = Activity.add_root(
                project=project,
                name=activity_description,
                code=code,
                description=f'Atividade criada automaticamente: {activity_description}',
                weight=Decimal('0.00'),
                status=ActivityStatus.NOT_STARTED,
            )
            logger.info("Activity criada como raiz: %s", activity.code)
            return activity
        except IntegrityError:
            if attempt < max_attempts - 1:
                code = f'{base_code}-{int(time.time()) % 10000}'
            else:
                try:
                    return Activity.objects.get(project=project, name=activity_description)
                except Activity.DoesNotExist:
                    raise
    return None


def create_worklogs_from_json(diary, project, work_logs_json_str):
    """
    Substitui os registros DailyWorkLog do diário pelos enviados em JSON.
    Remove os existentes e cria a partir da lista (activity_description, work_stage, etc.).

    Retorna a lista de DailyWorkLog criados.
    """
    if not diary or not project:
        return []
    try:
        data = json.loads(work_logs_json_str or '[]')
    except (json.JSONDecodeError, TypeError):
        logger.warning("work_logs_json inválido: %s", work_logs_json_str)
        return []
    if not isinstance(data, list):
        return []
    valid_count = sum(1 for item in data if isinstance(item, dict) and (item.get('activity_description') or '').strip())
    if valid_count == 0:
        logger.info("[DIARY_DEBUG] create_worklogs_from_json: nenhum item válido, não altera work logs (diary_id=%s)", diary.pk)
        return []
    logger.info("[DIARY_DEBUG] create_worklogs_from_json: recebidos %s itens, %s válidos (diary_id=%s)", len(data), valid_count, diary.pk)
    # Substituição: remove todos os work_logs atuais do diário
    deleted_count, _ = diary.work_logs.all().delete()
    if deleted_count:
        logger.info("Work logs anteriores do diário removidos: %s", deleted_count)
    saved = []
    for item in data:
        if not isinstance(item, dict):
            continue
        desc = (item.get('activity_description') or '').strip()
        if not desc:
            continue
        activity = _get_or_create_activity(project, desc)
        if not activity:
            continue
        work_stage = (item.get('work_stage') or 'AN').strip()[:2]
        if work_stage not in ('IN', 'AN', 'TE'):
            work_stage = 'AN'
        try:
            pct = Decimal(str(item.get('percentage_executed_today') or 0))
        except (ValueError, TypeError, InvalidOperation):
            pct = Decimal('0.00')
        try:
            acc = Decimal(str(item.get('accumulated_progress_snapshot') or 0))
        except (ValueError, TypeError, InvalidOperation):
            acc = Decimal('0.00')
        location = (item.get('location') or '')[:255]
        notes = (item.get('notes') or '')
        with transaction.atomic():
            try:
                worklog, created = DailyWorkLog.objects.get_or_create(
                    activity=activity,
                    diary=diary,
                    defaults={
                        'location': location,
                        'work_stage': work_stage,
                        'percentage_executed_today': pct,
                        'accumulated_progress_snapshot': acc,
                        'notes': notes,
                    },
                )
                if not created:
                    worklog.location = location
                    worklog.work_stage = work_stage
                    worklog.percentage_executed_today = pct
                    worklog.accumulated_progress_snapshot = acc
                    worklog.notes = notes
                    worklog.save()
                saved.append(worklog)
            except IntegrityError:
                existing = DailyWorkLog.objects.filter(activity=activity, diary=diary).first()
                if existing:
                    existing.location = location
                    existing.work_stage = work_stage
                    existing.percentage_executed_today = pct
                    existing.accumulated_progress_snapshot = acc
                    existing.notes = notes
                    existing.save()
                    saved.append(existing)
    logger.info("[DIARY_DEBUG] create_worklogs_from_json: criados/atualizados %s worklogs", len(saved))
    return saved


def create_occurrences_from_json(diary, occurrences_json_str, created_by):
    """
    Substitui as ocorrências do diário pelas enviadas em JSON.
    Remove as existentes e cria a partir da lista (description e opcionalmente tag_ids).

    Retorna a lista de DiaryOccurrence criados.
    created_by: usuário logado (obrigatório; DiaryOccurrence.created_by NOT NULL).
    """
    if not diary:
        logger.warning("create_occurrences_from_json: diary ausente, ignorando.")
        return []
    # Exige usuário logado com PK (evita IntegrityError em created_by_id e deixa o erro visível)
    if not created_by or getattr(created_by, 'pk', None) is None or getattr(created_by, 'is_anonymous', True):
        logger.error(
            "create_occurrences_from_json: created_by inválido (None, sem pk ou anônimo). "
            "Ocorrências não foram salvas. created_by=%s",
            type(created_by).__name__ if created_by else None,
        )
        raise ValueError(
            "É necessário estar logado para salvar ocorrências. "
            "O usuário (created_by) não foi passado ou é anônimo."
        )
    try:
        data = json.loads(occurrences_json_str or '[]')
    except (json.JSONDecodeError, TypeError) as e:
        logger.warning("occurrences_json inválido: %s - %s", occurrences_json_str, e)
        return []
    if not isinstance(data, list):
        return []
    valid_count = sum(1 for item in data if isinstance(item, dict) and (item.get('description') or '').strip())
    if valid_count == 0:
        logger.info("[DIARY_DEBUG] create_occurrences_from_json: nenhum item válido, não altera ocorrências (diary_id=%s)", diary.pk)
        return []
    logger.info("[DIARY_DEBUG] create_occurrences_from_json: recebidos %s itens, %s válidos (diary_id=%s)", len(data), valid_count, diary.pk)
    # Substituição: remove todas as ocorrências atuais do diário
    deleted_count, _ = diary.occurrences.all().delete()
    if deleted_count:
        logger.info("Ocorrências anteriores do diário removidas: %s", deleted_count)
    saved = []
    for item in data:
        if not isinstance(item, dict):
            continue
        description = (item.get('description') or '').strip()
        if not description:
            continue
        occ = DiaryOccurrence.objects.create(
            diary=diary,
            description=description,
            created_by=created_by,
        )
        tag_ids = item.get('tag_ids') or item.get('tags') or []
        if isinstance(tag_ids, list):
            tags = OccurrenceTag.objects.filter(pk__in=tag_ids, is_active=True)
            occ.tags.set(tags)
        saved.append(occ)
    logger.info("[DIARY_DEBUG] create_occurrences_from_json: criadas %s ocorrências", len(saved))
    return saved
