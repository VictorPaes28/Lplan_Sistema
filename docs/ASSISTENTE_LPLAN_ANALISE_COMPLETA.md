# Assistente LPLAN — Análise completa (diagnóstico)

Documento de **inventário, regras conforme código, pontos de confusão, riscos e recomendações**, no mesmo espírito de `BI_DA_OBRA_ANALISE_COMPLETA.md`. **Não descreve implementações futuras**; apenas o que existe hoje no repositório.

---

## Parte 1 — Inventário funcional e fluxo

### 1.1 Superfície exposta (URLs)

| Rota (nome) | Método | Função |
|-------------|--------|--------|
| `assistente_lplan:home` | GET | Página principal do chat, histórico, sugestões, obra ativa |
| `set_session_project` | POST | Grava `selected_project_id` na sessão após validação de permissão |
| `perguntar` | POST | API JSON: pergunta → orquestrador → resposta estruturada |
| `feedback` | POST | Registo de feedback (útil/não, correção de intenção) |
| `download_rdo_period_pdf` | GET | Download de PDF RDO por período via token assinado (`t=`) |

Definições em `assistente_lplan/urls.py`.

### 1.2 Quem pode usar

- Todas as vistas referidas usam `@login_required`; **não** há `require_group` neste módulo — qualquer utilizador autenticado pode chamar `perguntar` e `feedback`.
- O **escopo de dados** (quais projetos/obras aparecem) vem de `AssistantPermissionService`: staff/superuser como `admin` (acesso amplo); caso contrário, projetos via `ProjectMember`/`ProjectOwner`, e obras de gestão via `WorkOrderPermission`. Isto filtra resolução de projeto e consultas nos serviços.

### 1.3 Home do assistente

- Contexto montado em `build_assistant_home_context` (`suggested_questions.py`): obra ativa (`get_selected_project`), ou **uma única obra acessível** inferida automaticamente (persistência na sessão), ou lista de obras para escolha.
- Grupos de sugestões por tema (visão/pendências, mapa, RDO, gestão) com textos que citam código da obra e datas (hoje/ontem).
- Histórico na UI: mistura de sessão e persistência (`AssistantResponseLog` via `_load_persistent_history`).

### 1.4 Fluxo `perguntar`

1. Corpo JSON: `pergunta`, opcionalmente `contexto` (ex.: `selected_project_id`).
2. **Cache** (`CACHE_TTL_SECONDS = 1000`): chave por utilizador + pergunta normalizada + contexto serializado. Hit devolve payload em cache (com `_normalize_response_payload`).
3. `AssistantOrchestrator.run`: clarificação de obra/utilizador quando necessário, deteção de intenção, despacho por intenção.
4. Pós-processamento: `_ensure_actionability`, `_apply_primary_action_highlight`, e em muitos casos `LLMProvider.improve_summary` (exceto domínios `inteligencia`/`clarification` e intenções de relatório mapa/RDO período).
5. Persistência: `AssistantQuestionLog` + `AssistantResponseLog` com payload JSON.
6. Resposta JSON alinhada ao que o frontend espera (`summary`, `radar_score`, `cards`, `table`, `alerts`, `suggested_replies`, `question_log_id`, etc.).

### 1.5 O que a UI desenha de facto (`assistant_ui.js`)

A função `renderResponse` monta, **nesta ordem**:

- Resumo em texto (`summary`)
- Badges
- **Radar** (se `radar_score` não for nulo)
- **Cards** (apenas `title` e `value` — **não** usa `subtitle` nem `tone` para estilo)
- Tabela, timeline, alertas, sugestões rápidas, bloco de feedback

**Lacuna importante:** os campos `actions` e `links` devolvidos pelo backend (e preenchidos em vários serviços, clarificação ambígua e pós-radar) **não são renderizados** no HTML da resposta. O utilizador **não vê** botões nem links estruturados vindos do `AssistantResponse`, embora existam no JSON e em `_normalize_response_payload`.

