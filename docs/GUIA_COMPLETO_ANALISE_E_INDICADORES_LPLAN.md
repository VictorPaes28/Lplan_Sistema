# Guia completo: indicadores, análise de dados, BI e assistente (Lplan)

**Para quem é este documento**

- **Usuários finais** que já sabem usar os aplicativos e querem saber **que informações o sistema oferece** e **o que podem extrair** (mensagens, reuniões, relatórios simples).
- **Gestores e analistas** que precisam **interpretar números**, montar visões no **BI**, usar o **assistente** e **exportações** sem confundir conceitos.
- **Quem consolida comunicação** (WhatsApp, e-mail interno): há seções prontas para copiar e trechos técnicos mínimos só onde evitar erro de interpretação.

**O que este documento não substitui**

- Treinamento de clique a clique em cada tela (isso é uso do app).
- Política comercial ou contratual da empresa (metas e SLAs são **suas**; o sistema fornece base numérica).

---

## Parte A — Resposta objetiva: o que dá para ver e extrair (linguagem comum)

**Leitura importante:** tudo depende do **perfil de acesso** (obra, empresa, módulo). Se alguém não vê um indicador, em geral é **permissão**, não “falha” do sistema.

### A.1 RDO (Diário de obra)

- Quantidade de **relatórios** da obra e **lista** com filtros (datas, situação, busca em texto).
- **Calendário** com visão dos dias em que há relatório.
- **Situação** de cada relatório (em preenchimento, aguardando aprovação do gestor, aprovado, reprovado, etc. — conforme o fluxo da obra).
- **Horas trabalhadas** registradas no diário (total e média no que a tela/agregado calcular).
- **Resumo de clima** quando o sistema der visão dos últimos dias (baseado no **texto** preenchido em condições climáticas, não em estação meteorológica automática).
- **Fotos, vídeos, anexos** vinculados aos relatórios; **atividades** da obra; **ocorrências** ligadas ao diário; **observações / comentários** (texto do relatório).
- Conteúdo típico por dia: responsáveis, clima, deliberações, observações, acidentes, paralisações, riscos, incidentes, fiscalizações, DDS, entre outros campos previstos no formulário.
- **PDF** do relatório de **um dia** e **PDF reunindo um período** (consolidado), quando houver registros no intervalo.
- Registro de **dia sem relatório** (quando a obra usa esse recurso), para não interpretar buraco no calendário como “esquecimento” sem contexto.

### A.2 Gestão (pedidos de obra — aprovações)

- **Lista de pedidos** com filtros (obra, situação, tipo de solicitação, etc.).
- **Fila** de pedidos aguardando decisão e pedidos já **aprovados**, **reprovados**, em **reaprovação**, **rascunho**, **cancelados** (conforme cadastro).
- **PDF** da lista de pedidos e **PDF** de cada pedido (instantâneo do que está no sistema).
- Telas de **desempenho** (tempo até decisão, reprovações, retrabalho), com **exportação** em planilha (CSV) e/ou PDF **quando a tela permitir** e o usuário tiver acesso.
- Segmentação por **tipo de solicitação** (ex.: contrato, medição, ordem de serviço, mapa de cotação), conforme a empresa usar.

### A.3 Suprimentos e mapa de materiais

- **Total de itens** planejados/ativos na obra.
- Indicadores do tipo: com **pedido de compra** (SC) ou sem; **recebidos** na obra; **alocados** aos locais; **atrasados** (segundo a regra do sistema).
- Visão por **local** da obra (onde está o material, o que falta distribuir).
- **Mapa de controle**: indicadores como itens sem SC, sem PC, sem entrega, sem alocação no sentido daquela tela, atrasos, rankings (por local, categoria, fornecedor), conforme implementação e filtros.
- **Exportação para Excel** em fluxos de engenharia do mapa, quando liberado ao perfil.

### A.4 Outras frentes úteis

