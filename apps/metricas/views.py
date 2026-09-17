"""
Vistas del dashboard de métricas. Solo accesible para usuarios
autenticados con sesión activa.
"""

import logging

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET

from .services import calculador


logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════
# VISTA PRINCIPAL
# ═══════════════════════════════════════════════════════════════
@login_required
def dashboard(request):
    """
    Renderiza el esqueleto del dashboard. Los KPIs se calculan
    aquí (rápido). El resto se carga vía AJAX.
    """
    kpis = calculador.kpis_resumen()
    return render(request, 'metricas/dashboard.html', {
        'kpis': kpis,
    })


# ═══════════════════════════════════════════════════════════════
# ENDPOINTS AJAX (uno por sección)
# ═══════════════════════════════════════════════════════════════
def _ajax(view_func):
    """Decorador común: login + GET + manejo de errores."""
    @login_required
    @require_GET
    def wrapper(request):
        try:
            data = view_func(request)
            return JsonResponse({'ok': True, 'data': data})
        except Exception as e:
            logger.exception('Error en métrica %s', view_func.__name__)
            return JsonResponse(
                {'ok': False, 'error': str(e)}, status=500,
            )
    wrapper.__name__ = view_func.__name__
    return wrapper


@_ajax
def api_tendencia(request):
    return calculador.tendencia_semanal()


@_ajax
def api_activos_hora(request):
    return calculador.circuitos_activos_por_hora(horas=24)


@_ajax
def api_media_diaria(request):
    return calculador.media_activos_por_dia(dias=10)


@_ajax
def api_rotacion_media(request):
    return calculador.rotacion_media(dias=10)


@_ajax
def api_mayor_rotacion(request):
    return calculador.circuitos_mayor_rotacion(dias=10, limite=15)


@_ajax
def api_sin_rotacion(request):
    return calculador.circuitos_sin_rotacion(dias=10)


@_ajax
def api_daf_semana(request):
    return calculador.circuitos_daf_semana()


@_ajax
def api_mas_horas_sin_servicio(request):
    return calculador.circuitos_mas_horas_sin_servicio(limite=15)


@_ajax
def api_mas_horas_servicio(request):
    return calculador.circuitos_mas_horas_servicio(limite=15)


@_ajax
def api_mttr(request):
    return calculador.mttr_por_circuito(limite=15)


@_ajax
def api_disponibilidad(request):
    return calculador.disponibilidad_por_circuito(limite=20)


@_ajax
def api_heatmap_hora(request):
    return calculador.heatmap_hora_dia(dias=10)


@_ajax
def api_top_municipios(request):
    return calculador.top_municipios(limite=12)


@_ajax
def api_estabilidad(request):
    return calculador.indice_estabilidad(limite=20)


@_ajax
def api_tiempo_entre(request):
    return calculador.tiempo_entre_afectaciones(limite=15)


@_ajax
def api_prediccion(request):
    return calculador.prediccion_proximas_horas(limite=10)


@_ajax
def api_ranking_usuarios(request):
    return calculador.ranking_usuarios(limite=15)


@_ajax
def api_alertas_historicas(request):
    return calculador.alertas_historicas(limite=20)


@_ajax
def api_cronicos(request):
    return calculador.circuitos_cronicos(limite=15)


@_ajax
def api_duracion_usuarios(request):
    return calculador.duracion_acumulada_usuarios(dias=7, limite=15)


@_ajax
def api_todo(request):
    """Carga todo en una sola llamada (usado para exportar)."""
    return {
        'tendencia': calculador.tendencia_semanal(),
        'activos_hora': calculador.circuitos_activos_por_hora(24),
        'media_diaria': calculador.media_activos_por_dia(10),
        'rotacion': calculador.rotacion_media(10),
        'mayor_rotacion': calculador.circuitos_mayor_rotacion(10, 15),
        'sin_rotacion': calculador.circuitos_sin_rotacion(10),
        'daf': calculador.circuitos_daf_semana(),
        'mas_horas_sin_servicio': calculador.circuitos_mas_horas_sin_servicio(15),
        'mas_horas_servicio': calculador.circuitos_mas_horas_servicio(15),
        'mttr': calculador.mttr_por_circuito(15),
        'disponibilidad': calculador.disponibilidad_por_circuito(20),
        'heatmap': calculador.heatmap_hora_dia(10),
        'municipios': calculador.top_municipios(12),
        'estabilidad': calculador.indice_estabilidad(20),
        'tiempo_entre': calculador.tiempo_entre_afectaciones(15),
        'prediccion': calculador.prediccion_proximas_horas(10),
        'ranking': calculador.ranking_usuarios(15),
        'alertas': calculador.alertas_historicas(20),
        'cronicos': calculador.circuitos_cronicos(15),
        'duracion_usuarios': calculador.duracion_acumulada_usuarios(7, 15),
    }