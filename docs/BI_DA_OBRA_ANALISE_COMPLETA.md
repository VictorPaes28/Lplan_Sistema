# BI da Obra — análise completa (diagnóstico, sem alterações de código)

**Escopo:** módulo servido por `suprimentos/views_analise_obra.py`, template `suprimentos/templates/suprimentos/analise_obra.html`, serviço `suprimentos/services/analise_obra_service.py`, agregação de materiais `suprimentos/services/mapa_controle_service.py`, gráficos `suprimentos/static/js/analise_obra.js`.

**Premissa:** descreve o **comportamento verificado** (regras no serviço/backend e **apresentação atual** do template/JS). Trechos de interface foram alinhados à revisão de UX do BI (hierarquia visual, sem mudança de regra de cálculo).

---

## Parte 1 — Inventário completo do BI

### 1.1 Uma única “tela”

Não há múltiplas rotas de BI: existe a página **BI da Obra** (`/engenharia/analise-obra/` conforme `urls_engenharia`). Conteúdo em **seções numeradas** no template.

### 1.2 Filtros globais (barra principal + colapso “Mais filtros”)

| Controle | Parâmetro GET | Afeta |
|----------|---------------|--------|
| Obra | `obra` | Toda a análise; resolve `mapa_obras.Obra` e sessão |
| De / Até | `data_inicio`, `data_fim` | Período do **diário** e janela temporal exibida em `meta.periodo`; controle físico e suprimentos são **recortados por filtros de obra**, não por data (exceto onde indicado) |
| `visao` (Geral / Detalhe) | `visao` | Continua aceito no GET e repassado em `AnaliseObraFilters`; **não aparece mais como controle na barra rápida** (campo oculto no formulário, padrão `geral`). **Ainda não altera cálculos** em `AnaliseObraService` (ver Parte 3) |
| Setor, Bloco, Pavimento, Unidade, Etapa/atividade | `setor`, `bloco`, `pavimento`, `apto`, `atividade` | Queryset `ItemMapaServico` (`controle_base_queryset`) |
| Status obra | `status_servico` | Filtra linhas de serviço por **ratio** derivado de `status_percentual` / `status_texto` (Python) |
| Local material, categoria, prioridade, status SC/PC, busca material | `local_suprimento_id`, `categoria_suprimento`, `prioridade_suprimento`, `status_suprimento`, `busca_suprimento` | `MapaControleService` via `to_mapa_suprimentos_filters()` — base `ItemMapa`, `nao_aplica=False` |
| Tag ocorrência, texto ocorrência, responsável | `tag_ocorrencia_id`, `busca_diario_texto`, `responsavel_texto` | Apenas **diário** (`ConstructionDiary` / `DiaryOccurrence`) |

### 1.3 Blocos da interface (ordem do template)

| # | Seção | Conteúdo |
|---|--------|------------|
| Hero | Título, obra, código Sienge, link código projeto diário (se houver), **Situação** (rótulo executivo), **4 KPIs** hero (inclui total de **Ocorrências** no período), baseline “em breve” |
| 0 | Ocorrências | **3 cards** (críticas, dias com ocorrência, fila P1–P4) + tabela últimas ocorrências + filtro prioridade + ações recomendadas — *o total de ocorrências não tem card duplicado; está só no hero* |
| 1 | Obra | **Um bloco** “Andamento físico”: concluídos, em andamento, não iniciados + linha auxiliar “Linhas no recorte” (`total_itens`); em seguida **heatmap** (bloco×piso, % médio, criticidade); **gráfico por eixo** (“Progressão dos eixos”) em painel **recolhido** (“Mostrar gráfico por eixo (detalhe)”) — o Chart.js só é desenhado ao abrir o painel |
| 2 | Campo | 2 gráficos (ocorrências no tempo, tags) + timeline últimos dias |
| 3 | Locais com risco de atraso | Tabela de **cruzamento** (execução × suprimento por local) — priorizada antes do material |
| 4 | Material | Card fila (4 linhas) + gráfico “Onde mais pesa” (pendências por local; caption esclarece suprimentos) |
| Tabela extra | Progressão por eixo (tabela completa) |
| Offcanvas | Drilldown (carregado via API) |

### 1.4 Gráficos Chart.js (IDs)

