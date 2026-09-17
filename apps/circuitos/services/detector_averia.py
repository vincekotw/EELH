"""
Detecta ciclos de afectación a partir de los mensajes periódicos
de "Averías existentes hasta el momento".

Los circuitos que DESAPARECEN del listado entre un snapshot y el
siguiente se consideran restablecidos implícitamente.
"""

import logging
import re

from django.utils import timezone

from apps.circuitos.models import Circuito, EventoCircuito, SnapshotAverias


logger = logging.getLogger(__name__)


# Patrón para identificar los mensajes de averías
RE_AVERIAS_EXISTENTES = re.compile(
    r'Aver[íi]as\s+existentes\s+hasta\s+el\s+momento',
    re.IGNORECASE,
)


def es_mensaje_averias(texto: str) -> bool:
    """True si el mensaje es un listado de 'Averías existentes'."""
    if not texto:
        return False
    return bool(RE_AVERIAS_EXISTENTES.search(texto))


def procesar_snapshot_averias(mensaje) -> None:
    """
    Procesa un mensaje de 'Averías existentes':
      1. Compara con el snapshot anterior.
      2. Cierra ciclos de circuitos que desaparecieron (restablecimiento implícito).
      3. Registra el snapshot actual.
    """
    if not es_mensaje_averias(mensaje.texto):
        return

    # Evitar reprocesar el mismo mensaje
    if SnapshotAverias.objects.filter(mensaje=mensaje).exists():
        return

    circuitos_actuales = set(mensaje.circuitos_mencionados or [])

    # Buscar el snapshot anterior (por fecha, no por ID)
    snapshot_anterior = (
        SnapshotAverias.objects
        .filter(fecha__lt=mensaje.fecha)
        .order_by('-fecha')
        .first()
    )

    if snapshot_anterior:
        circuitos_anteriores = set(snapshot_anterior.circuitos_afectados)

        # ── Restablecimientos implícitos ──────────────────────
        restablecidos = circuitos_anteriores - circuitos_actuales
        for codigo in restablecidos:
            circuito = Circuito.objects.filter(codigo=codigo).first()
            if not circuito or not circuito.afectacion_activa:
                continue

            # Cerrar el ciclo de afectación
            from apps.circuitos.services.actualizador import _aplicar_restablecimiento
            _aplicar_restablecimiento(
                circuito,
                mensaje.fecha or timezone.now(),
                None,   # no hay hora de contenido específica
            )
            circuito.save()

            logger.info(
                'Restablecimiento implícito (desapareció del listado): %s '
                '(msg=%s)',
                codigo, mensaje.telegram_id,
            )

    # Registrar el snapshot actual
    SnapshotAverias.objects.create(
        mensaje=mensaje,
        fecha=mensaje.fecha or timezone.now(),
        circuitos_afectados=sorted(circuitos_actuales),
    )

    logger.info(
        'Snapshot registrado: %s circuitos (msg=%s)',
        len(circuitos_actuales), mensaje.telegram_id,
    )