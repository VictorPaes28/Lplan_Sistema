# Contratos semânticos de indicadores — Lplan (referência densa)

Documento **normativo interno**: cada linha descreve **o que o código faz hoje** ou **onde há mais de uma definição possível**. Serve para alinhar BI, telas, assistente e radar sem depender de interpretação solta.

---

## Índice

1. [Identidade de obra entre módulos](#1-identidade-de-obra-entre-módulos)  
2. [Gestão — `WorkOrder` (GestControll)](#2-gestão--workorder-gestcontroll)  
3. [Gestão — `Approval` e tempo de resposta](#3-gestão--approval-e-tempo-de-resposta)  
4. [Core — `ConstructionDiary` e `DiaryOccurrence`](#4-core--constructiondiary-e-diaryoccurrence)  
5. [Suprimentos — `ItemMapa` e três definições de “sem alocação”](#5-suprimentos--itemmapa-e-três-definições-de-sem-alocação)  
6. [Mapa de Controle (`MapaControleService`)](#6-mapa-de-controle-mapacontroleservice)  
7. [Radar (`RadarObraService`)](#7-radar-radarobraservice)  
8. [Módulo canônico `core/kpi_queries`](#8-módulo-canônico-corekpi_queries)  
9. [Matriz de colisão (o que nunca pode ser comparado direto)](#9-matriz-de-colisão-o-que-nunca-pode-ser-comparado-direto)  
10. [Referência rápida de arquivos](#10-referência-rápida-de-arquivos)

---

## 1. Identidade de obra entre módulos

| Entidade | Modelo | Chave usada para cruzar |
|----------|--------|-------------------------|
| Projeto do diário | `core.Project` | `id`, `code` (texto único, alinhado ao Sienge na prática) |
| Obra da gestão | `gestao_aprovacao.Obra` | `project` → FK opcional para `core.Project` |
| Obra do mapa | `mapa_obras.Obra` | `codigo_sienge` deve coincidir com `Project.code` para joins |

**Risco operacional:** se `gestao_aprovacao.Obra.project` estiver nulo ou `mapa_obras.Obra.codigo_sienge` divergir de `Project.code`, contagens “por obra” **não fecham** entre Diário, Gestão e Mapa — o problema é **cadastro**, não fórmula.

---

## 2. Gestão — `WorkOrder` (GestControll)

**Modelo:** `gestao_aprovacao.models.WorkOrder` (`obra` FK obrigatória para `gestao_aprovacao.Obra`).

### Status canônicos (`STATUS_CHOICES`)

| Valor DB | Label |
|----------|--------|
| `rascunho` | Rascunho |
| `pendente` | Pendente Aprovação |
| `aprovado` | Aprovado |
| `reprovado` | Reprovado |
| `reaprovacao` | Reaprovação |
| `cancelado` | Cancelado |

### Onde cada métrica usa o quê

| Métrica | Filtro / regra | Observação |
|---------|----------------|------------|
| **Pendentes “fila de aprovação”** | `status='pendente'` | Usado em `detail_obra` (`workorders_pendentes`), assistente (`core.kpi_queries.count_pedidos_pendentes`), radar (vários trechos). |
| **Aguardando ação do aprovador (modelo)** | `status in ('pendente','reaprovacao')` | Método `WorkOrder.precisa_aprovacao` (aprox. linha 418 em `models.py`) — **não** é o mesmo que só `pendente`. |
| **Lembretes automáticos** | `status in ('pendente','reaprovacao')` | `gestao_aprovacao/management/commands/enviar_lembretes.py` — números de “pendentes” por e-mail **≠** KPI só `pendente`. |
| **Pedidos enviados no período (capacidade)** | `data_envio` entre datas | `desempenho_equipe_api`: `buscar_pedidos_recebidos` filtra por `data_envio`. |
| **Tempo até decisão (radar)** | Média em dias entre `created_at` do pedido e `data_aprovacao` | `RadarObraService._calc_aprovacoes` — **não** é a mesma base que a API de desempenho (que usa `Approval`). |

**Tipo de solicitação** (`tipo_solicitacao`): `contrato`, `medicao`, `ordem_servico`, `mapa_cotacao` — útil para segmentar BI; hoje nem todo agregado quebra por esse campo.

---

## 3. Gestão — `Approval` e tempo de resposta

**Modelo:** `gestao_aprovacao.models.Approval` — `decisao` ∈ `aprovado` | `reprovado`; histórico com `tags_erro` (M2M) em reprovações.

### API Desempenho da equipe (`desempenho_equipe_api`)

| Campo | Uso |
|-------|-----|
| Janela | `Approval.created_at` entre `agora - dias` e `agora`; `dias` ∈ {7, 15, 30, 60, 90}. |
| Escopo empresa | Responsável de empresa: `work_order__obra__empresa_id__in=empresas_ids`. Admin: sem filtro de empresa. |
| Início do SLA | `work_order.data_envio or work_order.created_at` |
| Fim | `approval.created_at` |
| Unidade | Horas `(fim - início).total_seconds() / 3600` |
| SLA | 24h — `% fora do SLA` sobre lista de tempos válidos (≥ 0). |
| Limite | `MAX_APPROVALS = 500` por consulta — extremos do período podem subcontar. |

**Arquivo:** `gestao_aprovacao/views.py` (funções aninhadas `buscar_aprovacoes`, `processar_aprovacoes`, `buscar_retrabalho`).

### Retrabalho (fluxo)

`StatusHistory` com `status_anterior='reprovado'` e `status_novo='reaprovacao'` no período — usado na mesma API para indicar retrabalho.

### Desempenho de solicitantes

`desempenho_solicitantes_api` — métricas por solicitante (reprovações, tags, tempos); **período e escopo** seguem lógica própria na mesma área do arquivo (~3885+).

---

## 4. Core — `ConstructionDiary` e `DiaryOccurrence`

### Status (`DiaryStatus` — campo 2 caracteres)

| Código | Significado |
|--------|-------------|
| `PR` | Preenchendo |
| `SP` | Salvamento Parcial (rascunho) |
| `AG` | Aguardando aprovação do gestor |
| `RG` | Reprovado pelo gestor |
| `RV` | Revisar (legado) |
| `AP` | Aprovado |

### Duas métricas de “pendência” que não devem ser misturadas

| Nome sugerido | Definição | Uso típico |
|-----------------|-----------|------------|
| `diarios_nao_aprovados` | `status != AP` | `core.kpi_queries.count_diarios_nao_aprovados`; radar/gargalos “amplo”. |
| `diarios_aguardando_gestor` | `status == AG` | Listagem `report_list_view` (`pending_approval_diaries`); fila do gestor. |

**Listagem geral:** `core/frontend_views.py` — `report_list_view` filtra `ConstructionDiary` por projeto selecionado + filtros GET (`search`, datas, `status`).

### Radar — subscore “diário” (`_calc_diario`)

- Janelas: 7 e 30 dias (`date` do diário).
- “Crítico”: texto não vazio em `stoppages`, `imminent_risks`, `accidents` ou `incidents` (campos do modelo).
- `DiaryOccurrence`: contagem e subconjunto com tags contendo `atraso`, `risco`, `paralisa` (icontains).

Isso **não** é o mesmo que “quantos diários não aprovados” — é **densidade de risco em texto/ocorrências**.

---

## 5. Suprimentos — `ItemMapa` e três definições de “sem alocação”

**Modelo:** `suprimentos.models.ItemMapa` — planejamento por local; alocações em `AlocacaoRecebimento` (`related_name` em `ItemMapa`: `alocacoes`).

### A — Canônico assistente/radar suprimentos (`core.kpi_queries`)

- Base: `obra = mapa_obras.Obra` com `codigo_sienge=project.code` e `ativa=True`.
- `ItemMapa`: `quantidade_planejada > 0`.
- `annotate(total_alocado=Coalesce(Sum('alocacoes__quantidade_alocada'), 0))`.
- Conta linhas com `total_alocado <= 0`.

**Não** filtra `nao_aplica` (ver colisão §9).

### B — Radar histórico (`_calc_historico`)

Mesma ideia de soma, mas em subconjuntos com **janela em `atualizado_em`** (7d vs 7d anterior) para tendência — **número diferente** do total estático da obra.

### C — Mapa de Controle (`MapaControleService`)

- Base: `ItemMapa.objects.filter(obra=..., nao_aplica=False)` + annotate de soma.
- KPI `sem_alocacao` no **summary**: `quantidade_recebida_obra > 0` **e** `quantidade_alocada_local <= 0` — ou seja, **material já recebido na obra** sem alocar ao local, **não** “planejado sem nenhuma alocação” como em (A).

**Arquivo:** `suprimentos/services/mapa_controle_service.py` — `build_summary_payload`, `_matches_status` para filtro `sem_alocacao`.

### Outros KPIs do Mapa de Controle (mesmo serviço)

| Chave JSON | Significado (lógica no código) |
|------------|--------------------------------|
| `sem_sc` | Sem número de SC preenchido |
| `sem_pc` | Tem SC, não tem PC |
| `sem_entrega` | Tem PC, `quantidade_recebida_obra <= 0` |
| `sem_alocacao` | Ver (C) |
| `atrasados` | `item.is_atrasado` |
| `percentual_medio_alocacao` | Média de `percentual_alocado_porcentagem` |

Rankings: por local, categoria, fornecedor; `distribuicao_status` usa `status_etapa`; `quem_cobrar` usa campo `quem_cobrar`.

---

## 6. Mapa de Controle (`MapaControleService`)

- **Entrada:** uma `mapa_obras.Obra` + `MapaControleFilters` (categoria, local, prioridade, status textual da etapa, busca, limite).
- **Contrato documentado no código:** docstring da classe (`kpis`, `ranking`, `distribuicao_status`, `quem_cobrar`, `filtros`).
- **View:** `suprimentos/views_controle.py` — `_layer_aggregates` para camada **serviços** (`ItemMapaServico`) é **outro** objeto (progresso/custo), não confundir com `ItemMapa` do mapa de cotação.

---

## 7. Radar (`RadarObraService`)

**Arquivo:** `assistente_lplan/services/radar_obra_service.py`.

### Pesos do score final

`suprimentos` 30%, `aprovacoes` 25%, `diario` 25%, `historico` 20% — método `_weighted_score`.

### Subscores (resumo)

| Bloco | Principais entradas |
|-------|---------------------|
| `_calc_suprimentos` | Itens sem aloc (soma), prazo vencido/próximo, recebimento não distribuído, etc. |
| `_calc_aprovacoes` | Pendentes, média dias até `data_aprovacao`, reprovações recentes em `Approval` |
| `_calc_diario` | Diários “críticos” por campos de texto + ocorrências tagueadas |
| `_calc_historico` | Índice agregando pendências de pedido, diário crítico, itens sem aloc com janela de data, reprovações 30d, top tags |

**Classificação:** `score <= 30` BAIXO; `<= 60` MÉDIO; senão ALTO. **Tendência:** `determine_trend` compara índices 7d com janelas anteriores.

**Importante:** o radar é **derivado**; comparar “score radar” com um único KPI do BI só faz sentido se o BI reproduzir os **mesmos** sub-ingredientes.

---

## 8. Módulo canônico `core/kpi_queries`

**Arquivo:** `core/kpi_queries.py`.

Funções expostas para **alinhamento** entre assistente e futuros relatórios:

- `count_pedidos_pendentes` — só `pendente`.
- `count_diarios_nao_aprovados` / `count_diarios_aguardando_gestor`.
- `queryset_itens_sem_alocacao_efetiva` / `count_itens_sem_alocacao_efetiva` — definição **(A)**.

**Não cobre:** Mapa de Controle (C), nem janelas do radar (B).

---

## 9. Matriz de colisão (o que nunca pode ser comparado direto)

| Conceito | Definição A (kpi_queries / radar suprimentos) | Definição B (Mapa de Controle) | Definição C (radar histórico) |
|----------|-----------------------------------------------|----------------------------------|--------------------------------|
| “Sem alocação” | Planejado > 0 e soma alocações ≤ 0 | Recebido na obra > 0 e alocado no local ≤ 0 | Igual ideia a (A) mas **filtrado por datas** em `atualizado_em` |

| Outra colisão | Detalhe |
|---------------|---------|
| `nao_aplica` | `MapaControleService` exclui `nao_aplica=True`; `kpi_queries` e `_calc_suprimentos` **não** excluem — mesma obra pode ter contagens diferentes. |
| Tempo de aprovação | API desempenho: deltas por `Approval`; radar: média via datas no `WorkOrder` — **duas histórias** para “quanto tempo leva”. |
| Pedido “pendente” | KPIs estritos usam só `pendente`; lembretes e `precisa_aprovacao` incluem `reaprovacao`. |
| Diário “pendente” | “Não APROVADO” ≠ “só AGUARDANDO gestor”. |

---

## 10. Referência rápida de arquivos

| Área | Arquivo principal |
|------|-------------------|
| Lista relatórios / filtros diário | `core/frontend_views.py` (`report_list_view`) |
| Pedidos / APIs gestão | `gestao_aprovacao/views.py` |
| Modelos pedido/aprovação | `gestao_aprovacao/models.py` |
| Lembretes pedidos | `gestao_aprovacao/management/commands/enviar_lembretes.py` |
| Mapa controle (API/página) | `suprimentos/views_controle.py`, `suprimentos/services/mapa_controle_service.py` |
| Radar | `assistente_lplan/services/radar_obra_service.py` |
| KPIs reutilizáveis | `core/kpi_queries.py` |
| Assistente obras / cross | `assistente_lplan/services/obras_service.py`, `cross_domain_service.py` |

---

*Última revisão: alinhado ao código do repositório; ao alterar qualquer filtro acima, atualizar este arquivo e, se possível, centralizar a regra em `kpi_queries` ou em um serviço único por domínio.*
