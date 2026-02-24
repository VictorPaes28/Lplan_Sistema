# 📘 Guia do Diário de Obra - Sistema LPLAN

## 🎯 Visão Geral

Este documento serve como **guia técnico completo** para integração do sistema **Diário de Obra** com outros projetos da LPLAN. Ele explica **o que o sistema faz**, **como funciona**, **o que pode ser feito** e **o que NÃO pode ser feito**.

---

## 📋 Índice

1. [O que este sistema faz](#o-que-este-sistema-faz)
2. [Arquitetura e Tecnologias](#arquitetura-e-tecnologias)
3. [Estrutura de Dados](#estrutura-de-dados)
4. [APIs e Endpoints](#apis-e-endpoints)
5. [O que PODE ser feito](#o-que-pode-ser-feito)
6. [O que NÃO PODE ser feito](#o-que-não-pode-ser-feito)
7. [Regras de Negócio Críticas](#regras-de-negócio-críticas)
8. [Dependências e Requisitos](#dependências-e-requisitos)
9. [Como Integrar](#como-integrar)
10. [Limitações e Considerações](#limitações-e-considerações)

---

## 🎯 O que este sistema faz

### Funcionalidade Principal
Sistema completo de **gestão de diários de obra** para projetos de construção civil, com:
- **Estrutura Analítica de Projetos (EAP)** hierárquica
- **Workflow de aprovação** de relatórios diários
- **Geração de PDFs** profissionais (formato RQ-10)
- **Gestão de recursos** (mão de obra e equipamentos)
- **Upload e gestão de mídia** (fotos, vídeos, anexos)
- **Sistema de notificações**

### Casos de Uso
1. **Engenheiros/Fiscais**: Preencher diários diários de obra com atividades, progresso, fotos
2. **Supervisores**: Revisar e aprovar diários
3. **Gestores**: Visualizar relatórios, estatísticas, exportar dados
4. **Administradores**: Gerenciar projetos, atividades EAP, recursos

---

## 🏗️ Arquitetura e Tecnologias

### Stack Tecnológico
- **Backend**: Django 5.2.11 (Python 3.10+)
- **API**: Django REST Framework 3.16.1
- **Frontend**: Templates Django + HTMX + Alpine.js
- **Banco de Dados**: PostgreSQL (produção) ou SQLite (desenvolvimento)
- **Task Queue**: Celery + Redis
- **PDF**: WeasyPrint (preferencial) ou xhtml2pdf (fallback)
- **EAP Hierárquica**: django-treebeard (Materialized Path)

### Estrutura de Diretórios
```
Diario_obra/
├── core/                    # App principal Django
│   ├── models.py           # Modelos de dados
│   ├── views.py            # ViewSets DRF (API REST)
│   ├── frontend_views.py   # Views para templates HTML
│   ├── serializers.py      # Serializers DRF
│   ├── forms.py            # Django Forms
│   ├── services.py         # Lógica de negócio
│   ├── permissions.py      # Permissões customizadas
│   ├── tasks.py            # Tarefas Celery
│   ├── utils/
│   │   └── pdf_generator.py # Geração de PDF
│   └── templates/          # Templates HTML
├── diario_obra/            # Configurações do projeto
│   ├── settings.py
│   ├── urls.py
│   └── celery.py
└── requirements.txt
```

---

## 📊 Estrutura de Dados

### Modelos Principais

#### 1. **Project** (Projeto)
```python
# Entidade raiz - representa um projeto de construção
- code: str (único, ex: "PROJ-2024-001")
- name: str
- description: TextField
- address: str
- responsible: str
- client_name: str
- contract_number: str
- start_date: Date
- end_date: Date
- is_active: Boolean
```

**Relacionamentos**:
- `activities` (1:N) → Activity
- `diaries` (1:N) → ConstructionDiary

#### 2. **Activity** (Atividade EAP)
```python
# Hierarquia infinita usando django-treebeard (MP_Node)
- project: ForeignKey → Project
- name: str
- code: str (ex: "1.2.1")
- description: TextField
- weight: Decimal (0-100, para progresso ponderado)
- status: TextChoices (NOT_STARTED, IN_PROGRESS, COMPLETED, BLOCKED, CANCELLED)
- planned_start: Date
- planned_end: Date
```

**Características Especiais**:
- **Herda de MP_Node** (Materialized Path) - suporta hierarquia infinita
- **Métodos treebeard**: `get_children()`, `get_descendants()`, `get_ancestors()`, `move()`
- **Performance**: Otimizado para milhares de atividades

#### 3. **ConstructionDiary** (Diário de Obra)
```python
# Registro diário principal
- project: ForeignKey → Project
- date: Date (único por projeto)
- status: TextChoices (PREENCHENDO, REVISAR, APROVADO)
- report_number: Integer (sequencial por projeto)
- created_by: ForeignKey → User
- reviewed_by: ForeignKey → User (nullable)
- approved_at: DateTime (nullable)
- work_hours: Decimal
- weather_morning: str
- weather_afternoon: str
- weather_night: str
- pluviometric: Decimal
- stoppages: TextField
- accidents: TextField
- imminent_risks: TextField
- incidents: TextField
- inspections: TextField
- inspection_responsible: str
- dds: TextField
- production_responsible: str
- general_notes: TextField
```

**Workflow de Estados**:
```
PREENCHENDO → REVISAR → APROVADO
   ↑            ↓
   └────────────┘ (rejeitar volta para PREENCHENDO)
```

**Regras Importantes**:
- `report_number` é **sequencial por projeto** (não global)
- Diários **APROVADOS são imutáveis** (ReadOnly)
- Apenas o `created_by` pode mover de PREENCHENDO → REVISAR
- Apenas usuários com `can_approve_diary` podem aprovar

#### 4. **DailyWorkLog** (Registro de Trabalho Diário)
```python
# Registro de progresso em uma atividade específica
- diary: ForeignKey → ConstructionDiary
- activity: ForeignKey → Activity
- location: str
- percentage_executed_today: Decimal (0-100)
- accumulated_progress_snapshot: Decimal (0-100)
- notes: TextField
- resources_labor: ManyToMany → Labor
- resources_equipment: ManyToMany → Equipment
```

**Constraint Único**:
- `unique_together = [['activity', 'diary']]` - **Uma atividade por diário**

#### 5. **Labor** (Mão de Obra)
```python
# Recurso de mão de obra
- name: str
- role: TextChoices (INDIRETO, DIRETO, TERCEIROS, OUTRO)
- role_custom: str (se role=OUTRO)
- company: str
- hourly_rate: Decimal
- is_active: Boolean
```

#### 6. **Equipment** (Equipamento)
```python
# Recurso de equipamento
- name: str
- code: str (único)
- equipment_type: str
- is_active: Boolean
```

#### 7. **DiaryImage** (Foto do Diário)
```python
- diary: ForeignKey → ConstructionDiary
- image: ImageField
- caption: str (obrigatório)
- is_approved_for_report: Boolean
- uploaded_at: DateTime
```

#### 8. **DiaryVideo** (Vídeo do Diário)
```python
- diary: ForeignKey → ConstructionDiary
- video: FileField
- caption: str
- uploaded_at: DateTime
```

#### 9. **DiaryAttachment** (Anexo do Diário)
```python
- diary: ForeignKey → ConstructionDiary
- file: FileField
- description: str
- uploaded_at: DateTime
```

#### 10. **DiaryOccurrence** (Ocorrência do Diário)
```python
- diary: ForeignKey → ConstructionDiary
- description: TextField
- tags: ManyToMany → OccurrenceTag
- created_at: DateTime
```

---

## 🔌 APIs e Endpoints

### API REST (DRF)

**Base URL**: `/api/`

#### ViewSets Disponíveis:

1. **ProjectViewSet**
   - `GET /api/projects/` - Listar projetos
   - `POST /api/projects/` - Criar projeto
   - `GET /api/projects/{id}/` - Detalhes do projeto
   - `PUT/PATCH /api/projects/{id}/` - Atualizar projeto
   - `DELETE /api/projects/{id}/` - Deletar projeto
   - `GET /api/projects/{id}/progress/` - Progresso do projeto

2. **ActivityViewSet**
   - `GET /api/activities/` - Listar atividades
   - `POST /api/activities/` - Criar atividade
   - `GET /api/activities/{id}/` - Detalhes da atividade
   - `PUT/PATCH /api/activities/{id}/` - Atualizar atividade
   - `DELETE /api/activities/{id}/` - Deletar atividade
   - `POST /api/activities/{id}/move/` - Mover atividade na árvore

3. **ConstructionDiaryViewSet**
   - `GET /api/diaries/` - Listar diários
   - `POST /api/diaries/` - Criar diário
   - `GET /api/diaries/{id}/` - Detalhes do diário
   - `PUT/PATCH /api/diaries/{id}/` - Atualizar diário
   - `POST /api/diaries/{id}/move_to_review/` - Mover para revisão
   - **IMPORTANTE**: Diários APROVADOS são ReadOnly

4. **DailyWorkLogViewSet**
   - `GET /api/worklogs/` - Listar registros
   - `POST /api/worklogs/` - Criar registro
   - `GET /api/worklogs/{id}/` - Detalhes
   - `PUT/PATCH /api/worklogs/{id}/` - Atualizar
   - `DELETE /api/worklogs/{id}/` - Deletar

5. **LaborViewSet**, **EquipmentViewSet**
   - CRUD completo

6. **DiaryImageViewSet**
   - CRUD completo de imagens

### Frontend URLs (Templates)

**Base URL**: `/` (raiz)

Principais rotas:
- `/login/` - Login
- `/dashboard/` - Dashboard principal
- `/projects/` - Lista de projetos
- `/diaries/new/` - Criar diário
- `/diaries/{id}/` - Detalhes do diário
- `/diaries/{id}/pdf/` - Gerar PDF
- `/diaries/{id}/excel/` - Exportar Excel
- `/diaries/{id}/approve/` - Aprovar diário
- `/reports/` - Lista de relatórios

---

## ✅ O que PODE ser feito

### 1. **Integração via API REST**
- ✅ Consumir todos os endpoints DRF
- ✅ Criar/ler/atualizar/deletar recursos
- ✅ Autenticação via Session ou Token
- ✅ Filtros e busca via django-filter

### 2. **Acesso a Dados**
- ✅ Ler projetos, atividades, diários
- ✅ Consultar progresso de projetos
- ✅ Exportar dados (PDF, Excel)
- ✅ Acessar mídia (fotos, vídeos, anexos)

### 3. **Operações Permitidas**
- ✅ Criar novos projetos
- ✅ Adicionar atividades à EAP
- ✅ Criar diários de obra
- ✅ Adicionar worklogs (registros de trabalho)
- ✅ Upload de mídia
- ✅ Mover diário para revisão (se criador)
- ✅ Aprovar diário (se tiver permissão)

### 4. **Integração de Dados**
- ✅ Importar projetos de outros sistemas
- ✅ Sincronizar dados via API
- ✅ Compartilhar autenticação (User model padrão Django)

### 5. **Extensões**
- ✅ Adicionar novos campos aos modelos (via migrações)
- ✅ Criar novos endpoints API
- ✅ Adicionar novos templates/frontend
- ✅ Criar novas tarefas Celery

---

## ❌ O que NÃO PODE ser feito

### 1. **Modificações em Diários Aprovados**
- ❌ **NÃO pode editar** diários com `status='APROVADO'`
- ❌ **NÃO pode deletar** diários aprovados
- ❌ **NÃO pode modificar** worklogs de diários aprovados
- **Razão**: Integridade de dados históricos

### 2. **Violação de Constraints**
- ❌ **NÃO pode criar** dois `DailyWorkLog` com mesma `activity` e `diary`
- ❌ **NÃO pode criar** dois `ConstructionDiary` com mesma `date` e `project`
- ❌ **NÃO pode criar** `Activity` sem `project`
- **Razão**: Constraints de integridade do banco

### 3. **Modificações na Estrutura Treebeard**
- ❌ **NÃO modifique diretamente** campos `path`, `depth`, `numchild` do treebeard
- ❌ **Use os métodos** `move()`, `add_child()`, `add_sibling()` do treebeard
- **Razão**: Treebeard gerencia esses campos automaticamente

### 4. **Workflow de Aprovação**
- ❌ **NÃO pode aprovar** diário sem passar por `REVISAR`
- ❌ **NÃO pode mover** diário para `REVISAR` se não for o criador
- ❌ **NÃO pode aprovar** sem permissão `can_approve_diary`
- **Razão**: Regras de negócio e auditoria

### 5. **Modificações Perigosas**
- ❌ **NÃO delete** `Project` que tem `diaries` aprovados (CASCADE deleta tudo)
- ❌ **NÃO modifique** `report_number` manualmente (é gerado automaticamente)
- ❌ **NÃO altere** `created_by` de diário aprovado
- **Razão**: Integridade referencial e auditoria

### 6. **Dependências Críticas**
- ❌ **NÃO remova** django-treebeard (EAP depende dele)
- ❌ **NÃO remova** Celery (PDFs são gerados assincronamente)
- ❌ **NÃO remova** WeasyPrint/xhtml2pdf (geração de PDF)

---

## 🔒 Regras de Negócio Críticas

### 1. **Geração de report_number**
```python
# report_number é SEQUENCIAL POR PROJETO (não global)
# Gerado automaticamente no save() do ConstructionDiary
# NÃO modifique manualmente!
```

### 2. **Workflow de Aprovação**
```
PREENCHENDO → REVISAR → APROVADO
   ↑            ↓
   └────────────┘ (rejeitar)

Regras:
- Apenas created_by pode mover PREENCHENDO → REVISAR
- Apenas usuários com can_approve_diary podem aprovar
- Diários APROVADOS são imutáveis (ReadOnly)
```

### 3. **Constraint de DailyWorkLog**
```python
# Uma atividade só pode ter UM worklog por diário
unique_together = [['activity', 'diary']]

# Se tentar criar duplicado, o sistema atualiza o existente
# (implementado no save() do DailyWorkLogForm)
```

### 4. **EAP Hierárquica**
```python
# Activity herda de MP_Node (treebeard)
# Use métodos do treebeard para manipular:
- activity.add_child()  # Adicionar filho
- activity.move()       # Mover na árvore
- activity.get_children()  # Obter filhos
- activity.get_descendants()  # Obter todos descendentes
```

### 5. **Progresso Ponderado**
```python
# Progresso é calculado usando weight das atividades
# Rollup automático: atividades filhas calculam progresso dos pais
# Implementado em: core/services.py -> ProgressService
```

---

## 📦 Dependências e Requisitos

### Python
- **Python**: >= 3.10
- **Django**: >= 5.0, < 6.0 (atual: 5.2.11)

### Dependências Principais
```txt
Django>=5.0,<6.0
djangorestframework>=3.15.0
django-treebeard>=4.7          # CRÍTICO: EAP depende disso
django-filter>=24.0
psycopg2-binary>=2.9.0
celery>=5.3.0                   # CRÍTICO: PDFs assíncronos
redis>=5.0.0                    # CRÍTICO: Celery precisa
WeasyPrint>=60.0                # PDF (pode usar xhtml2pdf como fallback)
Pillow>=10.0.0
```

### Banco de Dados
- **Desenvolvimento**: SQLite (padrão)
- **Produção**: PostgreSQL (recomendado)
- **Configuração**: Via variáveis de ambiente

### Cache/Queue
- **Redis**: Obrigatório para Celery
- **Celery**: Para processamento assíncrono de PDFs

---

## 🔗 Como Integrar

### Opção 1: Via API REST (Recomendado)

```python
# Exemplo: Criar um diário via API
import requests

# Autenticação
session = requests.Session()
session.post('http://localhost:8000/login/', {
    'username': 'user',
    'password': 'pass'
})

# Criar diário
response = session.post('http://localhost:8000/api/diaries/', {
    'project': 1,
    'date': '2024-01-15',
    'work_hours': 8.0,
    'status': 'PREENCHENDO'
})
```

### Opção 2: Compartilhar Models (Mesmo Projeto)

```python
# Se unificar em um único projeto Django:
from diario_obra.core.models import Project, ConstructionDiary

# Usar diretamente
project = Project.objects.get(code='PROJ-001')
diary = ConstructionDiary.objects.create(
    project=project,
    date='2024-01-15',
    status='PREENCHENDO'
)
```

### Opção 3: Banco de Dados Compartilhado

```python
# Se compartilhar o mesmo banco de dados:
# Configure DATABASES no settings.py para apontar para o mesmo DB
# Use os models diretamente
```

### Autenticação Compartilhada

```python
# O sistema usa User padrão do Django
# Pode compartilhar autenticação entre projetos:
from django.contrib.auth.models import User

# Verificar permissões
user.has_perm('core.can_approve_diary')
```

---

## ⚠️ Limitações e Considerações

### 1. **Performance**
- EAP com **milhares de atividades**: Use `get_descendants()` com cuidado
- **PDFs grandes**: Processamento assíncrono via Celery (pode demorar)
- **Upload de mídia**: Limite de tamanho configurável

### 2. **Concorrência**
- `report_number` usa `select_for_update()` para evitar race conditions
- `DailyWorkLog` usa `get_or_create()` para evitar duplicatas

### 3. **Windows vs Linux**
- **WeasyPrint**: Requer GTK+ no Windows (pode não funcionar)
- **Fallback**: Sistema usa xhtml2pdf automaticamente se WeasyPrint falhar

### 4. **Migrações**
- **NÃO delete migrações** existentes
- **Sempre crie novas migrações** para mudanças
- **Teste migrações** em ambiente de desenvolvimento primeiro

### 5. **Permissões**
- Sistema usa **grupos Django** para controle de acesso
- Permissões customizadas em `core/permissions.py`
- **can_approve_diary**: Permissão especial para aprovar diários

---

## 📝 Exemplos de Uso

### Criar Projeto e EAP
```python
from core.models import Project, Activity

# Criar projeto
project = Project.objects.create(
    code='PROJ-2024-001',
    name='Obra Exemplo',
    start_date='2024-01-01',
    end_date='2024-12-31'
)

# Criar atividade raiz
root = Activity.add_root(
    project=project,
    name='Obra',
    code='1',
    weight=100.0
)

# Adicionar filho
child = root.add_child(
    project=project,
    name='Fundação',
    code='1.1',
    weight=30.0
)
```

### Criar Diário e Worklog
```python
from core.models import ConstructionDiary, DailyWorkLog, Activity

# Criar diário
diary = ConstructionDiary.objects.create(
    project=project,
    date='2024-01-15',
    status='PREENCHENDO',
    created_by=user
)

# Criar worklog
worklog = DailyWorkLog.objects.create(
    diary=diary,
    activity=child,
    percentage_executed_today=10.0,
    accumulated_progress_snapshot=5.0,
    notes='Início da fundação'
)
```

### Mover para Aprovação
```python
from core.services import WorkflowService

# Mover para revisão (apenas criador)
WorkflowService.move_to_review(diary, user)

# Aprovar (apenas com permissão)
WorkflowService.approve(diary, approver_user)
```

---

## 🆘 Troubleshooting

### Problema: "UNIQUE constraint failed: activity_id, diary_id"
**Solução**: Use `get_or_create()` ou atualize o worklog existente

### Problema: "Cannot modify approved diary"
**Solução**: Diários aprovados são ReadOnly. Crie um novo diário se necessário.

### Problema: "WeasyPrint não funciona no Windows"
**Solução**: Sistema usa xhtml2pdf automaticamente como fallback.

### Problema: "Celery não processa PDFs"
**Solução**: Verifique se Redis está rodando e Celery worker está ativo.

---

## 📞 Contato e Suporte

Para dúvidas sobre integração:
1. Consulte este documento primeiro
2. Verifique os modelos em `core/models.py`
3. Veja exemplos em `core/tests.py`
4. Consulte a documentação do Django e DRF

---

## ✅ Checklist de Integração

- [ ] Entendeu a estrutura de dados (models)
- [ ] Identificou quais APIs usar
- [ ] Verificou regras de negócio críticas
- [ ] Testou autenticação/permissões
- [ ] Validou constraints e relacionamentos
- [ ] Configurou dependências (Redis, Celery se necessário)
- [ ] Testou criação de recursos básicos
- [ ] Validou workflow de aprovação
- [ ] Testou geração de PDF (se necessário)

---

**Última atualização**: 2024-01-XX
**Versão do Sistema**: 2.0.0
**Django**: 5.2.11
