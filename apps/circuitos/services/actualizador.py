"""
Aplica un mensaje de Telegram sobre los circuitos mencionados.
Actualiza estado, ciclos de afectación/servicio y estadísticas.

Detecta mensajes de rotación APOLO en sus múltiples formatos y
asigna cada circuito al bloque correcto (afectado / en servicio).

NOTA: los regex usan \\w en lugar de vocales acentuadas literales
para evitar problemas de encoding.
"""

import re
from datetime import datetime, timezone

from django.db import models, transaction

from apps.circuitos.models import Circuito, EventoCircuito
from apps.circuitos.services.parser_horas import parsear_hora_contenido
from apps.telegram_base.models import Mensaje


# ── Detección de rotación APOLO ───────────────────────────────
# "rotación" / "rotacion" y "subestación apolo" / "subestacion apolo"
RE_MARCA_ROTACION = re.compile(
    r'rotaci\w+n|subestaci\w+n\s+apolo',
    re.IGNORECASE,
)

# Marcadores que abren un bloque de "en servicio".
# Acepta: 🟢, ✅, "Con servicio", "Circuitos restablecidos", "Restablecidos"
RE_INICIO_SERVICIO = re.compile(
    r'(?:🟢|✅|Con servicio:?|Circuitos restablecidos?:?|Restablecidos?:?)',
    re.IGNORECASE,
)

# Marcadores que abren un bloque de "afectados".
# Acepta: 🛑, 🔴, "Afectados", "Circuitos afectados", "Sin servicio"
RE_INICIO_AFECTADOS = re.compile(
    r'(?:🛑|🔴|Afectados:?|Circuitos afectados?:?|Sin servicio:?)',
    re.IGNORECASE,
)


# ── Utilidades ────────────────────────────────────────────────
def _normalizar_codigo(codigo: str) -> str:
    return codigo.upper().replace(' ', '').replace('-', '')


def _minutos(a: datetime | None, b: datetime | None) -> int | None:
    """Diferencia en minutos redondeada. None si falta alguno."""
    if a is None or b is None:
        return None
    delta = (b - a).total_seconds() / 60
    return max(0, int(round(delta)))


def _es_mensaje_rotacion(texto: str) -> bool:
    """
    True si el mensaje menciona rotación APOLO con bloques de
    circuitos afectados y con servicio mezclados.
    """
    if not texto:
        return False
    if not RE_MARCA_ROTACION.search(texto):
        return False
    tiene_servicio = bool(RE_INICIO_SERVICIO.search(texto))
    tiene_afectados = bool(RE_INICIO_AFECTADOS.search(texto))
    return tiene_servicio and tiene_afectados


def _separar_circuitos_rotacion(
    texto: str,
    todos: list[str],
) -> tuple[list[str], list[str]]:
    """
    Divide los circuitos en (afectados, con_servicio) usando la
    posición de los marcadores en el texto.

    Robusto ante:
      - Orden invertido de bloques (restablecidos primero o después).
      - Distintos encabezados ("Con servicio", "Restablecidos", etc.).
      - Múltiples marcadores repetidos (emoji + texto).
    """
    marcadores: list[tuple[int, str]] = []

    for m in RE_INICIO_SERVICIO.finditer(texto):
        marcadores.append((m.start(), 'servicio'))
    for m in RE_INICIO_AFECTADOS.finditer(texto):
        marcadores.append((m.start(), 'afectados'))

    if not marcadores:
        return [], []

    marcadores.sort(key=lambda x: x[0])

    afectados: list[str] = []
    con_servicio: list[str] = []

    for codigo in todos:
        pos = texto.find(codigo)
        if pos == -1:
            continue

        # Encontrar el último marcador ANTES de la mención del circuito
        tipo_bloque = None
        for m_pos, m_tipo in marcadores:
            if m_pos < pos:
                tipo_bloque = m_tipo
            else:
                break

        if tipo_bloque == 'servicio':
            con_servicio.append(codigo)
        elif tipo_bloque == 'afectados':
            afectados.append(codigo)

    return afectados, con_servicio


# ── Procesamiento de un circuito individual ───────────────────
def _procesar_circuito(
    codigo: str,
    tipo_evento: str,
    fecha_msg: datetime,
    hora_contenido: datetime | None,
    mensaje: Mensaje,
) -> None:
    """
    Aplica un evento (afectación / restablecimiento / mención) a un
    circuito. Crea el circuito si no existe, registra el evento y
    actualiza los ciclos.
    """
    tipo_evento_efectivo = 'mencion' if tipo_evento == 'otro' else tipo_evento

    circuito, _ = Circuito.objects.get_or_create(
        codigo=codigo,
        defaults={
            'codigo_normalizado': _normalizar_codigo(codigo),
            'primera_mencion': fecha_msg,
        },
    )

    # Registrar evento atómico (idempotente)
    EventoCircuito.objects.get_or_create(
        circuito=circuito,
        mensaje=mensaje,
        defaults={
            'tipo': tipo_evento_efectivo,
            'fecha_mensaje': fecha_msg,
            'fecha_contenido': hora_contenido,
        },
    )

    # Actualizar marcas de mención
    circuito.ultima_mencion = fecha_msg
    if circuito.primera_mencion is None or fecha_msg < circuito.primera_mencion:
        circuito.primera_mencion = fecha_msg

    # Aplicar lógica según tipo
    if tipo_evento_efectivo == 'afectacion':
        _aplicar_afectacion(circuito, fecha_msg, hora_contenido)
    elif tipo_evento_efectivo == 'restablecimiento':
        _aplicar_restablecimiento(circuito, fecha_msg, hora_contenido)

    circuito.save()


