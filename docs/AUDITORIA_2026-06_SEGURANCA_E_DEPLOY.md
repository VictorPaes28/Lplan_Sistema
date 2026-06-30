# Auditoria de Segurança e Riscos de Deploy — Sistema LPLAN

> Data: 2026-06 · Base: `lplan_central/settings.py` + código. `.claude/worktrees/` ignorado.
> Severidade: 🔴 Crítico · 🟠 Alto · 🟡 Médio · ⚪ Baixo.

---

## 🔴 Críticos (resolver primeiro)

### C1 — Credenciais reais de produção versionadas no repositório
- **Arquivo:** `docs/env.producao.correto.txt`
- **Contém:** `SECRET_KEY`, `DB_PASSWORD`, `EMAIL_HOST_PASSWORD`, `EMAIL_RDO_HOST_PASSWORD` e hosts reais.
- **Risco:** qualquer pessoa com acesso ao repositório **ou ao histórico git** consegue comprometer banco, e-mail e sessões.
- **Ação:**
  1. **Rotacionar imediatamente** tudo que aparece no arquivo (trocar senha do banco, senhas de e-mail, gerar nova `SECRET_KEY`).
  2. Remover o arquivo do repositório e adicionar ao `.gitignore`.
  3. Limpar do histórico git (ex.: `git filter-repo` ou BFG) — apenas apagar o arquivo **não** remove do histórico.
  4. Manter um modelo **sem segredos** (`.env.example` já existe) como referência.

### C2 — `DEBUG=True` é o padrão se faltar `.env`
- **Local:** `settings.py:29` — `DEBUG = os.environ.get('DEBUG', 'True')...`
- **Efeito colateral:** com `DEBUG=True`, `settings.py:39-40` força `ALLOWED_HOSTS = ['*']`.
- **Risco:** deploy incompleto expõe tracebacks, configs internas e aceita qualquer Host header.
- **Ação:** falhar o startup (ou logar erro grave) se `DEBUG=True` fora de ambiente de desenvolvimento; documentar `DEBUG=False` como obrigatório em produção.

### C3 — `SECRET_KEY` com fallback inseguro
- **Local:** `settings.py:26` — default `'django-insecure-change-in-production'`.
- **Risco:** assinaturas de sessão/CSRF previsíveis se a variável não for definida.
- **Ação:** sem `SECRET_KEY` no ambiente de produção, **não subir** (levantar exceção quando `DEBUG=False`).

### C4 — SQLite usado silenciosamente quando mal configurado
- **Local:** `settings.py:127-170` — só usa MySQL/Postgres se `USE_MYSQL`/`USE_POSTGRES` = True; senão cai em SQLite.
- **Risco:** produção rodando em SQLite (concorrência, backup, escala e isolamento ruins) sem ninguém perceber.
- **Ação:** exigir banco real em produção; abortar se `DEBUG=False` e nenhum banco configurado.

### C5 — Webhook Sienge aceita POST sem autenticação se o secret estiver vazio
- **Local:** `suprimentos/views_webhook.py:42-55` (verificação HMAC só roda `if webhook_secret:`); default vazio em `settings.py:417`.
- **Risco:** com `SIENGE_WEBHOOK_SECRET` vazio, **qualquer** POST em `/api/webhook/sienge/` pode alterar insumos, SCs, PCs e NFs.
- **Ação:** rejeitar (401) quando o secret não estiver configurado, em vez de aceitar sem validar.

---

## 🟠 Altos

| # | Achado | Local | Ação |
|---|--------|-------|------|
| A1 | Cookies/HTTPS seguros são **opt-in** (`SECURE_COOKIES_AND_REDIRECT` default False) — sessão/CSRF podem trafegar em HTTP mesmo com `DEBUG=False` | `settings.py:259-273` | Default `True` quando `DEBUG=False` |
| A2 | `ALLOWED_HOSTS=['*']` em DEBUG | `settings.py:39-40` | Aceitável em dev; nunca subir staging com DEBUG=True |
| A3 | CSRF custom aceita origem se host estiver em `ALLOWED_HOSTS` | `core/csrf_middleware.py:45-50,106-108` | Revisar; manter `CSRF_TRUSTED_ORIGINS` explícito |
| A4 | Webhook WhatsApp **não valida** `X-Hub-Signature-256` no POST | `whatsapp_ia/views_webhook.py:336-463` | Implementar verificação de assinatura Meta |
| A5 | `WHATSAPP_VERIFY_TOKEN` fraco/previsível no exemplo (`lplan_webhook_2026`) | `.env.example:136`, `settings.py:523` | Token forte por instância |
| A6 | `/media/` servido publicamente (uploads RH, anexos de diário, PDFs) | `lplan_central/urls.py:62-71` | Servir com auth ou storage privado + signed URLs |
| A7 | PDFs WhatsApp em URL pública adivinhável por UUID | `whatsapp_ia/views_webhook.py:122-186` | Reduzir janela / storage privado |
| A8 | `@csrf_exempt` em endpoints autenticados por sessão | `suprimentos/views_api.py:608+`, `views_engenharia.py:1191+` | Reavaliar; usar CSRF normal onde houver sessão |
| A9 | `/api/csrf-token/` acessível sem login | `core/csrf_views.py:50-59` | Restringir se possível |
| A10 | Defaults de banco com nomes/credenciais LPLAN | `settings.py:143-145` | Forçar via `.env`; sem defaults de cliente |

