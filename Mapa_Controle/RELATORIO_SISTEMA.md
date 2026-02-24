# 📋 RELATÓRIO DETALHADO DO SISTEMA - MAPA DE CONTROLE DE SUPRIMENTOS

## 📌 INFORMAÇÕES GERAIS

**Nome do Sistema:** SupplyMap - Sistema de Controle de Suprimentos  
**Versão:** 1.0.0  
**Framework:** Django 5.0+  
**Linguagem:** Python 3.11+  
**Banco de Dados:** SQLite (desenvolvimento) / PostgreSQL (produção)  
**Data do Relatório:** 2024

---

## 🎯 OBJETIVO DO SISTEMA

O SupplyMap é um sistema web desenvolvido para **substituir a planilha "MAPA DE SUPRIMENTOS"** por um sistema dinâmico que:

1. **Unifica Planejamento e Realizado:**
   - **Planejamento (Engenharia):** Quantidades necessárias, locais de aplicação, prazos, responsáveis
   - **Realizado (Sienge):** Solicitações de Compra (SC), Pedidos de Compra (PC), recebimentos, notas fiscais

2. **Mantém Fidelidade Visual:**
   - Sistema de cores idêntico ao mapa original (branco, vermelho, amarelo, laranja, verde, atrasado)
   - Colunas e estrutura compatíveis com a planilha original

3. **Prepara Integração Futura:**
   - Arquitetura preparada para trocar importação CSV por API do Sienge
   - Padrão Provider para facilitar migração

---

## 🏗️ ARQUITETURA DO SISTEMA

### Estrutura de Apps Django

O sistema é dividido em **3 apps principais:**

#### 1. **`accounts/` - Autenticação e Grupos**

**Responsabilidade:** Gerenciamento de usuários, autenticação e controle de acesso por grupos.

**Arquivos Principais:**
- `models.py` - Vazio (usa User padrão do Django)
- `decorators.py` - Decorator `@require_group()` para proteger views por grupo
- `views.py` - Home e perfil do usuário
- `views_admin.py` - **Admin Central** (interface administrativa completa)
- `urls.py` - Rotas de autenticação e admin
- `management/commands/seed_grupos.py` - Comando para criar grupos padrão

**Grupos de Usuários:**
- **CHEFIA:** Visualização completa (readonly), acesso a dashboard, pode marcar "Não Aplica"
- **ENGENHARIA:** Edita campos de planejamento (local, prazo, quantidade, responsável, prioridade)
- **COMPRAS:** Visualização e comentários (opcional)
- **ALMOX:** Pode lançar alocação/recebimento manual

**URLs Principais:**
- `/accounts/login/` - Página de login
- `/accounts/logout/` - Logout
- `/accounts/home/` - Home do usuário
- `/accounts/profile/` - Perfil do usuário
- `/accounts/admin-central/` - **Dashboard administrativo**
- `/accounts/admin-central/criar-usuario/` - Criar novo usuário
- `/accounts/admin-central/gerenciar-usuarios/` - Gerenciar usuários existentes
- `/accounts/admin-central/criar-obra/` - Criar nova obra
- `/accounts/admin-central/gerenciar-obras/` - Gerenciar obras

---

#### 2. **`obras/` - Obras e Locais**

**Responsabilidade:** Gerenciamento de obras e hierarquia de locais dentro das obras.

**Models:**
- **`Obra`:** Representa uma obra/empreendimento
  - `codigo_sienge` (único) - Código da obra no Sienge
  - `nome` - Nome da obra
  - `ativa` - Status ativo/inativo

- **`LocalObra`:** Hierarquia de locais dentro de uma obra
  - `obra` - Obra pai
  - `nome` - Nome do local (ex: "Bloco A", "Pavimento 1", "Apto 101")
  - `tipo` - Tipo do local (BLOCO, PAVIMENTO, APTO, SETOR, OUTRO)
  - `parent` - Local pai (permite hierarquia: Bloco → Pavimento → Apto)

**Arquivos:**
- `models.py` - Models Obra e LocalObra
- `admin.py` - Configuração Django Admin
- `context_processors.py` - Context processor para seleção de obra ativa
- `urls.py` - URLs de seleção de obra
- `management/commands/seed_locais.py` - Comando para criar locais comuns