- **Assistente / perguntas sobre a obra:** respostas rápidas e visão integrada (pendências, localização de insumos, PDF de RDO por período, etc.) — depende de obra selecionada e permissão.
- **Leitura integrada / radar** (quando ativo): priorização combinando vários eixos (ver Parte F) — é **derivado**, não substitui auditoria com regra fixa no BI.
- **Workflow de aprovação** (módulo próprio): fila de processos e configuração de fluxos — **não confundir automaticamente** com a fila de pedidos da Gestão clássica; a empresa define o que usa onde.
- **Comunicados** (se usado): métricas de alcance/desempenho e exportação (CSV) na área do módulo.

---

## Parte B — Textos prontos para canal informal (WhatsApp)

### B.1 Versão curta (5–6 linhas)

No Lplan vocês acompanham, por obra e conforme o acesso: relatórios de diário (RDO) com fotos, vídeos, ocorrências e PDFs; pedidos de gestão com fila de aprovação e relatórios em PDF ou planilha de desempenho; suprimentos com totais, recebidos, alocados por local, atrasos e mapa de controle, além de Excel onde estiver liberado. Há ainda assistente com resumos e PDF de RDO por período, e comunicados com exportação quando o módulo for usado. O que cada um vê depende do perfil.

### B.2 Gestores / escritório / aprovação (foco em análise)

- Fila e situação dos pedidos; exportações em PDF da lista e do pedido.
- Desempenho da equipe (tempos, reprovações, retrabalho) com CSV/PDF quando disponível.
- Visão ampla do RDO: quantidade de relatórios, calendário, aprovação de diários.
- Mapa de suprimentos: indicadores globais da obra, atrasos, rankings, mapa de controle.

### B.3 Campo / preenchimento (foco em registro)

- Preenchimento e envio do RDO do dia (texto, fotos, vídeos, ocorrências).
- PDF do dia ou do período.
- Consulta ao mapa por local (o que chegou, o que falta alocar), conforme permissão.
- Criação e acompanhamento dos próprios pedidos (rascunho, envio, correções após reprovação).

---

## Parte C — Como “analisar dados” de verdade (além de usar o app)

### C.1 O que é análise neste contexto

- **Operar o sistema** = lançar e consultar.
- **Analisar** = responder perguntas: está **melhorando ou piorando**? o gargalo é **informação**, **decisão** ou **material**? esse número **compara coisas comparáveis**?

Atividade (muito lançamento) não é automaticamente resultado (obra indo bem).

### C.2 Regras que valem para qualquer BI ou planilha

1. **Defina antes:** período (semana, mês, trimestre), **obra** (ou conjunto), e o que é “bom” (**meta interna**).
2. **Separe taxa e volume:** “90% aprovado” com 10 pedidos não tem o mesmo peso que com 1000; reprovações podem ser poucas e **críticas**.
3. **Separe retrato e tendência:** “Como está hoje” vs “comparado ao período anterior”. Para decisão, tendência costuma importar mais.
4. **Cuidado com média:** valores extremos puxam a média; quando existir, use **mediana** ou percentis no BI para ver distorção.
5. **Janela de tempo:** comparar “últimos 7 dias” com “7 dias anteriores” é frequentemente mais honesto que “mês cheio” quando o mês ainda está aberto.
6. **Um número, uma pergunta:** se a pergunta não estiver escrita, o número não quer dizer nada.

### C.3 Papel do BI, do assistente e das exportações

| Ferramenta | Bom para | Não substitui |
|------------|----------|----------------|
| **BI / dashboards** | Mesma pergunta todo mês, mesma definição, cortes por obra/tipo/período | Conferência pontual sem filtro documentado |
| **Assistente** | Resposta rápida, primeiro corte, visão integrada para **priorizar** reunião | Número “oficial” assinado sem checar na lista/export com regra explícita |
| **CSV / Excel / PDF** | Auditoria, cruzamento externo, apresentação com **filtro congelado** | Atualização em tempo real se o arquivo for antigo |

### C.4 Antes de levar um número para a diretoria (checklist)

