# BI da Obra — documentação atual (2026)

Visão executiva unificada: execução física (Mapa de Controle), suprimentos, diário, GestControll, Central de Aprovações, restrições, TrackHub, RH e Mapa Geográfico.

## Rotas principais

| Item | Valor |
|------|--------|
| BI por obra | `/engenharia/analise-obra/` (`engenharia:analise_obra`) |
| **Portfólio multi-obra** | `/engenharia/analise-obra/portfolio/` (`engenharia:analise_obra_portfolio`) |
| Resumo PDF (por obra) | `/engenharia/analise-obra/resumo/` (`engenharia:analise_obra_resumo`) |
| API interna | `/api/internal/analise-obra/?obra=&secao=` (`suprimentos:analise_obra_api`) |

## Arquivos

| Área | Caminhos |
|------|----------|
| Views | `suprimentos/views_analise_obra.py` |
| Serviço BI | `suprimentos/services/analise_obra_service.py` |
| Serviço portfólio | `suprimentos/services/analise_obra_portfolio_service.py` |
| Links / fila resolver | `suprimentos/services/analise_obra_portfolio_links.py` |
| Templates | `analise_obra.html`, `analise_obra_portfolio.html` |
| CSS / JS | `analise_obra.css`, `analise_obra_ux.css`, `analise_obra_shell.js` |
| Snapshots | `BiObraKpiSnapshot`, `python manage.py bi_obra_snapshot` |
| Testes | `suprimentos/tests/test_analise_obra.py` |
| Grupo | `BI da Obra` (`accounts.groups.GRUPOS.BI_DA_OBRA`) |

## BI por obra

### Carregamento
1. **Shell (SSR):** hero, KPIs, execução física resumida, filtros, `meta`, `controle` básico.
2. **Lazy (AJAX):** seções pesadas via `data-secao` + `analise_obra.js`.
3. **Cache:** 120s por usuário/obra/filtros (`ANALISE_OBRA_CACHE_TTL_SECONDS`).

### Seções API (`secao`)
`meta`, `filtros`, `controle`, `suprimentos`, `diario`, `heatmap`, `cruzamento`, `gestcontroll`, `restricoes`, `trackhub`, `rh`, `mapa_geo`, `workflow_central`, `all`, `full`.

### Filtros
- **Barra:** obra, frente, período (30/60/90/todos + personalizado), datas.
- **Mais filtros:** recortes de mapa de controle, suprimentos e diário.

### Hero e UX
- KPIs clicáveis → âncora + drawer (`meta.hero_drawer`).
- Sparklines 7d via `BiObraKpiSnapshot`.
- Barra de ações prioritárias (`meta.acoes_prioritarias`).
- Resumo PDF → `analise_obra_resumo.html`.

## Portfólio multi-obra (gestor)

Visão consolidada de **todas as obras** acessíveis ao usuário, orientada a **resolver pendências**.

### O que mostra
- **Hero:** totais do portfólio (obras em alerta, média de avanço, restrições, suprimentos, TrackHub).
- **Resolver agora:** fila global priorizada (URGENTE → ROTINA) com botão **Resolver** → módulo correto.
- **Cards por obra:** situação, gargalo principal (exec×suprimento), ações, sparklines 7d, módulos resumidos.

### Fila de resolução (tipos)
| Tipo | Destino típico |
|------|----------------|
| TrackHub vencidas/abertas | `/trackhub/fila/?obra=` |
| Restrições vencidas | Impedimentos ou BI `#bloco-3` |
| Gargalo exec×suprimento | BI `#bloco-1b` + mapa no bloco |
| Suprimentos atrasados | Mapa `?status=atrasados` |
| RDOs / GestControll / diário | BI `#bloco-4` / `#bloco-2` |

### Filtros do portfólio
- **Período:** 30 / 60 / 90 / todos (início = menor data entre obras do escopo).
- **Exibir:** todas as obras ou somente com alerta (`somente_alerta=1`).

### Cache
- TTL **300s** por usuário + alerta + período (`ANALISE_OBRA_PORTFOLIO_CACHE_TTL_SECONDS`).
- Sparklines e KPIs hero usam snapshot diário quando disponível; módulos BI usam o período selecionado.

### Links úteis no menu
- Portfólio ↔ BI por obra (`Todas as obras` / `BI por obra`).
- Drill-down: cada card → BI da obra com mesmo preset de período na URL.

## Integrações (ambas as telas)

| Módulo | Origem |
|--------|--------|
| Execução física | Mapa de controle / `AmbienteVersao.layout` |
| Suprimentos | `MapaControleService` |
| Diário | `ConstructionDiary`, ocorrências |
| GestControll | `gestao_aprovacao` |
| Restrições | `impedimentos` |
| TrackHub | `trackhub.Pendencia` |
| RH / Mapa Geo / Central | lazy no BI por obra |

## Operação

```bash
# Snapshot diário (cron recomendado 1×/dia)
python manage.py bi_obra_snapshot

python manage.py bi_obra_snapshot --obra=123

python manage.py test suprimentos.tests.test_analise_obra
```

## Meta block (BI por obra)

`obra_id`, `gestao_obra_id`, `projeto_diario_id`, `kpis_hero`, `situacao_executiva`, `sparklines`, `acoes_prioritarias`, `hero_drawer`, `ambiente_id`, `periodo`.