- `chart-blocos-controle` — barras horizontais, eixos “piores” ou lista completa (botão expandir); **só é inicializado depois que o utilizador abre** o collapse “Mostrar gráfico por eixo (detalhe)” (evita canvas com largura zero)
- `chart-ocorrencias-dia` — linha, série `diario.ocorrencias_por_dia`
- `chart-tags-diario` — distribuição de tags (`tags_top`)
- `chart-suprimentos-locais` — barras ranking locais (`suprimentos.ranking.locais`)

### 1.5 APIs auxiliares

- `GET .../api/internal/analise-obra/?obra=&secao=...` — fatia do payload (`build_section`)
- `GET .../analise-obra/drilldown/` — `build_drill_down` (drawer)

### 1.6 Alertas / textos fixos

- Aviso **“Diário não ligado à obra”** se `Project` não resolve por código Sienge
- **Alertas semânticos** em `cruzamento.alertas_semanticos` (lista de strings)
- Legenda criticidade no payload heatmap `legenda_criticidade`

---

## Parte 2 — Explicação técnica por elemento (estrutura pedida)

Abaixo, cada item segue os campos solicitados. Itens muito semelhantes foram agrupados quando a regra é idêntica.

---

### Meta · Situação executiva (`meta.situacao_executiva`)

- **Nome exibido no BI:** “Situação” + texto (`rotulo` dinâmico, ex.: “Obra dentro do previsto”)
- **Tipo:** Indicador textual composto
- **Onde aparece:** Cabeçalho hero (direita)
- **O que esse dado mostra de fato:** Classificação **heurística** em 3 níveis (`ok`, `atencao`, `risco`) a partir de soma de “sinais” derivados de: % médio de execução física, número de itens de material atrasados, volume/criticidade de ocorrências no diário
- **Qual consulta/modelo:** `_classify_situacao` em `analise_obra_service.py` — lê `controle.kpis.percentual_medio`, `suprimentos.kpis.atrasados`, `diario.kpis` e `prioridades.p1_critica`
- **Regra de cálculo:** Pontuação acumulada por faixas (ex.: `pct < 35` +2 sinais; `atrasados >= 15` +2; `occ_crit >= 3` +2; etc.) → se `sinais <= 1` ok; `<= 3` atenção; senão risco
- **Filtros que alteram:** Recorte de **controle** (setor/bloco/…/status_servico), **suprimentos** (categoria, local, …), **diário** (período, tag, texto, responsável)
- **Interpretação gerencial:** “Termômetro” executivo; não é KPI financeiro nem cronograma
- **Bom sinal:** “Obra dentro do previsto” com motivos vazios ou leves
- **Alerta:** “Obra com risco…” com vários motivos
- **Erros prováveis:** Tratar como verdade absoluta; ignorar que mistura três domínios com pesos arbitrários
- **Nome parecido em outro lugar:** “Situação” no Mapa de Controle (ficha de célula) é outro conceito
- **Clareza do nome:** Média — “Situação” é genérico
- **Risco de inconsistência:** **Médio** (depende de três fontes)

---

### Hero · KPI “Avanço médio” (badge Obra)

- **Nome exibido:** “Avanço médio”
- **Tipo:** Card percentual
- **Onde:** Faixa `ao-hero-kpis`
- **O que mostra:** Média dos **ratios** de avanço das linhas `ItemMapaServico` no recorte, expressa em %
- **Origem:** `_build_controle` → `kpis.percentual_medio` = `round((soma_pct / pct_count) * 100, 2)` onde `soma_pct` soma `_status_to_ratio(item)` por linha com ratio não nulo
- **Regra `_status_to_ratio`:** Usa `status_percentual` numérico (0–1 ou 0–100); senão heurística em `status_texto` (palavras “conclu”, “andamento”, “pend”, etc.)
- **Filtros:** Setor, bloco, pavimento, apto, atividade, status_servico
- **Interpretação:** Execução física média declarada no **mapa de serviço**, não medição de cronograma Sienge
- **Bom sinal:** % alto com dados confiáveis
- **Alerta:** % baixo persistente
- **Erros:** Confundir com avanço de **obra** no Mapa de Controle de **materiais** ou com percentual de **alocação** de material
- **Termo parecido:** “% médio” no heatmap (mesma família de ratio)
- **Clareza:** Razoável se se ler subtítulo em `descricao_curta` do bloco controle
- **Risco inconsistência:** **Médio** (depende da qualidade de `status_texto`/`status_percentual`)

---

### Hero · KPI “Atrasos” (badge Material)

