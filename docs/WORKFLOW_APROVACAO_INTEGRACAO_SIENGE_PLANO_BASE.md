# Workflow Aprovacao - Plano Base de Integracao (Sienge/ERP)

Data: 2026-04-20

Objetivo: definir uma base tecnica unica para integrar a Central de Aprovacoes com sistema oficial (Sienge ou ERP), cobrindo fonte de dados, entidades, contrato de API, autenticacao, sincronizacao, regras de aprovacao e criterio de verdade.

## 1) O que foi confirmado na pesquisa

- No modulo `workflow_aprovacao`, hoje nao existe consumo de API externa para configurar fluxos.
- A configuracao atual e 100% local em banco:
  - `core.Project` (obras)
  - `ProcessCategory` (categorias)
  - `ApprovalFlowDefinition`, `ApprovalStep`, `ApprovalStepParticipant` (fluxo/alcadas/aprovadores)
  - `User` + `Group` (responsaveis)
- A camada de engine ja tem preparacao para integracao futura (`external_system`, `sync_status`, outbox no fechamento de processo), mas sem conector Sienge implementado no workflow.
- A documentacao publica do Sienge consultada indica:
  - URL padrao com subdominio cliente: `https://api.sienge.com.br/{subdominio}/public/api/{versao}/{recurso}`
  - Rate limit de seguranca: REST 200/minuto, BULK 20/minuto
  - Autenticacao descrita em `Basic Authorization` (usuario-api:senha em base64)
  - Existe mecanismo de hooks/webhooks com eventos de mudanca

## 2) Gap tecnico identificado (importante)

- No projeto existe codigo antigo de `suprimentos/services/sienge_provider.py` modelando OAuth2/Bearer e endpoints placeholders.
- Na doc oficial encontrada, o Sienge descreve Basic Auth.
- Decisao obrigatoria antes de implementar:
  - Confirmar com o tenant/ambiente real se o contrato atual e Basic Auth, OAuth2, ou ambos por produto/versao.

## 3) Recomendacao de arquitetura (proposta pronta)

Fonte oficial recomendada:
- Primaria: Sienge (ou ERP definido pela operacao) para dados mestres de negocio.
- Secundaria: banco local LPlan como cache operacional e para resiliencia.

Padrao de integracao:
- Hibrido (recomendado):
  - Pull inicial/sincronizacao por API REST paginada.
  - Atualizacao incremental por webhooks do provedor.
  - Reconciliacao por agendamento (job periodico) para corrigir drift.

Camadas sugeridas:
- Conector provider (`integrations/providers/sienge.py`) com retries, backoff e rate-limit awareness.
- Servico de mapeamento para entidades internas (`workflow_aprovacao/services/integration_mapper.py`).
- Orquestracao assincrona por Celery (aproveitando padrao de `dispatch_event_on_commit`).
- Outbox/inbox de eventos para idempotencia e auditoria.

## 4) Entidades minimas a integrar (MVP)

Obrigatorias:
- Obras/Empreendimentos (chave de negocio para o fluxo).
- Categorias de processo (ou mapeamento das categorias locais para tipos externos).
- Usuarios aprovadores.
- Grupos/cargos de aprovacao.

Desejaveis (fase 2):
- Centro de custo.
- Contratos e medicoes (para regras por valor/faixa).
- Unidade organizacional/departamento.

Mapeamento recomendado de identidade:
- `external_system`: "sienge" (ou outro)
- `external_entity_type`: ex. `enterprise`, `contract`, `measurement`, `user`
- `external_id`: id externo estavel

## 5) Contrato tecnico - API interna do LPlan (para o front)

Observacao: o front da Central deve consumir API interna do LPlan, nao falar direto com Sienge.

Endpoints internos sugeridos:
- `GET /aprovacoes/api/v1/flows/reference-data`
  - retorna obras, categorias, usuarios, grupos (ja normalizados)
- `GET /aprovacoes/api/v1/flows/{flow_id}`
  - retorna configuracao completa para editor
- `PUT /aprovacoes/api/v1/flows/{flow_id}`
  - grava configuracao de alcadas/aprovadores
