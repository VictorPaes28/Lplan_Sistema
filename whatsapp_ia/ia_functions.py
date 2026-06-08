import inspect
import json
from datetime import datetime
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
    {
        'type': 'function',
        'function': {
            'name': 'consultar_usuarios',
            'description': (
                'Consulta usuários do sistema. '
                'Retorna total, lista de ativos/inativos, '
                'ou dados de um usuário específico com '
                'últimos registros de atividade. '
                'Use quando perguntar sobre usuários, '
                'quem está ativo, ou atividade de alguém.'
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
                'por obra, por responsável/aprovador, por tipo, por credor, '
                'por solicitante, por status específico. '
                "Exemplos: 'pedidos pendentes da última semana', "
                "'pedidos atrasados há mais de 15 dias', "
                "'pedidos de medição', 'pedidos do credor X'."
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
                'Consulta o desempenho da equipe no GestControll: '
                'tempo médio de resposta por aprovador, '
                'total aprovado/reprovado por pessoa, '
                'desempenho de solicitantes. '
                'Use quando perguntar sobre desempenho, '
                'quem está demorando mais para aprovar, '
                'ranking de aprovadores.'
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
                'Consulta restrições abertas filtradas por responsável. '
                "Use quando perguntar 'restrições do João', "
                "'impedimentos da Maria', 'o que o Carlos tem pendente'."
            ),
            'parameters': {
                'type': 'object',
                'properties': {
                    'responsavel_nome': {
                        'type': 'string',
                        'description': 'Nome do responsável pela restrição.',
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
            'name': 'consultar_pendencias_por_responsavel',
            'description': (
                'Consulta pendências TrackHub de um responsável específico. '
                "Use quando perguntar 'pendências do Cleiton', "
                "'o que a Emília tem aberto', 'tarefas do responsável X'."
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


def consultar_usuarios(
    usuario_nome=None, apenas_ativos=False, usuario_wa=None,
) -> str:
    from django.contrib.auth import get_user_model

    User = get_user_model()

    qs = User.objects.all()
    if apenas_ativos:
        qs = qs.filter(is_active=True)
    if usuario_nome:
        qs = qs.filter(
            Q(first_name__icontains=usuario_nome)
            | Q(last_name__icontains=usuario_nome)
            | Q(username__icontains=usuario_nome)
        )

    total = qs.count()
    ativos = User.objects.filter(is_active=True).count()
    inativos = User.objects.filter(is_active=False).count()

    usuarios = []
    for u in qs[:20]:
        ultimo_login = str(u.last_login.date()) if u.last_login else 'Nunca'
        usuarios.append({
            'id': u.id,
            'nome': u.get_full_name() or u.username,
            'username': u.username,
            'email': u.email,
            'ativo': u.is_active,
            'ultimo_login': ultimo_login,
        })

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
    atraso_minimo_dias=None, ordem=None,
    usuario_wa=None,
) -> str:
    from datetime import timedelta

    from django.contrib.auth import get_user_model

    from gestao_aprovacao.models import Approval, WorkOrder, WorkOrderPermission

    User = get_user_model()

    qs = WorkOrder.objects.select_related('obra').order_by('-data_envio')

    if obra_nome:
        project = _resolver_project(
            obra_nome=obra_nome, usuario_wa=usuario_wa,
        )
        obra_g = _obra_gestao_por_project(project)
        if obra_g:
            qs = qs.filter(obra=obra_g)

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

    if ordem == 'antigos':
        qs = qs.order_by('data_envio')
    elif ordem == 'obra':
        qs = qs.order_by('obra__nome')

    total = qs.count()
    pedidos = []
    for w in qs[:20]:
        pedidos.append({
            'id': w.id,
            'codigo': w.codigo,
            'tipo': w.tipo_solicitacao,
            'credor': w.nome_credor,
            'status': w.status,
            'obra': w.obra.nome if w.obra else '-',
            'data_envio': (
                str(w.data_envio.date()) if w.data_envio else '-'
            ),
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
    from django.contrib.auth import get_user_model
    from django.db.models import Count

    from gestao_aprovacao.models import Approval, WorkOrder

    User = get_user_model()
    obra_g = None
    if obra_nome:
        project = _resolver_project(
            obra_nome=obra_nome, usuario_wa=usuario_wa,
        )
        obra_g = _obra_gestao_por_project(project)

    aprovadores = []
    if not tipo or tipo == 'aprovadores':
        qs_ap = Approval.objects.select_related(
            'aprovado_por', 'work_order',
        )
        if obra_g:
            qs_ap = qs_ap.filter(work_order__obra=obra_g)

        por_aprovador = {}
        for ap in qs_ap:
            uid = ap.aprovado_por_id or 'desconhecido'
            if uid not in por_aprovador:
                por_aprovador[uid] = {
                    'nome': (
                        ap.aprovado_por.get_full_name()
                        if ap.aprovado_por else 'Desconhecido'
                    ),
                    'total': 0,
                    'aprovados': 0,
                    'reprovados': 0,
                }
            por_aprovador[uid]['total'] += 1
            if ap.decisao == 'reprovado':
                por_aprovador[uid]['reprovados'] += 1
            else:
                por_aprovador[uid]['aprovados'] += 1

        aprovadores = sorted(
            por_aprovador.values(),
            key=lambda x: x['total'],
            reverse=True,
        )[:10]

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
    from datetime import timedelta

    from gestao_aprovacao.models import Approval, WorkOrder

    qs = WorkOrder.objects.filter(
        status='reprovado',
    ).select_related('obra', 'criado_por').order_by('-data_envio')

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
                        'sem_sc': s.sem_sc,
                        'sem_pc': s.sem_pc,
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

        resultado_ambientes.append({
            'id': amb.id,
            'nome': amb.nome,
            'ativo': amb.ativo,
            'ultima_atualizacao': (
                str(amb.updated_at.date()) if amb.updated_at else '-'
            ),
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
    responsavel_nome, obra_nome=None,
    incluir_concluidas=False, usuario_wa=None,
) -> str:
    from django.contrib.auth import get_user_model

    from impedimentos.models import Impedimento, StatusImpedimento

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

    qs = Impedimento.objects.filter(
        responsaveis__in=usuarios,
        parent__isnull=True,
    ).select_related('obra', 'status').distinct()

    if obra_nome:
        obra = _resolver_obra_gestao(
            obra_nome=obra_nome, usuario_wa=usuario_wa,
        )
        if obra:
            qs = qs.filter(obra=obra)

    if not incluir_concluidas:
        final_ids = []
        for obra_id in qs.values_list('obra_id', flat=True).distinct():
            status_final = StatusImpedimento.objects.filter(
                obra_id=obra_id,
            ).order_by('-ordem').first()
            if status_final:
                final_ids.append(status_final.id)
        if final_ids:
            qs = qs.exclude(status_id__in=final_ids)

    hoje = timezone.localdate()
    resultados = []
    for imp in qs[:20]:
        resultados.append({
            'id': imp.id,
            'titulo': imp.titulo,
            'prioridade': imp.prioridade,
            'obra': imp.obra.nome if imp.obra else '-',
            'status': (
                imp.status.nome if imp.status else '-'
            ),
            'prazo': str(imp.prazo) if imp.prazo else '-',
            'vencida': imp.prazo < hoje if imp.prazo else False,
        })

    return json.dumps({
        'responsavel': responsavel_nome,
        'total': qs.count(),
        'restricoes': resultados,
    }, ensure_ascii=False)


def consultar_pendencias_por_responsavel(
    responsavel_nome, obra_nome=None,
    incluir_concluidas=False, usuario_wa=None,
) -> str:
    from django.contrib.auth import get_user_model

    from trackhub.models import Pendencia

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

    qs = Pendencia.objects.filter(
        responsavel_interno__in=usuarios,
    ).select_related('obra')

    if not incluir_concluidas:
        qs = qs.exclude(status__in=['concluida', 'cancelada'])

    if obra_nome:
        obra = _resolver_obra_mapa(
            obra_nome=obra_nome, usuario_wa=usuario_wa,
        )
        if obra:
            qs = qs.filter(obra=obra)

    hoje = timezone.localdate()
    resultados = []
    for p in qs[:20]:
        resultados.append({
            'id': p.id,
            'titulo': p.titulo,
            'tipo': p.tipo,
            'status': p.status,
            'obra': p.obra.nome if p.obra else '-',
            'prazo': str(p.prazo) if p.prazo else '-',
            'vencida': p.prazo < hoje if p.prazo else False,
        })

    return json.dumps({
        'responsavel': responsavel_nome,
        'total': qs.count(),
        'pendencias': resultados,
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
