"""
Funções de consulta da IA WhatsApp — retornos JSON para tool calls.

Convenção de strings e metadados
--------------------------------
* Campos para o USUÁRIO FINAL (`mensagem`, `alerta`, `descricao`, `aviso`):
  linguagem natural exibível no WhatsApp.
* Metadados INTERNOS (`nivel`, `tipo`, flags, classificação, parâmetros):
  ficam em `_meta` no payload. A IA usa `_meta` para formatação e
  priorização, mas NUNCA deve citá-los na resposta (ver prompts.py).
"""
import inspect
import json
from datetime import datetime, timedelta
from decimal import Decimal

from django.db.models import Count, DecimalField, Q, Sum, Value
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


def _meta_ia(**kwargs):
    """Metadados internos — não devem aparecer na resposta ao usuário."""
    return {k: v for k, v in kwargs.items() if v is not None}


def _lacunas_exibicao(lacunas):
    return [
        {
            'de': item['apos_data'],
            'ate': item['antes_data'],
            'dias': item['dias_sem_rdo'],
        }
        for item in lacunas
    ]


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
                'Retorna dias_em_aberto, frente e agregação por obra '
                'quando obra não for informada. '
                'Aceita obra_nome ou obra_id — nunca peça ID se tiver nome.'
            ),
            'parameters': {
                'type': 'object',
                'properties': {
                    'obra_nome': {
                        'type': 'string',
                        'description': 'Nome ou parte do nome da obra (opcional).',
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
                'Lista obras ativas sem RDO aprovado em uma data '
                'específica (sem_rdo_hoje) e obras que nunca '
                'registraram RDO no histórico (nunca_teve_rdo). '
                'Diferencie os dois conceitos na resposta.'
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
            'name': 'consultar_frequencia_rdos',
            'description': (
                'Analisa frequência de RDOs por obra e por frente: '
                'obras/frentes que nunca tiveram RDO, último RDO há X dias, '
                'lacunas no histórico (buracos entre registros) e total no período. '
                'Use SEMPRE em análises gerais, panoramas e resumos operacionais.'
            ),
            'parameters': {
                'type': 'object',
                'properties': {
                    'obra_nome': {
                        'type': 'string',
                        'description': 'Nome ou parte do nome da obra (opcional).',
                    },
                    'obra_id': {
                        'type': 'integer',
                        'description': 'ID do core.Project (opcional).',
                    },
                    'dias_sem_rdo_alerta': {
                        'type': 'integer',
                        'description': 'Alerta se último RDO há mais de N dias. Default 7.',
                    },
                    'dias_analise': {
                        'type': 'integer',
                        'description': 'Janela de análise em dias. Default 90.',
                    },
                    'lacuna_minima_dias': {
                        'type': 'integer',
                        'description': (
                            'Buracos no histórico com pelo menos N dias '
                            'sem RDO. Default 7.'
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
            'name': 'consultar_situacao_rdo_obra',
            'description': (
                'Situação completa de RDO de uma obra: total no período, '
                'aprovados, pendentes de aprovação, rascunhos, dias com falta, '
                'alerta se último RDO >7 dias e RDOs AG há muitos dias (crítico). '
                'Use para perguntas sobre RDO de obra específica.'
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
                    'dias_analise': {
                        'type': 'integer',
                        'description': 'Janela de análise em dias. Default 90.',
                    },
                },
                'required': [],
            },
        },
    },
    {
        'type': 'function',
        'function': {
            'name': 'consultar_situacao_geral_obras',
            'description': (
                'Panorama operacional consolidado de TODAS as obras: RDOs, '
                'pedidos (GestControll), restrições, suprimentos, '
                'mapa de controle, mapa geográfico e TrackHub (inclui Sede). '
                'Use SEMPRE quando o usuário pedir situação geral das obras.'
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
            'name': 'consultar_situacao_pedidos_obras',
            'description': (
                'Panorama de pedidos por obra e frente: pendentes total, '
                'atrasados na aprovação, com prazo vencido e lista completa '
                'de pedidos atrasados (por dias em aberto) quando obra não '
                'for especificada. Use em análises gerais de aprovação.'
            ),
            'parameters': {
                'type': 'object',
                'properties': {
                    'obra_nome': {
                        'type': 'string',
                        'description': 'Nome ou parte do nome da obra (opcional).',
                    },
                    'obra_id': {
                        'type': 'integer',
                        'description': 'ID do core.Project (opcional).',
                    },
                    'dias_aprovacao_alerta': {
                        'type': 'integer',
                        'description': (
                            'Pedido considerado atrasado após N dias. Default 7.'
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
            'name': 'listar_frentes_obra',
            'description': (
                'Lista frentes/subobras ativas de uma obra com responsável. '
                'Use antes de resumos por frente ou quando o usuário '
                'perguntar sobre frentes, torres, blocos ou setores da obra.'
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
    {
        'type': 'function',
        'function': {
            'name': 'resumo_frente_obra',
            'description': (
                'Resumo operacional de uma frente específica: RDOs (último, '
                'lacunas), pedidos pendentes/atrasados e restrições abertas. '
                'Requer obra e frente (nome ou ID).'
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
                    'frente_nome': {
                        'type': 'string',
                        'description': 'Nome ou parte do nome da frente.',
                    },
                    'frente_id': {
                        'type': 'integer',
                        'description': 'ID da frente (opcional).',
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
            'name': 'consultar_panorama_suprimentos',
            'description': (
                'Panorama consolidado de suprimentos em todas as obras do '
                'escopo: total de itens, sem alocação e atrasados no pipeline. '
                'Ordenado por obras com mais itens. Use em análises gerais.'
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
            'name': 'consultar_panorama_mapa_controle',
            'description': (
                'Panorama do mapa de controle em todas as obras: se tem mapa, '
                'percentual geral de conclusão e quantidade de unidades. '
                'Ordenado por desenvolvimento. Use em análises gerais.'
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
                'Consulta pendências TrackHub por obra. Inclui Sede. '
                'Retorna totais globais, abertas, vencidas, responsáveis '
                'das pendências atrasadas e dias de atraso. '
                'Lista TODAS as obras, inclusive com zero pendências.'
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
                'pendências TrackHub, itens sem alocação e mini-resumo '
                'por frente quando a obra tiver frentes ativas. '
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
    {
        'type': 'function',
        'function': {
            'name': 'consultar_usuarios',
            'description': (
                'Consulta usuários do sistema. Com usuario_nome, retorna '
                'perfil cruzado: obras vinculadas (membro/permissão Gest), '
                'restrições abertas, pedidos aguardando aprovação DESTE usuário, '
                'pendências TrackHub atrasadas (separado: responsável da pendência '
                'vs responsável de etapa) e tempo médio de aprovação.'
            ),
            'parameters': {
                'type': 'object',
                'properties': {
                    'usuario_nome': {
                        'type': 'string',
                        'description': 'Nome ou username do usuário (opcional).',
                    },
                    'apenas_ativos': {
                        'type': 'boolean',
                        'description': (
                            'Se True, retorna só ativos. '
                            'Default False (todos).'
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
            'name': 'consultar_dados_obra',
            'description': (
                'Retorna dados completos de uma obra específica: '
                'locais do mapa, aprovadores de RDO, emails do diário, '
                'mão de obra, equipamentos, totais de atividades, '
                'membros e configurações. '
                'Use quando perguntar sobre detalhes de uma obra específica.'
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
    {
        'type': 'function',
        'function': {
            'name': 'consultar_modulos_sistema',
            'description': (
                'Retorna informações gerais de todos os módulos do sistema: '
                'total de itens em cada módulo (obras, pedidos, RDOs, '
                'restrições, pendências TrackHub, insumos, usuários). '
                'Use quando perguntar sobre o sistema em geral ou '
                'visão geral dos módulos.'
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
            'name': 'consultar_rdos_por_periodo',
            'description': (
                'Consulta RDOs de uma obra em um período. '
                'Retorna lista com data, status, número do relatório. '
                "Use quando perguntar 'RDOs de maio', 'diários da semana', "
                "'relatórios do mês', 'RDOs entre datas'."
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
                    'data_inicio': {
                        'type': 'string',
                        'description': 'Data inicial YYYY-MM-DD.',
                    },
                    'data_fim': {
                        'type': 'string',
                        'description': (
                            'Data final YYYY-MM-DD. '
                            'Se não informada, usa hoje.'
                        ),
                    },
                    'status': {
                        'type': 'string',
                        'description': (
                            'Filtrar por status: PR, SP, AG, RG, AP (opcional).'
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
            'name': 'consultar_detalhes_rdo',
            'description': (
                'Retorna detalhes completos de um RDO específico: '
                'clima, equipe, equipamentos, atividades, ocorrências, '
                'status, aprovadores e quem preencheu. '
                "Use quando perguntar sobre 'detalhes do RDO', "
                "'como foi o dia na obra X', 'o que teve no RDO de ontem'."
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
                    'data': {
                        'type': 'string',
                        'description': (
                            'Data YYYY-MM-DD. Se não informada, usa hoje.'
                        ),
                    },
                    'diary_id': {
                        'type': 'integer',
                        'description': 'ID direto do ConstructionDiary (opcional).',
                    },
                },
                'required': [],
            },
        },
    },
    {
        'type': 'function',
        'function': {
            'name': 'consultar_aprovadores_obra',
            'description': (
                'Lista aprovadores de RDO e membros de uma obra. '
                "Use quando perguntar 'quem aprova o RDO da obra X', "
                "'aprovadores do diário', 'quem preenche o diário'."
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
    {
        'type': 'function',
        'function': {
            'name': 'consultar_rdos_por_responsavel',
            'description': (
                'Consulta RDOs filtrados por quem preencheu/criou. '
                "Use quando perguntar 'RDOs do Cleiton', "
                "'diários enviados pela Emília', 'quem enviou RDO hoje'."
            ),
            'parameters': {
                'type': 'object',
                'properties': {
                    'responsavel_nome': {
                        'type': 'string',
                        'description': 'Nome ou username de quem preencheu o RDO.',
                    },
                    'obra_nome': {
                        'type': 'string',
                        'description': 'Nome da obra (opcional).',
                    },
                    'data_inicio': {
                        'type': 'string',
                        'description': 'Data inicial YYYY-MM-DD (opcional).',
                    },
                    'data_fim': {
                        'type': 'string',
                        'description': 'Data final YYYY-MM-DD (opcional).',
                    },
                },
                'required': [],
            },
        },
    },
    {
        'type': 'function',
        'function': {
            'name': 'consultar_pedidos_filtrados',
            'description': (
                'Consulta pedidos do GestControll com filtros avançados. '
                'Use para: pedidos dos últimos N dias, pedidos atrasados, '
                'com prazo vencido, por obra, frente, responsável/aprovador, '
                'tipo, credor, solicitante ou status. '
                "Exemplos: 'pedidos pendentes da última semana', "
                "'pedidos atrasados há mais de 15 dias', "
                "'pedidos com prazo vencido', 'pedidos da frente Norte'."
            ),
            'parameters': {
                'type': 'object',
                'properties': {
                    'obra_nome': {
                        'type': 'string',
                        'description': 'Nome ou parte do nome da obra (opcional).',
                    },
                    'status': {
                        'type': 'string',
                        'description': (
                            'Status: rascunho, pendente, aprovado, '
                            'reprovado, reaprovacao, cancelado (opcional).'
                        ),
                    },
                    'tipo': {
                        'type': 'string',
                        'description': (
                            'Tipo do pedido: medicao, contrato, etc (opcional).'
                        ),
                    },
                    'credor_nome': {
                        'type': 'string',
                        'description': 'Nome do credor/fornecedor (opcional).',
                    },
                    'solicitante_nome': {
                        'type': 'string',
                        'description': 'Nome de quem solicitou (opcional).',
                    },
                    'aprovador_nome': {
                        'type': 'string',
                        'description': 'Nome do aprovador (opcional).',
                    },
                    'ultimos_dias': {
                        'type': 'integer',
                        'description': (
                            'Filtrar pedidos dos últimos N dias (opcional).'
                        ),
                    },
                    'atraso_minimo_dias': {
                        'type': 'integer',
                        'description': (
                            'Pedidos pendentes há mais de N dias (opcional).'
                        ),
                    },
                    'frente_nome': {
                        'type': 'string',
                        'description': (
                            'Filtrar por frente (ou "obra inteira" para '
                            'pedidos sem frente). Opcional.'
                        ),
                    },
                    'prazo_vencido': {
                        'type': 'boolean',
                        'description': (
                            'Se True, retorna apenas pedidos pendentes/reaprovação '
                            'com prazo estimado vencido. Opcional.'
                        ),
                    },
                    'ordem': {
                        'type': 'string',
                        'description': (
                            'Ordenar por: recentes, antigos, obra (opcional).'
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
            'name': 'consultar_status_pedido',
            'description': (
                'Consulta status detalhado de um pedido específico: '
                'histórico de aprovações, alçada atual, quem aprovou, '
                'quem está pendente, datas. '
                'Use quando perguntar sobre um pedido específico por código.'
            ),
            'parameters': {
                'type': 'object',
                'properties': {
                    'codigo': {
                        'type': 'string',
                        'description': 'Código do pedido (ex: PC-001, 1234).',
                    },
                    'pedido_id': {
                        'type': 'integer',
                        'description': 'ID do WorkOrder (opcional).',
                    },
                },
                'required': [],
            },
        },
    },
    {
        'type': 'function',
        'function': {
            'name': 'consultar_desempenho_equipe_gest',
            'description': (
                'Desempenho de aprovadores no GestControll: pedidos '
                'pendentes AGORA (não histórico), tempo médio de '
                'aprovação em dias e pedidos aprovados no mês atual. '
                'Use para ranking de aprovadores ou gargalos.'
            ),
            'parameters': {
                'type': 'object',
                'properties': {
                    'obra_nome': {
                        'type': 'string',
                        'description': 'Filtrar por obra (opcional).',
                    },
                    'tipo': {
                        'type': 'string',
                        'description': (
                            'aprovadores ou solicitantes (opcional).'
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
            'name': 'buscar_pdf_pedido',
            'description': (
                'Gera e envia o PDF snapshot de um pedido específico. '
                "Use quando perguntar 'manda o PDF do pedido X', "
                "'envia o pedido 1234', 'PDF da solicitação'."
            ),
            'parameters': {
                'type': 'object',
                'properties': {
                    'codigo': {
                        'type': 'string',
                        'description': 'Código do pedido.',
                    },
                    'pedido_id': {
                        'type': 'integer',
                        'description': 'ID do WorkOrder (opcional).',
                    },
                },
                'required': [],
            },
        },
    },
    {
        'type': 'function',
        'function': {
            'name': 'consultar_pedidos_reprovados',
            'description': (
                'Consulta pedidos reprovados no GestControll. '
                'Retorna lista com motivo, obra e data. '
                'Use quando perguntar sobre pedidos reprovados, '
                'recusados ou negados.'
            ),
            'parameters': {
                'type': 'object',
                'properties': {
                    'obra_nome': {
                        'type': 'string',
                        'description': 'Filtrar por obra (opcional).',
                    },
                    'ultimos_dias': {
                        'type': 'integer',
                        'description': 'Últimos N dias (opcional).',
                    },
                },
                'required': [],
            },
        },
    },
    {
        'type': 'function',
        'function': {
            'name': 'localizar_insumo',
            'description': (
                'Localiza um insumo específico no mapa de suprimentos '
                'de uma obra por nome, código ou descrição. '
                'Retorna status, quantidade planejada, recebida, '
                'alocada e localização. '
                "Use quando perguntar sobre um material específico: "
                "'onde está o cimento', 'status do aço', "
                "'quanto tem de tinta na obra X'."
            ),
            'parameters': {
                'type': 'object',
                'properties': {
                    'insumo_nome': {
                        'type': 'string',
                        'description': 'Nome ou parte do nome do insumo.',
                    },
                    'obra_nome': {
                        'type': 'string',
                        'description': 'Nome da obra (opcional).',
                    },
                    'obra_id': {
                        'type': 'integer',
                        'description': 'ID do mapa_obras.Obra (opcional).',
                    },
                },
                'required': ['insumo_nome'],
            },
        },
    },
    {
        'type': 'function',
        'function': {
            'name': 'consultar_suprimentos_por_local',
            'description': (
                'Consulta o pipeline de materiais de um local específico '
                'de uma obra (bloco, pavimento, apartamento, setor). '
                'Retorna pendências, entregues, sem SC/PC. '
                "Use quando perguntar 'como está o bloco A', "
                "'situação do apto 302', 'materiais do pavimento 2'."
            ),
            'parameters': {
                'type': 'object',
                'properties': {
                    'obra_nome': {
                        'type': 'string',
                        'description': 'Nome da obra.',
                    },
                    'local_nome': {
                        'type': 'string',
                        'description': (
                            'Nome do local (bloco, apto, pavimento).'
                        ),
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
            'name': 'consultar_mapa_controle_completo',
            'description': (
                'Consulta o mapa de controle (execução física) completo '
                'de uma obra: percentual por bloco, pavimento, unidade, '
                'atividades. Informa qual ambiente está ativo, '
                'última atualização e versão. '
                "Use quando perguntar sobre avanço físico, "
                "'% de execução', 'como está o bloco B no controle', "
                "'qual o progresso da obra'."
            ),
            'parameters': {
                'type': 'object',
                'properties': {
                    'obra_nome': {
                        'type': 'string',
                        'description': 'Nome da obra.',
                    },
                    'obra_id': {
                        'type': 'integer',
                        'description': 'ID do mapa_obras.Obra (opcional).',
                    },
                    'detalhar_blocos': {
                        'type': 'boolean',
                        'description': (
                            'Se True, retorna % por bloco. Default True.'
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
            'name': 'consultar_bi_obra',
            'description': (
                'Consulta o BI consolidado de uma obra: '
                'todos os módulos juntos (suprimentos, diário, '
                'pedidos, restrições, TrackHub, execução física). '
                "Use quando perguntar por uma visão completa, "
                "'análise da obra', 'BI da obra X', "
                "'como está tudo na obra'."
            ),
            'parameters': {
                'type': 'object',
                'properties': {
                    'obra_nome': {
                        'type': 'string',
                        'description': 'Nome da obra.',
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
            'name': 'consultar_restricoes_por_responsavel',
            'description': (
                'Agrega restrições abertas por responsável: nome, '
                'quantidade abertas, vencidas e dias médios de atraso. '
                'Sem responsavel_nome retorna panorama de todos. '
                'NUNCA confundir responsável com obra.'
            ),
            'parameters': {
                'type': 'object',
                'properties': {
                    'responsavel_nome': {
                        'type': 'string',
                        'description': (
                            'Nome do responsável (opcional — sem ele, '
                            'retorna ranking de todos os responsáveis).'
                        ),
                    },
                    'obra_nome': {
                        'type': 'string',
                        'description': 'Filtrar por obra (opcional).',
                    },
                    'incluir_concluidas': {
                        'type': 'boolean',
                        'description': 'Default False.',
                    },
                },
                'required': [],
            },
        },
    },
    {
        'type': 'function',
        'function': {
            'name': 'consultar_pendencias_por_responsavel',
            'description': (
                'Consulta pendências TrackHub de um responsável. '
                'Separa como_responsavel_pendencia (dono da pendência) de '
                'como_responsavel_etapa (etapa dentro da pendência). '
                "Use quando perguntar 'pendências do Cleiton'."
            ),
            'parameters': {
                'type': 'object',
                'properties': {
                    'responsavel_nome': {
                        'type': 'string',
                        'description': 'Nome do responsável.',
                    },
                    'obra_nome': {
                        'type': 'string',
                        'description': 'Filtrar por obra (opcional).',
                    },
                    'incluir_concluidas': {
                        'type': 'boolean',
                        'description': 'Default False.',
                    },
                },
                'required': ['responsavel_nome'],
            },
        },
    },
    {
        'type': 'function',
        'function': {
            'name': 'consultar_etapas_pendencia',
            'description': (
                'Consulta as etapas de uma pendência TrackHub específica: '
                'quais foram concluídas, quais faltam, prazos e responsáveis. '
                "Use quando perguntar sobre o checklist de uma pendência, "
                "'como está a pendência X', 'etapas da tarefa Y'."
            ),
            'parameters': {
                'type': 'object',
                'properties': {
                    'pendencia_id': {
                        'type': 'integer',
                        'description': 'ID da pendência.',
                    },
                    'pendencia_titulo': {
                        'type': 'string',
                        'description': (
                            'Título ou parte do título (opcional).'
                        ),
                    },
                    'obra_nome': {
                        'type': 'string',
                        'description': 'Filtrar por obra (opcional).',
                    },
                },
                'required': [],
            },
        },
    },
    {
        'type': 'function',
        'function': {
            'name': 'consultar_resumo_mapa_obra',
            'description': (
                'Resumo do mapa geográfico de uma obra: totais de pontos, '
                'linhas e áreas, progresso geral, marcadores GPS, vínculos EAP '
                'e última data de diário. Requer nome ou ID da obra.'
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
    {
        'type': 'function',
        'function': {
            'name': 'listar_elementos_mapa_obra',
            'description': (
                'Lista elementos geográficos (GeoFeature) de uma obra com '
                'filtros opcionais por pasta, tipo (kind) e status.'
            ),
            'parameters': {
                'type': 'object',
                'properties': {
                    'obra_nome': {'type': 'string'},
                    'obra_id': {'type': 'integer'},
                    'folder': {
                        'type': 'string',
                        'description': 'Filtrar por pasta/trecho (opcional).',
                    },
                    'kind': {
                        'type': 'string',
                        'description': (
                            'segment, point, obstacle, vistoria, caixa, '
                            'area ou other (opcional).'
                        ),
                    },
                    'status': {
                        'type': 'string',
                        'description': (
                            'planned, in_progress, completed, blocked ou '
                            'vistoria (opcional).'
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
            'name': 'listar_pastas_mapa_obra',
            'description': (
                'Lista pastas/trechos distintos do mapa geográfico de uma obra.'
            ),
            'parameters': {
                'type': 'object',
                'properties': {
                    'obra_nome': {'type': 'string'},
                    'obra_id': {'type': 'integer'},
                },
                'required': [],
            },
        },
    },
    {
        'type': 'function',
        'function': {
            'name': 'consultar_alertas_mapa_obra',
            'description': (
                'Alertas do mapa geográfico: trechos bloqueados, sem vínculo '
                'EAP, estagnação de progresso e restrições cruzadas.'
            ),
            'parameters': {
                'type': 'object',
                'properties': {
                    'obra_nome': {'type': 'string'},
                    'obra_id': {'type': 'integer'},
                },
                'required': [],
            },
        },
    },
    {
        'type': 'function',
        'function': {
            'name': 'consultar_elementos_bloqueados_mapa',
            'description': (
                'Elementos bloqueados ou obstáculos no mapa geográfico da obra.'
            ),
            'parameters': {
                'type': 'object',
                'properties': {
                    'obra_nome': {'type': 'string'},
                    'obra_id': {'type': 'integer'},
                },
                'required': [],
            },
        },
    },
    {
        'type': 'function',
        'function': {
            'name': 'consultar_marcadores_gps_rdo',
            'description': (
                'Marcadores GPS de RDO no mapa geográfico (pontos vinculados '
                'a diários de obra).'
            ),
            'parameters': {
                'type': 'object',
                'properties': {
                    'obra_nome': {'type': 'string'},
                    'obra_id': {'type': 'integer'},
                },
                'required': [],
            },
        },
    },
    {
        'type': 'function',
        'function': {
            'name': 'comparar_progresso_mapa_datas',
            'description': (
                'Compara progresso do mapa geográfico entre duas datas: '
                'elementos que avançaram, estagnaram ou regrediram.'
            ),
            'parameters': {
                'type': 'object',
                'properties': {
                    'obra_nome': {'type': 'string'},
                    'obra_id': {'type': 'integer'},
                    'data_inicio': {
                        'type': 'string',
                        'description': 'Data inicial YYYY-MM-DD.',
                    },
                    'data_fim': {
                        'type': 'string',
                        'description': 'Data final YYYY-MM-DD.',
                    },
                },
                'required': ['data_inicio', 'data_fim'],
            },
        },
    },
    {
        'type': 'function',
        'function': {
            'name': 'panorama_mapas_obras',
            'description': (
                'Panorama dos mapas geográficos de todas as obras autorizadas '
                'do usuário: totais, progresso e segmentos por obra.'
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
            'name': 'consultar_resumo_rh',
            'description': (
                'Painel rápido do RH/DP: colaboradores por status e resumo '
                'de alertas (documentos, admissões, contratos).'
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
            'name': 'consultar_colaboradores_ativos',
            'description': (
                'Lista colaboradores ativos (nome, cargo, obras). '
                'Não retorna dados pessoais sensíveis.'
            ),
            'parameters': {
                'type': 'object',
                'properties': {
                    'obra_nome': {
                        'type': 'string',
                        'description': 'Filtrar por obra de alocação (opcional).',
                    },
                    'cargo': {
                        'type': 'string',
                        'description': 'Filtrar por cargo (opcional).',
                    },
                },
                'required': [],
            },
        },
    },
    {
        'type': 'function',
        'function': {
            'name': 'consultar_admissoes_em_andamento',
            'description': (
                'Colaboradores em processo de admissão: etapa, documentos '
                'faltando e pendentes.'
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
            'name': 'consultar_documentos_vencendo',
            'description': (
                'Documentos com validade vencendo nos próximos N dias '
                '(default: configuração de alertas do RH).'
            ),
            'parameters': {
                'type': 'object',
                'properties': {
                    'dias': {
                        'type': 'integer',
                        'description': 'Janela em dias (opcional).',
                    },
                },
                'required': [],
            },
        },
    },
    {
        'type': 'function',
        'function': {
            'name': 'consultar_documentos_vencidos',
            'description': 'Documentos de colaboradores já vencidos.',
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
            'name': 'consultar_prazos_contrato_vencendo',
            'description': (
                'Prazos de contrato ativos que vencem em breve ou já venceram.'
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
            'name': 'consultar_contratos_pendentes_assinatura',
            'description': (
                'Contratos de admissão aguardando assinatura (sem PDF/link).'
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
            'name': 'consultar_alertas_rh_criticos',
            'description': (
                'Top alertas críticos do RH (urgência vermelha e amarela), '
                'ordenados por prazo.'
            ),
            'parameters': {
                'type': 'object',
                'properties': {},
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


def _nomes_obras_excluidas_operacionais():
    from django.conf import settings

    raw = getattr(settings, 'WHATSAPP_IA_OBRAS_EXCLUIDAS', 'Sede')
    return [n.strip().lower() for n in raw.split(',') if n.strip()]


def _excluir_nao_obras_qs(qs, campo_nome='nome'):
    for nome in _nomes_obras_excluidas_operacionais():
        qs = qs.exclude(**{f'{campo_nome}__iexact': nome})
    return qs


def _get_escopo_obras(usuario_wa=None):
    """
    Retorna queryset de mapa_obras.Obra permitidas para o usuário.
    - Se usuario_wa é None ou sem permissão: retorna todas ativas.
    - Se tem IaPermissaoConsulta com obras: retorna só essas.
    - Se tem IaPermissaoConsulta sem obras: retorna todas ativas.
    - Exclui sede/escritório conforme WHATSAPP_IA_OBRAS_EXCLUIDAS.
    """
    from mapa_obras.models import Obra as ObraMapa
    from whatsapp_ia.models import IaPermissaoConsulta

    todas_ativas = _excluir_nao_obras_qs(ObraMapa.objects.filter(ativa=True))

    if not usuario_wa:
        return todas_ativas

    try:
        permissao = IaPermissaoConsulta.objects.get(usuario=usuario_wa)
        obras_auth = permissao.obras_autorizadas.all()
        if obras_auth.exists():
            return _excluir_nao_obras_qs(obras_auth.filter(ativa=True))
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
        try:
            exato = escopo.filter(nome__iexact=obra_nome).first()
            if exato:
                return exato
            return escopo.filter(nome__icontains=obra_nome).first()
        except Exception:
            nome_lower = obra_nome.lower()
            for obra in escopo:
                if obra.nome.lower() == nome_lower:
                    return obra
            for obra in escopo:
                if nome_lower in obra.nome.lower():
                    return obra
            return None
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
        try:
            exato = qs.filter(nome__iexact=obra_nome).first()
            if exato:
                return exato
            return qs.filter(nome__icontains=obra_nome).first()
        except Exception:
            nome_lower = obra_nome.lower()
            for obra in qs:
                if obra.nome.lower() == nome_lower:
                    return obra
            for obra in qs:
                if nome_lower in obra.nome.lower():
                    return obra
            return None
    return None


def _resolver_project(obra_nome=None, obra_id=None, usuario_wa=None):
    project_ids = _project_ids_escopo(usuario_wa)
    qs = Project.objects.filter(is_active=True, id__in=project_ids)
    if obra_id:
        return qs.filter(id=obra_id).first()
    if obra_nome:
        try:
            exato = qs.filter(name__iexact=obra_nome).first()
            if exato:
                return exato
            return qs.filter(name__icontains=obra_nome).first()
        except Exception:
            nome_lower = obra_nome.lower()
            for project in qs:
                if project.name.lower() == nome_lower:
                    return project
            for project in qs:
                if nome_lower in project.name.lower():
                    return project
            return None
    return None


def _queryset_workorders_escopo(usuario_wa=None):
    project_ids = _project_ids_escopo(usuario_wa)
    return WorkOrder.objects.filter(
        obra__project_id__in=project_ids,
    ).select_related('obra', 'front')


def _dias_em_aberto_pedido(workorder, hoje=None):
    if not workorder.data_envio:
        return None
    hoje = hoje or timezone.localdate()
    return max(0, (hoje - workorder.data_envio.date()).days)


def _pedido_prazo_vencido(workorder, hoje=None):
    if workorder.status not in ('pendente', 'reaprovacao'):
        return False
    if workorder.prazo_estimado is None or not workorder.data_envio:
        return False
    hoje = hoje or timezone.localdate()
    limite = workorder.data_envio.date() + timedelta(days=workorder.prazo_estimado)
    return limite < hoje


def _nome_frente_workorder(workorder):
    if getattr(workorder, 'front', None) and workorder.front_id:
        return workorder.front.name
    return 'Obra inteira'


def _frentes_ativas_project(project):
    from core.models import ProjectFront

    return list(
        ProjectFront.objects.filter(
            project=project,
            is_active=True,
        ).order_by('name'),
    )


def _resolver_frente(project, frente_nome=None, frente_id=None):
    from core.models import ProjectFront

    if not project:
        return None
    qs = ProjectFront.objects.filter(project=project, is_active=True)
    if frente_id:
        return qs.filter(pk=frente_id).first()
    if frente_nome:
        exato = qs.filter(name__iexact=frente_nome).first()
        if exato:
            return exato
        return qs.filter(name__icontains=frente_nome).first()
    return None


def _calcular_lacunas_rdo(datas, lacuna_minima_dias=7):
    if len(datas) < 2:
        return 0, []
    maior = 0
    lacunas = []
    for i in range(1, len(datas)):
        gap = (datas[i] - datas[i - 1]).days - 1
        if gap > maior:
            maior = gap
        if gap >= lacuna_minima_dias:
            lacunas.append({
                'apos_data': str(datas[i - 1]),
                'antes_data': str(datas[i]),
                'dias_sem_rdo': gap,
            })
    return maior, lacunas


def _metricas_rdo_frequencia(
    project,
    front_id=None,
    dias_analise=90,
    dias_sem_rdo_alerta=7,
    lacuna_minima_dias=7,
):
    hoje = timezone.localdate()
    inicio_periodo = hoje - timedelta(days=dias_analise)

    qs_all = ConstructionDiary.objects.filter(project=project)
    qs_periodo = qs_all.filter(date__gte=inicio_periodo, date__lte=hoje)

    if front_id == 'todas':
        pass
    elif front_id is None:
        qs_all = qs_all.filter(front__isnull=True)
        qs_periodo = qs_periodo.filter(front__isnull=True)
    else:
        qs_all = qs_all.filter(front_id=front_id)
        qs_periodo = qs_periodo.filter(front_id=front_id)

    datas_all = sorted(set(qs_all.values_list('date', flat=True)))
    datas_periodo = sorted(set(qs_periodo.values_list('date', flat=True)))

    nunca_teve = len(datas_all) == 0
    ultimo = datas_all[-1] if datas_all else None
    dias_desde_ultimo = (hoje - ultimo).days if ultimo else None
    maior_lacuna, lacunas = _calcular_lacunas_rdo(
        datas_periodo,
        lacuna_minima_dias=lacuna_minima_dias,
    )

    return {
        'ultimo_rdo_data': str(ultimo) if ultimo else None,
        'dias_desde_ultimo': dias_desde_ultimo,
        'total_rdos_periodo': len(datas_periodo),
        'maior_intervalo_sem_rdo_dias': maior_lacuna,
        'lacunas_no_periodo': _lacunas_exibicao(lacunas),
        'qtd_lacunas_no_periodo': len(lacunas),
        '_meta': _meta_ia(
            nunca_teve_rdo=nunca_teve,
            sem_rdo_recente=(
                dias_desde_ultimo is not None
                and dias_desde_ultimo > dias_sem_rdo_alerta
            ),
            dias_analise=dias_analise,
        ),
    }


def _get_escopo_trackhub(usuario_wa=None):
    """
    Escopo de obras para TrackHub — inclui Sede/escritório.
    Respeita permissões do usuário, mas não aplica WHATSAPP_IA_OBRAS_EXCLUIDAS.
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


def _situacao_rdo_periodo(
    project,
    front_id=None,
    dias_analise=90,
    dias_ag_critico=7,
):
    from core.models import DiaryNoReportDay

    hoje = timezone.localdate()
    inicio = hoje - timedelta(days=dias_analise)

    qs = ConstructionDiary.objects.filter(
        project=project,
        date__gte=inicio,
        date__lte=hoje,
    )
    if front_id == 'todas':
        pass
    elif front_id is None:
        qs = qs.filter(front__isnull=True)
    else:
        qs = qs.filter(front_id=front_id)

    por_status = {}
    for row in qs.values('status').annotate(qtd=Count('id')):
        por_status[row['status']] = row['qtd']

    total = sum(por_status.values())
    aprovados = por_status.get('AP', 0)
    pendentes_aprovacao = por_status.get('AG', 0)
    rascunhos = por_status.get('SP', 0) + por_status.get('PR', 0)

    qs_falta = DiaryNoReportDay.objects.filter(
        project=project,
        date__gte=inicio,
        date__lte=hoje,
    )
    dias_com_falta = qs_falta.count()

    ag_detalhes = []
    for d in qs.filter(status='AG').order_by('date'):
        dias_aberto = (hoje - d.date).days
        item = {
            'data': str(d.date),
            'dias_em_aberto': dias_aberto,
            'critico': dias_aberto >= dias_ag_critico,
        }
        ag_detalhes.append(item)

    ag_detalhes.sort(key=lambda x: -x['dias_em_aberto'])
    ag_criticos = [r for r in ag_detalhes if r['critico']]

    return {
        'total_rdos': total,
        'aprovados': aprovados,
        'pendentes_aprovacao': pendentes_aprovacao,
        'rascunhos': rascunhos,
        'reprovados': por_status.get('RG', 0),
        'dias_com_falta': dias_com_falta,
        'rdos_aguardando_aprovacao': ag_detalhes[:15],
        'rdos_ag_criticos': ag_criticos,
        'total_ag_criticos': len(ag_criticos),
        '_meta': _meta_ia(
            periodo_dias=dias_analise,
            por_status=por_status,
        ),
    }


def _classificar_volume_suprimentos(total_itens):
    if total_itens == 0:
        return {
            'descricao': (
                'Nenhum item cadastrado — pode indicar falta de controle'
            ),
            '_meta': _meta_ia(classificacao='sem_cadastro', sem_itens=True),
        }
    if total_itens < 15:
        return {
            'descricao': f'{total_itens} itens — volume baixo',
            '_meta': _meta_ia(classificacao='baixo'),
        }
    if total_itens < 50:
        return {
            'descricao': f'{total_itens} itens — volume moderado',
            '_meta': _meta_ia(classificacao='medio'),
        }
    if total_itens < 150:
        return {
            'descricao': f'{total_itens} itens — volume alto',
            '_meta': _meta_ia(classificacao='alto'),
        }
    return {
        'descricao': f'{total_itens} itens — volume muito alto',
        '_meta': _meta_ia(classificacao='muito_alto'),
    }


def _kpis_ambiente_controle(obra, ambiente):
    from painel_operacional.models import VersaoEstado
    from suprimentos.services.analise_obra_service import (
        AnaliseObraService,
        _collect_all_activity_pcts_from_rows,
    )

    service = AnaliseObraService(obra)
    versao = (
        ambiente.versoes.filter(estado=VersaoEstado.DRAFT)
        .order_by('-numero')
        .first()
        or ambiente.versoes.filter(estado=VersaoEstado.PUBLISHED)
        .order_by('-numero')
        .first()
    )
    if not versao:
        return {'percentual_conclusao': None, 'total_unidades': 0}

    layout = versao.layout if isinstance(versao.layout, dict) else {}
    rows = service._parse_layout_rows(layout)
    if not rows:
        return {'percentual_conclusao': None, 'total_unidades': 0}

    all_values = _collect_all_activity_pcts_from_rows(rows)
    pct = round(sum(all_values) / len(all_values), 1) if all_values else None
    return {
        'percentual_conclusao': pct,
        'total_unidades': len(all_values),
    }


def _serialize_pendencia_vencida(p, hoje):
    from trackhub.models import EtapaPendencia

    dias_atraso = (hoje - p.prazo).days if p.prazo else None
    resp_pendencia = p.responsavel_nome or 'Sem responsável'

    etapas_pendentes = []
    for et in EtapaPendencia.objects.filter(
        pendencia=p,
        status='pendente',
    ).select_related('responsavel_interno').order_by('ordem'):
        resp_etapa = (
            et.responsavel_interno.get_full_name()
            if et.responsavel_interno else 'Sem responsável'
        )
        etapas_pendentes.append({
            'etapa': et.titulo,
            'responsavel_etapa': resp_etapa,
            'prazo_etapa': str(et.prazo) if et.prazo else None,
        })

    return {
        'titulo': p.titulo,
        'tipo': p.tipo,
        'status': p.status,
        'prazo': str(p.prazo) if p.prazo else None,
        'dias_atraso': dias_atraso,
        'responsavel_pendencia': resp_pendencia,
        'etapas_pendentes': etapas_pendentes,
    }


def _agregar_pendencias_obra(obra, hoje):
    from trackhub.models import Pendencia

    qs = Pendencia.objects.filter(obra=obra).exclude(
        status__in=['concluida', 'cancelada'],
    )
    total_abertas = qs.count()
    vencidas_qs = qs.filter(prazo__isnull=False, prazo__lt=hoje)
    vencidas = vencidas_qs.count()

    por_status = {}
    for p in qs:
        por_status[p.status] = por_status.get(p.status, 0) + 1

    por_tipo = list(
        qs.values('tipo').annotate(qtd=Count('id')).order_by('-qtd'),
    )

    vencidas_detalhe = [
        _serialize_pendencia_vencida(p, hoje)
        for p in vencidas_qs.select_related(
            'responsavel_interno',
        ).order_by('prazo')[:20]
    ]

    resp_atraso = {}
    for item in vencidas_detalhe:
        nome = item['responsavel_pendencia']
        dias = item['dias_atraso'] or 0
        if nome not in resp_atraso:
            resp_atraso[nome] = {'pendencias': 0, 'maior_atraso_dias': 0}
        resp_atraso[nome]['pendencias'] += 1
        resp_atraso[nome]['maior_atraso_dias'] = max(
            resp_atraso[nome]['maior_atraso_dias'],
            dias,
        )

    responsaveis_atrasados = [
        {
            'responsavel_pendencia': nome,
            'pendencias_vencidas': stats['pendencias'],
            'maior_atraso_dias': stats['maior_atraso_dias'],
        }
        for nome, stats in sorted(
            resp_atraso.items(),
            key=lambda x: (-x[1]['maior_atraso_dias'], -x[1]['pendencias']),
        )
    ]

    return {
        'obra': obra.nome,
        'total_abertas': total_abertas,
        'vencidas': vencidas,
        'por_status': por_status,
        'por_tipo': por_tipo,
        'vencidas_detalhe': vencidas_detalhe,
        'responsaveis_atrasados': responsaveis_atrasados,
    }


def _contar_restricoes_abertas(obra_gestao, front_id=None):
    from impedimentos.models import Impedimento, StatusImpedimento

    if not obra_gestao:
        return {'total_abertas': 0, 'vencidas': 0}

    status_final = StatusImpedimento.objects.filter(
        obra=obra_gestao,
    ).order_by('-ordem').first()
    qs = Impedimento.objects.filter(
        obra=obra_gestao,
        parent__isnull=True,
    )
    if status_final:
        qs = qs.exclude(status_id=status_final.id)
    if front_id is None:
        qs = qs.filter(front__isnull=True)
    else:
        qs = qs.filter(front_id=front_id)

    hoje = timezone.localdate()
    return {
        'total_abertas': qs.count(),
        'vencidas': qs.filter(
            prazo__isnull=False,
            prazo__lt=hoje,
        ).count(),
    }


def _restricoes_totais_obra(obra_gestao) -> dict:
    from impedimentos.models import Impedimento, StatusImpedimento

    if not obra_gestao:
        return {'total_abertas': 0, 'vencidas': 0, 'criticas_altas': 0}

    status_final = StatusImpedimento.objects.filter(
        obra=obra_gestao,
    ).order_by('-ordem').first()
    qs = Impedimento.objects.filter(
        obra=obra_gestao,
        parent__isnull=True,
    )
    if status_final:
        qs = qs.exclude(status_id=status_final.id)

    hoje = timezone.localdate()
    return {
        'total_abertas': qs.count(),
        'vencidas': qs.filter(
            prazo__isnull=False,
            prazo__lt=hoje,
        ).count(),
        'criticas_altas': qs.filter(
            prioridade__in=['ALTA', 'CRITICA'],
        ).count(),
    }


def _restricoes_por_obra_escopo(usuario_wa) -> dict:
    from gestao_aprovacao.models import Obra as ObraGestao

    escopo_ids = list(_get_escopo_obras(usuario_wa).values_list('id', flat=True))
    obras_gestao = ObraGestao.objects.filter(
        ativo=True,
        project__obra_mapa__id__in=escopo_ids,
    ).order_by('nome')

    total_abertas = 0
    total_vencidas = 0
    total_criticas_altas = 0
    por_obra = []

    for obra_g in obras_gestao:
        stats = _restricoes_totais_obra(obra_g)
        total_abertas += stats['total_abertas']
        total_vencidas += stats['vencidas']
        total_criticas_altas += stats['criticas_altas']
        por_obra.append({
            'obra': obra_g.nome,
            'abertas': stats['total_abertas'],
            'vencidas': stats['vencidas'],
            'criticas_altas': stats['criticas_altas'],
        })

    por_obra.sort(key=lambda x: (-x['abertas'], x['obra']))
    return {
        'total_abertas': total_abertas,
        'total_vencidas': total_vencidas,
        'total_criticas_altas': total_criticas_altas,
        'obras': por_obra,
    }


def _anotar_alertas_rdo_segmento(seg, dias_sem_rdo_alerta=7, situacao=None):
    sit = situacao or seg.get('situacao_periodo') or seg.get('situacao') or {}
    meta = seg.setdefault('_meta', {})
    nivel = None
    tipo = None
    if meta.get('sem_rdo_recente'):
        dias = seg.get('dias_desde_ultimo')
        seg['alerta'] = f'Último RDO há {dias} dias sem registro recente'
        nivel = 'atencao'
        tipo = 'sem_rdo_recente'
    if meta.get('nunca_teve_rdo'):
        seg['alerta'] = 'Obra nunca registrou RDO'
        nivel = 'atencao'
        tipo = 'nunca_teve_rdo'
    ag_criticos = sit.get('rdos_ag_criticos') or []
    if sit.get('total_ag_criticos', 0) > 0:
        max_dias = max(
            (r.get('dias_em_aberto') or 0 for r in ag_criticos),
            default=0,
        )
        seg['alerta_ag_atrasado'] = (
            f'{sit["total_ag_criticos"]} RDO(s) aguardando aprovação '
            f'— o mais antigo há {max_dias} dias'
        )
        nivel = 'critico'
        tipo = 'ag_atrasado'
    if nivel:
        meta['nivel'] = nivel
        meta['tipo'] = tipo


def _obra_tem_alerta_rdo(obra_rdo: dict) -> bool:
    for seg in obra_rdo.get('segmentos', []):
        if seg.get('alerta') or seg.get('alerta_ag_atrasado'):
            return True
        seg_meta = seg.get('_meta', {})
        if seg_meta.get('sem_rdo_recente') or seg_meta.get('nunca_teve_rdo'):
            return True
    return False


def _obras_com_alerta_panorama(
    rdo: dict,
    pedidos: dict,
    restricoes: dict,
    suprimentos: dict,
    mapa: dict,
    trackhub_obras: list,
    obras_escopo: list,
) -> set:
    com_alerta = set()
    for obra in rdo.get('obras', []):
        if _obra_tem_alerta_rdo(obra):
            com_alerta.add(obra['obra'])
    for obra in pedidos.get('obras', []):
        if obra.get('atrasados', 0) > 0 or obra.get('prazo_vencido', 0) > 0:
            com_alerta.add(obra['obra'])
    for obra in restricoes.get('obras', []):
        if obra.get('abertas', 0) > 0:
            com_alerta.add(obra['obra'])
    for obra in suprimentos.get('obras', []):
        sem_itens = obra.get('total_itens', 0) == 0
        if sem_itens or obra.get('atrasados', 0) > 0:
            com_alerta.add(obra['obra'])
    for obra in mapa.get('obras', []):
        if not obra.get('tem_mapa_controle'):
            com_alerta.add(obra['obra'])
    trackhub_map = {t['obra']: t for t in trackhub_obras}
    for nome in obras_escopo:
        th = trackhub_map.get(nome)
        if th and th.get('vencidas', 0) > 0:
            com_alerta.add(nome)
    return com_alerta


def _serializar_pedido_pendente(workorder, hoje=None):
    hoje = hoje or timezone.localdate()
    dias = _dias_em_aberto_pedido(workorder, hoje)
    return {
        'codigo': workorder.codigo,
        'tipo': workorder.tipo_solicitacao,
        'credor': workorder.nome_credor,
        'status': workorder.status,
        'obra': workorder.obra.nome if workorder.obra else '-',
        'frente': _nome_frente_workorder(workorder),
        'data_envio': (
            str(workorder.data_envio.date()) if workorder.data_envio else '-'
        ),
        'dias_em_aberto': dias,
        'prazo_vencido': _pedido_prazo_vencido(workorder, hoje),
    }


def _agregar_pedidos_obra(
    obra_gestao,
    qs_pendentes,
    dias_aprovacao_alerta=7,
    hoje=None,
):
    hoje = hoje or timezone.localdate()
    pedidos = list(
        qs_pendentes.filter(obra=obra_gestao).select_related('front'),
    )

    por_frente = {}
    criticos = []
    atrasados = 0
    prazo_vencido = 0

    for w in pedidos:
        frente = _nome_frente_workorder(w)
        dias = _dias_em_aberto_pedido(w, hoje) or 0
        pv = _pedido_prazo_vencido(w, hoje)
        atrasado = dias > dias_aprovacao_alerta

        if frente not in por_frente:
            por_frente[frente] = {
                'pendentes': 0,
                'atrasados': 0,
                'prazo_vencido': 0,
            }
        por_frente[frente]['pendentes'] += 1
        if atrasado:
            por_frente[frente]['atrasados'] += 1
            atrasados += 1
        if pv:
            por_frente[frente]['prazo_vencido'] += 1
            prazo_vencido += 1

        if atrasado or pv:
            criticos.append({
                'codigo': w.codigo,
                'tipo': w.tipo_solicitacao,
                'credor': w.nome_credor,
                'frente': frente,
                'dias_em_aberto': dias,
                'prazo_vencido': pv,
                'data_envio': (
                    str(w.data_envio.date()) if w.data_envio else '-'
                ),
            })

    criticos.sort(
        key=lambda x: (x['prazo_vencido'], x['dias_em_aberto']),
        reverse=True,
    )

    return {
        'pendentes_total': len(pedidos),
        'atrasados': atrasados,
        'prazo_vencido': prazo_vencido,
        'por_frente': [
            {'frente': nome, **dados}
            for nome, dados in sorted(por_frente.items())
        ],
        'pedidos_atrasados': criticos[:10],
    }


def _mini_resumo_frente(project, front, obra_gestao, hoje=None):
    hoje = hoje or timezone.localdate()
    front_id = front.id if front else None
    metricas_rdo = _metricas_rdo_frequencia(
        project,
        front_id=front_id,
        dias_analise=30,
        dias_sem_rdo_alerta=7,
        lacuna_minima_dias=7,
    )

    qs_pendentes = WorkOrder.objects.filter(
        obra=obra_gestao,
        status__in=['pendente', 'reaprovacao'],
    )
    if front_id is None:
        qs_pendentes = qs_pendentes.filter(front__isnull=True)
    else:
        qs_pendentes = qs_pendentes.filter(front_id=front_id)

    pedidos_pendentes = qs_pendentes.count()
    pedidos_atrasados = sum(
        1 for w in qs_pendentes.select_related('front')
        if (_dias_em_aberto_pedido(w, hoje) or 0) > 7
    )
    restricoes = _contar_restricoes_abertas(obra_gestao, front_id=front_id)

    return {
        'frente': front.name if front else 'Obra inteira',
        'frente_id': front_id,
        'rdos': {
            'ultimo_rdo_data': metricas_rdo['ultimo_rdo_data'],
            'dias_desde_ultimo': metricas_rdo['dias_desde_ultimo'],
            'qtd_lacunas_no_periodo': metricas_rdo['qtd_lacunas_no_periodo'],
            '_meta': metricas_rdo.get('_meta', {}),
        },
        'pedidos_pendentes': pedidos_pendentes,
        'pedidos_atrasados': pedidos_atrasados,
        'restricoes_abertas': restricoes['total_abertas'],
        'restricoes_vencidas': restricoes['vencidas'],
    }


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


def consultar_pedidos_pendentes(
    obra_nome=None, obra_id=None, usuario_wa=None,
) -> str:
    if obra_nome and not obra_id:
        project = _resolver_project(obra_nome=obra_nome, usuario_wa=usuario_wa)
        if project:
            obra_id = project.id

    project_ids = _project_ids_escopo(usuario_wa)
    if obra_id and obra_id not in project_ids:
        return json.dumps({
            'total': 0,
            'pedidos': [],
            'agregacao_por_obra': [],
            'mensagem': 'Obra não encontrada ou sem permissão.',
        }, ensure_ascii=False)

    hoje = timezone.localdate()
    qs = _queryset_workorders_escopo(usuario_wa).filter(
        status__in=['pendente', 'reaprovacao'],
    ).order_by('-data_envio')
    if obra_id:
        qs = qs.filter(obra__project_id=obra_id)

    resultados = [
        _serializar_pedido_pendente(w, hoje)
        for w in qs[:20]
    ]

    payload = {
        'total': qs.count(),
        'pedidos': resultados,
    }

    if not obra_id:
        agregacao = {}
        for w in qs.select_related('obra', 'front'):
            nome_obra = w.obra.nome if w.obra else '-'
            if nome_obra not in agregacao:
                agregacao[nome_obra] = {
                    'obra': nome_obra,
                    'pendentes': 0,
                    'atrasados': 0,
                    'prazo_vencido': 0,
                }
            agregacao[nome_obra]['pendentes'] += 1
            dias = _dias_em_aberto_pedido(w, hoje) or 0
            if dias > 7:
                agregacao[nome_obra]['atrasados'] += 1
            if _pedido_prazo_vencido(w, hoje):
                agregacao[nome_obra]['prazo_vencido'] += 1
        payload['agregacao_por_obra'] = sorted(
            agregacao.values(),
            key=lambda x: (-x['pendentes'], x['obra']),
        )

    return json.dumps(payload, ensure_ascii=False)


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

    projetos_com_rdo_aprovado_hoje = ConstructionDiary.objects.filter(
        date=data,
        status='AP',
        project_id__in=project_ids,
    ).values_list('project_id', flat=True)

    sem_rdo_hoje = list(
        projetos_ativos.exclude(
            id__in=projetos_com_rdo_aprovado_hoje,
        ).values('id', 'name'),
    )

    projetos_com_qualquer_rdo = ConstructionDiary.objects.filter(
        project_id__in=project_ids,
    ).values_list('project_id', flat=True).distinct()

    nunca_teve_rdo = list(
        projetos_ativos.exclude(
            id__in=projetos_com_qualquer_rdo,
        ).values('id', 'name'),
    )

    return json.dumps({
        'data_referencia': str(data),
        'sem_rdo_hoje': {
            'total': len(sem_rdo_hoje),
            'descricao': (
                'Obras ativas sem RDO aprovado na data de referência'
            ),
            'obras': sem_rdo_hoje,
        },
        'obras_sem_historico_rdo': {
            'total': len(nunca_teve_rdo),
            'descricao': 'Obras ativas que nunca registraram RDO no histórico',
            'obras': nunca_teve_rdo,
        },
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
            'sem_solicitacao_compra': kpis.get('sem_sc', 0),
            'sem_pedido_compra': kpis.get('sem_pc', 0),
            'sem_entrega_registrada': kpis.get('sem_entrega', 0),
            'sem_alocacao': kpis.get('sem_alocacao', 0),
            'atrasados': kpis.get('atrasados', 0),
            'percentual_medio_alocacao_pct': kpis.get(
                'percentual_medio_alocacao', 0,
            ),
        }, ensure_ascii=False)
    except Exception as e:
        return json.dumps({'erro': str(e)}, ensure_ascii=False)


def consultar_panorama_suprimentos(usuario_wa=None) -> str:
    obras = list(_get_escopo_obras(usuario_wa).order_by('nome'))
    resultado = []
    for obra in obras:
        try:
            service = MapaControleService(obra, MapaControleFilters())
            kpis = service.build_summary_payload().get('kpis', {})
            total_itens = kpis.get('total_itens', 0)
            volume = _classificar_volume_suprimentos(total_itens)
            resultado.append({
                'obra': obra.nome,
                'total_itens': total_itens,
                'sem_alocacao': kpis.get('sem_alocacao', 0),
                'atrasados': kpis.get('atrasados', 0),
                'descricao_volume': volume['descricao'],
                '_meta': volume.get('_meta', {}),
            })
        except Exception:
            volume = _classificar_volume_suprimentos(0)
            resultado.append({
                'obra': obra.nome,
                'total_itens': 0,
                'sem_alocacao': 0,
                'atrasados': 0,
                'descricao_volume': volume['descricao'],
                '_meta': {**volume.get('_meta', {}), 'erro_dados': True},
            })
    resultado.sort(key=lambda x: (-x['total_itens'], x['obra']))
    obras_sem_itens = [r['obra'] for r in resultado if r['total_itens'] == 0]
    aviso = None
    if obras_sem_itens:
        aviso = (
            f'{len(obras_sem_itens)} obra(s) sem nenhum item cadastrado'
        )
    return json.dumps({
        'total_obras': len(resultado),
        'obras': resultado,
        'obras_sem_itens': obras_sem_itens,
        'aviso': aviso,
    }, ensure_ascii=False)


def consultar_panorama_mapa_controle(usuario_wa=None) -> str:
    from painel_operacional.models import AmbienteOperacional, AmbienteTipo
    from suprimentos.services.mapa_controle_viewmodel import AmbienteProvider
    from suprimentos.views_controle import (
        _build_matrix_payload_from_rows,
        _extract_first_matrix_rows_from_layout,
    )

    provider = AmbienteProvider(
        extract_first_matrix_rows_from_layout=_extract_first_matrix_rows_from_layout,
        build_matrix_payload_from_rows=_build_matrix_payload_from_rows,
    )
    selected_base = {
        'setor': '',
        'bloco': '',
        'pavimento': '',
        'apto': '',
        'atividade': '',
        'status': '',
        'search': '',
        'quick_find': '',
        'matrix_mode': '',
        'column_group': '',
    }

    obras = list(_get_escopo_obras(usuario_wa).order_by('nome'))
    resultado = []
    for obra in obras:
        ambientes = AmbienteOperacional.objects.filter(
            obra=obra,
            tipo=AmbienteTipo.MAPA_CONTROLE,
            ativo=True,
        ).order_by('-updated_at')

        mapas = []
        for amb in ambientes:
            view_ctx = provider.build(
                obra=obra,
                selected=dict(selected_base),
                ambiente_id=amb.id,
            )
            pct = None
            total_unidades = 0
            if view_ctx:
                matrix = view_ctx.get('matrix') or {}
                kpis = view_ctx.get('kpis') or {}
                raw_pct = matrix.get('total_geral')
                if raw_pct is None and kpis.get('total_itens'):
                    raw_pct = kpis.get('percentual_medio')
                if raw_pct is not None:
                    pct = float(raw_pct)
                total_unidades = int(kpis.get('total_itens') or 0)

            mapas.append({
                'nome': amb.nome,
                'ultima_atualizacao': (
                    str(amb.updated_at.date()) if amb.updated_at else '-'
                ),
                'percentual_conclusao': pct,
                'quantidade_unidades': total_unidades,
            })

        item = {
            'obra': obra.nome,
            'tem_mapa_controle': len(mapas) > 0,
            'total_mapas': len(mapas),
            'mapas': mapas,
        }
        if len(mapas) == 1:
            item['percentual_conclusao'] = mapas[0]['percentual_conclusao']
        elif len(mapas) > 1:
            item['_meta'] = {'multiplos_mapas': True}
        resultado.append(item)

    def _ordem_mapa_obra(obra_item):
        if not obra_item['tem_mapa_controle']:
            return (True, 0)
        pcts = [
            m['percentual_conclusao']
            for m in obra_item['mapas']
            if m['percentual_conclusao'] is not None
        ]
        return (False, -(max(pcts) if pcts else 0))

    resultado.sort(key=_ordem_mapa_obra)
    return json.dumps({
        'total_obras': len(resultado),
        'obras': resultado,
    }, ensure_ascii=False)


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
    hoje = timezone.localdate()

    if obra_nome or obra_id:
        escopo_th = _get_escopo_trackhub(usuario_wa)
        if obra_id:
            obra = escopo_th.filter(id=obra_id).first()
        elif obra_nome:
            obra = escopo_th.filter(nome__icontains=obra_nome).first()
            if not obra:
                obra = _resolver_obra_mapa(obra_nome, obra_id, usuario_wa)
        else:
            obra = None
        if not obra:
            return json.dumps(
                {'erro': 'Obra não encontrada.'},
                ensure_ascii=False,
            )
        obras = [obra]
    else:
        obras = list(_get_escopo_trackhub(usuario_wa).order_by('nome'))

    resultado = []
    total_abertas_global = 0
    total_vencidas_global = 0

    for obra in obras:
        item = _agregar_pendencias_obra(obra, hoje)
        resultado.append(item)
        total_abertas_global += item['total_abertas']
        total_vencidas_global += item['vencidas']

    resultado.sort(
        key=lambda x: (-x['vencidas'], -x['total_abertas'], x['obra']),
    )

    return json.dumps({
        'data_referencia': str(hoje),
        'inclui_sede': True,
        'totais': {
            'obras': len(resultado),
            'abertas': total_abertas_global,
            'vencidas': total_vencidas_global,
        },
        'obras': resultado,
    }, ensure_ascii=False)


def consultar_pendencias_vencidas(obra_nome=None, usuario_wa=None) -> str:
    from trackhub.models import Pendencia

    hoje = timezone.localdate()
    escopo = _get_escopo_trackhub(usuario_wa)

    qs = Pendencia.objects.filter(
        prazo__lt=hoje,
        obra__in=escopo,
    ).exclude(
        status__in=['concluida', 'cancelada'],
    ).select_related('obra', 'responsavel_interno')

    if obra_nome:
        obra = _resolver_obra_mapa(obra_nome=obra_nome, usuario_wa=usuario_wa)
        if not obra:
            obra = escopo.filter(nome__icontains=obra_nome).first()
        if not obra:
            return json.dumps({
                'total_vencidas': 0,
                'pendencias': [],
                'mensagem': 'Obra não encontrada ou sem permissão.',
            }, ensure_ascii=False)
        qs = qs.filter(obra=obra)

    resultado = []
    for p in qs.order_by('prazo')[:30]:
        resultado.append({
            'obra': p.obra.nome if p.obra else '-',
            **_serialize_pendencia_vencida(p, hoje),
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
    obra_gestao = None
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

    frentes_resumo = []
    if obra_gestao:
        frentes_ativas = _frentes_ativas_project(project)
        if frentes_ativas:
            frentes_resumo.append(
                _mini_resumo_frente(project, None, obra_gestao),
            )
            for front in frentes_ativas:
                frentes_resumo.append(
                    _mini_resumo_frente(project, front, obra_gestao),
                )

    payload = {
        'obra': project.name,
        'rdos_pendentes_gestor': rdos_pendentes,
        'pedidos_pendentes': pedidos_pendentes,
        'itens_sem_alocacao': itens_sem_alocacao,
        'restricoes_abertas': restricoes_abertas,
        'pendencias_trackhub_abertas': pendencias_abertas,
        'rdo': _situacao_rdo_periodo(project, front_id='todas'),
        'rdo_frequencia': _metricas_rdo_frequencia(
            project, front_id='todas',
        ),
    }
    freq = payload['rdo_frequencia']
    freq_meta = freq.get('_meta', {})
    if freq_meta.get('sem_rdo_recente'):
        payload['alerta_rdo'] = (
            f'Último RDO há {freq["dias_desde_ultimo"]} dias sem registro recente'
        )
        payload['_meta'] = _meta_ia(
            alerta_rdo_nivel='atencao',
            alerta_rdo_tipo='sem_rdo_recente',
        )
    elif freq_meta.get('nunca_teve_rdo'):
        payload['alerta_rdo'] = 'Obra nunca registrou RDO'
        payload['_meta'] = _meta_ia(
            alerta_rdo_nivel='atencao',
            alerta_rdo_tipo='nunca_teve_rdo',
        )
    if frentes_resumo:
        payload['tem_frentes_ativas'] = True
        payload['frentes'] = frentes_resumo
    else:
        payload['tem_frentes_ativas'] = False

    return json.dumps(payload, ensure_ascii=False)


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


def consultar_usuarios(
    usuario_nome=None, apenas_ativos=False, usuario_wa=None,
) -> str:
    from django.contrib.auth import get_user_model

    from core.models import Project, ProjectMember
    from gestao_aprovacao.models import Approval, WorkOrderPermission
    from impedimentos.models import Impedimento, StatusImpedimento
    from trackhub.models import Pendencia

    User = get_user_model()

    qs = User.objects.all()
    if apenas_ativos:
        qs = qs.filter(is_active=True)
    if usuario_nome:
        qs = qs.filter(
            Q(first_name__icontains=usuario_nome)
            | Q(last_name__icontains=usuario_nome)
            | Q(username__icontains=usuario_nome),
        )

    total = qs.count()
    ativos = User.objects.filter(is_active=True).count()
    inativos = User.objects.filter(is_active=False).count()

    hoje = timezone.localdate()
    inicio_mes = hoje.replace(day=1)
    project_ids = _project_ids_escopo(usuario_wa)
    escopo_ids = list(_get_escopo_obras(usuario_wa).values_list('id', flat=True))

    usuarios = []
    for u in qs[:20]:
        ultimo_login = str(u.last_login.date()) if u.last_login else 'Nunca'
        perfil = {
            'id': u.id,
            'nome': u.get_full_name() or u.username,
            'username': u.username,
            'ativo': u.is_active,
            'ultimo_login': ultimo_login,
        }

        if usuario_nome:
            obras_vinculadas = set()
            for pm in ProjectMember.objects.filter(
                user=u,
                project_id__in=project_ids,
            ).select_related('project'):
                obras_vinculadas.add(pm.project.name)
            for perm in WorkOrderPermission.objects.filter(
                usuario=u,
                ativo=True,
                obra__project_id__in=project_ids,
            ).select_related('obra'):
                obras_vinculadas.add(perm.obra.nome)

            imp_qs = Impedimento.objects.filter(
                parent__isnull=True,
                responsaveis=u,
                obra__project__obra_mapa__id__in=escopo_ids,
            )
            restricoes_abertas = 0
            for imp in imp_qs.select_related('obra', 'status'):
                sf = StatusImpedimento.objects.filter(
                    obra=imp.obra,
                ).order_by('-ordem').first()
                if sf and imp.status_id == sf.id:
                    continue
                restricoes_abertas += 1

            obras_aprovador = WorkOrderPermission.objects.filter(
                usuario=u,
                tipo_permissao='aprovador',
                ativo=True,
                obra__project_id__in=project_ids,
            ).values_list('obra_id', flat=True)
            pedidos_pendentes = _queryset_workorders_escopo(usuario_wa).filter(
                status__in=['pendente', 'reaprovacao'],
                obra_id__in=obras_aprovador,
            ).count()

            pendencias_resp_pendencia = Pendencia.objects.filter(
                responsavel_interno=u,
                obra_id__in=list(
                    _get_escopo_trackhub(usuario_wa).values_list('id', flat=True),
                ),
                prazo__lt=hoje,
            ).exclude(
                status__in=['concluida', 'cancelada'],
            ).count()

            from trackhub.models import EtapaPendencia

            pendencias_resp_etapa = EtapaPendencia.objects.filter(
                responsavel_interno=u,
                status='pendente',
                pendencia__obra_id__in=list(
                    _get_escopo_trackhub(usuario_wa).values_list('id', flat=True),
                ),
            ).exclude(
                pendencia__status__in=['concluida', 'cancelada'],
            ).filter(
                prazo__lt=hoje,
            ).count()

            tempos = []
            for ap in Approval.objects.filter(
                aprovado_por=u,
                decisao='aprovado',
                work_order__obra__project_id__in=project_ids,
            ).select_related('work_order'):
                wo = ap.work_order
                if wo.data_envio:
                    tempos.append(
                        max(0, (ap.created_at.date() - wo.data_envio.date()).days),
                    )

            perfil.update({
                'obras_vinculadas': sorted(obras_vinculadas),
                'restricoes_abertas': restricoes_abertas,
                'pedidos_aguardando_aprovacao': pedidos_pendentes,
                'pendencias_atrasadas_como_dono': pendencias_resp_pendencia,
                'pendencias_atrasadas_como_responsavel_etapa': (
                    pendencias_resp_etapa
                ),
                'tempo_medio_aprovacao_dias': (
                    round(sum(tempos) / len(tempos), 1) if tempos else None
                ),
                'pedidos_aprovados_mes_atual': Approval.objects.filter(
                    aprovado_por=u,
                    decisao='aprovado',
                    created_at__date__gte=inicio_mes,
                    work_order__obra__project_id__in=project_ids,
                ).count(),
            })
        else:
            perfil['email'] = u.email

        usuarios.append(perfil)

    return json.dumps({
        'total': total,
        'total_ativos': ativos,
        'total_inativos': inativos,
        'usuarios': usuarios,
    }, ensure_ascii=False)


def consultar_dados_obra(
    obra_nome=None, obra_id=None, usuario_wa=None,
) -> str:
    from core.models import (
        Activity,
        ConstructionDiary,
        Equipment,
        Labor,
        ProjectDiaryApprover,
        ProjectMember,
    )

    project = _resolver_project(
        obra_nome=obra_nome,
        obra_id=obra_id,
        usuario_wa=usuario_wa,
    )
    if not project:
        return json.dumps(
            {'erro': 'Obra não encontrada.'},
            ensure_ascii=False,
        )

    membros = list(
        ProjectMember.objects.filter(project=project)
        .select_related('user')
        .values('user__first_name', 'user__last_name', 'user__email')
    )

    aprovadores = list(
        ProjectDiaryApprover.objects.filter(
            project=project, is_active=True,
        ).order_by('order')
        .select_related('user')
        .values('user__first_name', 'user__last_name', 'order')
    )

    try:
        from mapa_obras.models import LocalObra
        total_locais = LocalObra.objects.filter(
            obra__project=project,
        ).count()
    except Exception:
        total_locais = 0

    total_rdos = ConstructionDiary.objects.filter(
        project=project,
    ).count()
    rdos_aprovados = ConstructionDiary.objects.filter(
        project=project, status='AP',
    ).count()

    try:
        total_atividades = Activity.objects.filter(
            project=project,
        ).count()
    except Exception:
        total_atividades = 0

    try:
        total_equipamentos = Equipment.objects.filter(
            project=project,
        ).count()
        total_mao_obra = Labor.objects.filter(
            project=project,
        ).count()
    except Exception:
        total_equipamentos = 0
        total_mao_obra = 0

    return json.dumps({
        'obra': project.name,
        'ativa': project.is_active,
        'total_membros': len(membros),
        'membros': membros,
        'aprovadores_rdo': aprovadores,
        'total_locais_mapa': total_locais,
        'total_rdos': total_rdos,
        'rdos_aprovados': rdos_aprovados,
        'total_atividades': total_atividades,
        'total_equipamentos_rdo': total_equipamentos,
        'total_mao_obra_rdo': total_mao_obra,
    }, ensure_ascii=False)


def consultar_modulos_sistema(usuario_wa=None) -> str:
    from django.contrib.auth import get_user_model

    from core.models import ConstructionDiary, Project
    from gestao_aprovacao.models import WorkOrder
    from impedimentos.models import Impedimento
    from suprimentos.models import ItemMapa
    from trackhub.models import Pendencia

    User = get_user_model()

    try:
        from painel_operacional.models import AmbienteOperacional
        total_ambientes = AmbienteOperacional.objects.filter(
            ativo=True,
        ).count()
    except Exception:
        total_ambientes = 0

    return json.dumps({
        'usuarios': {
            'total': User.objects.count(),
            'ativos': User.objects.filter(is_active=True).count(),
        },
        'obras': {
            'total': Project.objects.count(),
            'ativas': Project.objects.filter(is_active=True).count(),
        },
        'diario_obra': {
            'total_rdos': ConstructionDiary.objects.count(),
            'aprovados': ConstructionDiary.objects.filter(
                status='AP',
            ).count(),
            'pendentes_gestor': ConstructionDiary.objects.filter(
                status='AG',
            ).count(),
        },
        'gestcontroll': {
            'total_pedidos': WorkOrder.objects.count(),
            'pendentes': WorkOrder.objects.filter(
                status__in=['pendente', 'reaprovacao'],
            ).count(),
            'aprovados': WorkOrder.objects.filter(
                status='aprovado',
            ).count(),
        },
        'restricoes': {
            'total': Impedimento.objects.filter(
                parent__isnull=True,
            ).count(),
        },
        'trackhub': {
            'total_pendencias': Pendencia.objects.count(),
            'abertas': Pendencia.objects.exclude(
                status__in=['concluida', 'cancelada'],
            ).count(),
        },
        'suprimentos': {
            'total_itens_mapa': ItemMapa.objects.count(),
        },
        'ambientes_operacionais': {
            'total_ativos': total_ambientes,
        },
    }, ensure_ascii=False)


def consultar_rdos_por_periodo(
    obra_nome=None, obra_id=None,
    data_inicio=None, data_fim=None,
    status=None, usuario_wa=None,
) -> str:
    project = _resolver_project(
        obra_nome=obra_nome,
        obra_id=obra_id,
        usuario_wa=usuario_wa,
    )
    if not project:
        return json.dumps(
            {'erro': 'Obra não encontrada.'},
            ensure_ascii=False,
        )

    qs = ConstructionDiary.objects.filter(
        project=project,
    ).order_by('-date')

    if data_inicio:
        try:
            qs = qs.filter(
                date__gte=datetime.strptime(
                    data_inicio, '%Y-%m-%d',
                ).date(),
            )
        except ValueError:
            pass

    if data_fim:
        try:
            qs = qs.filter(
                date__lte=datetime.strptime(
                    data_fim, '%Y-%m-%d',
                ).date(),
            )
        except ValueError:
            pass
    else:
        qs = qs.filter(date__lte=timezone.localdate())

    if status:
        qs = qs.filter(status=status.upper())

    status_labels = {
        'PR': 'Preenchendo',
        'SP': 'Salvamento parcial',
        'AG': 'Aguardando aprovação',
        'RG': 'Reprovado',
        'AP': 'Aprovado',
    }

    rdos = []
    for d in qs[:30]:
        rdos.append({
            'id': d.id,
            'data': str(d.date),
            'status': status_labels.get(d.status, d.status),
            'report_number': getattr(d, 'report_number', None),
            'criado_por': (
                d.created_by.get_full_name()
                if hasattr(d, 'created_by') and d.created_by
                else '-'
            ),
        })

    return json.dumps({
        'obra': project.name,
        'total': qs.count(),
        'rdos': rdos,
    }, ensure_ascii=False)


def consultar_detalhes_rdo(
    obra_nome=None, obra_id=None,
    data=None, diary_id=None,
    usuario_wa=None,
) -> str:
    from core.models import DailyWorkLog, DiaryOccurrence

    if diary_id:
        try:
            diary = ConstructionDiary.objects.select_related(
                'project',
            ).get(id=diary_id)
        except ConstructionDiary.DoesNotExist:
            return json.dumps(
                {'erro': 'RDO não encontrado.'},
                ensure_ascii=False,
            )
    else:
        project = _resolver_project(
            obra_nome=obra_nome,
            obra_id=obra_id,
            usuario_wa=usuario_wa,
        )
        if not project:
            return json.dumps(
                {'erro': 'Obra não encontrada.'},
                ensure_ascii=False,
            )
        data_obj = _data_ou_hoje(data)
        try:
            diary = ConstructionDiary.objects.get(
                project=project, date=data_obj,
            )
        except ConstructionDiary.DoesNotExist:
            return json.dumps({
                'erro': f'Nenhum RDO em {data_obj} '
                        f'para {project.name}.',
            }, ensure_ascii=False)

    clima = {}
    for campo in [
        'weather_conditions',
        'weather_morning_rain', 'weather_afternoon_rain',
        'weather_night_rain',
    ]:
        val = getattr(diary, campo, None)
        if val is not None:
            clima[campo] = val

    work_logs = DailyWorkLog.objects.filter(
        diary=diary,
    ).select_related('activity').prefetch_related(
        'resources_labor', 'resources_equipment',
    )

    atividades = []
    equipe = set()
    equipamentos = set()

    for wl in work_logs:
        if wl.activity:
            atividades.append(wl.activity.name)
        for labor in wl.resources_labor.all():
            equipe.add(
                getattr(labor, 'name', str(labor)),
            )
        for equip in wl.resources_equipment.all():
            equipamentos.add(
                getattr(equip, 'name', str(equip)),
            )

    ocorrencias = []
    try:
        for oc in DiaryOccurrence.objects.filter(
            diary=diary,
        )[:10]:
            ocorrencias.append(
                getattr(oc, 'description', str(oc)),
            )
    except Exception:
        pass

    status_labels = {
        'PR': 'Preenchendo',
        'SP': 'Salvamento parcial',
        'AG': 'Aguardando aprovação',
        'RG': 'Reprovado',
        'AP': 'Aprovado',
    }

    return json.dumps({
        'obra': diary.project.name,
        'data': str(diary.date),
        'status': status_labels.get(diary.status, diary.status),
        'report_number': getattr(diary, 'report_number', None),
        'criado_por': (
            diary.created_by.get_full_name()
            if hasattr(diary, 'created_by') and diary.created_by
            else '-'
        ),
        'clima': clima,
        'atividades': list(set(atividades)),
        'equipe': list(equipe),
        'equipamentos': list(equipamentos),
        'ocorrencias': ocorrencias,
    }, ensure_ascii=False)


def consultar_aprovadores_obra(
    obra_nome=None, obra_id=None, usuario_wa=None,
) -> str:
    from core.models import ProjectDiaryApprover, ProjectMember

    project = _resolver_project(
        obra_nome=obra_nome,
        obra_id=obra_id,
        usuario_wa=usuario_wa,
    )
    if not project:
        return json.dumps(
            {'erro': 'Obra não encontrada.'},
            ensure_ascii=False,
        )

    aprovadores = []
    for ap in ProjectDiaryApprover.objects.filter(
        project=project, is_active=True,
    ).order_by('order').select_related('user'):
        aprovadores.append({
            'nome': ap.user.get_full_name() or ap.user.username,
            'email': ap.user.email,
            'ordem': ap.order,
        })

    membros = []
    for m in ProjectMember.objects.filter(
        project=project,
    ).select_related('user'):
        membros.append({
            'nome': m.user.get_full_name() or m.user.username,
            'email': m.user.email,
        })

    return json.dumps({
        'obra': project.name,
        'aprovadores_rdo': aprovadores,
        'membros_diario': membros,
    }, ensure_ascii=False)


def consultar_rdos_por_responsavel(
    responsavel_nome=None, obra_nome=None,
    data_inicio=None, data_fim=None,
    usuario_wa=None,
) -> str:
    from django.contrib.auth import get_user_model

    User = get_user_model()

    qs = ConstructionDiary.objects.select_related(
        'project', 'created_by',
    ).filter(
        project_id__in=_project_ids_escopo(usuario_wa),
    ).order_by('-date')

    if responsavel_nome:
        usuarios = User.objects.filter(
            Q(first_name__icontains=responsavel_nome)
            | Q(last_name__icontains=responsavel_nome)
            | Q(username__icontains=responsavel_nome),
        )
        if not usuarios.exists():
            return json.dumps({
                'erro': f'Usuário "{responsavel_nome}" não encontrado.',
            }, ensure_ascii=False)
        qs = qs.filter(created_by__in=usuarios)

    if obra_nome:
        project = _resolver_project(
            obra_nome=obra_nome,
            usuario_wa=usuario_wa,
        )
        if project:
            qs = qs.filter(project=project)

    if data_inicio:
        try:
            qs = qs.filter(
                date__gte=datetime.strptime(
                    data_inicio, '%Y-%m-%d',
                ).date(),
            )
        except ValueError:
            pass
    if data_fim:
        try:
            qs = qs.filter(
                date__lte=datetime.strptime(
                    data_fim, '%Y-%m-%d',
                ).date(),
            )
        except ValueError:
            pass

    status_labels = {
        'PR': 'Preenchendo', 'SP': 'Rascunho',
        'AG': 'Aguardando aprovação',
        'RG': 'Reprovado', 'AP': 'Aprovado',
    }

    rdos = []
    for d in qs[:20]:
        rdos.append({
            'id': d.id,
            'obra': d.project.name,
            'data': str(d.date),
            'status': status_labels.get(d.status, d.status),
            'criado_por': (
                d.created_by.get_full_name()
                if d.created_by else '-'
            ),
        })

    return json.dumps({
        'total': qs.count(),
        'rdos': rdos,
    }, ensure_ascii=False)


def _obra_gestao_por_project(project):
    if not project:
        return None
    from gestao_aprovacao.models import Obra as ObraGestao
    return ObraGestao.objects.filter(project=project).first()


def consultar_pedidos_filtrados(
    obra_nome=None, status=None, tipo=None,
    credor_nome=None, solicitante_nome=None,
    aprovador_nome=None, ultimos_dias=None,
    atraso_minimo_dias=None, frente_nome=None,
    prazo_vencido=None, ordem=None,
    usuario_wa=None,
) -> str:
    from django.contrib.auth import get_user_model

    from gestao_aprovacao.models import Approval, WorkOrderPermission

    User = get_user_model()
    hoje = timezone.localdate()

    qs = _queryset_workorders_escopo(usuario_wa).order_by('-data_envio')

    if obra_nome:
        project = _resolver_project(
            obra_nome=obra_nome, usuario_wa=usuario_wa,
        )
        obra_g = _obra_gestao_por_project(project)
        if obra_g:
            qs = qs.filter(obra=obra_g)

    if frente_nome:
        nome_lower = frente_nome.strip().lower()
        if nome_lower in ('obra inteira', 'sem frente', 'obra toda'):
            qs = qs.filter(front__isnull=True)
        else:
            qs = qs.filter(front__name__icontains=frente_nome)

    if status:
        qs = qs.filter(status=status.lower())

    if tipo:
        qs = qs.filter(tipo_solicitacao__icontains=tipo)

    if credor_nome:
        qs = qs.filter(nome_credor__icontains=credor_nome)

    if solicitante_nome:
        usuarios = User.objects.filter(
            Q(first_name__icontains=solicitante_nome)
            | Q(last_name__icontains=solicitante_nome)
            | Q(username__icontains=solicitante_nome),
        )
        qs = qs.filter(criado_por__in=usuarios)

    if aprovador_nome:
        usuarios_ap = User.objects.filter(
            Q(first_name__icontains=aprovador_nome)
            | Q(last_name__icontains=aprovador_nome)
            | Q(username__icontains=aprovador_nome),
        )
        obra_ids = WorkOrderPermission.objects.filter(
            usuario__in=usuarios_ap,
            tipo_permissao='aprovador',
            ativo=True,
        ).values_list('obra_id', flat=True)
        pedidos_aprovados = Approval.objects.filter(
            aprovado_por__in=usuarios_ap,
        ).values_list('work_order_id', flat=True)
        qs = qs.filter(
            Q(obra_id__in=obra_ids) | Q(id__in=pedidos_aprovados),
        )

    if ultimos_dias:
        desde_dt = timezone.now() - timedelta(days=ultimos_dias)
        qs = qs.filter(data_envio__gte=desde_dt)

    if atraso_minimo_dias:
        limite_dt = timezone.now() - timedelta(days=atraso_minimo_dias)
        qs = qs.filter(
            status__in=['pendente', 'reaprovacao'],
            data_envio__lte=limite_dt,
        )

    if prazo_vencido:
        candidatos = qs.filter(
            status__in=['pendente', 'reaprovacao'],
            prazo_estimado__isnull=False,
            data_envio__isnull=False,
        ).select_related('front')
        ids_vencidos = [
            w.id for w in candidatos
            if _pedido_prazo_vencido(w, hoje)
        ]
        qs = qs.filter(id__in=ids_vencidos)

    if ordem == 'antigos':
        qs = qs.order_by('data_envio')
    elif ordem == 'obra':
        qs = qs.order_by('obra__nome')

    total = qs.count()
    pedidos = []
    for w in qs.select_related('front')[:20]:
        dias = _dias_em_aberto_pedido(w, hoje)
        pedidos.append({
            'id': w.id,
            'codigo': w.codigo,
            'tipo': w.tipo_solicitacao,
            'credor': w.nome_credor,
            'status': w.status,
            'obra': w.obra.nome if w.obra else '-',
            'frente': _nome_frente_workorder(w),
            'data_envio': (
                str(w.data_envio.date()) if w.data_envio else '-'
            ),
            'dias_em_aberto': dias,
            'prazo_vencido': _pedido_prazo_vencido(w, hoje),
            'criado_por': (
                w.criado_por.get_full_name()
                if w.criado_por else '-'
            ),
        })

    return json.dumps({
        'total': total,
        'pedidos': pedidos,
    }, ensure_ascii=False)


def consultar_status_pedido(
    codigo=None, pedido_id=None, usuario_wa=None,
) -> str:
    from gestao_aprovacao.models import Approval, WorkOrder

    qs = WorkOrder.objects.select_related('obra')
    if pedido_id:
        qs = qs.filter(id=pedido_id)
    elif codigo:
        qs = qs.filter(codigo__icontains=codigo)
    else:
        return json.dumps(
            {'erro': 'Informe o código ou ID do pedido.'},
            ensure_ascii=False,
        )

    workorder = qs.first()
    if not workorder:
        return json.dumps(
            {'erro': f'Pedido "{codigo or pedido_id}" não encontrado.'},
            ensure_ascii=False,
        )

    aprovacoes = []
    for ap in Approval.objects.filter(
        work_order=workorder,
    ).select_related('aprovado_por').order_by('created_at'):
        aprovacoes.append({
            'aprovador': (
                ap.aprovado_por.get_full_name()
                if ap.aprovado_por else '-'
            ),
            'decisao': ap.decisao,
            'data': (
                str(ap.created_at.date()) if ap.created_at else '-'
            ),
            'comentario': ap.comentario or '',
        })

    return json.dumps({
        'id': workorder.id,
        'codigo': workorder.codigo,
        'tipo': workorder.tipo_solicitacao,
        'credor': workorder.nome_credor,
        'status': workorder.status,
        'obra': workorder.obra.nome if workorder.obra else '-',
        'data_envio': (
            str(workorder.data_envio.date())
            if workorder.data_envio else '-'
        ),
        'data_aprovacao': (
            str(workorder.data_aprovacao.date())
            if workorder.data_aprovacao else '-'
        ),
        'criado_por': (
            workorder.criado_por.get_full_name()
            if workorder.criado_por else '-'
        ),
        'historico_aprovacoes': aprovacoes,
    }, ensure_ascii=False)


def consultar_desempenho_equipe_gest(
    obra_nome=None, tipo=None, usuario_wa=None,
) -> str:
    from gestao_aprovacao.models import Approval, WorkOrder, WorkOrderPermission

    hoje = timezone.localdate()
    inicio_mes = hoje.replace(day=1)

    obra_g = None
    if obra_nome:
        project = _resolver_project(
            obra_nome=obra_nome, usuario_wa=usuario_wa,
        )
        obra_g = _obra_gestao_por_project(project)

    project_ids = _project_ids_escopo(usuario_wa)

    aprovadores = []
    if not tipo or tipo == 'aprovadores':
        perm_qs = WorkOrderPermission.objects.filter(
            tipo_permissao='aprovador',
            ativo=True,
            obra__project_id__in=project_ids,
        ).select_related('usuario', 'obra')
        if obra_g:
            perm_qs = perm_qs.filter(obra=obra_g)

        obras_por_aprovador = {}
        nomes = {}
        for perm in perm_qs:
            uid = perm.usuario_id
            nomes[uid] = perm.usuario.get_full_name() or perm.usuario.username
            obras_por_aprovador.setdefault(uid, set()).add(perm.obra_id)

        qs_pendentes = _queryset_workorders_escopo(usuario_wa).filter(
            status__in=['pendente', 'reaprovacao'],
        )
        if obra_g:
            qs_pendentes = qs_pendentes.filter(obra=obra_g)

        pendentes_por_user = dict.fromkeys(obras_por_aprovador, 0)
        for w in qs_pendentes.values('obra_id'):
            obra_id = w['obra_id']
            for uid, obras in obras_por_aprovador.items():
                if obra_id in obras:
                    pendentes_por_user[uid] += 1

        qs_aprovados = Approval.objects.filter(
            decisao='aprovado',
            work_order__obra__project_id__in=project_ids,
        ).select_related('aprovado_por', 'work_order')
        if obra_g:
            qs_aprovados = qs_aprovados.filter(work_order__obra=obra_g)

        tempos_por_user = {}
        aprovados_mes_por_user = {}
        for ap in qs_aprovados:
            uid = ap.aprovado_por_id
            if not uid:
                continue
            wo = ap.work_order
            if wo.data_envio:
                dias = max(
                    0,
                    (ap.created_at.date() - wo.data_envio.date()).days,
                )
                tempos_por_user.setdefault(uid, []).append(dias)
            if ap.created_at.date() >= inicio_mes:
                aprovados_mes_por_user[uid] = (
                    aprovados_mes_por_user.get(uid, 0) + 1
                )

        for uid in obras_por_aprovador:
            tempos = tempos_por_user.get(uid, [])
            aprovadores.append({
                'aprovador': nomes.get(uid, 'Desconhecido'),
                'pedidos_pendentes_agora': pendentes_por_user.get(uid, 0),
                'tempo_medio_aprovacao_dias': (
                    round(sum(tempos) / len(tempos), 1) if tempos else None
                ),
                'pedidos_aprovados_mes_atual': aprovados_mes_por_user.get(uid, 0),
            })

        aprovadores.sort(
            key=lambda x: (-x['pedidos_pendentes_agora'], x['aprovador']),
        )

    solicitantes = []
    if not tipo or tipo == 'solicitantes':
        qs_sol = WorkOrder.objects.filter(criado_por__isnull=False)
        if obra_g:
            qs_sol = qs_sol.filter(obra=obra_g)
        sol_count = (
            qs_sol.values(
                'criado_por__first_name',
                'criado_por__last_name',
                'criado_por__id',
            )
            .annotate(total=Count('id'))
            .order_by('-total')[:10]
        )
        for s in sol_count:
            nome = (
                f"{s['criado_por__first_name'] or ''} "
                f"{s['criado_por__last_name'] or ''}".strip()
                or 'Desconhecido'
            )
            solicitantes.append({
                'nome': nome,
                'total_pedidos': s['total'],
            })

    return json.dumps({
        'aprovadores': aprovadores,
        'solicitantes': solicitantes,
    }, ensure_ascii=False)


def buscar_pdf_pedido(
    codigo=None, pedido_id=None, usuario_wa=None,
) -> str:
    from gestao_aprovacao.models import WorkOrder

    qs = WorkOrder.objects.select_related('obra')
    if pedido_id:
        qs = qs.filter(id=pedido_id)
    elif codigo:
        qs = qs.filter(codigo__icontains=codigo)
    else:
        return json.dumps(
            {'erro': 'Informe o código ou ID do pedido.'},
            ensure_ascii=False,
        )

    workorder = qs.first()
    if not workorder:
        return json.dumps(
            {'erro': f'Pedido "{codigo or pedido_id}" não encontrado.'},
            ensure_ascii=False,
        )

    return json.dumps({
        'acao': 'enviar_pdf_pedido',
        'pedido_id': workorder.id,
        'codigo': workorder.codigo,
        'obra': workorder.obra.nome if workorder.obra else '-',
        'status': workorder.status,
    }, ensure_ascii=False)


def consultar_pedidos_reprovados(
    obra_nome=None, ultimos_dias=None, usuario_wa=None,
) -> str:
    from gestao_aprovacao.models import Approval

    qs = _queryset_workorders_escopo(usuario_wa).filter(
        status='reprovado',
    ).select_related('obra', 'criado_por', 'front').order_by('-data_envio')

    if obra_nome:
        project = _resolver_project(
            obra_nome=obra_nome, usuario_wa=usuario_wa,
        )
        obra_g = _obra_gestao_por_project(project)
        if obra_g:
            qs = qs.filter(obra=obra_g)

    if ultimos_dias:
        desde_dt = timezone.now() - timedelta(days=ultimos_dias)
        qs = qs.filter(data_envio__gte=desde_dt)

    pedidos = []
    for w in qs[:20]:
        motivo = '-'
        ultima_ap = Approval.objects.filter(
            work_order=w, decisao='reprovado',
        ).order_by('-created_at').first()
        if ultima_ap:
            motivo = ultima_ap.comentario or '-'

        pedidos.append({
            'id': w.id,
            'codigo': w.codigo,
            'tipo': w.tipo_solicitacao,
            'credor': w.nome_credor,
            'obra': w.obra.nome if w.obra else '-',
            'frente': _nome_frente_workorder(w),
            'data_envio': (
                str(w.data_envio.date()) if w.data_envio else '-'
            ),
            'motivo_reprovacao': motivo,
            'solicitante': (
                w.criado_por.get_full_name()
                if w.criado_por else '-'
            ),
        })

    return json.dumps({
        'total': qs.count(),
        'pedidos': pedidos,
    }, ensure_ascii=False)


def _filtrar_itens_insumo(qs, termo: str):
    return qs.filter(
        Q(insumo__descricao__icontains=termo)
        | Q(insumo__codigo_sienge__icontains=termo),
    )


def localizar_insumo(
    insumo_nome, obra_nome=None, obra_id=None,
    usuario_wa=None,
) -> str:
    from django.db.models import Sum

    from suprimentos.models import ItemMapa

    qs = ItemMapa.objects.select_related(
        'insumo', 'obra', 'local_aplicacao',
    )
    qs = _filtrar_itens_insumo(qs, insumo_nome)

    if obra_nome or obra_id:
        obra = _resolver_obra_mapa(
            obra_nome=obra_nome, obra_id=obra_id,
            usuario_wa=usuario_wa,
        )
        if obra:
            qs = qs.filter(obra=obra)
        else:
            return json.dumps(
                {'erro': 'Obra não encontrada.'},
                ensure_ascii=False,
            )
    else:
        qs = qs.filter(obra__in=_get_escopo_obras(usuario_wa))

    if not qs.exists():
        qs = ItemMapa.objects.select_related(
            'insumo', 'obra', 'local_aplicacao',
        ).filter(obra__in=_get_escopo_obras(usuario_wa))
        qs = _filtrar_itens_insumo(qs, insumo_nome)
        if obra_nome or obra_id:
            obra = _resolver_obra_mapa(
                obra_nome=obra_nome, obra_id=obra_id,
                usuario_wa=usuario_wa,
            )
            if obra:
                qs = qs.filter(obra=obra)

    resultados = []
    for item in qs[:15]:
        total_alocado = (
            item.alocacoes.aggregate(
                total=Sum('quantidade_alocada'),
            )['total'] or 0
        )
        resultados.append({
            'insumo': item.insumo.descricao if item.insumo else '-',
            'codigo': (
                item.insumo.codigo_sienge if item.insumo else '-'
            ),
            'obra': item.obra.nome if item.obra else '-',
            'local': (
                item.local_aplicacao.nome
                if item.local_aplicacao else '-'
            ),
            'qtd_planejada': float(item.quantidade_planejada or 0),
            'qtd_alocada': float(total_alocado),
            'numero_sc': item.numero_sc or '-',
            'numero_pc': item.numero_pc or '-',
            'status_etapa': item.status_etapa or '-',
            'status_css': item.status_css or '-',
        })

    return json.dumps({
        'total_encontrados': len(resultados),
        'insumo_buscado': insumo_nome,
        'itens': resultados,
    }, ensure_ascii=False)


def consultar_suprimentos_por_local(
    obra_nome=None, local_nome=None,
    obra_id=None, usuario_wa=None,
) -> str:
    from mapa_obras.models import LocalObra
    from suprimentos.services.local_mapa_relatorio_service import (
        LocalMapaRelatorioService,
        find_local_obra,
    )

    obra = _resolver_obra_mapa(
        obra_nome=obra_nome, obra_id=obra_id,
        usuario_wa=usuario_wa,
    )
    if not obra:
        return json.dumps(
            {'erro': 'Obra não encontrada.'},
            ensure_ascii=False,
        )

    service = LocalMapaRelatorioService(obra)
    local = None
    if local_nome:
        local = find_local_obra(obra, texto_usuario=local_nome)
        if not local:
            local = LocalObra.objects.filter(
                obra=obra, nome__icontains=local_nome,
            ).first()

    try:
        if local:
            payload = service.build_facts_for_local(local)
        else:
            snapshots = service.build_snapshots_por_local()
            payload = {
                'total_locais': len(snapshots),
                'locais': [
                    {
                        'nome': s.nome,
                        'tipo': s.tipo,
                        'total': s.total,
                        'pendentes': s.pendentes,
                        'entregues': s.entregues,
                        'sem_solicitacao_compra': s.sem_sc,
                        'sem_pedido_compra': s.sem_pc,
                        'atrasados': s.atrasados,
                        'saude_score': s.saude_score,
                    }
                    for s in snapshots.values()
                ],
            }
        return json.dumps({
            'obra': obra.nome,
            'local': local.nome if local else (local_nome or 'todos'),
            'resumo': payload,
        }, ensure_ascii=False, default=str)
    except Exception as e:
        return json.dumps({'erro': str(e)}, ensure_ascii=False)


def consultar_mapa_controle_completo(
    obra_nome=None, obra_id=None,
    detalhar_blocos=True, usuario_wa=None,
) -> str:
    from painel_operacional.models import (
        AmbienteOperacional,
        AmbienteTipo,
        AmbienteVersao,
    )
    from suprimentos.services.analise_obra_service import AnaliseObraService

    obra = _resolver_obra_mapa(
        obra_nome=obra_nome, obra_id=obra_id,
        usuario_wa=usuario_wa,
    )
    if not obra:
        return json.dumps(
            {'erro': 'Obra não encontrada.'},
            ensure_ascii=False,
        )

    ambientes = AmbienteOperacional.objects.filter(
        obra=obra,
        tipo=AmbienteTipo.MAPA_CONTROLE,
    ).order_by('-updated_at')

    if not ambientes.exists():
        return json.dumps({
            'obra': obra.nome,
            'erro': 'Nenhum mapa de controle encontrado.',
        }, ensure_ascii=False)

    resultado_ambientes = []
    for amb in ambientes:
        versao = AmbienteVersao.objects.filter(
            ambiente=amb,
        ).order_by('-numero').first()
        kpis_amb = _kpis_ambiente_controle(obra, amb)

        resultado_ambientes.append({
            'id': amb.id,
            'nome': amb.nome,
            'ativo': amb.ativo,
            'ultima_atualizacao': (
                str(amb.updated_at.date()) if amb.updated_at else '-'
            ),
            'percentual_conclusao': kpis_amb['percentual_conclusao'],
            'quantidade_unidades': kpis_amb['total_unidades'],
            'versao': versao.numero if versao else '-',
            'versao_estado': versao.estado if versao else '-',
        })

    controle_kpis = {}
    progresso_blocos = []
    try:
        service = AnaliseObraService(obra)
        secao = service.build_section('controle')
        controle_kpis = secao or {}
        if detalhar_blocos and secao:
            controle = secao.get('controle', {})
            kpis = controle.get('kpis', {}) if isinstance(controle, dict) else {}
            progresso_blocos = kpis.get('progresso_blocos', [])
    except Exception:
        pass

    return json.dumps({
        'obra': obra.nome,
        'ambientes': resultado_ambientes,
        'ambiente_mais_recente': (
            resultado_ambientes[0] if resultado_ambientes else None
        ),
        'kpis_controle': controle_kpis,
        'progresso_blocos': progresso_blocos if detalhar_blocos else [],
    }, ensure_ascii=False, default=str)


def consultar_bi_obra(
    obra_nome=None, obra_id=None, usuario_wa=None,
) -> str:
    from suprimentos.services.analise_obra_service import AnaliseObraService

    obra = _resolver_obra_mapa(
        obra_nome=obra_nome, obra_id=obra_id,
        usuario_wa=usuario_wa,
    )
    if not obra:
        return json.dumps(
            {'erro': 'Obra não encontrada.'},
            ensure_ascii=False,
        )

    try:
        service = AnaliseObraService(obra)
        payload = service.build_payload()
        bi = {
            chave: payload.get(chave)
            for chave in (
                'meta', 'controle', 'suprimentos', 'diario',
                'gestcontroll', 'restricoes', 'trackhub', 'cruzamento',
            )
        }
        return json.dumps({
            'obra': obra.nome,
            'bi': bi,
        }, ensure_ascii=False, default=str)
    except Exception as e:
        return json.dumps({'erro': str(e)}, ensure_ascii=False)


def consultar_restricoes_por_responsavel(
    responsavel_nome=None, obra_nome=None,
    incluir_concluidas=False, usuario_wa=None,
) -> str:
    from django.contrib.auth import get_user_model

    from gestao_aprovacao.models import Obra as ObraGestao
    from impedimentos.models import Impedimento, StatusImpedimento

    User = get_user_model()
    escopo_ids = list(_get_escopo_obras(usuario_wa).values_list('id', flat=True))
    obras_gestao_qs = ObraGestao.objects.filter(
        ativo=True,
        project__obra_mapa__id__in=escopo_ids,
    )
    if obra_nome:
        obra = _resolver_obra_gestao(obra_nome=obra_nome, usuario_wa=usuario_wa)
        if not obra:
            return json.dumps(
                {'erro': 'Obra não encontrada.'},
                ensure_ascii=False,
            )
        obras_gestao_qs = obras_gestao_qs.filter(id=obra.id)

    obras_gestao_ids = list(obras_gestao_qs.values_list('id', flat=True))
    status_final_por_obra = {}
    for obra_id in obras_gestao_ids:
        sf = StatusImpedimento.objects.filter(
            obra_id=obra_id,
        ).order_by('-ordem').first()
        if sf:
            status_final_por_obra[obra_id] = sf.id

    usuarios_filtro = None
    usuario_ids_filtro = None
    if responsavel_nome:
        usuarios_filtro = User.objects.filter(
            Q(first_name__icontains=responsavel_nome)
            | Q(last_name__icontains=responsavel_nome)
            | Q(username__icontains=responsavel_nome),
        )
        if not usuarios_filtro.exists():
            return json.dumps({
                'erro': f'Responsável "{responsavel_nome}" não encontrado.',
            }, ensure_ascii=False)
        usuario_ids_filtro = set(usuarios_filtro.values_list('id', flat=True))

    qs = Impedimento.objects.filter(
        parent__isnull=True,
        obra_id__in=obras_gestao_ids,
    ).prefetch_related('responsaveis')
    if usuarios_filtro is not None:
        qs = qs.filter(responsaveis__in=usuarios_filtro).distinct()

    hoje = timezone.localdate()
    por_responsavel = {}
    for imp in qs:
        if not incluir_concluidas:
            final_id = status_final_por_obra.get(imp.obra_id)
            if final_id and imp.status_id == final_id:
                continue

        responsaveis = list(imp.responsaveis.all())
        if not responsaveis:
            continue

        vencida = imp.prazo is not None and imp.prazo < hoje
        dias_atraso = (hoje - imp.prazo).days if vencida else None

        for user in responsaveis:
            if usuario_ids_filtro is not None and user.id not in usuario_ids_filtro:
                continue
            uid = user.id
            if uid not in por_responsavel:
                por_responsavel[uid] = {
                    'responsavel': user.get_full_name() or user.username,
                    'restricoes_abertas': 0,
                    'vencidas': 0,
                    '_soma_dias_atraso': 0,
                    '_count_vencidas': 0,
                }
            por_responsavel[uid]['restricoes_abertas'] += 1
            if vencida:
                por_responsavel[uid]['vencidas'] += 1
                por_responsavel[uid]['_soma_dias_atraso'] += dias_atraso
                por_responsavel[uid]['_count_vencidas'] += 1

    resultado = []
    for stats in por_responsavel.values():
        count_v = stats.pop('_count_vencidas', 0)
        soma = stats.pop('_soma_dias_atraso', 0)
        stats['dias_medio_atraso'] = (
            round(soma / count_v, 1) if count_v else 0
        )
        resultado.append(stats)

    resultado.sort(
        key=lambda x: (-x['restricoes_abertas'], x['responsavel']),
    )

    payload = {
        'total_responsaveis': len(resultado),
        'responsaveis': resultado[:30],
    }
    if responsavel_nome:
        payload['filtro_responsavel'] = responsavel_nome
    if obra_nome:
        payload['filtro_obra'] = obra_nome

    return json.dumps(payload, ensure_ascii=False)


def consultar_pendencias_por_responsavel(
    responsavel_nome, obra_nome=None,
    incluir_concluidas=False, usuario_wa=None,
) -> str:
    from django.contrib.auth import get_user_model

    from trackhub.models import EtapaPendencia, Pendencia

    User = get_user_model()

    usuarios = User.objects.filter(
        Q(first_name__icontains=responsavel_nome)
        | Q(last_name__icontains=responsavel_nome)
        | Q(username__icontains=responsavel_nome),
    )

    if not usuarios.exists():
        return json.dumps({
            'erro': f'Responsável "{responsavel_nome}" não encontrado.',
        }, ensure_ascii=False)

    escopo_th = _get_escopo_trackhub(usuario_wa)
    hoje = timezone.localdate()

    qs_pendencia = Pendencia.objects.filter(
        responsavel_interno__in=usuarios,
        obra__in=escopo_th,
    ).select_related('obra', 'responsavel_interno')

    if not incluir_concluidas:
        qs_pendencia = qs_pendencia.exclude(
            status__in=['concluida', 'cancelada'],
        )

    if obra_nome:
        obra = escopo_th.filter(nome__icontains=obra_nome).first()
        if obra:
            qs_pendencia = qs_pendencia.filter(obra=obra)

    pendencias_como_dono = []
    for p in qs_pendencia.order_by('prazo')[:20]:
        vencida = p.prazo < hoje if p.prazo else False
        pendencias_como_dono.append({
            'id': p.id,
            'titulo': p.titulo,
            'tipo': p.tipo,
            'status': p.status,
            'obra': p.obra.nome if p.obra else '-',
            'prazo': str(p.prazo) if p.prazo else '-',
            'vencida': vencida,
            'dias_atraso': (hoje - p.prazo).days if vencida else None,
            'tipo_responsabilidade': 'dono da pendência',
        })

    qs_etapa = EtapaPendencia.objects.filter(
        responsavel_interno__in=usuarios,
        pendencia__obra__in=escopo_th,
        status='pendente',
    ).exclude(
        pendencia__status__in=['concluida', 'cancelada'],
    ).select_related(
        'pendencia', 'pendencia__obra', 'responsavel_interno',
    )

    if obra_nome:
        obra = escopo_th.filter(nome__icontains=obra_nome).first()
        if obra:
            qs_etapa = qs_etapa.filter(pendencia__obra=obra)

    pendencias_como_responsavel_etapa = []
    for et in qs_etapa.order_by('prazo')[:20]:
        vencida = et.prazo < hoje if et.prazo else False
        pendencias_como_responsavel_etapa.append({
            'pendencia_id': et.pendencia_id,
            'pendencia_titulo': et.pendencia.titulo,
            'etapa': et.titulo,
            'obra': (
                et.pendencia.obra.nome
                if et.pendencia and et.pendencia.obra else '-'
            ),
            'prazo': str(et.prazo) if et.prazo else '-',
            'vencida': vencida,
            'dias_atraso': (hoje - et.prazo).days if vencida else None,
            'tipo_responsabilidade': 'responsável de etapa',
        })

    return json.dumps({
        'responsavel': responsavel_nome,
        'total_como_dono': qs_pendencia.count(),
        'total_como_responsavel_etapa': qs_etapa.count(),
        'pendencias_como_dono': pendencias_como_dono,
        'pendencias_como_responsavel_etapa': pendencias_como_responsavel_etapa,
    }, ensure_ascii=False)


def consultar_etapas_pendencia(
    pendencia_id=None, pendencia_titulo=None,
    obra_nome=None, usuario_wa=None,
) -> str:
    from trackhub.models import EtapaPendencia, Pendencia

    if pendencia_id:
        try:
            pendencia = Pendencia.objects.select_related(
                'obra',
            ).get(id=pendencia_id)
        except Pendencia.DoesNotExist:
            return json.dumps(
                {'erro': 'Pendência não encontrada.'},
                ensure_ascii=False,
            )
    elif pendencia_titulo:
        qs = Pendencia.objects.filter(
            titulo__icontains=pendencia_titulo,
        ).select_related('obra')
        if obra_nome:
            obra = _resolver_obra_mapa(
                obra_nome=obra_nome, usuario_wa=usuario_wa,
            )
            if obra:
                qs = qs.filter(obra=obra)
        pendencia = qs.first()
        if not pendencia:
            return json.dumps(
                {'erro': 'Pendência não encontrada.'},
                ensure_ascii=False,
            )
    else:
        return json.dumps(
            {'erro': 'Informe o ID ou título da pendência.'},
            ensure_ascii=False,
        )

    etapas = []
    hoje = timezone.localdate()
    for et in EtapaPendencia.objects.filter(
        pendencia=pendencia,
    ).select_related('responsavel_interno').order_by('ordem'):
        concluida = et.status == 'concluida'
        prazo = et.prazo
        etapas.append({
            'ordem': et.ordem,
            'titulo': et.titulo,
            'concluida': concluida,
            'status': et.status,
            'responsavel': (
                et.responsavel_interno.get_full_name()
                if et.responsavel_interno else '-'
            ),
            'prazo': str(prazo) if prazo else '-',
            'vencida': (
                prazo < hoje and not concluida if prazo else False
            ),
        })

    total = len(etapas)
    concluidas = sum(1 for e in etapas if e['concluida'])

    return json.dumps({
        'pendencia': pendencia.titulo,
        'obra': pendencia.obra.nome if pendencia.obra else '-',
        'status': pendencia.status,
        'total_etapas': total,
        'concluidas': concluidas,
        'pendentes': total - concluidas,
        'etapas': etapas,
    }, ensure_ascii=False)


_LIMITE_LISTA = 30

_ERRO_SEM_PERMISSAO = json.dumps({'erro': 'sem permissão'}, ensure_ascii=False)

_CAMPOS_SENSIVEIS_RH = frozenset({
    'cpf', 'rg', 'pis', 'salario', 'dados_bancarios', 'endereco',
    'data_nascimento', 'token_portal', 'email', 'telefone', 'arquivo',
    'pdf_contrato',
})


def _tem_permissao_modulo(usuario_wa, campo: str) -> bool:
    from whatsapp_ia.models import IaPermissaoConsulta

    if not usuario_wa:
        return False
    try:
        permissao = IaPermissaoConsulta.objects.get(usuario=usuario_wa)
        return bool(getattr(permissao, campo, False))
    except IaPermissaoConsulta.DoesNotExist:
        return False


def _pode_consultar_mapa_geo(usuario_wa) -> bool:
    return _tem_permissao_modulo(usuario_wa, 'pode_consultar_mapa_geo')


def _pode_consultar_rh(usuario_wa) -> bool:
    return _tem_permissao_modulo(usuario_wa, 'pode_consultar_rh')


def _resolver_project_mapa_geo(obra_nome=None, obra_id=None, usuario_wa=None):
    if not _pode_consultar_mapa_geo(usuario_wa):
        return None, _ERRO_SEM_PERMISSAO
    project = _resolver_project(
        obra_nome=obra_nome,
        obra_id=obra_id,
        usuario_wa=usuario_wa,
    )
    if not project:
        return None, json.dumps(
            {'erro': 'Obra não encontrada.'},
            ensure_ascii=False,
        )
    return project, None


def _serializar_colaborador_resumo(colab) -> dict:
    return {
        'id': colab.pk,
        'nome': colab.nome,
        'cargo': colab.cargo,
        'status': colab.status,
        'etapa_admissao': colab.etapa_admissao,
        'obras': list(colab.obras.values_list('nome', flat=True)[:5]),
    }


def consultar_resumo_mapa_obra(
    obra_nome=None, obra_id=None, usuario_wa=None,
) -> str:
    project, erro = _resolver_project_mapa_geo(
        obra_nome=obra_nome, obra_id=obra_id, usuario_wa=usuario_wa,
    )
    if erro:
        return erro

    from mapa_geo.services import get_map_summary

    summary = get_map_summary(project)
    return json.dumps({
        'obra': project.name,
        'total_elementos': summary['total'],
        'pontos': summary['points'],
        'linhas': summary['segments'],
        'areas': summary['areas'],
        'progresso_geral_pct': summary['overall_progress_pct'],
        'marcadores_gps': summary['gps_markers'],
        'rdos_com_gps': summary['diaries_with_gps'],
        'ultima_data_diario': summary['last_diary_date'],
        '_meta': _meta_ia(
            project_id=project.id,
            vinculos_eap=summary['eap_linked'],
            fonte_importacao=summary['import_label'],
        ),
    }, ensure_ascii=False)


def listar_elementos_mapa_obra(
    obra_nome=None, obra_id=None, folder=None, kind=None,
    status=None, usuario_wa=None,
) -> str:
    project, erro = _resolver_project_mapa_geo(
        obra_nome=obra_nome, obra_id=obra_id, usuario_wa=usuario_wa,
    )
    if erro:
        return erro

    from mapa_geo.models import GeoFeature
    from mapa_geo.services import _features_queryset_for_project

    qs = _features_queryset_for_project(project)
    if folder:
        qs = qs.filter(folder__icontains=folder)
    if kind:
        qs = qs.filter(kind=kind)
    if status:
        qs = qs.filter(status=status)

    total = qs.count()
    elementos = []
    for feat in qs.order_by('sort_order', 'name')[:_LIMITE_LISTA]:
        elementos.append({
            'nome': feat.name or f'#{feat.pk}',
            'pasta': feat.folder,
            'tipo_geometria': feat.geometry_type,
            'kind': feat.kind,
            'status': feat.status,
            'progresso_pct': float(feat.progress_pct),
        })

    return json.dumps({
        'obra': project.name,
        'total': total,
        'elementos': elementos,
    }, ensure_ascii=False)


def listar_pastas_mapa_obra(
    obra_nome=None, obra_id=None, usuario_wa=None,
) -> str:
    project, erro = _resolver_project_mapa_geo(
        obra_nome=obra_nome, obra_id=obra_id, usuario_wa=usuario_wa,
    )
    if erro:
        return erro

    from mapa_geo.enrichment import list_feature_folders

    pastas = list_feature_folders(project)[:_LIMITE_LISTA]
    return json.dumps({
        'obra': project.name,
        'total': len(pastas),
        'pastas': pastas,
    }, ensure_ascii=False)


def consultar_alertas_mapa_obra(
    obra_nome=None, obra_id=None, usuario_wa=None,
) -> str:
    project, erro = _resolver_project_mapa_geo(
        obra_nome=obra_nome, obra_id=obra_id, usuario_wa=usuario_wa,
    )
    if erro:
        return erro

    from mapa_geo.enrichment import get_map_alerts

    dados = get_map_alerts(project)
    items = dados.get('items', [])[:_LIMITE_LISTA]
    por_tipo = {}
    for item in items:
        tipo = item.get('type', 'outro')
        por_tipo[tipo] = por_tipo.get(tipo, 0) + 1

    return json.dumps({
        'obra': project.name,
        'total': dados.get('count', len(items)),
        'por_tipo': por_tipo,
        'alertas': [
            {
                'tipo': i.get('type'),
                'severidade': i.get('severity'),
                'nome': i.get('name'),
                'mensagem': i.get('message'),
            }
            for i in items
        ],
    }, ensure_ascii=False)


def consultar_elementos_bloqueados_mapa(
    obra_nome=None, obra_id=None, usuario_wa=None,
) -> str:
    project, erro = _resolver_project_mapa_geo(
        obra_nome=obra_nome, obra_id=obra_id, usuario_wa=usuario_wa,
    )
    if erro:
        return erro

    from django.db.models import Q

    from mapa_geo.models import GeoFeature
    from mapa_geo.services import _features_queryset_for_project

    qs = _features_queryset_for_project(project).filter(
        Q(status='blocked') | Q(kind='obstacle'),
    )
    total = qs.count()
    elementos = [
        {
            'nome': f.name or f'#{f.pk}',
            'pasta': f.folder,
            'kind': f.kind,
            'status': f.status,
            'progresso_pct': float(f.progress_pct),
        }
        for f in qs.order_by('sort_order', 'name')[:_LIMITE_LISTA]
    ]

    return json.dumps({
        'obra': project.name,
        'total': total,
        'elementos': elementos,
    }, ensure_ascii=False)


def consultar_marcadores_gps_rdo(
    obra_nome=None, obra_id=None, usuario_wa=None,
) -> str:
    project, erro = _resolver_project_mapa_geo(
        obra_nome=obra_nome, obra_id=obra_id, usuario_wa=usuario_wa,
    )
    if erro:
        return erro

    from mapa_geo.models import GeoFeature
    from mapa_geo.services import _features_queryset_for_project

    qs = _features_queryset_for_project(project).filter(
        diary__isnull=False,
    ).select_related('diary')
    total = qs.count()
    marcadores = []
    for feat in qs.order_by('-diary__date')[:_LIMITE_LISTA]:
        diary = feat.diary
        marcadores.append({
            'nome': feat.name or f'#{feat.pk}',
            'pasta': feat.folder,
            'rdo_numero': getattr(diary, 'report_number', None) or diary.pk,
            'data': str(diary.date) if diary else None,
        })

    return json.dumps({
        'obra': project.name,
        'total': total,
        'marcadores': marcadores,
    }, ensure_ascii=False)


def comparar_progresso_mapa_datas(
    obra_nome=None, obra_id=None, data_inicio=None, data_fim=None,
    usuario_wa=None,
) -> str:
    project, erro = _resolver_project_mapa_geo(
        obra_nome=obra_nome, obra_id=obra_id, usuario_wa=usuario_wa,
    )
    if erro:
        return erro

    if not data_inicio or not data_fim:
        return json.dumps(
            {'erro': 'Informe data_inicio e data_fim (YYYY-MM-DD).'},
            ensure_ascii=False,
        )

    d_inicio = _data_ou_hoje(data_inicio)
    d_fim = _data_ou_hoje(data_fim)

    from mapa_geo.enrichment import compare_features_at_dates

    resultado = compare_features_at_dates(project, d_inicio, d_fim)
    avancaram = []
    estagnados = []
    regrediram = []

    for feat in resultado.get('features', []):
        props = feat.get('properties', {})
        cmp = props.get('compare', {})
        delta = cmp.get('delta_progress', 0)
        change_type = cmp.get('change_type', 'same')
        item = {
            'nome': props.get('name') or f'#{props.get("id", "?")}',
            'progresso_inicio': cmp.get('progress_a'),
            'progresso_fim': cmp.get('progress_b'),
            'delta': delta,
        }
        if change_type == 'same' or (change_type == 'changed' and delta == 0):
            if len(estagnados) < _LIMITE_LISTA:
                estagnados.append(item)
        elif delta > 0:
            if len(avancaram) < _LIMITE_LISTA:
                avancaram.append(item)
        elif delta < 0:
            if len(regrediram) < _LIMITE_LISTA:
                regrediram.append(item)

    stats = resultado.get('meta', {}).get('stats', {})
    return json.dumps({
        'obra': project.name,
        'data_inicio': str(d_inicio),
        'data_fim': str(d_fim),
        'total_elementos': stats.get('same', 0) + stats.get('changed', 0)
            + stats.get('added', 0) + stats.get('removed', 0),
        'contagem_avancaram': len(avancaram),
        'contagem_estagnados': len(estagnados),
        'contagem_regrediram': len(regrediram),
        'avancaram': avancaram,
        'estagnados': estagnados,
        'regrediram': regrediram,
    }, ensure_ascii=False)


def _panorama_mapa_geografico_escopo(usuario_wa):
    """Resumo do mapa geográfico por obra para panorama geral."""
    if not _pode_consultar_mapa_geo(usuario_wa):
        return {'disponivel': False}

    from mapa_geo.services import get_map_summary

    project_ids = _project_ids_escopo(usuario_wa)
    projects = Project.objects.filter(
        is_active=True,
        id__in=project_ids,
    ).order_by('name')

    obras = []
    for project in projects[:_LIMITE_LISTA]:
        summary = get_map_summary(project)
        total = summary['total']
        item = {
            'obra': project.name,
            'tem_elementos': total > 0,
            'total_elementos': total,
            'pontos': summary['points'],
            'marcadores_gps_rdo': summary['gps_markers'],
            'tem_marcadores_gps': summary['gps_markers'] > 0,
        }
        if total == 0:
            item['descricao'] = 'sem dados geográficos cadastrados'
        obras.append(item)

    return {
        'disponivel': True,
        'total_obras': len(obras),
        'obras': obras,
    }


def panorama_mapas_obras(usuario_wa=None) -> str:
    if not _pode_consultar_mapa_geo(usuario_wa):
        return _ERRO_SEM_PERMISSAO

    from mapa_geo.models import GeoObraConfig
    from mapa_geo.services import get_map_summary

    project_ids = _project_ids_escopo(usuario_wa)
    projects = Project.objects.filter(
        is_active=True, id__in=project_ids,
    ).order_by('name')

    obras = []
    for project in projects[:_LIMITE_LISTA]:
        summary = get_map_summary(project)
        config = GeoObraConfig.objects.filter(project=project).first()
        obras.append({
            'project_id': project.id,
            'nome': project.name,
            'codigo': project.code,
            'total_elementos': summary['total'],
            'linhas': summary['segments'],
            'pontos': summary['points'],
            'areas': summary['areas'],
            'progresso_geral_pct': summary['overall_progress_pct'],
            'marcadores_gps': summary['gps_markers'],
            'ultima_data_diario': summary['last_diary_date'],
            'centro': (
                [float(config.center_latitude), float(config.center_longitude)]
                if config and config.center_latitude and config.center_longitude
                else None
            ),
        })

    return json.dumps({
        'total_obras': projects.count(),
        'obras': obras,
    }, ensure_ascii=False)


def consultar_resumo_rh(usuario_wa=None) -> str:
    if not _pode_consultar_rh(usuario_wa):
        return _ERRO_SEM_PERMISSAO

    from recursos_humanos.models import Colaborador
    from recursos_humanos.services.alerts import gerar_alertas, resumo_alertas

    alertas = gerar_alertas()
    resumo = resumo_alertas(alertas)
    criticos = sum(
        1 for a in alertas if a.urgencia in ('red', 'yellow')
    )

    return json.dumps({
        'colaboradores': {
            'ativos': Colaborador.objects.filter(
                status=Colaborador.Status.ATIVO,
            ).count(),
            'em_admissao': Colaborador.objects.filter(
                status=Colaborador.Status.EM_ADMISSAO,
            ).count(),
            'desligados': Colaborador.objects.filter(
                status=Colaborador.Status.DESLIGADO,
            ).count(),
        },
        'alertas': {
            'total': resumo['total'],
            'criticos': criticos,
            'vencendo': resumo['vencendo'],
            'vencidos': resumo['vencidos'],
            'admissoes': resumo['admissoes'],
            'contratos': resumo['contratos'],
        },
        'data': str(resumo['hoje']),
    }, ensure_ascii=False)


def consultar_colaboradores_ativos(
    obra_nome=None, cargo=None, usuario_wa=None,
) -> str:
    if not _pode_consultar_rh(usuario_wa):
        return _ERRO_SEM_PERMISSAO

    from recursos_humanos.models import Colaborador

    qs = Colaborador.objects.filter(
        status=Colaborador.Status.ATIVO,
    ).prefetch_related('obras')
    if obra_nome:
        qs = qs.filter(obras__nome__icontains=obra_nome)
    if cargo:
        qs = qs.filter(cargo__icontains=cargo)

    total = qs.distinct().count()
    colaboradores = [
        _serializar_colaborador_resumo(c)
        for c in qs.distinct().order_by('nome')[:_LIMITE_LISTA]
    ]

    return json.dumps({
        'total': total,
        'colaboradores': colaboradores,
    }, ensure_ascii=False)


def consultar_admissoes_em_andamento(usuario_wa=None) -> str:
    if not _pode_consultar_rh(usuario_wa):
        return _ERRO_SEM_PERMISSAO

    from recursos_humanos.models import Colaborador, DocumentoColaborador

    qs = Colaborador.objects.filter(
        status=Colaborador.Status.EM_ADMISSAO,
    ).order_by('etapa_admissao', 'nome')
    total = qs.count()
    admissoes = []
    for colab in qs[:_LIMITE_LISTA]:
        admissoes.append({
            'nome': colab.nome,
            'cargo': colab.cargo,
            'etapa_admissao': colab.etapa_admissao,
            'documentos_faltando': colab.documentos.filter(
                status=DocumentoColaborador.Status.FALTANDO,
            ).count(),
            'documentos_pendentes': colab.documentos.filter(
                status=DocumentoColaborador.Status.PENDENTE,
            ).count(),
            'gestor': colab.gestor_aprovador or None,
        })

    return json.dumps({
        'total': total,
        'admissoes': admissoes,
    }, ensure_ascii=False)


def consultar_documentos_vencendo(dias=None, usuario_wa=None) -> str:
    if not _pode_consultar_rh(usuario_wa):
        return _ERRO_SEM_PERMISSAO

    from datetime import timedelta

    from recursos_humanos.models import Colaborador, DocumentoColaborador
    from recursos_humanos.services.alertas_config import obter_configuracao_alertas

    config = obter_configuracao_alertas()
    janela = dias if dias is not None else config.dias_antecedencia_documentos
    hoje = timezone.localdate()
    limite = hoje + timedelta(days=janela)

    qs = DocumentoColaborador.objects.filter(
        tipo__tem_validade=True,
        vencimento__isnull=False,
        vencimento__gte=hoje,
        vencimento__lte=limite,
        colaborador__status__in=(
            Colaborador.Status.ATIVO,
            Colaborador.Status.EM_ADMISSAO,
        ),
    ).select_related('colaborador', 'tipo').order_by('vencimento')

    total = qs.count()
    documentos = []
    for doc in qs[:_LIMITE_LISTA]:
        documentos.append({
            'colaborador_nome': doc.colaborador.nome,
            'tipo_documento': doc.tipo.nome,
            'vencimento': str(doc.vencimento),
            'dias_restantes': (doc.vencimento - hoje).days,
            'status': doc.status,
        })

    return json.dumps({
        'dias_janela': janela,
        'total': total,
        'documentos': documentos,
    }, ensure_ascii=False)


def consultar_documentos_vencidos(usuario_wa=None) -> str:
    if not _pode_consultar_rh(usuario_wa):
        return _ERRO_SEM_PERMISSAO

    from recursos_humanos.models import Colaborador, DocumentoColaborador

    hoje = timezone.localdate()
    qs = DocumentoColaborador.objects.filter(
        tipo__tem_validade=True,
        vencimento__isnull=False,
        vencimento__lt=hoje,
    ).select_related('colaborador', 'tipo').order_by('vencimento')

    total = qs.count()
    documentos = []
    for doc in qs[:_LIMITE_LISTA]:
        documentos.append({
            'colaborador_nome': doc.colaborador.nome,
            'tipo_documento': doc.tipo.nome,
            'vencimento': str(doc.vencimento),
            'dias_atraso': (hoje - doc.vencimento).days,
            'status': doc.status,
            'colaborador_status': doc.colaborador.status,
        })

    return json.dumps({
        'total': total,
        'documentos': documentos,
    }, ensure_ascii=False)


def consultar_prazos_contrato_vencendo(usuario_wa=None) -> str:
    if not _pode_consultar_rh(usuario_wa):
        return _ERRO_SEM_PERMISSAO

    from recursos_humanos.services.alertas_config import obter_configuracao_alertas
    from recursos_humanos.services.prazo_contrato import prazos_vencendo

    config = obter_configuracao_alertas()
    prazos = prazos_vencendo(
        dias_antecedencia=config.dias_antecedencia_documentos,
    )
    total = prazos.count()
    itens = []
    for prazo in prazos[:_LIMITE_LISTA]:
        dias = prazo.dias_restantes()
        itens.append({
            'colaborador_nome': prazo.colaborador.nome,
            'tipo_contrato': prazo.get_tipo_display(),
            'data_fim': str(prazo.data_fim) if prazo.data_fim else None,
            'dias_restantes': dias,
            'status': prazo.status,
        })

    return json.dumps({
        'total': total,
        'prazos': itens,
    }, ensure_ascii=False)


def consultar_contratos_pendentes_assinatura(usuario_wa=None) -> str:
    if not _pode_consultar_rh(usuario_wa):
        return _ERRO_SEM_PERMISSAO

    from recursos_humanos.models import ContratoAdmissao

    qs = ContratoAdmissao.objects.filter(
        status=ContratoAdmissao.Status.PENDENTE,
    ).select_related('colaborador').order_by('-criado_em')

    total = qs.count()
    contratos = [
        {
            'colaborador_nome': c.colaborador.nome,
            'cargo': c.colaborador.cargo,
            'etapa_admissao': c.colaborador.etapa_admissao,
            'criado_em': str(c.criado_em.date()),
        }
        for c in qs[:_LIMITE_LISTA]
    ]

    return json.dumps({
        'total': total,
        'contratos': contratos,
    }, ensure_ascii=False)


def consultar_alertas_rh_criticos(usuario_wa=None) -> str:
    if not _pode_consultar_rh(usuario_wa):
        return _ERRO_SEM_PERMISSAO

    from recursos_humanos.services.alerts import gerar_alertas

    alertas = [
        a for a in gerar_alertas()
        if a.urgencia in ('red', 'yellow')
    ]
    ordem = {'red': 0, 'yellow': 1}
    alertas.sort(key=lambda a: (ordem.get(a.urgencia, 9), a.dias_restantes))

    itens = [
        {
            'colaborador_nome': a.colaborador_nome,
            'tipo': a.tipo,
            'detalhe': a.detalhe,
            'prazo': a.prazo,
            'dias_restantes': a.dias_restantes,
            'urgencia': a.urgencia,
        }
        for a in alertas[:20]
    ]

    return json.dumps({
        'total': len(alertas),
        'alertas': itens,
    }, ensure_ascii=False)


def _obras_sem_rdo_recente_escopo(
    projects,
    *,
    dias_analise=90,
    dias_sem_rdo_alerta=7,
    lacuna_minima_dias=7,
):
    """Obras cujo último RDO (qualquer status) está há mais de N dias."""
    obras = []
    for project in projects:
        metricas = _metricas_rdo_frequencia(
            project,
            front_id='todas',
            dias_analise=dias_analise,
            dias_sem_rdo_alerta=dias_sem_rdo_alerta,
            lacuna_minima_dias=lacuna_minima_dias,
        )
        meta = metricas.get('_meta', {})
        if not (meta.get('sem_rdo_recente') or meta.get('nunca_teve_rdo')):
            continue
        item = {
            'obra': project.name,
            'project_id': project.id,
            'ultimo_rdo_data': metricas.get('ultimo_rdo_data'),
            'dias_desde_ultimo': metricas.get('dias_desde_ultimo'),
        }
        if meta.get('nunca_teve_rdo'):
            item['nunca_teve_rdo'] = True
        obras.append(item)

    obras.sort(
        key=lambda x: (
            not x.get('nunca_teve_rdo'),
            -(x.get('dias_desde_ultimo') or 9999),
            x['obra'],
        ),
    )
    return obras


def consultar_frequencia_rdos(
    obra_nome=None,
    obra_id=None,
    dias_sem_rdo_alerta=None,
    dias_analise=None,
    lacuna_minima_dias=None,
    usuario_wa=None,
) -> str:
    dias_sem_rdo_alerta = 7 if dias_sem_rdo_alerta is None else dias_sem_rdo_alerta
    dias_analise = 90 if dias_analise is None else dias_analise
    lacuna_minima_dias = 7 if lacuna_minima_dias is None else lacuna_minima_dias

    project_ids = _project_ids_escopo(usuario_wa)
    if obra_id or obra_nome:
        project = _resolver_project(obra_nome, obra_id, usuario_wa)
        if not project:
            return json.dumps(
                {'erro': 'Obra não encontrada.'},
                ensure_ascii=False,
            )
        projects = [project]
    else:
        projects = list(
            Project.objects.filter(
                is_active=True,
                id__in=project_ids,
            ).order_by('name'),
        )

    resultado_obras = []
    for project in projects:
        frentes = _frentes_ativas_project(project)
        bloco = {
            'obra': project.name,
            'project_id': project.id,
            'tem_frentes_ativas': len(frentes) > 0,
            'segmentos': [],
        }

        if frentes:
            bloco['segmentos'].append({
                'frente': 'Obra inteira',
                'frente_id': None,
                **_metricas_rdo_frequencia(
                    project,
                    front_id='todas',
                    dias_analise=dias_analise,
                    dias_sem_rdo_alerta=dias_sem_rdo_alerta,
                    lacuna_minima_dias=lacuna_minima_dias,
                ),
                'situacao_periodo': _situacao_rdo_periodo(
                    project,
                    front_id='todas',
                    dias_analise=dias_analise,
                    dias_ag_critico=dias_sem_rdo_alerta,
                ),
            })
            for front in frentes:
                bloco['segmentos'].append({
                    'frente': front.name,
                    'frente_id': front.id,
                    **_metricas_rdo_frequencia(
                        project,
                        front_id=front.id,
                        dias_analise=dias_analise,
                        dias_sem_rdo_alerta=dias_sem_rdo_alerta,
                        lacuna_minima_dias=lacuna_minima_dias,
                    ),
                    'situacao_periodo': _situacao_rdo_periodo(
                        project,
                        front_id=front.id,
                        dias_analise=dias_analise,
                        dias_ag_critico=dias_sem_rdo_alerta,
                    ),
                })
        else:
            bloco['segmentos'].append({
                'frente': 'Obra',
                'frente_id': None,
                **_metricas_rdo_frequencia(
                    project,
                    front_id='todas',
                    dias_analise=dias_analise,
                    dias_sem_rdo_alerta=dias_sem_rdo_alerta,
                    lacuna_minima_dias=lacuna_minima_dias,
                ),
                'situacao_periodo': _situacao_rdo_periodo(
                    project,
                    front_id='todas',
                    dias_analise=dias_analise,
                    dias_ag_critico=dias_sem_rdo_alerta,
                ),
            })

        for seg in bloco['segmentos']:
            _anotar_alertas_rdo_segmento(
                seg,
                dias_sem_rdo_alerta=dias_sem_rdo_alerta,
            )

        resultado_obras.append(bloco)

    obras_sem_rdo_recente = _obras_sem_rdo_recente_escopo(
        projects,
        dias_analise=dias_analise,
        dias_sem_rdo_alerta=dias_sem_rdo_alerta,
        lacuna_minima_dias=lacuna_minima_dias,
    )

    return json.dumps({
        'total_obras': len(resultado_obras),
        'obras_sem_rdo_recente': {
            'limite_dias': dias_sem_rdo_alerta,
            'total': len(obras_sem_rdo_recente),
            'descricao': (
                'Obras com último RDO há mais de '
                f'{dias_sem_rdo_alerta} dias (independente do status)'
            ),
            'obras': obras_sem_rdo_recente,
        },
        'obras': resultado_obras,
    }, ensure_ascii=False)


def consultar_situacao_rdo_obra(
    obra_nome=None,
    obra_id=None,
    dias_analise=None,
    usuario_wa=None,
) -> str:
    dias_analise = 90 if dias_analise is None else dias_analise
    project = _resolver_project(obra_nome, obra_id, usuario_wa)
    if not project:
        return json.dumps(
            {'erro': 'Obra não encontrada.'},
            ensure_ascii=False,
        )

    frentes = _frentes_ativas_project(project)
    segmentos = []

    if frentes:
        configs = [('todas', 'Obra inteira')] + [
            (f.id, f.name) for f in frentes
        ]
        for front_id, nome in configs:
            freq = _metricas_rdo_frequencia(
                project, front_id=front_id, dias_analise=dias_analise,
            )
            sit = _situacao_rdo_periodo(
                project, front_id=front_id, dias_analise=dias_analise,
            )
            seg = {'frente': nome, 'frente_id': front_id, **freq, 'situacao': sit}
            _anotar_alertas_rdo_segmento(seg, dias_sem_rdo_alerta=7, situacao=sit)
            segmentos.append(seg)
    else:
        freq = _metricas_rdo_frequencia(
            project, front_id='todas', dias_analise=dias_analise,
        )
        sit = _situacao_rdo_periodo(
            project, front_id='todas', dias_analise=dias_analise,
        )
        seg = {'frente': 'Obra', **freq, 'situacao': sit}
        _anotar_alertas_rdo_segmento(seg, dias_sem_rdo_alerta=7, situacao=sit)
        segmentos.append(seg)

    return json.dumps({
        'obra': project.name,
        'segmentos': segmentos,
    }, ensure_ascii=False)


def consultar_situacao_geral_obras(usuario_wa=None) -> str:
    """
    Panorama consolidado: RDO + pedidos + restrições + suprimentos +
    mapa de controle + mapa geográfico + TrackHub (inclui Sede).
    """
    hoje = timezone.localdate()
    rdo = json.loads(consultar_frequencia_rdos(usuario_wa=usuario_wa))
    pedidos = json.loads(
        consultar_situacao_pedidos_obras(usuario_wa=usuario_wa),
    )
    restricoes = _restricoes_por_obra_escopo(usuario_wa)
    suprimentos = json.loads(consultar_panorama_suprimentos(usuario_wa=usuario_wa))
    mapa = json.loads(consultar_panorama_mapa_controle(usuario_wa=usuario_wa))
    mapa_geo = _panorama_mapa_geografico_escopo(usuario_wa)

    obras_th = list(_get_escopo_trackhub(usuario_wa).order_by('nome'))
    trackhub_obras = []
    total_abertas_th = 0
    total_vencidas_th = 0
    for obra in obras_th:
        item = _agregar_pendencias_obra(obra, hoje)
        trackhub_obras.append(item)
        total_abertas_th += item['total_abertas']
        total_vencidas_th += item['vencidas']
    trackhub_obras.sort(
        key=lambda x: (-x['vencidas'], -x['total_abertas'], x['obra']),
    )

    obras_escopo = list(
        _get_escopo_obras(usuario_wa).order_by('nome').values_list('nome', flat=True),
    )
    com_alerta = _obras_com_alerta_panorama(
        rdo,
        pedidos,
        restricoes,
        suprimentos,
        mapa,
        trackhub_obras,
        obras_escopo,
    )
    obras_sem_alertas = [n for n in obras_escopo if n not in com_alerta]
    todas_obras_com_alerta = bool(obras_escopo) and not obras_sem_alertas

    resumo_obras_ok = {
        'total_obras_escopo': len(obras_escopo),
        'obras_sem_alertas': obras_sem_alertas,
        'total_sem_alertas': len(obras_sem_alertas),
        'todas_obras_com_alerta': todas_obras_com_alerta,
    }
    if todas_obras_com_alerta:
        resumo_obras_ok['mensagem'] = (
            'Todas as obras apresentam pelo menos um alerta em algum módulo'
        )
    elif obras_sem_alertas:
        resumo_obras_ok['mensagem'] = (
            f'{len(obras_sem_alertas)} obra(s) sem alerta em nenhum módulo: '
            + ', '.join(obras_sem_alertas)
        )

    obras_com_alerta_rdo = []
    for obra in rdo.get('obras', []):
        for seg in obra.get('segmentos', []):
            if seg.get('alerta') or seg.get('alerta_ag_atrasado'):
                obras_com_alerta_rdo.append({
                    'obra': obra['obra'],
                    'frente': seg.get('frente'),
                    'alerta': (
                        seg.get('alerta') or seg.get('alerta_ag_atrasado')
                    ),
                })

    return json.dumps({
        'modulos': [
            'rdos', 'pedidos', 'restricoes', 'suprimentos',
            'mapa_controle', 'mapa_geografico', 'trackhub',
        ],
        'resumo_obras_ok': resumo_obras_ok,
        'rdos': {
            'total_obras': rdo.get('total_obras', 0),
            'obras_com_alerta': obras_com_alerta_rdo,
            'detalhe': rdo,
        },
        'pedidos': {
            'total_obras': pedidos.get('total_obras', 0),
            'total_pedidos_atrasados': pedidos.get('total_pedidos_atrasados', 0),
            'pedidos_mais_atrasados': pedidos.get(
                'pedidos_mais_atrasados', [],
            )[:8],
            'detalhe': pedidos,
        },
        'restricoes': {
            'total_abertas': restricoes['total_abertas'],
            'total_vencidas': restricoes['total_vencidas'],
            'total_criticas_altas': restricoes['total_criticas_altas'],
            'obras': restricoes['obras'],
        },
        'suprimentos': {
            'obras_sem_itens': suprimentos.get('obras_sem_itens', []),
            'aviso': suprimentos.get('aviso'),
            'detalhe': suprimentos,
        },
        'mapa_controle': {
            'obras': [
                {
                    'obra': o['obra'],
                    'total_mapas': o['total_mapas'],
                    'tem_mapa_controle': o['tem_mapa_controle'],
                    'mapas': o['mapas'],
                    **(
                        {'percentual_conclusao': o['percentual_conclusao']}
                        if o.get('percentual_conclusao') is not None else {}
                    ),
                    **(
                        {'_meta': o['_meta']}
                        if o.get('_meta') else {}
                    ),
                }
                for o in mapa.get('obras', [])
            ],
            'detalhe': mapa,
        },
        'mapa_geografico': mapa_geo,
        'trackhub': {
            'data_referencia': str(hoje),
            'inclui_sede': True,
            'totais': {
                'obras': len(trackhub_obras),
                'abertas': total_abertas_th,
                'vencidas': total_vencidas_th,
            },
            'obras': trackhub_obras,
        },
    }, ensure_ascii=False)


def consultar_situacao_pedidos_obras(
    obra_nome=None,
    obra_id=None,
    dias_aprovacao_alerta=None,
    usuario_wa=None,
) -> str:
    from gestao_aprovacao.models import Obra as ObraGestao

    dias_aprovacao_alerta = (
        7 if dias_aprovacao_alerta is None else dias_aprovacao_alerta
    )
    hoje = timezone.localdate()
    project_ids = _project_ids_escopo(usuario_wa)
    qs_pendentes = _queryset_workorders_escopo(usuario_wa).filter(
        status__in=['pendente', 'reaprovacao'],
    )

    if obra_id or obra_nome:
        project = _resolver_project(obra_nome, obra_id, usuario_wa)
        if not project:
            return json.dumps(
                {'erro': 'Obra não encontrada.'},
                ensure_ascii=False,
            )
        obras_gestao = list(
            ObraGestao.objects.filter(project=project, ativo=True),
        )
    else:
        obras_gestao = list(
            ObraGestao.objects.filter(
                ativo=True,
                project_id__in=project_ids,
            ).select_related('project').order_by('nome'),
        )

    obras_resultado = []
    todos_criticos = []
    for obra_g in obras_gestao:
        ag = _agregar_pedidos_obra(
            obra_g,
            qs_pendentes,
            dias_aprovacao_alerta=dias_aprovacao_alerta,
            hoje=hoje,
        )
        item = {
            'obra': obra_g.nome,
            'project_id': obra_g.project_id,
            **ag,
        }
        obras_resultado.append(item)
        for pedido_atrasado in ag['pedidos_atrasados']:
            pedido_com_obra = dict(pedido_atrasado)
            pedido_com_obra['obra'] = obra_g.nome
            todos_criticos.append(pedido_com_obra)

    todos_criticos.sort(
        key=lambda x: (x.get('prazo_vencido', False), x.get('dias_em_aberto', 0)),
        reverse=True,
    )

    payload = {
        'total_obras': len(obras_resultado),
        'obras': obras_resultado,
        'pedidos_mais_atrasados': todos_criticos[:15],
    }

    if not (obra_id or obra_nome):
        todos_atrasados = []
        for w in qs_pendentes.select_related('obra', 'front'):
            dias = _dias_em_aberto_pedido(w, hoje) or 0
            if dias > dias_aprovacao_alerta:
                todos_atrasados.append({
                    'codigo': w.codigo,
                    'obra': w.obra.nome if w.obra else '-',
                    'frente': _nome_frente_workorder(w),
                    'credor': w.nome_credor,
                    'dias_em_aberto': dias,
                })
        todos_atrasados.sort(
            key=lambda x: x['dias_em_aberto'],
            reverse=True,
        )
        payload['pedidos_atrasados'] = todos_atrasados
        payload['total_pedidos_atrasados'] = len(todos_atrasados)

    return json.dumps(payload, ensure_ascii=False)


def listar_frentes_obra(
    obra_nome=None,
    obra_id=None,
    usuario_wa=None,
) -> str:
    project = _resolver_project(obra_nome, obra_id, usuario_wa)
    if not project:
        return json.dumps(
            {'erro': 'Obra não encontrada.'},
            ensure_ascii=False,
        )

    frentes = _frentes_ativas_project(project)
    resultado = [
        {
            'id': f.id,
            'nome': f.name,
            'codigo': f.code or '',
            'responsavel': f.responsible_name or '-',
            'localizacao': f.location_reference or '-',
        }
        for f in frentes
    ]

    return json.dumps({
        'obra': project.name,
        'project_id': project.id,
        'total_frentes': len(resultado),
        'frentes': resultado,
    }, ensure_ascii=False)


def resumo_frente_obra(
    obra_nome=None,
    obra_id=None,
    frente_nome=None,
    frente_id=None,
    usuario_wa=None,
) -> str:
    project = _resolver_project(obra_nome, obra_id, usuario_wa)
    if not project:
        return json.dumps(
            {'erro': 'Obra não encontrada.'},
            ensure_ascii=False,
        )

    obra_gestao = _obra_gestao_por_project(project)
    if not obra_gestao:
        return json.dumps(
            {'erro': 'Obra sem vínculo no GestControll.'},
            ensure_ascii=False,
        )

    if frente_nome or frente_id:
        front = _resolver_frente(project, frente_nome, frente_id)
        if not front:
            return json.dumps(
                {'erro': 'Frente não encontrada nesta obra.'},
                ensure_ascii=False,
            )
    else:
        frentes = _frentes_ativas_project(project)
        if len(frentes) == 1:
            front = frentes[0]
        else:
            return json.dumps(
                {
                    'erro': (
                        'Informe o nome ou ID da frente. '
                        'Use listar_frentes_obra para ver as opções.'
                    ),
                },
                ensure_ascii=False,
            )

    hoje = timezone.localdate()
    front_id = front.id
    metricas_rdo = _metricas_rdo_frequencia(
        project,
        front_id=front_id,
        dias_analise=90,
        dias_sem_rdo_alerta=7,
        lacuna_minima_dias=7,
    )

    qs_pendentes = WorkOrder.objects.filter(
        obra=obra_gestao,
        status__in=['pendente', 'reaprovacao'],
        front_id=front_id,
    ).select_related('front')

    pedidos_pendentes = []
    for w in qs_pendentes:
        pedidos_pendentes.append(_serializar_pedido_pendente(w, hoje))

    pedidos_atrasados = [
        p for p in pedidos_pendentes
        if (p.get('dias_em_aberto') or 0) > 7
    ]
    pedidos_prazo_vencido = [
        p for p in pedidos_pendentes if p.get('prazo_vencido')
    ]
    restricoes = _contar_restricoes_abertas(obra_gestao, front_id=front_id)

    return json.dumps({
        'obra': project.name,
        'frente': front.name,
        'frente_id': front.id,
        'responsavel_frente': front.responsible_name or '-',
        'rdos': metricas_rdo,
        'pedidos': {
            'pendentes_total': len(pedidos_pendentes),
            'atrasados': len(pedidos_atrasados),
            'prazo_vencido': len(pedidos_prazo_vencido),
            'lista_pendentes': pedidos_pendentes[:10],
        },
        'restricoes': restricoes,
    }, ensure_ascii=False)


FUNCOES_DISPONIVEIS = {
    'consultar_rdos_pendentes': consultar_rdos_pendentes,
    'consultar_pedidos_pendentes': consultar_pedidos_pendentes,
    'listar_obras_ativas': listar_obras_ativas,
    'consultar_obras_sem_rdo': consultar_obras_sem_rdo,
    'consultar_frequencia_rdos': consultar_frequencia_rdos,
    'consultar_situacao_rdo_obra': consultar_situacao_rdo_obra,
    'consultar_situacao_geral_obras': consultar_situacao_geral_obras,
    'consultar_situacao_pedidos_obras': consultar_situacao_pedidos_obras,
    'listar_frentes_obra': listar_frentes_obra,
    'resumo_frente_obra': resumo_frente_obra,
    'consultar_suprimentos_obra': consultar_suprimentos_obra,
    'consultar_panorama_suprimentos': consultar_panorama_suprimentos,
    'consultar_panorama_mapa_controle': consultar_panorama_mapa_controle,
    'consultar_itens_sem_alocacao': consultar_itens_sem_alocacao,
    'consultar_restricoes_obra': consultar_restricoes_obra,
    'consultar_restricoes_criticas': consultar_restricoes_criticas,
    'consultar_pendencias_trackhub': consultar_pendencias_trackhub,
    'consultar_pendencias_vencidas': consultar_pendencias_vencidas,
    'consultar_execucao_fisica_obra': consultar_execucao_fisica_obra,
    'resumo_obra': resumo_obra,
    'buscar_pdf_rdo': buscar_pdf_rdo,
    'consultar_usuarios': consultar_usuarios,
    'consultar_dados_obra': consultar_dados_obra,
    'consultar_modulos_sistema': consultar_modulos_sistema,
    'consultar_rdos_por_periodo': consultar_rdos_por_periodo,
    'consultar_detalhes_rdo': consultar_detalhes_rdo,
    'consultar_aprovadores_obra': consultar_aprovadores_obra,
    'consultar_rdos_por_responsavel': consultar_rdos_por_responsavel,
    'consultar_pedidos_filtrados': consultar_pedidos_filtrados,
    'consultar_status_pedido': consultar_status_pedido,
    'consultar_desempenho_equipe_gest': consultar_desempenho_equipe_gest,
    'buscar_pdf_pedido': buscar_pdf_pedido,
    'consultar_pedidos_reprovados': consultar_pedidos_reprovados,
    'localizar_insumo': localizar_insumo,
    'consultar_suprimentos_por_local': consultar_suprimentos_por_local,
    'consultar_mapa_controle_completo': consultar_mapa_controle_completo,
    'consultar_bi_obra': consultar_bi_obra,
    'consultar_restricoes_por_responsavel': consultar_restricoes_por_responsavel,
    'consultar_pendencias_por_responsavel': consultar_pendencias_por_responsavel,
    'consultar_etapas_pendencia': consultar_etapas_pendencia,
    'consultar_resumo_mapa_obra': consultar_resumo_mapa_obra,
    'listar_elementos_mapa_obra': listar_elementos_mapa_obra,
    'listar_pastas_mapa_obra': listar_pastas_mapa_obra,
    'consultar_alertas_mapa_obra': consultar_alertas_mapa_obra,
    'consultar_elementos_bloqueados_mapa': consultar_elementos_bloqueados_mapa,
    'consultar_marcadores_gps_rdo': consultar_marcadores_gps_rdo,
    'comparar_progresso_mapa_datas': comparar_progresso_mapa_datas,
    'panorama_mapas_obras': panorama_mapas_obras,
    'consultar_resumo_rh': consultar_resumo_rh,
    'consultar_colaboradores_ativos': consultar_colaboradores_ativos,
    'consultar_admissoes_em_andamento': consultar_admissoes_em_andamento,
    'consultar_documentos_vencendo': consultar_documentos_vencendo,
    'consultar_documentos_vencidos': consultar_documentos_vencidos,
    'consultar_prazos_contrato_vencendo': consultar_prazos_contrato_vencendo,
    'consultar_contratos_pendentes_assinatura': consultar_contratos_pendentes_assinatura,
    'consultar_alertas_rh_criticos': consultar_alertas_rh_criticos,
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
