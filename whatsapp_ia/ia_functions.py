import json
from datetime import datetime

from django.utils import timezone

from core.models import ConstructionDiary, Project
from gestao_aprovacao.models import WorkOrder

TOOLS = [
    {
        'type': 'function',
        'function': {
            'name': 'consultar_rdos_pendentes',
            'description': (
                'Consulta RDOs pendentes de aprovação do gestor '
                '(status AG) em uma data. Se obra_id não informado, '
                'retorna todos os projetos ativos com RDO pendente.'
            ),
            'parameters': {
                'type': 'object',
                'properties': {
                    'data': {
                        'type': 'string',
                        'description': (
                            'Data no formato YYYY-MM-DD. '
                            'Se não informada, usa hoje.'
                        ),
                    },
                    'obra_id': {
                        'type': 'integer',
                        'description': 'ID do core.Project (opcional).',
                    },
                },
                'required': [],
            },
        },
    },
    {
        'type': 'function',
        'function': {
            'name': 'consultar_pedidos_pendentes',
            'description': (
                'Consulta pedidos de aprovação pendentes no '
                'GestControll (status pendente ou reaprovacao).'
            ),
            'parameters': {
                'type': 'object',
                'properties': {
                    'obra_id': {
                        'type': 'integer',
                        'description': 'ID do core.Project (opcional).',
                    },
                },
                'required': [],
            },
        },
    },
    {
        'type': 'function',
        'function': {
            'name': 'listar_obras_ativas',
            'description': 'Lista obras ativas no sistema (Project.is_active=True).',
            'parameters': {
                'type': 'object',
                'properties': {},
                'required': [],
            },
        },
    },
    {
        'type': 'function',
        'function': {
            'name': 'consultar_obras_sem_rdo',
            'description': (
                'Lista obras ativas que não têm RDO aprovado '
                'em uma data específica.'
            ),
            'parameters': {
                'type': 'object',
                'properties': {
                    'data': {
                        'type': 'string',
                        'description': (
                            'Data no formato YYYY-MM-DD. '
                            'Se não informada, usa hoje.'
                        ),
                    },
                },
                'required': [],
            },
        },
    },
]


def _data_ou_hoje(data_str):
    if not data_str:
        return timezone.localdate()
    try:
        return datetime.strptime(data_str, '%Y-%m-%d').date()
    except ValueError:
        return timezone.localdate()


def consultar_rdos_pendentes(data=None, obra_id=None) -> str:
    data = _data_ou_hoje(data)
    qs = ConstructionDiary.objects.filter(
        status='AG',
        date=data,
        project__is_active=True,
    ).select_related('project')
    if obra_id:
        qs = qs.filter(project_id=obra_id)
    resultados = [
        {
            'obra': d.project.name,
            'project_id': d.project.id,
            'data': str(d.date),
        }
        for d in qs
    ]
    if not resultados:
        return json.dumps({
            'total': 0,
            'data': str(data),
            'rdos': [],
            'mensagem': f'Nenhum RDO pendente em {data}.',
        }, ensure_ascii=False)
    return json.dumps({
        'total': len(resultados),
        'data': str(data),
        'rdos': resultados,
    }, ensure_ascii=False)


def consultar_pedidos_pendentes(obra_id=None) -> str:
    qs = WorkOrder.objects.filter(
        status__in=['pendente', 'reaprovacao'],
    ).select_related('obra')
    if obra_id:
        qs = qs.filter(obra__project_id=obra_id)
    resultados = [
        {
            'codigo': w.codigo,
            'tipo': w.tipo_solicitacao,
            'credor': w.nome_credor,
            'status': w.status,
            'obra': w.obra.nome if w.obra else '-',
            'data_envio': str(w.data_envio) if w.data_envio else '-',
        }
        for w in qs[:20]
    ]
    return json.dumps({
        'total': qs.count(),
        'pedidos': resultados,
    }, ensure_ascii=False)


def listar_obras_ativas() -> str:
    obras = Project.objects.filter(is_active=True).values('id', 'name')
    lista = list(obras)
    return json.dumps({
        'total': len(lista),
        'obras': lista,
    }, ensure_ascii=False)


def consultar_obras_sem_rdo(data=None) -> str:
    data = _data_ou_hoje(data)
    projetos_ativos = Project.objects.filter(is_active=True)
    projetos_com_rdo_aprovado = ConstructionDiary.objects.filter(
        date=data,
        status='AP',
    ).values_list('project_id', flat=True)
    sem_rdo = list(
        projetos_ativos.exclude(
            id__in=projetos_com_rdo_aprovado,
        ).values('id', 'name')
    )
    return json.dumps({
        'total': len(sem_rdo),
        'data': str(data),
        'obras': sem_rdo,
    }, ensure_ascii=False)


FUNCOES_DISPONIVEIS = {
    'consultar_rdos_pendentes': consultar_rdos_pendentes,
    'consultar_pedidos_pendentes': consultar_pedidos_pendentes,
    'listar_obras_ativas': listar_obras_ativas,
    'consultar_obras_sem_rdo': consultar_obras_sem_rdo,
}


def executar_funcao(nome: str, argumentos: dict) -> str:
    fn = FUNCOES_DISPONIVEIS.get(nome)
    if not fn:
        return json.dumps({'erro': f'Função {nome} não encontrada.'})
    try:
        return fn(**argumentos)
    except Exception as e:
        return json.dumps({'erro': str(e)})
