"""
Utilitários para verificação de permissões e perfis de usuário.
"""
from functools import wraps
from django.shortcuts import redirect
from django.contrib import messages
from .models import Notificacao


def get_user_profile(user):
    """
    Retorna o perfil do usuário baseado nos grupos.
    Retorna: 'admin', 'responsavel_empresa', 'aprovador', 'solicitante' ou None
    """
    if not user.is_authenticated:
        return None
    
    if user.is_superuser or user.groups.filter(name='Administrador').exists():
        return 'admin'
    elif user.groups.filter(name='Responsavel Empresa').exists():
        return 'responsavel_empresa'
    elif user.groups.filter(name='Aprovador').exists():
        return 'aprovador'
    elif user.groups.filter(name='Solicitante').exists():
        return 'solicitante'
    
    return None


def is_engenheiro(user):
    """Verifica se o usuário é solicitante."""
    return user.is_authenticated and (
        user.groups.filter(name='Solicitante').exists() or
        user.is_superuser
    )


def is_aprovador(user):
    """Verifica se o usuário é aprovador."""
    return user.is_authenticated and (
        user.groups.filter(name='Aprovador').exists() or
        user.is_superuser
    )


def is_responsavel_empresa(user):
    """Verifica se o usuário é responsável por empresa."""
    return user.is_authenticated and (
        user.groups.filter(name='Responsavel Empresa').exists() or
        user.is_superuser
    )


def is_gestor(user):
    """Alias para is_aprovador (mantido para compatibilidade)."""
    return is_aprovador(user)


def is_admin(user):
    """Verifica se o usuário é administrador."""
    return user.is_authenticated and (
        user.groups.filter(name='Administrador').exists() or
        user.is_superuser
    )


def gestor_required(view_func):
    """
    Decorator para views que requerem permissão de gestor ou admin.
    """
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            messages.error(request, 'Você precisa estar autenticado para acessar esta página.')
            return redirect('login')
        
        if not (is_gestor(request.user) or is_admin(request.user)):
            messages.error(request, 'Você não tem permissão para acessar esta página.')
            return redirect('home')
        
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
            return redirect('login')
        
        if not is_admin(request.user):
            messages.error(request, 'Você não tem permissão para acessar esta página.')
            return redirect('home')
        
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

