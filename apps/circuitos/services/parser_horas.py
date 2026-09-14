"""
Extrae horas del contenido de los mensajes de la Empresa Eléctrica.

Formatos soportados:
    1. Formato estándar EELH (con AM/PM):
       "a partir de las 2:47 PM se afectó"
       "a partir de las 03:20 pm quedó restablecido"
       "a partir de las 3 :23 am se afectó"     (espacio antes de :)
       "Siendo las 04:20 PM se afectan"
       "11:47 AM queda restablecido"

    2. Formato UNE (24h, al inicio del mensaje):
       "20:50 || En línea la Unidad 1 de Felton"
       "17:46 fuera de línea la Unidad 1 de Felton"
       "23:50 || En línea la Unidad 3"

El resultado es siempre un datetime aware en UTC.

NOTA: los regex usan \\w en lugar de vocales acentuadas literales
para evitar problemas de encoding al compartir el archivo entre
editores/SOs distintos.
"""

import re
from datetime import datetime, timedelta, timezone


# Zona horaria de Cuba. En verano (mayo-oct) es UTC-4, en invierno UTC-5.
# Usamos UTC-4 por defecto. Si se necesita precisión estacional, se puede
# derivar con dateutil.tz o una tabla de cambio de horario.
OFFSET_CUBA = timedelta(hours=-4)
TZ_CUBA = timezone(OFFSET_CUBA)


# ── Patrón 1: hora con AM/PM ──────────────────────────────────
RE_HORA_AMPM = re.compile(
    r'(\d{1,2})\s*:\s*(\d{2})\s*(AM|PM|am|pm|a\.m\.|p\.m\.|A\.M\.|P\.M\.)',
    re.IGNORECASE,
)

# ── Patrón 2: hora 24h al inicio del mensaje (formato UNE) ────
# Coincide con "HH:MM ||", "HH:MM fuera", "HH:MM en línea", "HH:MM en servicio".
# Solo cuando está al principio (primeros caracteres del texto limpio).
RE_HORA_UNE_INICIO = re.compile(
    r'^\s*(\d{1,2})\s*:\s*(\d{2})\s*(?:\|\||fuera|en\s+l\w+nea|en\s+servicio)',
    re.IGNORECASE,
)


def _construir_datetime(
    fecha_msg: datetime,
    hora: int,
    minuto: int,
) -> datetime | None:
    """
    Combina la fecha del mensaje con la hora/minuto dados.
    Asume zona horaria de Cuba, devuelve UTC.

    Ajusta al día anterior si la hora interpretada queda más de 6 horas
    en el futuro respecto al mensaje (típico en mensajes publicados poco
    después de medianoche sobre eventos de la noche anterior).
    """
    if not (0 <= hora <= 23 and 0 <= minuto <= 59):
        return None

    fecha_cuba = fecha_msg.astimezone(TZ_CUBA)
    candidato = datetime(
        fecha_cuba.year, fecha_cuba.month, fecha_cuba.day,
        hora, minuto, tzinfo=TZ_CUBA,
    )

    # Margen de 6 horas: si el candidato queda muy adelantado, es del día previo.
    if candidato > fecha_cuba + timedelta(hours=6):
        candidato -= timedelta(days=1)

    return candidato.astimezone(timezone.utc)


def _normalizar_ampm(hora: int, sufijo: str) -> int | None:
    """Convierte hora de 12h con AM/PM a formato 24h."""
    sufijo = sufijo.lower().replace('.', '').strip()
    if sufijo == 'pm':
        return hora if hora == 12 else hora + 12
    if sufijo == 'am':
        return 0 if hora == 12 else hora
    return None


def parsear_hora_contenido(
    texto: str,
    fecha_msg: datetime,
) -> datetime | None:
    """
    Devuelve un datetime aware (UTC) con la hora mencionada en el texto.
    Si el mensaje no contiene hora interpretable, devuelve None.

    `fecha_msg` se usa solo para extraer el día/mes/año.
    """
    if not texto or not fecha_msg:
        return None

    # ── Intento 1: formato UNE al inicio ─────────────────────
    m_une = RE_HORA_UNE_INICIO.match(texto)
    if m_une:
        try:
            hora = int(m_une.group(1))
            minuto = int(m_une.group(2))
        except (ValueError, IndexError):
            hora, minuto = -1, -1
        resultado = _construir_datetime(fecha_msg, hora, minuto)
        if resultado:
            return resultado

    # ── Intento 2: formato EELH con AM/PM ────────────────────
    m = RE_HORA_AMPM.search(texto)
    if not m:
        return None

    try:
        hora12 = int(m.group(1))
        minuto = int(m.group(2))
        sufijo = m.group(3)
    except (ValueError, IndexError):
        return None

    if not (1 <= hora12 <= 12):
        return None

    hora24 = _normalizar_ampm(hora12, sufijo)
    if hora24 is None:
        return None

    return _construir_datetime(fecha_msg, hora24, minuto)