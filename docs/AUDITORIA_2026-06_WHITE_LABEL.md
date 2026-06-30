# White-Label — Guia de Revenda e Personalização

> Data: 2026-06 · Pergunta central: **"Quão difícil é vender este sistema para outra empresa e tirar as referências à LPLAN?"**
> `.claude/worktrees/` ignorado.

---

## Resposta curta

**É viável, com esforço moderado**, desde que a venda seja por **instância dedicada** (cada cliente roda seu próprio deploy, com seu `.env` e seus arquivos de imagem) — modelo que o repositório já assume (ver `docs/PRODUTO_INSTANCIA_DEDICADA_E_PACOTES.md`).

O obstáculo é que **não existe hoje uma camada única de marca**. Texto ("LPLAN", "Engenharia integrada"), logos, cores e e-mails estão espalhados em **~130 arquivos** (~1.200–1.500 ocorrências de `lplan`, metade técnica e invisível ao usuário). O caminho pragmático é **centralizar a marca visível** e deixar o resto como identificador interno.

| Estratégia | Esforço | Recomendação |
|-----------|---------|--------------|
| **A. Instância dedicada + camada de marca** | 3–5 dias | ✅ Recomendada |
| **B. "Zero LPLAN no código"** (renomear apps, vars JS, pacote `lplan_central`) | 2–4 semanas | ❌ Desnecessário p/ revenda |
| **C. Multi-tenant na mesma instância** | Grande (não suportado hoje) | ❌ Fora de escopo |

---

## Inventário da marca (onde está e quão difícil mudar)

| Categoria | Ocorrências (estimativa) | Dificuldade |
|-----------|--------------------------|-------------|
| Strings `LPLAN`/`Lplan`/`lplan` | ~1.200–1.500 em ~130 arquivos | Médio–Difícil |
| Assets de logo | 7 arquivos + ~35 referências | Fácil–Médio |
| Dados demo/cliente (Adamo, obras AL) | ~15 arquivos (seeds/dev) | Fácil |
| E-mails/domínios LPLAN | ~40 pontos | Fácil via `.env`; Médio nos fallbacks |
| Identificadores `lplan_central`/`assistente_lplan` | 50+ refs estruturais | Difícil (opcional) |
| Paleta/cores | ~5 "hubs" CSS + hex soltos | Médio |
| Títulos/footer/meta | ~45 templates | Médio |

### 1. Texto da marca visível (prioridade alta)
Arquivos "hub" que aparecem para o usuário:
- `core/templates/base.html` (título, sidebar/mobile logo+texto, botão "Assistente LPLAN") — linhas 17, 19-21, 135, 137, 155, 158, 613-614
- `core/templates/core/login.html` — 6, 10-11, 325-328
- `core/templates/core/select_system.html` — 4-5, 9-10, 258, 263 (lockup + footer ©)
- `core/templates/core/signup_request_form.html`, `support_hub.html`, `password_reset_*.html`
- `templates/base_mapa.html` — 11, 14-23, 63-65 (`window.__LPLAN_*`)
- `gestao_aprovacao/templates/base.html` — 15-16, 84, 257, 263 (© "LPLAN - GestControll")
- Títulos `- LPLAN` em ~45 templates de `suprimentos`, `recursos_humanos`, `accounts`, `painel_operacional`, `trackhub`

### 2. Logos / assets (7 arquivos físicos)
| Arquivo | Uso |
|---------|-----|
| `core/static/core/images/lplan-logo2.png` | Principal — favicon, login, sidebar, e-mails |
| `core/static/core/images/lpla-logo-pdf.png` | PDFs do Diário |
| `core/static/core/images/lpla-logo-pdf-transparent.png` | PDFs GestControll/impedimentos/workflow |
| `suprimentos/static/img/lplan-logo.jpg` | Navbar `base_mapa.html` |
| `gestao_aprovacao/static/images/lplan-logo.png` | Home GestControll |
| `gestao_aprovacao/static/images/lplan.png` | Header legado |
| `gestao_aprovacao/static/favicon.svg` | Favicon alternativo |

Referenciados em PDF/e-mail: `core/utils/pdf_generator.py:315`, `gestao_aprovacao/views.py:971,2543,7028`, `gestao_aprovacao/services/fila_atraso_pdf.py:30`, `impedimentos/pdf_export.py:27-30`, `workflow_aprovacao/services/signing.py:55`, `recursos_humanos/services/notificacoes.py:202-213`.

> ⚠️ `gestao_aprovacao/templates/obras/home.html:369` referencia `lplan-logo.svg` que **não existe** — corrigir.

### 3. Dados de cliente específicos (fáceis de isolar)
- `core/frontend_views.py:82-86` — `OBRA_CONTRATANTE_MAP` (mapa obra→"Incorporadora Adamo" etc.). **Remover ou tornar configurável.**
- Seeds: `seed_dados_demo_completo.py`, `reset_local_4_obras.py`, `bootstrap.py`, `mapa_obras/.../seed_obras_lplan.py` — só rodam em dev.
- Migração com e-mails reais: `gestao_aprovacao/migrations/0023_aprovacaoemaildestinatario.py:8-11`.

