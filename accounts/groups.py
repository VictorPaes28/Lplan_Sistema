"""
Constantes centralizadas para os nomes de grupos do Sistema LPLAN.

Modelo de usuários e grupos:
  - Um usuário pode ter VÁRIOS grupos (ex.: Solicitante + Mapa de Suprimentos).
  - Os grupos definem em quais sistemas e com qual papel a pessoa atua:
    Gestão (GestControll), Diário de Obra ou Mapa de Suprimentos.
  - Na tela "Selecionar Sistema" o usuário vê apenas os sistemas para os quais
    tem pelo menos um grupo. Ex.: quem tem Solicitante e Mapa de Suprimentos acessa
    GestControll e Mapa de Suprimentos.

Uso:
    from accounts.groups import GRUPOS

    # Em decorators:
    @require_group(GRUPOS.ENGENHARIA)

    # Em queries:
    user.groups.filter(name=GRUPOS.GERENTES)

    # Em views:
    if user.groups.filter(name__in=GRUPOS.GESTAO_TODOS).exists():
        ...
"""


class _Grupos:
    """
    Container para nomes de grupos do sistema.
    Evita typos e centraliza alterações.
    """

    # ──────────────────────────────────────────────
    # Gestão de Aprovação (GestControll)
    # ──────────────────────────────────────────────
    # Painel do sistema (accounts/admin-central, locais por obra, análise): ver accounts.painel_sistema_access
    ADMINISTRADOR = 'Administrador'
    RESPONSAVEL_EMPRESA = 'Responsavel Empresa'
    APROVADOR = 'Aprovador'
    SOLICITANTE = 'Solicitante'
    # Nome do grupo em auth.Group (UI exibe "Restrições" em GROUP_UI_MODULES).
    GESTAO_IMPEDIMENTOS = 'Gestão de Impeditivos'

    # ──────────────────────────────────────────────
    # Diário de Obra (Core)
    # ──────────────────────────────────────────────
    GERENTES = 'Diário de Obra'

    # ──────────────────────────────────────────────
    # Central de Aprovações (workflow genérico)
    # ──────────────────────────────────────────────
    CENTRAL_APROVACOES_ADMIN = 'Central Aprovacoes Admin'
    CENTRAL_APROVACOES_APROVADOR = 'Central Aprovacoes Aprovador'
    CENTRAL_APROVACOES_EXTERNO = 'Central Aprovacoes Externo'

    # ──────────────────────────────────────────────
    # Mapa de Suprimentos (Suprimentos/Engenharia)
    # ──────────────────────────────────────────────
    ENGENHARIA = 'Mapa de Suprimentos'

    # ──────────────────────────────────────────────
    # Conjuntos úteis para verificações rápidas
    # ──────────────────────────────────────────────
    @property
    def GESTAO_TODOS(self):
        """Todos os grupos do módulo Gestão de Aprovação."""
        return [self.ADMINISTRADOR, self.RESPONSAVEL_EMPRESA, self.APROVADOR, self.SOLICITANTE]

    @property
    def TODOS(self):
        """Todos os grupos do sistema LPLAN."""
        return [
            self.ADMINISTRADOR, self.RESPONSAVEL_EMPRESA,
            self.APROVADOR, self.SOLICITANTE,
            self.GESTAO_IMPEDIMENTOS,
            self.GERENTES, self.ENGENHARIA,
            self.CENTRAL_APROVACOES_ADMIN,
            self.CENTRAL_APROVACOES_APROVADOR,
            self.CENTRAL_APROVACOES_EXTERNO,
        ]


# Instância singleton para importar diretamente
GRUPOS = _Grupos()

# ──────────────────────────────────────────────
# UI de atribuição (cadastro/edição de usuário, aprovação de signup)
# ──────────────────────────────────────────────
# Grupos que permanecem no banco e nas regras de código, mas não devem ser
# atribuídos nem exibidos em formulários operacionais (legado preservado no save).

GRUPOS_OCULTOS_ATRIBUICAO_UI = frozenset({GRUPOS.RESPONSAVEL_EMPRESA})

# Nome técnico do grupo em auth.Group (POST / permissões) → texto na UI de atribuição.
GRUPO_LABEL_ATRIBUICAO_UI = {
    GRUPOS.GESTAO_IMPEDIMENTOS: 'Gestão de Restrições',
}


def grupo_label_atribuicao(nome_oficial: str) -> str:
    """Rótulo para checkboxes de grupos; padrão é o próprio nome do grupo."""
    return GRUPO_LABEL_ATRIBUICAO_UI.get(nome_oficial, nome_oficial)

