"""
Cómputo de las 20 métricas del dashboard.
Todas las funciones son puras y cacheables.
"""

from collections import Counter, defaultdict
from datetime import datetime, timedelta

from django.contrib.auth.models import User
from django.db.models import (
    Count, Sum, Avg, Q, F, Max, Min,
)
from django.utils import timezone

from apps.circuitos.models import (
    Circuito, EventoCircuito, AlertaMasiva,
    ReporteDiscrepancia, CircuitoDAF,
)
from apps.telegram_base.models import Mensaje
from apps.usuarios.models import CircuitoUsuario, NavegacionLog

from .cache import memoize, TTL_CORTO, TTL_MEDIO, TTL_LARGO
from statistics import mean, median


# ── Configuración ────────────────────────────────────────────
MAX_HORAS_CICLO_VALIDO = 72       # un ciclo > 72h se considera anómalo
MIN_MUESTRAS_PARA_PROMEDIO = 3    # mínimo de ciclos para calcular medias

def _ciclos_cerrados(dias=30, max_horas=MAX_HORAS_CICLO_VALIDO, tipo='afectacion'):
    """
    Extrae ciclos cerrados reales desde EventoCircuito.

    Recorre eventos cronológicamente por circuito y empareja
    afectación → restablecimiento. Filtra ciclos cuya duración
    excede max_horas (probablemente por falta de datos).

    Devuelve lista de dicts:
      {'codigo', 'municipio', 'inicio', 'fin', 'duracion_min'}
    """
    desde = timezone.now() - timedelta(days=dias)
    max_min = max_horas * 60

    eventos = (
        EventoCircuito.objects
        .filter(
            tipo__in=['afectacion', 'restablecimiento'],
            fecha_mensaje__gte=desde,
        )
        .select_related('circuito')
        .order_by('circuito_id', 'fecha_mensaje')
    )

    por_circuito = defaultdict(list)
    for ev in eventos:
        por_circuito[ev.circuito_id].append(ev)

    ciclos = []
    for circuito_id, evs in por_circuito.items():
        inicio = None
        for ev in evs:
            if tipo == 'afectacion':
                if ev.tipo == 'afectacion':
                    inicio = ev
                elif ev.tipo == 'restablecimiento' and inicio:
                    duracion = (ev.fecha_mensaje - inicio.fecha_mensaje).total_seconds() / 60
                    if 0 < duracion <= max_min:
                        ciclos.append({
                            'codigo': inicio.circuito.codigo,
                            'municipio': inicio.circuito.municipio,
                            'inicio': inicio.fecha_mensaje,
                            'fin': ev.fecha_mensaje,
                            'duracion_min': duracion,
                        })
                    inicio = None
            # Nota: el tipo servicio se puede implementar similar

    return ciclos


# ═══════════════════════════════════════════════════════════════
# UTILIDADES INTERNAS
# ═══════════════════════════════════════════════════════════════
def _eventos_rango(desde, hasta, tipos=('afectacion', 'restablecimiento')):
    """Trae los eventos de un rango en orden cronológico."""
    return (
        EventoCircuito.objects
        .filter(
            fecha_mensaje__gte=desde,
            fecha_mensaje__lt=hasta,
            tipo__in=tipos,
        )
        .select_related('circuito')
        .order_by('fecha_mensaje')
    )


def _activos_en(ts, eventos):
    """
    Dado un timestamp y una lista de eventos ordenada, devuelve el
    set de IDs de circuitos afectados en ese instante.
    """
    activos = set()
    for ev in eventos:
        if ev.fecha_mensaje > ts:
            break
        if ev.tipo == 'afectacion':
            activos.add(ev.circuito_id)
        elif ev.tipo == 'restablecimiento':
            activos.discard(ev.circuito_id)
    return activos


def _fmt_hora(dt):
    return dt.strftime('%Y-%m-%d %H:%M')


# ═══════════════════════════════════════════════════════════════
# 1. CIRCUITOS ACTIVOS POR HORA (ÚLTIMAS 24H)
# ═══════════════════════════════════════════════════════════════
@memoize(ttl=TTL_CORTO)
def circuitos_activos_por_hora(horas=24):
    ahora = timezone.now()
    desde = ahora - timedelta(hours=horas)

    # Traer todos los eventos desde 24h antes para tener contexto
    eventos = list(_eventos_rango(
        desde - timedelta(hours=24),
        ahora + timedelta(minutes=1),
    ))

    serie = []
    for h in range(horas, -1, -1):
        ts = ahora - timedelta(hours=h)
        activos = _activos_en(ts, eventos)
        serie.append({
            'hora': ts.strftime('%H:%M'),
            'timestamp': ts.isoformat(),
            'total': len(activos),
        })
    return serie


