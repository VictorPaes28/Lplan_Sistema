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
    # «Administrador» = papel global de administração operacional do cliente (painel, comunicados,
    # configurações correlatas — não apenas GestControll). Legacy: mesmo privilégio reconhecido
    # também para grupos TrackHub Administrador e Central Aprovacoes Admin (ver migrações).
    ADMINISTRADOR = 'Administrador'
    RESPONSAVEL_EMPRESA = 'Responsavel Empresa'
    APROVADOR = 'Aprovador'
    SOLICITANTE = 'Solicitante'
    # Django auth.Group nomeado para o app de impeditivos (tela própria de Restrições).
    GESTAO_IMPEDIMENTOS = 'Gestão de Impeditivos'

    # ──────────────────────────────────────────────
    # TrackHub
    # ──────────────────────────────────────────────
    TRACKHUB = 'TrackHub'  # legado
    TRACKHUB_ADMIN = 'TrackHub Administrador'
    TRACKHUB_APROVADOR = 'TrackHub Aprovador'
    TRACKHUB_SOLICITANTE = 'TrackHub Solicitante'

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
    # Mapa de Suprimentos / Mapa de Controle / BI (Suprimentos)
    # ──────────────────────────────────────────────
    ENGENHARIA = 'Mapa de Suprimentos'
    MAPA_CONTROLE = 'Mapa de Controle'
    BI_DA_OBRA = 'BI da Obra'
    FERRAMENTA_OPERACIONAL = 'Ferramenta Operacional'

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
            self.TRACKHUB,
            self.TRACKHUB_ADMIN,
            self.TRACKHUB_APROVADOR,
            self.TRACKHUB_SOLICITANTE,
            self.GERENTES, self.ENGENHARIA, self.MAPA_CONTROLE, self.BI_DA_OBRA, self.FERRAMENTA_OPERACIONAL,
            self.CENTRAL_APROVACOES_ADMIN,
            self.CENTRAL_APROVACOES_APROVADOR,
            self.CENTRAL_APROVACOES_EXTERNO,
        ]


# Instância singleton para importar diretamente
GRUPOS = _Grupos()

# Papel único de administrador operacional: grupo canônico «Administrador» no cadastro;
# TrackHub Administrador / Central Aprovacoes Admin permanecem reconhecidos no código e na migração.
ADMINISTRADOR_GLOBAL_GROUP_NAMES = (
    GRUPOS.ADMINISTRADOR,
    GRUPOS.TRACKHUB_ADMIN,
    GRUPOS.CENTRAL_APROVACOES_ADMIN,
)
_ADMIN_GLOBAL_FSET = frozenset(ADMINISTRADOR_GLOBAL_GROUP_NAMES)


def usuario_tem_administracao_global_na_plataforma(user) -> bool:
    """True se o usuário tem o papel de administrador global (vários nomes Django legados)."""
    if not user or not getattr(user, "is_authenticated", False):
        return False
    return bool(_ADMIN_GLOBAL_FSET.intersection(user.groups.values_list("name", flat=True)))


# ──────────────────────────────────────────────
# UI de atribuição (cadastro/edição de usuário, aprovação de signup)
# ──────────────────────────────────────────────
# Grupos que permanecem no banco e nas regras de código, mas não devem ser
# atribuídos nem exibidos em formulários operacionais (legado preservado no save).

GRUPOS_OCULTOS_ATRIBUICAO_UI = frozenset({
    GRUPOS.RESPONSAVEL_EMPRESA,
    GRUPOS.TRACKHUB_ADMIN,
    GRUPOS.CENTRAL_APROVACOES_ADMIN,
})

# Nome técnico do grupo em auth.Group (POST / permissões) → texto na UI de atribuição.
# Mantém nome do arquivo de grupo sempre explícito no rótulo para não confundir papéis homônimos.
GRUPO_LABEL_ATRIBUICAO_UI = {
    GRUPOS.ADMINISTRADOR: 'Administrador do sistema',
    GRUPOS.APROVADOR: 'Aprovador GestControll',
    GRUPOS.SOLICITANTE: 'Solicitante GestControll',
    GRUPOS.GESTAO_IMPEDIMENTOS: 'Acesso a Restrições (Gestão de Impeditivos)',
    GRUPOS.TRACKHUB: 'TrackHub — perfil único (legado)',
    GRUPOS.TRACKHUB_ADMIN: 'TrackHub — administrador',
    GRUPOS.TRACKHUB_APROVADOR: 'TrackHub — aprovador',
    GRUPOS.TRACKHUB_SOLICITANTE: 'TrackHub — solicitante',
    GRUPOS.GERENTES: 'Acesso ao Diário de Obra',
    GRUPOS.ENGENHARIA: 'Acesso ao Mapa de Suprimentos',
    GRUPOS.MAPA_CONTROLE: 'Acesso ao Mapa de Controle',
    GRUPOS.BI_DA_OBRA: 'Acesso ao BI da Obra',
    GRUPOS.FERRAMENTA_OPERACIONAL: 'Acesso à Ferramenta de ambientes (Ferramenta Operacional)',
    GRUPOS.CENTRAL_APROVACOES_ADMIN: 'Central de Aprovações — configurador de fluxos',
    GRUPOS.CENTRAL_APROVACOES_APROVADOR: 'Central de Aprovações — fila interna',
    GRUPOS.CENTRAL_APROVACOES_EXTERNO: 'Central de Aprovações — aprovador externo',
}


def grupo_label_atribuicao(nome_oficial: str) -> str:
    """Rótulo para checkboxes de grupos; padrão é o próprio nome do grupo."""
    return GRUPO_LABEL_ATRIBUICAO_UI.get(nome_oficial, nome_oficial)


