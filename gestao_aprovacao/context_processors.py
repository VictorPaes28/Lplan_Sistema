"""
Context processors para adicionar variáveis globais aos templates.
"""
from .models import Notificacao, WorkOrderPermission
from .utils import get_user_profile, is_admin, is_responsavel_empresa, is_engenheiro


def notificacoes_count(request):
    """
    Adiciona o contador de notificações não lidas ao contexto de todos os templates.
    Otimizado para evitar queries desnecessárias.
    """
    if request.user.is_authenticated:
        # count() já é otimizado - não carrega objetos, apenas conta
        count = Notificacao.objects.filter(usuario=request.user, lida=False).count()
        return {'notificacoes_count': count}
    return {'notificacoes_count': 0}


def user_context(request):
    """
    Adiciona informações do usuário ao contexto de todos os templates.
    """
    context = {}
    
    if request.user.is_authenticated:
        user = request.user
        context['user_profile'] = get_user_profile(user)
        context['is_admin'] = is_admin(user)
        context['is_responsavel_empresa'] = is_responsavel_empresa(user)
        
        # Verificar se pode criar pedido (otimizado - apenas verifica existência)
        pode_criar_pedido = (
            is_engenheiro(user) or
            WorkOrderPermission.objects.filter(
                usuario=user,
                tipo_permissao='solicitante',
                ativo=True
            ).exists() or  # exists() já é otimizado - não carrega objetos
            is_admin(user)
        )
        context['pode_criar_pedido'] = pode_criar_pedido
    else:
        context['user_profile'] = None
        context['is_admin'] = False
        context['is_responsavel_empresa'] = False
        context['pode_criar_pedido'] = False
    
    return context

