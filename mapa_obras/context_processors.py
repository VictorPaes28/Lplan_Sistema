"""
Context processor para disponibilizar a obra selecionada em todos os templates do Mapa.
Só inclui obras às quais o usuário está vinculado (mesma regra do Diário de Obra).
"""
from .models import Obra


def obra_context(request):
    """
    Adiciona ao contexto:
    - obra_atual: Obra atualmente selecionada na sessão (só se o usuário tiver acesso)
    - obras_disponiveis: Lista de obras que o usuário pode acessar (para o dropdown)
    """
    if not request.user.is_authenticated:
        return {}

    from .views import _get_obras_for_user, _user_can_access_obra

    obras_disponiveis = _get_obras_for_user(request)
    obra_atual = None

    obra_id = request.session.get('obra_id')
    if obra_id:
        try:
            obra = Obra.objects.get(id=obra_id, ativa=True)
            if _user_can_access_obra(request, obra):
                obra_atual = obra
            else:
                request.session.pop('obra_id', None)
        except Obra.DoesNotExist:
            request.session.pop('obra_id', None)

    return {
        'obra_atual': obra_atual,
        'obras_disponiveis': obras_disponiveis,
    }
