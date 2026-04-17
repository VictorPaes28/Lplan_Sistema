# Inventário gerencial — elementos visuais por tela (Lplan)

**Objetivo:** apoiar gestores a interpretar o que cada número, gráfico ou tabela **mostra**, **de onde vem** e **como usar** na decisão.

**Fonte:** inspeção dos templates Django e das views associadas no repositório (sem inferência de telas inexistentes).

**Não coberto como “BI” separado:** não existe um módulo nomeado apenas “BI” fora da tela **BI da Obra** (`suprimentos` / `analise_obra.html`). O **Painel do sistema** (`accounts` / `admin_central.html`) é painel administrativo com totais globais.

**Conceitos que mudam de significado entre telas** (sempre cruzar com o rótulo da tela):

| Palavra | Onde | Significado canônico neste sistema |
|--------|------|-------------------------------------|
| **Sem alocação** | Dashboard SC/PC (Mapa) — chip “Não Alocado” | Material **recebido** na obra mas **não alocado** ao local (`views_engenharia` / filtros `nao_alocado`). |
| **Sem alocação** | BI da Obra — card “Entregue sem alocar” | Mesma família: fila de suprimentos do **MapaControleService** (`sem_alocacao` no payload). |
| **Sem alocação** | Assistente / Radar (componente suprimentos) | Pode usar regra de **itens planejados sem soma de alocações** — ver `core/kpi_queries` vs `MapaControleService` em `docs/KPI_CONTRATOS_LPLAN.md`. |
| **Pendente** | Gestão — “Aguardando análise” (detalhe obra) | Apenas pedidos com `status='pendente'`. **Não** inclui `reaprovacao`. |
| **Pendente** | Workflow | Processos do **workflow_aprovacao** — outro modelo, não confundir com pedido GestControll. |
| **Tempo até aprovação** | Desempenho — coluna na tabela de solicitantes | Intervalo até **aprovação final** do pedido (ver API `desempenho_solicitantes_api`). |
| **Demora média para decidir** | Desempenho — bloco aprovadores | Baseado em registros de `Approval` e SLA 24h (ver `desempenho_equipe_api`). |
| **Não aprovado** (diário) | Lista / calendário | Qualquer status diferente de aprovado (inclui rascunho, reprovado, aguardando). |
| **Aguardando aprovação** (calendário RDO) | Dashboard | Só relatórios em **aguardando aprovação do gestor**. |
| **Itens não se aplica** | Mapa de Controle | Excluídos de vários agregados do serviço de controle; outras contagens podem **não** excluir. |

---

## 1. BI / “BI da Obra”

**Módulo:** Suprimentos (rota de engenharia)  
**Tela:** **BI da Obra** — `suprimentos/templates/suprimentos/analise_obra.html`  
**View/API:** payload montado para `analise_payload` (filtros: obra, datas, `visao` opcional no GET, setor/bloco/pavimento/apto, material, diário, etc.).

**Filtros que mudam a leitura:** os controles visíveis do formulário (`obra`, `data_inicio`, `data_fim`, recorte físico, material, tag de ocorrência, texto, etc.). O parâmetro **`visao`** permanece no GET/formulário como campo **oculto** (não altera cálculos no serviço atual). Cada alteração nos filtros efetivos redefine o universo dos números.

### 1.1 Situação executiva (hero)

| Campo no template | Tipo | O que mostra | Origem dos dados | Interpretação | Bom sinal | Alerta | Erro comum | Ação sugerida | Observação técnica |
|-------------------|------|--------------|------------------|---------------|-----------|--------|------------|---------------|---------------------|
| Rótulo “Situação” + `situacao_executiva.rotulo` | Indicador textual | Síntese qualitativa calculada para a obra/período | Campo `analise_payload.meta.situacao_executiva` | Leitura executiva; não substitui auditar listas | Rotulo “verde”/estável conforme regra do backend | Rotulo de pressão ou risco | Tratar como auditoria financeira | Priorizar seções 0–1 e cruzamento (material) conforme hierarquia atual; drilldown | Depende do gerador do payload |
| `gerado_em` | Timestamp | Momento da geração do payload | Meta | Frescor dos dados | Data/hora recentes | Muito antigo se você precisa tempo real | Confundir com data do relatório RDO | Clicar “Atualizar” / reaplicar filtros | — |

