"""Papéis configuráveis do fluxo de admissão (quem faz o quê em cada etapa)."""
from __future__ import annotations

from recursos_humanos.models import PapelFluxoAdmissao

ETAPAS_FLUXO_LABELS = [
    (1, 'Requisição'),
    (2, 'Conferência de docs'),
    (3, 'Validação final'),
    (4, 'Contrato (ZapSign)'),
    (5, 'Ativo'),
]

PAPEL_POR_ETAPA = {
    1: PapelFluxoAdmissao.Codigo.REQUISICAO,
    2: PapelFluxoAdmissao.Codigo.CONFERENCIA_DOCS,
    3: PapelFluxoAdmissao.Codigo.VALIDACAO_FINAL,
    4: PapelFluxoAdmissao.Codigo.CONTRATO,
}

# Textos curtos para a tela Papéis do fluxo.
PAPEL_META = {
    PapelFluxoAdmissao.Codigo.REQUISICAO: {
        'responsavel': 'Responsável pela admissão',
        'nota': 'O usuário logado que cria a requisição.',
        'automatico': True,
        'auto_msg': 'Definido automaticamente — não precisa configurar usuários.',
    },
    PapelFluxoAdmissao.Codigo.CONFERENCIA_DOCS: {
        'responsavel': 'Equipe RH',
        'nota': 'Preferencialmente quem abriu a requisição; qualquer usuário RH pode conferir.',
        'automatico': True,
        'auto_msg': 'Quem criou a admissão é o responsável nominal — qualquer RH pode atuar nesta etapa.',
    },
    PapelFluxoAdmissao.Codigo.VALIDACAO_FINAL: {
        'responsavel': 'Responsável pela validação final',
        'nota': 'Aprova o pacote antes do contrato.',
        'automatico': False,
    },
    PapelFluxoAdmissao.Codigo.CONTRATO: {
        'responsavel': 'Responsável pelo contrato',
        'nota': 'PDF, ZapSign e arquivamento.',
        'automatico': False,
    },
}


def meta_papel(codigo: str) -> dict:
    return PAPEL_META.get(codigo, {
        'responsavel': 'Responsável',
        'nota': '',
        'automatico': False,
        'auto_msg': '',
    })


def papel_eh_automatico(codigo: str) -> bool:
    return bool(meta_papel(codigo).get('automatico'))


def responsavel_admissao_colaborador(colaborador) -> str:
    """Nome do usuário que abriu a admissão (etapas 1 e 2)."""
    from recursos_humanos.services.admissao_actions import garantir_requisicao_criada_por

    if colaborador is None:
        return ''
    garantir_requisicao_criada_por(colaborador)
    criador = colaborador.requisicao_criada_por
    if criador:
        return criador.get_full_name() or criador.username
    return 'Responsável pela admissão'


def _usuario_eh_rh(user) -> bool:
    if not user or not getattr(user, 'is_authenticated', False):
        return False
    if getattr(user, 'is_superuser', False):
        return True
    from accounts.groups import GRUPOS

    return user.groups.filter(name=GRUPOS.RECURSOS_HUMANOS).exists()


def garantir_papeis_padrao() -> None:
    PapelFluxoAdmissao.garantir_papeis_padrao()


def listar_papeis_configurados():
    garantir_papeis_padrao()
    return list(
        PapelFluxoAdmissao.objects.prefetch_related('usuarios').order_by('ordem', 'etapa')
    )


def obter_papel(codigo: str) -> PapelFluxoAdmissao | None:
    garantir_papeis_padrao()
    return PapelFluxoAdmissao.objects.filter(codigo=codigo).prefetch_related('usuarios').first()


def _usuarios_ativos_do_papel(papel: PapelFluxoAdmissao):
    return list(
        papel.usuarios.filter(is_active=True).order_by(
            'first_name', 'last_name', 'username',
        )
    )


