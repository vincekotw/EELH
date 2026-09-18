"""
Envío de notificaciones Web Push.

Usa pywebpush para enviar a los endpoints de los navegadores
suscritos. Las suscripciones se guardan en PushSubscription.
"""

import json
import logging

from django.conf import settings
from django.utils import timezone

from apps.usuarios.models import Notificacion, PushSubscription, NotificacionPush


logger = logging.getLogger(__name__)


# ── Configuración ────────────────────────────────────────────
def _webpush_disponible() -> bool:
    """Comprueba si pywebpush está instalado y configurado."""
    try:
        from pywebpush import webpush  # noqa
    except ImportError:
        return False

    cfg = getattr(settings, 'WEBPUSH_SETTINGS', {})
    return bool(cfg.get('VAPID_PRIVATE_KEY') and cfg.get('VAPID_PUBLIC_KEY'))


# ── Envío individual ─────────────────────────────────────────
def _enviar_a_suscripcion(sub, titulo, cuerpo, url='', dedup_key=''):
    """
    Envía un push a una suscripción específica.
    Devuelve True si tuvo éxito, False si falló.
    """
    from pywebpush import webpush, WebPushException

    payload = json.dumps({
        'titulo': titulo,
        'cuerpo': cuerpo,
        'url': url or '/circuitos/',
    })

    cfg = settings.WEBPUSH_SETTINGS

    try:
        webpush(
            subscription_info={
                'endpoint': sub.endpoint,
                'keys': {
                    'p256dh': sub.p256dh,
                    'auth': sub.auth,
                },
            },
            data=payload,
            vapid_private_key=cfg['VAPID_PRIVATE_KEY'],
            vapid_claims={
                'sub': f"mailto:{cfg['VAPID_ADMIN_EMAIL']}",
            },
        )

        sub.ultimo_uso = timezone.now()
        sub.save(update_fields=['ultimo_uso'])

        NotificacionPush.objects.create(
            suscripcion=sub,
            titulo=titulo,
            cuerpo=cuerpo,
            url=url,
            exito=True,
            dedup_key=dedup_key,
        )
        return True

    except WebPushException as e:
        # 404/410 → suscripción expirada, borrarla
        if e.response is not None and e.response.status_code in (404, 410):
            logger.info('Eliminando suscripción expirada: %s', sub.endpoint[:60])
            sub.delete()
            return False

        NotificacionPush.objects.create(
            suscripcion=sub,
            titulo=titulo,
            cuerpo=cuerpo,
            url=url,
            exito=False,
            error=str(e),
            dedup_key=dedup_key,
        )
        logger.warning('Push falló para %s: %s', sub.endpoint[:60], e)
        return False

    except Exception as e:
        logger.exception('Error inesperado en push: %s', e)
        return False


# ── Envío a un usuario ───────────────────────────────────────
def enviar_a_usuario(user, titulo, cuerpo, url='', dedup_key=''):
    """
    Envía push a todas las suscripciones activas de un usuario.
    Devuelve el número de envíos exitosos.
    """
    if not _webpush_disponible():
        return 0

    subs = PushSubscription.objects.filter(user=user)
    exitos = 0
    for sub in subs:
        if _enviar_a_suscripcion(sub, titulo, cuerpo, url, dedup_key):
            exitos += 1
    return exitos


# ── Cola de pendientes (llamada desde cron_tick) ─────────────
def enviar_pendientes():
    """
    Procesa las notificaciones in-app no enviadas aún por push.
    Se llama desde el endpoint /api/cron/tick/ cada 5 min.

    Devuelve el número de pushes enviados.
    """
    if not _webpush_disponible():
        return 0

    # Notificaciones de los últimos 10 min que no se hayan enviado ya por push
    hace_10min = timezone.now() - timezone.timedelta(minutes=10)

    notifs = (
        Notificacion.objects
        .filter(
            creado_en__gte=hace_10min,
            leida=False,
        )
        .select_related('user', 'circuito')
    )

    enviados = 0
    for n in notifs:
        # Verificar si ya se envió push para esta notificación
        dedup_key = f'notif:{n.id}'
        if NotificacionPush.objects.filter(dedup_key=dedup_key).exists():
            continue

        url = n.enlace or (f'/circuitos/c/{n.circuito.codigo}/' if n.circuito else '/circuitos/')

        enviados += enviar_a_usuario(
            user=n.user,
            titulo=n.titulo,
            cuerpo=n.mensaje or '',
            url=url,
            dedup_key=dedup_key,
        )

    if enviados:
        logger.info('Pushes enviados: %s', enviados)

    return enviados