### 1.2 Faixa de KPIs do hero (`ao-hero-kpis`)

| Nome no card | Tipo | O que mostra | Origem | Interpretação | Bom sinal | Alerta | Erro comum | Ação | Notas |
|--------------|------|--------------|--------|---------------|-----------|--------|------------|------|-------|
| Avanço médio (badge Obra) | Card % | Média de avanço do **mapa de controle** no recorte | `analise_payload.controle.kpis.percentual_medio` | Quanto a obra está avançada em média no recorte filtrado | % alto | % baixo persistente | Comparar com outra obra sem normalizar recorte | Ir à seção “Obra” e matriz / drill | Mesma família do Mapa de Controle |
| Atrasos (badge Material) | Card contagem | Quantidade de itens de material atrasados | `analise_payload.suprimentos.kpis.atrasados` | Pressão na logística | Zero ou em queda | Subida com obra parada | Achar que é atraso de **serviço** | Abrir Dashboard SC/PC no mesmo obra | Definição “atrasado” = regra `ItemMapa` / serviço |
| Ocorrências (badge Campo) | Card contagem | Ocorrências de diário no período | `analise_payload.diario.kpis.ocorrencias_no_periodo` | Intensidade de registro de problemas no campo | Queda após ações | Alta sem plano de mitigação | Confundir com acidente oficial | Revisar RDOs listados abaixo | Depende de preenchimento |
| Período | Card texto | Janela temporal ativa | `meta.periodo` | Contexto obrigatório para qualquer comparação | Período alinhado à reunião | Comparar períodos de tamanhos diferentes | Usar “últimos 7” vs “mês” sem avisar | Ajustar datas e reaplicar | `dias` explicitados no card |

### 1.3 Seção “0 · Ocorrências”

| Elemento | Tipo | O que mostra | Origem | Bom sinal | Alerta | Erro comum | Ação |
|----------|------|--------------|--------|-----------|--------|------------|------|
| Total no período | *(hero — não repete na seção 0)* | Mesmo valor que **Campo · Ocorrências** no quadro superior | `diario.kpis.ocorrencias_no_periodo` | — | — | Procurar card duplicado na seção 0 | Usar o KPI do hero como total |
| Ocorrências críticas | Card número | Subconjunto “crítico/urgente” conforme regra do backend | `diario.kpis.ocorrencias_criticas_no_periodo` | Zero | >0 | Ignorar porque o total geral é baixo | Escalar segurança / engenharia |
| Dias com ocorrência | Card número | Dias distintos com ao menos uma ocorrência | `diario.kpis.dias_com_ocorrencia` | Poucos dias | Muitos dias seguidos | Dividir pelo número de dias úteis sem contexto | Cruzar com timeline |
| Fila de prioridade (badges P1–P4) | Indicadores | Contagem por faixa de prioridade | `diario.prioridades` | P1 próximo de zero | P1 alto | Tratar P4 como irrelevante sem ler texto | Priorizar P1/P2 na obra |
| Tabela “Últimas ocorrências” | Tabela | Lista com data, RDO, prioridade, tags, descrição | `diario.ocorrencias_recentes` | Tags coerentes com ação | Muitas URGENTE | Achar que tag substitui investigação | Abrir RDO (linha clicável quando `relatorio_id`) |
| “Ações recomendadas para hoje” | Lista | Sugestões automáticas cruzadas | `cruzamento.acoes_recomendadas` | Itens factíveis | Lista vazia com P1>0 | Tratar como ordem formal sem validar | Converter em tarefas na obra |

### 1.4 Seção “1 · Obra”