- **Nome exibido:** “Atrasos”
- **Tipo:** Card contagem
- **O que mostra:** Contagem de `ItemMapa` com `is_atrasado` verdadeiro, após filtros do MapaControle
- **Origem:** `MapaControleService.build_summary_payload()` → `kpis.atrasados`
- **Regra:** `sum(1 for i in items if i.is_atrasado)` sobre itens filtrados; base exclui `nao_aplica=True`
- **Filtros suprimentos:** categoria, local, prioridade, status SC/PC, busca — **não** os filtros de setor/bloco do **serviço** (são outro modelo)
- **Interpretação:** Atraso na **cadeia de compra/entrega** conforme modelo de item
- **Alerta:** Número alto (Situação usa ≥15 como “muitos atrasos”)
- **Erros:** Confundir com atraso de **cronograma físico** do controle
- **Nome parecido:** “Atrasados” no Dashboard SC/PC (mesma família se mesmos filtros)
- **Risco:** **Baixo** a **médio** (depende da definição de `is_atrasado` no modelo)

---

### Hero · KPI “Ocorrências” (badge Campo)

- **Nome exibido:** “Ocorrências”
- **Tipo:** Card contagem
- **O que mostra:** Total de `DiaryOccurrence` ligadas a diários **aprovados** no período (`ConstructionDiary` filtrado por datas + filtros de responsável nos diários)
- **Regra:** `occ_qs.count()` após filtros de tag e texto na ocorrência
- **Filtros:** Período, `tag_ocorrencia_id`, `busca_diario_texto`, `responsavel_texto` (último nos diários)
- **Erros:** Comparar com ocorrências em RDO não aprovados — **excluídos**
- **Risco:** **Médio** (só aprovados)

---

### Hero · KPI “Período”

- **O que mostra:** Datas e número de dias (`(fim - inicio).days + 1`)
- **Origem:** `AnaliseObraPeriodo`
- **Risco:** **Baixo**

---

### Seção 0 · Cards de ocorrências

| Nome no BI | Chave payload | Regra resumida |
|------------|---------------|----------------|
| *(sem card dedicado)* | `kpis.ocorrencias_no_periodo` | Total de ocorrências no período continua no **hero** (“Campo · Ocorrências”); não há card duplicado na seção 0 |
| Ocorrências críticas | `kpis.ocorrencias_criticas_no_periodo` | Igual a `prioridades.p1_critica` — contagem de ocorrências cuja severidade heurística é `critica` (`_classify_occurrence_severity`) |
| Dias com ocorrência | `kpis.dias_com_ocorrencia` | Dias distintos com ≥1 ocorrência |
| Fila de prioridade | `prioridades` p1–p4 | Cada ocorrência classificada em critica/alta/media/baixa pela mesma heurística |

**Heurística de severidade:** palavras-chave em descrição + tags (ex.: “acidente” → crítica; “atraso”, “risco” → alta; “pendência”, “retrabalho” → média; senão baixa).

**Risco:** **Alto** para gestor — severidade **não** é classificação de segurança legal; é texto.

---

### Seção 0 · Tabela “Últimas ocorrências”

- **Origem:** Lista `ocorrencias_recentes` — **todas** as ocorrências do `occ_qs` ordenadas por data (não apenas “últimas N” no serviço — ver código: **sem slice** na construção da lista; o template pode truncar visualmente)
- **Risco de performance/UX:** Lista pode ser longa; template tem “Ver mais”
- **Risco interpretação:** **Médio**

---

### Seção 0 · “Ações recomendadas para hoje”

- **Origem:** `_build_cruzamento` — combina candidatos (controle + ranking local suprimentos) + regras P1/P2 do diário + fallback ROTINA
- **Natureza:** **Sugestão textual**, não ordem de serviço
- **Risco:** **Médio** (prioridade “URGENTE” automática)

---

### Seção 1 · Andamento físico (mapa de serviço)

- **Concluído / em_andamento / nao_iniciados:** contagens por linha `ItemMapaServico` após `_status_to_ratio`; se ratio `None`, a linha conta como **não iniciado** (comentário no código: conservador). Na UI aparecem em **um único card** (“Andamento físico”), com três números, mais linha auxiliar **Linhas no recorte** (`total_itens` = `len(items)`).
- **percentual_medio (hero):** média dos ratios válidos — permanece no hero como “Avanço médio”
- **Risco:** **Médio** — linhas sem dado válido viram “não iniciado”, empurrando interpretação

---

### Seção 1 · Heatmap (mapa bloco × piso)