# ═══════════════════════════════════════════════════════════════
# 2. MEDIA CIRCUITOS ACTIVOS POR DÍA (10 DÍAS)
# ═══════════════════════════════════════════════════════════════
@memoize(ttl=TTL_MEDIO)
def media_activos_por_dia(dias=10):
    ahora = timezone.now()
    desde = ahora - timedelta(days=dias)

    eventos = list(_eventos_rango(
        desde - timedelta(days=2),
        ahora + timedelta(minutes=1),
    ))

    serie = []
    for d in range(dias, -1, -1):
        # Punto medio del día a las 12:00
        dia_actual = (ahora - timedelta(days=d)).replace(
            hour=12, minute=0, second=0, microsecond=0,
        )
        activos = _activos_en(dia_actual, eventos)
        serie.append({
            'fecha': dia_actual.strftime('%d %b'),
            'total': len(activos),
            'timestamp': dia_actual.isoformat(),
        })
    return serie


# ═══════════════════════════════════════════════════════════════
# 3. ROTACIÓN MEDIA (SERVICIO vs SIN SERVICIO)
# ═══════════════════════════════════════════════════════════════
@memoize(ttl=TTL_MEDIO)
def rotacion_media(dias=10):
    """
    Media y mediana de duración de ciclos CERRADOS de afectación
    y de servicio. La mediana es más robusta ante outliers.
    """
    ciclos_afect = _ciclos_cerrados(dias=dias, tipo='afectacion')

    if not ciclos_afect:
        return {
            'media_afectacion_min': 0,
            'mediana_afectacion_min': 0,
            'muestras': 0,
        }

    duraciones = [c['duracion_min'] for c in ciclos_afect]

    return {
        'media_afectacion_min': round(mean(duraciones), 1),
        'mediana_afectacion_min': round(median(duraciones), 1),
        'muestras': len(duraciones),
    }


# ═══════════════════════════════════════════════════════════════
# 4. CIRCUITOS CON MAYOR ROTACIÓN (10 DÍAS)
# ═══════════════════════════════════════════════════════════════
@memoize(ttl=TTL_MEDIO)
def circuitos_mayor_rotacion(dias=10, limite=15):
    desde = timezone.now() - timedelta(days=dias)

    qs = (
        EventoCircuito.objects
        .filter(tipo='afectacion', fecha_mensaje__gte=desde)
        .values('circuito__codigo', 'circuito__municipio', 'circuito_id')
        .annotate(veces=Count('id'))
        .order_by('-veces')[:limite]
    )
    return list(qs)


# ═══════════════════════════════════════════════════════════════
# 5. CIRCUITOS SIN ROTACIÓN (10 DÍAS)
# ═══════════════════════════════════════════════════════════════
@memoize(ttl=TTL_MEDIO)
def circuitos_sin_rotacion(dias=10):
    desde = timezone.now() - timedelta(days=dias)

    con_eventos = set(
        EventoCircuito.objects
        .filter(tipo='afectacion', fecha_mensaje__gte=desde)
        .values_list('circuito_id', flat=True)
    )

    sin_rotacion = (
        Circuito.objects
        .exclude(id__in=con_eventos)
        .values('codigo', 'municipio', 'estado')
        .order_by('codigo')
    )
    return list(sin_rotacion)


# ═══════════════════════════════════════════════════════════════
# 6. CIRCUITOS DAF DE LA SEMANA
# ═══════════════════════════════════════════════════════════════
@memoize(ttl=TTL_MEDIO)
def circuitos_daf_semana():
    hoy = timezone.now().date()
    qs = (
        CircuitoDAF.objects
        .filter(activo=True, desde__lte=hoy, hasta__gte=hoy)
        .select_related('circuito')
        .order_by('circuito__codigo')
    )
    return [
        {
            'codigo': d.circuito.codigo,
            'municipio': d.circuito.municipio,
            'desde': d.desde.strftime('%d %b'),
            'hasta': d.hasta.strftime('%d %b'),
        }
        for d in qs
    ]


