# Análise: arquitetura, módulos e melhorias futuras

**Data:** 2026-04-14  
**Âmbito:** `Lplan_Sistema` — visão técnica para evoluir o produto (instâncias dedicadas, pacotes, qualidade e operação).

**Relaciona com:** [PRODUTO_INSTANCIA_DEDICADA_E_PACOTES.md](PRODUTO_INSTANCIA_DEDICADA_E_PACOTES.md), [precificacao_produto_lplan.md](precificacao_produto_lplan.md).

---

## 1) Estrutura de repositório e dívida técnica

### 1.1 Pastas duplicadas / legado

**Atualização (2026-04-23):** Removidos do repositório **`Mapa_Controle/`** e **`Gestao_aprovacao_legacy/`** (projetos Django antigos paralelos, fora de `INSTALLED_APPS` / `lplan_central.urls`). O código canónico é só **`suprimentos/`**, **`gestao_aprovacao/`**, **`mapa_obras/`**, **`accounts/`**.

| Risco | Impacto |
|-------|---------|
| Duas árvores de `suprimentos` (removido em 2026-04-23) | Era correção no ramo errado; risco eliminado com o arquivo do legado. |
| Novas cópias paralelas no futuro | Reintroduz o mesmo risco; manter um único ramo por app. |

### 1.2 Testes e descoberta

- **Atualização (2026-04):** removido **`comunicados/tests.py`** vazio; mantém-se só o pacote **`comunicados/tests/`**. `python manage.py test comunicados` descobre os 24 testes corretamente.
- Cobertura é **desigual**: `suprimentos/tests/` e `core/tests_*.py` são fortes; `gestao_aprovacao` tem poucos testes; APIs críticas nem sempre têm testes de integração.

**Recomendação:** Renomear ou remover `comunicados/tests.py` (ou tornar `tests/` o único pacote). Adotar **`pytest`** + **`pytest-django`** opcionalmente, com um único comando que descubra testes sem ambiguidade.

### 1.3 CI/CD

- **Atualização (2026-04):** workflow **`.github/workflows/ci.yml`** — `manage.py check` + testes dos apps ativos (`core`, `gestao_aprovacao`, `mapa_obras`, `accounts`, `suprimentos`, `assistente_lplan`, `comunicados`). A suíte completa `manage.py test` sem labels ainda pode falhar ao descobrir **`integrations`** (app fora de `INSTALLED_APPS`).

**Recomendação (restante):** `ruff`/`flake8`, `migrate --check`, e excluir ou corrigir testes sob `integrations/` se se voltar a incluir o app.

---

## 2) Módulos Django e fronteiras

### 2.1 Mapa atual (canónico)

| Área | App | URL base | Papel |
|------|-----|----------|--------|
| Diário / núcleo | `core` | `/` | Obras, diário, APIs principais |
| Aprovações | `gestao_aprovacao` | `/gestao/` | Pedidos, fluxos, notificações |
| Mapa obras | `mapa_obras` | `/mapa/` | Vista mapa / obras |
| Contas / central | `accounts` | `/accounts/` | Auth, grupos, admin central |
| Engenharia / suprimentos | `suprimentos` | `/engenharia/`, APIs | Mapa controle, importações, webhooks |
| Assistente | `assistente_lplan` | `/assistente/` | IA, permissões por intenção |
| Comunicados | `comunicados` | `/comunicados/` | Megafone, painel admin |
| Integrações | `integrations` | (pausado) | Teams/Azure futuro |

Fronteiras estão **razoavelmente claras por URL**; o acoplamento aparece mais em **templates globais** (`base.html`), **context processors** e **grupos** partilhados.

### 2.2 Melhorias de modularidade

1. **`INSTALLED_APPS` dinâmico** (env `ENABLED_APPS` ou ficheiro por pacote): alinhar com [PRODUTO_INSTANCIA_DEDICADA_E_PACOTES.md](PRODUTO_INSTANCIA_DEDICADA_E_PACOTES.md) — hoje todos os apps entram sempre.
2. **`sidebar_systems` / menus:** hoje derivam de **grupos** (`core/context_processors.py`). Para pacotes, falta também **“módulo comprado”** (flag) para não mostrar apps desligados mesmo que o grupo exista.
3. **Contratos entre apps:** documentar dependências (ex.: `assistente_lplan` → serviços de `suprimentos`/`gestao_aprovacao`) para evitar imports circulares e facilitar desligar módulos.