- **Posição na tela:** integrado na **mesma seção 1**, após o card de andamento (não é mais um `<h2>` separado “Mapa · bloco e piso”).
- **% médio:** média de ratios por célula (bloco×pavimento ou setor+bloco×pavimento)
- **Criticidade:** `_criticidade_from_pct`: &lt;30 critica; &lt;55 alta; &lt;75 media; senão baixa; `None` → sem_dado
- **Caption:** faixas de % no texto do card (substitui footnote solta duplicada)
- **Origem:** só `ItemMapaServico`, **sem** misturar suprimento/diário (`descricao_curta` no payload)

---

### Seção 1 · Gráfico “Progressão dos eixos” (detalhe, recolhido)

- **Nome na UI:** subtítulo **“Progressão dos eixos”** (painel recolhido por padrão).
- **Dados:** `controle.blocos_mais_atrasados` (até 16 eixos, diversificação por setor) **ou** lista completa ao expandir
- **Eixo:** % médio por eixo (setor+bloco ou só bloco)
- **Nome “mais atrasados” (código):** Ordenação por **menor** % médio (piores primeiro) — o rótulo “atrasados” aqui significa **atraso de execução física relativa**, não atraso de material
- **Risco inconsistência nome:** **Alto** (“atrasados” vs “percentual médio”)

---

### Seção 2 · Gráficos diário

- **Ocorrências no tempo:** `ocorrencias_por_dia` — agregação `Count` por `diary__date`; só dias com ocorrência na série (dias sem evento podem não aparecer — ver série)
- **Tags:** `tags_top` — top tags entre ocorrências filtradas
- **Timeline:** últimos 12 diários **aprovados** com lista de ocorrências do dia

---

### Seção 4 · Material · Card “Fila”

| Linha no BI | Chave KPI | Regra em `MapaControleService` |
|-------------|-----------|--------------------------------|
| Sem pedido (SC) | `sem_sc` | `not numero_sc` |
| SC sem compra (PC) | `sem_pc` | tem SC e não tem PC |
| PC sem entrega | `sem_entrega` | tem PC e `quantidade_recebida_obra <= 0` |
| Entregue sem alocar | `sem_alocacao` | `quantidade_recebida_obra > 0` e `quantidade_alocada_local <= 0` |

- **Exclui:** `nao_aplica=True`
- **“Entregue sem alocar”:** Coerente com label **se** gestor entende “alocação” como destino local no mapa

---

### Seção 4 · Gráfico “Onde mais pesa”

- **Dados:** `ranking.locais` — contagem de itens **pendentes** por local (`status_etapa != "ENTREGUE"`) dentro dos itens filtrados
- **Interpretação:** Onde há mais linhas pendentes de fechamento, não necessariamente valor R$

---

### Seção 3 · “Locais com risco de atraso”

- **Origem:** `_build_cruzamento` — cruza **piores eixos** do controle com **ranking de pendências por local** do suprimento (match de chave normalizada ou substring)
- **Coluna Pend.:** `pendencias_pendentes_ranking` — valor do ranking de locais (contagem), não R$
- **Score `score_risco`:** mistura `(100 - %_execução)` e peso de pendência relativa ao máximo
- **Risco:** **Alto** se o gestor achar que é “atraso de prazo contratual”

---

### Drilldown API (`build_drill_down`)

- **Resumo executivo** local: score `0.6 * (100 - pct_local) + 0.4 * min(100, atrasados*6)` — fórmula explícita no código
- **Suprimentos:** novo `MapaControleService` com `search= bloco + pavimento` — **interpretação diferente** do resumo global (busca textual)

---

## Parte 3 — Pontos de confusão (gestor)

1. **Parâmetro `visao` (Geral/Detalhe):** continua no GET e no payload de filtros; **não altera nenhum cálculo** no backend nem no `analise_obra.js`. O seletor **foi retirado da barra rápida** (campo oculto; evita a expectativa de “mudar o zoom e mudar o dado”). Ainda é possível fixar `?visao=detalhe` na URL manualmente — **sem efeito nos números** até haver implementação no serviço.
2. **“Atrasados” (material) vs “blocos mais atrasados” (controle):** primeiro = flag `is_atrasado` em **ItemMapa**; segundo = **menor % médio** de execução em **ItemMapaServico** — palavra “atrasado” em ambos.
3. **“Concluído / andamento / parado” no controle:** derivado de texto/percentual com heurística; não é necessariamente o mesmo “concluído” que o gestor usa no canteiro.
4. **“Ocorrências críticas”:** conta heurística de texto/tags — não equivale a incidente regulatório.
5. **Diário só “aprovado”:** KPIs de campo ignoram RDO pendente/reprovado.
6. **Sem vínculo Project:** diário quase vazio; mensagem exibida — risco de achar que “não há problemas”.
7. **Cruzamento execução×material:** matching de chaves por normalização/substring — pode **não** encontrar par e subdimensionar risco.
8. **Ranking local “pendências”:** conta itens não ENTREGUE, não o mesmo que KPIs do topo em todos os casos.

