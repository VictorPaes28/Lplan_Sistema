"""Keywords por intenção — ordem importa para desempate (mais específico primeiro)."""
from assistente_lplan.services.intents import (
    INTENT_FALLBACK,
    INTENT_FRENTES_OBRA,
    INTENT_INTELIGENCIA_INTEGRADA,
    INTENT_LIST_OBRA_PENDING,
    INTENT_LIST_PENDING_APPROVALS,
    INTENT_LOCATE_SUPPLY,
    INTENT_MAPA_CONTROLE_GERAL,
    INTENT_MAPA_GEO,
    INTENT_OBRA_BOTTLENECKS,
    INTENT_OBRA_SUMMARY,
    INTENT_PANORAMA_GERAL,
    INTENT_PEDIDOS_APROVADOR,
    INTENT_PEDIDOS_ATRASADOS,
    INTENT_PESSOA_PERFIL,
    INTENT_RDO_BY_DATE,
    INTENT_RDO_FREQUENCIA,
    INTENT_RELATORIO_LOCAL_MAPA,
    INTENT_RELATORIO_RDO_PERIOD,
    INTENT_REJECTED_REQUESTS,
    INTENT_RESTRICOES_OBRA,
    INTENT_RESTRICOES_RESPONSAVEL,
    INTENT_RH_GERAL,
    INTENT_TRACKHUB_PENDENCIAS,
    INTENT_TRACKHUB_RESPONSAVEL,
    INTENT_UNALLOCATED_ITEMS,
    INTENT_USER_STATUS,
)

