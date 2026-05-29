"""
Códigos estáveis de tipos de comunicação (e-mail / notificação interna).
"""

# GestControll
TIPO_GESTCONTROLL_COPIA_ADMIN = 'gestcontroll.pedido_aprovado.copia_administrativa'
TIPO_GESTCONTROLL_APROVADO_SOLICITANTE = 'gestcontroll.pedido_aprovado.solicitante'
TIPO_GESTCONTROLL_NOVO_PEDIDO = 'gestcontroll.novo_pedido.aprovador'
TIPO_GESTCONTROLL_REPROVADO_SOLICITANTE = 'gestcontroll.pedido_reprovado.solicitante'

# Cadastro
TIPO_CADASTRO_NOVA_SOLICITACAO = 'cadastro.nova_solicitacao_admin'
TIPO_CADASTRO_CREDENCIAIS = 'cadastro.credenciais_usuario'
TIPO_CADASTRO_SOLICITACAO_REPROVADA = 'cadastro.solicitacao_reprovada_solicitante'

# RDO
TIPO_RDO_CLIENTE = 'rdo.envio_cliente'
TIPO_RDO_LISTA_INTERNA = 'rdo.envio_lista_interna'

# Sistema
TIPO_SISTEMA_RESET_SENHA = 'sistema.reset_senha'
TIPO_SISTEMA_ALERTA_CRITICO = 'sistema.alerta_critico'

# TrackHub
TIPO_TRACKHUB_NOTIFICACAO_ETAPA_EMAIL = 'trackhub.notificacao_etapa.email'

# Tipos com router integrado (envio real passa pelo ComunicacaoPreferenciasService)
TIPOS_COM_ROUTER_ATIVO = frozenset({
    TIPO_GESTCONTROLL_COPIA_ADMIN,
    TIPO_GESTCONTROLL_APROVADO_SOLICITANTE,
    TIPO_GESTCONTROLL_NOVO_PEDIDO,
    TIPO_GESTCONTROLL_REPROVADO_SOLICITANTE,
    TIPO_CADASTRO_NOVA_SOLICITACAO,
    TIPO_CADASTRO_CREDENCIAIS,
    TIPO_CADASTRO_SOLICITACAO_REPROVADA,
    TIPO_RDO_CLIENTE,
    TIPO_RDO_LISTA_INTERNA,
    TIPO_TRACKHUB_NOTIFICACAO_ETAPA_EMAIL,
})

# Nunca desligar na UI nem no router (segurança / contrato)
TIPOS_NUNCA_DESLIGAR = frozenset({
    TIPO_CADASTRO_CREDENCIAIS,
    TIPO_CADASTRO_SOLICITACAO_REPROVADA,
    TIPO_RDO_CLIENTE,
    TIPO_RDO_LISTA_INTERNA,
    TIPO_SISTEMA_RESET_SENHA,
    TIPO_SISTEMA_ALERTA_CRITICO,
})

# Resumo diário: desligado até existir job de digest
RESUMO_DIARIO_DISPONIVEL = False

# Rótulos de modo na UI (perfil e admin)
MODO_LABELS = {
    'padrao': 'Usar regra da empresa',
    'email': 'E-mail imediato',
    'sem_email': 'Não enviar e-mail',
}

# Opções exibidas na UI (perfil do usuário) — linguagem simples
MODO_OPCOES_PERFIL = [
    {
        'value': 'padrao',
        'titulo': 'Usar regra da empresa',
        'descricao': (
            'Segue o padrão do seu perfil no sistema (ex.: Administrador, Aprovador) '
            'ou o padrão geral. Escolha esta opção se não tiver certeza.'
        ),
        'icone': 'fa-building',
    },
    {
        'value': 'email',
        'titulo': 'Quero receber por e-mail',
        'descricao': (
            'Este aviso sempre chega no seu e-mail, mesmo que o perfil da empresa '
            'esteja configurado para não enviar.'
        ),
        'icone': 'fa-envelope',
    },
    {
        'value': 'sem_email',
        'titulo': 'Não receber este e-mail',
        'descricao': (
            'O sistema deixa de enviar este aviso para você por e-mail. '
            'Isso não cria alerta no sino — só interrompe o e-mail.'
        ),
        'icone': 'fa-envelope-open-text',
    },
]