| Elemento | Tipo | O que mostra | Origem | Notas |
|----------|------|--------------|--------|-------|
| Andamento físico (mapa de serviço) | Card único | Concluídos, em andamento, não iniciados + linha “Linhas no recorte” | `controle.kpis.concluidos`, `em_andamento`, `nao_iniciados`, `total_itens` | Três métricas em bloco único; `total_itens` como contexto de base, não como KPI paralelo ao hero |
| Mapa · bloco e piso (heatmap) | Tabela | `heatmap.celulas` | Mesma seção 1, abaixo do card de andamento | Leitura principal de **onde** o físico está fraco (bloco×piso); faixas de % no caption |
| Progressão dos eixos | Gráfico (Chart.js) `chart-blocos-controle` | Média de % por eixo | `controle.blocos_mais_atrasados` / completo ao expandir | Painel **recolhido** por padrão (“Mostrar gráfico por eixo (detalhe)”); gráfico só inicializa ao abrir — detalhe em relação ao heatmap |

### 1.5 Seção “2 · Campo”

| Elemento | Tipo | Origem | Notas |
|----------|------|--------|-------|
| “Ocorrências no tempo” | Gráfico linha/barra `chart-ocorrencias-dia` | Série diária no período | Permite ver picos por dia |
| “Tipos” (tags) | Gráfico pizza/doughnut `chart-tags-diario` | Distribuição de tags | “Toque na fatia para filtrar” — altera interpretação (subconjunto) |
| “Últimos dias” timeline | Lista expansível | `diario.timeline` | Cada dia: contagem de ocorrências, clima resumido, link ao RDO |
| Aviso “Diário não ligado à obra” | Alerta textual | `diario.vinculo_projeto` falso | **Crítico:** KPIs de diário podem não refletir a obra correta até alinhar código Sienge / projeto |

### 1.6 Seção “3 · Locais com risco de atraso”

| Coluna | O que mostra |
|--------|--------------|
| Local | Identificação normalizada |
| % obra | Média de avanço do controle naquele local (`c.controle.percentual_medio`) |
| Pend. | Ranking de pendências de suprimento (`suprimentos.pendencias_pendentes_ranking`) |
| Prioridade / Nota | Cruzamento interpretativo (`prioridade`, `leitura`) |

*Ordem na página:* esta secção aparece **antes** da seção 4 Material (prioridade de leitura executiva: cruzamento físico×suprimento antes da fila só de suprimentos).

### 1.7 Seção “4 · Material”

| Elemento | Tipo | O que mostra | Origem (`suprimentos.kpis`) |
|----------|------|--------------|-----------------------------|
| Card “Fila” — listas | Lista | Contagens **sem SC**, **SC sem PC**, **PC sem entrega**, **Entregue sem alocar** | `sem_sc`, `sem_pc`, `sem_entrega`, `sem_alocacao` |
| Gráfico “Onde mais pesa” | Barras horizontais `chart-suprimentos-locais` | Pendências agregadas por local (itens ainda não entregues) | Ranking por local do payload |

**Alerta:** “Entregue sem alocar” **não** é a mesma métrica que “sem alocação” do assistente em todas as definições — ver tabela de colisão no topo.

### 1.8 “Progressão por eixo — tabela”

Tabela plana dos eixos com % médio e itens — espelha dados do gráfico com possibilidade de drill (offcanvas `aoDrilldown` preenchido via JS/API).

---

## 2. Diário de Obra / RDO

### 2.1 Dashboard do Diário

**Tela:** `core/templates/core/dashboard.html`  
**Contexto:** `dashboard_view` em `core/frontend_views.py` (projeto selecionado na sessão).