**Uso:** Cada item do mapa pode ter um `local_aplicacao` para rateio/alocação de materiais.

---

#### 3. **`suprimentos/` - Core do Sistema**

**Responsabilidade:** Gerenciamento do mapa de suprimentos, insumos, recebimentos e alocações.

**Models Principais:**

##### **`Insumo`** - Catálogo de Insumos
- `codigo_sienge` (único) - Código do insumo no Sienge
- `descricao` - Descrição do insumo
- `unidade` - Unidade de medida (KG, M², UND, etc)
- `ativo` - Status ativo/inativo
- `eh_macroelemento` - Indica se é macroelemento (grande volume/valor)

##### **`ItemMapa`** - Linha do Mapa (Coração do Sistema)
Representa a necessidade de um insumo em um local específico.

**Campos de Classificação:**
- `obra` - Obra onde será aplicado
- `categoria` - Categoria de aplicação (FUNDAÇÃO, ESTRUTURA, ALVENARIA, etc)
- `prioridade` - URGENTE, ALTA, MÉDIA, BAIXA
- `nao_aplica` - Flag para itens não aplicáveis

**Campos de Planejamento (Engenharia):**
- `insumo` - Insumo necessário
- `local_aplicacao` - Local onde será aplicado
- `responsavel` - Responsável técnico
- `prazo_necessidade` - Prazo que precisa do insumo
- `quantidade_planejada` - Quantidade necessária neste local
- `observacao_eng` - Observações da engenharia

**Campos de Ligação com Sienge:**
- `numero_sc` - Nº Solicitação de Compra
- `item_sc` - Nº do item na SC (quando houver múltiplos itens)
- `data_sc` - Data da SC
- `numero_pc` - Nº Pedido de Compra
- `data_pc` - Data do PC
- `empresa_fornecedora` - Fornecedor
- `prazo_recebimento` - Prazo previsto de entrega

**Propriedades Calculadas:**
- `status_css` - Classe CSS do status (branco/vermelho/amarelo/laranja/verde/atrasado)
- `status_etapa` - Texto do status (LEVANTAMENTO/SOLICITACAO/COMPRA/PARCIAL/ENTREGUE)
- `is_atrasado` - True se prazo vencido
- `percentual_entregue` - Percentual entregue (0 a 1)
- `quem_cobrar` - ENGENHARIA/COMPRAS/FORNECEDOR/ALMOXARIFADO
- `quantidade_alocada_local` - Quantidade alocada para este local específico
- `saldo_a_entregar_sienge` - Saldo pendente de entrega

##### **`RecebimentoObra`** - Recebimento na Obra (do Sienge)
Representa o que chegou na obra como um todo (sem local específico).

- `obra` - Obra onde chegou
- `insumo` - Insumo recebido
- `numero_sc` - Nº Solicitação de Compra
- `item_sc` - Nº do item na SC
- `data_sc` - Data da SC
- `numero_pc` - Nº Pedido de Compra
- `data_pc` - Data do PC
- `empresa_fornecedora` - Fornecedor
- `prazo_recebimento` - Prazo previsto
- `quantidade_solicitada` - Quantidade solicitada
- `quantidade_recebida` - Quantidade que chegou na obra
- `saldo_a_entregar` - Saldo pendente

##### **`AlocacaoRecebimento`** - Rateio de Recebimento por Local
Distribui o recebimento para os locais específicos da obra.

- `obra` - Obra
- `insumo` - Insumo
- `local_aplicacao` - Local para onde foi alocado
- `recebimento` - Recebimento de onde veio o material
- `item_mapa` - Item do mapa que recebeu a alocação
- `quantidade_alocada` - Quantidade alocada para este local
- `observacao` - Observação da alocação

**Validação:** Não permite alocar mais do que foi recebido.

##### **`NotaFiscalEntrada`** - Detalhe de NFs de Entrada
Detalhe das notas fiscais para drill-down e histórico.

- `obra` - Obra
- `insumo` - Insumo
- `recebimento` - Recebimento vinculado
- `numero_pc` - Nº Pedido de Compra
- `numero_nf` - Nº da Nota Fiscal
- `data_entrada` - Data de entrada
- `quantidade` - Quantidade da NF

