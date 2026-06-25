# BI da Obra — documentação atual (2026)

Visão executiva unificada: execução física (Mapa de Controle), suprimentos, diário, GestControll, Central de Aprovações, restrições, TrackHub, RH e Mapa Geográfico.

## Rota e arquivos

| Item | Valor |
|------|--------|
| URL página | `/engenharia/analise-obra/` (`engenharia:analise_obra`) |
| URL resumo PDF | `/engenharia/analise-obra/resumo/` (`engenharia:analise_obra_resumo`) |
| API interna | `/api/internal/analise-obra/?obra=&secao=` (`suprimentos:analise_obra_api`) |
| View HTML | `suprimentos/views_analise_obra.py` |
| Serviço | `suprimentos/services/analise_obra_service.py` |
| Template | `suprimentos/templates/suprimentos/analise_obra.html` |
| CSS | `suprimentos/static/suprimentos/css/analise_obra.css`, `analise_obra_ux.css` |
| JS | `analise_obra.js` (lazy), `analise_obra_ux.js` (drawer/sparklines), `analise_obra_shell.js` (tema/sidebar) |
| Snapshots KPI | model `BiObraKpiSnapshot`, comando `python manage.py bi_obra_snapshot` |
| Testes | `suprimentos/tests/test_analise_obra.py` |
| Grupo Django | `BI da Obra` (`accounts.groups.GRUPOS.BI_DA_OBRA`) |

## Arquitetura de carregamento

1. **Shell (SSR):** hero, KPIs, execução física resumida, filtros, `meta`, `controle` básico.
2. **Lazy (AJAX):** seções pesadas via `data-secao` + `analise_obra.js`.
3. **Cache:** 120s por usuário/obra/filtros (`ANALISE_OBRA_CACHE_TTL_SECONDS`).

### Seções (`secao` na API)

`meta`, `filtros`, `controle`, `suprimentos`, `diario`, `heatmap`, `cruzamento`, `gestcontroll`, `restricoes`, `trackhub`, `rh`, `mapa_geo`, `workflow_central`, `all`, `full`.

## Filtros

### Barra principal
- Obra, frente (`front`), data início/fim.

### Mais filtros (colapsável)
- **Mapa de controle:** setor, bloco, pavimento, unidade, atividade, status execução.
- **Suprimentos:** status, categoria, prioridade, local, busca.
- **Diário:** tag ocorrência, busca texto, responsável.

**Nota:** frente afeta **Diário** e **Restrições**. Suprimentos e mapa de controle usam filtros de obra/recorte físico.

## Hero e UX

- **4 KPIs clicáveis** → âncora da seção + drawer contextual (`meta.hero_drawer` via JSON).
- **Sparklines 7 dias** → `BiObraKpiSnapshot` (gravado ao abrir o BI + comando cron).
- **Barra ações prioritárias** → `meta.acoes_prioritarias` (+ enriquecimento após cruzamento/TrackHub).
- **Situação executiva** → `meta.situacao_executiva` (motivos no clique).
- **Baseline planejado × real** → curva linear `Project.start_date` / `end_date` vs avanço físico (`meta.baseline_planejamento`).
- **Resumo PDF** → página de impressão (`analise_obra_resumo.html`).

## Integrações

| Módulo | Origem no serviço |
|--------|-------------------|
| Execução física | `AmbienteVersao.layout` / mapa controle |
| Suprimentos | `MapaControleService` / `ItemMapa` |
| Diário | `ConstructionDiary`, `DiaryOccurrence` |
| GestControll | `gestao_aprovacao` via `_resolve_gestao_obra` → `meta.gestao_obra_id` |
| Restrições | `impedimentos` (obra GestControll) |
| TrackHub | pendências da obra |
| RH | `recursos_humanos` |
| Mapa Geo | `mapa_geo` (projeto diário) |
| Central | `workflow_aprovacao` |

## Clicabilidade (padrão UX)

- Números/linhas com `stat-row--link` ou `›` → módulo filtrado.
- Heatmap → `/engenharia/mapa-controle/?obra=&bloco=&pavimento=`.
- Funil suprimentos → `/engenharia/mapa/?obra=&status=...`.
- Cruzamento → mapa controle ou suprimentos por local.

## Removido (legado)

- Chart.js na página BI.
- API `drilldown` e parâmetro `visao` na UI.
- CSS/JS duplicados em `suprimentos/static/js/analise_obra.js` (raiz).

## Operação

```bash
# Snapshot diário (cron recomendado 1×/dia)
python manage.py bi_obra_snapshot

# Snapshot de uma obra
python manage.py bi_obra_snapshot --obra=123

# Testes
python manage.py test suprimentos.tests.test_analise_obra
```

## Meta block (campos principais)

`obra_id`, `gestao_obra_id`, `projeto_diario_id`, `kpis_hero`, `situacao_executiva`, `sparklines`, `acoes_prioritarias`, `hero_drawer`, `baseline_planejamento`, `ambiente_id`, `periodo`.
