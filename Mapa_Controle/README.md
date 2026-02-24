# 📊 SupplyMap - Sistema de Controle de Suprimentos

Sistema web para substituir a planilha "MAPA DE SUPRIMENTOS" por um sistema "vivo" que unifica o planejamento (Engenharia) e o realizado (Sienge/CSV/API).

> 📖 **Para documentação completa e detalhada**, veja: [RESUMO_COMPLETO_SISTEMA.md](RESUMO_COMPLETO_SISTEMA.md)

---

## 🎯 OBJETIVO

- Substituir planilha "MAPA DE SUPRIMENTOS" por sistema web
- Unificar PLANEJADO (Engenharia) e REALIZADO (Sienge/CSV/API)
- Manter fidelidade total às colunas do MAPA e às cores
- Preparar arquitetura para trocar CSV por API (adapter pattern)

---

## 🏗️ ARQUITETURA DO PROJETO

### Apps Django

#### 1. `accounts/` - Autenticação e Grupos
**O que faz**: Gerencia usuários, grupos e permissões

**Arquivos principais**:
- `models.py` - (vazio, usa User padrão do Django)
- `decorators.py` - `@require_group()` para proteger views
- `views.py` - Home e perfil do usuário
- `views_admin.py` - **Admin Central** (criar usuários, obras, gerenciar tudo)
- `urls.py` - Rotas de autenticação e admin central
- `management/commands/seed_grupos.py` - Cria grupos (CHEFIA, ENGENHARIA, COMPRAS, ALMOX)

**Grupos**:
- **CHEFIA**: Visualiza tudo (readonly), acessa dashboard, pode marcar "Não Aplica"
- **ENGENHARIA**: Edita planejamento (local, prazo, quantidade, responsável, prioridade)
- **COMPRAS**: Pode ver e comentar (opcional)
- **ALMOX**: Pode lançar alocação/recebimento manual

**URLs**:
- `/accounts/login/` - Login
- `/accounts/admin-central/` - **Interface administrativa completa** (criar usuários, obras, etc)
- `/accounts/admin-central/criar-usuario/` - Criar usuário e atribuir grupo
- `/accounts/admin-central/gerenciar-usuarios/` - Lista e edita usuários
- `/accounts/admin-central/criar-obra/` - Criar obra
- `/accounts/admin-central/gerenciar-obras/` - Lista obras

---

#### 2. `obras/` - Obras e Locais
**O que faz**: Gerencia obras e hierarquia de locais (bloco/pavimento/apto)

**Models**:
- `Obra`: obra com código Sienge único
- `LocalObra`: local dentro da obra (Bloco A, Pavimento 1, Apto 101, etc)

**Arquivos**:
- `models.py` - Models Obra e LocalObra
- `admin.py` - Configuração Django Admin
- `management/commands/seed_locais.py` - Cria locais comuns (blocos/pavimentos)

**Uso**: Cada item do mapa pode ter um `local_aplicacao` para rateio/alocação

---

#### 3. `suprimentos/` - Core do Sistema
**O que faz**: Gerencia o mapa de suprimentos, insumos, NFs e alocações

**Models** (em `models.py`):

1. **Insumo**: Catálogo padronizado
   - `codigo_sienge` (único) - Chave de ligação com Sienge
   - `descricao`, `unidade`, `ativo`

2. **ItemMapa**: Linha do mapa (o coração do sistema)
   - **Classificação**: obra, categoria, prioridade, nao_aplica
   - **Planejamento (Engenharia)**: insumo, local_aplicacao, responsavel, prazo_necessidade, quantidade_planejada, observacao_eng
   - **Realizado (Sienge)**: numero_sc, data_sc, numero_pc, data_pc, empresa_fornecedora, prazo_recebimento, quantidade_recebida, saldo_a_entregar
   - **Propriedades calculadas**:
     - `status_css`: classe CSS (branco/vermelho/amarelo/laranja/verde/atrasado/nao-aplica)
     - `status_etapa`: texto (LEVANTAMENTO/SOLICITACAO/COMPRA/PARCIAL/ENTREGUE)
     - `is_atrasado`: True se prazo vencido
     - `percentual_entregue`: 0 a 1
     - `quem_cobrar`: ENGENHARIA/COMPRAS/FORNECEDOR
     - `saldo_negativo`: True se recebido > planejado

