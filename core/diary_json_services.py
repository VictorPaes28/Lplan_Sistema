"""
Serviço para criar/atualizar atividades (work_logs) e ocorrências do diário a partir de JSON.
Usado pelo formulário do diário ao salvar via work_logs_json e occurrences_json no POST.
"""
import json
import logging
import re
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

WORK_LOG_PREFIX = 'work_logs'
OCCURRENCE_PREFIX = 'ocorrencias'
_WORK_LOG_INDEX_RE = re.compile(r'^work_logs-(\d+)-')
_OCCURRENCE_INDEX_RE = re.compile(r'^ocorrencias-(\d+)-')


def _post_value(post, key, default=''):
    """Último valor de um campo no POST (QueryDict pode repetir chaves)."""
    if hasattr(post, 'getlist'):
        values = post.getlist(key)
        if not values:
            return default
        return values[-1]
    val = post.get(key, default)
    return default if val is None else val


def _is_formset_row_deleted(post, prefix: str, index: int) -> bool:
    val = _post_value(post, f'{prefix}-{index}-DELETE', '')
    return str(val).lower() in ('on', 'true', '1', 'yes')


def _indices_from_post(post, prefix: str, total_key: str, index_re) -> list[int]:
    indices: set[int] = set()
    try:
        total = int(_post_value(post, total_key, '0') or 0)
    except (TypeError, ValueError):
        total = 0
    if total > 0:
        indices.update(range(total))
    if hasattr(post, 'keys'):
        for key in post.keys():
            match = index_re.match(key)
            if match:
                indices.add(int(match.group(1)))
    return sorted(indices)


def extract_work_logs_from_post(post):
    """
    Lê work_logs-N-* enviados pelo formset HTML (independente do JS).
    Retorna lista no mesmo formato de work_logs_json.
    """
    items = []
    for index in _indices_from_post(
        post, WORK_LOG_PREFIX, f'{WORK_LOG_PREFIX}-TOTAL_FORMS', _WORK_LOG_INDEX_RE
    ):
        if _is_formset_row_deleted(post, WORK_LOG_PREFIX, index):
            continue
        desc = (_post_value(post, f'{WORK_LOG_PREFIX}-{index}-activity_description') or '').strip()
        if not desc:
            continue
        work_stage = (_post_value(post, f'{WORK_LOG_PREFIX}-{index}-work_stage') or 'AN').strip()[:2]
        if work_stage not in ('IN', 'AN', 'TE'):
            work_stage = 'AN'
        items.append({
            'activity_description': desc,
            'work_stage': work_stage,
            'percentage_executed_today': _post_value(
                post, f'{WORK_LOG_PREFIX}-{index}-percentage_executed_today', '0'
            ),
            'accumulated_progress_snapshot': _post_value(
                post, f'{WORK_LOG_PREFIX}-{index}-accumulated_progress_snapshot', '0'
            ),
            'location': (_post_value(post, f'{WORK_LOG_PREFIX}-{index}-location') or '')[:255],
            'notes': _post_value(post, f'{WORK_LOG_PREFIX}-{index}-notes') or '',
        })
    return items


def _parse_work_logs_json(work_logs_json_str):
    try:
        data = json.loads(work_logs_json_str or '[]')
    except (json.JSONDecodeError, TypeError):
        return []
    if not isinstance(data, list):
        return []
    return [item for item in data if isinstance(item, dict)]


def _merge_work_log_items(json_items, formset_items):
    """União por nome de atividade; campos do formset prevalecem em duplicatas."""
    by_desc: dict[str, dict] = {}
    order: list[str] = []
    for item in json_items:
        key = (item.get('activity_description') or '').strip().lower()
        if not key:
            continue
        by_desc[key] = dict(item)
        order.append(key)
    for item in formset_items:
        key = (item.get('activity_description') or '').strip().lower()
        if not key:
            continue
        if key in by_desc:
            merged = dict(by_desc[key])
            merged.update(item)
            by_desc[key] = merged
        else:
            by_desc[key] = dict(item)
            order.append(key)
    return [by_desc[key] for key in order if key in by_desc]


def reconcile_work_logs_payload(post, work_logs_json_str):
    """
    Combina work_logs_json (JS) com campos work_logs-N-* do POST (formset).
    Se o JS perder linhas, o servidor recupera a partir do HTML enviado.
    """
    json_items = _parse_work_logs_json(work_logs_json_str)
    formset_items = extract_work_logs_from_post(post)

    json_valid = sum(
        1 for item in json_items if (item.get('activity_description') or '').strip()
    )
    formset_valid = len(formset_items)

    if not formset_items:
        return work_logs_json_str or '[]'

    if not json_items:
        merged = formset_items
    else:
        merged = _merge_work_log_items(json_items, formset_items)

    if formset_valid > json_valid:
        logger.warning(
            'work_logs_json incompleto (%s atividade(s)) vs formset POST (%s); '
            'payload reconciliado no servidor.',
            json_valid,
            formset_valid,
        )

    return json.dumps(merged, ensure_ascii=False)


