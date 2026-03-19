"""
Central: gestão de usuários (e obras = /projects/) fora do GestControll.
Apenas staff/superuser. As views de usuário delegam ao gestao com request._central_redirect=True
para que os redirects apontem para /central/usuarios/.
"""
from django.shortcuts import redirect, render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import Group
from django.core.exceptions import PermissionDenied
from django.contrib import messages
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
from django.conf import settings
from django.utils import timezone
from django.core.mail import EmailMessage

from accounts.models import UserSignupRequest
from accounts.signup_services import approve_signup_request
from accounts.groups import GRUPOS
from core.models import Project, ProjectOwner


def _staff_required(f):
    def wrapper(request, *args, **kwargs):
        if not (request.user.is_authenticated and (request.user.is_staff or request.user.is_superuser)):
            raise PermissionDenied('Acesso restrito ao central.')
        return f(request, *args, **kwargs)
    return wrapper


def _signup_approver_required(f):
    def wrapper(request, *args, **kwargs):
        if not request.user.is_superuser:
            raise PermissionDenied('Acesso restrito a superusuário.')
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


@login_required
@_staff_required
@_signup_approver_required
def central_signup_requests_list(request):
    from core.models import Project
    groups = list(
        Group.objects.filter(name__in=GRUPOS.TODOS).order_by('name')
    )
    projects = list(Project.objects.filter(is_active=True).order_by('name'))
    status_filter = (request.GET.get('status') or '').strip()
    requests_qs = UserSignupRequest.objects.select_related('approved_by', 'approved_user', 'requested_by')
    if status_filter in {
        UserSignupRequest.STATUS_PENDENTE,
        UserSignupRequest.STATUS_APROVADO,
        UserSignupRequest.STATUS_REJEITADO,
    }:
        requests_qs = requests_qs.filter(status=status_filter)
    requests_qs = requests_qs.order_by('-created_at')
    return render(
        request,
        'core/central_signup_requests.html',
        {
            'requests_qs': requests_qs,
            'status_filter': status_filter,
            'groups': groups,
            'projects': projects,
        },
    )


@login_required
@_staff_required
@_signup_approver_required
def central_signup_request_approve(request, pk):
    if request.method != 'POST':
        return redirect('central_signup_requests')
    signup_request = get_object_or_404(UserSignupRequest, pk=pk)
    selected_groups = request.POST.getlist('approved_groups')
    selected_projects = request.POST.getlist('approved_projects')
    if not selected_groups:
        messages.error(request, 'Selecione pelo menos uma permissão (grupo) antes de aprovar.')
        return redirect('central_signup_requests')
    try:
        user = approve_signup_request(
            signup_request,
            request.user,
            selected_groups=selected_groups,
            selected_project_ids=selected_projects,
        )
    except Exception as exc:
        messages.error(request, f'Não foi possível aprovar a solicitação: {exc}')
    else:
        if signup_request.requested_by and signup_request.requested_by != request.user:
            try:
                from gestao_aprovacao.utils import criar_notificacao
                criar_notificacao(
                    usuario=signup_request.requested_by,
                    tipo='pedido_aprovado',
                    titulo='Solicitação de cadastro aprovada',
                    mensagem=f'A solicitação de {signup_request.full_name} foi aprovada.',
                    work_order=None,
                )
            except Exception:
                pass
        messages.success(request, f'Solicitação aprovada. Usuário "{user.username}" criado com sucesso.')
    return redirect('central_signup_requests')