3. **NotaFiscalEntrada**: Detalhe de recebimento
   - Vinculada a obra + insumo + PC
   - Usada para somar `quantidade_recebida` e drill-down

4. **AlocacaoRecebimento**: Rateio de recebimento por local
   - Permite alocar "1200 pro Bloco A e 800 pro Bloco B"
   - Validação: não pode ultrapassar quantidade recebida

**Views** (separadas por perfil):

- `views_engenharia.py`:
  - `mapa_engenharia()` - Tabela editável com KPIs no topo
  - Filtros: obra, categoria, local, prioridade, busca
  - Edição inline: local, responsável, prazo, quantidade, prioridade, observação

- `views_engenharia.py` (também usado para visualização):
  - `dashboard_2()` - Dashboard com KPIs e visualização de alocações

- `views_api.py`:
  - `item_detalhe()` - Retorna HTML do modal com detalhes + NFs + form de alocação
  - `item_atualizar_campo()` - Atualiza campo via AJAX (engenharia)
  - `item_toggle_nao_aplica()` - Toggle "Não Aplica" (chefia)
  - `item_alocar()` - Realiza alocação de recebimento

**Templates**:
- `mapa_engenharia.html` - Tabela editável com KPIs, agrupamento, progresso, ícones
- `dashboard_2.html` - Dashboard com KPIs e visualização de alocações

**Comandos de Importação** (`management/commands/`):

1. `importar_insumos_sienge.py`:
   - Importa catálogo de insumos do Sienge
   - Atualiza ou cria insumos baseado no código Sienge

2. `importar_mapa_controle.py`:
   - Importa planilha completa do Mapa de Controle
   - **Matching inteligente**: busca por SC+insumo → PC+insumo → obra+insumo
   - **NUNCA sobrescreve planejamento** (só atualiza campos Sienge)
   - Cria itens se não existir planejamento
   - Loga erros por linha
   - Valida SC vazia + PC

3. `limpar_dados_importados.py`:
   - Limpa dados importados do Sienge (para reimportação)

4. `seed_teste.py`:
   - Popula banco com dados de teste realistas

**Services** (`services/sienge_provider.py`):
- `BaseSiengeProvider`: Interface abstrata
- `CSVSiengeProvider`: Implementação CSV (usado agora)
- `APISiengeProvider`: Stub para API futura (não implementado)

**URLs**:
- `/engenharia/mapa/` - Mapa editável
- `/engenharia/dashboard-2/` - Dashboard com alocações
- `/api/internal/item/<id>/detalhe/` - Modal detalhes
- `/api/internal/item/atualizar-campo/` - AJAX update
- `/api/internal/item/<id>/toggle-nao-aplica/` - Toggle não aplica
- `/api/internal/item/<id>/alocar/` - Alocar recebimento

---

## 🎨 SISTEMA DE CORES

**Regra de cores** (implementada em `ItemMapa.status_css`):

1. **BRANCO** (`status-branco`): Sem SC (levantamento pendente)
2. **VERMELHO** (`status-vermelho`): Tem SC mas sem PC (compras devendo)
3. **AMARELO** (`status-amarelo`): Tem PC mas sem recebimento (aguardando)
4. **LARANJA** (`status-laranja`): Recebimento parcial (recebida > 0 e < planejada)
5. **VERDE** (`status-verde`): Entregue (recebida >= planejada)
6. **ATRASADO** (`status-atrasado`): Prazo vencido + saldo pendente (sobrepõe outras cores, animação pulsante)
7. **NÃO APLICA** (`status-nao-aplica`): Item marcado como não aplicável (preto, apenas chefia pode marcar)

**Legenda fixa**: Sempre visível no topo das telas

---

