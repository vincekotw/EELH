"""
Generación de notificaciones in-app cuando un circuito vinculado
cambia de estado.
"""

import logging

from django.utils import timezone

from apps.usuarios.models import CircuitoUsuario, Notificacion


logger = logging.getLogger(__name__)


def notificar_cambio_circuito(circuito, tipo_evento: str, mensaje=None) -> int:
    """
    Crea notificaciones para todos los usuarios que tienen
    `circuito` vinculado.

    tipo_evento ∈ {'afectacion', 'restablecimiento'}
    Devuelve el número de notificaciones creadas.
    """
    if tipo_evento not in ('afectacion', 'restablecimiento'):
        return 0

    # Usuarios que tienen este circuito vinculado
    usuarios = (
        CircuitoUsuario.objects
        .filter(circuito=circuito)
        .select_related('user')
    )

    if not usuarios:
        return 0

    # Título y mensaje según tipo
    if tipo_evento == 'afectacion':
        titulo = f'⚡ {circuito.codigo} ha quedado sin servicio'
        cuerpo = (
            f'El circuito {circuito.codigo} ({circuito.municipio or "—"}) '
            f'acaba de ser reportado como afectado.'
        )
        enlace = f'/circuitos/c/{circuito.codigo}/'
    else:
        titulo = f'✅ {circuito.codigo} ha restablecido el servicio'
        cuerpo = (
            f'El circuito {circuito.codigo} ({circuito.municipio or "—"}) '
            f'ha recuperado el servicio eléctrico.'
        )
        enlace = f'/circuitos/c/{circuito.codigo}/'

    creadas = 0
    for cu in usuarios:
        # Evitar duplicados: si ya existe una notificación igual
        # para este usuario+circuito+tipo en las últimas 2h, no crear otra.
        from datetime import timedelta
        hace_2h = timezone.now() - timedelta(hours=2)
        existente = Notificacion.objects.filter(
            user=cu.user,
            circuito=circuito,
            tipo=tipo_evento,
            creado_en__gte=hace_2h,
        ).exists()
        if existente:
            continue

        Notificacion.objects.create(
            user=cu.user,
            circuito=circuito,
            tipo=tipo_evento,
            titulo=titulo,
            mensaje=cuerpo,
            enlace=enlace,
            dedup_key=f'{cu.user_id}:{circuito.id}:{tipo_evento}',
        )
        creadas += 1

    if creadas:
        logger.info(
            'Notificaciones creadas: %s para %s (%s)',
            creadas, circuito.codigo, tipo_evento,
        )

    return creadas