| Elemento | Tipo | O que mostra | Origem | Bom sinal | Alerta | Erro comum | Ação |
|----------|------|--------------|--------|-----------|--------|------------|------|
| Card **Relatórios** | Card contagem | Total de diários da obra | `ConstructionDiary` filtrados por projeto | Cresce com a obra | Queda sem justificativa | Comparar obras de tamanhos diferentes | Ver lista completa |
| Card **Atividades** | Card | Total de atividades cadastradas na obra | `Activity` | — | — | — | Abrir filtro de atividades |
| Card **Ocorrências** | Card | Total de `DiaryOccurrence` ligadas a diários da obra | Contagem | — | Alto com P1 | Confundir com NC formal | Ver filtro de ocorrências |
| Card **Comentários** | Card | Diários com `general_notes` não vazio | Query no view | — | — | Achar “comentário” = chat | Ler notas nos RDOs |
| Card **Fotos** | Card | Total de imagens em diários | `DiaryImage` | — | — | — | Galeria / filtro fotos |
| Card **Vídeos** | Card | Total de vídeos | `DiaryVideo` | — | — | — | Idem |
| **Calendário de Relatórios** | Calendário mensal (FullCalendar) | Dia a dia: preenchido, atraso, rascunho, aguardando aprovação, sem RDO justificado | Eventos montados em JS a partir de endpoints/dados injetados | Dias “preenchido” coerentes com operação | Muitos atrasos ou aguardando aprovação | Ignorar “sem RDO (justif.)” como falha | Agir sobre atraso ou fila de aprovação |
| Tabela **Relatórios Recentes** | Tabela | Últimos relatórios: data, nº, status, fotos | `recent_reports` | Status “Aprovado” | Muitos reprovados ou aguardando | — | Abrir linha |
| **Fotos Recentes** | Galeria miniaturas | Últimas fotos | `recent_photos` | — | — | — | Ir ao RDO |
| **Vídeos recentes** | Lista de players | Últimos vídeos | `recent_videos` | — | — | — | Idem |
| **Informações da obra** — Status | Badge | Texto fixo “Em andamento” no template | **Não** vem de regra dinâmica de projeto | — | — | Achar que reflete cronograma real | Usar outras fontes para status comercial |
| **Informações da obra** — Prazo contratual | Barra + números | Dias totais, decorridos, restantes, progresso % | `project_days_*`, `project_progress_percent` | Barra coerente com calendário | Prazo restante baixo sem entrega | — | Replanejar |
| Banner pedido “dia sem RDO” | Modal (JS) | Registro de justificativa de dia sem relatório | `DiaryNoReportDay` | Uso disciplinado | Dias “vazios” sem justificar | — | Treinar equipe |

**Nota:** a view calcula também média de clima, pendentes amplos, horas — **essas métricas não aparecem nos cards** deste template na versão inspecionada; não inventar que estão na tela.

### 2.2 Lista de relatórios (RDO)

**Tela:** `core/templates/core/report_list_partial.html` + página pai (lista).

| Elemento | Tipo | O que mostra |
|----------|------|--------------|
| Faixa “X–Y de Z” | Indicador de página | Paginação da lista filtrada |
| Colunas Data, N°, Status, Fotos | Tabela | Mesmos conceitos do dashboard; inclui linhas **sem RDO** com motivo (feriado, fim de semana, obra parada) |
| Ordenação | Controle | Altera a ordem **sem** mudar o universo (exceto se combinado com filtros GET) |

**Filtros GET** (`report_list_view`): `search`, `date_start`, `date_end`, `status` — qualquer filtro reduz Z e muda médias mentais que você fizer “de cabeça”.

### 2.3 Fila de aprovação (gestor RDO)

Quando o usuário é aprovador, a view injeta lista de diários **aguardando aprovação do gestor** — não está no `report_list_partial` snippet; aparece na página completa de relatórios. **Definição:** `status = AGUARDANDO_APROVACAO_GESTOR` apenas.

---

## 3. Gestão / GestControll (pedidos)

### 3.1 Home GestControll

**Tela:** `gestao_aprovacao/templates/obras/home.html`

| Elemento | Tipo | O que mostra |
|----------|------|--------------|
| **Últimas atualizações** | Lista feed | Últimos `WorkOrder` alterados com **badge de status** (aprovado, reprovado, pendente, reaprovacao, …) | Útil para ver ritmo; **não** é KPI agregado |

### 3.2 Detalhe da obra (Gestão)

**Tela:** `gestao_aprovacao/templates/obras/detail_obra.html`  
**View:** `detail_obra` — `workorders_pendentes = obra.work_orders.filter(status='pendente').count()`.

| Elemento | Tipo | Origem | Alerta |
|----------|------|--------|--------|
| Total de Pedidos | Número | Contagem total de `WorkOrder` da obra | — |
| **Aguardando análise** | Número | **Somente** `pendente` | Se pedidos em `reaprovacao` crescem, esse número **não** mostra — ver lista de pedidos |
| Datas de criação/atualização da obra | Metadado | Auditoria | — |