def papel_tem_responsaveis_configurados(codigo: str) -> bool:
    papel = obter_papel(codigo)
    if not papel:
        return False
    return papel.usuarios.filter(is_active=True).exists()


def usuarios_do_papel(codigo: str):
    """Usuários explicitamente configurados no papel (pode ser lista vazia)."""
    papel = obter_papel(codigo)
    if not papel:
        return []
    return _usuarios_ativos_do_papel(papel)


def usuario_pode_executar_papel(user, codigo: str) -> bool:
    """
    True se o usuário pode atuar no papel.
    Com responsáveis configurados: só eles (+ superuser).
    Sem responsáveis: qualquer usuário do grupo RH.
    """
    if not user or not getattr(user, 'is_authenticated', False):
        return False
    if getattr(user, 'is_superuser', False):
        return True
    papel = obter_papel(codigo)
    if not papel:
        return _usuario_eh_rh(user)
    configurados = papel.usuarios.filter(is_active=True)
    if configurados.exists():
        return configurados.filter(pk=user.pk).exists()
    return _usuario_eh_rh(user)


def usuario_pode_conferir_documentos(user, colaborador) -> bool:
    """Etapa 2: responsável nominal = quem criou a admissão; qualquer RH pode atuar."""
    return _usuario_eh_rh(user)


def usuarios_destinatarios_papel(codigo: str):
    """Responsáveis do papel; se vazio, todo o grupo RH."""
    from django.contrib.auth.models import User

    users = usuarios_do_papel(codigo)
    if users:
        return users
    from accounts.groups import GRUPOS

    return list(
        User.objects.filter(is_active=True, groups__name=GRUPOS.RECURSOS_HUMANOS)
        .distinct()
        .order_by('first_name', 'last_name', 'username')
    )


def nomes_responsaveis_papel(codigo: str) -> list[str]:
    users = usuarios_do_papel(codigo)
    if users:
        return [u.get_full_name() or u.username for u in users]
    return ['Equipe RH (padrão)']


def contexto_papel_etapa(codigo: str, user=None, colaborador=None) -> dict:
    papel = obter_papel(codigo)
    meta = meta_papel(codigo)
    automatico = meta.get('automatico', False)
    if automatico and colaborador is not None:
        responsaveis = [responsavel_admissao_colaborador(colaborador)]
    elif automatico:
        responsaveis = ['Quem criar a admissão']
    else:
        responsaveis = nomes_responsaveis_papel(codigo)
    return {
        'codigo': codigo,
        'titulo': papel.titulo if papel else codigo,
        'descricao': papel.descricao if papel else '',
        'etapa': papel.etapa if papel else None,
        'responsaveis': responsaveis,
        'responsaveis_texto': ', '.join(responsaveis),
        'tem_configuracao': False if automatico else papel_tem_responsaveis_configurados(codigo),
        'usuario_pode': usuario_pode_executar_papel(user, codigo) if user and not automatico else (
            usuario_pode_conferir_documentos(user, colaborador) if user and colaborador else bool(user)
        ),
        'responsavel': meta['responsavel'],
        'nota': meta['nota'],
        'automatico': automatico,
        'auto_msg': meta.get('auto_msg', ''),
    }


def contexto_papeis_fluxo(user=None, colaborador=None) -> dict:
    garantir_papeis_padrao()
    papeis = {}
    for papel in listar_papeis_configurados():
        ctx = contexto_papel_etapa(papel.codigo, user=user, colaborador=colaborador)
        if colaborador and papel.codigo == PapelFluxoAdmissao.Codigo.CONFERENCIA_DOCS:
            ctx['usuario_pode'] = usuario_pode_conferir_documentos(user, colaborador) if user else False
        if colaborador and papel.codigo == PapelFluxoAdmissao.Codigo.REQUISICAO:
            ctx['responsaveis'] = [responsavel_admissao_colaborador(colaborador)]
            ctx['responsaveis_texto'] = ctx['responsaveis'][0]
        papeis[papel.codigo] = ctx
    return papeis
