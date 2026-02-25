# Integração ao Sistema Principal LPLAN

## ✅ STATUS: SISTEMA EM PRODUÇÃO E FUNCIONANDO

O **Sistema de Gestão de Aprovações** está **100% operacional** e em uso ativo na LPLAN Engenharia Integrada.

**URL de Produção:** https://gestao.lplan.com.br

---

## 📋 RESUMO DO SISTEMA

### O que é
Sistema web interno para gestão de pedidos de obra e aprovações. Permite que engenheiros criem pedidos (contratos, medições, ordens de serviço, mapas de cotação) que são analisados e aprovados/reprovados por gestores.

### Funcionalidades Principais
- ✅ Gestão completa de pedidos de obra
- ✅ Sistema de aprovação/reprovação com comentários
- ✅ Upload e gestão de anexos (até 50MB)
- ✅ Notificações automáticas por e-mail e internas
- ✅ Histórico completo de auditoria
- ✅ Relatórios e estatísticas
- ✅ Sistema de permissões granular por obra

### Tecnologias
- **Backend:** Django 5.0.1 (Python 3.11+)
- **Banco de Dados:** MySQL 8.0+ (cPanel)
- **Frontend:** HTML5, CSS3, JavaScript vanilla
- **Hospedagem:** cPanel com Passenger WSGI

---

## 🔗 PONTOS DE INTEGRAÇÃO

### 1. Banco de Dados
- **Banco:** `lplan_gestaoap`
- **Usuário:** `lplan_gestaoap2`
- **Host:** 127.0.0.1 (cPanel)
- **Driver:** pymysql (com monkey patch obrigatório)

### 2. Autenticação
- Sistema próprio do Django (User, Groups, Permissions)
- **Grupos:** Engenheiro, Gestor, Administrador, Responsável Empresa
- Pode ser integrado com SSO do sistema principal

### 3. URLs e Rotas
- Todas as rotas estão em `obras/urls.py`
- Prefixo atual: `/` (raiz)
- Pode ser movido para subdiretório: `/gestao/` ou `/aprovacoes/`

### 4. Templates
- Template base: `templates/base.html`
- 26 templates HTML organizados
- CSS separado por template (10 arquivos)

### 5. API e Endpoints
- Endpoints JSON disponíveis:
  - `/api/notificacoes/count/` - Contador de notificações
  - `/api/desempenho-equipe/` - Dados de desempenho
  - `/api/desempenho-solicitantes/` - Desempenho por solicitante

---

## 📁 ESTRUTURA DO PROJETO

```
Gestao_aprovacao/
├── gestao_aprovacao/      # Configurações Django
│   ├── settings.py        # MySQL, e-mail, segurança
│   └── urls.py            # URLs principais
├── obras/                 # App principal
│   ├── models.py          # 14 modelos de dados
│   ├── views.py           # Views (CRUD, aprovação)
│   ├── forms.py           # Formulários
│   ├── utils.py           # Utilitários e decorators
│   ├── email_utils.py     # Sistema de e-mail
│   └── management/commands/  # Comandos Django
├── templates/             # 26 templates HTML
├── static/css/            # 10 arquivos CSS
└── requirements.txt       # Dependências Python
```

---

## 🔧 CONFIGURAÇÃO ATUAL

### Variáveis de Ambiente (.env)
```env
# Django
SECRET_KEY=...
DEBUG=False
USE_LOCAL_DB=False  # MySQL em produção

# Database (cPanel)
DB_NAME=lplan_gestaoap
DB_USER=lplan_gestaoap2
DB_PASSWORD=...
DB_HOST=127.0.0.1
DB_PORT=3306

# Email
EMAIL_HOST=mail.lplan.com.br
EMAIL_PORT=465
EMAIL_USE_SSL=True
EMAIL_HOST_USER=sistema@lplan.com.br
EMAIL_HOST_PASSWORD=...
DEFAULT_FROM_EMAIL=sistema@lplan.com.br
SITE_URL=https://gestao.lplan.com.br
```

