from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from .groups import GRUPOS


@login_required
def profile(request):
    return render(request, 'accounts/profile.html', {
        'user': request.user,
    })


@login_required
def home(request):
    """
    Página inicial após login.
    Sistema unificado: redireciona para o seletor de sistemas (select-system).
    Usuários que só acessam o Mapa de Suprimentos são redirecionados direto.
    """
    user = request.user
    user_groups = set(user.groups.values_list('name', flat=True))
    
    # Se o usuário só tem grupo ENGENHARIA (sem outros), vai direto ao mapa
    if user_groups == {GRUPOS.ENGENHARIA}:
        return redirect('engenharia:mapa')
    
    # Se tem algum grupo de qualquer sistema, vai pro seletor
    if user_groups or user.is_staff or user.is_superuser:
        return redirect('select-system')
    
    # Se não tem nenhum grupo, mostra página de aviso
    return render(request, 'accounts/home.html', {
        'user': user,
    })
