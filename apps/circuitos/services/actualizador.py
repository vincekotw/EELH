"""
Aplica un mensaje de Telegram sobre los circuitos mencionados.
Actualiza estado, ciclos de afectación/servicio y estadísticas.

Detecta mensajes de rotación APOLO en sus múltiples formatos y
asigna cada circuito al bloque correcto (afectado / en servicio).

NOTA: los regex usan \\w en lugar de vocales acentuadas literales
para evitar problemas de encoding.
"""

import logging
import re
from datetime import datetime, timezone

from django.db import models, transaction

from apps.circuitos.models import Circuito, EventoCircuito
from apps.circuitos.services.parser_horas import parsear_hora_contenido
from apps.circuitos.services.parser_daf import procesar_mensaje_daf
from apps.circuitos.services.detector_averia import procesar_snapshot_averias
from apps.usuarios.services.notificaciones import notificar_cambio_circuito
from apps.telegram_base.models import Mensaje


logger = logging.getLogger(__name__)


# ── Detección de rotación APOLO ───────────────────────────────
RE_MARCA_ROTACION = re.compile(
    r'rotaci\w+n|subestaci\w+n\s+apolo',
    re.IGNORECASE,
)

RE_INICIO_SERVICIO = re.compile(
    r'(?:🟢|✅|Con servicio:?|Circuitos restablecidos?:?|Restablecidos?:?)',
    re.IGNORECASE,
)

RE_INICIO_AFECTADOS = re.compile(
    r'(?:🛑|🔴|Afectados:?|Circuitos afectados?:?|Sin servicio:?)',
    re.IGNORECASE,
)


# ── Utilidades ────────────────────────────────────────────────
def _normalizar_codigo(codigo: str) -> str:
    return codigo.upper().replace(' ', '').replace('-', '')


def _minutos(a: datetime | None, b: datetime | None) -> int | None:
    if a is None or b is None:
        return None
    delta = (b - a).total_seconds() / 60
    return max(0, int(round(delta)))


def _es_mensaje_rotacion(texto: str) -> bool:
    if not texto:
        return False
    if not RE_MARCA_ROTACION.search(texto):
        return False
    tiene_servicio = bool(RE_INICIO_SERVICIO.search(texto))
    tiene_afectados = bool(RE_INICIO_AFECTADOS.search(texto))
    return tiene_servicio and tiene_afectados


def _separar_circuitos_rotacion(texto, todos):
    marcadores = []
    for m in RE_INICIO_SERVICIO.finditer(texto):
        marcadores.append((m.start(), 'servicio'))
    for m in RE_INICIO_AFECTADOS.finditer(texto):
        marcadores.append((m.start(), 'afectados'))

    if not marcadores:
        return [], []

    marcadores.sort(key=lambda x: x[0])
    afectados, con_servicio = [], []

    for codigo in todos:
        pos = texto.find(codigo)
        if pos == -1:
            continue
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
def _procesar_circuito(codigo, tipo_evento, fecha_msg, hora_contenido, mensaje):
    tipo_evento_efectivo = 'mencion' if tipo_evento == 'otro' else tipo_evento

    circuito, _ = Circuito.objects.get_or_create(
        codigo=codigo,
        defaults={
            'codigo_normalizado': _normalizar_codigo(codigo),
            'primera_mencion': fecha_msg,
        },
    )

    EventoCircuito.objects.get_or_create(
        circuito=circuito,
        mensaje=mensaje,
        defaults={
            'tipo': tipo_evento_efectivo,
            'fecha_mensaje': fecha_msg,
            'fecha_contenido': hora_contenido,
        },
    )

    circuito.ultima_mencion = fecha_msg
    if circuito.primera_mencion is None or fecha_msg < circuito.primera_mencion:
        circuito.primera_mencion = fecha_msg

    if tipo_evento_efectivo == 'afectacion':
        _aplicar_afectacion(circuito, fecha_msg, hora_contenido)
    elif tipo_evento_efectivo == 'restablecimiento':
        _aplicar_restablecimiento(circuito, fecha_msg, hora_contenido)

    circuito.save()


