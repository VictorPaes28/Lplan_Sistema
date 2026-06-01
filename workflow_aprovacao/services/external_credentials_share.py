"""Mensagem e link WhatsApp com credenciais de acesso para terceirizados externos."""
from __future__ import annotations

from urllib.parse import quote

from django.conf import settings
from django.urls import reverse

from accounts.signup_services import build_default_password
from workflow_aprovacao.services.notifications import _normalize_phone


def _login_site_url(*, request=None) -> str:
    if request is not None:
        try:
            return request.build_absolute_uri(reverse('login')).rstrip('/')
        except Exception:
            pass
    return (getattr(settings, 'SITE_URL', None) or '').rstrip('/') or 'http://127.0.0.1:8001'


def _password_for_created_external(full_name: str) -> str:
    parts = (full_name or '').strip().split()
    first_name = parts[0] if parts else ''
    last_name = ' '.join(parts[1:]) if len(parts) > 1 else ''
    return build_default_password(first_name, last_name)


def build_external_credentials_message(
    *,
    signup_request,
    login_url: str,
    process_access_url: str,
) -> str:
    """Monta texto com login e link do pedido para compartilhar com o terceirizado."""
    name = (signup_request.full_name or '').strip() or 'terceirizado'
    username = ''
    if signup_request.linked_user_id:
        username = (signup_request.linked_user.username or '').strip()

    lines = [
        f'Olá, {name}!',
        '',
        'Seu acesso à Central de Aprovações Lplan foi liberado.',
        '',
    ]
    if signup_request.created_linked_user and username:
        password = _password_for_created_external(signup_request.full_name)
        lines.extend(
            [
                f'Link de login: {login_url}',
                f'Usuário: {username}',
                f'Senha temporária: {password}',
                '',
                'Recomendamos alterar a senha no primeiro acesso.',
                '',
            ]
        )
    elif username:
        lines.extend(
            [
                f'Use seu login existente em: {login_url}',
                f'Usuário: {username}',
                '',
            ]
        )
    else:
        lines.extend(
            [
                f'Acesse com seu login Lplan: {login_url}',
                '',
            ]
        )

    lines.extend(
        [
            f'Pedido para assinar: {process_access_url}',
            f'Obra: {signup_request.process.project.code}',
        ]
    )
    return '\n'.join(lines)


def build_central_signup_credentials_message(*, signup_request, login_url: str, process_access_url: str = '') -> str:
    """Mensagem de login para solicitação aprovada na Central de Cadastros (sem pedido workflow)."""
    name = (signup_request.full_name or '').strip() or 'terceirizado'
    user = signup_request.approved_user
    username = (user.username or '').strip() if user else ''

    lines = [
        f'Olá, {name}!',
        '',
        'Seu acesso ao sistema Lplan foi liberado.',
        '',
    ]
    if username:
        if signup_request.password_hash:
            lines.extend(
                [
                    f'Link de login: {login_url}',
                    f'Usuário: {username}',
                    '',
                    'Use a senha que você definiu ao enviar a solicitação de cadastro.',
                    '',
                ]
            )
        else:
            password = _password_for_created_external(signup_request.full_name)
            lines.extend(
                [
                    f'Link de login: {login_url}',
                    f'Usuário: {username}',
                    f'Senha temporária: {password}',
                    '',
                    'Recomendamos alterar a senha no primeiro acesso.',
                    '',
                ]
            )
    else:
        lines.extend([f'Acesse: {login_url}', ''])

    if process_access_url:
        lines.append(f'Pedido para assinar: {process_access_url}')
    return '\n'.join(lines)


def _whatsapp_url_from_message(*, phone: str, message: str) -> str:
    normalized = _normalize_phone(phone or '')
    if len(normalized) >= 10:
        if not normalized.startswith('55'):
            normalized = f'55{normalized}'
        return f'https://wa.me/{normalized}?text={quote(message)}'
    return f'https://wa.me/?text={quote(message)}'


def build_central_signup_whatsapp_url(*, request, signup_request) -> str:
    """WhatsApp para solicitação aprovada na Central de Cadastros."""
    from accounts.models import UserSignupRequest
    from workflow_aprovacao.models import ExternalSignupStatus

    if signup_request.status != UserSignupRequest.STATUS_APROVADO:
        return ''
    if not signup_request.approved_user_id:
        return ''

    wf = getattr(signup_request, 'workflow_external_signup', None)
    if wf and wf.status == ExternalSignupStatus.APPROVED and wf.linked_user_id:
        return build_external_credentials_whatsapp_url(request=request, signup_request=wf)

    login_url = _login_site_url(request=request)
    phone = signup_request.phone or ''
    message = build_central_signup_credentials_message(
        signup_request=signup_request,
        login_url=login_url,
    )
    return _whatsapp_url_from_message(phone=phone, message=message)


def build_external_credentials_whatsapp_url(*, request, signup_request) -> str:
    """URL wa.me com mensagem pré-preenchida (com telefone quando informado)."""
    login_url = _login_site_url(request=request)
    process_path = reverse('workflow_aprovacao:process_detail', kwargs={'pk': signup_request.process_id})
    process_access_url = request.build_absolute_uri(process_path)
    message = build_external_credentials_message(
        signup_request=signup_request,
        login_url=login_url,
        process_access_url=process_access_url,
    )
    return _whatsapp_url_from_message(phone=signup_request.phone_whatsapp or '', message=message)