@login_required
@_staff_required
@_signup_approver_required
def central_signup_request_reject(request, pk):
    if request.method != 'POST':
        return redirect('central_signup_requests')
    signup_request = get_object_or_404(UserSignupRequest, pk=pk)
    if signup_request.status != UserSignupRequest.STATUS_PENDENTE:
        messages.warning(request, 'Esta solicitação já foi processada.')
        return redirect('central_signup_requests')

    rejection_reason = (request.POST.get('rejection_reason') or '').strip()
    if not rejection_reason:
        messages.error(request, 'Informe o motivo da rejeição.')
        return redirect('central_signup_requests')

    signup_request.status = UserSignupRequest.STATUS_REJEITADO
    signup_request.approved_by = request.user
    signup_request.rejected_at = timezone.now()
    signup_request.rejection_reason = rejection_reason
    signup_request.save(
        update_fields=['status', 'approved_by', 'rejected_at', 'rejection_reason', 'updated_at']
    )

    if signup_request.email:
        site_url = (getattr(settings, 'SITE_URL', '') or '').rstrip('/') or '/'
        subject = 'Solicitação de cadastro reprovada'
        body = (
            f'Olá, {signup_request.full_name}.\n\n'
            f'Sua solicitação de cadastro no sistema LPLAN foi reprovada.\n'
            f'Motivo informado: {rejection_reason}\n\n'
            f'Se necessário, envie uma nova solicitação em {site_url}/cadastro/solicitar/.\n\n'
            f'Mensagem automática do sistema.'
        )
        from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', '') or getattr(settings, 'EMAIL_HOST_USER', '')
        try:
            EmailMessage(subject=subject, body=body, from_email=from_email, to=[signup_request.email]).send(fail_silently=True)
        except Exception:
            pass
    if signup_request.requested_by and signup_request.requested_by != request.user:
        try:
            from gestao_aprovacao.utils import criar_notificacao
            criar_notificacao(
                usuario=signup_request.requested_by,
                tipo='pedido_reprovado',
                titulo='Solicitação de cadastro rejeitada',
                mensagem=f'A solicitação de {signup_request.full_name} foi rejeitada.',
                work_order=None,
            )
        except Exception:
            pass

    messages.success(request, 'Solicitação rejeitada.')
    return redirect('central_signup_requests')


# ═══════════════════════════════════════════════════════════════
# Clientes (Donos da Obra) — cadastro e gestão
# ═══════════════════════════════════════════════════════════════

def _build_clients_list():
    """Monta lista agrupada de clientes (ProjectOwners) por usuário."""
    owners = (
        ProjectOwner.objects
        .select_related('user', 'project')
        .order_by('user__first_name', 'user__username', 'project__code')
    )
    clients_map = {}
    for owner in owners:
        uid = owner.user.id
        if uid not in clients_map:
            clients_map[uid] = {'user': owner.user, 'projects': []}
        clients_map[uid]['projects'].append(owner)
    return list(clients_map.values())


def _get_client_user_or_404(user_id):
    """
    Retorna usuário alvo apenas se ele for cliente (possui vínculo ProjectOwner).
    Evita ações acidentais em usuários administrativos.
    """
    from django.contrib.auth.models import User
    user = get_object_or_404(User, pk=user_id)
    if not ProjectOwner.objects.filter(user=user).exists():
        raise PermissionDenied('Usuário informado não é cliente do portal de diários.')
    return user


