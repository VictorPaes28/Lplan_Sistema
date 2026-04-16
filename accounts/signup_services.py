import logging
import re
from datetime import datetime

from django.conf import settings
from django.contrib.auth.models import Group, User
from django.db import transaction
from django.core.mail import EmailMessage
from django.utils import timezone

from accounts.groups import GRUPOS, GRUPOS_OCULTOS_ATRIBUICAO_UI
from accounts.models import UserSignupRequest

logger = logging.getLogger(__name__)


def get_allowed_signup_domains():
    domains = getattr(settings, 'SIGNUP_ALLOWED_EMAIL_DOMAINS', []) or []
    return [str(d).strip().lower() for d in domains if str(d).strip()]


def is_allowed_signup_email(email):
    value = (email or '').strip().lower()
    if '@' not in value:
        return False
    domain = value.split('@')[-1]
    allowed = get_allowed_signup_domains()
    if not allowed:
        return True
    return domain in allowed


def get_signup_approver_users():
    """Retorna superusuários ativos para aprovação de cadastro."""
    return User.objects.filter(is_superuser=True, is_active=True).exclude(email='').order_by('id')


def _normalize_groups(group_names):
    allowed = set(GRUPOS.TODOS) - GRUPOS_OCULTOS_ATRIBUICAO_UI
    clean = []
    for name in group_names or []:
        value = (name or '').strip()
        if value and value in allowed and value not in clean:
            clean.append(value)
    return clean


def _normalize_project_ids(project_ids):
    out = []
    for pid in project_ids or []:
        try:
            value = int(pid)
        except (TypeError, ValueError):
            continue
        if value not in out:
            out.append(value)
    return out


def create_signup_request(*, full_name, email, username_suggestion='', notes='', requested_groups=None, requested_project_ids=None, origem='auto', requested_by=None):
    return UserSignupRequest.objects.create(
        full_name=(full_name or '').strip(),
        email=(email or '').strip().lower(),
        username_suggestion=(username_suggestion or '').strip(),
        notes=(notes or '').strip(),
        requested_groups=_normalize_groups(requested_groups),
        requested_project_ids=_normalize_project_ids(requested_project_ids),
        origem=origem,
        requested_by=requested_by,
    )


def notify_signup_request_created(signup_request):
    approvers = list(get_signup_approver_users())
    if not approvers:
        logger.warning('Nenhum superusuário ativo com e-mail para receber alertas de cadastro.')
        return

    # Notificação in-app (GestControll) para todos superusers
    for approver in approvers:
        try:
            from gestao_aprovacao.utils import criar_notificacao
            criar_notificacao(
                usuario=approver,
                tipo='pedido_criado',
                titulo='Nova solicitação de cadastro',
                mensagem=(
                    f'{signup_request.full_name} ({signup_request.email}) enviou uma solicitação '
                    f'de cadastro para aprovação.'
                ),
                work_order=None,
            )
        except Exception as exc:
            logger.warning('Falha ao criar notificação de solicitação de cadastro: %s', exc)

    # E-mail para aprovador
    site_url = (getattr(settings, 'SITE_URL', '') or '').rstrip('/')
    approval_url = f'{site_url}/central/cadastros/' if site_url else '/central/cadastros/'
    subject = 'Nova solicitação de cadastro pendente'
    body = (
        f'Olá,\n\n'
        f'Uma nova solicitação de cadastro foi registrada.\n\n'
        f'Nome: {signup_request.full_name}\n'
        f'E-mail: {signup_request.email}\n'
        f'Origem: {"Auto cadastro" if signup_request.origem == "auto" else "Cadastro interno"}\n\n'
        f'Acesse o painel para aprovar/rejeitar:\n{approval_url}\n\n'
        f'Mensagem automática do sistema LPLAN.'
    )
    from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', '') or getattr(settings, 'EMAIL_HOST_USER', '')
    for approver in approvers:
        try:
            msg = EmailMessage(subject=subject, body=body, from_email=from_email, to=[approver.email])
            msg.send(fail_silently=True)
        except Exception as exc:
            logger.warning('Falha ao enviar e-mail de solicitação de cadastro: %s', exc)


