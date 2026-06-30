# Auditoria de Código Morto, Legado e Estrutura

> Data: 2026-06 · `.claude/worktrees/` ignorado (worktree git duplicado).
> Projeto ativo: `lplan_central` (ver `INSTALLED_APPS` em `settings.py:43-70`).

---

## Parte 1 — Código morto / legado

### 1.1 Seguro de remover (confiança ALTA — confirmar com 1 grep antes)

> Procedimento: para cada item, busque o nome no projeto inteiro. Se só aparecer na própria definição (ou em `.claude/worktrees/`), pode remover. Depois rode `python manage.py check`.

**Templates órfãos (views redirecionam / não renderizam):**
| Template | Evidência |
|----------|-----------|
| `gestao_aprovacao/templates/obras/list_obras.html` | `list_obras()` (`views.py:3922-3927`) só faz `redirect('central_project_list')` |
| `gestao_aprovacao/templates/obras/detail_obra.html` | `detail_obra()` (`views.py:3971-3998`) só redireciona |
| `gestao_aprovacao/templates/obras/delete_user_confirm.html` | `delete_user()` (`views.py:4989-4990`) redireciona com modal JS |
| `gestao_aprovacao/templates/obras/central_send_confirm.html` | `views_central_dispatch.py:22-60` redireciona direto |
| `core/templates/core/pdf_template.html` (~1087 linhas) | PDF do diário usa ReportLab (`core/utils/pdf_generator.py`); HTML legado |
| `core/templates/core/diario_pdf.html` | nenhuma referência no repo |
| `gestao_aprovacao/templates/base.html` | "shadowed": loader resolve `core/templates/base.html` primeiro (core vem antes em INSTALLED_APPS) |
| `suprimentos/templates/suprimentos/partials/mapa_kpis_snippet.html` | KPIs estão inline em `mapa_engenharia.html:30`; snippet nunca incluído |

**Static órfão:**
- `gestao_aprovacao/static/css/login.css`
- `gestao_aprovacao/static/favicon.svg`
- `suprimentos/static/css/analise_obra.css` e `suprimentos/static/js/analise_obra.js` (templates usam o path `suprimentos/static/suprimentos/...`, não o path "flat") — confirmar.

**URL duplicada (nunca casa):**
- `gestao_aprovacao/urls.py:57-61` — duplica `usuarios/` já definido em `:11-14`; Django usa o primeiro match, então o bloco 57-61 é morto. (As **views** permanecem — são usadas pelos wrappers.)

**Pastas:**
- `_mvp_hr_extract/` — protótipo React/TSX, zero referências Django. Arquivar fora do repo.
- `Lplan_Sistema/` (subpasta) — contém só `.gitignore`, sem código.

**Correção (não remoção):**
- `gestao_aprovacao/templates/obras/home.html:369` referencia `lplan-logo.svg` inexistente.
- `recursos_humanos/tests_experiencia.py` — nome não casa com `test_*.py`; o runner **não descobre**. Mover para `recursos_humanos/tests/test_experiencia.py`.

### 1.2 NÃO remover (pausado/intencional)
| Item | Motivo |
|------|--------|
| App `integrations/` | Pausado em `settings.py:69` e `urls.py:56`; código preparado p/ Teams/Azure |
| `teams_chat_embed_view` (`core/frontend_views.py:1340-1357`) + template | Feature Teams pausada |
| Blocos comentados Azure/Teams (`settings.py:349-384`) | Referência para reativar |
| `core/middleware.SecurityHeadersMiddleware` (desativado, `settings.py:89`) | Alternativa de CSP; não é lixo |
| Scripts SQL em `gestao_aprovacao/migrations/*.sql` | Úteis p/ DBA; mover p/ `scripts/sql/` se quiser limpar |
| `recursos_humanos/fix_*.py`, `seed_*.py` importados por migrations | Necessários para `migrate` |
| Management commands de ops (lembretes, smtp, importações) | Utilitários intencionais |

### 1.3 Observações
- Rodar `ruff check --select F401` para imports não usados (não fazer manualmente em arquivos de 7k linhas).
- `accounts/login` **não** pode sair: `workflow_aprovacao/decorators.py:8` depende. `accounts/profile.html`/`home.html` são edge-cases legados, mas mantêm casos reais.

---

## Parte 2 — Arquivos gigantes e estrutura

### 2.1 Maiores arquivos (fonte canônica, excluindo `staticfiles/` e vendors)
| Linhas | Tipo | Caminho |
|--------|------|---------|
| 7.421 | py | `gestao_aprovacao/views.py` |
| ~7.553 | html | `core/templates/core/daily_log_form.html` |
| 7.089 | py | `core/frontend_views.py` |
| 7.039 | css | `recursos_humanos/static/recursos_humanos/css/rh.css` |
| 6.639 | css | `impedimentos/static/impedimentos/css/list_impedimentos.css` |
| 5.717 | js | `painel_operacional/static/painel_operacional/js/editor_ambiente.js` |
| ~5.889 | html | `impedimentos/templates/impedimentos/list_impedimentos.html` |
| 5.270 | py | `whatsapp_ia/ia_functions.py` |
| 4.872 | js | `painel_operacional/.../editar_mapa_controle.js` |
| 3.070 | py | `trackhub/views.py` |
| 2.252 | py | `core/models.py` |

