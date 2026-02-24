# 📋 Resumo do Diário de Obra - Guia Rápido

## 🎯 O que é?
Sistema Django para **gestão de diários de obra** com EAP hierárquica, workflow de aprovação e geração de PDFs.

## 🏗️ Tecnologias
- **Django 5.2.11** (Python 3.10+)
- **DRF 3.16.1** (API REST)
- **django-treebeard** (EAP hierárquica)
- **Celery + Redis** (PDFs assíncronos)
- **WeasyPrint/xhtml2pdf** (Geração de PDF)

## 📊 Modelos Principais

### 1. Project (Projeto)
- Código único, nome, datas, cliente
- Relaciona com: Activities, Diaries

### 2. Activity (Atividade EAP)
- Hierarquia infinita (treebeard)
- Peso para progresso ponderado
- Status: Não Iniciada, Em Andamento, Concluída, etc.

### 3. ConstructionDiary (Diário)
- **Workflow**: PREENCHENDO → REVISAR → APROVADO
- `report_number` sequencial por projeto
- Campos: clima, horas, paradas, acidentes, etc.

### 4. DailyWorkLog (Registro de Trabalho)
- Uma atividade por diário (constraint único)
- Progresso diário e acumulado
- Relaciona com: Labor, Equipment

## ✅ PODE fazer
- ✅ Consumir API REST completa
- ✅ Criar/ler/atualizar recursos
- ✅ Exportar PDF/Excel
- ✅ Integrar dados via API
- ✅ Compartilhar autenticação (User Django)

## ❌ NÃO PODE fazer
- ❌ Editar diários **APROVADOS** (ReadOnly)
- ❌ Criar worklog duplicado (mesma activity + diary)
- ❌ Aprovar sem passar por REVISAR
- ❌ Modificar campos treebeard diretamente (use métodos)
- ❌ Alterar `report_number` manualmente (gerado automaticamente)

## 🔒 Regras Críticas

1. **Diários Aprovados são Imutáveis**
   ```python
   if diary.status == 'APROVADO':
       # ReadOnly - não pode editar
   ```

2. **report_number é Sequencial por Projeto**
   ```python
   # Não global! Cada projeto tem sua sequência
   # Gerado automaticamente no save()
   ```

3. **Workflow Rigoroso**
   ```
   PREENCHENDO → REVISAR → APROVADO
   - Apenas criador pode mover para REVISAR
   - Apenas com permissão pode aprovar
   ```

4. **Constraint de Worklog**
   ```python
   # Uma atividade = um worklog por diário
   unique_together = [['activity', 'diary']]
   ```

## 🔌 APIs Disponíveis

**Base**: `/api/`

- `GET/POST /api/projects/` - Projetos
- `GET/POST /api/activities/` - Atividades EAP
- `GET/POST /api/diaries/` - Diários
- `GET/POST /api/work-logs/` - Registros de trabalho
- `GET/POST /api/labor/` - Mão de obra
- `GET/POST /api/equipment/` - Equipamentos

**Ações Especiais**:
- `POST /api/diaries/{id}/move_to_review/` - Enviar para revisão
- `GET /api/projects/{id}/progress/` - Progresso do projeto

## 📦 Dependências Críticas

```txt
Django>=5.0,<6.0
django-treebeard>=4.7    # CRÍTICO: EAP depende
celery>=5.3.0            # CRÍTICO: PDFs assíncronos
redis>=5.0.0             # CRÍTICO: Celery precisa
WeasyPrint>=60.0         # PDF (fallback: xhtml2pdf)
```

## 🔗 Como Integrar

### Opção 1: API REST (Recomendado)
```python
import requests
session = requests.Session()
session.post('http://localhost:8000/login/', {...})
response = session.get('http://localhost:8000/api/projects/')
```

### Opção 2: Models Compartilhados
```python
from diario_obra.core.models import Project, ConstructionDiary
project = Project.objects.get(code='PROJ-001')
```

### Opção 3: Banco Compartilhado
Configure `DATABASES` para apontar ao mesmo DB.

## ⚠️ Atenção

- **Windows**: WeasyPrint pode não funcionar (usa xhtml2pdf automaticamente)
- **Performance**: EAP com milhares de atividades pode ser lento
- **Permissões**: Use grupos Django (`can_approve_diary`)
- **Migrações**: Não delete migrações existentes

## 📖 Documentação Completa
Veja `GUIA_DIARIO_OBRA.md` para detalhes completos.

---

**Versão**: 2.0.0 | **Django**: 5.2.11 | **Data**: 2024