def build_unique_username(suggestion, email):
    raw = (suggestion or '').strip() or (email or '').split('@')[0].strip()
    raw = re.sub(r'[^a-zA-Z0-9.@_+-]', '.', raw).strip('.')
    base = raw[:150] or 'usuario'
    candidate = base
    suffix = 1
    while User.objects.filter(username=candidate).exists():
        tail = f'.{suffix}'
        candidate = f'{base[:150-len(tail)]}{tail}'
        suffix += 1
    return candidate


def build_default_password(first_name, last_name):
    """Senha padrão no formato usado na importação em lote."""
    ano = str(getattr(settings, 'SIGNUP_DEFAULT_PASSWORD_YEAR', datetime.now().year))
    f = (first_name or '').strip()
    l = (last_name or '').strip()
    ini_1 = f[0].upper() if f else 'X'
    ini_2 = l[0].lower() if l else 'x'
    return f'@#{ini_1}{ini_2}{ano}'


@transaction.atomic
def approve_signup_request(signup_request, approved_by, selected_groups=None, selected_project_ids=None):
    """Aprova solicitação pendente, cria usuário e vínculos de acesso."""
    if signup_request.status != UserSignupRequest.STATUS_PENDENTE:
        raise ValueError('A solicitação não está pendente.')

    from core.models import Project, ProjectMember
    from gestao_aprovacao.models import Obra, WorkOrderPermission, UserEmpresa, UserProfile
    from gestao_aprovacao.email_utils import enviar_email_credenciais_novo_usuario

    username = build_unique_username(signup_request.username_suggestion, signup_request.email)
    first_name = ''
    last_name = ''
    full_name = (signup_request.full_name or '').strip()
    if full_name:
        parts = full_name.split()
        first_name = parts[0]
        last_name = ' '.join(parts[1:]) if len(parts) > 1 else ''

    password = build_default_password(first_name, last_name)
    user = User.objects.create_user(
        username=username,
        email=signup_request.email,
        password=password,
        first_name=first_name,
        last_name=last_name,
    )

    requested_groups = _normalize_groups(selected_groups if selected_groups is not None else signup_request.requested_groups)
    for group_name in requested_groups:
        group = Group.objects.filter(name=group_name).first()
        if group:
            user.groups.add(group)

    requested_project_ids = _normalize_project_ids(
        selected_project_ids if selected_project_ids is not None else signup_request.requested_project_ids
    )
    active_projects = Project.objects.filter(pk__in=requested_project_ids, is_active=True)
    for project in active_projects:
        ProjectMember.objects.get_or_create(user=user, project=project)
        obra = Obra.objects.filter(project_id=project.id, ativo=True).first()
        if not obra:
            continue
        if GRUPOS.SOLICITANTE in requested_groups:
            WorkOrderPermission.objects.get_or_create(
                usuario=user,
                obra=obra,
                tipo_permissao='solicitante',
                defaults={'ativo': True},
            )
        if GRUPOS.APROVADOR in requested_groups:
            WorkOrderPermission.objects.get_or_create(
                usuario=user,
                obra=obra,
                tipo_permissao='aprovador',
                defaults={'ativo': True},
            )
        if obra.empresa_id:
            UserEmpresa.objects.update_or_create(
                usuario=user,
                empresa=obra.empresa,
                defaults={'ativo': True},
            )

    UserProfile.objects.get_or_create(usuario=user)

    signup_request.status = UserSignupRequest.STATUS_APROVADO
    signup_request.approved_by = approved_by
    signup_request.approved_user = user
    signup_request.approved_at = timezone.now()
    signup_request.rejected_at = None
    signup_request.rejection_reason = ''
    signup_request.save(
        update_fields=[
            'status',
            'approved_by',
            'approved_user',
            'approved_at',
            'rejected_at',
            'rejection_reason',
            'updated_at',
        ]
    )

    if user.email:
        try:
            site_url = getattr(settings, 'SITE_URL', '').rstrip('/')
            enviar_email_credenciais_novo_usuario(
                email_destino=user.email,
                username=user.username,
                senha_plana=password,
                nome_completo=user.get_full_name() or user.username,
                site_url=site_url,
            )
        except Exception as exc:
            logger.warning('Falha ao enviar e-mail de credenciais para usuário aprovado: %s', exc)
    return user