### 2.2 Blocos inline a extrair (JS/CSS dentro de template)
| Template | Bloco | ~Linhas | Início |
|----------|-------|---------|--------|
| `daily_log_form.html` | `<script>` | ~5.444 | L1853 |
| `list_impedimentos.html` | `<script>` | ~2.614 | L2859 |
| `list_impedimentos.html` | `<script>` | ~1.700 | L1159 |
| `accounts/.../admin_central.html` | `<style>` | ~1.062 | L9 |
| `suprimentos/.../dashboard_2.html` | `<script>` | ~974 | L839 |
| `recursos_humanos/.../colaboradores_list.html` | `<script>` | ~889 | L445 |
| `core/.../dashboard.html` | `<script>` | ~765 | L555 |
| `core/templates/base.html` | `<script>` | ~429 | L677 |

### 2.3 Funções muito longas (hotspots de regressão)
| Linhas | Função | Arquivo |
|--------|--------|---------|
| 1.922 | `diary_form_view()` | `core/frontend_views.py:4233-6154` |
| 746 | `dashboard_2()` | `suprimentos/views_engenharia.py:1912-2657` |
| 575 | `list_impedimentos()` | `impedimentos/views.py:783-1357` |
| 508 | `item_atualizar_campo()` | `suprimentos/views_api.py:907-1414` |
| 418 | `_gerar_pdf_historico()` | `gestao_aprovacao/views.py:6968-7385` |

### 2.4 Duplicação entre apps
- Duas `criar_notificacao` (`gestao_aprovacao/utils.py:285` vs `core/notification_utils.py:31`) — `gestao_aprovacao/views.py:58-59` importa as duas.
- Infra de e-mail mora em `gestao_aprovacao/email_utils.py` (1.161 linhas) mas é usada por `core`, `accounts`, `workflow_aprovacao` (acoplamento invertido).
- Lógica de acesso a projeto/obra reimplementada em `core/frontend_views.py` vs `assistente_lplan/services/permissions.py`.

### 2.5 Inconsistência arquitetural
| App | Tem `services/`? | Linhas de views |
|-----|------------------|-----------------|
| suprimentos | Sim (6 módulos) | ~6.620 (split) ✅ referência |
| workflow_aprovacao | Sim (~15) | 1.464 ✅ |
| gestao_aprovacao | Parcial | 7.421 (99% em views.py) ⚠️ |
| core | **Não** | ~10.208 (frontend_views monolito) ⚠️ |
| painel_operacional | Não | lógica no JS de 5k+ ⚠️ |

---

## Parte 3 — Plano de refatoração priorizado

Cada item: problema → ação → **risco** / **esforço**.

### Quick wins (baixo risco)
- **QW1** Remover código morto da seção 1.1 (templates/static órfãos, URL duplicada). Risco baixo / esforço pequeno.
- **QW2** Unificar `criar_notificacao` em `core/notification_utils.py` (adapter fino no gestao). Risco baixo / pequeno.
- **QW3** Extrair `<style>` de `central_signup_requests.html` e `notifications.html` para `.css`. Risco baixo / pequeno. (Mesmo procedimento já usado em `select_system.css`.)
- **QW4** Extrair JS/CSS de `base.html` (~429 linhas) para estático. Risco baixo / pequeno.

### Médio prazo
- **M1** Quebrar `core/models.py` em pacote `core/models/` (re-export no `__init__.py`, sem migration). Risco médio / médio.
- **M2** Extrair infra de e-mail para `core/mail/` (desacoplar de gestao). Risco médio / médio.
- **M3** Centralizar permissões em `core/access.py`. Risco médio / médio.
- **M4** Modularizar CSS gigantes (rh.css, list_impedimentos.css). Risco médio (regressão visual) / médio.

### Estratégico (alto risco — só com testes e tempo)
- **E1** Split `gestao_aprovacao/views.py` por domínio (`views/workorders.py`, `views/reports.py`...), `urls.py` re-exportando. Risco alto / grande.
- **E2** Split `core/frontend_views.py` + criar `core/services/diary/`. Risco alto / grande.
- **E3** Extrair os ~5.444 linhas de JS de `daily_log_form.html` para módulos JS + `DiaryFormService`. Risco **alto** (formulário central, offline, uploads) / grande.
- **E4** Extrair JS de `list_impedimentos.html`. Risco alto / grande.

### Ordem sugerida (segura)
`QW2 → QW4 → QW3 → QW1 → M2 → M3 → M1 → E1 → E2 → E3 → E4`

> **Regra de ouro:** itens E* só depois que houver smoke tests cobrindo as telas afetadas. Extração de JS inline deve ser "mover sem reescrever" primeiro (1:1), só depois refatorar a lógica — em commits separados.

---

## Como remover algo com segurança (passo a passo)

1. Busca global pelo nome (arquivo/função/rota/template), ignorando `.claude/worktrees/` e `staticfiles/`.
2. Se houver referência viva → **não remova**, investigue.
3. Se só na própria definição → mova para fora do repo (backup) ou delete.
4. `python manage.py check`.
5. Se for template/estático: abra a tela relacionada logado (smoke test).
6. Commit isolado, mensagem clara ("remove dead template X — no references").
