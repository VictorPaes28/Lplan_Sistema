"""Token e estados de acesso ao portal público do candidato."""
from __future__ import annotations

import secrets
from datetime import timedelta

from django.utils import timezone

from recursos_humanos.models import Colaborador

# Admissão pode levar dias (exames, certidões); rotação a cada envio do RH reduz risco.
PORTAL_TOKEN_VALIDADE_DIAS = 7


def token_portal_vigente(colaborador: Colaborador) -> bool:
    """True se o colaborador já tem link de portal ainda dentro do prazo."""
    return bool(colaborador.token_portal) and colaborador.token_portal_valido()


def renovar_pin_portal_colaborador(colaborador: Colaborador) -> str:
    """Gera PIN novo para reenvio em notificações, sem alterar o link do portal."""
    from recursos_humanos.services.portal_auth import gerar_pin_portal, hash_pin_portal

    pin = gerar_pin_portal()
    colaborador.portal_pin_hash = hash_pin_portal(pin)
    colaborador.save(update_fields=['portal_pin_hash', 'atualizado_em'])
    return pin


def obter_ou_renovar_token_portal_colaborador(
    colaborador: Colaborador,
    *,
    reenviar_pin: bool = False,
) -> tuple[str, str | None]:
    """
    Mantém token e PIN se o link ainda estiver no prazo.
    Gera token e PIN novos se expirado ou inexistente.
    Com reenviar_pin=True e link vigente, mantém o token e gera PIN novo para a mensagem.
    Retorna (token, pin) — pin é None apenas quando o link permanece e reenviar_pin=False.
    """
    if token_portal_vigente(colaborador):
        if reenviar_pin:
            return colaborador.token_portal, renovar_pin_portal_colaborador(colaborador)
        return colaborador.token_portal, None
    return colaborador.gerar_token_portal(dias=PORTAL_TOKEN_VALIDADE_DIAS)


def renovar_token_portal_colaborador(
    colaborador: Colaborador,
    *,
    renovar_pin: bool = True,
) -> tuple[str, str | None]:
    """Gera token novo e invalida links anteriores. PIN só é rotacionado quando solicitado."""
    if renovar_pin:
        return colaborador.gerar_token_portal(dias=PORTAL_TOKEN_VALIDADE_DIAS)
    colaborador.token_portal = secrets.token_urlsafe(32)
    colaborador.token_portal_expira = timezone.now() + timedelta(days=PORTAL_TOKEN_VALIDADE_DIAS)
    colaborador.save(update_fields=['token_portal', 'token_portal_expira'])
    return colaborador.token_portal, None


def colaborador_por_token_portal(token: str) -> Colaborador | None:
    if not token:
        return None
    return Colaborador.objects.filter(token_portal=token).first()
