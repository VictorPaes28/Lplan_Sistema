# Sistema de Gestão de Aprovações - LPLAN

## ✅ STATUS: EM PRODUÇÃO E FUNCIONANDO

**URL de Produção:** https://gestao.lplan.com.br  
**Ambiente:** cPanel (hospedagem compartilhada)  
**Banco de Dados:** MySQL 8.0+ (cPanel)  
**Status Operacional:** ✅ Sistema estável e em uso ativo

---

## 📋 O QUE É O SISTEMA

O **Sistema de Gestão de Aprovações** é uma plataforma web interna desenvolvida para a **LPLAN Engenharia Integrada** que gerencia o fluxo completo de **pedidos de obra** e suas **aprovações**.

### Objetivo Principal
Centralizar e padronizar o processo de solicitação e aprovação de pedidos de obra, garantindo rastreabilidade completa de todas as decisões e facilitando a comunicação entre engenheiros (solicitantes) e gestores (aprovadores).

### Funcionalidade Core
- Engenheiros criam pedidos de obra (contratos, medições, ordens de serviço, mapas de cotação)
- Gestores analisam e aprovam/reprovam os pedidos
- Sistema registra todo o histórico de aprovações e mudanças
- Notificações automáticas por e-mail e internas
- Upload e gestão de anexos/documentos

---

## 🏗️ ARQUITETURA TECNOLÓGICA

### Stack
- **Backend:** Django 5.0.1 (Python 3.11+)
- **Banco de Dados:** MySQL 8.0+ (produção) / SQLite (desenvolvimento)
- **Frontend:** HTML5, CSS3 puro, JavaScript vanilla
- **Hospedagem:** cPanel com Passenger WSGI
- **E-mail:** SMTP próprio (mail.lplan.com.br)

### Dependências Principais
```
Django>=5.0.1,<6.0.0
mysqlclient>=2.2.0,<3.0.0
pymysql>=1.1.0,<2.0.0  # Obrigatório no cPanel
Pillow>=10.0.0,<11.0.0
whitenoise>=6.6.0,<7.0.0
python-dotenv>=1.0.0,<2.0.0
```

---

## 📊 ESTRUTURA DE DADOS

O sistema possui **14 modelos de dados** principais:

1. **Empresa** - Empresas cliente
2. **Obra** - Obras físicas onde são feitos os pedidos
3. **WorkOrder** - Pedidos de obra (modelo principal)
4. **Approval** - Aprovações/reprovações
5. **Attachment** - Anexos de documentos (até 50MB)
6. **StatusHistory** - Histórico de mudanças de status
7. **WorkOrderPermission** - Permissões por obra
8. **UserEmpresa** - Vínculo usuário-empresa
9. **UserProfile** - Perfis de usuário
10. **Comment** - Comentários em pedidos
11. **Lembrete** - Lembretes de pedidos pendentes
12. **Notificacao** - Notificações internas
13. **TagErro** - Tags de erro por tipo de solicitação
14. **EmailLog** - Logs de e-mail

---

## 👥 SISTEMA DE PERMISSÕES

### Grupos de Usuários
1. **Engenheiro** (Solicitante)
   - Cria pedidos de obra
   - Vê apenas seus próprios pedidos
   - Pode editar pedidos em rascunho/pendente

2. **Gestor** (Aprovador)
   - Vê todos os pedidos das obras sob sua responsabilidade
   - Aprova/reprova pedidos
   - Gerencia anexos

3. **Administrador**
   - Acesso total ao sistema
   - Gerencia obras, empresas e usuários
   - Acesso a relatórios e logs

---

## 🔄 FLUXO DE TRABALHO

1. **Engenheiro cria pedido** → Status: Rascunho ou Pendente
2. **Se Pendente** → E-mail automático para gestores + notificação interna
3. **Gestor analisa** → Aprova (comentário opcional) ou Reprova (comentário obrigatório)
4. **E-mail automático** → Notifica engenheiro sobre a decisão
5. **Se reprovado** → Engenheiro pode editar e reenviar (reaprovação)

---

## ✨ FUNCIONALIDADES PRINCIPAIS

✅ **Gestão Completa de Pedidos**
- CRUD completo de pedidos de obra
- Código único por obra
- Filtros avançados (obra, status, tipo, credor, período)
- Busca por texto
- Exportação CSV

✅ **Sistema de Aprovação**
- Aprovação/reprovação com comentários
- Tags de erro por tipo de solicitação
- Histórico completo de decisões
- Reaprovação de pedidos reprovados

✅ **Gestão de Anexos**
- Upload de arquivos (PDF, DOC, XLS, imagens, ZIP, RAR)
- Limite de 50MB por arquivo
- Download e exclusão
- Histórico de uploads

✅ **Comunicação**
- Comentários em pedidos
- Notificações internas em tempo real
- E-mails automáticos (novo pedido, aprovação, reprovação)
- Lembretes de pedidos pendentes