### 3.3 Desempenho da equipe — Qualidade das solicitações

**Tela:** `gestao_aprovacao/templates/obras/desempenho_equipe.html`  
**APIs:** `desempenho_solicitantes_api`, `desempenho_equipe_api`.

| Elemento | Tipo | O que mostra | Origem / regra |
|----------|------|--------------|----------------|
| Filtro período (7–90 dias) | Filtro | Recorte temporal da API | Mudar dias muda todos os números |
| Filtro tipo de solicitação | Filtro | Contrato, medição, OS, mapa de cotação | Segmentação |
| **Total de Reprovações** | Card | Soma reprovações no período | API solicitantes |
| **Solicitantes com Erros** | Card | Quantidade de linhas (solicitantes) retornadas | Não é “só quem tem erro” no nome — ver API |
| **Taxa de Reprovação** | Card % | `taxa_reprovacao_geral` | Denominador da API |
| **Top Tags de Erro (Geral)** | Ranking de tags | Tags mais frequentes em reprovações | Para treinamento |
| **Reprovações por Tipo de Solicitação** | Mini-cards | Distribuição por tipo | Ver gargalo por tipo |
| Tabela **Análise Detalhada por Solicitante** | Tabela | Colunas: Total Pedidos, Reprovações, Taxa de Erro, Motivos por reprovação, Tempo para corrigir, Tempo até aprovação, Por tipo, Principais motivos | **Ordenação:** maior reprovações primeiro (texto no template) |

### 3.4 Desempenho da equipe — Fluxo de aprovação (aprovadores)

Cards gerados em JS (`criarBlocosAprovadores`), um **por aprovador**, com:

| Campo no card | O que mostra | Origem API | Meta exibida |
|---------------|--------------|------------|--------------|
| Nome + “N decisões no período” | Cabeçalho | Decisões de `Approval` no período | — |
| Média de decisões por dia | Taxa | `total / dias` do filtro | — |
| Demora média para decidir | Tempo (h) | `tempo_medio_horas` | Meta SLA **24h** (valor `sla_horas` da API, default 24) |
| **Decisões atrasadas** (`pct_fora_sla`) | % | % fora do SLA | Texto “ideal < 20%” no template |
| Aprovados / Reprovados | Par + % aprovação | Contagens de decisões | — |
| **Aguardando análise** (`backlog`) | Contagem | Pedidos não analisados na definição da API | Gargalo pessoal |
| Diagnóstico | Texto | `diagnostico` quando existir | Narrativa automática |

**Erro comum:** comparar “Aguardando análise” do aprovador com “Aguardando análise” do detalhe da obra — são bases diferentes (pessoa vs obra, pedidos vs workflow).

### 3.5 Lista de pedidos

**Tela:** `list_workorders.html` — tabela com paginação; **sem** cartões de KPI no template; interpretação é **linha a linha** + filtros aplicados na URL.

---

## 4. Mapa de Suprimentos — Dashboard SC/PC (“Dashboard 2”)

**Tela:** `suprimentos/templates/suprimentos/dashboard_2.html`  
**View:** `views_engenharia.dashboard_2` — KPIs globais calculados sobre **lista completa de itens ativos** da obra (comentário no código: filtros da lista não alteram os totais do topo).

| Elemento | Tipo | O que mostra | Origem | Bom sinal | Alerta |
|----------|------|--------------|--------|-----------|--------|
| Seletor de obra | Filtro | Troca obra inteira | Querystring `obra` | — | Obra errada = todos os números errados |
| Busca + chips de status | Filtro | Refina **lista** inferior; **não** os KPIs do topo | Parâmetros GET | — | Achar que barra KPI mudou ao buscar |
| **Barra KPI — Total** | Card | `kpi_total_itens` | Itens ativos globais | — | Queda sem mudança de escopo |
| **Solicitados (Com SC)** | Card + % + barra | `kpi_com_sc`, `kpi_pct_sc` | Cobertura de compras | Alta % | Baixa % |
| **Recebidos** | Card + % | Itens com recebimento > 0 | `kpi_recebidos`, `kpi_pct_recebidos` | — | — |
| **Alocados** | Card + % | Itens com alocação > 0 **no número exibido**; **clique** aplica filtro `nao_alocado` (ver tooltip template: ver itens **não** alocados) | Leia o título: mostra alocados; clique mostra o oposto | — | Confundir número com “pendentes” sem abrir filtro |
| **Sem SC** | Card | `kpi_sem_sc` | Falta pedido de compra | — | Valor alto |
| **Atrasados** | Card | `kpi_atrasados` | Prazo vencido na regra do item | — | Valor alto |
| Modo **Tabela** (drill) | Painel alternativo | Resumo por Local, Categoria, Status + tabela de itens com colunas Planejado / Comprado / Recebido / Saldo | `drill_totals` no rodapé | Totais batem com soma das linhas visíveis | — | Esquecer que é export CSV do recorte |