# Opções na tela admin de padrões por grupo
MODO_OPCOES_GRUPO = [
    {
        'value': 'padrao',
        'titulo': 'Sem regra para este grupo',
        'descricao': 'Quem está neste grupo segue o padrão geral do sistema para este aviso.',
        'icone': 'fa-minus-circle',
    },
    {
        'value': 'email',
        'titulo': 'Enviar e-mail para este grupo',
        'descricao': 'Por padrão, pessoas deste grupo recebem este aviso por e-mail.',
        'icone': 'fa-envelope',
    },
    {
        'value': 'sem_email',
        'titulo': 'Não enviar e-mail para este grupo',
        'descricao': (
            'Por padrão, pessoas deste grupo não recebem este e-mail. '
            'Cada pessoa ainda pode mudar isso no próprio perfil.'
        ),
        'icone': 'fa-ban',
    },
]

# Seed inicial (migration)
TIPOS_COMUNICACAO_SEED = [
    {
        'codigo': TIPO_GESTCONTROLL_COPIA_ADMIN,
        'nome': 'Cópia administrativa — pedido aprovado',
        'modulo': 'gestcontroll',
        'descricao': 'Cópia informativa enviada a departamentos e destinatários fixos quando um pedido é aprovado.',
        'categoria': 'informativo',
        'criticidade': 'informativo',
        'email_padrao': True,
        'interno_padrao': False,
        'resumo_padrao': False,
        'permite_usuario_desativar_email': True,
        'permite_admin_desativar_email': True,
        'permite_usuario_alterar_interno': False,
        'permite_resumo': True,
        'obrigatorio': False,
        'ordem': 10,
    },
    {
        'codigo': TIPO_GESTCONTROLL_APROVADO_SOLICITANTE,
        'nome': 'Pedido aprovado — solicitante',
        'modulo': 'gestcontroll',
        'descricao': 'E-mail ao solicitante quando o pedido é aprovado (com anexos).',
        'categoria': 'operacional_acompanhamento',
        'criticidade': 'operacional',
        'email_padrao': True,
        'interno_padrao': True,
        'resumo_padrao': False,
        'permite_usuario_desativar_email': True,
        'permite_admin_desativar_email': True,
        'permite_usuario_alterar_interno': False,
        'permite_resumo': False,
        'obrigatorio': False,
        'ordem': 20,
    },
    {
        'codigo': TIPO_GESTCONTROLL_NOVO_PEDIDO,
        'nome': 'Novo pedido — aprovador',
        'modulo': 'gestcontroll',
        'descricao': 'E-mail aos aprovadores quando um pedido aguarda aprovação.',
        'categoria': 'operacional_acao',
        'criticidade': 'operacional',
        'email_padrao': True,
        'interno_padrao': True,
        'resumo_padrao': False,
        'permite_usuario_desativar_email': True,
        'permite_admin_desativar_email': True,
        'permite_usuario_alterar_interno': False,
        'permite_resumo': False,
        'obrigatorio': False,
        'ordem': 30,
    },
    {
        'codigo': TIPO_GESTCONTROLL_REPROVADO_SOLICITANTE,
        'nome': 'Pedido reprovado — solicitante',
        'modulo': 'gestcontroll',
        'descricao': 'E-mail ao solicitante quando o pedido é reprovado.',
        'categoria': 'operacional_acao',
        'criticidade': 'operacional',
        'email_padrao': True,
        'interno_padrao': True,
        'resumo_padrao': False,
        'permite_usuario_desativar_email': True,
        'permite_admin_desativar_email': True,
        'permite_usuario_alterar_interno': False,
        'permite_resumo': False,
        'obrigatorio': False,
        'ordem': 40,
    },
    {
        'codigo': TIPO_CADASTRO_NOVA_SOLICITACAO,
        'nome': 'Nova solicitação de cadastro',
        'modulo': 'cadastro',
        'descricao': 'Alerta a superusuários sobre nova solicitação de cadastro.',
        'categoria': 'operacional_acompanhamento',
        'criticidade': 'operacional',
        'email_padrao': True,
        'interno_padrao': True,
        'resumo_padrao': False,
        'permite_usuario_desativar_email': True,
        'permite_admin_desativar_email': True,
        'permite_usuario_alterar_interno': False,
        'permite_resumo': True,
        'obrigatorio': False,
        'ordem': 50,
    },
    {
        'codigo': TIPO_CADASTRO_CREDENCIAIS,
        'nome': 'Credenciais de acesso',
        'modulo': 'cadastro',
        'descricao': 'E-mail com login e senha para novos usuários.',
        'categoria': 'critico',
        'criticidade': 'critico',
        'email_padrao': True,
        'interno_padrao': False,
        'resumo_padrao': False,
        'permite_usuario_desativar_email': False,
        'permite_admin_desativar_email': False,
        'permite_usuario_alterar_interno': False,
        'permite_resumo': False,
        'obrigatorio': True,
        'ordem': 60,
    },
    {
        'codigo': TIPO_CADASTRO_SOLICITACAO_REPROVADA,
        'nome': 'Solicitação de cadastro reprovada',
        'modulo': 'cadastro',
        'descricao': 'E-mail ao solicitante quando o cadastro é reprovado.',
        'categoria': 'critico',
        'criticidade': 'critico',
        'email_padrao': True,
        'interno_padrao': False,
        'resumo_padrao': False,
        'permite_usuario_desativar_email': False,
        'permite_admin_desativar_email': False,
        'permite_usuario_alterar_interno': False,
        'permite_resumo': False,
        'obrigatorio': True,
        'ordem': 65,
    },
    {
        'codigo': TIPO_RDO_CLIENTE,
        'nome': 'RDO — envio ao cliente',
        'modulo': 'rdo',
        'descricao': 'Diário de obra aprovado enviado ao dono/cliente da obra.',
        'categoria': 'critico',
        'criticidade': 'critico',
        'email_padrao': True,
        'interno_padrao': False,
        'resumo_padrao': False,
        'permite_usuario_desativar_email': False,
        'permite_admin_desativar_email': False,
        'permite_usuario_alterar_interno': False,
        'permite_resumo': False,
        'obrigatorio': True,
        'ordem': 70,
    },
    {
        'codigo': TIPO_RDO_LISTA_INTERNA,
        'nome': 'RDO — lista interna da obra',
        'modulo': 'rdo',
        'descricao': 'PDF/detailed diário para e-mails cadastrados na obra.',
        'categoria': 'operacional_acompanhamento',
        'criticidade': 'operacional',
        'email_padrao': True,
        'interno_padrao': False,
        'resumo_padrao': False,
        'permite_usuario_desativar_email': False,
        'permite_admin_desativar_email': False,
        'permite_usuario_alterar_interno': False,
        'permite_resumo': True,
        'obrigatorio': False,
        'ordem': 80,
    },
    {
        'codigo': TIPO_SISTEMA_RESET_SENHA,
        'nome': 'Redefinição de senha',
        'modulo': 'sistema',
        'descricao': 'Link para redefinir senha de acesso.',
        'categoria': 'critico',
        'criticidade': 'critico',
        'email_padrao': True,
        'interno_padrao': False,
        'resumo_padrao': False,
        'permite_usuario_desativar_email': False,
        'permite_admin_desativar_email': False,
        'permite_usuario_alterar_interno': False,
        'permite_resumo': False,
        'obrigatorio': True,
        'ordem': 90,
    },
    {
        'codigo': TIPO_SISTEMA_ALERTA_CRITICO,
        'nome': 'Alerta crítico do sistema',
        'modulo': 'sistema',
        'descricao': 'Falhas graves, integrações e eventos de segurança.',
        'categoria': 'critico',
        'criticidade': 'critico',
        'email_padrao': True,
        'interno_padrao': True,
        'resumo_padrao': False,
        'permite_usuario_desativar_email': False,
        'permite_admin_desativar_email': False,
        'permite_usuario_alterar_interno': False,
        'permite_resumo': False,
        'obrigatorio': True,
        'ordem': 100,
    },
    {
        'codigo': TIPO_TRACKHUB_NOTIFICACAO_ETAPA_EMAIL,
        'nome': 'TrackHub — notificação de etapa por e-mail',
        'modulo': 'trackhub',
        'descricao': 'E-mail manual enviado a partir de uma etapa da pendência no TrackHub.',
        'categoria': 'operacional_acao',
        'criticidade': 'operacional',
        'email_padrao': True,
        'interno_padrao': False,
        'resumo_padrao': False,
        'permite_usuario_desativar_email': True,
        'permite_admin_desativar_email': True,
        'permite_usuario_alterar_interno': False,
        'permite_resumo': False,
        'obrigatorio': False,
        'ordem': 110,
    },
]

