# Sistema de Gestão de Aprovações - LPLAN

## ✅ STATUS: EM PRODUÇÃO E FUNCIONANDO

**URL de Produção:** https://gestao.lplan.com.br  
**Sistema web interno para gestão de pedidos de obra e aprovações.**

> 📖 **Para um resumo completo do sistema, consulte [RESUMO_SISTEMA.md](RESUMO_SISTEMA.md)**

## Stack Tecnológica

- **Backend**: Django 5.0.1 (Python 3.11+)
- **Banco de Dados**: MySQL 8.0+ (produção) / SQLite (desenvolvimento)
- **Frontend**: HTML5, CSS3, JavaScript puro

## Pré-requisitos

- Python 3.11+
- MySQL 8.0+
- pip (gerenciador de pacotes Python)

## Instalação

### 1. Clone o repositório (ou navegue até o diretório do projeto)

```bash
cd Gestao_aprovacao
```

### 2. Crie e ative um ambiente virtual (recomendado)

**Windows:**
```bash
python -m venv venv
venv\Scripts\activate
```

**Linux/Mac:**
```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Instale as dependências

```bash
pip install -r requirements.txt
```

### 4. Configure o banco de dados MySQL

Crie um banco de dados MySQL:

```sql
CREATE DATABASE gestao_aprovacao CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

### 5. Configure as variáveis de ambiente

Crie um arquivo `.env` na raiz do projeto com o seguinte conteúdo:

```env
# Django
SECRET_KEY=sua_chave_secreta_aqui
DEBUG=True

# Database
DB_NAME=gestao_aprovacao
DB_USER=root
DB_PASSWORD=sua_senha_mysql
DB_HOST=localhost
DB_PORT=3306

# Email (opcional, para notificações)
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=seu_email@gmail.com
EMAIL_HOST_PASSWORD=sua_senha_app
DEFAULT_FROM_EMAIL=seu_email@gmail.com
SITE_URL=http://localhost:8000
```

**Importante:** Gere uma nova `SECRET_KEY` para produção. Você pode gerar uma usando:

```python
from django.core.management.utils import get_random_secret_key
print(get_random_secret_key())
```

### 6. Execute as migrações

```bash
python manage.py migrate
```

### 7. Crie os grupos de usuários

```bash
python manage.py create_groups
```

Este comando criará os grupos: **Engenheiro**, **Gestor** e **Administrador**.

### 8. Crie um superusuário

```bash
python manage.py createsuperuser
```

Este usuário terá acesso ao Django Admin e pode ser atribuído ao grupo **Administrador**.

### 9. Execute o servidor de desenvolvimento

```bash
python manage.py runserver
```

Acesse: http://127.0.0.1:8000/

## Estrutura do Projeto

```
Gestao_aprovacao/
├── gestao_aprovacao/      # Configurações do projeto Django
│   ├── settings.py        # Configurações (incluindo MySQL)
│   ├── urls.py            # URLs principais
│   └── ...
├── obras/                 # App principal
│   ├── models.py         # Modelos (Obra, WorkOrder, Approval, Attachment, StatusHistory)
│   ├── views.py          # Views (CRUD completo)
│   ├── forms.py          # Formulários
│   ├── urls.py           # URLs do app
│   ├── admin.py          # Configuração do Django Admin
│   ├── utils.py          # Funções utilitárias
│   ├── email_utils.py    # Utilitários de e-mail
│   └── ...
├── templates/            # Templates HTML
│   ├── base.html
│   └── obras/
│       ├── home.html
│       ├── login.html
│       ├── list_workorders.html
│       ├── list_obras.html
│       ├── workorder_form.html
│       ├── obra_form.html
│       ├── detail_workorder.html
│       ├── detail_obra.html
│       └── ...
├── static/              # Arquivos estáticos
│   └── css/            # Arquivos CSS organizados
│       ├── base.css
│       ├── home.css
│       ├── login.css
│       ├── list_workorders.css
│       ├── workorder_form.css
│       ├── detail_workorder.css
│       └── ...
├── media/               # Uploads de arquivos (anexos)
├── manage.py            # Script de gerenciamento Django
└── requirements.txt     # Dependências Python
```

## Funcionalidades Implementadas

### ✅ Autenticação e Autorização
- Sistema de login/logout
- Grupos de usuários: Engenheiro, Gestor, Administrador
- Controle de acesso baseado em permissões
- Proteção de views com decorators

### ✅ Gestão de Obras
- CRUD completo de Obras (apenas para administradores)
- Vinculação de engenheiros e gestores às obras
- Filtros e busca
- Estatísticas de pedidos por obra

