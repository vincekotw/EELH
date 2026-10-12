"""
Predicción avanzada de afectaciones y restablecimientos.

Criterios (idénticos para ambas direcciones):
  1. Precursores habituales ya en el estado esperado.
  2. Balance de afectaciones vs restablecimientos en las últimas 4h.
  3. Duración del ciclo actual > duración media histórica del circuito.

Además incluye la validación del estado interno a partir del
mensaje con la tabla de "circuitos con más tiempo afectado".
"""

import logging
import re
from collections import Counter
from datetime import timedelta
from statistics import mean

from django.db import transaction
from django.utils import timezone

from apps.circuitos.models import Circuito, EventoCircuito
from .cache import memoize, TTL_CORTO, TTL_LARGO


logger = logging.getLogger(__name__)


# ── Configuración ────────────────────────────────────────────
DIAS_ANALISIS = 30
VENTANA_PRECURSOR_MIN = 180
TOP_PRECURSORES = 5
MIN_PRECURSORES_COINCIDENTES = 3
VENTANA_BALANCE_H = 4
MIN_DESBALANCE = 3
MIN_CICLOS_HISTORICOS = 2
UMBRAL_SCORE = 50


# ═══════════════════════════════════════════════════════════════
# 1. PRECURSORES
# ═══════════════════════════════════════════════════════════════
@memoize(ttl=TTL_LARGO)
def _precursores_de(codigo, tipo, dias=DIAS_ANALISIS,
                    ventana_min=VENTANA_PRECURSOR_MIN,
                    top=TOP_PRECURSORES):
    """
    Devuelve los N circuitos que más frecuentemente aparecen en
    eventos del tipo indicado ANTES de `codigo`.
    """
    desde = timezone.now() - timedelta(days=dias)
    eventos = list(
        EventoCircuito.objects
        .filter(tipo=tipo, fecha_mensaje__gte=desde)
        .select_related('circuito')
        .order_by('fecha_mensaje')
    )

    contador = Counter()
    for i, ev in enumerate(eventos):
        if ev.circuito.codigo != codigo:
            continue
        for j in range(i - 1, -1, -1):
            prev = eventos[j]
            delta = (ev.fecha_mensaje - prev.fecha_mensaje).total_seconds() / 60
            if delta > ventana_min:
                break
            if prev.circuito.codigo != codigo:
                contador[prev.circuito.codigo] += 1

    return [c for c, _ in contador.most_common(top)]


# ═══════════════════════════════════════════════════════════════
# 2. DURACIONES HISTÓRICAS
# ═══════════════════════════════════════════════════════════════
def _duraciones_previas(circuito, tipo, dias=DIAS_ANALISIS):
    """
    Duraciones (min) de ciclos completos del tipo indicado.

    tipo='afectacion'  →  afectación → restablecimiento
    tipo='servicio'    →  restablecimiento → siguiente afectación
    """
    desde = timezone.now() - timedelta(days=dias)
    eventos = list(
        EventoCircuito.objects
        .filter(circuito=circuito, fecha_mensaje__gte=desde)
        .order_by('fecha_mensaje')
    )

    duraciones = []
    inicio = None
    inicio_tipo = 'afectacion' if tipo == 'afectacion' else 'restablecimiento'
    fin_tipo = 'restablecimiento' if tipo == 'afectacion' else 'afectacion'

    for ev in eventos:
        if ev.tipo == inicio_tipo:
            inicio = ev.fecha_mensaje
        elif ev.tipo == fin_tipo and inicio:
            duraciones.append(
                (ev.fecha_mensaje - inicio).total_seconds() / 60
            )
            inicio = None

    return duraciones


# ═══════════════════════════════════════════════════════════════
# 3. BALANCE 4H
# ═══════════════════════════════════════════════════════════════
@memoize(ttl=TTL_CORTO)
def _balance_ultimas_4h():
    hace = timezone.now() - timedelta(hours=VENTANA_BALANCE_H)
    afect = EventoCircuito.objects.filter(
        tipo='afectacion', fecha_mensaje__gte=hace,
    ).count()
    restab = EventoCircuito.objects.filter(
        tipo='restablecimiento', fecha_mensaje__gte=hace,
    ).count()
    return afect, restab


