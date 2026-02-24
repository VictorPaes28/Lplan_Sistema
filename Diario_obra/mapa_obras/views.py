"""
Views para gestão de obras e seleção de contexto.
Obras listadas e selecionáveis seguem a mesma regra do Diário de Obra: apenas as
obras cujo projeto (core.Project) o usuário está vinculado (ProjectMember ou GestControll).
"""
from django.shortcuts import redirect, get_object_or_404, render
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from .models import Obra, LocalObra


def _get_obras_for_user(request):
    """
    Obras que o usuário pode acessar no Mapa (mesma regra do Diário: vínculo por projeto).
    Staff/superuser vê todas; demais só obras cujo codigo_sienge corresponde a um
    core.Project ao qual o usuário está vinculado (ProjectMember ou permissão GestControll).
    """
    from core.frontend_views import _get_projects_for_user
    projects = _get_projects_for_user(request)
    codigos = list(projects.values_list('code', flat=True))
    return Obra.objects.filter(ativa=True, codigo_sienge__in=codigos).order_by('nome')


def _user_can_access_obra(request, obra):
    """Verifica se o usuário pode acessar a obra no Mapa (mesma regra do Diário)."""
    from core.frontend_views import _get_projects_for_user
    projects = _get_projects_for_user(request)
    codigos = set(projects.values_list('code', flat=True))
    return obra.ativa and obra.codigo_sienge in codigos


@login_required
def listar_obras(request):
    """
    Lista as obras disponíveis para seleção (apenas as que o usuário está vinculado).
    """
    obras = _get_obras_for_user(request)
    obra_atual = None
    obra_id = request.session.get('obra_id')
    if obra_id:
        try:
            obj = Obra.objects.get(id=obra_id, ativa=True)
            if _user_can_access_obra(request, obj):
                obra_atual = obj
        except Obra.DoesNotExist:
            pass
    return render(request, 'mapa_obras/listar_obras.html', {
        'obras': obras,
        'obra_atual': obra_atual,
    })


@login_required
def selecionar_obra(request, obra_id):
    """
    Seleciona uma obra e armazena na sessão.
    Só permite obras às quais o usuário está vinculado (mesma regra do Diário).
    """
    obra = get_object_or_404(Obra, id=obra_id, ativa=True)
    if not _user_can_access_obra(request, obra):
        messages.error(request, 'Você não está vinculado a esta obra.')
        return redirect('mapa_obras:home')
    
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
    
    messages.success(request, f'Obra "{obra.nome}" selecionada com sucesso!')
    
    # Se o usuário estava em uma página de engenharia, voltar para lá
    referer = request.META.get('HTTP_REFERER', '')
    if '/engenharia/' in referer:
        return redirect(referer)
    
    # Caso contrário (veio da seleção de obras), ir para o Mapa
    return redirect('engenharia:mapa')


@login_required
def api_locais_por_obra(request, obra_id):
    """
    API para carregar locais de uma obra específica (cascata de selects).
    Só retorna dados se o usuário tiver acesso à obra.
    """
    obra = get_object_or_404(Obra, id=obra_id, ativa=True)
    if not _user_can_access_obra(request, obra):
        return JsonResponse({'success': False, 'error': 'Sem permissão para esta obra.'}, status=403)
    
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