# ═══════════════════════════════════════════════════════════════
# 7. CIRCUITOS CON MÁS HORAS SIN SERVICIO
# ═══════════════════════════════════════════════════════════════
@memoize(ttl=TTL_MEDIO)
def circuitos_mas_horas_sin_servicio(limite=15):
    qs = (
        Circuito.objects
        .filter(total_minutos_afectado__gt=0)
        .values('codigo', 'municipio', 'total_minutos_afectado',
                'total_afectaciones', 'estado')
        .order_by('-total_minutos_afectado')[:limite]
    )
    return [
        {**c, 'total_horas': round(c['total_minutos_afectado'] / 60, 1)}
        for c in qs
    ]


# ═══════════════════════════════════════════════════════════════
# 8. CIRCUITOS CON MÁS HORAS DE SERVICIO
# ═══════════════════════════════════════════════════════════════
@memoize(ttl=TTL_MEDIO)
def circuitos_mas_horas_servicio(limite=15):
    qs = (
        Circuito.objects
        .filter(servicio_duracion_msg_min__isnull=False)
        .values('codigo', 'municipio', 'servicio_duracion_msg_min', 'estado')
        .order_by('-servicio_duracion_msg_min')[:limite]
    )
    return [
        {**c, 'horas_servicio': round(c['servicio_duracion_msg_min'] / 60, 1)}
        for c in qs
    ]


# ═══════════════════════════════════════════════════════════════
# 9. MTTR (MEAN TIME TO RESTORE)
# ═══════════════════════════════════════════════════════════════
@memoize(ttl=TTL_MEDIO)
def mttr_por_circuito(limite=15, dias=30):
    """
    MTTR (Mean Time To Restore) por circuito, calculado sobre
    ciclos CERRADOS en los últimos `dias`, filtrando duraciones
    anómalas.
    """
    ciclos = _ciclos_cerrados(dias=dias)

    # Agrupar por circuito
    por_circuito = defaultdict(list)
    for c in ciclos:
        por_circuito[c['codigo']].append(c['duracion_min'])

    # Solo circuitos con suficientes muestras
    resultados = []
    for codigo, duraciones in por_circuito.items():
        if len(duraciones) < 2:
            continue
        resultados.append({
            'codigo': codigo,
            'municipio': next(
                (c['municipio'] for c in ciclos if c['codigo'] == codigo), ''
            ),
            'mttr_min': round(mean(duraciones), 1),
            'mttr_horas': round(mean(duraciones) / 60, 1),
            'muestras': len(duraciones),
        })

    resultados.sort(key=lambda x: -x['mttr_min'])
    return resultados[:limite]


# ═══════════════════════════════════════════════════════════════
# 10. DISPONIBILIDAD (%) POR CIRCUITO
# ═══════════════════════════════════════════════════════════════
@memoize(ttl=TTL_MEDIO)
def disponibilidad_por_circuito(limite=20):
    """
    Disponibilidad = horas_servicio / (horas_servicio + horas_afectado) * 100
    """
    circuitos = Circuito.objects.filter(
        Q(total_minutos_afectado__gt=0)
        | Q(servicio_duracion_msg_min__isnull=False)
    )

    resultados = []
    for c in circuitos:
        min_afect = c.total_minutos_afectado or 0
        min_serv = c.servicio_duracion_msg_min or 0
        total = min_afect + min_serv
        if total == 0:
            continue
        disp = round(min_serv * 100 / total, 1)
        resultados.append({
            'codigo': c.codigo,
            'municipio': c.municipio,
            'disponibilidad': disp,
            'min_afectado': min_afect,
            'min_servicio': min_serv,
        })

    # Ordenar por disponibilidad ascendente (los peores primero)
    resultados.sort(key=lambda x: x['disponibilidad'])
    return resultados[:limite]


# ═══════════════════════════════════════════════════════════════
# 11. HEATMAP POR HORA DEL DÍA
# ═══════════════════════════════════════════════════════════════
@memoize(ttl=TTL_MEDIO)
def heatmap_hora_dia(dias=10):
    """
    Conteo de afectaciones por hora del día (0-23).
    Útil para ver patrones horarios.
    """
    desde = timezone.now() - timedelta(days=dias)
    eventos = EventoCircuito.objects.filter(
        tipo='afectacion',
        fecha_mensaje__gte=desde,
    ).values_list('fecha_mensaje', flat=True)

    # Cuba es UTC-4 (verano) o UTC-5 (invierno). Usamos -4.
    offset_horas = -4
    contador = Counter()
    for ts in eventos:
        hora_local = (ts.hour + offset_horas) % 24
        contador[hora_local] += 1

    return [
        {'hora': h, 'total': contador.get(h, 0)}
        for h in range(24)
    ]


