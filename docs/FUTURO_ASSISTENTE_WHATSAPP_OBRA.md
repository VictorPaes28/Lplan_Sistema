# Futuro: Assistente por WhatsApp (voz + dados da obra)

Documento de **backlog / visão** — não é escopo implementado. Complementa o [Plano Centro de Inteligência](PLANO_CENTRO_INTELIGENCIA_LPLAN.md).

## 1. Visão do produto

- Canal **WhatsApp** (texto e **áudio**).
- Usuário pergunta qualquer informação **da obra** (dentro do que o sistema e as permissões dele permitem).
- A resposta vem de **dados reais** (Django, serviços já existentes), não de conhecimento genérico do modelo.
- Experiência próxima ao que o mercado mostra em assistentes “Jarvis-like”: conveniência do WhatsApp + IA que **consulta** o Lplan.

## 2. Encaixe no que já existe

| Peça | Uso nesta aplicação |
|------|---------------------|
| `assistente_lplan/` | Orquestrador, intenções, `permissions`, serviços por domínio (`obras_service`, `radar_obra_service`, suprimentos, aprovações, etc.) |
| `LLMProvider` | Classificação de intenção, extração de entidades (obra, período), **formatação** da resposta a partir de JSON factual |
| Regra de ouro do plano | Números e fatos vêm do **código/banco**; o LLM **narra** e **estrutura**, não inventa métricas |

**Princípio:** o webhook do WhatsApp não duplica lógica de negócio — chama a mesma camada que a UI web usa (ou um adaptador fino em cima dela).

## 3. Fluxo técnico (alto nível)

1. **Entrada** — Meta WhatsApp Cloud API ou BSP (provedor) envia evento para `POST` no Django (webhook verificado).
2. **Identidade** — Mapear `wa_id` / telefone → `User` (cadastro prévio ou fluxo de vínculo primeiro uso).
3. **Mídia** — Se mensagem for áudio: baixar com token da API, transcrever (ex.: **Whisper** ou STT do provedor).
4. **Texto unificado** — Pergunta em texto (digitada ou transcrita).
5. **Processamento** — Reutilizar pipeline do assistente: parser → intenção → serviços → (opcional) LLM para redação curta.
6. **Saída** — Enviar resposta texto pela API do WhatsApp; opcionalmente TTS no futuro (menos prioritário que áudio de entrada).

## 4. O que desenvolver (fases sugeridas)

### Fase 0 — Pré-requisitos

- Conta Meta Business + número aprovado para WhatsApp Business API (ou contrato com BSP).
- Política de **LGPD**: finalidade, base legal, retenção de logs de conversa, opt-out.
- Definir **quem pode** usar (por empresa, por obra, por papel).

### Fase 1 — MVP texto

- Webhook + verificação + envio de mensagens texto.
- Vincular telefone ↔ usuário (tabela ou campo em perfil).
- Encaminhar mensagem ao `orchestrator` (ou view/service equivalente) com `user` resolvido e contexto de obra (última obra usada, ou pedir esclarecimento).
- Respostas curtas; sem áudio ainda.

### Fase 2 — Áudio de entrada

- Download de `audio/ogg` (ou formato enviado pela API).
- Transcrição → texto → mesmo pipeline da Fase 1.
- Limites: tamanho máximo do áudio, timeout, fila se necessário.

### Fase 3 — Robustez e produto

- Rate limit por usuário/obra; mensagens de erro amigáveis.
- Cache de respostas idênticas ou pré-cálculo (alinhado à Fase B do plano: snapshots).
- Métricas: tempo de resposta, custo STT + LLM, satisfação.

### Fase 4 (opcional)

- Resposta em áudio (TTS).
- Cartões/listas ricas se a API e o produto justificarem.

## 5. Segurança e governança

- **Autorização obrigatória** em cada consulta: mesmas regras que o web (`permissions` do assistente).
- **Separação por tenant/empresa** — nunca misturar dados de obras de clientes diferentes.
- Logs: conteúdo sensível minimizado; retenção configurável.
- Webhook: validação de assinatura (Meta) / segredo do provedor.

## 6. Custos (ordem de grandeza)