##### **`HistoricoAlteracao`** - Auditoria de Alterações
Registro de todas as alterações feitas no sistema.

- `obra` - Obra
- `item_mapa` - Item alterado (pode ser null se foi exclusão)
- `tipo` - Tipo de alteração (CRIACAO, EDICAO, ALOCACAO, STATUS, IMPORTACAO, EXCLUSAO)
- `campo_alterado` - Campo que foi alterado
- `valor_anterior` - Valor antes da alteração
- `valor_novo` - Valor após a alteração
- `descricao` - Descrição legível
- `usuario` - Usuário que fez a alteração
- `data_hora` - Data e hora da alteração
- `ip_address` - IP do usuário

**Views (separadas por funcionalidade):**

##### **`views_engenharia.py`** - Views para Engenharia
- `mapa_engenharia()` - Tabela editável com KPIs no topo
  - Filtros: obra, categoria, local, prioridade, busca
  - Edição inline: local, responsável, prazo, quantidade, prioridade, observação
- `dashboard_2()` - Dashboard com KPIs e visualização de alocações
- `exportar_mapa_excel()` - Exporta mapa para Excel
- `criar_item_mapa()` - Cria novo item do mapa
- `criar_levantamento_rapido()` - Cria levantamento rápido
- `importar_sienge_upload()` - Upload e importação de CSV do Sienge
- `criar_insumo()` - Cria novo insumo

##### **`views_api.py`** - API Interna (AJAX)
- `item_detalhe()` - Retorna HTML do modal com detalhes + NFs + form de alocação
- `item_atualizar_campo()` - Atualiza campo via AJAX (engenharia)
- `item_toggle_nao_aplica()` - Toggle "Não Aplica" (chefia)
- `item_alocar()` - Realiza alocação de recebimento
- `item_remover_alocacao()` - Remove alocação
- `item_excluir()` - Exclui item do mapa
- `listar_insumos()` - Lista insumos (AJAX)
- `listar_locais()` - Lista locais (AJAX)
- `recebimentos_obra()` - Lista recebimentos da obra (AJAX)
- `listar_scs_disponiveis()` - Lista SCs disponíveis para alocação
- `busca_rapida_mobile()` - Busca rápida para mobile
- `dashboard2_alocar()` - Alocação via dashboard

##### **`views_webhook.py`** - Webhooks do Sienge
- `webhook_sienge()` - Recebe webhooks do Sienge (futuro)

**Templates:**
- `mapa_engenharia.html` - Tabela editável com KPIs, agrupamento, progresso, ícones
- `dashboard_2.html` - Dashboard com KPIs e visualização de alocações
- `importar_sienge.html` - Página de importação de CSV

**Comandos de Gerenciamento (`management/commands/`):**

1. **`importar_insumos_sienge.py`**
   - Importa catálogo de insumos do Sienge via CSV
   - Atualiza ou cria insumos baseado no código Sienge
   - Uso: `python manage.py importar_insumos_sienge --file insumos.csv`

2. **`importar_mapa_controle.py`**
   - Importa planilha completa do Mapa de Controle
   - **Matching inteligente:** busca por SC+insumo → PC+insumo → obra+insumo
   - **NUNCA sobrescreve planejamento** (só atualiza campos Sienge)
   - Cria itens se não existir planejamento
   - Loga erros por linha
   - Valida SC vazia + PC
   - Uso: `python manage.py importar_mapa_controle --file mapa.csv --obra-codigo OBRA001`

3. **`limpar_dados_importados.py`**
   - Limpa dados importados do Sienge (para reimportação)
   - Remove RecebimentoObra, NotaFiscalEntrada, mas mantém ItemMapa
   - Uso: `python manage.py limpar_dados_importados --obra-codigo OBRA001`

4. **`seed_teste.py`**
   - Popula banco com dados de teste realistas
   - Útil para testar o sistema sem integração com Sienge
   - Uso: `python manage.py seed_teste` ou `python manage.py seed_teste --limpar`

**Services (`services/sienge_provider.py`):**
- **`BaseSiengeProvider`:** Interface abstrata para providers do Sienge
- **`CSVSiengeProvider`:** Implementação CSV (usado atualmente)
- **`APISiengeProvider`:** Stub para API futura (não implementado)