# Layout das telas de grupos (cadastro/edição de usuário, aprovação de signup).
#
# Como incluir um módulo novo no futuro:
#   1. Defina o(s) nome(s) do grupo em _Grupos acima, inclua em GRUPOS.TODOS e garanta criação
#      do registro em auth (ex.: setup_groups, bootstrap ou migração), como já é feito hoje.
#   2. Acrescente um dict abaixo com: id (slug estável), title, subtitle (opcional), names
#      (lista de constantes GRUPOS.* que pertencem a esse módulo na UI).
#   3. Templates usam grupos_modulos_para_atribuicao(): cada entrada em modulo.groups
#      é um dict {'group': Group, 'label': str} (label pode diferir do group.name).
#   4. Para ocultar um grupo só da seleção (legado), use GRUPOS_OCULTOS_ATRIBUICAO_UI — não
#      remova o nome de GRUPOS.TODOS nem das regras de permissão.
#
GROUP_UI_MODULES = [
    {
        'id': 'gestcontroll',
        'title': 'Gestão de pedidos (GestControll)',
        'subtitle': 'Pedidos de obra, vínculo por obra e papéis de solicitante ou aprovador.',
        'names': [
            GRUPOS.ADMINISTRADOR,
            GRUPOS.APROVADOR,
            GRUPOS.SOLICITANTE,
        ],
    },
    {
        'id': 'impeditivos',
        'title': 'Restrições',
        'subtitle': 'Restrições, pendências e tarefas por obra',
        'names': [GRUPOS.GESTAO_IMPEDIMENTOS],
    },
    {
        'id': 'diario',
        'title': 'Diário de Obra',
        'subtitle': 'Registro diário (RDO). O BI da obra segue as regras atuais do Diário e da obra.',
        'names': [GRUPOS.GERENTES],
    },
    {
        'id': 'mapa',
        'title': 'Mapa de Controle e suprimentos',
        'subtitle': 'Mapa de Controle (execução físico) e planejamento no módulo Mapa.',
        'names': [GRUPOS.ENGENHARIA],
    },
    {
        'id': 'central_aprovacoes',
        'title': 'Central de Aprovações',
        'subtitle': 'Fluxos por obra e categoria (admin, aprovador ou externo).',
        'names': [
            GRUPOS.CENTRAL_APROVACOES_ADMIN,
            GRUPOS.CENTRAL_APROVACOES_APROVADOR,
            GRUPOS.CENTRAL_APROVACOES_EXTERNO,
        ],
    },
]


def ensure_official_groups_exist():
    """Garante que existam linhas em auth_group para todos os nomes oficiais."""
    from django.contrib.auth.models import Group

    for nome in GRUPOS.TODOS:
        Group.objects.get_or_create(name=nome)


def grupos_ordenados_atribuivel():
    """
    Lista plana de objetos Group na ordem dos módulos, excluindo grupos ocultos na UI.
    """
    from django.contrib.auth.models import Group

    ensure_official_groups_exist()
    flat = []
    for mod in GROUP_UI_MODULES:
        for name in mod['names']:
            if name in GRUPOS_OCULTOS_ATRIBUICAO_UI:
                continue
            flat.append(name)
    qs = list(Group.objects.filter(name__in=flat))
    by_name = {g.name: g for g in qs}
    return [by_name[n] for n in flat if n in by_name]


def grupos_modulos_para_atribuicao():
    """
    Lista de seções para templates: cada item tem id, title, subtitle, groups.

    Cada elemento de groups é ``{'group': Group, 'label': str}``; ``label`` segue
    GRUPO_LABEL_ATRIBUICAO_UI quando houver, mantendo ``group.name``
    para value do checkbox e permissões.
    """
    from django.contrib.auth.models import Group

    ensure_official_groups_exist()
    by_name = {g.name: g for g in Group.objects.filter(name__in=GRUPOS.TODOS)}
    out = []
    for mod in GROUP_UI_MODULES:
        row = {k: v for k, v in mod.items() if k != 'names'}
        row['groups'] = []
        for name in mod['names']:
            if name in GRUPOS_OCULTOS_ATRIBUICAO_UI:
                continue
            g = by_name.get(name)
            if g is not None:
                row['groups'].append(
                    {'group': g, 'label': grupo_label_atribuicao(name)}
                )
        out.append(row)
    return out


def filtrar_grupos_post_atribuivel(raw_names):
    """Normaliza POST de grupos por nome: só oficiais atribuíveis, sem duplicatas."""
    allowed = set(GRUPOS.TODOS) - GRUPOS_OCULTOS_ATRIBUICAO_UI
    seen = set()
    out = []
    for name in raw_names or []:
        v = (name or '').strip()
        if not v or v not in allowed or v in seen:
            continue
        seen.add(v)
        out.append(v)
    return out


def merge_grupos_legados_ocultos(user, post_names_filtrados):
    """Seleção do formulário + grupos ocultos que o usuário já possui (legado)."""
    legacy = set(user.groups.values_list('name', flat=True)) & GRUPOS_OCULTOS_ATRIBUICAO_UI
    base = list(post_names_filtrados)
    for n in legacy:
        if n not in base:
            base.append(n)
    return base


def normalize_group_pks_post_atribuivel(raw_ids):
    """IDs de Group vindos do POST: só grupos atribuíveis (exclui ocultos e inexistentes)."""
    from django.contrib.auth.models import Group

    ensure_official_groups_exist()
    allowed_names = set(GRUPOS.TODOS) - GRUPOS_OCULTOS_ATRIBUICAO_UI
    out = set()
    for x in raw_ids or []:
        try:
            pk = int(x)
        except (TypeError, ValueError):
            continue
        g = Group.objects.filter(pk=pk).first()
        if not g or g.name not in allowed_names:
            continue
        out.add(pk)
    return out


def merge_grupos_legados_ocultos_por_pk(user, normalized_pks):
    """União dos PKs do formulário com grupos ocultos já possuídos pelo usuário."""
    from django.contrib.auth.models import Group

    hidden_ids = set(
        Group.objects.filter(name__in=GRUPOS_OCULTOS_ATRIBUICAO_UI).values_list('pk', flat=True)
    )
    cur_hidden = set(user.groups.filter(pk__in=hidden_ids).values_list('pk', flat=True))
    return set(normalized_pks) | cur_hidden