O radar mostra `recommended_action.label` na secção “Ação recomendada”, mas **não** há renderização genérica da lista `actions`/`secondary_actions` como botões.

### 1.6 PDF RDO por período

- Intenção `relatorio_rdo_periodo` → `DiarioAssistantService.relatorio_rdo_periodo_pdf`: gera token assinado (`RDO_PERIOD_SIGN_SALT`, validade 7 dias) com utilizador, projeto e datas.
- Download em `download_rdo_period_pdf`: valida token, utilizador, projeto no escopo, gera bytes via `generate_rdo_period_pdf_bytes`.

---

## Parte 2 — Pipeline técnico: intenções e serviços

### 2.1 Lista canónica de intenções

Constantes em `assistente_lplan/services/intents.py` e conjunto `SUPPORTED_INTENTS`. Valores usados no despacho:

| Constante | Valor (string) |
|-----------|----------------|
| `INTENT_LOCATE_SUPPLY` | `localizar_insumo` |
| `INTENT_LIST_OBRA_PENDING` | `listar_pendencias_obra` |
| `INTENT_LIST_PENDING_APPROVALS` | `listar_aprovacoes_pendentes` |
| `INTENT_RDO_BY_DATE` | `consultar_rdo_por_data` |
| `INTENT_OBRA_SUMMARY` | `resumo_obra` |
| `INTENT_USER_STATUS` | `status_usuario` |
| `INTENT_UNALLOCATED_ITEMS` | `itens_sem_alocacao` |
| `INTENT_REJECTED_REQUESTS` | `solicitacoes_reprovadas` |
| `INTENT_OBRA_BOTTLENECKS` | `gargalos_obra` |
| `INTENT_INTELIGENCIA_INTEGRADA` | `inteligencia_obra_integrada` |
| `INTENT_RELATORIO_LOCAL_MAPA` | `relatorio_local_mapa` |
| `INTENT_RELATORIO_RDO_PERIOD` | `relatorio_rdo_periodo` |
| `INTENT_FALLBACK` | `fallback` |

### 2.2 Deteção de intenção

- `LLMProvider.detect_intent(question)`; se devolver `(intent, entities, confidence)` com `confidence >= 0.6`, usa-se o resultado do LLM.
- Caso contrário (ou sem LLM), **parser baseado em regras** (`fallback_parser.parse`) com confiança e candidatos alternativos.

### 2.3 Despacho (`AssistantOrchestrator._dispatch`)

Mapeamento direto intenção → método de serviço (trecho central em `orchestrator.py`):

- Suprimentos: `localizar_insumo`, `itens_sem_alocacao`, `relatorio_local_mapa`
- Obras: `listar_pendencias_obra`, `resumo_obra`
- Aprovações: `listar_aprovacoes_pendentes`, `solicitacoes_reprovadas`
- Diário: `consultar_rdo_por_data`, `relatorio_rdo_periodo_pdf`
- Utilizadores: `status_usuario`
- Cross-domain: `gargalos_obra`, `inteligencia_integrada`
- `fallback`: mensagens via `MessageCatalog`
- Intenção desconhecida: resposta “não suportado” com `MessageCatalog`

### 2.4 Clarificação e ambiguidade

- `_clarification_response` devolve `actions` e `links` para Diário, GestControll e Mapa — **mesma lacuna de UI** (não aparecem no chat).
- Sugestões de perguntas semelhantes via `SequenceMatcher` sobre pools de exemplos por intenção (`_intent_example_questions`).

### 2.5 Consolidação com radar

`ObrasAssistantService._attach_radar` e `CrossDomainAssistantService` aplicam `RadarObraService(project).build()` e **concatenam**:

- `cards`, `timeline`, `alerts`, `actions`, `links` da resposta base com as do radar
- `raw_data["radar"]` com `raw_components` (métricas internas)

Efeito na UI: além dos cards do serviço (ex.: pendências), aparecem cards do radar (“Radar de risco”, “Nivel”, “Tendencia”) e timeline/agregados do radar — pode parecer **dupla camada** de indicadores para o mesmo pedido.

