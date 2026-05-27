"""
Utilitários para verificação de permissões e perfis de usuário.
"""
from functools import wraps
from django.contrib.auth import get_user_model
from django.contrib import messages
from django.shortcuts import redirect
from accounts.groups import GRUPOS, usuario_tem_administracao_global_na_plataforma
from .models import Notificacao, AprovacaoEmailDestinatario, Empresa


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


def usuario_e_admin_sistema_gestao(user):
    """
    Admin operacional do sistema — pode solicitar exclusão de qualquer pedido elegível.
    Superuser, staff Django, grupo «Administrador» e demais admins globais legados.
    """
    if not user.is_authenticated:
        return False
    if user.is_superuser or getattr(user, 'is_staff', False):
        return True
    if usuario_tem_administracao_global_na_plataforma(user):
        return True
    return user.groups.filter(name=GRUPOS.ADMINISTRADOR).exists()


def projects_disponiveis_para_vinculo_usuario():
    """Projetos listados ao vincular usuário (ativos e inativos; inativos = consulta nos módulos)."""
    from core.models import Project

    return Project.objects.order_by('-is_active', 'name')


def obra_gestao_do_projeto(project_id):
    """Obra GestControll ligada ao projeto, inclusive inativa."""
    from .models import Obra

    if not project_id:
        return None
    return Obra.objects.filter(project_id=project_id).order_by('-ativo').first()


def usuario_pode_marcar_pedido_analisado(user):
    """
    Checkbox "Analisado" na lista de pedidos: apenas administradores da plataforma
    ou usuário cujo e-mail está cadastrado e ativo em
    /gestao/emails/destinatarios-aprovacao/ (modelo AprovacaoEmailDestinatario).
    """
    if not getattr(user, "is_authenticated", False):
        return False
    if is_admin(user):
        return True
    email = (getattr(user, "email", None) or "").strip().lower()
    if not email:
        return False
    try:
        return AprovacaoEmailDestinatario.objects.filter(ativo=True, email__iexact=email).exists()
    except Exception:
        return False


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


def texto_comentario_thread_reprovacao(tags_nomes: list[str], complemento: str) -> str:
    """
    Texto objetivo para registrar reprovação na thread de comentários do pedido,
    alinhado ao que já aparece no histórico de status (tags + observações).
    """
    tags = [str(t).strip() for t in (tags_nomes or []) if t and str(t).strip()]
    comp = (complemento or '').strip()
    lines = ['[Reprovação]', '']
    if tags:
        lines.append('Tags de controle: ' + ', '.join(tags))
    if comp:
        label = 'Complemento' if tags else 'Observações'
        lines.append(f'{label}: {comp}')
    return '\n'.join(lines).strip()

