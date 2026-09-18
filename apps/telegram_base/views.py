"""
Endpoints para cron externo. Protegidos por token.
Se llaman desde cron-job.org cada 5 minutos en producción.
"""

from datetime import timedelta

from django.conf import settings
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from .models import EstadoScraper, ScrapeRun


# ── Configuración ────────────────────────────────────────────
UMBRAL_MINUTOS_SCRAPE = 4       # si pasaron >4 min, correr scrape


def _validar_token(request) -> bool:
    """Verifica el token del cron."""
    token_secreto = getattr(settings, 'CRON_TOKEN', '')
    if not token_secreto:
        return False

    token = (
        request.headers.get('X-Cron-Token')
        or request.GET.get('token')
    )
    return token == token_secreto


@csrf_exempt
@require_http_methods(['GET', 'POST'])
def cron_tick(request):
    """
    Endpoint llamado cada 5 min por cron-job.org.
    Mantiene el servicio despierto y ejecuta tareas periódicas.
    """
    if not _validar_token(request):
        return JsonResponse({'error': 'unauthorized'}, status=401)

    from django.core.management import call_command

    resultado = {
        'timestamp': timezone.now().isoformat(),
        'scrape_ejecutado': False,
        'recalculo_ejecutado': False,
        'errores': [],
    }

    # ── 1. ¿Hay que scrapear? ────────────────────────────────
    estado = EstadoScraper.get_solo()
    ultimo_scrape = estado.ultimo_scrape

    debe_scrapear = (
        ultimo_scrape is None
        or (timezone.now() - ultimo_scrape) > timedelta(minutes=UMBRAL_MINUTOS_SCRAPE)
    )

    if debe_scrapear:
        try:
            call_command('scrape_telegram')
            resultado['scrape_ejecutado'] = True
        except Exception as e:
            resultado['errores'].append(f'scrape: {e}')

    # ── 2. Recalcular ciclos abiertos siempre ────────────────
    try:
        from apps.circuitos.services.actualizador import recalcular_abiertos
        recalcular_abiertos()
        resultado['recalculo_ejecutado'] = True
    except Exception as e:
        resultado['errores'].append(f'recalculo: {e}')

    # ── 3. Enviar notificaciones push pendientes ─────────────
    try:
        from apps.usuarios.services.push import enviar_pendientes
        enviadas = enviar_pendientes()
        resultado['push_enviadas'] = enviadas
    except ImportError:
        # Push aún no implementado, ignorar
        pass
    except Exception as e:
        resultado['errores'].append(f'push: {e}')

    resultado['ok'] = len(resultado['errores']) == 0
    return JsonResponse(resultado)