def extract_occurrences_from_post(post):
    """Lê ocorrencias-N-* do POST (mesmo formato de occurrences_json)."""
    items = []
    for index in _indices_from_post(
        post, OCCURRENCE_PREFIX, f'{OCCURRENCE_PREFIX}-TOTAL_FORMS', _OCCURRENCE_INDEX_RE
    ):
        if _is_formset_row_deleted(post, OCCURRENCE_PREFIX, index):
            continue
        description = (_post_value(post, f'{OCCURRENCE_PREFIX}-{index}-description') or '').strip()
        if not description:
            continue
        tag_ids: list[int] = []
        tag_key = f'{OCCURRENCE_PREFIX}-{index}-tags'
        if hasattr(post, 'getlist'):
            raw_tags = post.getlist(tag_key)
        else:
            raw = post.get(tag_key)
            raw_tags = raw if isinstance(raw, list) else ([raw] if raw else [])
        for raw in raw_tags:
            try:
                tag_id = int(raw)
            except (TypeError, ValueError):
                continue
            if tag_id not in tag_ids:
                tag_ids.append(tag_id)
        items.append({'description': description, 'tag_ids': tag_ids})
    return items


def _parse_occurrences_json(occurrences_json_str):
    try:
        data = json.loads(occurrences_json_str or '[]')
    except (json.JSONDecodeError, TypeError):
        return []
    if not isinstance(data, list):
        return []
    return [item for item in data if isinstance(item, dict)]


def _merge_occurrence_items(json_items, formset_items):
    by_desc: dict[str, dict] = {}
    order: list[str] = []
    for item in json_items:
        key = (item.get('description') or '').strip().lower()
        if not key:
            continue
        by_desc[key] = {
            'description': (item.get('description') or '').strip(),
            'tag_ids': list(item.get('tag_ids') or item.get('tags') or []),
        }
        order.append(key)
    for item in formset_items:
        key = (item.get('description') or '').strip().lower()
        if not key:
            continue
        if key in by_desc:
            merged = dict(by_desc[key])
            merged.update(item)
            by_desc[key] = merged
        else:
            by_desc[key] = dict(item)
            order.append(key)
    return [by_desc[key] for key in order if key in by_desc]


def reconcile_occurrences_payload(post, occurrences_json_str):
    """Combina occurrences_json com campos ocorrencias-N-* do POST."""
    json_items = _parse_occurrences_json(occurrences_json_str)
    formset_items = extract_occurrences_from_post(post)

    json_valid = sum(1 for item in json_items if (item.get('description') or '').strip())
    formset_valid = len(formset_items)

    if not formset_items:
        return occurrences_json_str or '[]'

    if not json_items:
        merged = formset_items
    else:
        merged = _merge_occurrence_items(json_items, formset_items)

    if formset_valid > json_valid:
        logger.warning(
            'occurrences_json incompleto (%s) vs formset POST (%s); payload reconciliado.',
            json_valid,
            formset_valid,
        )

    return json.dumps(merged, ensure_ascii=False)


def _get_or_create_activity(project, activity_description):
    """
    Obtém ou cria uma Activity no projeto a partir da descrição.
    Replica a lógica de DailyWorkLogForm.save() para criação de Activity.
    """
    activity_description = (activity_description or '').strip()
    if not activity_description:
        return None
    # Activity.name é CharField(max_length=255); evita DataError no MySQL.
    activity_name = activity_description[:255].strip()
    if not activity_name:
        return None
    try:
        activity = Activity.objects.get(project=project, name=activity_name)
        return activity
    except Activity.DoesNotExist:
        pass
    base_code = f'GEN-{activity_name[:20].upper().replace(" ", "-").replace("/", "-")}'
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
                name=activity_name,
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
                    return Activity.objects.get(project=project, name=activity_name)
                except Activity.DoesNotExist:
                    raise
    return None


def create_worklogs_from_json(diary, project, work_logs_json_str, replace_existing=False):
    """
    Cria/atualiza registros DailyWorkLog do diário a partir de JSON.
    Quando replace_existing=True, remove os existentes antes de recriar.
    Quando replace_existing=False (padrão), faz upsert sem apagar os atuais.

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
    if replace_existing and len(data) == 0:
        deleted_count, _ = diary.work_logs.all().delete()
        if deleted_count:
            logger.info("Work logs anteriores do diário removidos (JSON vazio): %s", deleted_count)
        return []
    if replace_existing and valid_count == 0:
        deleted_count, _ = diary.work_logs.all().delete()
        if deleted_count:
            logger.info(
                "Work logs anteriores do diário removidos (JSON sem atividades válidas): %s",
                deleted_count,
            )
        return []
    if valid_count == 0:
        return []
    if replace_existing:
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
    return saved


def create_occurrences_from_json(diary, occurrences_json_str, created_by, replace_existing=False):
    """
    Cria/atualiza ocorrências do diário a partir de JSON.
    Quando replace_existing=True, remove as existentes antes de recriar.
    Quando replace_existing=False (padrão), apenas adiciona novas (sem apagar as atuais).

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
    if replace_existing and len(data) == 0:
        deleted_count, _ = diary.occurrences.all().delete()
        if deleted_count:
            logger.info("Ocorrências anteriores do diário removidas (JSON vazio): %s", deleted_count)
        return []
    if replace_existing and valid_count == 0:
        deleted_count, _ = diary.occurrences.all().delete()
        if deleted_count:
            logger.info(
                "Ocorrências anteriores do diário removidas (JSON sem itens válidos): %s",
                deleted_count,
            )
        return []
    if valid_count == 0:
        return []
    if replace_existing:
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
    return saved
