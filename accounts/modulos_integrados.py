"""
Catálogo e estado operacional dos módulos em «Sistemas integrados».
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from django.core.cache import cache
from django.urls import reverse

CACHE_KEY = 'accounts:modulos_integrados_status'
CACHE_TTL = 30


@dataclass(frozen=True)
class ModuloMeta:
    codigo: str
    nome: str
    descricao: str
    css: str
    icon: str
    icon_class: str
    url_name: str
    stats_key: str
    stats_fields: tuple[tuple[str, str], ...]


MODULOS_INTEGRADOS: tuple[ModuloMeta, ...] = (
    ModuloMeta(
        'diario',
        'Diário de Obra',
        'Relatórios diários de obra',
        'diario',
        'fa-book',
        'icon-diario',
        'select-project',
        'stats_diario',
        (('Projetos ativos', 'projetos_ativos'), ('Diários registrados', 'diarios')),
    ),
    ModuloMeta(
        'gestao',
        'GestControll',
        'Ordens de serviço e aprovações',
        'gestao',
        'fa-clipboard-check',
        'icon-gestao',
        'gestao:home',
        'stats_gestao',
        (('Ordens de serviço', 'ordens'), ('Aprovações', 'aprovacoes')),
    ),
    ModuloMeta(
        'mapa',
        'Mapa de Suprimentos',
        'Suprimentos e insumos',
        'mapa',
        'fa-map',
        'icon-mapa',
        'mapa_obras:home',
        'stats_mapa',
        (
            ('Obras ativas', 'obras_ativas'),
            ('Insumos cadastrados', 'insumos'),
            ('Itens no mapa', 'itens_mapa'),
        ),
    ),
    ModuloMeta(
        'workflow',
        'Central de Aprovações',
        'Fluxos e filas de aprovação por obra',
        'workflow',
        'fa-check-double',
        'icon-workflow',
        'workflow_aprovacao:home',
        'stats_workflow',
        (('Processos', 'processos'), ('Aguardando alçada', 'aguardando')),
    ),
    ModuloMeta(
        'trackhub',
        'TrackHub',
        'Etapas, prazos e pendências da obra',
        'trackhub',
        'fa-compass',
        'icon-trackhub',
        'trackhub:fila',
        'stats_trackhub',
        (('Pendências', 'pendencias'), ('Em aberto', 'em_aberto')),
    ),
    ModuloMeta(
        'impedimentos',
        'Restrições',
        'Bloqueios e pendências por obra',
        'imped',
        'fa-shield-alt',
        'icon-imped',
        'impedimentos:select_obra',
        'stats_impedimentos',
        (('Registros', 'total'), ('Sem conclusão', 'em_aberto')),
    ),
)

MODULO_BY_CODIGO = {m.codigo: m for m in MODULOS_INTEGRADOS}


def invalidate_modulos_cache() -> None:
    cache.delete(CACHE_KEY)


def _row_to_status(row) -> dict[str, Any]:
    if row is None:
        return {
            'ativo': True,
            'mensagem': '',
            'previsao_retorno': None,
            'previsao_retorno_label': '',
            'atualizado_em': None,
            'atualizado_por_nome': '',
            'indisponivel': False,
        }
    previsao = row.previsao_retorno
    label = ''
    if previsao:
        label = previsao.strftime('%d/%m/%Y')
    por = ''
    if row.atualizado_por_id:
        por = row.atualizado_por.get_full_name() or row.atualizado_por.username
    return {
        'ativo': row.ativo,
        'mensagem': (row.mensagem or '').strip(),
        'previsao_retorno': previsao,
        'previsao_retorno_label': label,
        'atualizado_em': row.atualizado_em,
        'atualizado_por_nome': por,
        'indisponivel': not row.ativo,
    }


def default_modulos_status_map() -> dict[str, dict[str, Any]]:
    """Mapa com todos os módulos ativos (fallback seguro para templates e middleware)."""
    return {meta.codigo: _row_to_status(None) for meta in MODULOS_INTEGRADOS}


def load_modulos_status_map() -> dict[str, dict[str, Any]]:
    cached = cache.get(CACHE_KEY)
    if cached is not None:
        return cached

    from django.db.utils import OperationalError, ProgrammingError

    try:
        from accounts.models import ModuloIntegradoStatus

        rows = {
            r.codigo: r
            for r in ModuloIntegradoStatus.objects.select_related('atualizado_por').all()
        }
        result = {meta.codigo: _row_to_status(rows.get(meta.codigo)) for meta in MODULOS_INTEGRADOS}
    except (ProgrammingError, OperationalError):
        # Migration ainda não aplicada ou tabela indisponível — não derruba o site.
        result = default_modulos_status_map()

    cache.set(CACHE_KEY, result, CACHE_TTL)
    return result


def modulo_esta_ativo(codigo: str) -> bool:
    return load_modulos_status_map().get(codigo, {}).get('ativo', True)


# Rotas de suprimentos/engenharia bloqueadas pelo toggle «Mapa de Suprimentos».
# BI da Obra, Ferramenta de ambientes e Mapa Controle ficam fora deste escopo.
MAPA_SUPRIMENTOS_ENGENHARIA_PREFIXES = (
    '/engenharia/mapa/',
    '/engenharia/mapa-servico/',
    '/engenharia/dashboard',
    '/engenharia/insumo/',
)


def _path_is_mapa_suprimentos(path: str) -> bool:
    if path.startswith('/mapa/'):
        return True
    if path == '/engenharia/mapa' or path.startswith('/engenharia/mapa?'):
        return True
    return any(path.startswith(prefix) for prefix in MAPA_SUPRIMENTOS_ENGENHARIA_PREFIXES)


def resolve_modulo_from_path(path: str) -> str | None:
    """Retorna o código do módulo associado ao path ou None se não aplicável."""
    if not path:
        return None
    path = path if path.startswith('/') else f'/{path}'

    prefix_map = (
        ('/gestao/', 'gestao'),
        ('/impedimentos/', 'impedimentos'),
        ('/trackhub/', 'trackhub'),
        ('/aprovacoes/', 'workflow'),
    )
    for prefix, codigo in prefix_map:
        if path.startswith(prefix):
            return codigo

    if _path_is_mapa_suprimentos(path):
        return 'mapa'

    # Infraestrutura, painel, auth e cadastro central — nunca bloquear por módulo inativo.
    global_exempt = (
        '/accounts/',
        '/admin/',
        '/api/',
        '/assistente/',
        '/comunicados/',
        '/static/',
        '/media/',
        '/select-system',
        '/login',
        '/logout',
        '/signup',
        '/cadastro/',
        '/password-reset',
        '/central/',
        '/projects/',
        '/support',
        '/notifications',
        '/profile',
        '/central-ajuda',
        '/sw-rdo-offline.js',
    )
    if path.startswith(global_exempt):
        return None

    # Só URLs operacionais do Diário entram no bloqueio de manutenção do módulo.
    # (Antes: qualquer path desconhecido caía como «diario» e bloqueava senha, cadastro, etc.)
    diario_operational = (
        '/select-project/',
        '/dashboard/',
        '/reports/',
        '/diaries/',
        '/diaries',
        '/labor/',
        '/equipment/',
        '/filters/',
        '/analytics/',
        '/calendar-events/',
        '/cliente/diarios/',
        '/htmx/projects/',
        '/htmx/activities/',
    )
    if path.startswith(diario_operational):
        return 'diario'

    return None


def build_modulos_cards_for_admin(context: dict) -> list[dict[str, Any]]:
    status_map = load_modulos_status_map()
    cards = []
    for meta in MODULOS_INTEGRADOS:
        stats = context.get(meta.stats_key) or {}
        st = status_map.get(meta.codigo, _row_to_status(None))
        try:
            access_url = reverse(meta.url_name)
        except Exception:
            access_url = '#'
        stats_rows = [
            (label, stats.get(field, '—') if stats else '—')
            for label, field in meta.stats_fields
        ]
        cards.append(
            {
                'meta': meta,
                'stats_rows': stats_rows,
                'status': st,
                'access_url': access_url,
            }
        )
    return cards


def ensure_modulos_seeded() -> None:
    from accounts.models import ModuloIntegradoStatus

    for meta in MODULOS_INTEGRADOS:
        ModuloIntegradoStatus.objects.get_or_create(
            codigo=meta.codigo,
            defaults={'nome': meta.nome, 'ativo': True},
        )