# ═══════════════════════════════════════════════════════════════
# 12. TOP MUNICIPIOS MÁS CASTIGADOS
# ═══════════════════════════════════════════════════════════════
@memoize(ttl=TTL_MEDIO)
def top_municipios(limite=12):
    qs = (
        Circuito.objects
        .exclude(municipio='')
        .values('municipio')
        .annotate(
            total_circuitos=Count('id'),
            afectados_ahora=Count('id', filter=Q(estado='afectado')),
            minutos_totales=Sum('total_minutos_afectado'),
            ciclos=Sum('total_afectaciones'),
        )
        .order_by('-minutos_totales')[:limite]
    )
    return [
        {**m, 'horas_totales': round((m['minutos_totales'] or 0) / 60, 1)}
        for m in qs
    ]


# ═══════════════════════════════════════════════════════════════
# 13. ÍNDICE DE ESTABILIDAD
# ═══════════════════════════════════════════════════════════════
@memoize(ttl=TTL_MEDIO)
def indice_estabilidad(limite=20):
    """
    Score combinado 0-100:
      - 50% disponibilidad
      - 30% inverso a rotación (menos ciclos = mejor)
      - 20% inverso a MTTR (menos tiempo = mejor)

    Un score alto = circuito estable.
    """
    circuitos = Circuito.objects.all()
    resultados = []

    # Valores para normalizar
    max_ciclos = max(
        (c.total_afectaciones for c in circuitos), default=1,
    ) or 1
    max_mttr = max(
        (c.afectacion_duracion_msg_min or 0 for c in circuitos), default=1,
    ) or 1

    for c in circuitos:
        min_afect = c.total_minutos_afectado or 0
        min_serv = c.servicio_duracion_msg_min or 0
        total = min_afect + min_serv

        disp = (min_serv * 100 / total) if total > 0 else 100
        rot_score = 100 - (c.total_afectaciones * 100 / max_ciclos)
        mttr_score = 100 - ((c.afectacion_duracion_msg_min or 0) * 100 / max_mttr)

        score = 0.5 * disp + 0.3 * rot_score + 0.2 * mttr_score

        resultados.append({
            'codigo': c.codigo,
            'municipio': c.municipio,
            'score': round(score, 1),
            'disponibilidad': round(disp, 1),
            'ciclos': c.total_afectaciones,
        })

    resultados.sort(key=lambda x: -x['score'])
    return resultados[:limite]


# ═══════════════════════════════════════════════════════════════
# 14. TIEMPO ENTRE AFECTACIONES
# ═══════════════════════════════════════════════════════════════
@memoize(ttl=TTL_MEDIO)
def tiempo_entre_afectaciones(limite=15):
    """
    Media del tiempo (en minutos) entre el restablecimiento y la
    siguiente afectación por circuito. Valores bajos = inestable.
    """
    # Obtener todos los eventos agrupados por circuito
    eventos = (
        EventoCircuito.objects
        .filter(tipo__in=['afectacion', 'restablecimiento'])
        .select_related('circuito')
        .order_by('circuito_id', 'fecha_mensaje')
    )

    # Agrupar
    por_circuito = defaultdict(list)
    for ev in eventos:
        por_circuito[ev.circuito.codigo].append(ev)

    resultados = []
    for codigo, evs in por_circuito.items():
        gaps = []
        ultimo_restab = None
        for ev in evs:
            if ev.tipo == 'restablecimiento':
                ultimo_restab = ev.fecha_mensaje
            elif ev.tipo == 'afectacion' and ultimo_restab:
                delta = (ev.fecha_mensaje - ultimo_restab).total_seconds() / 60
                gaps.append(delta)
                ultimo_restab = None

        if gaps:
            resultados.append({
                'codigo': codigo,
                'municipio': evs[0].circuito.municipio,
                'tiempo_medio_min': round(sum(gaps) / len(gaps), 1),
                'muestras': len(gaps),
            })

    # Ordenar por tiempo más corto (los más inestables primero)
    resultados.sort(key=lambda x: x['tiempo_medio_min'])
    return resultados[:limite]


