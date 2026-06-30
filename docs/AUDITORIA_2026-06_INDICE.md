# Auditoria Técnica do Sistema LPLAN — Índice Geral

> **Data:** 2026-06 · **Escopo:** repositório `Lplan_Sistema` (projeto Django `lplan_central`).
> A pasta `.claude/worktrees/` foi **ignorada** (é um worktree git duplicado, não faz parte do sistema).
>
> Esta auditoria é **diagnóstico + documentação**. Nenhuma alteração de código foi feita ao gerá-la.
> Use estes documentos como referência antes de mexer em cada área.

## Documentos desta auditoria

| Documento | O que cobre |
|-----------|-------------|
| [`AUDITORIA_2026-06_SEGURANCA_E_DEPLOY.md`](AUDITORIA_2026-06_SEGURANCA_E_DEPLOY.md) | Segredos, DEBUG, banco, webhooks, `/media/`, checklist de deploy para novo cliente |
| [`AUDITORIA_2026-06_WHITE_LABEL.md`](AUDITORIA_2026-06_WHITE_LABEL.md) | Quão difícil é vender/personalizar para outra empresa; onde está a marca LPLAN; plano de marca configurável |
| [`AUDITORIA_2026-06_CODIGO_MORTO_E_ESTRUTURA.md`](AUDITORIA_2026-06_CODIGO_MORTO_E_ESTRUTURA.md) | Código morto/legado seguro de remover; arquivos gigantes; plano de refatoração priorizado |

## Como usar (procedimento seguro para qualquer alteração)

Antes de aplicar **qualquer** mudança sugerida aqui, siga este roteiro para não gerar erro:

1. **Confirme o uso real**: rode um `grep`/busca pelo nome do arquivo, função, template ou rota em todo o projeto (fora de `.claude/worktrees/` e `staticfiles/`).
2. **Cheque o Django**: `python manage.py check` (e `python manage.py makemigrations --check --dry-run` se mexer em models).
3. **Smoke test**: suba o `runserver` e abra a tela afetada logado; para a tela inicial existe um teste rápido documentado no doc de estrutura.
4. **Mudança pequena e isolada**: uma alteração por vez, com commit separado, para facilitar reverter.
5. **Nunca** edite `settings.py` direto no servidor — use `.env` ou `settings_local.py`.

## Top prioridades (visão consolidada)

### 🔴 Urgente (segurança)
1. **Remover/rotacionar credenciais reais** em `docs/env.producao.correto.txt` (e limpar do histórico git).
2. Garantir que produção **nunca** rode com `DEBUG=True`, `SECRET_KEY` default ou SQLite.
3. Fechar webhooks abertos: **Sienge** (`suprimentos/views_webhook.py`) e **WhatsApp** (`whatsapp_ia/views_webhook.py`).
4. Proteger `/media/` (uploads de RH/diário hoje são públicos).

### 🟡 Importante (qualidade / manutenção)
5. Remover código morto de baixo risco (lista no doc de estrutura).
6. Extrair blocos gigantes de JS inline (`daily_log_form.html`, `list_impedimentos.html`).
7. Quebrar views monolíticas (`gestao_aprovacao/views.py` 7.4k linhas, `core/frontend_views.py` 7k linhas).

### 🟢 Estratégico (revenda)
8. Criar uma **camada única de marca** (context processor + `.env`) para viabilizar white-label sem caçar texto em ~130 arquivos.

## Resumo dos números

| Métrica | Valor |
|---------|-------|
| Referências à marca "LPLAN" no código | ~1.200–1.500 em ~130 arquivos |
| Maior arquivo de view | `gestao_aprovacao/views.py` — 7.421 linhas |
| Maior função | `diary_form_view()` — 1.922 linhas |
| Maior template | `daily_log_form.html` — ~7.553 linhas |
| Maior bloco de JS inline | ~5.444 linhas (`daily_log_form.html`) |
| Achados de segurança CRÍTICOS | 5 |
| Itens de código morto seguros p/ remover | ~12 |