# Seed de padrões iniciais por grupo (migration 0045)
PADROES_GRUPO_SEED = [
    {
        'grupo': 'Administrador',
        'tipo_codigo': TIPO_GESTCONTROLL_COPIA_ADMIN,
        'email_ativo': False,
    },
]

MODULO_LABELS = {
    'gestcontroll': 'GestControll',
    'cadastro': 'Cadastro de usuários',
    'rdo': 'Diário de Obra (RDO)',
    'sistema': 'Sistema',
    'trackhub': 'TrackHub',
}

# Nomes e explicações para humanos (telas de perfil e admin)
TIPO_UI_AJUDA = {
    TIPO_GESTCONTROLL_COPIA_ADMIN: {
        'titulo': 'Pedido aprovado — aviso para quem acompanha',
        'quando': (
            'Quando um pedido é aprovado no GestControll e seu e-mail está na lista de '
            'cópia (departamento ou lista fixa). Não é o e-mail de quem criou o pedido.'
        ),
    },
    TIPO_GESTCONTROLL_APROVADO_SOLICITANTE: {
        'titulo': 'Pedido aprovado — para quem criou o pedido',
        'quando': 'O solicitante recebe confirmação com anexos.',
    },
    TIPO_GESTCONTROLL_NOVO_PEDIDO: {
        'titulo': 'Novo pedido aguardando aprovação',
        'quando': 'Aviso para aprovadores quando entra um pedido na fila.',
    },
    TIPO_GESTCONTROLL_REPROVADO_SOLICITANTE: {
        'titulo': 'Pedido reprovado — para quem criou o pedido',
        'quando': 'O solicitante é avisado da reprovação.',
    },
    TIPO_CADASTRO_NOVA_SOLICITACAO: {
        'titulo': 'Nova solicitação de cadastro no sistema',
        'quando': 'Administradores são avisados de novo pedido de acesso.',
    },
    TIPO_CADASTRO_CREDENCIAIS: {
        'titulo': 'Login e senha de novo usuário',
        'quando': 'Envio de credenciais após criar acesso.',
    },
    TIPO_CADASTRO_SOLICITACAO_REPROVADA: {
        'titulo': 'Solicitação de cadastro reprovada',
        'quando': 'Solicitante é avisado quando o pedido de acesso é rejeitado.',
    },
    TIPO_RDO_CLIENTE: {
        'titulo': 'Diário de obra enviado ao cliente',
        'quando': 'RDO aprovado enviado ao dono/cliente da obra.',
    },
    TIPO_RDO_LISTA_INTERNA: {
        'titulo': 'Diário de obra — lista interna da obra',
        'quando': 'PDF do diário para e-mails cadastrados na obra.',
    },
    TIPO_SISTEMA_RESET_SENHA: {
        'titulo': 'Link para redefinir senha',
        'quando': 'Usuário pediu recuperação de senha.',
    },
    TIPO_SISTEMA_ALERTA_CRITICO: {
        'titulo': 'Alerta grave do sistema',
        'quando': 'Falhas críticas, integração ou segurança.',
    },
    TIPO_TRACKHUB_NOTIFICACAO_ETAPA_EMAIL: {
        'titulo': 'TrackHub — aviso manual de etapa',
        'quando': 'E-mail enviado manualmente ao notificar uma etapa da pendência.',
    },
}


def texto_ui_tipo_comunicacao(tipo) -> dict:
    """Retorna título e texto 'quando' amigáveis para um TipoComunicacao."""
    info = TIPO_UI_AJUDA.get(tipo.codigo, {})
    return {
        'titulo': info.get('titulo') or tipo.nome,
        'quando': info.get('quando') or tipo.descricao or '',
    }