# ═══════════════════════════════════════════════════════════════
# 15. PREDICCIÓN HEURÍSTICA (PRÓXIMAS 6H)
# ═══════════════════════════════════════════════════════════════
@memoize(ttl=TTL_CORTO)
def prediccion_proximas_horas(limite=10, ventana_horas=6, dias_analisis=30):
    """
    Estima la probabilidad de que un circuito EN SERVICIO se afecte
    en las próximas `ventana_horas` horas.

    Método:
      1. Se toman las últimas `dias_analisis` jornadas.
      2. Para cada circuito en servicio, se cuenta en cuántos días
         tuvo al menos una afectación en la franja horaria objetivo.
      3. Probabilidad = días_con_afectación / días_totales * 100.

    Solo se listan circuitos con probabilidad >= 10% y al menos
    2 días coincidentes.
    """
    ahora = timezone.now()
    hora_actual = (ahora.hour - 4) % 24  # hora Cuba
    desde = ahora - timedelta(days=dias_analisis)

    # Franja objetivo (próximas N horas, ajustadas a hora Cuba)
    horas_objetivo = {
        (hora_actual + i) % 24 for i in range(1, ventana_horas + 1)
    }

    # Circuitos actualmente en servicio
    codigos_servicio = set(
        Circuito.objects
        .filter(estado='en_servicio')
        .values_list('codigo', flat=True)
    )

    # Afectaciones en el período
    eventos = (
        EventoCircuito.objects
        .filter(
            tipo='afectacion',
            fecha_mensaje__gte=desde,
            circuito__codigo__in=codigos_servicio,
        )
        .values_list(
            'circuito__codigo',
            'circuito__municipio',
            'fecha_mensaje',
        )
    )

    # Agrupar por (circuito, día, hora)
    dias_con_afectacion = defaultdict(set)  # (codigo, municipio) → set de fechas
    for codigo, municipio, ts in eventos:
        hora_evento = (ts.hour - 4) % 24
        if hora_evento in horas_objetivo:
            dias_con_afectacion[(codigo, municipio)].add(ts.date())

    # Calcular probabilidad
    resultados = []
    for (codigo, municipio), dias in dias_con_afectacion.items():
        if len(dias) < 2:  # mínimo 2 días con afectación en la franja
            continue
        prob = len(dias) * 100 / dias_analisis
        if prob < 10:
            continue
        resultados.append({
            'codigo': codigo,
            'municipio': municipio,
            'dias_coincidentes': len(dias),
            'dias_analizados': dias_analisis,
            'probabilidad': round(prob, 1),
        })

    resultados.sort(key=lambda x: -x['probabilidad'])
    return resultados[:limite]