---

## Parte 3 — Dados, definições e alinhamento com KPI

### 3.1 `core/kpi_queries.py` (contrato explícito)

Funções usadas pelo assistente e documentadas como canónicas:

- `count_pedidos_pendentes`: `WorkOrder` com `status="pendente"` e `obra__project=project`.
- `count_diarios_nao_aprovados`: diários **excluindo** `DiaryStatus.APROVADO` (qualquer outro estado conta).
- `count_itens_sem_alocacao_efetiva` / `queryset_itens_sem_alocacao_efetiva`: `ItemMapa` na obra de mapa resolvida por `mapa_obra_for_project`, `quantidade_planejada > 0`, soma de alocações `<= 0`. Comentário no código: alinhado a `RadarObraService._calc_suprimentos` para a parte “itens sem alocação”.

### 3.2 “Itens sem alocação” em três sítios (comparação honesta)

| Origem | Regra principal |
|--------|------------------|
| `itens_sem_alocacao` (SuprimentosAssistantService) | `ItemMapa` no **conjunto de obras do escopo** (`_obras_scope_qs`), `quantidade_planejada > 0`, `total_alocado <= 0`, limite 30 linhas na tabela |
| KPI / pendências / gargalos | `mapa_obra_for_project(project)` — **um** mapa por projeto; mesma lógica de soma de alocações |
| Radar (`_calc_suprimentos`) | Conta `itens_sem_aloc` no `mapa_obra` ligado ao projeto; **também** entra “recebimentos não distribuídos”, prazos, etc., no **score** do bloco suprimentos |

**Conclusão:** o **número** “itens sem alocação” do card em pendências/gargalos deve coincidir com o KPI **para o mesmo `Project`**. A lista detalhada da intenção `itens_sem_alocacao` pode **diferir** se o escopo de obras do assistente não for o mesmo que um único `mapa_obra_for_project` (multi-obra no utilizador). O **BI da Obra** pode ainda usar outras definições (ex.: “recebido sem alocar”) — isso é tratado no doc do BI; aqui o foco é consistência interna assistente + `kpi_queries` + radar.

### 3.3 “Diários pendentes” vs “Taxa de aprovação diário”

- **Pendências:** `count_diarios_nao_aprovados` — **todos** os não aprovados (rascunho, revisão, aguardando gestor, etc.).
- **Resumo (`resumo_obra`):** card “Taxa de aprovacao diario” = `diarios_aprovados / total_diarios` (percentagem). Conceito **diferente** de “quantos diários ainda abertos no fluxo”.

### 3.4 Radar de obra — pesos e nuances

- Score final: média ponderada dos blocos suprimentos (0,3), aprovações (0,25), diário (0,25), histórico (0,2), truncada 0–100.
- Níveis: BAIXO / MÉDIO / ALTO por faixas de score; tendência compara índices de “problemas” em janelas 7/14/30 dias.
- Em `_calc_aprovacoes`, a variável `prev_avg_days` é preenchida com **`.count()`** de `StatusHistory` num intervalo de datas — o nome sugere “média de dias”, mas o código usa **contagem de eventos** (contribuição `* 0.1` no score). Quem interpretar o `raw_components` deve tratar o campo pelo que **faz**, não pelo nome.

### 3.5 LLM

- Resumo melhorado (`improve_summary`) na maioria dos domínios.
- `inteligencia_integrada`: narrativa opcional (`narrate_obra_intelligence`) ancorada em factos derivados do radar; fallback textual se o LLM não devolver nada.

---

## Parte 4 — Pontos de confusão para utilizador e produto

