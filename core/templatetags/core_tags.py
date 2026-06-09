"""
Template tags customizados para o app core.
"""
import math
import re
from datetime import datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from django import template

register = template.Library()


@register.filter
def format_brl(value):
    """
    Formata valor numérico no padrão brasileiro (milhar com ponto e decimal com vírgula).
    Ex.: 1234.5 -> 1.234,50
    """
    if value is None or value == "":
        return "0,00"

    try:
        decimal_value = Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        integer_part, decimal_part = f"{decimal_value:.2f}".split(".")

        negative = integer_part.startswith("-")
        if negative:
            integer_part = integer_part[1:]

        grouped = []
        while integer_part:
            grouped.append(integer_part[-3:])
            integer_part = integer_part[:-3]
        integer_grouped = ".".join(reversed(grouped)) if grouped else "0"

        if negative:
            integer_grouped = f"-{integer_grouped}"

        return f"{integer_grouped},{decimal_part}"
    except (InvalidOperation, ValueError, TypeError):
        return "0,00"


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
def equipment_quantity_sum(value):
    """
    Soma o campo ``quantity`` de cada item (dict ou objeto com atributo quantity).
    Usado nos somatórios por coluna no detalhe do RDO.
    """
    if value is None:
        return 0
    total = 0
    for item in value:
        if isinstance(item, dict):
            total += int(item.get('quantity') or 0)
        else:
            total += int(getattr(item, 'quantity', 0) or 0)
    return total


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


def _user_display(user) -> str:
    if not user:
        return '—'
    return (user.get_full_name() or user.username or '—').strip()


def _truncate(text: str, limit: int = 72) -> str:
    text = (text or '').strip()
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + '…'


