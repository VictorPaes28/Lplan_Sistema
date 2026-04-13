# Plano: Centro de inteligência operacional (Lplan)

## 1. Objetivo

Unificar **leitura** do andamento da **obra** e, em fases seguintes, do **usuário**, sobre os mesmos dados já usados em Diário, GestControll (aprovações), Mapa de suprimentos e indicadores derivados — sem substituir BI: **números e regras no Django**; **LLM só narra, prioriza e explica** o que foi calculado.

## 2. O que já existe no repositório (base técnica)

| Peça | Local | Função |
|------|--------|--------|
| Assistente + orquestração | `assistente_lplan/` | Intenções, permissões, serviços por domínio |
| Provedor OpenAI | `assistente_lplan/services/llm_provider.py` | `OPENAI_API_KEY`, `ASSISTENTE_LPLAN_AI_ENABLED`, modelo via `ASSISTENTE_LPLAN_AI_MODEL` (padrão **gpt-4o-mini**) |
| Radar de obra | `assistente_lplan/services/radar_obra_service.py` | Cruza suprimentos, aprovações, diário e histórico em score, tendência e alertas |
| Cross-domain | `assistente_lplan/services/cross_domain_service.py` | Ex.: gargalos com radar anexado |
| Produção | `lplan_central/settings.py` | MySQL/cPanel, `.env`, proxy HTTPS, sessões |

## 3. Modelo de IA (custo)

- **Recomendado para começar:** [OpenAI **gpt-4o-mini**](https://platform.openai.com/docs/models) — bom equilíbrio custo/qualidade para classificação, JSON e textos curtos/médios.
- **Alternativa mais barata na família atual:** ver preços em [OpenAI Pricing](https://openai.com/pricing); ajustar `ASSISTENTE_LPLAN_AI_MODEL` no `.env` quando houver modelo “mini”/“nano” mais barato disponível na conta.
- **Boas práticas de custo:** cache de narrativas por `(obra_id, janela_temporal)`; não reenviar `raw_components` inteiro; limitar tokens de saída; fila para jobs pesados (fase 2).

## 4. Hospedagem: cPanel e ServHost

- O projeto já está preparado para **cPanel** (comentários em `settings.py`: `.env`, MySQL, `ProxyHeadersMiddleware`, CSRF, `CONN_MAX_AGE=0`).
- **ServHost** ([servhost.com.br](https://www.servhost.com.br/)) é um provedor BR que oferece planos com **cPanel** (gerenciamento de conta, SSL, banco MySQL, etc.), alinhado ao que o Lplan já documenta.
- **“Copanel”:** interpretação como **cPanel** (painel clássico). Se no seu contrato for **outro painel** (ex.: CWP, oPanel), o Django continua igual; mudam apenas **PHP/cron** e **paths** no servidor — variáveis de ambiente e WSGI permanecem o conceito central.

### Checklist de deploy (API OpenAI em hospedagem compartilhada)

1. **Outbound HTTPS** liberado para `api.openai.com` (443) — alguns hosts bloqueiam; abrir ticket se falhar.
2. **Segredo:** `OPENAI_API_KEY` só no `.env`, nunca no repositório.
3. **Timeout:** requisições curtas (o `LLMProvider` usa timeout de rede limitado); narrativas longas podem precisar de **Celery** + Redis se o hosting permitir.
4. **Cron** (opcional): pré-calcular fatos agregados por obra (materializar tabela “snapshot”) para o agente não bater no banco em toda pergunta.

## 5. Fases de desenvolvimento

### Fase A — MVP (entregue neste PR)

- Nova intenção **`inteligencia_obra_integrada`**: usa `RadarObraService` + narrativa LLM **ancorada** nos dados do radar (sem inventar métricas).
- Fallback sem IA: texto estruturado só com o radar.

### Fase B — Consolidação de fatos

- Tabela ou view `obra_inteligencia_snapshot` (job diário): KPIs alinhados aos mesmos nomes usados no BI (evita “duas verdades”).
- Motor de **regras** explícitas (ex.: data de contrato vs campo X) alimentando `alerts` antes da LLM.

### Fase C — Agente

- Ferramentas internas (funções) por domínio: `get_radar`, `get_pedidos_resumo`, `get_desempenho_usuario`, etc.
- Loop com orçamento de tokens e logs (`AssistantQuestionLog` já existe).

### Fase D — Governança

- Feedback humano já modelado (`AssistantLearningFeedback`, `AssistantGuidedRule`).
- Política de retenção e opt-out por empresa.

## 6. Variáveis de ambiente relevantes

```env
ASSISTENTE_LPLAN_AI_ENABLED=True
OPENAI_API_KEY=sk-...
ASSISTENTE_LPLAN_AI_MODEL=gpt-4o-mini
```

## 7. Riscos

| Risco | Mitigação |
|-------|-----------|
| Alucinação numérica | Só passar JSON factual; instrução “não inventar”; regra no código |
| Custo | Modelo mini, cache, limites por usuário |
| Performance em shared hosting | Narrativas assíncronas na fase B |

---

*Documento gerado para alinhamento de produto e deploy; evoluir com as fases B–D.*
