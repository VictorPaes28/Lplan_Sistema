"""
Context processor para disponibilizar a obra selecionada em todos os templates.
"""
from .models import Obra


def obra_context(request):
    """
    Adiciona ao contexto:
    - obra_atual: Obra atualmente selecionada na sessão
    - obras_disponiveis: Lista de obras ativas para o dropdown
    """
    if not request.user.is_authenticated:
        return {}
    
    obras_disponiveis = Obra.objects.filter(ativa=True).order_by('nome')
    obra_atual = None
    
    # Verificar se há obra na sessão
    obra_id = request.session.get('obra_id')
    
    if obra_id:
        try:
            obra_atual = Obra.objects.get(id=obra_id, ativa=True)
        except Obra.DoesNotExist:
            # Obra não existe mais, limpar sessão
            del request.session['obra_id']
            obra_id = None
    
    # Se não há obra selecionada, usar a primeira disponível
    if not obra_atual and obras_disponiveis.exists():
        obra_atual = obras_disponiveis.first()
        request.session['obra_id'] = obra_atual.id
    
    return {
        'obra_atual': obra_atual,
        'obras_disponiveis': obras_disponiveis,
    }

