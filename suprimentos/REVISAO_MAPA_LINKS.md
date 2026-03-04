# Revisão: links e rotas do Mapa de Suprimentos

Documento gerado após revisão de **todo o código** relacionado ao mapa de suprimentos (links, rotas, views, templates, JS).

---

## Estrutura de URLs (lplan_central)

| Prefixo | Inclusão | Namespace |
|--------|----------|-----------|
| `/engenharia/` | `suprimentos.urls_engenharia` | `engenharia` |
| `/api/internal/` | `suprimentos.urls_api` | `suprimentos` |
| `/mapa/` | `mapa_obras.urls` | `mapa_obras` |

---

## Rotas usadas pelo mapa

### Engenharia (templates e navegação)

- `engenharia:mapa` → `/engenharia/mapa/` — tela principal do mapa
- `engenharia:exportar_excel` → `/engenharia/mapa/exportar-excel/`
- `engenharia:criar_item` → `/engenharia/mapa/criar-item/`
- `engenharia:novo_levantamento` → `/engenharia/mapa/novo-levantamento/`
- `engenharia:importar_sienge` → `/engenharia/mapa/importar-sienge/`
- `engenharia:criar_insumo` → `/engenharia/insumo/criar/`
- `engenharia:dashboard_2` → `/engenharia/dashboard-2/`

### API interna (suprimentos)

- `suprimentos:item_detalhe` → `/api/internal/item/<id>/detalhe/`
- `suprimentos:item_atualizar_campo` → `/api/internal/item/atualizar-campo/`
- `suprimentos:item_excluir` → `/api/internal/item/<id>/excluir/`
- `suprimentos:item_alocacoes_json` → `/api/internal/item/<id>/alocacoes/`
- `suprimentos:item_alocar` → `/api/internal/item/<id>/alocar/`
- `suprimentos:item_remover_alocacao` → `/api/internal/item/<id>/remover-alocacao/`
- `suprimentos:listar_locais` → `/api/internal/locais/`
- `suprimentos:listar_scs` → `/api/internal/scs/`
- `suprimentos:dashboard2_alocar` → `/api/internal/dashboard2/alocar/`

### Mapa Obras (seleção de obra)

- `mapa_obras:home` → `/mapa/` — listar obras / "Trocar Obra"
- `mapa_obras:selecionar` → `/mapa/selecionar/<id>/` — seta sessão e redireciona para o mapa

---

## Templates que estendem base_mapa.html

- `accounts/login.html`, `accounts/home.html`, `accounts/profile.html`
- `suprimentos/mapa_engenharia.html`
- `suprimentos/importar_sienge.html`
- `suprimentos/dashboard_2.html`

Todos usam os links do navbar: Dashboard, Mapa, Importar, Trocar Obra (engenharia:* e mapa_obras:home/selecionar).

---

## Context processor

- `mapa_obras.context_processors.obra_context` está em lplan_central/settings.py.
- Expõe `obra_atual` e `obras_disponiveis` para o dropdown "Selecionar Obra" no base_mapa.html.

---

## JavaScript (supplymap.js)

- URLs resolvidas pelo template: data-update-url, data-delete-url, form.action (criar item, criar insumo) vêm dos templates com {% url %}.
- URLs fixas no JS: /api/internal/item/${itemId}/detalhe/ e /api/internal/locais/?obra= — corretas para o projeto atual (raiz em /). Se no futuro o sistema for servido sob subpath (ex.: /lplan/), será necessário injetar base URL.

---

## Correções feitas nesta revisão

1. **views_engenharia.py** — Redirect após "novo levantamento" passou a usar `redirect(reverse('engenharia:mapa') + f'?obra={obra_id}')` em vez de `redirect(...).url`.
2. **mapa_engenharia.html** — Form "Criar Item" (#formCriarItem) ganhou `action="{% url 'engenharia:criar_item' %}"`.
3. **supplymap.js** — criarItem() passou a usar `form.action` em vez de URL fixa.

---

## Verificação geral

- Não há referências quebradas a rotas antigas (ex.: do projeto Mapa_Controle/supplymap).
- Os arquivos em Mapa_Controle/ são de outro projeto; o que está em uso é suprimentos/, mapa_obras/, templates/base_mapa.html e lplan_central/urls.py.
- CSRF: base_mapa tem meta csrf-token e JS usa getCsrfToken() em todos os POSTs; context processor csrf está em settings.