---

## Parte 4 — Mapa de risco para ajustes futuros

| Área | Alteração | Risco |
|------|-----------|--------|
| `_status_to_ratio` / classificação texto | Mudar palavras-chave | **Alto** — altera todos os % e contagens de controle |
| `MapaControleService` KPIs | Mudar definição de sem_alocacao, atrasados | **Alto** — BI e Mapa de Controle compartilham serviço |
| `_classify_occurrence_severity` | Ajustar heurística | **Médio** — muda Situação, prioridades, críticos |
| `_classify_situacao` limiares (35, 15, 12…) | Só números do rótulo Situação | **Médio** |
| Filtro `visao` | Implementar efeito real no `AnaliseObraService` ou documentar como reservado | **Baixo** se só documentação; **médio** se começar a filtrar dados sem testes |
| Textos/template apenas | Tooltips, renomear rótulos | **Baixo** |
| Gráficos Chart.js | Cores/labels | **Baixo** |
| Cruzamento `_build_cruzamento` matching | Mudar lógica de join bloco/local | **Alto** — altera lista de risco e ações |

---

## Parte 5 — Recomendações futuras (sem implementação)

1. ~~**Remover ou implementar** o filtro “Zoom”~~ — **UI:** controle removido da barra (campo oculto). **Pendência:** implementar efeito no serviço ou ignorar `visao` explicitamente no código.
2. Renomear **“blocos mais atrasados”** para **“Eixos com menor % médio de execução”** ou similar; manter “atraso” só para material.
3. Subtítulo fixo no hero explicando que **Situação** combina três fontes com limiares internos.
4. Tooltip no card **Entregue sem alocar:** citar regra exata (`recebido > 0` e `alocado <= 0`) e exclusão `nao_aplica`.
5. Na seção diário, texto curto: **“Apenas RDOs aprovados no período.”**
6. Em **Ocorrências críticas**, nota: **“Classificação automática por palavras-chave; não substitui análise de SST.”**
7. Manter **alertas_semanticos** visíveis (já no payload) — reforçam não misturar domínios.
8. Revisão de produto: **cruzamento** por substring — documentar limitação ou melhorar chave (ex.: código de local único).

---

## Arquivos técnicos (mapa)

| Papel | Arquivo |
|-------|---------|
| Rotas página + API | `suprimentos/views_analise_obra.py` |
| Payload e regras | `suprimentos/services/analise_obra_service.py` |
| Materiais / KPIs pipeline | `suprimentos/services/mapa_controle_service.py` |
| UI | `suprimentos/templates/suprimentos/analise_obra.html` |
| Gráficos | `suprimentos/static/js/analise_obra.js` |
| Modelos | `ItemMapa`, `ItemMapaServico`, `ConstructionDiary`, `DiaryOccurrence`, `OccurrenceTag`, `Project`, `Obra` |
| Testes | `suprimentos/tests/test_analise_obra.py` |

---

## Apêndice A — Fichas no formato solicitado (elementos críticos)

### A.1 Situação (hero)

- **Nome exibido no BI:** Texto dinâmico em `meta.situacao_executiva.rotulo` (ex.: “Obra dentro do previsto”, “Obra em atenção”, “Obra com risco de atraso ou pressão operacional”)
- **Tipo:** Indicador textual / selo de nível (`ok` | `atencao` | `risco`)
- **Onde aparece:** Cabeçalho do BI (hero, ao lado do título da obra)
- **O que esse dado mostra de fato:** Uma síntese de **alerta operacional** obtida por somatório de “sinais” a partir de três fontes: média de execução física (controle), contagem de materiais atrasados, volume/criticidade de ocorrências no diário (aprovado)
- **Qual consulta/modelo/tabela/campo alimenta:** `_classify_situacao()` lê apenas agregados já calculados em `controle.kpis`, `suprimentos.kpis`, `diario.kpis`, `diario.prioridades` — não há SQL próprio
- **Qual regra de cálculo é usada:** Limiares numéricos no código (ex.: `pct < 35` +2 sinais; `atrasados >= 15` +2; `occ_crit >= 3` +2; `occ >= 12` +1) → faixas de `sinais` para escolher rótulo
- **Quais filtros alteram esse resultado:** Qualquer filtro que mude controle, suprimentos ou diário (lista na Parte 1)
- **Como interpretar gerencialmente:** Priorização para **onde olhar primeiro**, não decisão contratual isolada
- **Quando é um bom sinal:** Nível `ok` e poucos motivos
- **Quando é um alerta:** Nível `risco` ou lista longa de motivos
- **Erros prováveis:** Tratar como “atraso de obra” no sentido de cronograma master; confundir com lucro ou multa
- **Outro dado com nome parecido?** “Situação” em fichas do Mapa de Controle (campo `situacao` na célula) — outro contexto
- **Nome claro?** **Não** — “Situação” é genérico
- **Risco de inconsistência:** **Médio**