**URLs Principais:**
- `/engenharia/mapa/` - Mapa editável
- `/engenharia/mapa/exportar-excel/` - Exportar mapa para Excel
- `/engenharia/mapa/criar-item/` - Criar novo item
- `/engenharia/mapa/novo-levantamento/` - Criar levantamento rápido
- `/engenharia/mapa/importar-sienge/` - Importar CSV do Sienge
- `/engenharia/insumo/criar/` - Criar novo insumo
- `/engenharia/dashboard-2/` - Dashboard com alocações
- `/api/internal/item/<id>/detalhe/` - Modal detalhes (AJAX)
- `/api/internal/item/atualizar-campo/` - AJAX update
- `/api/internal/item/<id>/alocar/` - Alocar recebimento (AJAX)
- `/api/internal/item/<id>/remover-alocacao/` - Remover alocação (AJAX)
- `/api/internal/item/<id>/excluir/` - Excluir item (AJAX)
- `/api/internal/insumos/` - Listar insumos (AJAX)
- `/api/internal/locais/` - Listar locais (AJAX)
- `/api/internal/recebimentos/<obra_id>/` - Listar recebimentos (AJAX)
- `/api/internal/scs/` - Listar SCs disponíveis (AJAX)
- `/api/webhook/sienge/` - Webhook do Sienge (futuro)

---

## 🎨 SISTEMA DE CORES E STATUS

O sistema utiliza um código de cores para indicar o status de cada item:

1. **⚪ BRANCO (`status-branco`):** Sem SC (levantamento pendente)
   - Engenharia ainda não criou a solicitação
   - Quem cobrar: ENGENHARIA

2. **🔴 VERMELHO (`status-vermelho`):** Tem SC mas sem PC (compras devendo)
   - Solicitação criada, aguardando Compras gerar PC
   - Quem cobrar: COMPRAS

3. **🟡 AMARELO (`status-amarelo`):** Tem PC mas sem recebimento (aguardando)
   - Pedido de compra gerado, aguardando fornecedor entregar
   - Quem cobrar: FORNECEDOR

4. **🟠 LARANJA (`status-laranja`):** Recebimento parcial
   - Chegou na obra mas quantidade < planejada
   - Quem cobrar: FORNECEDOR (se falta entregar) ou ALMOXARIFADO (se falta alocar)

5. **🟢 VERDE (`status-verde`):** Entregue completamente
   - Quantidade alocada >= quantidade planejada
   - Item concluído

6. **🔴 ATRASADO (`status-atrasado`):** Prazo vencido + saldo pendente
   - Sobrepõe outras cores
   - Animação pulsante para chamar atenção
   - Quem cobrar: Depende do status (ENGENHARIA/COMPRAS/FORNECEDOR)

7. **⚫ NÃO APLICA (`status-nao-aplica`):** Item marcado como não aplicável
   - Apenas chefia pode marcar
   - Cor preta

**Legenda:** Sempre visível no topo das telas para referência.

---

## 📊 FLUXO DE DADOS

### 1. Planejamento (Engenharia)
- Engenharia cria `ItemMapa` com:
  - Categoria, insumo, local de aplicação
  - Prazo de necessidade, quantidade planejada
  - Responsável, prioridade, observações
- Campos editáveis inline na interface

### 2. Importação do Sienge
- Comando `importar_mapa_controle` importa dados do Sienge via CSV
- **Matching inteligente:**
  - Busca ItemMapa existente por SC+insumo
  - Se não encontrar, busca por PC+insumo
  - Se não encontrar, busca por obra+insumo
  - Se não encontrar, cria novo ItemMapa
- **NUNCA sobrescreve planejamento:**
  - Só atualiza campos do Sienge (SC, PC, recebimentos)
  - Mantém intactos: local_aplicacao, prazo_necessidade, quantidade_planejada
- Cria `RecebimentoObra` se houver recebimento
- Cria `NotaFiscalEntrada` para cada NF

### 3. Cálculo de Status
- Sistema calcula automaticamente:
  - `status_css` baseado em SC/PC/recebimento/atraso
  - `quem_cobrar` baseado no status
  - `percentual_entregue` baseado em quantidade alocada vs planejada
  - `is_atrasado` se prazo vencido