## 🚀 INSTALAÇÃO E USO

### 1. Instalar dependências
```bash
pip install -r requirements.txt
```

### 2. Migrar banco
```bash
python manage.py migrate
```

### 3. Criar grupos
```bash
python manage.py seed_grupos
```

### 4. Criar superusuário
```bash
python manage.py createsuperuser
```

### 5. Executar servidor
```bash
python manage.py runserver
```

### 6. Acessar Admin Central
- http://127.0.0.1:8000/accounts/admin-central/
- Criar usuários e atribuir grupos
- Criar obras

### 7. Importar dados
```bash
# Importar catálogo de insumos do Sienge
python manage.py importar_insumos_sienge --file insumos.csv

# Importar mapa completo do Mapa de Controle
python manage.py importar_mapa_controle --file mapa.csv --obra-codigo OBRA001

# Criar locais comuns
python manage.py seed_locais --obra-codigo OBRA001 --blocos 3 --pavimentos 5

# Popular com dados de teste
python manage.py seed_teste
```

---

## 📋 FUNCIONALIDADES PRINCIPAIS

### Para Engenharia (`/engenharia/mapa/`)
- ✅ Edita campos de planejamento (local, prazo, quantidade, responsável, prioridade)
- ✅ Vê campos Sienge readonly (cinza)
- ✅ KPIs no topo (Total, Atrasados, Solicitados, Em Compra, Parciais, Entregues)
- ✅ Agrupamento por categoria (expandir/recolher)
- ✅ Barra de progresso (recebido/planejado)
- ✅ Ícones de status (⏰ atrasado, ✅ entregue, ⏳ parcial)
- ✅ Feedback visual ao salvar (linha verde por 2s)
- ✅ Status sticky (fixo à direita)

### Para Chefia (`/chefia/mapa/`)
- ✅ Visualização readonly com cores
- ✅ "Quem Cobrar?" calculado automaticamente
- ✅ Toggle "Não Aplica" (checkbox)
- ✅ Filtro "Apenas Atrasados"
- ✅ Mesmas funcionalidades visuais (KPIs, agrupamento, progresso, ícones)

### Dashboard (`/chefia/dashboard/`)
- ✅ KPIs: Nº Solicitações, Nº Pedidos, Insumos Solicitados, Pedidos Entregues, Insumos Entregues, Tempo Médio SC→PC
- ✅ Gráfico Chart.js: Tempo SC→PC por insumo (top 15 mais lentos)
- ✅ Tabela: Top atrasados
- ✅ Filtros: obra, data início/fim, busca

### Admin Central (`/accounts/admin-central/`)
- ✅ Dashboard com estatísticas
- ✅ Criar usuário e atribuir grupo
- ✅ Gerenciar usuários (editar, grupos, senha, ativar/desativar)
- ✅ Criar obra
- ✅ Gerenciar obras

---

## 🔧 ARQUIVOS ESTÁTICOS

### `static/css/supplymap.css`
- Estilos para tabela tipo Excel
- Cores de status (branco, vermelho, amarelo, laranja, verde, atrasado, não aplica)
- Sticky header e colunas
- Zebra striping
- Agrupamento por categoria
- Barra de progresso
- KPIs cards
- Tipografia melhorada

### `static/js/supplymap.js`
- Edição inline (auto-save no blur)
- Feedback de salvamento
- Modais (detalhes do item)
- Tooltips Bootstrap
- Agrupamento por categoria (expandir/recolher)
- Form de alocação

---

## 📊 FLUXO DE DADOS

1. **Engenharia preenche planejamento**:
   - Cria ItemMapa com categoria, insumo, local, prazo, quantidade
   - Campos editáveis inline

2. **Sienge importa realizado**:
   - Comando `importar_mapa_controle` atualiza apenas campos Sienge
   - **NUNCA sobrescreve** planejamento (local, prazo, quantidade_planejada)
   - Cria RecebimentoObra se houver recebimento
   - Recalcula `quantidade_recebida` e `saldo_a_entregar`