### ✅ Gestão de Pedidos de Obra
- CRUD completo de Pedidos
- Código único por obra
- Campos: Obra, Nome do Credor, Tipo de Solicitação, Observações
- Campos opcionais: Valor Estimado, Prazo Estimado, Local
- Status: Rascunho, Pendente, Aprovado, Reprovado, Cancelado
- Data de envio automática

### ✅ Sistema de Aprovação
- Aprovação/reprovação de pedidos
- Comentários obrigatórios em reprovações
- Histórico completo de aprovações
- Notificações por e-mail

### ✅ Anexos
- Upload de arquivos (PDF, DOC, XLS, imagens, ZIP, RAR)
- Limite de 50MB por arquivo
- Download e exclusão de anexos
- Histórico de uploads

### ✅ Histórico e Auditoria
- Histórico completo de mudanças de status
- Registro de quem alterou e quando
- Observações em cada mudança

### ✅ Filtros e Busca
- Filtros por: Obra, Status, Tipo, Credor, Engenheiro, Período
- Busca por código, credor ou observações
- Paginação de resultados

### ✅ Exportação
- Exportação CSV dos pedidos filtrados
- Formato compatível com Excel
- Inclui todos os campos relevantes

### ✅ Notificações por E-mail
- E-mail quando novo pedido é criado (status pendente)
- E-mail de aprovação para o solicitante
- E-mail de reprovação com motivo
- Configurável via variáveis de ambiente

### ✅ Interface
- Design moderno e responsivo
- CSS separado e organizado por template
- Navegação intuitiva
- Mensagens de feedback ao usuário

## Perfis de Usuário

### Engenheiro
- Pode criar pedidos de obra nas obras às quais está vinculado
- Vê apenas seus próprios pedidos
- Pode editar pedidos em rascunho ou pendente
- Pode fazer upload de anexos

### Gestor
- Vê todos os pedidos das obras sob sua responsabilidade
- Pode aprovar/reprovar pedidos pendentes
- Pode criar pedidos em qualquer obra ativa
- Pode gerenciar anexos

### Administrador
- Acesso total ao sistema
- Pode gerenciar obras (CRUD completo)
- Vê todos os pedidos
- Acesso ao Django Admin

## URLs Principais

- `/` - Home
- `/login/` - Login
- `/logout/` - Logout
- `/pedidos/` - Lista de pedidos
- `/pedidos/criar/` - Criar novo pedido
- `/pedidos/<id>/` - Detalhes do pedido
- `/pedidos/<id>/editar/` - Editar pedido
- `/pedidos/<id>/aprovar/` - Aprovar pedido
- `/pedidos/<id>/reprovar/` - Reprovar pedido
- `/pedidos/<id>/anexos/upload/` - Upload de anexo
- `/pedidos/exportar/` - Exportar CSV
- `/obras/` - Lista de obras (apenas admin)
- `/obras/criar/` - Criar obra (apenas admin)
- `/obras/<id>/` - Detalhes da obra (apenas admin)
- `/obras/<id>/editar/` - Editar obra (apenas admin)
- `/admin/` - Django Admin

## Comandos Úteis

```bash
# Criar migrações
python manage.py makemigrations

# Aplicar migrações
python manage.py migrate

# Criar grupos de usuários
python manage.py create_groups

# Criar superusuário
python manage.py createsuperuser

# Coletar arquivos estáticos (produção)
python manage.py collectstatic

# Verificar configurações
python manage.py check
```

## Configuração de E-mail

Para habilitar notificações por e-mail, configure no arquivo `.env`:

```env
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=seu_email@gmail.com
EMAIL_HOST_PASSWORD=sua_senha_app  # Use senha de app do Gmail
DEFAULT_FROM_EMAIL=seu_email@gmail.com
SITE_URL=http://localhost:8000  # URL do seu sistema
```

**Nota:** Para Gmail, você precisará gerar uma "Senha de app" nas configurações de segurança da sua conta Google.

## 📖 Documentação Adicional

- **[RESUMO_SISTEMA.md](RESUMO_SISTEMA.md)** - Resumo executivo completo do sistema
- **[FUNCIONALIDADES.md](FUNCIONALIDADES.md)** - Checklist detalhado de funcionalidades

## 🚀 Status do Sistema

✅ **Sistema em produção e funcionando**  
✅ Banco de dados MySQL operacional  
✅ E-mails automáticos funcionando  
✅ Usuários ativos utilizando o sistema  

**Pronto para integração ao sistema principal da LPLAN.**

## Licença

Este projeto é de uso interno da LPLAN Engenharia Integrada.