**Tooltip “Não Alocado” no chip:** “Material recebido mas não alocado” — confirma definição para **esta** tela.

---

## 5. Mapa de Controle

**Tela:** `suprimentos/templates/suprimentos/mapa_controle.html`  
**Serviço:** `MapaControleService` / views de controle.

| Elemento | Tipo | O que mostra | Origem |
|----------|------|--------------|--------|
| **macro_pulse** (se visível) | Faixa textual | Headline/sub de situação | Payload `macro_pulse` |
| Seletor de obra | Filtro | — | Troca base |
| Filtros status / texto / “Ir para” | Filtro | Recorte da matriz | Afeta todas as contagens |
| **Matriz** (modo bloco / pavimento / unidade) | Tabela % | Cada célula: % de avanço da atividade na linha | Cores por faixas de % (90+, 70+, 40+, >0, 0) |
| Linha / coluna **Total** | % agregados | Médias/peso conforme backend | Ver célula sem bloco: pode não abrir drill |
| **matrix_context_compact** | Texto resumo | Grade N×M, status do filtro, `kpis.total_itens`, média %, contagem concluídos/em andamento/não iniciados, **confiabilidade** % e nível | `kpis`, `confiabilidade` |
| **confiabilidade** | Indicador | “Qualidade dos dados neste recorte” | Score e nível — alerta de dados incompletos |
| **importacao_info** | Metadado | Data da importação / arquivo | Rastreabilidade |
| Navegação chips Setor→Bloco→Pavimento→Unidade | Drills | Mesmos KPIs em recorte menor | — |
| Cards camada **Setores / Blocos / Pavimentos** | Cards | `total itens • progresso` + três contadores (ok/mid/bad) | `layers.*` |
| Painel **detalhe de célula** (`focus_detail`) | Painel | % na grade vs média, status macro, situação, responsável, prazo | KPI boxes: média da célula, aptos, concluídos, andamento, não iniciados |
| Tabela unidades no detalhe | Tabela | Pav, Apto, %, Status, Término, Obs | Granularidade fina |
| Linha **qualidade** (rodapé) | Alerta | Contagens de registros sem bloco/pav/unidade/%/término | Dados sujos — interpretar % com cautela |

---

## 6. Assistente LPLAN + Radar

**Tela:** `assistente_lplan/templates/assistente_lplan/home.html`  
**Radar:** renderizado via `assistente_lplan/static/assistente_lplan/js/assistant_ui.js` quando a resposta JSON traz `radar_score`.

| Elemento | Tipo | O que mostra | Origem |
|----------|------|--------------|--------|
| Painel **Obra priorizada** | Contexto | Código/nome do `Project` selecionado | Sessão |
| **Radar** (bloco dinâmico) | Score + pills + barra | Pontuação 0–100, nível BAIXO/MÉDIO/ALTO, tendência (Estável/Piorando/Melhorando) | `RadarObraService`: pesos 30% suprimentos, 25% aprovações, 25% diário, 20% histórico; níveis: ≤30 baixo, ≤60 médio; tendência compara índices 7d |

**Cartões adicionais vindos do radar** (`cards` na resposta): títulos “Radar de risco”, “Nivel”, “Tendencia”; **timeline** com índices 7 dias vs 7 anteriores vs média 30d.

