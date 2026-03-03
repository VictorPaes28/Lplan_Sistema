# Diário de Obra V2.0 - LPLAN

Sistema completo de gestão de obras com EAP hierárquica, workflow de aprovação e geração de PDF otimizada.

## 🚀 Tecnologias

- **Backend**: Django 4.2+ / Python 3.10+
- **Frontend**: Django Templates + Tailwind CSS + Alpine.js + HTMX
- **Banco de Dados**: PostgreSQL (recomendado)
- **Cache/Queue**: Redis + Celery
- **PDF**: WeasyPrint (Linux/macOS) ou xhtml2pdf (Windows)
- **EAP**: django-treebeard (Materialized Path)

## 📋 Pré-requisitos

- Python 3.10 ou superior
- PostgreSQL 12+ (ou SQLite para desenvolvimento)
- Redis (para Celery)
- Node.js (opcional, para compilar assets)

## 🔧 Instalação

### 1. Clone o repositório

```bash
git clone <repository-url>
cd Diario_obra
```

### 2. Crie um ambiente virtual

```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
# ou
venv\Scripts\activate  # Windows
```

### 3. Instale as dependências

```bash
pip install -r requirements.txt
```

### 4. Configure o banco de dados

Crie um arquivo `.env` na raiz do projeto:

```env
SECRET_KEY=sua-chave-secreta-aqui
DEBUG=True
DB_NAME=diario_obra
DB_USER=postgres
DB_PASSWORD=sua-senha
DB_HOST=localhost
DB_PORT=5432
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0
```

### 5. Execute as migrações

```bash
python manage.py makemigrations
python manage.py migrate
```

### 6. Crie um superusuário

**Opção 1: Comando padrão do Django**
```bash
python manage.py createsuperuser
```

**Opção 2: Comando customizado (mais flexível)**
```bash
python manage.py setup_superuser
```

**Opção 3: Modo não-interativo (para scripts)**
```bash
python manage.py setup_superuser --noinput --username admin --email admin@lplan.com --password senha123
```

### 7. Inicie o servidor de desenvolvimento

```bash
python manage.py runserver
```

Acesse no navegador: **http://127.0.0.1:8000** (use `http`, não `https`; o servidor de desenvolvimento é só HTTP).

### 8. Inicie o Celery (em outro terminal)

```bash
celery -A diario_obra worker -l info
```

### Geração de PDF no Windows

O sistema usa **xhtml2pdf** no Windows (WeasyPrint exige Cairo/GTK). Se aparecer *"Geração de PDF indisponível"*:

1. **Reinstale e reinicie:** `pip install xhtml2pdf` e reinicie o servidor.
2. **Se ainda falhar (erro de Cairo/libcairo):** uma dependência do xhtml2pdf pode exigir as bibliotecas gráficas. Instale o **GTK3 Runtime para Windows** (inclui Cairo) e reinicie:
   - [GTK for Windows Runtime - Releases](https://github.com/tschoonj/GTK-for-Windows-Runtime-Environment-Installer/releases) — baixe o instalador, execute e reinicie o PC se necessário.

## 📁 Estrutura do Projeto

```
Diario_obra/
├── core/                    # App principal
│   ├── models.py           # Modelos (EAP, Diários, etc.)
│   ├── views.py            # ViewSets DRF
│   ├── serializers.py      # Serializers DRF
│   ├── services.py         # Lógica de negócio
│   ├── forms.py            # Django Forms
│   ├── frontend_views.py   # Views para templates
│   ├── permissions.py      # Permissões customizadas
│   ├── tasks.py            # Tarefas Celery
│   ├── utils/
│   │   └── pdf_generator.py  # Geração de PDF
│   └── templates/
│       └── core/           # Templates HTML
├── diario_obra/            # Configurações do projeto
│   ├── settings.py
│   ├── urls.py
│   └── celery.py
└── requirements.txt
```

## 🎯 Funcionalidades Principais

### 1. Estrutura Analítica de Projetos (EAP)
- Hierarquia infinita usando django-treebeard
- Rollup automático de progresso ponderado
- Visualização em árvore com carregamento preguiçoso
- **CRUD completo de atividades** (criar, editar, deletar, mover)

### 2. Workflow de Aprovação
- Estados: Preenchendo → Revisar → Aprovado
- Controle de permissões rigoroso
- Diários aprovados são imutáveis
- **Sistema de notificações** para relatórios pendentes

### 3. Geração de PDF
- Otimização automática de imagens
- Layout profissional A4 (formato RQ-10)
- Processamento assíncrono via Celery
- Exportação para Excel (XLSX)

### 4. Frontend Moderno
- Design responsivo mobile-first
- Filtros HTMX sem reload
- Interface Alpine.js para interatividade
- **CRUD completo de projetos, mão de obra e equipamentos**

### 5. Gerenciamento de Recursos
- **Mão de Obra**: CRUD completo com categorização (Indireto/Direto/Terceiros)
- **Equipamentos**: CRUD completo com controle de custos
- Histogramas e estatísticas de uso

### 6. Sistema de Mídia
- **Fotos**: Upload com legenda obrigatória, otimização automática
- **Vídeos**: Upload de vídeos com thumbnails (modelo implementado)
- **Anexos**: Upload de documentos diversos (PDF, DOC, XLS, etc.)

### 7. Notificações
- Notificações automáticas para relatórios pendentes
- Interface de notificações com filtros
- Marcação de lidas/não lidas

## 🔐 Permissões

O sistema usa grupos Django para controle de acesso:

- **Gerentes**: Podem aprovar diários
- **Engenheiros**: Podem criar e editar seus próprios diários
- **Staff**: Acesso total

Para criar um grupo de Gerentes:

```bash
python manage.py shell
```

```python
from django.contrib.auth.models import Group
from accounts.groups import GRUPOS
Group.objects.get_or_create(name=GRUPOS.GERENTES)  # "Diário de Obra"
```

## 📊 API REST

A API está disponível em `/api/`:

- `/api/projects/` - Projetos
- `/api/activities/` - Atividades (EAP)
- `/api/diaries/` - Diários de obra
- `/api/work-logs/` - Registros de trabalho
- `/api/labor/` - Mão de obra
- `/api/equipment/` - Equipamentos

Documentação completa disponível em `/api/` quando usando DRF.

## 🎨 Interface do Usuário

### Páginas Principais
- **Dashboard**: Visão geral com KPIs, calendário e relatórios recentes
- **Relatórios**: Listagem com filtros avançados (data, status, busca)
- **EAP**: Visualização hierárquica de atividades com progresso
- **Filtros**: Páginas dedicadas para fotos, vídeos, atividades, ocorrências, comentários, anexos
- **Gerenciamento**: CRUD de projetos, mão de obra e equipamentos
- **Notificações**: Central de notificações do sistema
- **Perfil**: Edição de dados pessoais e alteração de senha
- **Análise de Dados**: Estatísticas e gráficos do projeto

### Funcionalidades de Relatórios
- Formulário completo com seções colapsáveis (accordion)
- Condições climáticas (manhã, tarde, noite) com índice pluviométrico
- Mão de obra categorizada (Indireto/Direto/Terceiros)
- Upload de fotos com legenda obrigatória
- Registro de atividades com localização
- Ocorrências (acidentes, paralisações, riscos iminentes)
- Eventos (inspeções, DDS)
- Assinaturas manuais (canvas)
- Histórico de edições e visualizações

## 🧪 Testes

```bash
python manage.py test core
```

## 📝 Notas de Desenvolvimento

### EAP Hierárquica
O sistema usa `django-treebeard` com implementação Materialized Path para suportar milhares de atividades com performance otimizada.

### Otimização de PDF
Imagens são automaticamente redimensionadas para max-width 800px, convertidas para JPEG (qualidade 80%) e têm dados EXIF removidos antes da geração do PDF.

### Carregamento Preguiçoso
A visualização de árvore EAP carrega apenas o primeiro nível inicialmente. Filhos são carregados sob demanda via HTMX.

## 🐛 Troubleshooting

### Erro ao gerar PDF
- Verifique se o WeasyPrint está instalado corretamente
- Certifique-se de que as imagens existem no caminho especificado
- Verifique os logs do Celery para erros de processamento

### Erro de permissão ao aprovar
- Verifique se o usuário pertence ao grupo "Gerentes" ou é staff
- Verifique se o diário está no status "REVISAR"

### Performance lenta na EAP
- Certifique-se de que os índices do banco estão criados
- Use `select_related` e `prefetch_related` nas queries
- Considere usar cache Redis para queries frequentes

## 📄 Licença

Proprietário - LPLAN

## 👥 Suporte

Para suporte, entre em contato com a equipe de desenvolvimento.