✅ **Auditoria e Rastreabilidade**
- Histórico completo de mudanças de status
- Registro de quem alterou e quando
- Logs de e-mail
- Rastreamento completo de alterações

✅ **Relatórios e Estatísticas**
- Exportação CSV com filtros
- Relatório de desempenho da equipe
- Estatísticas por obra e engenheiro
- Gráficos (Chart.js)

---

## 🔗 URLS PRINCIPAIS

- `/` - Dashboard/Home
- `/pedidos/` - Lista de pedidos
- `/pedidos/criar/` - Criar novo pedido
- `/pedidos/<id>/` - Detalhes do pedido
- `/pedidos/<id>/aprovar/` - Aprovar pedido
- `/pedidos/<id>/reprovar/` - Reprovar pedido
- `/obras/` - Gestão de obras (admin)
- `/empresas/` - Gestão de empresas (admin)
- `/usuarios/` - Gestão de usuários (admin)
- `/notificacoes/` - Notificações
- `/desempenho-equipe/` - Relatórios (admin)
- `/admin/` - Django Admin

---

## 📧 SISTEMA DE E-MAIL

**Configuração:**
- Servidor: mail.lplan.com.br (porta 465 SSL)
- Remetente: gestcontroll@lplan.com.br

**Tipos de E-mail:**
1. Novo pedido criado (para gestores)
2. Pedido aprovado (para engenheiro)
3. Pedido reprovado (para engenheiro)
4. Lembretes de pedidos pendentes (1, 2, 3, 5, 7, 10, 15, 20, 30 dias)

Todos os envios são registrados em `EmailLog` para rastreamento.

---

## 🔐 SEGURANÇA

✅ Validação de permissões em todas as views  
✅ Proteção contra edição não autorizada  
✅ Validação de acesso por obra  
✅ Validação de arquivos (tipo e tamanho)  
✅ Proteção CSRF em todos os formulários  
✅ Sanitização de nomes de arquivos  
✅ Sessão expira ao fechar navegador  
✅ Timeout de 8 horas de inatividade  
✅ Cookies HTTPOnly  

---

## 📁 ESTRUTURA DO PROJETO

```
Gestao_aprovacao/
├── gestao_aprovacao/      # Configurações Django
│   ├── settings.py        # MySQL, e-mail, segurança
│   └── urls.py
├── obras/                 # App principal
│   ├── models.py          # 14 modelos
│   ├── views.py           # Views (CRUD, aprovação)
│   ├── forms.py           # Formulários
│   ├── utils.py           # Utilitários
│   ├── email_utils.py     # E-mail
│   └── management/commands/  # Comandos Django
├── templates/             # 26 templates HTML
├── static/css/            # 10 arquivos CSS
├── media/                 # Uploads (anexos/, perfis/)
└── requirements.txt       # Dependências
```

---

## 🚀 INTEGRAÇÃO COM SISTEMA PRINCIPAL LPLAN

### Status Atual
✅ Sistema está **100% funcional e em produção**  
✅ Banco de dados MySQL configurado e operacional  
✅ E-mails funcionando  
✅ Usuários ativos utilizando o sistema  

### Para Integração
O sistema está pronto para ser integrado ao sistema principal da LPLAN. Principais pontos:

1. **Banco de Dados:** MySQL no cPanel (lplan_gestaoap)
2. **Autenticação:** Sistema próprio do Django (pode ser integrado com SSO)
3. **URLs:** Todas as rotas estão em `obras/urls.py`
4. **Permissões:** Baseadas em grupos Django (pode ser adaptado)
5. **Templates:** Base HTML em `templates/base.html`

### Configuração Necessária
- Variáveis de ambiente (.env) já configuradas
- Banco de dados MySQL já em produção
- E-mail SMTP já configurado
- Arquivos estáticos servidos via WhiteNoise

---

## 📝 COMANDOS ÚTEIS

```bash
# Criar grupos de usuários
python manage.py create_groups

# Enviar lembretes de pedidos pendentes
python manage.py enviar_lembretes

# Aplicar migrações
python manage.py migrate

# Coletar arquivos estáticos (produção)
python manage.py collectstatic

# Criar superusuário
python manage.py createsuperuser
```

---

## 📊 ESTATÍSTICAS DO SISTEMA

- **14 modelos de dados**
- **26 templates HTML**
- **10 arquivos CSS**
- **4 comandos Django personalizados**
- **~40 rotas/URLs**
- **Sistema completo de notificações**
- **Histórico completo de auditoria**
- **Logs de e-mail completos**

---

## ✅ CONCLUSÃO

O **Sistema de Gestão de Aprovações** é uma plataforma completa, estável e **já está em produção funcionando**. O sistema gerencia todo o fluxo de pedidos de obra e aprovações da LPLAN Engenharia Integrada, com rastreabilidade completa, notificações automáticas e interface moderna.

**Pronto para integração ao sistema principal da LPLAN.**

---

**Última Atualização:** Janeiro 2025  
**Versão:** 1.0.0  
**Status:** ✅ Produção
