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
    ADMINISTRADOR = 'Administrador'
    RESPONSAVEL_EMPRESA = 'Responsavel Empresa'
    APROVADOR = 'Aprovador'
    SOLICITANTE = 'Solicitante'

    # ──────────────────────────────────────────────
    # Diário de Obra (Core)
    # ──────────────────────────────────────────────
    GERENTES = 'Diário de Obra'

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
            self.GERENTES, self.ENGENHARIA,
        ]


# Instância singleton para importar diretamente
GRUPOS = _Grupos()