---

## 🟡 Médios (resumo)

- **M1** E-mails LPLAN hardcoded em settings + código + **migração** (`settings.py:330,345,387-396`; `gestao_aprovacao/email_utils.py:18-21`; `gestao_aprovacao/migrations/0023_aprovacaoemaildestinatario.py:8-11`). Novo cliente recebe notificações para `@lplan.com.br`.
- **M2** `SITE_URL` default `localhost` (`settings.py:342`) → links de e-mail/WhatsApp quebram em deploy incompleto.
- **M3** `SIGNUP_ALLOWED_EMAIL_DOMAINS` default `lplan.com.br` (`settings.py:345`); se esvaziada, aceita **qualquer** domínio (`accounts/signup_services.py:31-32`).
- **M4** Sem rate limiting em signup/login/API públicos (`/cadastro/solicitar/`).
- **M5** `BrowsableAPIRenderer` habilitado globalmente (`settings.py:250-253`) — expõe UI/▢schema da API.
- **M6** Upload global default 200 MB (`settings.py:233-235`) — risco DoS se o proxy não limitar.
- **M7** E-mail default = console backend (`settings.py:320-323`) — em produção sem SMTP, e-mails somem no log silenciosamente.
- **M8** Celery/Redis default localhost (`settings.py:301-302`) — sync agendado Sienge não roda sem Redis.
- **M9** Dependências sem pin exato (`requirements.txt`): muitos `>=`, `pypdf2` legado, `pillow-heif` sem versão.
- **M10** CI não roda `check --deploy` nem testes de segurança (`.github/workflows/ci.yml:24-30`).

## ⚪ Baixos (resumo)

- Dados de obras/cliente reais em `core/management/commands/bootstrap.py:21-25`.
- Seeds demo com senha conhecida `demo1234` (`core/management/commands/seed_demo.py`).
- Migração semeia colaboradores fictícios (`recursos_humanos/migrations/0023_seed_exemplos_quadro.py`).
- `TIME_ZONE = 'America/Recife'` fixo (`settings.py:190`).
- `.htaccess.cpanel.example` com paths placeholder; `.env.example` diverge de `settings.py` (Azure/Teams).

---

## ✅ Checklist de `.env` para um NOVO cliente/servidor

Use ao provisionar uma instância dedicada. **Não** copiar `docs/env.producao.correto.txt` sem rotacionar os segredos.

```env
# Núcleo
SECRET_KEY=<gerar novo, único por cliente>
DEBUG=False
ALLOWED_HOSTS=sistema.cliente.com.br
SITE_URL=https://sistema.cliente.com.br
CSRF_TRUSTED_ORIGINS=https://sistema.cliente.com.br
SECURE_COOKIES_AND_REDIRECT=True

# Banco (obrigatório real em produção)
USE_MYSQL=True
DB_NAME=...
DB_USER=...
DB_PASSWORD=...
DB_HOST=localhost

# E-mail
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=...
EMAIL_PORT=...
EMAIL_USE_SSL=True
EMAIL_HOST_USER=...
EMAIL_HOST_PASSWORD=...
DEFAULT_FROM_EMAIL=sistema@cliente.com.br

# Cadastro / aprovação
SIGNUP_ALLOWED_EMAIL_DOMAINS=cliente.com.br
EMAIL_DEPARTAMENTOS_APROVACAO=aprovador@cliente.com.br
EMAIL_APROVACAO_DESTINATARIOS_FIXOS=aprovador@cliente.com.br

# Integrações (se usar)
SIENGE_WEBHOOK_SECRET=<obrigatório se webhook ligado>
WHATSAPP_VERIFY_TOKEN=<token forte>
OPENAI_API_KEY=...
```

### Passos de deploy
1. Criar `.env` completo (acima).
2. **Não** rodar `bootstrap`, `seed_demo`, seeds de RH em produção real.
3. `python manage.py migrate`.
4. `python manage.py collectstatic`.
5. Criar superusuário (`setup_superuser`).
6. Revisar destinatários de e-mail LPLAN (settings + admin + tabela `AprovacaoEmailDestinatario` pós-migração).
7. Configurar nginx `client_max_body_size` (ver `deploy/nginx-upload-limits.conf`).
8. Se usar sync agendado Sienge: Redis + Celery worker/beat.
9. WhatsApp Meta: URL do webhook, verify token forte, validação de assinatura no POST.
10. Proteger `/media/`.

---

## Plano de remediação recomendado (ordem)

1. C1 — rotacionar e remover segredos do git.
2. C2/C3/C4 — guardas de startup: abortar em produção com DEBUG/SECRET_KEY/banco inseguros.
3. C5 + A4 — exigir secret no webhook Sienge; validar assinatura WhatsApp.
4. A6/A7 — proteger `/media/` e PDFs.
5. A1 — cookies secure por padrão quando `DEBUG=False`.
6. M1 — remover seeds/defaults de e-mail LPLAN para instalações white-label.
7. M9/M10 — pin de dependências + `manage.py check --deploy` no CI.

> Observação: várias dessas correções são pequenas e concentradas em `settings.py` e nos 2 webhooks. São de **baixo risco funcional** e **alto ganho**. Posso implementá-las uma a uma, com teste, quando você autorizar.
