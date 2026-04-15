"""
Template tags customizados para o app core.
"""
import math
from datetime import datetime

from django import template

register = template.Library()


def _balanced_partition(seq: list, k: int) -> list:
    """Divide ``seq`` em ``k`` sublistas com tamanhos o mais uniformes possível (k entre 1 e len(seq))."""
    n = len(seq)
    if n == 0:
        return []
    if k < 1:
        k = 1
    k = min(k, n)
    base, rem = divmod(n, k)
    chunks = []
    idx = 0
    for i in range(k):
        size = base + (1 if i < rem else 0)
        chunks.append(seq[idx : idx + size])
        idx += size
    return chunks


@register.filter
def can_edit(diary, user):
    """
    Template filter para verificar se um diário pode ser editado por um usuário.
    
    Uso: {% if diary|can_edit:user %}
    """
    if not diary or not user:
        return False
    return diary.can_be_edited_by(user)


@register.filter
def report_status_label(diary):
    """
    Retorna o rótulo de exibição do status do diário para a lista de relatórios.
    Uso: {{ diary|report_status_label }}
    """
    if not diary or not hasattr(diary, 'status'):
        return 'Indefinido'
    from core.models import DiaryStatus
    labels = {
        DiaryStatus.SALVAMENTO_PARCIAL.value: 'Rascunho',
        DiaryStatus.PREENCHENDO.value: 'Preenchido',
        DiaryStatus.AGUARDANDO_APROVACAO_GESTOR.value: 'Aguardando aprovação',
        DiaryStatus.REPROVADO_GESTOR.value: 'Reprovado',
        DiaryStatus.REVISAR.value: 'Em revisão',
        DiaryStatus.APROVADO.value: 'Aprovado',
    }
    status_key = getattr(diary.status, 'value', diary.status)
    return labels.get(status_key, 'Indefinido')


@register.filter
def report_status_css(diary):
    """
    Retorna a classe CSS do badge de status do diário (report-status--draft, etc.).
    Uso: {{ diary|report_status_css }}
    """
    if not diary or not hasattr(diary, 'status'):
        return 'report-status--approved'
    from core.models import DiaryStatus
    classes = {
        DiaryStatus.SALVAMENTO_PARCIAL.value: 'report-status--draft',
        DiaryStatus.PREENCHENDO.value: 'report-status--approved',
        DiaryStatus.AGUARDANDO_APROVACAO_GESTOR.value: 'report-status--pending-approval',
        DiaryStatus.REPROVADO_GESTOR.value: 'report-status--rejected',
        DiaryStatus.REVISAR.value: 'report-status--review',
        DiaryStatus.APROVADO.value: 'report-status--approved',
    }
    status_key = getattr(diary.status, 'value', diary.status)
    return classes.get(status_key, 'report-status--approved')


@register.filter
def report_status_style(diary):
    """
    Retorna string de estilo inline para o badge de status (cor que não pode ser sobrescrita por CSS).
    Uso: <span class="report-status" style="{{ diary|report_status_style }}">...
    """
    if not diary or not hasattr(diary, 'status'):
        return 'background-color:#d1fae5;color:#047857'
    from core.models import DiaryStatus
    status_key = getattr(diary.status, 'value', diary.status)
    styles = {
        DiaryStatus.SALVAMENTO_PARCIAL.value: 'background-color:#ffedd5;color:#c2410c',
        DiaryStatus.PREENCHENDO.value: 'background-color:#d1fae5;color:#047857',
        DiaryStatus.AGUARDANDO_APROVACAO_GESTOR.value: 'background-color:#dbeafe;color:#1d4ed8',
        DiaryStatus.REPROVADO_GESTOR.value: 'background-color:#fee2e2;color:#b91c1c',
        DiaryStatus.REVISAR.value: 'background-color:#fef3c7;color:#b45309',
        DiaryStatus.APROVADO.value: 'background-color:#d1fae5;color:#047857',
    }
    return styles.get(status_key, 'background-color:#d1fae5;color:#047857')


@register.filter
def chunk_list(value, chunk_size):
    """
    Divide uma sequência em sublistas com até ``chunk_size`` itens (útil para colunas no detalhe do RDO).

    Uso: {% for chunk in equipment_list|chunk_list:6 %}
    """
    try:
        n = int(chunk_size)
    except (TypeError, ValueError):
        n = 6
    if n < 1:
        n = 6
    if value is None:
        return []
    seq = list(value)
    return [seq[i : i + n] for i in range(0, len(seq), n)]


@register.filter
def partition_list(value, num_parts):
    """
    Divide a sequência em até ``num_parts`` partes equilibradas (ex.: 5 colunas de equipamentos).

    Reordena apenas o agrupamento: cada elemento aparece exatamente uma vez, sem alterar
    dicionários/objetos (as quantidades exibidas são as mesmas da lista de entrada).
    """
    try:
        k = int(num_parts)
    except (TypeError, ValueError):
        k = 5
    if k < 1:
        k = 1
    if value is None:
        return []
    seq = list(value)
    if not seq:
        return []
    return _balanced_partition(seq, k)


@register.filter
def equipment_display_chunks(value, rows_per_table=14):
    """
    Equipamentos no detalhe do RDO: uma tabela enquanto ``len <= rows_per_table``;
    acima disso, reparte em várias tabelas (até 5 colunas) para não concentrar scroll.

    Uso: {% for chunk in equipment_list|equipment_display_chunks:14 %}
    """
    try:
        t = int(rows_per_table)
    except (TypeError, ValueError):
        t = 14
    if t < 1:
        t = 14
    if value is None:
        return []
    seq = list(value)
    n = len(seq)
    if n == 0:
        return []
    if n <= t:
        return [seq]
    k = min(5, math.ceil(n / t))
    k = max(k, 2)
    return _balanced_partition(seq, k)


@register.filter
def get_item(dictionary, key):
    """Obtém um item de um dicionário."""
    if dictionary and isinstance(dictionary, dict):
        return dictionary.get(key)
    return None


@register.filter
def sum_values(dictionary):
    """Soma os valores de um dicionário."""
    if dictionary and isinstance(dictionary, dict):
        return sum(dictionary.values())
    return 0


@register.filter
def parse_date(date_string):
    """Converte uma string de data ISO para objeto date."""
    try:
        return datetime.fromisoformat(date_string).date()
    except (ValueError, AttributeError, TypeError):
        return None


@register.filter
def weekday_name(date_value):
    """Retorna o nome do dia da semana em português."""
    if not date_value:
        return ""
    
    weekdays = ['Segunda-Feira', 'Terça-Feira', 'Quarta-Feira', 'Quinta-Feira', 'Sexta-Feira', 'Sábado', 'Domingo']
    try:
        weekday_index = date_value.weekday()  # 0 = Monday, 6 = Sunday
        return weekdays[weekday_index]
    except (AttributeError, IndexError):
        return ""


@register.simple_tag(takes_context=False)
def get_unread_notifications_count(user):
    """Retorna o número de notificações não lidas do usuário."""
    try:
        # Verifica se o usuário existe e está autenticado
        if not user:
            return 0
        if not hasattr(user, 'is_authenticated'):
            return 0
        if not user.is_authenticated:
            return 0
        
        # Tenta importar o modelo
        try:
            from core.models import Notification
        except ImportError:
            return 0
        
        # Tenta buscar as notificações
        try:
            count = Notification.objects.filter(user=user, is_read=False).count()
            return count if count else 0
        except Exception:
            return 0
    except Exception:
        # Se houver qualquer erro, retorna 0 silenciosamente
        return 0