@login_required
@_staff_required
def central_clients_view(request):
    from django.contrib.auth.models import User

    if request.method == 'POST':
        action = request.POST.get('action', 'create')

        if action == 'create':
            username = (request.POST.get('username') or '').strip()
            email = (request.POST.get('email') or '').strip()
            first_name = (request.POST.get('first_name') or '').strip()
            last_name = (request.POST.get('last_name') or '').strip()
            password = (request.POST.get('password') or '').strip()
            project_ids = request.POST.getlist('projects')

            if not username:
                messages.error(request, 'Username é obrigatório.')
                return redirect('central_clients')
            if not project_ids:
                messages.error(request, 'Selecione pelo menos uma obra.')
                return redirect('central_clients')
            if User.objects.filter(username=username).exists():
                messages.error(request, f'O username "{username}" já existe.')
                return redirect('central_clients')
            if email:
                try:
                    validate_email(email)
                except ValidationError:
                    messages.error(request, 'E-mail inválido.')
                    return redirect('central_clients')

            unique_project_ids = sorted(set(pid for pid in project_ids if str(pid).strip()))
            projects_qs = Project.objects.filter(id__in=unique_project_ids, is_active=True)
            if projects_qs.count() != len(unique_project_ids):
                messages.error(request, 'Há obra inválida/inativa selecionada. Atualize a página e tente novamente.')
                return redirect('central_clients')

            if not password or len(password) < 8:
                messages.error(
                    request,
                    'Senha é obrigatória e deve ter no mínimo 8 caracteres.'
                )
                return redirect('central_clients')

            user = User(
                username=username,
                email=email,
                first_name=first_name,
                last_name=last_name,
                is_active=True,
                is_staff=False,
                is_superuser=False,
            )
            user.set_password(password)
            user.save()

            created_count = 0
            project_names = []
            for proj in projects_qs:
                _, created = ProjectOwner.objects.get_or_create(project=proj, user=user)
                if created:
                    created_count += 1
                project_names.append(f"{proj.code} — {proj.name}")

            messages.success(
                request,
                f'Cliente "{user.get_full_name() or user.username}" criado e vinculado a {created_count} obra(s). '
                f'Login: {user.username}.'
            )
            return redirect('central_clients')

        elif action == 'add_project':
            user_id = request.POST.get('user_id')
            project_id = request.POST.get('project_id')
            if user_id and project_id:
                user = _get_client_user_or_404(user_id)
                project = get_object_or_404(Project, pk=project_id, is_active=True)
                _, created = ProjectOwner.objects.get_or_create(project=project, user=user)
                if created:
                    messages.success(request, f'Obra "{project.code}" vinculada a "{user.get_full_name() or user.username}".')
                else:
                    messages.info(request, 'Este cliente já está vinculado a esta obra.')
            return redirect('central_clients')

        elif action == 'edit':
            user_id = request.POST.get('user_id')
            user = _get_client_user_or_404(user_id)
            new_email = (request.POST.get('edit_email') or '').strip()
            new_first = (request.POST.get('edit_first_name') or '').strip()
            new_last = (request.POST.get('edit_last_name') or '').strip()
            if new_email:
                try:
                    validate_email(new_email)
                    user.email = new_email
                except ValidationError:
                    messages.error(request, 'E-mail inválido.')
                    return redirect('central_clients')
            else:
                user.email = ''
            user.first_name = new_first
            user.last_name = new_last
            user.save(update_fields=['email', 'first_name', 'last_name'])
            messages.success(request, f'Dados de "{user.get_full_name() or user.username}" atualizados.')
            return redirect('central_clients')

        elif action == 'reset_password':
            user_id = request.POST.get('user_id')
            new_password = (request.POST.get('new_password') or '').strip()
            user = _get_client_user_or_404(user_id)
            if not new_password or len(new_password) < 8:
                messages.error(request, 'A nova senha deve ter no mínimo 8 caracteres.')
                return redirect('central_clients')
            user.set_password(new_password)
            user.save(update_fields=['password'])
            messages.success(request, f'Senha de "{user.get_full_name() or user.username}" redefinida.')
            return redirect('central_clients')

        elif action == 'toggle_active':
            user_id = request.POST.get('user_id')
            user = _get_client_user_or_404(user_id)
            user.is_active = not user.is_active
            user.save(update_fields=['is_active'])
            status = 'ativado' if user.is_active else 'desativado'
            messages.success(request, f'Cliente "{user.get_full_name() or user.username}" {status}.')
            return redirect('central_clients')

        elif action == 'delete':
            user_id = request.POST.get('user_id')
            user = _get_client_user_or_404(user_id)
            if user == request.user:
                messages.error(request, 'Você não pode excluir seu próprio usuário por esta tela.')
                return redirect('central_clients')
            name = user.get_full_name() or user.username
            user.delete()
            messages.success(request, f'Cliente "{name}" excluído permanentemente.')
            return redirect('central_clients')

    clients = _build_clients_list()
    projects = Project.objects.filter(is_active=True).order_by('code')

    site_url = (getattr(settings, 'SITE_URL', '') or '').rstrip('/')
    login_url = f'{site_url}/login/' if site_url else '/login/'

    return render(request, 'core/central_clients.html', {
        'clients': clients,
        'projects': projects,
        'login_url': login_url,
    })


@login_required
@_staff_required
def central_client_remove_owner(request, pk):
    if request.method != 'POST':
        return redirect('central_clients')
    owner = get_object_or_404(ProjectOwner, pk=pk)
    user = owner.user
    project_code = owner.project.code
    owner.delete()

    remaining = ProjectOwner.objects.filter(user=user).count()
    if remaining == 0:
        messages.info(
            request,
            f'Vínculo com "{project_code}" removido. '
            f'"{user.get_full_name() or user.username}" não é mais dono de nenhuma obra '
            f'(o login dele continua existindo).'
        )
    else:
        messages.success(request, f'Vínculo com "{project_code}" removido.')
    return redirect('central_clients')
