"""
Template tags customizados para o app core.
"""
from django import template
from datetime import datetime

register = template.Library()


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
        DiaryStatus.SALVAMENTO_PARCIAL: 'Rascunho',
        DiaryStatus.PREENCHENDO: 'Preenchido',
        DiaryStatus.REVISAR: 'Em revisão',
        DiaryStatus.APROVADO: 'Aprovado',
    }
    return labels.get(diary.status, 'Indefinido')


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
        DiaryStatus.SALVAMENTO_PARCIAL: 'report-status--draft',
        DiaryStatus.PREENCHENDO: 'report-status--approved',
        DiaryStatus.REVISAR: 'report-status--review',
        DiaryStatus.APROVADO: 'report-status--approved',
    }
    return classes.get(diary.status, 'report-status--approved')


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

