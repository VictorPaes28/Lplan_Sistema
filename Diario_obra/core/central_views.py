"""
Central: gestão de usuários (e obras = /projects/) fora do GestControll.
Apenas staff/superuser. As views de usuário delegam ao gestao com request._central_redirect=True
para que os redirects apontem para /central/usuarios/.
"""
from django.shortcuts import redirect, render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.contrib import messages
from django.core.validators import validate_email
from django.core.exceptions import ValidationError


def _staff_required(f):
    def wrapper(request, *args, **kwargs):
        if not (request.user.is_authenticated and (request.user.is_staff or request.user.is_superuser)):
            raise PermissionDenied('Acesso restrito ao central.')
        return f(request, *args, **kwargs)
    return wrapper


def _get_gestao_user_views():
    from gestao_aprovacao import views as g
    return g.list_users, g.create_user, g.edit_user, g.delete_user


@login_required
@_staff_required
def central_list_users(request):
    request._central_redirect = True
    return _get_gestao_user_views()[0](request)


@login_required
@_staff_required
def central_create_user(request):
    request._central_redirect = True
    return _get_gestao_user_views()[1](request)


@login_required
@_staff_required
def central_edit_user(request, pk):
    request._central_redirect = True
    return _get_gestao_user_views()[2](request, pk=pk)


@login_required
@_staff_required
def central_delete_user(request, pk):
    request._central_redirect = True
    return _get_gestao_user_views()[3](request, pk=pk)


@login_required
@_staff_required
def central_manutencao_view(request):
    """
    Tela de manutenção/diagnóstico do Central (staff): status da sincronia de obras,
    botão para re-sincronizar todas e links úteis (Admin, Logs de e-mail).
    """
    from core.models import Project
    from core.sync_obras import sync_project_to_gestao_and_mapa

    if request.method == 'POST' and request.POST.get('action') == 'sync_all':
        projects = list(Project.objects.all())
        ok_gestao = ok_mapa = 0
        errors = []
        for project in projects:
            r = sync_project_to_gestao_and_mapa(project, return_result=True)
            if r['gestao_ok']:
                ok_gestao += 1
            if r.get('gestao_error'):
                errors.append(f"{project.code} (GestControll): {r['gestao_error']}")
            if r['mapa_ok']:
                ok_mapa += 1
            if r.get('mapa_error'):
                errors.append(f"{project.code} (Mapa): {r['mapa_error']}")
        if errors:
            messages.error(
                request,
                "Algo deu errado ao atualizar as listas. Tente de novo em alguns minutos. Se o problema continuar, peça ajuda ao responsável técnico."
            )
        else:
            messages.success(
                request,
                f"Pronto! As listas foram atualizadas. {len(projects)} obra(s) agora aparecem no sistema de Pedidos e no Mapa."
            )
        return redirect('central_manutencao')

    # Estatísticas de sincronia
    try:
        from gestao_aprovacao.models import Obra as ObraGestao
        gestao_com_project = ObraGestao.objects.filter(project__isnull=False).count()
        gestao_total = ObraGestao.objects.count()
    except Exception:
        gestao_com_project = gestao_total = 0

    try:
        from mapa_obras.models import Obra as ObraMapa
        mapa_count = ObraMapa.objects.count()
    except Exception:
        mapa_count = 0

    projects_count = Project.objects.count()
    sync_ok = (
        projects_count > 0
        and projects_count == gestao_com_project
        and projects_count == mapa_count
    )

    context = {
        'projects_count': projects_count,
        'gestao_com_project': gestao_com_project,
        'gestao_total': gestao_total,
        'mapa_count': mapa_count,
        'sync_ok': sync_ok,
    }
    return render(request, 'core/central_manutencao.html', context)


@login_required
@_staff_required
def central_ajuda_view(request):
    """
    Página "Quando algo der errado" em linguagem simples para funcionário
    resolver sozinho, sem conhecimento técnico.
    """
    return render(request, 'core/central_ajuda.html')


@login_required
@_staff_required
def central_diary_emails_view(request, project_id):
    """
    Tela para cadastrar os e-mails que recebem o diário dessa obra todo dia.
    Lista os atuais e permite adicionar/remover.
    """
    from core.models import Project, ProjectDiaryRecipient

    project = get_object_or_404(Project, pk=project_id)
    recipients = project.diary_recipients.all()

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'add':
            email = (request.POST.get('email') or '').strip()
            nome = (request.POST.get('nome') or '').strip()
            if not email:
                messages.error(request, 'Informe o e-mail.')
            else:
                try:
                    validate_email(email)
                except ValidationError:
                    messages.error(request, 'E-mail inválido.')
                else:
                    _, created = ProjectDiaryRecipient.objects.get_or_create(
                        project=project,
                        email=email.lower(),
                        defaults={'nome': nome}
                    )
                    if created:
                        messages.success(request, f'E-mail {email} adicionado. Ele passará a receber o diário da obra todo dia.')
                    else:
                        messages.info(request, 'Este e-mail já estava cadastrado para esta obra.')
            return redirect('central_diary_emails', project_id=project_id)
        if action == 'remove':
            rec_id = request.POST.get('recipient_id')
            if rec_id:
                ProjectDiaryRecipient.objects.filter(project=project, pk=rec_id).delete()
                messages.success(request, 'E-mail removido.')
            return redirect('central_diary_emails', project_id=project_id)

    return render(request, 'core/central_diary_emails.html', {
        'project': project,
        'recipients': recipients,
    })


@login_required
@_staff_required
def central_diary_email_remove_view(request, project_id, pk):
    """Remove um e-mail da lista de envio do diário e redireciona de volta."""
    from core.models import Project, ProjectDiaryRecipient

    project = get_object_or_404(Project, pk=project_id)
    ProjectDiaryRecipient.objects.filter(project=project, pk=pk).delete()
    messages.success(request, 'E-mail removido.')
    return redirect('central_diary_emails', project_id=project_id)
