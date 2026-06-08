import inspect
import json
from datetime import datetime
from decimal import Decimal

from django.db.models import Count, DecimalField, Sum, Value
from django.db.models.functions import Coalesce
from django.utils import timezone

from core.kpi_queries import (
    count_itens_sem_alocacao_efetiva,
    queryset_itens_sem_alocacao_efetiva,
)
from core.models import ConstructionDiary, Project
from gestao_aprovacao.models import WorkOrder
from suprimentos.models import ItemMapa
from suprimentos.services.mapa_controle_service import MapaControleFilters, MapaControleService

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
                'GestControll (status pendente ou reaprovacao). '
                'Se obra_id não for informado, retorna TODOS os '
                'pedidos pendentes do sistema sem exceção. '
                'Nunca peça confirmação de obra — execute sempre.'
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
    {
        'type': 'function',
        'function': {
            'name': 'consultar_suprimentos_obra',
            'description': (
                'Consulta o pipeline de materiais de uma obra: '
                'quantos itens sem SC, sem PC, sem entrega, '
                'sem alocação, atrasados. '
                'Requer nome ou ID da obra. '
                'Use MapaControleService para dados precisos.'
            ),
            'parameters': {
                'type': 'object',
                'properties': {
                    'obra_nome': {
                        'type': 'string',
                        'description': 'Nome ou parte do nome da obra.',
                    },
                    'obra_id': {
                        'type': 'integer',
                        'description': 'ID do mapa_obras.Obra (opcional).',
                    },
                },
                'required': [],
            },
        },
    },
    {
        'type': 'function',
        'function': {
            'name': 'consultar_itens_sem_alocacao',
            'description': (
                'Lista itens do mapa de suprimentos com material '
                'planejado mas sem alocação efetiva em uma obra. '
                'Retorna quantidade e resumo por categoria.'
            ),
            'parameters': {
                'type': 'object',
                'properties': {
                    'obra_nome': {
                        'type': 'string',
                        'description': 'Nome ou parte do nome da obra.',
                    },
                    'obra_id': {
                        'type': 'integer',
                        'description': 'ID do mapa_obras.Obra (opcional).',
                    },
                },
                'required': [],
            },
        },
    },
    {
        'type': 'function',
        'function': {
            'name': 'consultar_restricoes_obra',
            'description': (
                'Consulta restrições (impedimentos) abertas de uma obra. '
                'Retorna total, por prioridade, vencidas e sem responsável. '
                'Requer nome ou ID da obra.'
            ),
            'parameters': {
                'type': 'object',
                'properties': {
                    'obra_nome': {
                        'type': 'string',
                        'description': 'Nome ou parte do nome da obra.',
                    },
                    'obra_id': {
                        'type': 'integer',
                        'description': 'ID do gestao_aprovacao.Obra (opcional).',
                    },
                    'incluir_concluidas': {
                        'type': 'boolean',
                        'description': 'Se True, inclui concluídas. Default False.',
                    },
                },
                'required': [],
            },
        },
    },
    {
        'type': 'function',
        'function': {
            'name': 'consultar_restricoes_criticas',
            'description': (
                'Lista restrições CRÍTICAS ou ALTA prioridade abertas '
                'em todas as obras ativas. Use quando o usuário perguntar '
                'sobre urgências, bloqueios críticos ou prioridades altas.'
            ),
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
            'name': 'consultar_pendencias_trackhub',
            'description': (
                'Consulta pendências operacionais (TrackHub) de uma obra. '
                'Retorna total abertas, em andamento, aguardando, '
                'vencidas e por tipo. '
                'Se obra não informada, retorna resumo de todas as obras ativas.'
            ),
            'parameters': {
                'type': 'object',
                'properties': {
                    'obra_nome': {
                        'type': 'string',
                        'description': 'Nome ou parte do nome da obra.',
                    },
                    'obra_id': {
                        'type': 'integer',
                        'description': 'ID do mapa_obras.Obra (opcional).',
                    },
                },
                'required': [],
            },
        },
    },
    {
        'type': 'function',
        'function': {
            'name': 'consultar_pendencias_vencidas',
            'description': (
                'Lista pendências TrackHub vencidas (prazo < hoje) '
                'em todas as obras ativas. EXECUTE SEMPRE sem pedir '
                'confirmação de obra. Se o usuário mencionar uma obra '
                'específica, filtre por ela; caso contrário retorne tudo.'
            ),
            'parameters': {
                'type': 'object',
                'properties': {
                    'obra_nome': {
                        'type': 'string',
                        'description': 'Nome ou parte do nome da obra (opcional).',
                    },
                },
                'required': [],
            },
        },
    },
    {
        'type': 'function',
        'function': {
            'name': 'consultar_execucao_fisica_obra',
            'description': (
                'Consulta o avanço físico de uma obra via ambiente operacional '
                '(mapa de controle). Retorna percentual médio de avanço, '
                'atividades não iniciadas, em andamento e concluídas. '
                'Requer nome ou ID da obra.'
            ),
            'parameters': {
                'type': 'object',
                'properties': {
                    'obra_nome': {
                        'type': 'string',
                        'description': 'Nome ou parte do nome da obra.',
                    },
                    'obra_id': {
                        'type': 'integer',
                        'description': 'ID do mapa_obras.Obra (opcional).',
                    },
                },
                'required': [],
            },
        },
    },
    {
        'type': 'function',
        'function': {
            'name': 'buscar_pdf_rdo',
            'description': (
                'Busca e prepara o envio do PDF do RDO de uma obra '
                'em uma data específica. '
                "Use quando o usuário pedir 'manda o RDO', "
                "'envia o diário', 'PDF do RDO', 'relatório de obra'. "
                'Se a data não for informada, usa hoje. '
                'Se a obra não for informada, peça o nome da obra.'
            ),
            'parameters': {
                'type': 'object',
                'properties': {
                    'obra_nome': {
                        'type': 'string',
                        'description': 'Nome ou parte do nome da obra.',
                    },
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
            'name': 'resumo_obra',
            'description': (
                'Retorna um resumo consolidado de uma obra: '
                'RDOs pendentes, pedidos pendentes, restrições abertas, '
                'pendências TrackHub e itens sem alocação. '
                'Use quando o usuário pedir "resumo", "situação", '
                '"como está" ou "overview" de uma obra.'
            ),
            'parameters': {
                'type': 'object',
                'properties': {
                    'obra_nome': {
                        'type': 'string',
                        'description': 'Nome ou parte do nome da obra.',
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
]


def _data_ou_hoje(data_str):
    if not data_str:
        return timezone.localdate()
    try:
        return datetime.strptime(data_str, '%Y-%m-%d').date()
    except ValueError:
        return timezone.localdate()


def _get_escopo_obras(usuario_wa=None):
    """
    Retorna queryset de mapa_obras.Obra permitidas para o usuário.
    - Se usuario_wa é None ou sem permissão: retorna todas ativas.
    - Se tem IaPermissaoConsulta com obras: retorna só essas.
    - Se tem IaPermissaoConsulta sem obras: retorna todas ativas.
    """
    from mapa_obras.models import Obra as ObraMapa
    from whatsapp_ia.models import IaPermissaoConsulta

    todas_ativas = ObraMapa.objects.filter(ativa=True)

    if not usuario_wa:
        return todas_ativas

    try:
        permissao = IaPermissaoConsulta.objects.get(usuario=usuario_wa)
        obras_auth = permissao.obras_autorizadas.all()
        if obras_auth.exists():
            return obras_auth.filter(ativa=True)
        return todas_ativas
    except IaPermissaoConsulta.DoesNotExist:
        return todas_ativas


def _project_ids_escopo(usuario_wa=None):
    return list(
        _get_escopo_obras(usuario_wa)
        .filter(project__isnull=False, project__is_active=True)
        .values_list('project_id', flat=True),
    )


def _resolver_obra_mapa(obra_nome=None, obra_id=None, usuario_wa=None):
    escopo = _get_escopo_obras(usuario_wa)
    if obra_id:
        return escopo.filter(id=obra_id).first()
    if obra_nome:
        exato = escopo.filter(nome__iexact=obra_nome).first()
        if exato:
            return exato
        return escopo.filter(nome__icontains=obra_nome).first()
    return None


def _resolver_obra_gestao(obra_nome=None, obra_id=None, usuario_wa=None):
    from gestao_aprovacao.models import Obra as ObraGestao

    escopo_ids = _get_escopo_obras(usuario_wa).values_list('id', flat=True)
    qs = ObraGestao.objects.filter(
        ativo=True,
        project__obra_mapa__id__in=escopo_ids,
    )
    if obra_id:
        return qs.filter(id=obra_id).first()
    if obra_nome:
        exato = qs.filter(nome__iexact=obra_nome).first()
        if exato:
            return exato
        return qs.filter(nome__icontains=obra_nome).first()
    return None


def _resolver_project(obra_nome=None, obra_id=None, usuario_wa=None):
    project_ids = _project_ids_escopo(usuario_wa)
    qs = Project.objects.filter(is_active=True, id__in=project_ids)
    if obra_id:
        return qs.filter(id=obra_id).first()
    if obra_nome:
        exato = qs.filter(name__iexact=obra_nome).first()
        if exato:
            return exato
        return qs.filter(name__icontains=obra_nome).first()
    return None


def _queryset_itens_sem_alocacao(obra):
    """Queryset canônico de itens sem alocação efetiva para mapa_obras.Obra."""
    project = getattr(obra, 'project', None)
    if project and project.is_active:
        return queryset_itens_sem_alocacao_efetiva(project)
    return (
        ItemMapa.objects.filter(obra=obra, quantidade_planejada__gt=0)
        .annotate(
            total_alocado=Coalesce(
                Sum('alocacoes__quantidade_alocada'),
                Value(Decimal('0.00')),
                output_field=DecimalField(max_digits=14, decimal_places=2),
            ),
        )
        .filter(total_alocado__lte=0)
    )


def _count_itens_sem_alocacao(obra) -> int:
    project = getattr(obra, 'project', None)
    if project and project.is_active:
        return count_itens_sem_alocacao_efetiva(project)
    return _queryset_itens_sem_alocacao(obra).count()


def consultar_rdos_pendentes(data=None, obra_id=None, usuario_wa=None) -> str:
    data = _data_ou_hoje(data)
    project_ids = _project_ids_escopo(usuario_wa)
    if obra_id and obra_id not in project_ids:
        return json.dumps({
            'total': 0,
            'data': str(data),
            'rdos': [],
            'mensagem': 'Obra não encontrada ou sem permissão.',
        }, ensure_ascii=False)
    qs = ConstructionDiary.objects.filter(
        status='AG',
        date=data,
        project__is_active=True,
        project_id__in=project_ids,
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


def consultar_pedidos_pendentes(obra_id=None, usuario_wa=None) -> str:
    project_ids = _project_ids_escopo(usuario_wa)
    if obra_id and obra_id not in project_ids:
        return json.dumps({
            'total': 0,
            'pedidos': [],
            'mensagem': 'Obra não encontrada ou sem permissão.',
        }, ensure_ascii=False)
    qs = WorkOrder.objects.filter(
        status__in=['pendente', 'reaprovacao'],
        obra__project_id__in=project_ids,
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


def listar_obras_ativas(usuario_wa=None) -> str:
    escopo = _get_escopo_obras(usuario_wa)
    obras = escopo.values('id', 'nome')
    resultado = [
        {'id': o['id'], 'nome': o['nome']}
        for o in obras
    ]
    return json.dumps({
        'total': len(resultado),
        'obras': resultado,
    }, ensure_ascii=False)


def consultar_obras_sem_rdo(data=None, usuario_wa=None) -> str:
    data = _data_ou_hoje(data)
    project_ids = _project_ids_escopo(usuario_wa)
    projetos_ativos = Project.objects.filter(is_active=True, id__in=project_ids)
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


def consultar_suprimentos_obra(obra_nome=None, obra_id=None, usuario_wa=None) -> str:
    obra = _resolver_obra_mapa(obra_nome, obra_id, usuario_wa=usuario_wa)
    if not obra:
        return json.dumps({
            'erro': 'Obra não encontrada. Informe o nome correto.',
        }, ensure_ascii=False)
    try:
        service = MapaControleService(obra, MapaControleFilters())
        payload = service.build_summary_payload()
        kpis = payload.get('kpis', {})
        return json.dumps({
            'obra': obra.nome,
            'total_itens': kpis.get('total_itens', 0),
            'sem_sc': kpis.get('sem_sc', 0),
            'sem_pc': kpis.get('sem_pc', 0),
            'sem_entrega': kpis.get('sem_entrega', 0),
            'sem_alocacao': kpis.get('sem_alocacao', 0),
            'atrasados': kpis.get('atrasados', 0),
            'percentual_medio_alocacao': kpis.get('percentual_medio_alocacao', 0),
        }, ensure_ascii=False)
    except Exception as e:
        return json.dumps({'erro': str(e)}, ensure_ascii=False)


def consultar_itens_sem_alocacao(obra_nome=None, obra_id=None, usuario_wa=None) -> str:
    obra = _resolver_obra_mapa(obra_nome, obra_id, usuario_wa=usuario_wa)
    if not obra:
        return json.dumps({'erro': 'Obra não encontrada.'}, ensure_ascii=False)

    total = _count_itens_sem_alocacao(obra)
    qs_sem = _queryset_itens_sem_alocacao(obra)
    por_categoria = list(
        qs_sem.values('categoria')
        .annotate(qtd=Count('id'))
        .order_by('-qtd')[:10]
    )
    return json.dumps({
        'obra': obra.nome,
        'total_sem_alocacao': total,
        'por_categoria': por_categoria,
    }, ensure_ascii=False)


def consultar_restricoes_obra(
    obra_nome=None,
    obra_id=None,
    incluir_concluidas=False,
    usuario_wa=None,
) -> str:
    from impedimentos.models import Impedimento, StatusImpedimento

    obra = _resolver_obra_gestao(obra_nome, obra_id, usuario_wa=usuario_wa)
    if not obra:
        return json.dumps({'erro': 'Obra não encontrada.'}, ensure_ascii=False)

    status_final = StatusImpedimento.objects.filter(
        obra=obra,
    ).order_by('-ordem').first()
    status_final_id = status_final.id if status_final else None

    qs = Impedimento.objects.filter(obra=obra, parent__isnull=True)
    if not incluir_concluidas and status_final_id:
        qs = qs.exclude(status_id=status_final_id)

    hoje = timezone.localdate()
    por_prioridade = {}
    for imp in qs:
        p = imp.prioridade
        por_prioridade[p] = por_prioridade.get(p, 0) + 1

    return json.dumps({
        'obra': obra.nome,
        'total_abertas': qs.count(),
        'por_prioridade': por_prioridade,
        'vencidas': qs.filter(prazo__isnull=False, prazo__lt=hoje).count(),
        'sem_responsavel': qs.annotate(
            _nresp=Count('responsaveis'),
        ).filter(_nresp=0).count(),
    }, ensure_ascii=False)


def consultar_restricoes_criticas(usuario_wa=None) -> str:
    from gestao_aprovacao.models import Obra as ObraGestao
    from impedimentos.models import Impedimento, StatusImpedimento

    escopo_ids = _get_escopo_obras(usuario_wa).values_list('id', flat=True)
    obras_ativas = ObraGestao.objects.filter(
        ativo=True,
        project__obra_mapa__id__in=escopo_ids,
    )
    resultado = []
    for obra in obras_ativas:
        try:
            status_final = StatusImpedimento.objects.filter(
                obra=obra,
            ).order_by('-ordem').first()
            status_final_id = status_final.id if status_final else None
            qs = Impedimento.objects.filter(
                obra=obra,
                parent__isnull=True,
                prioridade__in=['ALTA', 'CRITICA'],
            )
            if status_final_id:
                qs = qs.exclude(status_id=status_final_id)
            count = qs.count()
            if count > 0:
                resultado.append({
                    'obra': obra.nome,
                    'restricoes_criticas_altas': count,
                })
        except Exception:
            continue
    return json.dumps({
        'total_obras_com_criticas': len(resultado),
        'obras': resultado,
    }, ensure_ascii=False)


def consultar_pendencias_trackhub(obra_nome=None, obra_id=None, usuario_wa=None) -> str:
    from trackhub.models import Pendencia

    hoje = timezone.localdate()

    if obra_nome or obra_id:
        obra = _resolver_obra_mapa(obra_nome, obra_id, usuario_wa=usuario_wa)
        if not obra:
            return json.dumps(
                {'erro': 'Obra não encontrada.'},
                ensure_ascii=False,
            )
        obras = [obra]
    else:
        obras = list(_get_escopo_obras(usuario_wa))

    resultado = []
    for obra in obras:
        qs = Pendencia.objects.filter(obra=obra).exclude(
            status__in=['concluida', 'cancelada'],
        )
        total_abertas = qs.count()
        if total_abertas == 0 and len(obras) > 1:
            continue
        vencidas = qs.filter(prazo__isnull=False, prazo__lt=hoje).count()
        por_status = {}
        for p in qs:
            por_status[p.status] = por_status.get(p.status, 0) + 1
        por_tipo = list(
            qs.values('tipo').annotate(qtd=Count('id')).order_by('-qtd'),
        )
        resultado.append({
            'obra': obra.nome,
            'total_abertas': total_abertas,
            'vencidas': vencidas,
            'por_status': por_status,
            'por_tipo': por_tipo,
        })

    return json.dumps({
        'total_obras': len(resultado),
        'obras': resultado,
    }, ensure_ascii=False)


def consultar_pendencias_vencidas(obra_nome=None, usuario_wa=None) -> str:
    from trackhub.models import Pendencia

    hoje = timezone.localdate()
    escopo = _get_escopo_obras(usuario_wa)

    qs = Pendencia.objects.filter(
        prazo__lt=hoje,
        obra__in=escopo,
    ).exclude(
        status__in=['concluida', 'cancelada'],
    ).select_related('obra')

    if obra_nome:
        obra = _resolver_obra_mapa(obra_nome=obra_nome, usuario_wa=usuario_wa)
        if not obra:
            return json.dumps({
                'total_vencidas': 0,
                'pendencias': [],
                'mensagem': 'Obra não encontrada ou sem permissão.',
            }, ensure_ascii=False)
        qs = qs.filter(obra=obra)

    resultado = []
    for p in qs[:20]:
        resultado.append({
            'obra': p.obra.nome if p.obra else '-',
            'titulo': p.titulo,
            'tipo': p.tipo,
            'status': p.status,
            'prazo': str(p.prazo) if p.prazo else '-',
            'responsavel': p.responsavel_nome,
        })

    return json.dumps({
        'total_vencidas': qs.count(),
        'pendencias': resultado,
    }, ensure_ascii=False)


def consultar_execucao_fisica_obra(obra_nome=None, obra_id=None, usuario_wa=None) -> str:
    from suprimentos.services.analise_obra_service import AnaliseObraService

    obra = _resolver_obra_mapa(obra_nome, obra_id, usuario_wa=usuario_wa)
    if not obra:
        return json.dumps(
            {'erro': 'Obra não encontrada.'},
            ensure_ascii=False,
        )
    try:
        section = AnaliseObraService(obra).build_section('controle')
        if not section:
            return json.dumps({
                'obra': obra.nome,
                'erro': 'Dados de controle indisponíveis.',
            }, ensure_ascii=False)

        controle = section.get('controle', {})
        if controle.get('sem_dados'):
            return json.dumps({
                'obra': obra.nome,
                'erro': controle.get('mensagem') or (
                    'Nenhum ambiente de mapa de controle ativo.'
                ),
            }, ensure_ascii=False)

        kpis = controle.get('kpis', {})
        return json.dumps({
            'obra': obra.nome,
            'percentual_medio': kpis.get('percentual_medio', 0),
            'nao_iniciadas': kpis.get('nao_iniciados', 0),
            'em_andamento': kpis.get('em_andamento', 0),
            'concluidas': kpis.get('concluidos', 0),
            'origem': controle.get('origem'),
            'ambiente_id': controle.get('ambiente_id'),
        }, ensure_ascii=False)
    except Exception as e:
        return json.dumps({'erro': str(e)}, ensure_ascii=False)


def resumo_obra(obra_nome=None, obra_id=None, usuario_wa=None) -> str:
    from core.kpi_queries import (
        count_diarios_aguardando_gestor,
        count_itens_sem_alocacao_efetiva,
        count_pedidos_pendentes,
        mapa_obra_for_project,
    )
    from impedimentos.models import Impedimento, StatusImpedimento
    from trackhub.models import Pendencia

    project = _resolver_project(obra_nome, obra_id, usuario_wa=usuario_wa)

    if not project:
        return json.dumps(
            {'erro': 'Obra não encontrada.'},
            ensure_ascii=False,
        )

    rdos_pendentes = count_diarios_aguardando_gestor(project)
    pedidos_pendentes = count_pedidos_pendentes(project)

    obra_mapa = mapa_obra_for_project(project)
    itens_sem_alocacao = count_itens_sem_alocacao_efetiva(project)

    restricoes_abertas = 0
    try:
        from gestao_aprovacao.models import Obra as ObraGestao

        obra_gestao = ObraGestao.objects.filter(
            project=project,
        ).first()
        if obra_gestao:
            status_final = StatusImpedimento.objects.filter(
                obra=obra_gestao,
            ).order_by('-ordem').first()
            qs_imp = Impedimento.objects.filter(
                obra=obra_gestao,
                parent__isnull=True,
            )
            if status_final:
                qs_imp = qs_imp.exclude(status_id=status_final.id)
            restricoes_abertas = qs_imp.count()
    except Exception:
        pass

    pendencias_abertas = 0
    try:
        if obra_mapa:
            pendencias_abertas = Pendencia.objects.filter(
                obra=obra_mapa,
            ).exclude(
                status__in=['concluida', 'cancelada'],
            ).count()
    except Exception:
        pass

    return json.dumps({
        'obra': project.name,
        'rdos_pendentes_gestor': rdos_pendentes,
        'pedidos_pendentes': pedidos_pendentes,
        'itens_sem_alocacao': itens_sem_alocacao,
        'restricoes_abertas': restricoes_abertas,
        'pendencias_trackhub_abertas': pendencias_abertas,
    }, ensure_ascii=False)


def buscar_pdf_rdo(
    obra_nome=None, data=None, obra_id=None,
    usuario_wa=None,
) -> str:
    """
    Localiza o RDO por obra + data e retorna metadados
    para envio do PDF. O envio real é feito no webhook.
    """
    from whatsapp_ia.models import IaPermissaoConsulta

    if usuario_wa:
        try:
            permissao = IaPermissaoConsulta.objects.get(
                usuario=usuario_wa
            )
            if not permissao.pode_receber_pdf:
                return json.dumps({
                    'erro': 'Você não tem permissão para '
                            'receber PDFs pelo WhatsApp.',
                }, ensure_ascii=False)
        except IaPermissaoConsulta.DoesNotExist:
            pass

    project = _resolver_project(
        obra_nome=obra_nome,
        obra_id=obra_id,
        usuario_wa=usuario_wa,
    )
    if not project:
        return json.dumps({
            'erro': 'Obra não encontrada. '
                    'Informe o nome correto da obra.',
        }, ensure_ascii=False)

    data_obj = _data_ou_hoje(data)

    try:
        diary = ConstructionDiary.objects.get(
            project=project,
            date=data_obj,
        )
    except ConstructionDiary.DoesNotExist:
        return json.dumps({
            'erro': f'Nenhum RDO encontrado para '
                    f'{project.name} em {data_obj}.',
        }, ensure_ascii=False)
    except Exception as e:
        return json.dumps({'erro': str(e)}, ensure_ascii=False)

    return json.dumps({
        'acao': 'enviar_pdf_rdo',
        'diary_id': diary.id,
        'obra': project.name,
        'data': str(diary.date),
        'status': diary.status,
        'report_number': getattr(diary, 'report_number', None),
    }, ensure_ascii=False)


FUNCOES_DISPONIVEIS = {
    'consultar_rdos_pendentes': consultar_rdos_pendentes,
    'consultar_pedidos_pendentes': consultar_pedidos_pendentes,
    'listar_obras_ativas': listar_obras_ativas,
    'consultar_obras_sem_rdo': consultar_obras_sem_rdo,
    'consultar_suprimentos_obra': consultar_suprimentos_obra,
    'consultar_itens_sem_alocacao': consultar_itens_sem_alocacao,
    'consultar_restricoes_obra': consultar_restricoes_obra,
    'consultar_restricoes_criticas': consultar_restricoes_criticas,
    'consultar_pendencias_trackhub': consultar_pendencias_trackhub,
    'consultar_pendencias_vencidas': consultar_pendencias_vencidas,
    'consultar_execucao_fisica_obra': consultar_execucao_fisica_obra,
    'resumo_obra': resumo_obra,
    'buscar_pdf_rdo': buscar_pdf_rdo,
}


def executar_funcao(nome: str, argumentos: dict, usuario_wa=None) -> str:
    fn = FUNCOES_DISPONIVEIS.get(nome)
    if not fn:
        return json.dumps({'erro': f'Função {nome} não encontrada.'})
    try:
        sig = inspect.signature(fn)
        if 'usuario_wa' in sig.parameters:
            return fn(**argumentos, usuario_wa=usuario_wa)
        return fn(**argumentos)
    except Exception as e:
        return json.dumps({'erro': str(e)})