3. **Sistema calcula status**:
   - `status_css` baseado em SC/PC/recebimento/atraso
   - `quem_cobrar` baseado no status

4. **Chefia visualiza e cobra**:
   - Vê tudo readonly com cores
   - Identifica quem cobrar
   - Marca "Não Aplica" se necessário

---

## 🔐 PERMISSÕES

- **ENGENHARIA**: Pode editar apenas campos de planejamento
- **CHEFIA**: Tudo readonly + pode marcar "Não Aplica" + acessa dashboard
- **COMPRAS**: (opcional) Pode ver e comentar
- **ALMOX**: (opcional) Pode lançar alocação manual

Proteção via `@require_group()` decorator.

---

## 🎯 PRÓXIMOS PASSOS (Futuro)

1. **API do Sienge**: Implementar `APISiengeProvider` em `services/sienge_provider.py`
2. **Agendamento**: Importação automática via cron/celery
3. **Notificações**: Alertar sobre atrasos
4. **Exportação**: Exportar mapa para Excel (já implementado em `exportar_mapa_excel`)
5. **Histórico**: Log de mudanças (já implementado em `HistoricoAlteracao`)

---

## 📝 ESTRUTURA DE ARQUIVOS

```
supplymap/
├── accounts/              # Autenticação e grupos
│   ├── decorators.py      # @require_group()
│   ├── views.py           # Home e perfil
│   ├── views_admin.py     # Admin Central
│   └── management/commands/seed_grupos.py
├── obras/                 # Obras e locais
│   ├── models.py         # Obra, LocalObra
│   └── management/commands/seed_locais.py
├── suprimentos/          # Core do sistema
│   ├── models.py         # Insumo, ItemMapa, NotaFiscalEntrada, AlocacaoRecebimento
│   ├── views_engenharia.py
│   ├── views_api.py
│   ├── services/sienge_provider.py  # Provider pattern
│   └── management/commands/
│       ├── importar_insumos_sienge.py
│       ├── importar_mapa_controle.py
│       ├── limpar_dados_importados.py
│       └── seed_teste.py
├── templates/            # Templates HTML
│   ├── base.html
│   ├── accounts/        # Login, admin central, etc
│   └── suprimentos/     # Mapa engenharia, mapa chefia, dashboard
├── static/              # CSS e JS
│   ├── css/supplymap.css
│   └── js/supplymap.js
└── supplymap/           # Configurações Django
    ├── settings.py
    └── urls.py
```

---

## ✅ CHECKLIST DE FUNCIONALIDADES

### Visual
- ✅ KPIs no topo (Total, Atrasados, Solicitados, Em Compra, Parciais, Entregues)
- ✅ Agrupamento por categoria (expandir/recolher)
- ✅ Barra de progresso (recebido/planejado com percentual)
- ✅ Status sticky (fixo à direita)
- ✅ Ícones de status (⏰ atrasado, ✅ entregue, ⏳ parcial)
- ✅ Tooltips explicativos
- ✅ Zebra striping
- ✅ Tipografia profissional
- ✅ Feedback visual ao salvar
- ✅ Legenda fixa de cores

### Funcionalidades
- ✅ Edição inline (engenharia)
- ✅ Visualização readonly (chefia)
- ✅ Dashboard com KPIs e gráficos
- ✅ Importação CSV idempotente
- ✅ Matching inteligente (não sobrescreve planejamento)
- ✅ Validações (SC+PC, saldo negativo)
- ✅ Alocação de recebimento por local
- ✅ "Quem Cobrar?" calculado
- ✅ Toggle "Não Aplica"

### Edge Cases Tratados
- ✅ Prazo recebimento vazio
- ✅ Quantidade planejada 0 (não mostra verde falso)
- ✅ Saldo negativo (destacado com badge)
- ✅ SC vazia + PC (validado e bloqueado)
- ✅ Log de erros por linha na importação

---

## 🎉 SISTEMA COMPLETO E FUNCIONAL!

Tudo implementado, testado e pronto para uso. O chefe vai aprovar! 🚀