**Interpretação:** o radar é **derivado** e **não** substitui os KPIs das telas dedicadas; serve para **priorizar** conversa e visitas às áreas.

**Mensagens do chat:** podem incluir tabelas, badges, links — conteúdo **depende da pergunta**; não listável como dashboard fixo.

---

## 7. Workflow de aprovação

| Tela | Arquivo | Elementos visuais |
|------|---------|-------------------|
| Painel | `workflow_aprovacao/dashboard.html` | Card número **na fila** (`pending_count`); tile **Itens aguardando decisão** (repete contagem); tile **Fluxos por obra** (navegação, não é KPI) |
| Fila | `pending_list.html` | Contador `pending_count`; tabela/cards com ID, obra, categoria, alçada (`current_step`), **status do processo**; painel **Atividade recente** (processos já atuados) |

**Alerta:** processos aqui **não** são os mesmos registros que `WorkOrder` da Gestão, salvo integração explícita de negócio.

---

## 8. Comunicados — Desempenho

**Tela:** `comunicados/templates/comunicados/desempenho.html`

| KPI | O que mostra |
|-----|--------------|
| Deveriam ver | Público elegível |
| Visualizaram | Quem abriu |
| Confirmaram | Confirmação explícita (regra do módulo) |
| Responderam | Enviaram resposta |
| Ainda não viram | Pendência de leitura |
| Taxa leitura / confirmação / resposta | Percentuais sobre o público elegível |
| Tabela por usuário | 1ª e última visualização, vezes, confirmação, resposta, status final |
| Respostas recebidas | Corpo das respostas livres |

---

## 9. Painel do sistema (Admin Central)

**Tela:** `accounts/templates/accounts/admin_central.html`  
**Público:** gestão da plataforma (não é obra única).

| Elemento | Origem típica |
|----------|----------------|
| Banner pedidos de correção RDO | `pending_diary_edit_requests_count` |
| KPI **Usuários** | `total_usuarios`, badges ativos / novos 30d |
| KPI **Projetos ativos** | `stats_diario.projetos_ativos` (+ total) |
| KPI **Diários de obra** | `stats_diario.diarios` (+ últimos 30d) |
| KPI **GestControll** | `stats_gestao.ordens`, `stats_gestao.aprovacoes` |
| Painel **logs de e-mail** | Total, Enviados, Falhados, **Taxa de sucesso** % |
| Painel **logs de sistema** | Erros 24h, Avisos 24h, último erro, janela em horas |

**Interpretação:** indicadores **globais** da instalação; não usar para desempenho de uma obra sem filtrar em outra tela.

---

## 10. Outras telas com números (menor densidade analítica)

| Tela | Observação |
|------|------------|
| `gestao_aprovacao/.../list_obras.html` | Coluna **Pedidos** com `work_orders.count` por obra — comparativo simples |
| `workflow_aprovacao/process_detail.html` | Detalhe de um processo: histórico de etapas, não inventado aqui |
| Exportações PDF/CSV | São **instantâneos** do filtro atual — sempre registrar qual filtro gerou o arquivo |

---

## Limitações deste inventário

1. **Gráficos Chart.js** no BI da Obra: o eixo exato e agregação vêm de `analise_obra.js` + API; valores são consistentes com o payload, mas rótulos dinâmicos de eixo devem ser lidos na própria tela gerada.
2. **Calendário RDO:** eventos são montados em JS; categorias seguem a legenda no template (Preenchido, Atraso, Rascunho, Aguardando aprovação, Sem RDO justif.).
3. **Telas não listadas:** se uma tela não aparece aqui, **não foi inventada** — pode não ter KPIs ou não ter sido auditada nesta passagem.

---

## Apêndice — Modelo de ficha (formato solicitado)

Use o bloco abaixo como **molde** para copiar ao treinar o chefe ou ao detalhar no GPT. O corpo principal deste documento usa **tabelas** com as **mesmas colunas**, para não repetir centenas de blocos idênticos.

### Exemplo 1 — BI da Obra · Card “Entregue sem alocar”