# Cada entrada = um módulo claro na UI (sem misturar domínios). Papéis do mesmo produto ficam na mesma seção em linha.
GROUP_UI_SECTIONS = [
    {
        'id': 'mod_admin_global',
        'title': 'Administrador do sistema',
        'description': (
            'Acesso ao painel administrativo do cliente, comunicados institucionais e à configuração '
            'onde aplicável nos módulos (inclui o que antes eram admins separados do TrackHub ou da Central).'
        ),
        'modules': [
            {
                'id': 'admin_plataforma_credencial',
                'title': '',
                'subtitle': '',
                'names': [GRUPOS.ADMINISTRADOR],
            },
        ],
    },
    {
        'id': 'mod_gestcontroll_pedidos',
        'title': 'GestControll — pedidos de compra',
        'description': '',
        'modules': [
            {
                'id': 'gestcontroll_papeis',
                'title': '',
                'subtitle': '',
                'names': [
                    GRUPOS.APROVADOR,
                    GRUPOS.SOLICITANTE,
                ],
            },
        ],
    },
    {
        'id': 'mod_diario_obra',
        'title': 'Diário de Obra',
        'description': '',
        'modules': [
            {
                'id': 'diario_rdo',
                'title': '',
                'subtitle': '',
                'names': [GRUPOS.GERENTES],
            },
        ],
    },
    {
        'id': 'mod_restricoes',
        'title': 'Restrições (Gestão de Impeditivos)',
        'description': '',
        'modules': [
            {
                'id': 'restricoes_operador',
                'title': '',
                'subtitle': '',
                'names': [GRUPOS.GESTAO_IMPEDIMENTOS],
            },
        ],
    },
    {
        'id': 'mod_trackhub',
        'title': 'TrackHub',
        'description': '',
        'modules': [
            {
                'id': 'trackhub_papeis',
                'title': '',
                'subtitle': '',
                'names': [
                    GRUPOS.TRACKHUB_APROVADOR,
                    GRUPOS.TRACKHUB_SOLICITANTE,
                    GRUPOS.TRACKHUB,
                ],
            },
        ],
    },
    {
        'id': 'mod_mapa_suprimentos',
        'title': 'Mapa de Suprimentos',
        'description': '',
        'modules': [
            {
                'id': 'mapa_sup_credencial',
                'title': '',
                'subtitle': '',
                'names': [GRUPOS.ENGENHARIA],
            },
        ],
    },
    {
        'id': 'mod_mapa_controle',
        'title': 'Mapa de Controle',
        'description': '',
        'modules': [
            {
                'id': 'mapa_controle_credencial',
                'title': '',
                'subtitle': '',
                'names': [GRUPOS.MAPA_CONTROLE],
            },
        ],
    },
    {
        'id': 'mod_bi_obra',
        'title': 'BI da Obra',
        'description': '',
        'modules': [
            {
                'id': 'bi_obra_credencial',
                'title': '',
                'subtitle': '',
                'names': [GRUPOS.BI_DA_OBRA],
            },
        ],
    },
    {
        'id': 'mod_ferramenta_ambientes',
        'title': 'Ferramenta Operacional',
        'description': '',
        'modules': [
            {
                'id': 'ferramenta_oper_ambientes',
                'title': '',
                'subtitle': '',
                'names': [GRUPOS.FERRAMENTA_OPERACIONAL],
            },
        ],
    },
    {
        'id': 'mod_central_aprov_institucional',
        'title': 'Central de Aprovações',
        'description': '',
        'modules': [
            {
                'id': 'central_fluxo_papeis',
                'title': '',
                'subtitle': '',
                'names': [
                    GRUPOS.CENTRAL_APROVACOES_APROVADOR,
                    GRUPOS.CENTRAL_APROVACOES_EXTERNO,
                ],
            },
        ],
    },
]


def grupos_secoes_para_atribuicao():
    """Seções para a UI com listas ``modules`` já resolvidas em ``groups`` [{group,label}, …]."""
    from django.contrib.auth.models import Group

    ensure_official_groups_exist()
    by_name = {g.name: g for g in Group.objects.filter(name__in=GRUPOS.TODOS)}
    sections_out = []
    for sec in GROUP_UI_SECTIONS:
        sec_row = {
            'id': sec['id'],
            'title': sec['title'],
            'description': sec.get('description', ''),
            'modules': [],
        }
        for mod in sec['modules']:
            row = {k: v for k, v in mod.items() if k != 'names'}
            row['groups'] = []
            for name in mod.get('names', []):
                if name in GRUPOS_OCULTOS_ATRIBUICAO_UI:
                    continue
                g = by_name.get(name)
                if g is not None:
                    row['groups'].append({'group': g, 'label': grupo_label_atribuicao(name)})
            sec_row['modules'].append(row)
        sections_out.append(sec_row)
    return sections_out


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
    for sec in GROUP_UI_SECTIONS:
        for mod in sec['modules']:
            for name in mod.get('names', []):
                if name in GRUPOS_OCULTOS_ATRIBUICAO_UI:
                    continue
                flat.append(name)
    qs = list(Group.objects.filter(name__in=flat))
    by_name = {g.name: g for g in qs}
    return [by_name[n] for n in flat if n in by_name]


def grupos_modulos_para_atribuicao():
    """
    Lista **plana** de módulos (sem nível ``seções``).

    Preferir ``grupos_secoes_para_atribuicao()`` nos templates novos para leitura.
    """
    return [module for sec in grupos_secoes_para_atribuicao() for module in sec['modules']]


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