def _notification_resumo(notification, wo_map=None) -> str:
    """Resumo curto para a lista de notificações (uma linha, informação essencial)."""
    tipo = getattr(notification, 'notification_type', '') or ''
    msg = (getattr(notification, 'message', '') or '').strip()
    wo_map = wo_map or {}

    wo = None
    ek = (getattr(notification, 'event_key', '') or '').strip()
    if ek.startswith('gestao:wo:'):
        wo = wo_map.get(ek)

    if tipo in ('pedido_criado', 'pedido_reenviado', 'pedido_atualizado'):
        if wo:
            sol = _user_display(getattr(wo, 'criado_por', None))
            obra = getattr(getattr(wo, 'obra', None), 'nome', None) or '—'
            tipo_ped = (
                wo.get_tipo_solicitacao_display()
                if hasattr(wo, 'get_tipo_solicitacao_display')
                else '—'
            )
            return _truncate(f'{sol} · {obra} · {tipo_ped}')
        parts = [p.strip() for p in msg.split('·') if p.strip()]
        if parts:
            return _truncate(' · '.join(parts[:3]))
        return _truncate(msg)

    if tipo == 'pedido_aprovado':
        m = re.search(r'aprovado por (.+?)\.', msg, re.I)
        if m:
            return _truncate(f'{m.group(1).strip()} aprovou')
        return _truncate(msg)

    if tipo == 'pedido_reprovado':
        return 'Reprovado — ver comentários'

    if tipo == 'pedido_exclusao_solicitada':
        m = re.match(r'^(.+?)\s+pediu a exclusão(?: do pedido)?\.?\s*Motivo:\s*(.+)$', msg, re.I | re.S)
        if m:
            return _truncate(f'{m.group(1).strip()} · {m.group(2).strip()}')
        return _truncate(msg)

    if tipo == 'pedido_exclusao_aprovada':
        m = re.search(r'O aprovador (.+?) aprovou a exclusão', msg, re.I)
        if m:
            return _truncate(f'{m.group(1).strip()} aprovou exclusão')
        return _truncate(msg)

    if tipo == 'pedido_exclusao_rejeitada':
        m = re.search(r'O aprovador (.+?) rejeitou a exclusão', msg, re.I)
        com = re.search(r'Comentário:\s*(.+)$', msg, re.I | re.S)
        if m and com:
            return _truncate(f'{m.group(1).strip()} rejeitou · {com.group(1).strip()}')
        if m:
            return _truncate(f'{m.group(1).strip()} rejeitou exclusão')
        return _truncate(msg)

    if tipo == 'pedido_comentario':
        if ':' in msg:
            autor, texto = msg.split(':', 1)
            return _truncate(f'{autor.strip()} · {texto.strip()}')
        return _truncate(msg)

    if tipo == 'restricao_criada':
        m = re.search(r'"(.+?)"\s+na obra\s+(.+?)\.', msg, re.I | re.S)
        if m:
            return _truncate(f'{m.group(2).strip()} · {m.group(1).strip()}')
        return _truncate(msg)

    if tipo in ('restricao_status', 'restricao_prazo'):
        m = re.search(r'"(.+?)":\s*(.+)$', msg, re.S)
        if m:
            return _truncate(f'{m.group(1).strip()} · {m.group(2).strip()}')
        return _truncate(msg)

    if tipo == 'trackhub_etapa_concluida':
        m = re.search(
            r'A etapa "(.+?)" da pendência "(.+?)" foi concluída por (.+?)\.',
            msg,
            re.I | re.S,
        )
        if m:
            return _truncate(f'{m.group(3).strip()} · {m.group(1).strip()}')
        m = re.search(r'A pendência "(.+?)" foi (?:marcada como |totalmente )?concluída', msg, re.I)
        if m:
            return _truncate(f'{m.group(1).strip()} concluída')
        return _truncate(msg)

    if tipo == 'trackhub_prazo':
        m = re.search(r'etapa "(.+?)"', msg, re.I)
        if m:
            return _truncate(f'Prazo · {m.group(1).strip()}')
        return _truncate(msg)

    if tipo == 'rdo_pendente':
        m = re.search(
            r'relatório do dia\s+(.+?)\s+da obra\s+(.+?)\s+precisa',
            msg,
            re.I | re.S,
        )
        if m:
            return _truncate(f'{m.group(2).strip()} · {m.group(1).strip()}')
        return _truncate(msg)

    if tipo == 'rdo_aprovado':
        m = re.search(r'relatório do dia\s+(.+?)\s+foi aprovado', msg, re.I)
        if m:
            return _truncate(f'RDO {m.group(1).strip()} aprovado')
        return _truncate(msg)

    if tipo == 'rdo_reprovado':
        m = re.search(r'relatório do dia\s+(.+?)\s+foi reprovado', msg, re.I)
        if m:
            return _truncate(f'RDO {m.group(1).strip()} reprovado')
        return _truncate(msg)

    return _truncate(msg)


@register.simple_tag
def notification_resumo(notification, wo_map=None):
    return _notification_resumo(notification, wo_map)


_NOTIF_BADGE_LABELS = {
    'pedido_criado': 'Novo pedido',
    'pedido_reenviado': 'Reenvio',
    'pedido_atualizado': 'Pedido editado',
    'pedido_aprovado': 'Pedido aprovado',
    'pedido_reprovado': 'Pedido reprovado',
    'pedido_exclusao_solicitada': 'Exclusão solicitada',
    'pedido_exclusao_aprovada': 'Exclusão aprovada',
    'pedido_exclusao_rejeitada': 'Exclusão rejeitada',
    'restricao_criada': 'Nova restrição',
    'restricao_status': 'Restrição atualizada',
    'restricao_prazo': 'Prazo restrição',
    'trackhub_etapa_concluida': 'Etapa concluída',
    'trackhub_prazo': 'Prazo TrackHub',
    'rdo_pendente': 'RDO pendente',
    'rdo_aprovado': 'RDO aprovado',
    'rdo_reprovado': 'RDO reprovado',
}


@register.filter
def notification_badge_label(notification):
    tipo = getattr(notification, 'notification_type', '') or ''
    return _NOTIF_BADGE_LABELS.get(tipo) or notification.get_notification_type_display()


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
            from core.notification_utils import notificacoes_nao_lidas_qs

            count = notificacoes_nao_lidas_qs(user).count()
            return count if count else 0
        except Exception:
            return 0
    except Exception:
        # Se houver qualquer erro, retorna 0 silenciosamente
        return 0

