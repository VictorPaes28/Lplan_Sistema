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
from django.core.paginator import Paginator
from django.http import HttpResponse

from pathlib import Path
from datetime import datetime, timedelta
import re
import csv

from accounts.models import UserSignupRequest
from accounts.signup_services import approve_signup_request
from accounts.groups import GRUPOS
from core.models import Project, ProjectOwner, ConstructionDiary, DiaryCorrectionRequestLog


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


def _parse_log_datetime(raw_value):
    if not raw_value:
        return None
    for fmt in ('%Y-%m-%d %H:%M:%S,%f', '%Y-%m-%d %H:%M:%S'):
        try:
            return datetime.strptime(raw_value, fmt)
        except ValueError:
            continue
    return None


def _guess_log_user(message):
    if not message:
        return ''
    patterns = [
        r'\buser(?:name)?\s*[=:]\s*([A-Za-z0-9_.@+-]+)',
        r'\busu[aá]rio\s*[=:]\s*([A-Za-z0-9_.@+-]+)',
        r'\bpor\s+([A-Za-z0-9_.@+-]+)\b',
    ]
    for pattern in patterns:
        match = re.search(pattern, message, flags=re.IGNORECASE)
        if match:
            return match.group(1)
    return ''


def _parse_log_lines(file_path, source_label, max_lines=6000):
    entries = []
    simple_re = re.compile(
        r'^(?P<level>[A-Z]+)\s+'
        r'(?P<timestamp>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}(?:,\d+)?)\s+'
        r'(?P<logger>[A-Za-z0-9_.-]+)\s+'
        r'(?P<message>.*)$'
    )
    verbose_re = re.compile(
        r'^(?P<level>[A-Z]+)\s+'
        r'(?P<timestamp>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}(?:,\d+)?)\s+'
        r'(?P<logger>[A-Za-z0-9_.-]+)\s+'
        r'(?P<process>\d+)\s+(?P<thread>\d+)\s+'
        r'(?P<message>.*)$'
    )
    raw_lines = []
    try:
        with file_path.open('r', encoding='utf-8', errors='replace') as handle:
            raw_lines = handle.readlines()
    except OSError:
        return entries

    if len(raw_lines) > max_lines:
        raw_lines = raw_lines[-max_lines:]

    current_entry = None
    for raw_line in raw_lines:
        line = raw_line.rstrip('\n')
        if not line.strip():
            continue
        parsed = verbose_re.match(line) or simple_re.match(line)
        if parsed:
            if current_entry:
                entries.append(current_entry)
            payload = parsed.groupdict()
            message = (payload.get('message') or '').strip()
            current_entry = {
                'level': (payload.get('level') or 'INFO').upper(),
                'timestamp_str': payload.get('timestamp') or '',
                'timestamp': _parse_log_datetime(payload.get('timestamp') or ''),
                'logger': payload.get('logger') or 'sistema',
                'message': message,
                'details': '',
                'source': source_label,
                'user_hint': _guess_log_user(message),
            }
        elif current_entry:
            if current_entry['details']:
                current_entry['details'] += '\n' + line
            else:
                current_entry['details'] = line
    if current_entry:
        entries.append(current_entry)
    return entries


def get_log_health_snapshot(hours=24):
    """
    Retorna um resumo rápido de saúde dos logs para cards do painel.
    """
    try:
        log_dir = Path(getattr(settings, 'LOG_DIR', Path(settings.BASE_DIR) / 'logs'))
        errors_file = log_dir / 'lplan_errors.log'
        general_file = log_dir / 'lplan.log'
        entries = []
        if errors_file.exists():
            entries.extend(_parse_log_lines(errors_file, source_label='Erros', max_lines=5000))
        if general_file.exists():
            entries.extend(_parse_log_lines(general_file, source_label='Geral', max_lines=2000))
        now = timezone.now()
        window_start = now - timedelta(hours=hours)

        def to_aware(dt):
            if not dt:
                return None
            return timezone.make_aware(dt, timezone.get_current_timezone()) if timezone.is_naive(dt) else dt

        recent = []
        for item in entries:
            ts = to_aware(item.get('timestamp'))
            if ts and ts >= window_start:
                recent.append({**item, 'timestamp': ts})
        recent_errors = [e for e in recent if e.get('level') in {'ERROR', 'CRITICAL'}]
        recent_warnings = [e for e in recent if e.get('level') == 'WARNING']
        recent_errors.sort(key=lambda e: e.get('timestamp') or timezone.datetime.min.replace(tzinfo=timezone.get_current_timezone()), reverse=True)
        return {
            'window_hours': hours,
            'recent_errors': len(recent_errors),
            'recent_warnings': len(recent_warnings),
            'last_error_at': recent_errors[0]['timestamp'] if recent_errors else None,
            'has_alert': len(recent_errors) > 0,
        }
    except Exception:
        return {
            'window_hours': hours,
            'recent_errors': 0,
            'recent_warnings': 0,
            'last_error_at': None,
            'has_alert': False,
        }