### 4. Alocação de Recebimentos
- Almoarife/Engenharia aloca recebimentos para locais específicos
- Cria `AlocacaoRecebimento` vinculando:
  - RecebimentoObra → ItemMapa (local específico)
  - Quantidade alocada
- Validação: não pode ultrapassar quantidade recebida

### 5. Visualização e Cobrança (Chefia)
- Chefia visualiza tudo readonly com cores
- Identifica automaticamente quem cobrar
- Pode marcar "Não Aplica" se necessário
- Dashboard com KPIs e gráficos

---

## 🔐 SISTEMA DE PERMISSÕES

O sistema utiliza grupos do Django para controle de acesso:

### **ENGENHARIA**
- **Pode editar:** Campos de planejamento (local, prazo, quantidade, responsável, prioridade, observação)
- **Pode criar:** Novos itens do mapa, novos insumos
- **Pode importar:** CSV do Sienge
- **Pode alocar:** Recebimentos para locais
- **Pode visualizar:** Todos os campos (readonly para campos Sienge)

### **CHEFIA**
- **Pode visualizar:** Tudo (readonly)
- **Pode marcar:** "Não Aplica" em itens
- **Pode acessar:** Dashboard com KPIs e gráficos
- **Pode exportar:** Mapa para Excel

### **COMPRAS** (Opcional)
- **Pode visualizar:** Itens do mapa
- **Pode comentar:** (funcionalidade futura)

### **ALMOX** (Opcional)
- **Pode alocar:** Recebimentos para locais
- **Pode lançar:** Recebimento manual

**Proteção:** Views protegidas via decorator `@require_group()` em `accounts/decorators.py`

---

## 📦 DEPENDÊNCIAS

### Python (requirements.txt)
- **Django** >=5.0,<6.0 - Framework web
- **pandas** >=2.0.0,<3.0.0 - Processamento de dados CSV
- **openpyxl** >=3.1.0,<4.0.0 - Leitura/escrita de Excel
- **python-decouple** >=3.8,<4.0.0 - Gerenciamento de variáveis de ambiente
- **dj-database-url** >=2.1.0,<3.0.0 - Configuração de banco via URL
- **requests** >=2.31.0,<3.0.0 - Requisições HTTP (futuro para API)
- **psycopg2-binary** >=2.9.0,<3.0.0 - Driver PostgreSQL (produção)
- **gunicorn** >=21.2.0,<22.0.0 - Servidor WSGI (produção)
- **whitenoise** >=6.6.0,<7.0.0 - Servir arquivos estáticos (produção)
- **python-dateutil** >=2.8.2,<3.0.0 - Utilitários de data/hora

### Testes (Opcional)
- **pytest** >=7.4.0,<8.0.0
- **pytest-django** >=4.7.0,<5.0.0
- **model-bakery** >=1.12.0,<2.0.0

### JavaScript (package.json)
- **bootstrap** ^5.3.0 - Framework CSS
- **bootstrap-icons** ^1.11.0 - Ícones
- **chart.js** ^4.4.0 - Gráficos

---

## 🚀 INSTALAÇÃO E CONFIGURAÇÃO

### Pré-requisitos
- Python 3.11+
- pip (gerenciador de pacotes Python)
- PostgreSQL (produção) ou SQLite (desenvolvimento)
- Node.js e npm (opcional, para assets frontend)

### Passo a Passo

1. **Instalar dependências Python:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Configurar variáveis de ambiente:**
   Criar arquivo `.env` (não versionado) com:
   ```
   SECRET_KEY=sua-chave-secreta-aqui
   DEBUG=True
   ALLOWED_HOSTS=localhost,127.0.0.1
   DATABASE_URL=sqlite:///db.sqlite3  # ou postgresql://user:pass@localhost/dbname
   SIENGE_API_BASE_URL=https://api.sienge.com.br
   SIENGE_API_CLIENT_ID=
   SIENGE_API_CLIENT_SECRET=
   SIENGE_WEBHOOK_SECRET=
   ```

3. **Executar migrações:**
   ```bash
   python manage.py migrate
   ```

4. **Criar grupos de usuários:**
   ```bash
   python manage.py seed_grupos
   ```

5. **Criar superusuário:**
   ```bash
   python manage.py createsuperuser
   ```

6. **Executar servidor de desenvolvimento:**
   ```bash
   python manage.py runserver
   ```

