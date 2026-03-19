# Integracoes Azure e Teams

Este documento resume a implementacao base do roadmap de integracoes.

## Endpoints

- `POST /api/integrations/teams/bot/activity/`
  - Endpoint para receber atividades do bot do Teams (Azure Bot Service).
  - Comandos suportados:
    - `ajuda`
    - `pendencias`
    - `aprovar pedido <id|codigo> [comentario]`
    - `reprovar pedido <id|codigo> <motivo>`
    - `aprovar cadastro <id>`
    - `rejeitar cadastro <id> <motivo>`

- `POST /api/integrations/powerbi/export/`
  - Dispara exportacao incremental para Power BI via fila.

## Chat embutido no frontend

- Tela: `GET /integracoes/teams/chat/`
- Arquivo: `core/templates/core/teams_chat_embed.html`
- Configuracao:
  - `TEAMS_CHAT_EMBED_ENABLED=True`
  - `TEAMS_CHAT_EMBED_MODE=acs_iframe` (recomendado para web)
  - `TEAMS_CHAT_APP_URL=https://...` (URL da aplicacao ACS de chat)
  - Opcional: `TEAMS_CHAT_EMBED_MODE=embedded_sdk` e `TEAMS_EMBEDDED_SDK_URL=...`

Observacao: o Teams web nativo nao deve ser embutido por iframe direto devido restricoes de frame. O fluxo recomendado e usar ACS/SDK de embed.

## Variaveis de ambiente

Consulte `.env.example` para lista completa.

Principais:

- Azure/Teams:
  - `AZURE_TENANT_ID`
  - `AZURE_CLIENT_ID`
  - `AZURE_CLIENT_SECRET`
  - `TEAMS_TEAM_ID`
  - `TEAMS_CHANNEL_ID`

- Power BI:
  - `POWERBI_ENABLED`
  - `POWERBI_WORKSPACE_ID`
  - `POWERBI_DATASET_ID`

- SharePoint:
  - `SHAREPOINT_ENABLED`
  - `SHAREPOINT_SITE_ID`
  - `SHAREPOINT_DRIVE_ID`

- Assinatura:
  - `SIGNATURE_ENABLED`
  - `SIGNATURE_PROVIDER`
  - `SIGNATURE_API_KEY`

- Operacoes:
  - `OPERATIONS_ENABLED`
  - `PONTO_API_URL`
  - `ERP_API_URL`
  - `GEO_PROVIDER`

## Modelos de auditoria

App `integrations` cria:

- `IntegrationEventLog`
- `IntegrationCommandLog`
- `ExternalDocument`
- `SignatureRequest`
- `OperationsSyncRecord`

## Eventos automáticos

Sinais em `integrations/signals.py` disparam eventos com `transaction.on_commit` para:

- Criacao e mudanca de status de `WorkOrder`.
- Criacao e mudanca de status de `UserSignupRequest`.
- Aprovacao de `ConstructionDiary`.
- Criacao/atualizacao de `Project`.
- Upload de `Attachment` (base para SharePoint).