1. **`actions` / `links` invisíveis** — O backend prepara navegação rápida; o chat não mostra. O utilizador depende só do texto, badges, tabela e (no radar) do label da ação recomendada parcial.
2. **Cards duplicados ou densos** — Junção serviço + radar aumenta cards e timelines; rótulos como “Pedidos pendentes” (resumo) e “Radar de risco” aparecem no mesmo bubble sem hierarquia explícita na UI.
3. **`tone` e `subtitle` nos cards** — Schema pode incluir; JS ignora — perda de semântica visual.
4. **“Diário pendente”** no card vs **“taxa de aprovação”** — palavras próximas, métricas diferentes.
5. **Cache de 1000 s** — Mesma pergunta+contexto pode devolver resposta antiga sem indicador na UI de que é cache.
6. **Ambiguidade** — Mensagens e sugestões ajudam, mas links de clarificação não aparecem como botões (ver item 1).

---

## Parte 5 — Mapa de risco para alterações

| Área | Risco |
|------|--------|
| `kpi_queries` | Qualquer alteração em contagem propaga-se a BI, assistente, gargalos e radar parcialmente; exigir checklist de consumidores |
| `RadarObraService` | Pesos e fórmulas são opacos para o utilizador; mudanças alteram scores e tendências sem migração de dados |
| `AssistantOrchestrator` | Novo intent exige despacho, mensagens, exemplos de clarificação e eventual entrada no LLM |
| Frontend `assistant_ui.js` | Campos novos no JSON são ignorados se não forem mapeados; `actions`/`links` já mostram esse débito |
| Permissões | Ausência de grupo na view: qualquer user autenticado chama API; mitigação é só no scope de projetos |
| PDF/token RDO | Alterar salt ou campos do token invalida links antigos; validade 7 dias |
| Logs/retention | `MAX_LOGS_PER_USER` / `LOG_RETENTION_DAYS` e cleanup em `_cleanup_user_logs` — política de privacidade e suporte |

---

## Parte 6 — Recomendações (sem implementar)

1. **Produto:** Decidir se `actions`/`links` devem ser exibidos no chat; se sim, especificar layout (primário/secundário) e acessibilidade.
2. **UX:** Separar visualmente “resposta do domínio” vs “camada radar” ou fundir num único bloco coerente para evitar sobrecarga.
3. **Dados:** Documentar no UI o significado de “Diários pendentes” (fluxo amplo) vs “taxa de aprovação”.
4. **Operação:** Expor ao utilizador quando a resposta vem de cache (ou reduzir TTL em ambientes dinâmicos).
5. **Código:** Renomear ou documentar `prev_avg_days` no radar para refletir contagem de histórico, ou corrigir a métrica se a intenção era realmente média em dias.
6. **Segurança/compliance:** Reavaliar se endpoints do assistente devem restringir-se a grupos específicos (além do scope de projeto).

---

## Apêndice A — Ficheiros de referência rápida

| Ficheiro | Papel |
|----------|--------|
| `assistente_lplan/views.py` | Rotas, cache, logs, PDF, feedback |
| `assistente_lplan/services/orchestrator.py` | Intents, despacho, clarificação, summary LLM |
| `assistente_lplan/services/obras_service.py` | Pendências, resumo, radar attach |
| `assistente_lplan/services/suprimentos_service.py` | Insumo, sem alocação, relatório local mapa |
| `assistente_lplan/services/cross_domain_service.py` | Gargalos, inteligência integrada |
| `assistente_lplan/services/radar_obra_service.py` | Score, causas, ações recomendadas |
| `core/kpi_queries.py` | KPIs partilhados |
| `assistente_lplan/static/assistente_lplan/js/assistant_ui.js` | Renderização real da resposta |
| `assistente_lplan/schemas.py` | `AssistantResponse` |
| `assistente_lplan/services/suggested_questions.py` | Contexto da home |

---

## Apêndice B — Feedback e aprendizagem

- `feedback` chama `GuidedLearningService.register_feedback` com `question_log_id`, `helpful`, correções de intenção/entidades e nota.
- Mensagem de sucesso indica que regras sugeridas ficam **pendentes de aprovação** (fluxo fora do âmbito deste diagnóstico).

---

*Documento gerado com base na leitura do código no repositório; revisão após alterações grandes em `assistente_lplan` ou `core/kpi_queries`.*