### 4. E-mails / domínios
Centralizados (fáceis via `.env`): `ALLOWED_HOSTS`, `DEFAULT_FROM_EMAIL`, `SIGNUP_ALLOWED_EMAIL_DOMAINS`, `EMAIL_DEPARTAMENTOS_APROVACAO` (`settings.py`).
Hardcoded fora do settings (médio):
- `gestao_aprovacao/email_utils.py:19-20,418`
- `gestao_aprovacao/templates/base.html:257` (`suporte@lplan.com.br`)
- `core/templates/core/support_hub.html:39,43` (`suporte@lplan.app.br` — **domínio diferente!**)
- `recursos_humanos/services/notificacoes.py:182,190,302,311,320`
- `whatsapp_ia/views_webhook.py:135`, `workflow_aprovacao/services/geocoding.py:18`

> ⚠️ Inconsistência: `suporte@lplan.com.br` vs `suporte@lplan.app.br`. Alinhar.

### 5. Cores da marca
Sem `brand.css` único; há 3-4 blocos `:root` paralelos:
- `core/templates/base.html:50-77` (inline)
- `core/static/core/css/theme-global.css`
- `suprimentos/static/css/supplymap.css:36-43` (vars `--lplan-*`)
- `gestao_aprovacao/static/css/base.css:17-18`

Cores identitárias: `#0e6da8` (azul wordmark), `#1a365d`/`#2d4a7c` (navy GestControll), `#FF6600` (laranja CTA), `#1A3A5C` (PDFs).

### 6. Sub-marcas de produto
`GestControll`, `TrackHub`, `BI da Obra`, `Central` — centenas de referências. Para revenda, pode renomear por pacote **ou** manter como nomes de módulo.

### 7. Domínio de negócio com marca embutida
- Categoria de mão de obra **"Indireto (LPLAN)"** no RDO: `core/models.py:558,564,1433,1455`, `core/management/commands/ensure_dados_referencia_servidor.py:75`, PDFs. **Não é só marca** — outro contratante pode estranhar. Renomear para "Indireto" genérico ou configurável.

---

## Plano recomendado — Camada de marca configurável

### Passo 1 — Variáveis no `.env` (Fácil, ~1 dia)
```env
BRAND_NAME=Nome do Cliente
BRAND_TAGLINE=Engenharia integrada
BRAND_SUPPORT_EMAIL=suporte@cliente.com.br
BRAND_LOGO_STATIC=core/images/cliente-logo.png
BRAND_FAVICON_STATIC=core/images/cliente-favicon.png
BRAND_PRIMARY_COLOR=#0e6da8
```

### Passo 2 — Context processor de marca (Médio, ~2-3 dias)
- Criar `core/context_processors.py → brand()` que lê os settings e injeta `brand` em todos os templates.
- Registrar em `TEMPLATES['OPTIONS']['context_processors']` (`settings.py:108-116`).
- Substituir nos templates "hub" (base, login, select_system, base_mapa, password reset, e-mails) os textos/logos fixos por `{{ brand.name }}`, `{% static brand.logo %}`, etc.

### Passo 3 — PDFs e e-mails (Médio)
- Path do logo de PDF via settings (não hardcoded em cada gerador).
- Template de e-mail HTML do GestControll (`gestao_aprovacao/email_utils.py:356-407`) parametrizado.

### Passo 4 — Cores (Médio)
- Unificar os `:root` em um único arquivo (ou injetar `--brand-primary` via context processor no `base.html`).

### Passo 5 — Itens de negócio (decisão de produto)
- Remover/externalizar `OBRA_CONTRATANTE_MAP`.
- Decidir destino de "Indireto (LPLAN)".
- Parametrizar prompts de IA/WhatsApp (`whatsapp_ia/prompts.py:5`, `assistente_lplan/services/llm_provider.py:62-64`).

### Opcional (Difícil, desnecessário p/ revenda)
- Renomear pacote `lplan_central`, app `assistente_lplan`, vars JS `__LPLAN_*`, classes CSS `lplan-*`. Alto risco, pouco retorno se cada cliente tem instância isolada.

---

## Checklist rápido de revenda (por cliente)

1. `.env` com variáveis `BRAND_*` + domínio + SMTP + banco.
2. Substituir os **7 arquivos de imagem** por logos do cliente (no deploy).
3. Conferir `support_hub.html` e `gestao_aprovacao/base.html` (e-mail de suporte).
4. Remover/ajustar `OBRA_CONTRATANTE_MAP` (`frontend_views.py:82-86`).
5. Não rodar seeds demo; revisar migração de e-mails de aprovação.
6. Decidir nomes de produto (GestControll/TrackHub) e "Indireto (LPLAN)".
7. **Não** distribuir `.env`/`docs/env.producao.correto.txt` com segredos reais (ver doc de segurança).

> Estimativa: **3-5 dias** para a primeira instância com marca trocada; clientes seguintes reaproveitam a camada e levam **horas** (só `.env` + assets).