7. **Acessar Admin Central:**
   - http://127.0.0.1:8000/accounts/admin-central/
   - Criar usuários e atribuir grupos
   - Criar obras

8. **Importar dados iniciais:**
   ```bash
   # Importar catálogo de insumos do Sienge
   python manage.py importar_insumos_sienge --file insumos.csv
   
   # Importar mapa completo do Mapa de Controle
   python manage.py importar_mapa_controle --file mapa.csv --obra-codigo OBRA001
   
   # Criar locais comuns
   python manage.py seed_locais --obra-codigo OBRA001 --blocos 3 --pavimentos 5
   
   # Popular com dados de teste (opcional)
   python manage.py seed_teste
   ```

---

## 📁 ESTRUTURA DE ARQUIVOS

```
Mapa_Controle/
├── accounts/                    # App de autenticação e grupos
│   ├── __init__.py
│   ├── admin.py
│   ├── apps.py
│   ├── decorators.py           # @require_group()
│   ├── models.py               # Vazio (usa User padrão)
│   ├── urls.py                 # Rotas de autenticação
│   ├── views.py                # Home e perfil
│   ├── views_admin.py          # Admin Central
│   ├── management/
│   │   └── commands/
│   │       └── seed_grupos.py  # Criar grupos
│   └── migrations/             # Migrações do banco
│
├── obras/                      # App de obras e locais
│   ├── __init__.py
│   ├── admin.py
│   ├── apps.py
│   ├── context_processors.py   # Contexto multi-obra
│   ├── models.py               # Obra, LocalObra
│   ├── urls.py                 # URLs de seleção de obra
│   ├── views.py
│   ├── management/
│   │   └── commands/
│   │       └── seed_locais.py  # Criar locais comuns
│   └── migrations/
│
├── suprimentos/                # App core do sistema
│   ├── __init__.py
│   ├── admin.py
│   ├── apps.py
│   ├── forms.py
│   ├── models.py               # Insumo, ItemMapa, RecebimentoObra, etc
│   ├── urls_api.py             # URLs da API interna
│   ├── urls_engenharia.py      # URLs de engenharia
│   ├── urls_webhook.py         # URLs de webhook
│   ├── views_api.py            # Views da API (AJAX)
│   ├── views_engenharia.py     # Views de engenharia
│   ├── views_webhook.py        # Views de webhook
│   ├── services/
│   │   ├── __init__.py
│   │   └── sienge_provider.py  # Provider pattern para Sienge
│   ├── templatetags/
│   │   ├── __init__.py
│   │   └── suprimentos_filters.py  # Filtros de template
│   ├── management/
│   │   └── commands/
│   │       ├── importar_insumos_sienge.py
│   │       ├── importar_mapa_controle.py
│   │       ├── limpar_dados_importados.py
│   │       └── seed_teste.py
│   ├── tests/                  # Testes automatizados
│   │   ├── __init__.py
│   │   ├── conftest.py
│   │   ├── test_chaos.py
│   │   ├── test_load.py
│   │   ├── test_math_integrity.py
│   │   └── test_sync_logic.py
│   └── migrations/
│
├── supplymap/                  # Configurações do projeto Django
│   ├── __init__.py
│   ├── settings.py             # Configurações
│   ├── urls.py                 # URLs principais
│   └── wsgi.py                 # WSGI para produção
│
├── templates/                  # Templates HTML
│   ├── base.html               # Template base
│   ├── accounts/               # Templates de autenticação
│   │   ├── login.html
│   │   ├── home.html
│   │   ├── profile.html
│   │   └── admin_central/      # Templates do admin central
│   └── suprimentos/            # Templates de suprimentos
│       ├── mapa_engenharia.html
│       ├── dashboard_2.html
│       └── importar_sienge.html
│
├── static/                     # Arquivos estáticos
│   ├── css/
│   │   ├── dashboard_2.css
│   │   └── supplymap.css       # Estilos principais
│   ├── js/
│   │   └── supplymap.js       # JavaScript principal
│   └── img/
│       └── lplan-logo.jpg
│
├── manage.py                   # Script de gerenciamento Django
├── requirements.txt            # Dependências Python
├── package.json                # Dependências JavaScript
├── pytest.ini                  # Configuração de testes
├── .gitignore                  # Arquivos ignorados pelo Git
├── README.md                    # Documentação básica
└── RELATORIO_SISTEMA.md         # Este relatório
```