@login_required
@_staff_required
def central_system_logs_view(request):
    """Visão centralizada dos logs de sistema (arquivo local)."""
    log_dir = Path(getattr(settings, 'LOG_DIR', Path(settings.BASE_DIR) / 'logs'))
    source = (request.GET.get('source') or 'all').strip().lower()
    level = (request.GET.get('level') or '').strip().upper()
    logger_filter = (request.GET.get('logger') or '').strip().lower()
    search = (request.GET.get('q') or '').strip()
    user_filter = (request.GET.get('user') or '').strip().lower()
    date_start_raw = (request.GET.get('date_start') or '').strip()
    date_end_raw = (request.GET.get('date_end') or '').strip()
    page_number = request.GET.get('page')

    date_start = _parse_log_datetime(f'{date_start_raw} 00:00:00') if date_start_raw else None
    date_end = _parse_log_datetime(f'{date_end_raw} 23:59:59') if date_end_raw else None

    source_map = {
        'geral': ('lplan.log', 'Geral'),
        'erros': ('lplan_errors.log', 'Erros'),
    }
    selected_sources = []
    if source in source_map:
        selected_sources = [source]
    else:
        selected_sources = ['erros', 'geral']

    all_entries = []
    for source_key in selected_sources:
        filename, label = source_map[source_key]
        path = log_dir / filename
        if path.exists():
            all_entries.extend(_parse_log_lines(path, source_label=label))

    def _entry_matches(entry):
        if level and entry.get('level') != level:
            return False
        if logger_filter and logger_filter not in (entry.get('logger') or '').lower():
            return False
        if user_filter and user_filter not in (entry.get('user_hint') or '').lower():
            return False
        if date_start and entry.get('timestamp') and entry['timestamp'] < date_start:
            return False
        if date_end and entry.get('timestamp') and entry['timestamp'] > date_end:
            return False
        if search:
            haystack = ' '.join([
                entry.get('message') or '',
                entry.get('details') or '',
                entry.get('logger') or '',
                entry.get('user_hint') or '',
            ]).lower()
            if search.lower() not in haystack:
                return False
        return True

    filtered = [entry for entry in all_entries if _entry_matches(entry)]
    filtered.sort(key=lambda item: item.get('timestamp') or datetime.min, reverse=True)

    if (request.GET.get('format') or '').strip().lower() == 'csv':
        response = HttpResponse(content_type='text/csv; charset=utf-8')
        response['Content-Disposition'] = 'attachment; filename="logs_sistema_filtrados.csv"'
        response.write('\ufeff')
        writer = csv.writer(response, delimiter=';')
        writer.writerow(['timestamp', 'nivel', 'arquivo', 'logger', 'usuario', 'mensagem', 'detalhes'])
        for entry in filtered:
            writer.writerow([
                entry.get('timestamp_str') or '',
                entry.get('level') or '',
                entry.get('source') or '',
                entry.get('logger') or '',
                entry.get('user_hint') or '',
                (entry.get('message') or '').replace('\n', ' ').strip(),
                entry.get('details') or '',
            ])
        return response

    total_count = len(filtered)
    error_count = sum(1 for e in filtered if e.get('level') in {'ERROR', 'CRITICAL'})
    warning_count = sum(1 for e in filtered if e.get('level') == 'WARNING')
    last_at = filtered[0]['timestamp'] if filtered and filtered[0].get('timestamp') else None

    paginator = Paginator(filtered, 40)
    page_obj = paginator.get_page(page_number)

    loggers = sorted({(e.get('logger') or '').strip() for e in all_entries if e.get('logger')})

    context = {
        'page_obj': page_obj,
        'entries': page_obj.object_list,
        'source': source,
        'level': level,
        'logger_filter': logger_filter,
        'search': search,
        'user_filter': user_filter,
        'date_start': date_start_raw,
        'date_end': date_end_raw,
        'total_count': total_count,
        'error_count': error_count,
        'warning_count': warning_count,
        'last_at': last_at,
        'available_loggers': loggers,
    }
    return render(request, 'core/central_system_logs.html', context)


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


