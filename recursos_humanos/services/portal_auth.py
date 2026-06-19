"""Autenticação por PIN na sessão do portal público do candidato."""
from __future__ import annotations

import secrets
from datetime import timedelta

from django.contrib.auth.hashers import check_password, make_password
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from recursos_humanos.models import Colaborador

PORTAL_SESSION_KEY = 'rh_portal_auth'
PORTAL_TENTATIVAS_KEY = 'rh_portal_pin_tentativas'
PORTAL_EXPIRED_KEY_PREFIX = 'rh_portal_expired_'
PORTAL_MAX_TENTATIVAS_PIN = 5
PORTAL_AUTH_TTL_MINUTES = 10


def gerar_pin_portal() -> str:
    return f'{secrets.randbelow(10 ** 6):06d}'


def hash_pin_portal(pin: str) -> str:
    return make_password(pin.strip())


def portal_exige_pin(colaborador: Colaborador) -> bool:
    return bool(colaborador.portal_pin_hash)


def _auth_timestamp_valido(iso_str: str) -> bool:
    dt = parse_datetime(iso_str)
    if dt is None:
        return False
    if timezone.is_naive(dt):
        dt = timezone.make_aware(dt, timezone.get_current_timezone())
    return timezone.now() - dt < timedelta(minutes=PORTAL_AUTH_TTL_MINUTES)


def _marcar_aviso_sessao_expirada(request, token: str) -> None:
    request.session[f'{PORTAL_EXPIRED_KEY_PREFIX}{token}'] = True
    request.session.modified = True


def consumir_aviso_sessao_expirada(request, token: str) -> bool:
    key = f'{PORTAL_EXPIRED_KEY_PREFIX}{token}'
    if request.session.pop(key, None):
        request.session.modified = True
        return True
    return False


def portal_esta_autenticado(request, token: str, colaborador: Colaborador) -> bool:
    if not portal_exige_pin(colaborador):
        return True
    auth = request.session.get(PORTAL_SESSION_KEY) or {}
    iso_str = auth.get(token)
    if not iso_str:
        return False
    if not _auth_timestamp_valido(iso_str):
        limpar_portal_autenticado(request, token)
        _marcar_aviso_sessao_expirada(request, token)
        return False
    return True


def marcar_portal_autenticado(request, token: str) -> None:
    auth = dict(request.session.get(PORTAL_SESSION_KEY) or {})
    auth[token] = timezone.now().isoformat()
    request.session[PORTAL_SESSION_KEY] = auth
    request.session.modified = True
    _limpar_tentativas_pin(request, token)


def limpar_portal_autenticado(request, token: str) -> None:
    auth = dict(request.session.get(PORTAL_SESSION_KEY) or {})
    auth.pop(token, None)
    request.session[PORTAL_SESSION_KEY] = auth
    request.session.modified = True


def _tentativas_pin(request, token: str) -> int:
    data = request.session.get(PORTAL_TENTATIVAS_KEY) or {}
    return int(data.get(token) or 0)


def _incrementar_tentativas_pin(request, token: str) -> int:
    data = dict(request.session.get(PORTAL_TENTATIVAS_KEY) or {})
    data[token] = int(data.get(token) or 0) + 1
    request.session[PORTAL_TENTATIVAS_KEY] = data
    request.session.modified = True
    return data[token]


def _limpar_tentativas_pin(request, token: str) -> None:
    data = dict(request.session.get(PORTAL_TENTATIVAS_KEY) or {})
    data.pop(token, None)
    request.session[PORTAL_TENTATIVAS_KEY] = data
    request.session.modified = True


def pin_bloqueado(request, token: str) -> bool:
    return _tentativas_pin(request, token) >= PORTAL_MAX_TENTATIVAS_PIN


def verificar_pin_portal(colaborador: Colaborador, pin: str) -> bool:
    if not colaborador.portal_pin_hash:
        return True
    pin = (pin or '').strip()
    if len(pin) != 6 or not pin.isdigit():
        return False
    return check_password(pin, colaborador.portal_pin_hash)


def autenticar_portal(request, token: str, colaborador: Colaborador, pin: str, declaracao: bool) -> tuple[bool, str]:
    if not declaracao:
        return False, 'Marque a declaração para continuar.'
    if pin_bloqueado(request, token):
        return False, (
            f'Muitas tentativas incorretas. Aguarde e use o código enviado por e-mail '
            f'ou solicite um novo link ao RH.'
        )
    if not verificar_pin_portal(colaborador, pin):
        restantes = PORTAL_MAX_TENTATIVAS_PIN - _incrementar_tentativas_pin(request, token)
        if restantes <= 0:
            return False, 'Código incorreto. Número máximo de tentativas atingido.'
        return False, f'Código de acesso incorreto. Restam {restantes} tentativa(s).'
    marcar_portal_autenticado(request, token)
    return True, ''


def exigir_portal_autenticado(request, token: str, colaborador: Colaborador):
    """Redireciona para a tela de acesso se o PIN ainda não foi validado na sessão."""
    from django.shortcuts import redirect

    if portal_esta_autenticado(request, token, colaborador):
        return None
    return redirect('recursos_humanos:portal', token=token)