---

## 🔧 CONFIGURAÇÕES IMPORTANTES

### settings.py

**Apps Instalados:**
- `accounts` - Autenticação
- `obras` - Obras e locais
- `suprimentos` - Core do sistema

**Banco de Dados:**
- SQLite por padrão (desenvolvimento)
- PostgreSQL via `DATABASE_URL` (produção)

**Idioma e Fuso:**
- `LANGUAGE_CODE = 'pt-br'`
- `TIME_ZONE = 'America/Sao_Paulo'`

**Arquivos Estáticos:**
- `STATIC_URL = 'static/'`
- `STATICFILES_DIRS = [BASE_DIR / 'static']`
- `STATIC_ROOT = BASE_DIR / 'staticfiles'` (produção)

**Configurações do Sienge:**
- `SIENGE_API_BASE_URL` - URL base da API
- `SIENGE_API_CLIENT_ID` - Client ID da API
- `SIENGE_API_CLIENT_SECRET` - Client Secret
- `SIENGE_WEBHOOK_SECRET` - Secret para validar webhooks

---

## 🧪 TESTES

O sistema possui testes automatizados em `suprimentos/tests/`:

- **`test_chaos.py`** - Testes de edge cases e situações extremas
- **`test_load.py`** - Testes de carga e performance
- **`test_math_integrity.py`** - Testes de integridade matemática (decimais)
- **`test_sync_logic.py`** - Testes de lógica de sincronização

**Executar testes:**
```bash
pytest
```

**Configuração:** `pytest.ini`

---

## 📝 COMANDOS DE GERENCIAMENTO DISPONÍVEIS

1. **`seed_grupos`** - Cria grupos padrão (CHEFIA, ENGENHARIA, COMPRAS, ALMOX)
2. **`seed_locais`** - Cria locais comuns (blocos, pavimentos)
3. **`importar_insumos_sienge`** - Importa catálogo de insumos
4. **`importar_mapa_controle`** - Importa mapa completo do Sienge
5. **`limpar_dados_importados`** - Limpa dados importados (para reimportação)
6. **`seed_teste`** - Popula banco com dados de teste

---

## 🔄 INTEGRAÇÃO COM SISTEMA CENTRAL LPLAN

### Preparação para Integração

O sistema está preparado para ser integrado ao sistema central da LPlan:

1. **Estrutura Modular:**
   - Apps Django independentes (`accounts`, `obras`, `suprimentos`)
   - Pode ser integrado como módulo no sistema central

2. **URLs com Prefixo:**
   - URLs já organizadas por app
   - Pode ser facilmente prefixado no sistema central

3. **Autenticação:**
   - Usa sistema de autenticação padrão do Django
   - Pode ser integrado com sistema de autenticação central da LPlan

4. **Banco de Dados:**
   - Pode usar o mesmo banco do sistema central
   - Models podem ser migrados para o banco central

5. **Templates:**
   - Templates podem ser adaptados para o layout do sistema central
   - CSS e JS podem ser integrados aos assets do sistema central

### Arquivos Essenciais para Integração

**Mínimo necessário:**
- Todos os apps (`accounts/`, `obras/`, `suprimentos/`)
- `supplymap/settings.py` (configurações)
- `supplymap/urls.py` (URLs principais)
- `templates/` (todos os templates)
- `static/` (CSS e JS)
- `requirements.txt` (dependências)

**Opcional (pode ser removido):**
- `suprimentos/tests/` (testes - manter apenas se necessário)
- `pytest.ini` (configuração de testes)
- `package.json` (se assets forem gerenciados centralmente)

**Não necessário:**
- `db.sqlite3` (banco local - já removido)
- `__pycache__/` (arquivos compilados - já removidos)
- `.env` (variáveis de ambiente - não versionar)

---

## 🎯 FUNCIONALIDADES PRINCIPAIS

### ✅ Implementadas

