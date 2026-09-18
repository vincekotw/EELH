"""
Middleware que registra cada request de un usuario autenticado
en el modelo NavegacionLog. Excluye:
  - Peticiones a static/media
  - Peticiones AJAX de los endpoints de métricas (para no inflar)
  - Peticiones al admin (opcional)
"""

import hashlib
import logging

from .models import NavegacionLog


logger = logging.getLogger(__name__)


EXCLUIR_PREFIJOS = [
    '/static/',
    '/media/',
    '/admin/',
    '/favicon.ico',
    '/api/cron/',
]


class TrackingMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        # Solo registrar usuarios autenticados
        if not request.user.is_authenticated:
            return response

        # Excluir prefijos
        path = request.path
        if any(path.startswith(p) for p in EXCLUIR_PREFIJOS):
            return response

        # Excluir AJAX de métricas (opcional)
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return response

        try:
            ip = self._obtener_ip(request)
            ip_hash = hashlib.sha256(
                f'{ip}:nav_log_v1'.encode()
            ).hexdigest()[:32] if ip else ''

            NavegacionLog.objects.create(
                user=request.user,
                path=path[:300],
                metodo=request.method,
                ip_hash=ip_hash,
                user_agent=request.META.get('HTTP_USER_AGENT', '')[:255],
                referrer=request.META.get('HTTP_REFERER', '')[:300],
            )
        except Exception:
            logger.exception('Error guardando NavegacionLog')

        return response

    @staticmethod
    def _obtener_ip(request) -> str:
        xff = request.META.get('HTTP_X_FORWARDED_FOR', '')
        if xff:
            return xff.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR', '')