# ═══════════════════════════════════════════════════════════════
# 4. EVALUACIÓN DE UN CIRCUITO
# ═══════════════════════════════════════════════════════════════
def _evaluar_circuito(circuito, direccion):
    score = 0
    razones = []

    # ── Criterio 1: precursores ────────────────────────────
    estado_esperado = 'afectado' if direccion == 'afectacion' else 'en_servicio'
    precursores = _precursores_de(circuito.codigo, tipo=direccion)
    if precursores:
        coincidentes = Circuito.objects.filter(
            codigo__in=precursores, estado=estado_esperado,
        ).count()
        if coincidentes >= MIN_PRECURSORES_COINCIDENTES:
            score += 40
            razones.append(
                f'{coincidentes}/{len(precursores)} precursores ya en '
                f'estado "{estado_esperado}"'
            )
        elif coincidentes >= 2:
            score += 20
            razones.append(
                f'{coincidentes}/{len(precursores)} precursores coincidentes'
            )

    # ── Criterio 2: balance 4h ─────────────────────────────
    afect, restab = _balance_ultimas_4h()
    if direccion == 'afectacion':
        if afect - restab >= MIN_DESBALANCE:
            score += 30
            razones.append(
                f'{afect} afectaciones vs {restab} restablecimientos en 4h'
            )
    else:
        if restab - afect >= MIN_DESBALANCE:
            score += 30
            razones.append(
                f'{restab} restablecimientos vs {afect} afectaciones en 4h'
            )

    # ── Criterio 3: duración actual vs media histórica ─────
    if direccion == 'afectacion':
        if circuito.servicio_activo and circuito.servicio_inicio_msg:
            actual = (timezone.now() - circuito.servicio_inicio_msg).total_seconds() / 60
            previos = _duraciones_previas(circuito, tipo='servicio')
            if len(previos) >= MIN_CICLOS_HISTORICOS:
                media = mean(previos)
                if actual > media * 1.2:
                    score += 30
                    razones.append(
                        f'servicio actual {actual:.0f}min > media {media:.0f}min (×1.2)'
                    )
                elif actual > media:
                    score += 15
                    razones.append(
                        f'servicio actual {actual:.0f}min > media {media:.0f}min'
                    )
    else:
        if circuito.afectacion_activa and circuito.afectacion_inicio_msg:
            actual = (timezone.now() - circuito.afectacion_inicio_msg).total_seconds() / 60
            previos = _duraciones_previas(circuito, tipo='afectacion')
            if len(previos) >= MIN_CICLOS_HISTORICOS:
                media = mean(previos)
                if actual > media * 1.2:
                    score += 30
                    razones.append(
                        f'afectación actual {actual:.0f}min > media {media:.0f}min (×1.2)'
                    )
                elif actual > media:
                    score += 15
                    razones.append(
                        f'afectación actual {actual:.0f}min > media {media:.0f}min'
                    )

    return {
        'codigo': circuito.codigo,
        'municipio': circuito.municipio or '',
        'estado_actual': circuito.estado,
        'score': min(100, score),
        'razones': razones,
    }


# ═══════════════════════════════════════════════════════════════
# 5. PREDICCIÓN AGREGADA
# ═══════════════════════════════════════════════════════════════
@memoize(ttl=TTL_CORTO)
def prediccion_cambios_proximos(limite=15):
    candidatos_afect = []
    for c in Circuito.objects.filter(estado='en_servicio'):
        ev = _evaluar_circuito(c, 'afectacion')
        if ev['score'] >= UMBRAL_SCORE:
            candidatos_afect.append(ev)

    candidatos_restab = []
    for c in Circuito.objects.filter(estado='afectado'):
        ev = _evaluar_circuito(c, 'restablecimiento')
        if ev['score'] >= UMBRAL_SCORE:
            candidatos_restab.append(ev)

    candidatos_afect.sort(key=lambda x: -x['score'])
    candidatos_restab.sort(key=lambda x: -x['score'])

    afect, restab = _balance_ultimas_4h()
    return {
        'afectacion': candidatos_afect[:limite],
        'restablecimiento': candidatos_restab[:limite],
        'balance_4h': {
            'afectaciones': afect,
            'restablecimientos': restab,
        },
    }


# ═══════════════════════════════════════════════════════════════
# 6. VALIDACIÓN POR TABLA "TOP AFECTADOS"
# ═══════════════════════════════════════════════════════════════
RE_DETECTAR_TABLA_TOP = re.compile(
    r'(?:'
    r'top\s+(?:de\s+)?afectad|'
    r'afectados?\s+con\s+m[áa]s\s+tiempo|'
    r'mayor\s+tiempo\s+afectad|'
    r'ranking\s+(?:de\s+)?afectad|'
    r'circuitos?\s+m[áa]s\s+afectad|'
    r'tiempo\s+de\s+afectaci[óo]n'
    r')',
    re.IGNORECASE,
)