- [ ] Qual é a **pergunta** exata?
- [ ] Qual **período** e qual **obra**?
- [ ] O indicador é **contagem**, **soma**, **média** ou **percentual**? Sobre qual **universo** (denominador)?
- [ ] É a **mesma definição** usada no mês passado / na outra obra?
- [ ] Se alguém desconfiar, consigo mostrar a **lista filtrada** ou o **export** que sustenta o total?

---

## Parte D — Definições que não podem ser misturadas (erro clássico em BI)

Sem entrar em nomes de tela: o sistema pode calcular **a mesma palavra** de formas **diferentes**. Comparar dois dashboards sem ler a definição gera conflito aparente “sem bug”.

### D.1 Obra entre módulos

- Diário, Gestão e Mapa podem ter cadastros de obra que **precisam apontar para a mesma obra (mesmo código)**.
- Se vínculo ou código divergirem, **totais não fecham** entre módulos — prioridade de correção: **cadastro**, não “fórmula”.

### D.2 “Sem alocação” (três ideias diferentes)

| Ideia | Em linguagem de negócio |
|--------|-------------------------|
| **A** | Item **planejado** e a **soma das alocações** ainda é zero (ou equivalente na regra do cálculo). |
| **B (mapa de controle / resumo típico)** | Material **já recebido na obra** mas **ainda não distribuído** para os locais conforme a regra daquela visão. |
| **C (tendência / janela de datas)** | Mesma lógica geral de A, mas olhando **mudanças em um intervalo de tempo** — o número **não é igual** ao retrato estático “hoje”. |

**Regra prática:** no BI, uma métrica = **um nome explícito** (ex.: “Sem alocação — recebido sem distribuir” vs “Sem alocação — planejado sem alocar”).

### D.3 Pedido “pendente” vs “precisa de aprovador”

- Alguns indicadores usam só **pendente**.
- Outros fluxos (ex.: lembretes) tratam **pendente + reaprovação** como “precisa de alguém”.
- **Fila** e **e-mail** podem não bater com um gráfico que só conta **pendente**.

### D.4 Tempo até aprovação

- Uma linha de análise usa **histórico de decisões** (aprovação registrada) e intervalos entre envio e decisão.
- Outra (ex.: visões tipo radar) pode usar **datas no próprio pedido** de forma diferente.
- **Não comparar** esses números como se fossem a mesma métrica sem validar no BI.

### D.5 Diário “não aprovado” vs “aguardando o gestor”

- **Não aprovado** pode incluir rascunho, reprovado, aguardando, etc.
- **Aguardando aprovação do gestor** é um subconjunto.
- Reunião de “fila do gestor” ≠ reunião de “tudo que não está aprovado”.

### D.6 Itens “não se aplica”

- Algumas visões **excluem** itens marcados como não aplicáveis; outras agregações **podem não excluir**.
- Totais podem divergir **sem erro** se a regra for diferente.

### D.7 Equipamentos no diário (quando houver)

- A consolidação por dia segue regra de **não supercontar** o mesmo equipamento em várias atividades (uso do **maior** quantidade no dia entre vínculos, não soma ingênua em todos os contextos).
- Análises de “equipamento mais usado” dependem do **preenchimento**; tratar como indicador operacional, não contabilidade de frota fechada sem processo paralelo.

---

## Parte E — Catálogo ampliado de tipos de análise (o que o time pode querer medir)

Use como **cardápio de perguntas**; nem tudo estará num único painel pronto — pode exigir BI, export e **nomeação clara da métrica**.

### E.1 Operação e obra

- Cobertura de dias com relatório vs dias úteis; sazonalidade (chuva, fechamento de mês).
- Ritmo: atraso entre dia do trabalho e dia do lançamento (se o dado existir no BI).
- Serviços/atividades: o que mais aparece; picos; relação com clima ou ocorrências.
- Equipamentos no diário: frequência e volume declarados (logística, manutenção), com cautela de qualidade de preenchimento.
- Horas: tendência e outliers (erro de digitação vs evento real).

