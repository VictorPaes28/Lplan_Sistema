"""
Views HTMX para Diário de Obra V2.0 - LPLAN

Views para interface HTMX com carregamento preguiçoso da árvore EAP.
"""
from django.shortcuts import render, get_object_or_404
from django.http import HttpResponse
from django.template.loader import render_to_string
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from .models import Project, Activity


@login_required
@require_http_methods(["GET"])
def project_activities_tree(request, project_id):
    """
    View HTMX para visualização da árvore de atividades de um projeto.
    
    Renderiza apenas as atividades raiz. Filhos são carregados via AJAX/HTMX.
    """
    project = get_object_or_404(Project, pk=project_id)
    
    # Verifica se o usuário tem acesso ao projeto (staff ou projeto ativo)
    if not (request.user.is_staff or request.user.is_superuser):
        # Usuários comuns só podem ver projetos que estão na sessão
        if 'selected_project_id' not in request.session or request.session['selected_project_id'] != project_id:
            raise PermissionDenied("Você não tem permissão para acessar esta obra.")
    
    root_activities = Activity.objects.filter(
        project=project,
        depth=1
    ).order_by('code')
    
    context = {
        'project': project,
        'root_activities': root_activities,
    }
    
    return render(request, 'core/activities_tree.html', context)


@login_required
@require_http_methods(["GET"])
def activity_children(request, activity_id):
    """
    View HTMX para carregar filhos de uma atividade (carregamento preguiçoso).
    
    Retorna apenas o HTML dos filhos, que será inserido via HTMX.
    """
    activity = get_object_or_404(Activity, pk=activity_id)
    children = activity.get_children().order_by('code')
    
    # Calcula progresso para cada filho
    from .services import ProgressService
    children_with_progress = []
    for child in children:
        progress = ProgressService.get_activity_progress(child)
        children_with_progress.append({
            'activity': child,
            'progress': float(progress)
        })
    
    # Obtém o projeto da atividade para passar ao template
    project = activity.project
    
    context = {
        'parent_activity': activity,
        'children_with_progress': children_with_progress,
        'project': project,
    }
    
    html = render_to_string('core/activity_children.html', context)
    return HttpResponse(html)

