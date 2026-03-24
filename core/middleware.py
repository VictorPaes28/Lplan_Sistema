"""
Custom middleware for security headers and cache control.
"""
from django.utils.deprecation import MiddlewareMixin


class ProxyHeadersMiddleware(MiddlewareMixin):
    """
    Em produção atrás de proxy (cPanel/Apache): se o Apache não enviar
    X-Forwarded-Proto, define com base em SITE_URL para Django tratar
    a requisição como HTTPS (cookies Secure, redirect, CSRF).
    Deve rodar antes do SecurityMiddleware.
    """
    def process_request(self, request):
        from django.conf import settings
        if getattr(settings, 'DEBUG', True):
            return None
        if request.META.get('HTTP_X_FORWARDED_PROTO'):
            return None
        site_url = getattr(settings, 'SITE_URL', '') or ''
        if not site_url.startswith('https://'):
            return None
        request.META['HTTP_X_FORWARDED_PROTO'] = 'https'
        return None


class ClearLegacyMessagesCookieMiddleware(MiddlewareMixin):
    """
    Remove cookie legado "messages" (usado por CookieStorage/FallbackStorage).
    Ajuda a recuperar rapidamente casos de header/cookie grande após mudanças
    para armazenamento de mensagens em sessão.
    """

    def process_response(self, request, response):
        if request.COOKIES.get('messages') is not None:
            response.delete_cookie('messages')
        return response


class SecurityHeadersMiddleware(MiddlewareMixin):
    """
    Middleware to add security headers and cache control.
    Replaces X-Frame-Options with Content-Security-Policy.
    """
    
    def process_response(self, request, response):
        # Não alterar respostas de arquivos estáticos/media (evita interferência no carregamento)
        if request.path.startswith(('/static/', '/media/')):
            return response
        # Remove X-XSS-Protection header (not needed in modern browsers)
        if 'X-XSS-Protection' in response:
            del response['X-XSS-Protection']
        
        # Add Content-Security-Policy header (replaces X-Frame-Options)
        if 'Content-Security-Policy' not in response:
            csp = (
                "default-src 'self'; "
                "script-src 'self' 'unsafe-inline' https://cdnjs.cloudflare.com https://cdn.jsdelivr.net https://unpkg.com; "
                "style-src 'self' 'unsafe-inline' https://cdnjs.cloudflare.com https://cdn.jsdelivr.net https://fonts.googleapis.com; "
                "connect-src 'self' https://cdn.jsdelivr.net https://cdnjs.cloudflare.com https://fonts.gstatic.com; "
                "img-src 'self' data: blob: https:; "
                "media-src 'self' blob: data: https:; "
                "font-src 'self' data: https://fonts.gstatic.com https://cdnjs.cloudflare.com https://cdn.jsdelivr.net; "
                "frame-ancestors 'self';"
            )
            response['Content-Security-Policy'] = csp
        
        # Add cache-control headers for static files
        if request.path.startswith('/static/'):
            # Static files should be cached for 1 year
            response['Cache-Control'] = 'public, max-age=31536000, immutable'
        elif request.path.startswith('/media/'):
            # Media files should be cached for 1 day
            response['Cache-Control'] = 'public, max-age=86400'
        elif not request.path.startswith('/admin/') and response.get('Content-Type', '').startswith('text/html'):
            # HTML pages should not be cached
            response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
            response['Pragma'] = 'no-cache'
            response['Expires'] = '0'
        
        return response