- **WhatsApp:** conversação cobrada por categoria de mensagem (marketing, utilidade, serviço) — consultar tabela atual da Meta/BSP.
- **STT:** por minuto de áudio (Whisper API ou equivalente).
- **LLM:** já dimensionado no plano do Centro de Inteligência; priorizar modelo econômico para classificação e textos curtos.

## 7. Riscos específicos deste canal

| Risco | Mitigação |
|-------|-----------|
| Usuário pede dado que não pode ver | Checagem de permissão antes de qualquer query; resposta genérica se negado |
| Áudio ruim / sotaque | STT com retry; pedir reformulação em texto |
| Latência (STT + LLM + DB) | Resposta “estamos buscando…” só se UX exigir; fila assíncrona em volume alto |
| Dependência Meta/BSP | Contrato e plano B (notificação in-app já existente) |

## 8. Inteligência em cotações e materiais (visão alinhada ao Lplan)

No dia a dia de obra, **orçamentos e preços** não “aparecem” sozinhos: compras ou obra disparam um **pedido de cotação** (lista de itens) para **fornecedores já conhecidos** — e-mail, WhatsApp ou portal. Os fornecedores devolvem **PDF, Excel ou prints**; com muitas fontes, o trabalho pesado é **abrir cada ficheiro e consolidar** num único mapa (planilha ou tela de sistema). A IA entra com força nesse ponto: **ler e estruturar** o que voltou (linhas, unidades, preços, totais, prazos quando existirem), não “ir ao Google Shopping sozinha” — embora outras ferramentas possam fazer pesquisa ativa na web.

**Como isso conversa com o que o Lplan já caminha a ser**

- **`suprimentos/`** (ex.: análise por obra, matrizes, relatórios) é o lugar natural para evoluir um **mapa de cotação** ou comparativo alimentado por dados **extraídos**, não só digitados.
- O **`assistente_lplan`** já separa **factos no banco/serviços** da **narração** do modelo; para cotações, o mesmo princípio vale: preço final confiável vem de **registro validado** (ou do parser), não de “chute” do LLM.
- O canal **WhatsApp** (este documento) pode, no futuro, ser **um dos canais** onde o fornecedor ou o comprador **encaminha** o arquivo ou o resumo — mas o **núcleo** da funcionalidade é **backend + armazenamento + UI** reutilizáveis na web.
- **Referências de mercado** (ex.: tabelas tipo **SINAPI**, **ORSE** ou importações periódicas em CSV) podem conviver como **coluna de benchmark** ao lado das cotações reais dos fornecedores — útil para relatório e curva de mercado, sem substituir a proposta negociada para aquela obra.

**Pesquisa em site de varejo** (Leroy, etc.) é outro animal: dá para automatizar com scraping, mas **manutenção e bloqueios** são altos; em obra grande, o preço de **lista** costuma perder para **orçamento direto** com CNPJ. No produto, isso pode ser **opcional** ou fase posterior em relação a **RFQ + consolidação**.

### Ponto a pesquisar e consultar com a empresa

Antes de priorizar telas ou integrações, **validar com compras e gestão** como é o fluxo **hoje** na operação real (pode diferir do modelo “ideal” acima):

- Disparam cotação **quantos fornecedores** em média (ordem de grandeza: 3, 10, 20)?
- O pedido sai mais por **e-mail**, **WhatsApp**, **telefone** ou **portal do fornecedor**?
- A consolidação hoje é **planilha manual**, ERP externo ou já existe algum modelo interno?
- Há interesse em **upload de PDFs** no Lplan com extração assistida vs. foco primeiro em **tabelas de referência** (SINAPI/ORSE) importadas?
- **LGPD e retenção**: quem pode ver propostas de quais fornecedores (mesmo raciocínio de tenant do assistente)?

Respostas a essas perguntas definem se o roadmap desse tema começa por **inbox + mapa**, por **dados de referência**, ou por **ambos em paralelo mínimo**.

## 9. Próximo passo quando for priorizar (WhatsApp)

1. Escolher **Meta direto vs BSP** (suporte, preço, Brasil).
2. Desenhar **modelo de vínculo** telefone–usuário–obra padrão.
3. Implementar **Fase 1** reutilizando testes do `assistente_lplan` para o núcleo de perguntas.

---

*Última atualização: secção de cotações/materiais alinhada ao Lplan + pontos a validar com a empresa; visão WhatsApp + dados da obra.*
