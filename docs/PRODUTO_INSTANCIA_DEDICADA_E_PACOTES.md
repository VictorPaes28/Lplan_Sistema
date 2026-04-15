# Produto: instância dedicada por empresa + pacotes modulares

**Data:** 2026-04-14  
**Relaciona com:** [Precificação comercial](precificacao_produto_lplan.md) (planos, apps e add-ons), [Plano Centro de Inteligência](PLANO_CENTRO_INTELIGENCIA_LPLAN.md) (IA e deploy).

---

## 1) Ideia central (o que estamos a vender)

- Cada **cliente (empresa)** recebe o **seu próprio software**: uma **instalação dedicada** — base de dados, ficheiros, domínio e hospedagem **separados** das restantes.
- **Não** é obrigatório um único SaaS multi-empresa na mesma máquina; o isolamento entre clientes vem do **ambiente** (um deploy por contrato), não de linhas `tenant_id` na mesma tabela.
- Comercialmente, vendes **pacotes**: cada empresa **não tem de comprar tudo** — combina **módulos/apps** (Diário, Gestão/Aprovações, Mapas, Comunicados/Megafone, Assistente/IA, etc.) e limites (utilizadores, obras, franquias de IA).

Esta visão **complementa** o documento de precificação: lá estão números e modularidade por app; aqui fixamos o **modelo de entrega** (uma instância por cliente) e o que isso implica em produto e engenharia.

---

## 2) Desenvolvimento da ideia

### 2.1 Porque instância dedicada faz sentido

- **Segurança e perceção**: muitas construtoras preferem “o nosso sistema no nosso servidor/conta”, sobretudo com dados de obra e contratos.
- **Conformidade**: LGPD e políticas internas são mais simples de argumentar quando há **fronteira clara** por ambiente.
- **Operação previsível**: carga de um cliente não “derruba” outro; upgrades podem ser **agendados por cliente**.

### 2.2 O que “pacotes” significam tecnicamente (neste modelo)

Não precisas de multi-tenancy na mesma base; precisas de **definir o que está ligado em cada deploy**:

| Conceito | Função |
|----------|--------|
| **Catálogo de módulos** | Lista fina do que pode ser vendido (app Django, integração, IA). |
| **Pacote / edição** | Conjunto de módulos + regras (ex.: máx. N obras, IA incluída ou não). |
| **Ativação por instância** | Em cada instalação: quais apps em `INSTALLED_APPS` / URLs / menus, ou flags em configuração. |
| **Configuração por cliente** | Nome comercial, logos, cores, `SITE_URL`, e-mail — via `.env` e/ou tabela de settings, não código. |

Ou seja: **o mesmo código-base**, **várias instâncias**, **cada uma configurada** para o que o cliente pagou.

### 2.3 White-label e personalização

- **Mínimo viável**: marca, favicon, título das páginas, textos de e-mail, remetente, URL pública — todos **parametrizáveis** por instância.
- **Avançado**: textos legais (termos, política de privacidade), idioma, desligar funcionalidades que o pacote não inclui (menus e rotas inacessíveis).

### 2.4 Entrega e ciclo de vida

- **Implantação repetível**: script ou imagem (Docker), checklist, migrações Django, ficheiro `.env` por cliente — para não ser “copiar ficheiros à mão” a cada venda.
- **Atualizações**: política de versão (LTS vs. última), notas de release, janela de manutenção **por cliente**.
- **Suporte**: níveis (horário, canal, SLA) alinhados ao preço do pacote (já alinhado em espírito ao doc de precificação).

### 2.5 Licenciamento (opcional mas comum)

Mesmo com instância dedicada, podes querer **controlo de distribuição**: chave de licença, data de validade, ou contrato que restringe **binário completo vs. edição limitada**. Isto é **comercial/legal + eventual verificação em runtime**, não multi-tenant.

---

## 3) O que isto **não** exige

- **Um único servidor** a servir todas as empresas na mesma base de dados.
- **Modelo `Organização` obrigatório** em todas as tabelas *só* por causa do produto — pode existir por outras razões (hierarquia interna), mas **não** é o pilar do teu modelo de venda descrito aqui.

---

## 4) Estado atual do repositório (visão honesta)

### 4.1 O que já ajuda

- **`settings.py` já lê `.env`**: `SECRET_KEY`, `ALLOWED_HOSTS`, `SITE_URL`, base de dados, e-mail — bom para **uma instância = um `.env`**.
- **Documentação de deploy e produção**: `docs/env.producao.correto.txt`, `PLANO_CENTRO_INTELIGENCIA_LPLAN.md` (checklist hospedagem, IA).
- **Precificação modular** já descrita em `precificacao_produto_lplan.md` (apps, utilizadores, IA).
- **Apps bem separados** em `INSTALLED_APPS` (ex.: `gestao_aprovacao`, `suprimentos`, `comunicados`, `assistente_lplan`) — base natural para **ligar/desligar módulos** por instalação.

### 4.2 Lacunas para cumprir a visão “produto dedicado + pacotes”

| Área | Situação | O que falta |
|------|-----------|-------------|
| **Marca / white-label** | Textos e logos **LPLAN** hardcoded em `base.html`, login, etc. | Settings (`SITE_NAME`, logos) + templates a usar variáveis; remover dependência visual do nome LPLAN onde for “produto”. |
| **Pacotes no código** | Todos os apps listados em `INSTALLED_APPS` para todos | Convenção: `INSTALLED_APPS` / `urls.py` condicionais por env (ex. `ENABLED_APPS=...`) ou settings por pacote; menus (`sidebar`) a respeitar módulos desligados. |
| **E-mails** | Vários fallbacks `sistema.lplan.com.br`, textos “sistema LPLAN” | Centralizar remetente e copy em settings; evitar URLs fixas da Lplan em `gestao_aprovacao/email_utils.py` e similares. |
| **Documentação de entrega** | Fragmentada | Um **runbook**: novo cliente → requisitos, `.env`, migrações, SSL, backup, lista de módulos do pacote. |
| **Testes de “edição mínima”** | Pouco provável haver CI que valide “só Diário + Mapa” | Testes ou checklist manual por combinação crítica de apps. |
| **Nome do projeto** | “LPLAN Central” em vários sítios | Decisão de produto: marca **tecnológica** interna vs. **marca branca** por cliente (documentar). |

### 4.3 Prioridade sugerida (ordem prática)

1. **Parametrizar marca** (nome, logo, `SITE_URL`, e-mails) — maior impacto percebido pelo cliente.  
2. **Flags de módulos** (`ENABLED_APPS` ou equivalente) + URLs e menu alinhados.  
3. **Runbook de instalação** por pacote (o que ativar no `.env` e quais migrações).  
4. **Licenciamento** só se o modelo de negócio exigir controlo técnico além do contrato.

---

## 5) Referências internas

- Comercial e módulos: `docs/precificacao_produto_lplan.md`  
- IA, API e deploy partilhado (contexto técnico): `docs/PLANO_CENTRO_INTELIGENCIA_LPLAN.md`  
- Visão WhatsApp / separação de dados por empresa (ainda backlog): `docs/FUTURO_ASSISTENTE_WHATSAPP_OBRA.md`

Para uma **análise técnica alargada** (módulos, legado, testes, CI, APIs, observabilidade e roadmap), ver **[ANALISE_ARQUITETURA_E_MELHORIAS.md](ANALISE_ARQUITETURA_E_MELHORIAS.md)**.

---

*Documento vivo: atualizar quando fechar decisões de marca branca, empacotamento e runbook de deploy.*
