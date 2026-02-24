from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required


@login_required
def profile(request):
    return render(request, 'accounts/profile.html', {
        'user': request.user,
    })


@login_required
def home(request):
    """Dashboard do Mapa de Controle - página inicial após login."""
    user = request.user
    obra_atual = None
    if hasattr(request, 'session') and request.session.get('obra_id'):
        try:
            from obras.models import Obra
            obra_atual = Obra.objects.filter(id=request.session['obra_id'], ativa=True).first()
        except Exception:
            pass
    return render(request, 'accounts/dashboard.html', {
        'user': user,
        'obra_atual': obra_atual,
    })
