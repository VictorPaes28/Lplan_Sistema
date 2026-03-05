"""
Middleware CSRF que aceita a origem da própria requisição quando o host
está em ALLOWED_HOSTS. Resolve 403 "Sessão inválida" no cPanel quando
o Apache não envia X-Forwarded-Proto/Host ou CSRF_TRUSTED_ORIGINS está vazio.
"""
from urllib.parse import urlsplit

from django.conf import settings
from django.utils.http import is_same_domain

# Importar do Django para estender
from django.middleware.csrf import (
    REASON_BAD_ORIGIN,
    REASON_BAD_REFERER,
    REASON_INSECURE_REFERER,
    REASON_MALFORMED_REFERER,
    REASON_NO_REFERER,
    RejectRequest,
)
from django.middleware.csrf import CsrfViewMiddleware as DjangoCsrfViewMiddleware


def _origin_host_allowed(origin, allowed_hosts):
    """True se o host da origem (scheme + netloc) está em ALLOWED_HOSTS."""
    if not origin or not allowed_hosts:
        return False
    try:
        parsed = urlsplit(origin)
    except ValueError:
        return False
    if "" in (parsed.scheme, parsed.netloc):
        return False
    host = parsed.netloc.split(":")[0]  # sem porta
    return any(is_same_domain(host, h) for h in allowed_hosts if h and h != "*")


class CsrfViewMiddleware(DjangoCsrfViewMiddleware):
    """
    Estende o CSRF do Django: além de CSRF_TRUSTED_ORIGINS, aceita origem/referer
    quando o host está em ALLOWED_HOSTS (útil atrás de proxy sem headers).
    """

    def _origin_verified(self, request):
        if not self._origin_verified_django(request):
            request_origin = request.META.get("HTTP_ORIGIN", "")
            if _origin_host_allowed(request_origin, settings.ALLOWED_HOSTS):
                return True
            return False
        return True

    def _origin_verified_django(self, request):
        """Lógica original do Django (chamada em ordem)."""
        request_origin = request.META.get("HTTP_ORIGIN")
        if not request_origin:
            return False
        try:
            good_host = request.get_host()
        except Exception:
            pass
        else:
            good_origin = "%s://%s" % (
                "https" if request.is_secure() else "http",
                good_host,
            )
            if request_origin == good_origin:
                return True
        if request_origin in self.allowed_origins_exact:
            return True
        try:
            parsed_origin = urlsplit(request_origin)
        except ValueError:
            return False
        parsed_origin_scheme = parsed_origin.scheme
        parsed_origin_netloc = parsed_origin.netloc
        return any(
            is_same_domain(parsed_origin_netloc, host)
            for host in self.allowed_origin_subdomains.get(parsed_origin_scheme, ())
        )

    def _check_referer(self, request):
        referer = request.META.get("HTTP_REFERER")
        if referer is None:
            raise RejectRequest(REASON_NO_REFERER)

        try:
            referer_parsed = urlsplit(referer)
        except ValueError:
            raise RejectRequest(REASON_MALFORMED_REFERER)

        if "" in (referer_parsed.scheme, referer_parsed.netloc):
            raise RejectRequest(REASON_MALFORMED_REFERER)

        if referer_parsed.scheme != "https":
            raise RejectRequest(REASON_INSECURE_REFERER)

        # Primeiro tenta a lógica padrão (trusted origins / get_host())
        try:
            self._check_referer_django(request)
            return
        except RejectRequest:
            pass

        # Fallback: aceitar se o host do Referer está em ALLOWED_HOSTS
        if _origin_host_allowed(referer, settings.ALLOWED_HOSTS):
            return
        raise RejectRequest(REASON_BAD_REFERER % referer)

    def _check_referer_django(self, request):
        """Lógica original do Django para referer."""
        referer = request.META.get("HTTP_REFERER")
        if referer is None:
            raise RejectRequest(REASON_NO_REFERER)

        try:
            referer = urlsplit(referer)
        except ValueError:
            raise RejectRequest(REASON_MALFORMED_REFERER)

        if "" in (referer.scheme, referer.netloc):
            raise RejectRequest(REASON_MALFORMED_REFERER)

        if referer.scheme != "https":
            raise RejectRequest(REASON_INSECURE_REFERER)

        if any(
            is_same_domain(referer.netloc, host)
            for host in self.csrf_trusted_origins_hosts
        ):
            return

        good_referer = (
            settings.SESSION_COOKIE_DOMAIN
            if getattr(settings, "CSRF_USE_SESSIONS", False)
            else settings.CSRF_COOKIE_DOMAIN
        )
        if good_referer is None:
            try:
                good_referer = request.get_host()
            except Exception:
                raise RejectRequest(REASON_BAD_REFERER % referer.geturl())
        else:
            server_port = request.get_port()
            if server_port not in ("443", "80"):
                good_referer = "%s:%s" % (good_referer, server_port)

        if not is_same_domain(referer.netloc, good_referer):
            raise RejectRequest(REASON_BAD_REFERER % referer.geturl())