1. **Mapa de Suprimentos Editável:**
   - Edição inline de campos de planejamento
   - Filtros avançados (obra, categoria, local, prioridade, busca)
   - Agrupamento por categoria (expandir/recolher)
   - KPIs no topo (Total, Atrasados, Solicitados, Em Compra, Parciais, Entregues)
   - Barra de progresso (recebido/planejado)
   - Ícones de status
   - Sistema de cores completo

2. **Importação do Sienge:**
   - Importação via CSV
   - Matching inteligente (não sobrescreve planejamento)
   - Validações e logs de erro
   - Suporte a múltiplos itens por SC

3. **Alocação de Recebimentos:**
   - Alocação manual de recebimentos para locais
   - Validação de quantidades
   - Histórico de alocações

4. **Dashboard:**
   - KPIs principais
   - Gráficos (Chart.js)
   - Tabela de top atrasados
   - Filtros por obra e período

5. **Admin Central:**
   - Criar e gerenciar usuários
   - Criar e gerenciar obras
   - Atribuir grupos

6. **Auditoria:**
   - Histórico de alterações
   - Rastreamento de quem fez o quê e quando

### 🚧 Futuras (Preparadas)

1. **API do Sienge:**
   - Estrutura preparada (`APISiengeProvider`)
   - Webhook endpoint criado
   - Falta implementar a integração real

2. **Notificações:**
   - Estrutura de histórico pronta
   - Falta implementar sistema de notificações

3. **Exportação:**
   - Exportação para Excel já implementada
   - Pode ser expandida

---

## 📊 MÉTRICAS E KPIs

O sistema calcula automaticamente:

- **Total de Itens:** Total de itens no mapa
- **Atrasados:** Itens com prazo vencido e saldo pendente
- **Solicitados:** Itens com SC mas sem PC
- **Em Compra:** Itens com PC mas sem recebimento
- **Parciais:** Itens com recebimento parcial
- **Entregues:** Itens totalmente entregues
- **Tempo Médio SC→PC:** Tempo médio entre SC e PC
- **Top Atrasados:** Lista dos itens mais atrasados

---

## 🔒 SEGURANÇA

- **Autenticação:** Sistema padrão do Django
- **Autorização:** Controle por grupos
- **CSRF Protection:** Habilitado
- **XSS Protection:** Templates escapam automaticamente
- **SQL Injection:** Protegido pelo ORM do Django
- **Secrets:** Variáveis sensíveis em `.env` (não versionado)

---

## 📞 SUPORTE E MANUTENÇÃO

### Logs
- Logs de importação: Console durante importação
- Histórico de alterações: Banco de dados (`HistoricoAlteracao`)

### Backup
- Backup do banco de dados deve ser feito regularmente
- Histórico de alterações permite auditoria completa

### Monitoramento
- Verificar logs de erro do Django
- Monitorar performance de queries (usar `django-debug-toolbar` em dev)

---

## 📚 DOCUMENTAÇÃO ADICIONAL

- **README.md** - Documentação básica e guia rápido
- **Este relatório** - Documentação detalhada completa
- **Código comentado** - Models e views possuem docstrings detalhadas

---

## ✅ CHECKLIST DE LIMPEZA REALIZADA

- ✅ Removido `db.sqlite3` (banco local)
- ✅ Removidos `__pycache__/` (arquivos compilados Python)
- ✅ Removidos `*.pyc` (arquivos compilados)
- ✅ Verificado ausência de arquivos temporários (.log, .tmp)
- ✅ Verificado ausência de arquivos CSV/Excel de teste
- ✅ Mantidos arquivos de teste (úteis para desenvolvimento)
- ✅ Mantido `.gitignore` (configurado corretamente)

---

## 🎉 CONCLUSÃO

O **SupplyMap - Sistema de Controle de Suprimentos** é um sistema completo e funcional para gerenciamento de suprimentos em obras, substituindo planilhas estáticas por um sistema dinâmico e integrado.

**Principais Diferenciais:**
- ✅ Unifica planejamento (Engenharia) e realizado (Sienge)
- ✅ Sistema de cores visual e intuitivo
- ✅ Alocação de recebimentos por local
- ✅ Matching inteligente na importação
- ✅ Auditoria completa de alterações
- ✅ Preparado para integração com sistema central

**Pronto para:**
- ✅ Integração ao sistema central da LPlan
- ✅ Deploy em produção
- ✅ Expansão de funcionalidades

---

**Fim do Relatório**
