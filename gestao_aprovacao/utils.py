"""
Utilitários para verificação de permissões e perfis de usuário.
"""
from functools import wraps
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib import messages
from django.shortcuts import redirect
from accounts.groups import GRUPOS, usuario_tem_administracao_global_na_plataforma
from .models import Notificacao, AprovacaoEmailDestinatario, Empresa

# Coluna "Analisado" (lista de pedidos): fallback quando o banco não está acessível; senão AprovacaoEmailDestinatario + superuser.
_EMAILS_MARCAR_PEDIDO_ANALISADO_DEFAULT = frozenset({
    "luiz.henrique@lplan.com.br",
    "luizdomingos@lplan.com.br",
})


def _frozenset_emails_marcar_pedido_analisado():
    s = set(_EMAILS_MARCAR_PEDIDO_ANALISADO_DEFAULT)
    for e in getattr(settings, "EMAIL_DEPARTAMENTOS_APROVACAO", None) or []:
        e = (e or "").strip().lower()
        if e:
            s.add(e)
    return frozenset(s)


_EMAILS_MARCAR_PEDIDO_ANALISADO = _frozenset_emails_marcar_pedido_analisado()


def usuario_pode_marcar_pedido_analisado(user):
    """
    Quem pode usar o checkbox "Analisado" na lista de pedidos (GestControll).
    Alinhado aos e-mails cadastrados como destinatários de pedido aprovado (tela de destinatários).
    """
    if getattr(user, "is_superuser", False):
        return True
    email = (getattr(user, "email", None) or "").strip().lower()
    if not email:
        return False
    try:
        if AprovacaoEmailDestinatario.objects.filter(ativo=True, email__iexact=email).exists():
            return True
    except Exception:
        pass
    return email in _EMAILS_MARCAR_PEDIDO_ANALISADO


def get_user_profile(user):
    """
    Retorna o perfil do usuário baseado nos grupos.
    Retorna: 'admin', 'responsavel_empresa', 'aprovador', 'solicitante' ou None
    """
    if not user.is_authenticated:
        return None
    
    if user.is_superuser or usuario_tem_administracao_global_na_plataforma(user):
        return 'admin'
    elif user.groups.filter(name=GRUPOS.RESPONSAVEL_EMPRESA).exists():
        return 'responsavel_empresa'
    elif user.groups.filter(name=GRUPOS.APROVADOR).exists():
        return 'aprovador'
    elif user.groups.filter(name=GRUPOS.SOLICITANTE).exists():
        return 'solicitante'
    
    return None


def is_engenheiro(user):
    """Verifica se o usuário é solicitante."""
    return user.is_authenticated and (
        user.groups.filter(name=GRUPOS.SOLICITANTE).exists() or
        user.is_superuser
    )


def is_aprovador(user):
    """Verifica se o usuário é aprovador."""
    return user.is_authenticated and (
        user.groups.filter(name=GRUPOS.APROVADOR).exists() or
        user.is_superuser
    )


def is_responsavel_empresa(user):
    """Verifica se o usuário é responsável por empresa."""
    return user.is_authenticated and (
        user.groups.filter(name=GRUPOS.RESPONSAVEL_EMPRESA).exists() or
        user.is_superuser
    )


def is_gestor(user):
    """Alias para is_aprovador (mantido para compatibilidade)."""
    return is_aprovador(user)


def is_admin(user):
    """Verifica se o usuário é administrador de plataforma (Gestão + equivalentes globais legados)."""
    return user.is_authenticated and (
        usuario_tem_administracao_global_na_plataforma(user) or
        user.is_superuser
    )


def usuarios_escopo_pedido_para_notificar(workorder):
    """
    Destinatários de notificações operacionais ligadas ao pedido (GestControll).

    Inclui apenas quem está no contexto da obra/empresa: aprovadores com permissão
    ativa e o responsável da empresa (quando existir empresa). Superusuários ou
    administradores globais deixam de ser notificados em massa sobre todos os projetos —
    esse tipo de visão continua em listas/ações de administração ou na auditoria.
    """
    User = get_user_model()
    obra = getattr(workorder, "obra", None)
    if obra is None:
        return User.objects.none()

    empresa_id = obra.empresa_id
    if empresa_id:
        qs = User.objects.filter(
            permissoes_obra__obra__empresa_id=empresa_id,
            permissoes_obra__tipo_permissao="aprovador",
            permissoes_obra__ativo=True,
            is_active=True,
        ).distinct()
        responsavel_id = (
            Empresa.objects.filter(pk=empresa_id, ativo=True, responsavel_id__isnull=False)
            .values_list("responsavel_id", flat=True)
            .first()
        )
        if responsavel_id:
            qs = qs | User.objects.filter(pk=responsavel_id, is_active=True)
            return qs.distinct()
        return qs

    return User.objects.filter(
        permissoes_obra__obra_id=obra.pk,
        permissoes_obra__tipo_permissao="aprovador",
        permissoes_obra__ativo=True,
        is_active=True,
    ).distinct()


def gestor_required(view_func):
    """
    Decorator para views que requerem permissão de gestor ou admin.
    """
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            messages.error(request, 'Você precisa estar autenticado para acessar esta página.')
            return redirect('login')  # Tela única de login (core em /login/)
        
        if not (is_gestor(request.user) or is_admin(request.user)):
            messages.error(request, 'Você não tem permissão para acessar esta página.')
            return redirect('gestao:home')
        
        return view_func(request, *args, **kwargs)
    return _wrapped_view


def admin_required(view_func):
    """
    Decorator para views que requerem permissão de administrador.
    """
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            messages.error(request, 'Você precisa estar autenticado para acessar esta página.')
            return redirect('login')  # Tela única de login (core em /login/)
        
        if not is_admin(request.user):
            messages.error(request, 'Você não tem permissão para acessar esta página.')
            return redirect('gestao:home')
        
        return view_func(request, *args, **kwargs)
    return _wrapped_view


def criar_notificacao(usuario, tipo, titulo, mensagem, work_order=None):
    """
    Cria uma notificação para um usuário.
    
    Args:
        usuario: Usuário que receberá a notificação
        tipo: Tipo da notificação (pedido_criado, pedido_aprovado, etc.)
        titulo: Título da notificação
        mensagem: Mensagem da notificação
        work_order: Pedido relacionado (opcional)
    """
    Notificacao.objects.create(
        usuario=usuario,
        tipo=tipo,
        titulo=titulo,
        mensagem=mensagem,
        work_order=work_order
    )

