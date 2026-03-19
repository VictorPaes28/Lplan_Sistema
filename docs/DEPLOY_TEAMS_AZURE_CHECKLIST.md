# Checklist manual no servidor (Teams + Azure)

Este arquivo concentra o que precisa ser configurado manualmente em producao.

## 1) Variaveis de ambiente no servidor

No `.env` de producao, preencher:

```env
# Base de integracoes
INTEGRATIONS_ENABLED=True

# Azure / Entra ID
AZURE_TENANT_ID=
AZURE_CLIENT_ID=
AZURE_CLIENT_SECRET=
AZURE_BOT_APP_ID=
AZURE_BOT_APP_SECRET=

# Teams (envio de mensagens)
TEAMS_ENABLED=True
TEAMS_TEAM_ID=
TEAMS_CHANNEL_ID=
TEAMS_DEFAULT_MESSAGE_PREFIX=[LPLAN]

# Chat embutido no LPLAN
TEAMS_CHAT_EMBED_ENABLED=True
TEAMS_CHAT_EMBED_MODE=acs_iframe
TEAMS_CHAT_APP_URL=
TEAMS_EMBEDDED_SDK_URL=
TEAMS_CHAT_ENTITY_PREFIX=LPLAN

# Power BI (se ativar)
POWERBI_ENABLED=False
POWERBI_WORKSPACE_ID=
POWERBI_DATASET_ID=

# SharePoint (se ativar)
SHAREPOINT_ENABLED=False
SHAREPOINT_SITE_ID=
SHAREPOINT_DRIVE_ID=

# Assinatura (se ativar)
SIGNATURE_ENABLED=False
SIGNATURE_PROVIDER=clicksign
SIGNATURE_API_KEY=
SIGNATURE_WEBHOOK_SECRET=

# Operacoes (se ativar)
OPERATIONS_ENABLED=False
PONTO_API_URL=
PONTO_API_TOKEN=
ERP_API_URL=
ERP_API_TOKEN=
GEO_PROVIDER=azure_maps
GEO_API_KEY=
```

## 2) Azure App Registration (manual)

- Criar/usar App Registration no Entra ID.
- Gerar `Client Secret` e salvar no `.env`.
- Garantir permissao Microsoft Graph para envio em Teams.
- Conceder consentimento de administrador do tenant.

## 3) Bot / endpoint publico

- Publicar o sistema com HTTPS publico.
- Validar endpoint de atividade do bot:
  - `POST /api/integrations/teams/bot/activity/`
- Se houver reverse proxy, liberar rota e metodos `POST`.

## 4) Teams Chat embutido (ACS recomendado)

- Publicar sua aplicacao web ACS (frontend do chat).
- Configurar `TEAMS_CHAT_APP_URL` com a URL publica dessa app.
- Testar em:
  - `/integracoes/teams/chat/`

## 5) Banco de dados

- Aplicar migracoes em producao:
  - `python manage.py migrate`
- Isso cria tabelas de auditoria de integracoes.

## 6) Worker assíncrono

- Subir worker Celery no servidor.
- Garantir Redis disponivel.
- Validar filas para eventos de integracao.

## 7) Validacao final (smoke test)

- Abrir tela de chat embutido.
- Enviar comando no Teams e verificar resposta.
- Verificar logs no admin:
  - `IntegrationEventLog`
  - `IntegrationCommandLog`
- Confirmar que aprovacoes/cadastros disparam eventos.

