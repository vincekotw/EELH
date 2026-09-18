"""
Parser de mensajes DAF (Disparo Automático por Frecuencia).

Detecta mensajes del tipo:
    "⚡ 📣 Informamos a los clientes de la capital que los circuitos
    protegidos por Disparo Automático por Frecuencia (DAF) serán
    rotados cada viernes...
    🛑 DAF: desde el viernes 11 hasta el jueves 17 de septiembre
    📌 Playa 👉 A1218:...
    ..."

Extrae:
  - Rango de fechas (desde/hasta)
  - Lista de circuitos DAF
  - Crea registros en CircuitoDAF (marcando como inactivos los anteriores)
"""

import re
import logging
from datetime import datetime, date

from django.utils import timezone

from apps.circuitos.models import Circuito, CircuitoDAF


logger = logging.getLogger(__name__)


# ── Patrones ─────────────────────────────────────────────────
RE_MENSAJE_DAF = re.compile(
    r'Disparo\s+Autom[áa]tico\s+por\s+Frecuencia|DAF',
    re.IGNORECASE,
)

RE_RANGO_FECHAS = re.compile(
    r'DAF:\s*desde\s+el\s+(\w+)\s+(\d{1,2})\s+hasta\s+el\s+(\w+)\s+(\d{1,2})\s+de\s+(\w+)',
    re.IGNORECASE,
)

RE_CIRCUITO = re.compile(
    r'👉\s*([A-Z]{0,4}-?\d{1,5})\s*:',
    re.IGNORECASE,
)

MESES_ES = {
    'enero': 1, 'febrero': 2, 'marzo': 3, 'abril': 4,
    'mayo': 5, 'junio': 6, 'julio': 7, 'agosto': 8,
    'septiembre': 9, 'octubre': 10, 'noviembre': 11, 'diciembre': 12,
}


def es_mensaje_daf(texto: str) -> bool:
    """True si el mensaje es una rotación DAF."""
    if not texto:
        return False
    return bool(
        RE_MENSAJE_DAF.search(texto)
        and RE_RANGO_FECHAS.search(texto)
    )


def extraer_rango_daf(texto: str) -> tuple[date, date] | None:
    """
    Extrae el rango de fechas del mensaje.
    Devuelve (desde, hasta) como date objects, o None si no se encuentra.
    """
    m = RE_RANGO_FECHAS.search(texto)
    if not m:
        return None

    try:
        dia_desde = int(m.group(2))
        dia_hasta = int(m.group(4))
        mes_nombre = m.group(5).lower()
        mes = MESES_ES.get(mes_nombre)
        if not mes:
            return None

        # Año actual (asumimos que el mensaje es del año en curso)
        anio = timezone.now().year
        desde = date(anio, mes, dia_desde)
        hasta = date(anio, mes, dia_hasta)

        # Si el rango cruza de mes (ej: desde 28 marzo hasta 3 abril)
        if hasta < desde:
            # Ajustar al siguiente mes
            if mes == 12:
                hasta = date(anio + 1, 1, dia_hasta)
            else:
                hasta = date(anio, mes + 1, dia_hasta)

        return desde, hasta
    except (ValueError, IndexError):
        return None


def extraer_circuitos_daf(texto: str) -> list[str]:
    """Extrae los circuitos mencionados en el mensaje DAF."""
    if not texto:
        return []

    circuitos = RE_CIRCUITO.findall(texto)
    normalizados = []
    vistos = set()
    for c in circuitos:
        c_upper = c.upper().strip()
        if c_upper not in vistos:
            vistos.add(c_upper)
            normalizados.append(c_upper)
    return normalizados


def procesar_mensaje_daf(mensaje) -> None:
    """
    Procesa un mensaje DAF:
      1. Extrae el rango de fechas.
      2. Extrae los circuitos.
      3. Desactiva los DAF vigentes anteriores.
      4. Crea los nuevos registros CircuitoDAF.
    """
    if not es_mensaje_daf(mensaje.texto):
        return

    rango = extraer_rango_daf(mensaje.texto)
    if not rango:
        logger.warning('No se pudo extraer el rango de fechas DAF (msg=%s)', mensaje.telegram_id)
        return

    desde, hasta = rango
    circuitos_codigos = extraer_circuitos_daf(mensaje.texto)
    if not circuitos_codigos:
        logger.warning('No se encontraron circuitos DAF (msg=%s)', mensaje.telegram_id)
        return

    # Desactivar los DAF vigentes anteriores
    CircuitoDAF.objects.filter(activo=True).update(activo=False)

    # Crear nuevos registros
    creados = 0
    for codigo in circuitos_codigos:
        circuito = Circuito.objects.filter(codigo__iexact=codigo).first()
        if not circuito:
            logger.warning('Circuito DAF no encontrado: %s', codigo)
            continue

        CircuitoDAF.objects.create(
            circuito=circuito,
            desde=desde,
            hasta=hasta,
            mensaje_origen=mensaje,
            activo=True,
        )
        creados += 1

    logger.info(
        'DAF actualizado: %s circuitos (%s → %s) desde msg=%s',
        creados, desde, hasta, mensaje.telegram_id,
    )