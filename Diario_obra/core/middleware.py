"""
Custom middleware for security headers and cache control.
"""
from django.utils.deprecation import MiddlewareMixin


class SecurityHeadersMiddleware(MiddlewareMixin):
    """
    Middleware to add security headers and cache control.
    Replaces X-Frame-Options with Content-Security-Policy.
    """
    
    def process_response(self, request, response):
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