# ── Transiciones de estado ────────────────────────────────────
def _aplicar_afectacion(
    c: Circuito,
    fecha_msg: datetime,
    hora_contenido: datetime | None,
) -> None:
    """Lógica cuando llega un mensaje de afectación."""

    # Cerrar ciclo de servicio previo si lo había
    if c.servicio_activo and c.servicio_inicio_msg:
        c.servicio_fin_msg = fecha_msg
        c.servicio_fin_contenido = hora_contenido
        c.servicio_duracion_msg_min = _minutos(c.servicio_inicio_msg, fecha_msg)
        c.servicio_duracion_contenido_min = _minutos(
            c.servicio_inicio_contenido, hora_contenido,
        )
        c.servicio_activo = False

    # Si ya estaba afectado, no reiniciar el ciclo
    # (es un mensaje adicional: actualización, aviso de mantenimiento, etc.)
    if c.afectacion_activa:
        return

    # Nuevo ciclo de afectación
    c.afectacion_inicio_msg = fecha_msg
    c.afectacion_inicio_contenido = hora_contenido
    c.afectacion_fin_msg = None
    c.afectacion_fin_contenido = None
    c.afectacion_duracion_msg_min = None
    c.afectacion_duracion_contenido_min = None
    c.afectacion_activa = True

    c.estado = 'afectado'
    c.estado_origen = 'afectacion'
    c.estado_actualizado_en = fecha_msg
    c.total_afectaciones += 1


def _aplicar_restablecimiento(
    c: Circuito,
    fecha_msg: datetime,
    hora_contenido: datetime | None,
) -> None:
    """Lógica cuando llega un mensaje de restablecimiento."""

    # Cerrar ciclo de afectación si estaba abierto
    if c.afectacion_activa and c.afectacion_inicio_msg:
        c.afectacion_fin_msg = fecha_msg
        c.afectacion_fin_contenido = hora_contenido
        c.afectacion_duracion_msg_min = _minutos(c.afectacion_inicio_msg, fecha_msg)
        c.afectacion_duracion_contenido_min = _minutos(
            c.afectacion_inicio_contenido, hora_contenido,
        )
        c.afectacion_activa = False

        if c.afectacion_duracion_msg_min:
            c.total_minutos_afectado += c.afectacion_duracion_msg_min

    # Abrir nuevo ciclo de servicio
    c.servicio_inicio_msg = fecha_msg
    c.servicio_inicio_contenido = hora_contenido
    c.servicio_fin_msg = None
    c.servicio_fin_contenido = None
    c.servicio_duracion_msg_min = None
    c.servicio_duracion_contenido_min = None
    c.servicio_activo = True

    c.estado = 'en_servicio'
    c.estado_origen = 'restablecimiento'
    c.estado_actualizado_en = fecha_msg


# ── Punto de entrada ──────────────────────────────────────────
@transaction.atomic
def procesar_mensaje(mensaje: Mensaje) -> None:
    """
    Recibe un Mensaje recién guardado y actualiza todos los
    circuitos mencionados. Idempotente.
    """

    # ── 0. Idempotencia ──────────────────────────────────────
    if EventoCircuito.objects.filter(mensaje=mensaje).exists():
        return  # ya procesado

    # ── 1. Validar tipo ──────────────────────────────────────
    if mensaje.tipo_evento not in ('afectacion', 'restablecimiento', 'otro'):
        return

    # ── 2. Fecha del mensaje ─────────────────────────────────
    fecha_msg = mensaje.fecha
    if not fecha_msg:
        return

    hora_contenido = parsear_hora_contenido(mensaje.texto, fecha_msg)
    circuitos = mensaje.circuitos_mencionados or []
    if not circuitos:
        return

    # ── 3. Caso especial: mensaje de rotación APOLO ──────────
    #    Independiente del tipo_evento asignado por el clasificador,
    #    porque el mensaje mezcla afectación y restablecimiento.
    if _es_mensaje_rotacion(mensaje.texto):
        afectados, con_servicio = _separar_circuitos_rotacion(
            mensaje.texto, circuitos,
        )

        for codigo in afectados:
            _procesar_circuito(
                codigo, 'afectacion', fecha_msg, hora_contenido, mensaje,
            )
        for codigo in con_servicio:
            _procesar_circuito(
                codigo, 'restablecimiento', fecha_msg, hora_contenido, mensaje,
            )
        return

    # ── 4. Caso normal: aplicar el mismo tipo a todos ────────
    for codigo in circuitos:
        _procesar_circuito(
            codigo, mensaje.tipo_evento, fecha_msg, hora_contenido, mensaje,
        )


# ── Recalcular ciclos abiertos ────────────────────────────────
def recalcular_abiertos() -> None:
    """
    Para circuitos con ciclo abierto, actualiza la duración
    hasta el momento actual. Se puede llamar desde un cron cada
    hora o desde una vista.
    """
    ahora = datetime.now(timezone.utc)

    qs = Circuito.objects.filter(
        models.Q(afectacion_activa=True) | models.Q(servicio_activo=True)
    )

    for c in qs:
        campos = []

        if c.afectacion_activa and c.afectacion_inicio_msg:
            c.afectacion_duracion_msg_min = _minutos(c.afectacion_inicio_msg, ahora)
            c.afectacion_duracion_contenido_min = _minutos(
                c.afectacion_inicio_contenido, ahora,
            )
            campos += ['afectacion_duracion_msg_min', 'afectacion_duracion_contenido_min']

        if c.servicio_activo and c.servicio_inicio_msg:
            c.servicio_duracion_msg_min = _minutos(c.servicio_inicio_msg, ahora)
            c.servicio_duracion_contenido_min = _minutos(
                c.servicio_inicio_contenido, ahora,
            )
            campos += ['servicio_duracion_msg_min', 'servicio_duracion_contenido_min']

        if campos:
            c.save(update_fields=campos)