### Dependências (requirements.txt)
```
Django>=5.0.1,<6.0.0
mysqlclient>=2.2.0,<3.0.0
pymysql>=1.1.0,<2.0.0  # Obrigatório no cPanel
Pillow>=10.0.0,<11.0.0
whitenoise>=6.6.0,<7.0.0
python-dotenv>=1.0.0,<2.0.0
```

---

## 🚀 PASSOS PARA INTEGRAÇÃO

### Opção 1: Manter como Sistema Separado
- Sistema continua em `https://gestao.lplan.com.br`
- Integração via links no sistema principal
- Compartilhamento de autenticação (SSO)

### Opção 2: Integrar ao Sistema Principal
1. **Copiar app `obras/`** para o projeto principal
2. **Adicionar em INSTALLED_APPS:**
   ```python
   INSTALLED_APPS = [
       # ... apps existentes ...
       'obras',  # Sistema de aprovações
   ]
   ```
3. **Adicionar URLs:**
   ```python
   urlpatterns = [
       # ... URLs existentes ...
       path('gestao/', include('obras.urls')),  # Ou outro prefixo
   ]
   ```
4. **Ajustar configurações:**
   - Banco de dados (pode usar o mesmo MySQL)
   - Autenticação (integrar com sistema existente)
   - Templates base (adaptar ao layout principal)

### Opção 3: Microserviço/API
- Expor endpoints REST
- Integração via API
- Autenticação via tokens

---

## ⚠️ PONTOS DE ATENÇÃO

### 1. Banco de Dados
- ⚠️ Sistema usa MySQL no cPanel (diferente do SQLite em desenvolvimento)
- ⚠️ pymysql com monkey patch obrigatório no cPanel
- Configuração detecta ambiente via `USE_LOCAL_DB` no .env

### 2. Permissões
- Sistema baseado em grupos Django
- Permissões granulares por obra
- Validação em múltiplas camadas

### 3. E-mail
- SMTP próprio (mail.lplan.com.br)
- Logs completos em `EmailLog`
- Remetente: gestcontroll@lplan.com.br

### 4. Arquivos Estáticos
- CSS/JS puro (sem frameworks)
- Chart.js via CDN
- WhiteNoise para servir estáticos

### 5. Uploads
- Anexos em `media/anexos/`
- Perfis em `media/perfis/`
- Organizados por data (YYYY/MM/DD)

---

## 📊 MODELOS DE DADOS PRINCIPAIS

1. **Empresa** - Empresas cliente
2. **Obra** - Obras físicas
3. **WorkOrder** - Pedidos de obra (modelo principal)
4. **Approval** - Aprovações/reprovações
5. **Attachment** - Anexos
6. **StatusHistory** - Histórico de status
7. **WorkOrderPermission** - Permissões por obra
8. **UserEmpresa** - Vínculo usuário-empresa
9. **UserProfile** - Perfis de usuário
10. **Comment** - Comentários
11. **Lembrete** - Lembretes
12. **Notificacao** - Notificações internas
13. **TagErro** - Tags de erro
14. **EmailLog** - Logs de e-mail

---

## 📞 CONTATO E SUPORTE

**Sistema:** Sistema de Gestão de Aprovações  
**Versão:** 1.0.0  
**Status:** ✅ Produção  
**Última Atualização:** Janeiro 2025

Para mais detalhes, consulte:
- **[RESUMO_SISTEMA.md](RESUMO_SISTEMA.md)** - Resumo executivo completo
- **[README.md](README.md)** - Documentação técnica
- **[FUNCIONALIDADES.md](FUNCIONALIDADES.md)** - Checklist de funcionalidades

---

## ✅ CHECKLIST DE INTEGRAÇÃO

- [ ] Analisar estrutura do sistema principal
- [ ] Decidir estratégia de integração (separado/integrado/API)
- [ ] Verificar compatibilidade de dependências
- [ ] Configurar banco de dados compartilhado (se necessário)
- [ ] Integrar autenticação (SSO ou unificado)
- [ ] Adaptar templates ao layout principal (se integrado)
- [ ] Testar todas as funcionalidades após integração
- [ ] Migrar dados (se necessário)
- [ ] Configurar URLs e rotas
- [ ] Atualizar documentação

---

**O sistema está pronto para integração!** 🚀