RE_FILA_TABLA = re.compile(
    r'(?:^|\n)\s*(?:(?:\d+|[•·\-–—])\s*[\.\):]?\s*)?'
    r'(?P<codigo>[A-Za-z]{1,4}-?\d{1,5})\s*'
    r'[\-–—:]\s*'
    r'(?P<tiempo>\d+\s*(?:h|horas?|:)[^\n]*)',
    re.IGNORECASE,
)

RE_TIEMPO_COLON = re.compile(r'(?P<h>\d+)\s*:\s*(?P<m>\d{2})')
RE_TIEMPO_HMS = re.compile(
    r'(?:(?P<h>\d+)\s*h(?:rs?|oras?)?)?\s*'
    r'(?:(?P<m>\d+)\s*m(?:in(?:utos?)?)?)?',
    re.IGNORECASE,
)


def _parsear_tiempo(texto):
    texto = texto.strip()

    mc = RE_TIEMPO_COLON.search(texto)
    if mc:
        return int(mc.group('h')) * 60 + int(mc.group('m'))

    mh = RE_TIEMPO_HMS.search(texto)
    if mh:
        h = int(mh.group('h') or 0)
        mn = int(mh.group('m') or 0)
        if h or mn:
            return h * 60 + mn
    return None


def _parsear_tabla_top(texto):
    filas = []
    for m in RE_FILA_TABLA.finditer(texto):
        codigo = m.group('codigo').upper().replace(' ', '')
        minutos = _parsear_tiempo(m.group('tiempo'))
        if minutos is None:
            continue
        filas.append({'codigo': codigo, 'minutos': minutos})
    return filas


@transaction.atomic
def validar_afectados_por_tabla(mensaje):
    """
    Cuando llega el mensaje con la tabla de "circuitos con más tiempo
    afectado", valida el estado interno:

    Si un circuito marcado con `afectacion_activa=True` tiene un
    tiempo acumulado mayor que el del circuito MÁS afectado de la
    tabla y NO aparece en ella, entonces fue restablecido sin
    mensaje. Se cierra su ciclo.

    Devuelve la lista de códigos corregidos.
    """
    if not mensaje or not mensaje.texto:
        return []

    if not RE_DETECTAR_TABLA_TOP.search(mensaje.texto):
        return []

    filas = _parsear_tabla_top(mensaje.texto)
    if not filas:
        return []

    top_minutos = max(f['minutos'] for f in filas)
    codigos_en_tabla = {f['codigo'] for f in filas}
    fecha = mensaje.fecha or timezone.now()

    corregidos = []
    for c in Circuito.objects.filter(
        afectacion_activa=True,
        afectacion_inicio_msg__isnull=False,
    ):
        duracion_actual = (
            (fecha - c.afectacion_inicio_msg).total_seconds() / 60
        )
        if (c.codigo.upper() not in codigos_en_tabla
                and duracion_actual > top_minutos):
            _cerrar_afectacion_por_inferencia(c, fecha, razon='tabla_top')
            corregidos.append(c.codigo)
            logger.info(
                'Circuito %s cerrado por tabla top (tenía %.0f min, '
                'tope tabla %d min)',
                c.codigo, duracion_actual, top_minutos,
            )

    return corregidos


def _cerrar_afectacion_por_inferencia(circuito, fecha_fin, razon=''):
    """
    Cierra el ciclo de afectación sin mensaje oficial.
    """
    if not circuito.afectacion_activa:
        return

    duracion = None
    if circuito.afectacion_inicio_msg:
        duracion = int(
            (fecha_fin - circuito.afectacion_inicio_msg).total_seconds() / 60
        )

    circuito.afectacion_activa = False
    circuito.afectacion_fin_msg = fecha_fin
    circuito.afectacion_duracion_msg_min = duracion
    circuito.estado = 'en_servicio'
    circuito.estado_origen = 'inferido'
    circuito.estado_actualizado_en = fecha_fin

    circuito.servicio_inicio_msg = fecha_fin
    circuito.servicio_activo = True
    circuito.servicio_duracion_msg_min = None

    if duracion:
        circuito.total_minutos_afectado = (
            (circuito.total_minutos_afectado or 0) + duracion
        )

    nota = f'\n[{fecha_fin:%Y-%m-%d %H:%M}] Cerrado por {razon}.'
    circuito.notas = ((circuito.notas or '') + nota).strip()

    circuito.save(update_fields=[
        'afectacion_activa', 'afectacion_fin_msg',
        'afectacion_duracion_msg_min',
        'estado', 'estado_origen', 'estado_actualizado_en',
        'servicio_inicio_msg', 'servicio_activo',
        'servicio_duracion_msg_min',
        'total_minutos_afectado', 'notas',
    ])