### E.2 Aprovações e processo

- Fila atual vs **vazão** (entradas e saídas no período).
- Tempo até decisão; reprovação; retrabalho (reenvio após reprovação).
- Corte por **tipo de pedido** (contrato, medição, OS, cotação).
- Corte por **etapa**, se o processo estiver modelado assim no dado.

### E.3 Suprimentos e cadeia

- Planejado × recebido × alocado (três perguntas, não uma só).
- Atraso; concentração por local; ranking por fornecedor/categoria quando o dado existir.
- “Custo de espera” pode ser em **dias de atraso** ou prioridade de itens críticos, mesmo sem R$ no painel.

### E.4 Risco, segurança e qualidade de registro

- Densidade e temas de ocorrências (tags): onde o time mais registra tensão.
- Evolução de campos críticos (acidentes, paralisações, riscos): para reunião de segurança e auditoria interna — é **registro**, não substitui investigação formal sozinha.
- Qualidade de dado: campos vazios, volume de mídia por relatório — mede **disciplina de preenchimento**.

### E.5 Pessoas e governança

- Comparar pessoas ou equipes só com **volume mínimo** e **mesmo tipo de tarefa**; evitar ranking injusto.
- Carga por aprovador (se o dado existir): desbalanceamento de fila.

### E.6 Comunicação interna

- Alcance/desempenho de comunicados (onde export existir); não misturar com produtividade de obra sem contexto.

### E.7 Visão integrada e assistente

- Perguntas transversais (“o que mais pesa nesta obra?”) para **priorizar** reunião.
- Para decisão formal ou número assinado para cliente: cruzar com BI/export com **definição fixa**.

### E.8 Estratégico e comparativo

- Benchmark **obra vs obra** (mesma empresa, fase parecida): sempre **mesmo conjunto de métricas** e **mesmo período**.
- Antes/depois de mudança (processo, fornecedor, responsável): linha do tempo no BI.

---

## Parte F — Radar / leitura integrada (visão de prioridade)

- Costuma ser um **índice combinado** de vários eixos (ex.: suprimentos, aprovações, diário, histórico recente), com **pesos** entre blocos.
- **Tendência** compara janela recente com janela anterior.
- É **derivado**: útil para **ordem do que olhar primeiro**; não use o mesmo número para bater com **um único** KPI de planilha sem reproduzir a mesma receita no BI.

---

## Parte G — Frases prontas para alinhamento interno

**Para o time:**  
“Dado responde a uma pergunta. Se a pergunta não estiver escrita, o número não quer dizer nada.”

**Para gestão e BI:**  
“Os números vêm dos cadastros que a equipe alimenta. Quando a palavra é a mesma mas a definição muda — sem alocação, pendente, tempo de aprovação — o sistema pode mostrar valores diferentes em telas diferentes; não é necessariamente falha, são regras diferentes. Comparabilidade exige **mesmo código de obra entre módulos** e **filtro explícito** no painel.”

**Para o assistente:**  
“É atalho inteligente e primeiro corte; para decisão cara ou número oficial, validar na lista ou export com a regra acordada.”

---

## Parte H — Índice do que este guia cobre (para não faltar o que você pediu)

| Tema | Onde está |
|------|-----------|
| Lista de indicadores e extrações (RDO, Gestão, Suprimentos, outros) | Parte A |
| Textos curtos e por perfil (gestor vs campo) | Parte B |
| Como analisar (perguntas, regras, BI vs assistente vs export) | Parte C |
| Definições que não se misturam (alocação, pendente, tempo, diário) | Parte D |
| Catálogo ampliado de tipos de análise | Parte E |
| Radar / visão integrada | Parte F |
| Frases de alinhamento | Parte G |
| Obra única entre módulos | D.1 |

---

*Documento único gerado para consolidar comunicação a usuários, base analítica para BI e uso consciente do assistente. Ajuste nomes de módulos ou exemplos à linguagem da sua empresa.*