# ═══════════════════════════════════════════════════════════════
# 16. RANKING DE USUARIOS MÁS ACTIVOS
# ═══════════════════════════════════════════════════════════════
@memoize(ttl=TTL_LARGO)
def ranking_usuarios(limite=15):
    """
    Ranking por contribución:
      - 1 punto por circuito vinculado
      - 2 puntos por reporte de discrepancia
      - 1 punto por cada 50 navegaciones (cap a 10 puntos)
    """
    desde = timezone.now() - timedelta(days=30)

    usuarios = User.objects.filter(is_active=True)
    resultados = []

    for u in usuarios:
        vinculados = CircuitoUsuario.objects.filter(user=u).count()
        reportes = ReporteDiscrepancia.objects.filter(
            circuito__usuarios_vinculados__user=u,
            creado_en__gte=desde,
        ).count()
        navegaciones = NavegacionLog.objects.filter(
            user=u, creado_en__gte=desde,
        ).count()

        puntos = vinculados + (reportes * 2) + min(10, navegaciones // 50)
        if puntos == 0:
            continue

        resultados.append({
            'username': u.username,
            'vinculados': vinculados,
            'reportes': reportes,
            'puntos': puntos,
        })

    resultados.sort(key=lambda x: -x['puntos'])
    return resultados[:limite]


# ═══════════════════════════════════════════════════════════════
# 17. TENDENCIA SEMANAL (ACTUAL vs ANTERIOR)
# ═══════════════════════════════════════════════════════════════
@memoize(ttl=TTL_LARGO)
def tendencia_semanal():
    """
    Compara las afectaciones de los últimos 7 días vs los 7 anteriores.
    Devuelve el % de cambio.
    """
    ahora = timezone.now()
    hace_7d = ahora - timedelta(days=7)
    hace_14d = ahora - timedelta(days=14)

    esta_semana = EventoCircuito.objects.filter(
        tipo='afectacion', fecha_mensaje__gte=hace_7d,
    ).count()

    semana_anterior = EventoCircuito.objects.filter(
        tipo='afectacion',
        fecha_mensaje__gte=hace_14d,
        fecha_mensaje__lt=hace_7d,
    ).count()

    if semana_anterior > 0:
        cambio = round((esta_semana - semana_anterior) * 100 / semana_anterior, 1)
    else:
        cambio = 100 if esta_semana > 0 else 0

    return {
        'esta_semana': esta_semana,
        'semana_anterior': semana_anterior,
        'cambio_pct': cambio,
        'mejora': cambio < 0,  # menos afectaciones = mejor
    }


# ═══════════════════════════════════════════════════════════════
# 18. ALERTAS HISTÓRICAS POR SEVERIDAD
# ═══════════════════════════════════════════════════════════════
@memoize(ttl=TTL_MEDIO)
def alertas_historicas(limite=20):
    qs = (
        AlertaMasiva.objects
        .order_by('-iniciado_en')[:limite]
    )
    return [
        {
            'titulo': a.titulo,
            'tipo': a.get_tipo_display(),
            'inicio': a.iniciado_en.strftime('%d %b %Y %H:%M'),
            'duracion_min': a.duracion_min,
            'duracion_h': round(a.duracion_min / 60, 1),
            'activo': a.activo,
        }
        for a in qs
    ]


# ═══════════════════════════════════════════════════════════════
# 19. CIRCUITOS CRÓNICOS
# ═══════════════════════════════════════════════════════════════
@memoize(ttl=TTL_MEDIO)
def circuitos_cronicos(limite=15):
    """
    Circuitos con:
      - Disponibilidad < 60%
      - >= 3 afectaciones en el período
      - MTTR elevado
    """
    resultados = []
    for c in Circuito.objects.filter(total_afectaciones__gte=3):
        min_afect = c.total_minutos_afectado or 0
        min_serv = c.servicio_duracion_msg_min or 0
        total = min_afect + min_serv
        if total == 0:
            continue

        disp = min_serv * 100 / total
        if disp < 60:
            resultados.append({
                'codigo': c.codigo,
                'municipio': c.municipio,
                'disponibilidad': round(disp, 1),
                'ciclos': c.total_afectaciones,
                'horas_afectado': round(min_afect / 60, 1),
            })

    resultados.sort(key=lambda x: x['disponibilidad'])
    return resultados[:limite]


# ═══════════════════════════════════════════════════════════════
# 20. DURACIÓN ACUMULADA POR USUARIO
# ═══════════════════════════════════════════════════════════════
@memoize(ttl=TTL_CORTO)
def duracion_acumulada_usuarios(dias=7, limite=15):
    """
    Para cada usuario, suma los minutos que sus circuitos vinculados
    estuvieron afectados en el período. Métrica personal.
    """
    desde = timezone.now() - timedelta(days=dias)

    resultados = []
    for user in User.objects.filter(is_active=True):
        circuitos = CircuitoUsuario.objects.filter(
            user=user,
        ).values_list('circuito_id', flat=True)

        if not circuitos:
            continue

        # Afectaciones en el período
        total = EventoCircuito.objects.filter(
            tipo='afectacion',
            circuito_id__in=circuitos,
            fecha_mensaje__gte=desde,
        ).aggregate(
            total_min=Sum(F('circuito__afectacion_duracion_msg_min'))
        )['total_min'] or 0

        if total > 0:
            resultados.append({
                'username': user.username,
                'circuitos': len(circuitos),
                'minutos_afectado': total,
                'horas_afectado': round(total / 60, 1),
            })

    resultados.sort(key=lambda x: -x['minutos_afectado'])
    return resultados[:limite]


# ═══════════════════════════════════════════════════════════════
# KPIs RESUMEN
# ═══════════════════════════════════════════════════════════════
@memoize(ttl=TTL_CORTO)
def kpis_resumen():
    """KPIs de cabecera del dashboard."""
    total = Circuito.objects.count()
    afectados = Circuito.objects.filter(estado='afectado').count()
    alerta_activa = AlertaMasiva.objects.filter(activo=True).exists()

    return {
        'total_circuitos': total,
        'afectados_ahora': afectados,
        'porcentaje_afectados': round(afectados * 100 / total, 1) if total else 0,
        'en_servicio': total - afectados,
        'alerta_activa': alerta_activa,
        'total_eventos': EventoCircuito.objects.count(),
    }