def _aplicar_afectacion(c, fecha_msg, hora_contenido):
    if c.servicio_activo and c.servicio_inicio_msg:
        c.servicio_fin_msg = fecha_msg
        c.servicio_fin_contenido = hora_contenido
        c.servicio_duracion_msg_min = _minutos(c.servicio_inicio_msg, fecha_msg)
        c.servicio_duracion_contenido_min = _minutos(
            c.servicio_inicio_contenido, hora_contenido,
        )
        c.servicio_activo = False

    if c.afectacion_activa:
        return

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


def _aplicar_restablecimiento(c, fecha_msg, hora_contenido):
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


# ── Notificaciones ────────────────────────────────────────────
def _notificar_lote(codigos, tipo_notif, mensaje):
    """
    Notifica a los usuarios vinculados a cada circuito de `codigos`
    que han cambiado al estado indicado por `tipo_notif`.
    """
    if tipo_notif not in ('afectacion', 'restablecimiento'):
        return
    for codigo in codigos:
        circuito_obj = Circuito.objects.filter(codigo=codigo).first()
        if circuito_obj:
            notificar_cambio_circuito(circuito_obj, tipo_notif, mensaje)


# ═══════════════════════════════════════════════════════════════
# PUNTO DE ENTRADA
# ═══════════════════════════════════════════════════════════════
@transaction.atomic
def procesar_mensaje(mensaje: Mensaje) -> None:
    """
    Recibe un Mensaje recién guardado y actualiza los circuitos
    mencionados. Idempotente para el resto del pipeline.
    """

    # ── 0a. Validación por tabla top afectados ──────────────
    # Corre SIEMPRE, incluso si el resto del mensaje ya fue procesado.
    try:
        from apps.metricas.services.prediccion_avanzada import (
            validar_afectados_por_tabla,
        )
        validar_afectados_por_tabla(mensaje)
    except Exception:
        logger.exception(
            'Error en validar_afectados_por_tabla (msg=%s)',
            mensaje.telegram_id,
        )

    # ── 0b. Detección de alerta masiva ──────────────────────
    try:
        from apps.circuitos.services.detectar_apagon import procesar_alerta_masiva
        procesar_alerta_masiva(mensaje)
    except Exception:
        logger.exception('Error en detector_apagon')

    # ── 1. Idempotencia del resto ───────────────────────────
    if EventoCircuito.objects.filter(mensaje=mensaje).exists():
        return

    if mensaje.tipo_evento not in ('afectacion', 'restablecimiento', 'otro'):
        return

    fecha_msg = mensaje.fecha
    if not fecha_msg:
        return

    hora_contenido = parsear_hora_contenido(mensaje.texto, fecha_msg)
    circuitos = mensaje.circuitos_mencionados or []
    if not circuitos:
        return

    # ── 2. Caso especial: mensaje de rotación APOLO ─────────
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

        # Notificaciones DESPUÉS de aplicar los cambios
        try:
            _notificar_lote(afectados, 'afectacion', mensaje)
            _notificar_lote(con_servicio, 'restablecimiento', mensaje)
        except Exception:
            logger.exception(
                'Error notificando rotación (msg=%s)', mensaje.telegram_id,
            )

        return

    # ── 3. Caso normal: aplicar el mismo tipo a todos ───────
    tipo_notif = mensaje.tipo_evento  # 'afectacion' | 'restablecimiento' | 'otro'

    for codigo in circuitos:
        _procesar_circuito(
            codigo, tipo_notif, fecha_msg, hora_contenido, mensaje,
        )

    # ── 4. Snapshot de averías ──────────────────────────────
    try:
        procesar_snapshot_averias(mensaje)
    except Exception:
        logger.exception(
            'Error en detector_averias (msg=%s)', mensaje.telegram_id,
        )

    # ── 5. Mensajes DAF ────────────────────────────────────
    try:
        procesar_mensaje_daf(mensaje)
    except Exception:
        logger.exception(
            'Error en parser_daf (msg=%s)', mensaje.telegram_id,
        )

    # ── 6. Notificaciones (DESPUÉS de actualizar estados) ───
    # Se usa `tipo_notif` del propio mensaje, no el estado previo
    # del circuito. Así se evita la inversión de notificaciones.
    try:
        _notificar_lote(circuitos, tipo_notif, mensaje)
    except Exception:
        logger.exception(
            'Error generando notificaciones (msg=%s)', mensaje.telegram_id,
        )


# ── Recalcular ciclos abiertos ────────────────────────────────
def recalcular_abiertos() -> None:
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