---

## 3) Configuração, marca e operação

### 3.1 Settings

- Boa base: **`.env`**, `SITE_URL`, `ALLOWED_HOSTS`, DB MySQL/Postgres/SQLite.
- **White-label:** ainda há muitos textos e assets **LPLAN** em templates e e-mails (ver doc de produto dedicado).

### 3.2 Segurança e robustez

| Tema | Estado típico | Melhoria |
|------|----------------|----------|
| DRF | `IsAuthenticated` por defeito | Revisar **ViewSets** expostos; rate limiting em APIs sensíveis; escopos por recurso onde fizer sentido. |
| Webhooks | Sienge em `suprimentos` | Assinatura/secreto, idempotência, logs de auditoria. |
| Ficheiros / uploads | Diário, anexos | Limites de tamanho já tratados em parte (`handler400`); validar tipos MIME e antivírus em cenários enterprise. |
| Sessões / cookies | Documentado em settings | `SESSION_COOKIE_SECURE` em produção HTTPS; revisão periódica. |

### 3.3 Assíncrono e filas

- **Celery** e **Redis** nas dependências — garantir que **produção** por cliente tem processo worker onde for necessário (e-mails pesados, importações), não só o web.

---

## 4) APIs e integrações

- Várias superfícies: **`/api/diario/`**, **`/api/internal/`**, **`/api/webhook/`**, APIs em `core` e `suprimentos`.
- **Melhorias:** versão na URL (`/api/v1/`), documentação OpenAPI (drf-spectacular ou similar), política clara de **paginação** e **erros** JSON uniformes.

---

## 5) Frontend e UX técnica

- Mistura de **templates Django**, **Tailwind-ish** em `base.html`, JS inline e estáticos por app.
- **Sugestão incremental:** extrair JS crítico para módulos, reduzir duplicação entre `base.html` e `base_mapa.html`, e definir **guia de componentes** (botões, tabelas admin) para consistência entre Diário, Gestão e Comunicados.

---

## 6) Observabilidade e suporte

- Centralizar **logging** estruturado (request id, utilizador, obra) em caminhos críticos (aprovações, webhooks, assistente).
- **Erros em produção:** integração Sentry ou similar por instância.
- **Backups:** runbook por cliente (BD + `MEDIA_ROOT`) — produto “dedicado” exige isto explícito.

---

## 7) Roadmap sugerido (priorizado)

| Prioridade | Item | Benefício |
|------------|------|-----------|
| P0 | Eliminar ambiguidade de testes (`comunicados/tests.py` vs `tests/`) + CI mínimo | Menos regressões, deploy confiável |
| P0 | Pastas legado — **feito (2026-04-23):** removidas `Mapa_Controle/`, `Gestao_aprovacao_legacy/` | Um único sítio para editar código |
| P1 | Settings de marca (`SITE_NAME`, logos) + retirar LPLAN hardcoded dos templates críticos | White-label / instância dedicada |
| P1 | Flags de módulo + sidebar condicional | Pacotes comerciais reais no código |
| P2 | OpenAPI + limites DRF em APIs públicas/internas | Integrações e segurança |
| P2 | Observabilidade (logs + Sentry) | Operação em escala |
| P3 | Pytest, cobertura alvo em `gestao_aprovacao` e fluxos de pagamento/aprovação | Confiança em refactor |

---

## 8) Conclusão

O sistema é **maduro em funcionalidade** (vários domínios de obra, suprimentos, IA, comunicados), com **configuração por ambiente** já pensada. Os maiores ganhos para o **teu modelo de negócio** (instância dedicada + pacotes) e para a **saúde do código** vêm de: **(1)** limpar legado e testes, **(2)** parametrizar marca e módulos, **(3)** automatizar qualidade (CI) e **(4)** endurecer APIs e observabilidade à medida que mais integrações forem vendidas.

---

*Documento de trabalho — atualizar após decisões de arquivo de legado e escolha de ferramentas (pytest, Sentry, OpenAPI).*