- **Módulo:** Suprimentos — BI da Obra  
- **Tela:** BI da Obra (`analise_obra.html`, seção 3 · Material, card Fila)  
- **Nome do gráfico/card/tabela:** Entregue sem alocar (linha na lista do card “Fila”)  
- **Tipo:** Indicador numérico (linha de lista dentro de card)  
- **O que mostra:** Quantidade de itens em que há material entregue na obra mas ainda **sem alocação** ao local, segundo a regra do `MapaControleService` / payload de análise.  
- **De onde vem o dado:** `analise_payload.suprimentos.kpis.sem_alocacao` (backend de análise da obra).  
- **Como o gestor deve interpretar:** Tamanho da fila física “no pátio” sem destino administrado no sistema.  
- **Quando é um bom sinal:** Valor baixo ou em queda semanal quando a obra está em fase de acabamento (contexto dependente).  
- **Quando é um alerta:** Valor alto e estável com reclamações de falta de material no local.  
- **Erro comum de interpretação:** Igualar a “sem alocação” do Radar ou de outras queries sem ler o rótulo da tela.  
- **Ação prática que esse dado sugere:** Priorizar **distribuição interna** e conferência de alocação no mapa; escalar logística interna.  
- **Observações técnicas importantes:** Definição alinhada ao Mapa de Controle para “recebido sem distribuir”; diverge de outras definições de “sem alocação” no ecossistema (ver tabela de colisão no início deste doc).

### Exemplo 2 — Gestão · “Aguardando análise” na obra

- **Módulo:** Gestão (GestControll)  
- **Tela:** Detalhes da Obra (`detail_obra.html`)  
- **Nome do gráfico/card/tabela:** Aguardando análise  
- **Tipo:** Indicador numérico grande  
- **O que mostra:** Quantidade de pedidos (`WorkOrder`) da obra com **status exatamente igual a `pendente`**.  
- **De onde vem o dado:** `obra.work_orders.filter(status='pendente').count()` em `gestao_aprovacao/views.py` (`detail_obra`).  
- **Como o gestor deve interpretar:** Fila **formal** de pedidos aguardando primeira análise/aprovação neste status.  
- **Quando é um bom sinal:** Número compatível com a capacidade do time de aprovação e prazos contratuais.  
- **Quando é um alerta:** Crescimento contínuo ou valores altos com reclamações de obra parada.  
- **Erro comum de interpretação:** Achar que inclui pedidos em **reaprovacao** — **não inclui**.  
- **Ação prática que esse dado sugere:** Desbloquear aprovadores, revisar prioridade dos pedidos ou subdividir envios.  
- **Observações técnicas importantes:** Para fila completa do aprovador (pendente + reaprovacao), usar listas/relatórios ou desempenho, não só este campo.

### Exemplo 3 — Diário · Card “Relatórios” no dashboard

- **Módulo:** Core / Diário de Obra  
- **Tela:** Dashboard (`core/templates/core/dashboard.html`)  
- **Nome do gráfico/card/tabela:** Relatórios (primeiro card KPI)  
- **Tipo:** Card contagem  
- **O que mostra:** Número total de diários (`ConstructionDiary`) registrados para o **projeto selecionado**.  
- **De onde vem o dado:** Agregação em `dashboard_view` (`core/frontend_views.py`), filtro `project=projeto da sessão`.  
- **Como o gestor deve interpretar:** Volume histórico de RDOs; não mede por si só qualidade nem cobertura de dias úteis.  
- **Quando é um bom sinal:** Crescimento alinhado ao tempo de obra e à disciplina de registro.  
- **Quando é um alerta:** Estagnação com obra ativa, ou contagem alta com muitos reprovados/aguardando (ver calendário e lista).  
- **Erro comum de interpretação:** Comparar totais entre obras de durações muito diferentes sem normalizar por tempo.  
- **Ação prática que esse dado sugere:** Se baixo: reforçar cultura de RDO; se alto com problemas de status: olhar calendário e fila de aprovação.  
- **Observações técnicas importantes:** Não confundir com “dias cobertos”; use o **calendário** para cobertura.

---

*Última atualização: gerado a partir dos ficheiros do repositório no estado atual; ao alterar templates ou regras de negócio, atualize este documento e `docs/KPI_CONTRATOS_LPLAN.md`.*