### A.2 “Entregue sem alocar” (card Fila, seção Material)

- **Nome exibido no BI:** “Entregue sem alocar” (lista no card Fila)
- **Tipo:** Indicador numérico (contagem)
- **Onde aparece:** Seção “4 · Material”, card com lista Sem pedido / SC sem PC / …
- **O que mostra de fato:** Número de linhas `ItemMapa` (não `ItemMapaServico`) com quantidade recebida na obra **>** 0 e quantidade alocada ao local **≤** 0, excluindo `nao_aplica=True`
- **Origem:** `MapaControleService.build_summary_payload` → `kpis.sem_alocacao`
- **Regra:** `item.quantidade_recebida_obra > 0 and item.quantidade_alocada_local <= 0`
- **Filtros:** `MapaControleFilters` derivados de categoria, local, prioridade, status SC/PC, busca material
- **Interpretação:** Material no pátio/obra sem destino administrado no sistema
- **Bom sinal:** Baixo em fase final com logística disciplinada
- **Alerta:** Alto com reclamações de falta no local
- **Erros:** Igualar a “sem alocação” do Radar/assistente ou do Dashboard SC (clique “Alocados” mostra outra coisa)
- **Nome parecido:** “Recebido sem alocação” no Mapa de Controle (mesma regra no serviço)
- **Nome claro?** **Razoável** se o gestor conhece “alocar ao local”
- **Risco de inconsistência:** **Médio** (outros módulos usam outras definições de “sem alocação”)

### A.3 Gráfico “Progressão dos eixos” (lista `blocos_mais_atrasados`)

- **Nome exibido no BI:** “Progressão dos eixos” — painel **“Mostrar gráfico por eixo (detalhe)”** (recolhido por padrão); subtítulo menciona eixos piores / limite 16 quando aberto
- **Tipo:** Gráfico de barras horizontais (Chart.js); **renderização adiada** até o utilizador abrir o collapse
- **O que mostra de fato:** **% médio de execução** por eixo (bloco ou setor+bloco), ordenado para mostrar os **menores** % primeiro (execução física mais fraca), com quota por setor
- **Origem:** `controle.blocos_mais_atrasados` ou `progressao_eixos_completo` ao expandir — dados de `ItemMapaServico` + `_status_to_ratio`
- **Regra:** Média de ratios por eixo; ranking “piores” = menor % (nome “atrasados” no código Python refere-se a **atraso de execução relativa**, não a campo “atrasado” de material)
- **Filtros:** Recorte físico e status_servico do **serviço**
- **Erros:** Ler “atrasados” como atraso de **compra** ou **cronograma master**
- **Risco inconsistência nome vs regra:** **Alto**

### A.4 Parâmetro `visao` (Geral / Detalhe)

- **Nome na UI (atual):** *não há seletor visível* — valor enviado por `<input type="hidden" name="visao">` (preserva links com `?visao=detalhe` e submissões do formulário).
- **Tipo:** Parâmetro GET / campo oculto do formulário
- **Origem:** `request.GET.visao` → `AnaliseObraFilters.visao`
- **Regra no cálculo:** **Nenhuma** — campo **não referenciado** em `AnaliseObraService` para agregações (apenas estrutura de filtros / opções)
- **Nota:** A remoção do dropdown elimina a **falsa expectativa** de mudança de dados ao “mudar o zoom”; o parâmetro ainda existe para compatibilidade de URL.

---

*Documento de diagnóstico. Revalidar após qualquer alteração em `analise_obra_service.py`, `mapa_controle_service.py`, `analise_obra.html` ou `analise_obra.js`.*