def _merge_pending_correction_items():
    """Pendentes de liberação: logs novos + diários legados sem linha de log aberta."""
    pending_logs = list(
        DiaryCorrectionRequestLog.objects.filter(granted_at__isnull=True)
        .select_related('diary', 'diary__project', 'requested_by')
    )
    open_diary_ids = {log.diary_id for log in pending_logs}
    legacy_diaries = list(
        ConstructionDiary.objects.filter(
            edit_requested_at__isnull=False,
            provisional_edit_granted_at__isnull=True,
        )
        .exclude(pk__in=open_diary_ids)
        .select_related('project', 'edit_requested_by')
    )
    items = []
    for log in pending_logs:
        items.append({
            'kind': 'log',
            'diary': log.diary,
            'requested_at': log.requested_at,
            'requested_by': log.requested_by,
            'note': log.note or '',
            'log': log,
        })
    for d in legacy_diaries:
        items.append({
            'kind': 'legacy',
            'diary': d,
            'requested_at': d.edit_requested_at,
            'requested_by': d.edit_requested_by,
            'note': (d.edit_request_note or ''),
            'log': None,
        })
    items.sort(key=lambda x: x['requested_at'] or timezone.now(), reverse=True)
    return items


@login_required
@_staff_required
def central_diary_edit_requests_view(request):
    """Lista pedidos pendentes de liberação e histórico de pedidos já liberados."""
    pending_items = _merge_pending_correction_items()
    history = (
        DiaryCorrectionRequestLog.objects.filter(granted_at__isnull=False)
        .select_related('diary', 'diary__project', 'requested_by', 'granted_by')
        .order_by('-granted_at')[:200]
    )
    return render(
        request,
        'core/central_diary_edit_requests.html',
        {'pending_items': pending_items, 'history': history},
    )


@login_required
@_staff_required
def central_diary_grant_provisional_edit(request, pk):
    """Libera edição provisória do diário (staff). O utilizador pode editar até guardar."""
    if request.method != 'POST':
        return redirect('central_diary_edit_requests')
    diary = get_object_or_404(ConstructionDiary, pk=pk)
    if not diary.edit_requested_at:
        messages.error(request, 'Este relatório não tem pedido de correção pendente.')
        return redirect('central_diary_edit_requests')
    if diary.provisional_edit_granted_at:
        messages.info(request, 'Este relatório já tem edição liberada.')
        return redirect('central_diary_edit_requests')
    now = timezone.now()
    diary.provisional_edit_granted_at = now
    diary.provisional_edit_granted_by = request.user
    diary.save(update_fields=['provisional_edit_granted_at', 'provisional_edit_granted_by', 'updated_at'])
    log = (
        DiaryCorrectionRequestLog.objects.filter(diary=diary, granted_at__isnull=True)
        .order_by('-requested_at')
        .first()
    )
    if log:
        log.granted_at = now
        log.granted_by = request.user
        log.save(update_fields=['granted_at', 'granted_by'])
    else:
        DiaryCorrectionRequestLog.objects.create(
            diary=diary,
            requested_at=diary.edit_requested_at or now,
            requested_by=diary.edit_requested_by,
            note=diary.edit_request_note or '',
            granted_at=now,
            granted_by=request.user,
        )
    messages.success(
        request,
        f'Edição liberada para o relatório nº {diary.report_number or diary.pk} ({diary.project.code}).',
    )
    return redirect('central_diary_edit_requests')
