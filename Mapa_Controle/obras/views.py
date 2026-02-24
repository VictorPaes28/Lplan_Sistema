"""
Views para gestão de obras e seleção de contexto.
"""
from django.shortcuts import redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from .models import Obra, LocalObra


@login_required
def selecionar_obra(request, obra_id):
    """
    Seleciona uma obra e armazena na sessão.
    Redireciona para a página anterior ou para home.
    """
    obra = get_object_or_404(Obra, id=obra_id, ativa=True)
    
    # Armazenar na sessão
    request.session['obra_id'] = obra.id
    
    # Se for requisição AJAX, retornar JSON
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({
            'success': True,
            'message': f'Obra "{obra.nome}" selecionada.',
            'obra': {
                'id': obra.id,
                'nome': obra.nome,
                'codigo_sienge': obra.codigo_sienge
            }
        })
    
    messages.success(request, f'Obra "{obra.nome}" selecionada.')
    
    # Redirecionar para a página anterior ou para home
    referer = request.META.get('HTTP_REFERER', '/')
    return redirect(referer)


@login_required
def api_locais_por_obra(request, obra_id):
    """
    API para carregar locais de uma obra específica (cascata de selects).
    Retorna JSON com lista de locais.
    """
    obra = get_object_or_404(Obra, id=obra_id, ativa=True)
    
    locais = LocalObra.objects.filter(obra=obra).order_by('tipo', 'nome')
    
    locais_list = [
        {
            'id': local.id,
            'nome': local.nome,
            'tipo': local.tipo,
            'tipo_display': local.get_tipo_display(),
            'parent_id': local.parent_id,
            'full_path': str(local)
        }
        for local in locais
    ]
    
    return JsonResponse({
        'success': True,
        'obra': {
            'id': obra.id,
            'nome': obra.nome,
            'codigo_sienge': obra.codigo_sienge
        },
        'locais': locais_list
    })