# (intent, keywords) — avaliados em ordem para boosts; scoring usa todas as regras
PARSER_RULES: list[tuple[str, list[str]]] = [
    (
        INTENT_RELATORIO_RDO_PERIOD,
        [
            "ultimos", "pdf", "gerar pdf", "baixar pdf", "relatorio em pdf", "exportar pdf",
            "exportar", "consolidado", "periodo do rdo", "rdo dos ultimos", "diario dos ultimos",
            "baixar diario", "pdf do diario", "consolidado rdo",
        ],
    ),
    (
        INTENT_RELATORIO_LOCAL_MAPA,
        [
            "mapa de controle", "mapa de suprimentos", "apartamento", "apto", "apt", "unidade",
            "local no mapa", "situacao do apartamento", "como esta o apartamento",
            "como esta o apto", "o que falta no apartamento", "relatorio do apartamento",
            "pavimento", "bloco", "andar", "setor", "status do apartamento", "status do local",
            "pendencias do apartamento", "unidade habitacional", "desempenho do local",
            "indicadores do local", "como vai o", "como vai a",
        ],
    ),
    (
        INTENT_RESTRICOES_RESPONSAVEL,
        [
            "quem tem mais restric", "ranking de restric", "responsavel com mais atraso",
            "mais restricoes vencidas", "top restric", "restricoes do ", "impedimentos do ",
        ],
    ),
    (
        INTENT_TRACKHUB_RESPONSAVEL,
        [
            "quem tem mais pendenc", "ranking trackhub", "mais pendencias trackhub",
            "responsavel com mais atraso no trackhub", "tarefas do ", "pendencias do ",
            "trackhub do ", "carga de pendenc",
        ],
    ),
    (
        INTENT_PEDIDOS_APROVADOR,
        [
            "quem aprova", "quem esta aprovando", "aprovador", "fila do aprovador",
            "pedidos para aprovar", "aprovacoes do ", "minha fila de aprovacao",
            "sou aprovador", "quem libera pedido", "medição pendente", "medicao pendente",
        ],
    ),
    (
        INTENT_PESSOA_PERFIL,
        [
            "como esta o", "como esta a", "situacao do", "status do", "desempenho do",
            "o que tem pendente", "perfil do", "perfil da", "ultimos 30 dias",
            "atividade do", "andamento do", "o que precisa aprovar", "pendencias do",
        ],
    ),
    (
        INTENT_USER_STATUS,
        ["status do usuario", "status de usuario", "desempenho do usuario"],
    ),
    (
        INTENT_PEDIDOS_ATRASADOS,
        [
            "pedido atrasado", "pedidos atrasados", "pedidos parados", "parado ha",
            "dias em aberto", "quanto tempo parado", "aprovacao demorada",
            "pedido mais antigo", "prazo vencido", "pedido travado", "mais de 30 dias",
            "gestcontroll atrasado", "oc atrasada", "sc atrasada",
        ],
    ),
    (
        INTENT_RDO_FREQUENCIA,
        [
            "frequencia de rdo", "obras sem rdo", "sem rdo", "nunca teve rdo",
            "ultimo rdo", "ultima vez que teve rdo", "diario em atraso", "sem diario",
            "rdo em dia", "lacuna no diario", "buraco no rdo", "historico de diario",
            "pendente de aprovacao do diario", "obras sem registro", "frequencia do diario",
        ],
    ),
    (
        INTENT_PANORAMA_GERAL,
        [
            "situacao geral", "panorama", "panorama geral", "panorama operacional",
            "como estao as obras", "visao geral", "todas as obras", "o que esta critico",
            "resumo do dia", "o que esta atrasado hoje", "como esta o sistema",
            "resumo geral", "qual obra esta pior", "obra mais critica", "dashboard geral",
            "todas obras", "tudo",
        ],
    ),
    (
        INTENT_RESTRICOES_OBRA,
        [
            "restricao", "restricoes", "impedimento", "impedimentos", "impeditivo",
            "bloqueio", "critico", "critica", "vencida", "vencido", "alta prioridade",
            "restricoes abertas", "impedimentos da obra", "gestao de impeditivos",
            "prazo da restricao", "lista de restric",
        ],
    ),
    (
        INTENT_TRACKHUB_PENDENCIAS,
        [
            "trackhub", "track hub", "pendencia trackhub", "tarefa", "tarefas",
            "tarefa vencida", "tarefa atrasada", "etapa pendente", "tarefas em aberto",
            "pendencias em aberto", "prazo trackhub", "vencida no trackhub",
            "lista de pendenc",
        ],
    ),
    (
        INTENT_MAPA_GEO,
        [
            "mapa geografico", "mapa geo", "gps", "elementos no mapa", "marcador",
            "marcadores", "pontos no mapa", "localizacao das obras", "progresso geografico",
            "pin no mapa", "mapa com gps",
        ],
    ),
    (
        INTENT_MAPA_CONTROLE_GERAL,
        [
            "mapa de controle geral", "execucao fisica", "avanco fisico",
            "percentual de conclusao", "quanto avancou", "ferramenta", "ambiente",
            "unidade concluida", "progresso fisico", "kpis do mapa controle",
            "nao iniciadas", "em andamento", "analise do mapa de controle",
        ],
    ),
    (
        INTENT_RH_GERAL,
        [
            "rh", "dp", "departamento pessoal", "recursos humanos", "colaborador",
            "colaboradores", "funcionario", "funcionarios", "admissao", "admissoes",
            "documento vencendo", "documentos vencendo", "contrato vencendo",
            "prazo de experiencia", "clt", "carteira assinada", "quem esta em admissao",
            "alerta rh", "alertas rh", "rh alertas", "rh alerta", "situacao do rh",
        ],
    ),
    (
        INTENT_FRENTES_OBRA,
        [
            "frente", "frentes", "frente de obra", "subobra", "subobras", "md", "mnd",
            "divisao da obra", "como estao as frentes", "rdo por frente", "diario por frente",
        ],
    ),
    (
        INTENT_INTELIGENCIA_INTEGRADA,
        [
            "inteligencia integrada", "visao integrada", "panorama da obra",
            "analise consolidada", "centro de inteligencia", "visao geral da obra",
            "leitura integrada", "radar da obra",
        ],
    ),
    (
        INTENT_LOCATE_SUPPLY,
        [
            "onde esta", "onde fica", "cade o", "localizar", "localizacao", "insumo",
            "material", "materiais", "insumos", "cimento", "achar insumo", "buscar insumo",
        ],
    ),
    (
        INTENT_UNALLOCATED_ITEMS,
        [
            "itens sem aloc", "sem alocacao", "nao alocados", "sem alocar",
            "pipeline sem alocacao", "sc sem alocacao", "linhas sem alocacao",
        ],
    ),
    (
        INTENT_LIST_PENDING_APPROVALS,
        [
            "aprovacao pendente", "aprovacoes pendentes", "pedido pendente", "pedidos pendentes",
            "fila de aprovacao", "gestcontroll", "gest controll", "aguardando aprovacao",
            "oc pendente", "reaprovacao", "fila do gestcontroll",
        ],
    ),
    (
        INTENT_REJECTED_REQUESTS,
        [
            "reprovad", "reprovado", "reprovadas", "solicitacoes reprovadas",
            "pedido reprovado", "negado", "recusado", "nao aprovado",
        ],
    ),
    (
        INTENT_RDO_BY_DATE,
        [
            "rdo do dia", "diario do dia", "relatorio do dia", "rdo de hoje",
            "rdo de ontem", "diario de hoje", "qual rdo", "ver rdo", "registro do dia",
        ],
    ),
    (
        INTENT_OBRA_BOTTLENECKS,
        [
            "gargalo", "gargalos", "travando", "travado", "impedindo", "bloqueando",
            "problema na obra", "dificuldade", "incidente", "lentidao", "emperrado",
        ],
    ),
    (
        INTENT_OBRA_SUMMARY,
        [
            "resumo da obra", "resuma a situacao", "situacao da obra", "obra atual",
            "como esta a obra", "como anda a obra", "resumo operacional", "status da obra",
        ],
    ),
    (
        INTENT_LIST_OBRA_PENDING,
        [
            "pendencia da obra", "pendencias da obra", "o que falta na obra",
            "pendencias operacionais", "alertas da obra",
        ],
    ),
]