- `POST /aprovacoes/api/v1/sync/run`
  - dispara sync manual (com escopo)
- `GET /aprovacoes/api/v1/sync/status`
  - status da ultima sincronizacao e pendencias

Payload base de configuracao (editor):
- `is_active: bool`
- `steps[]`:
  - `id: int|null`
  - `name: str`
  - `is_active: bool`
  - `participants[]`:
    - `subject_kind: "user" | "django_group" | "role"` (role opcional fase 2)
    - `user_id` ou `group_id` ou `role_code`

Paginacao/filtros (reference-data):
- `page`, `page_size`, `q`, `project_code`, `is_active`

## 6) Autenticacao e seguranca (proposta)

LPlan -> Sienge:
- Se Basic Auth confirmado:
  - guardar credencial cifrada (secret manager/env)
  - montar `Authorization: Basic ...` no provider
- Se OAuth2 confirmado:
  - armazenar client_id/client_secret
  - cachear token com expiracao e refresh antecipado

Sienge -> LPlan (webhook):
- `X-Signature`/segredo compartilhado
- anti-replay (timestamp + nonce)
- idempotencia por `event_id`/hash do payload

LPlan Front -> LPlan API:
- sessao autenticada + permissao `configure_approval_flows`
- logs de auditoria para alteracoes de fluxo

## 7) Regra de sincronizacao (proposta operacional)

Fluxo recomendado:
- Tempo real:
  - receber webhook do provedor
  - enfileirar evento
  - buscar detalhes no endpoint de recurso
  - aplicar upsert local
- Agendado:
  - job a cada 15 minutos para delta (janela retroativa)
  - reconciliacao completa noturna
- Fallback manual:
  - botao "Sincronizar agora" com escopo por obra/categoria

Politica de falhas:
- retry exponencial com jitter
- dead-letter para eventos falhados
- dashboard de erros por tipo de entidade

## 8) Regra de negocio de aprovadores (proposta)

Niveis de regra:
- Nivel 1 (MVP): aprovador fixo por fluxo/alcada (ja suportado hoje)
- Nivel 2: aprovador por cargo/grupo dinamico
- Nivel 3: aprovacao por faixa de valor e tipo de processo

Precedencia recomendada:
1. Regra explicita por obra+categoria+faixa
2. Regra por obra+categoria
3. Regra por categoria global
4. Fallback administrativo

Regra de bloqueio:
- Se houver processo em andamento, nao permitir mudar estrutura de alcadas (ja aplicado no modulo).

## 9) Criterio de verdade (Source of Truth)

Proposta:
- Sienge/ERP = verdade para dados mestres e eventos externos.
- LPlan = verdade para:
  - desenho operacional do fluxo (alcadas, participantes, status local)
  - historico de aprovacao e auditoria
  - estado de sincronizacao (outbox/inbox, erros, retries)

Conflitos:
- timestamp de atualizacao + prioridade da origem por entidade
- nunca sobrescrever decisao humana local sem regra explicita

## 10) O que voce precisa me passar para eu fechar a implementacao

Preencher este bloco:

- Sistema oficial:
  - `[PREENCHER]` Sienge / ERP interno / outro
- Entidades obrigatorias:
  - `[PREENCHER]` obras, usuarios, centros de custo, contratos, medicoes, cargos...
- Contrato da API oficial:
  - `[PREENCHER]` base URL, endpoints, filtros, paginacao, limite
- Autenticacao:
  - `[PREENCHER]` Basic / OAuth2 / outro
  - `[PREENCHER]` credenciais de homolog e forma de armazenamento seguro
- Sincronizacao:
  - `[PREENCHER]` webhook, agendamento, janela de reconciliacao, SLA
- Regra de aprovadores:
  - `[PREENCHER]` fixo por fluxo, por cargo, por faixa de valor, por centro de custo
- Criterio de verdade:
  - `[PREENCHER]` qual sistema vence por entidade

## 11) Proximo passo recomendado

Assim que voce preencher os itens da secao 10, eu te entrego:
- especificacao tecnica final (sem placeholders),
- backlog tecnico em ordem de execucao,
- contrato de endpoints internos definitivo,
- plano de rollout (homologacao -> producao) com checklist.
