from datetime import timedelta

from django.shortcuts import render
from django.utils import timezone
from django.db.models import Sum, Count, Q

from apps.telegram_base.models import Mensaje
from apps.circuitos.models import (
    AlertaMasiva,
    Circuito,
    EventoCircuito,
    ReporteUsuario,
)


# ═══════════════════════════════════════════════════════════════
# HOME (bifurca entre modo normal y modo apagón)
# ═══════════════════════════════════════════════════════════════
def home(request):
    alerta_activa = AlertaMasiva.objects.filter(activo=True).first()

    if alerta_activa:
        return _home_modo_apagon(request, alerta_activa)
    return _home_normal(request)


# ═══════════════════════════════════════════════════════════════
# MODO NORMAL
# ═══════════════════════════════════════════════════════════════
def _home_normal(request):
    circuitos = Circuito.objects.all()
    total = circuitos.count()
    afectados = circuitos.filter(estado='afectado').count()
    en_servicio = circuitos.filter(estado='en_servicio').count()

    agg = circuitos.aggregate(
        total_afectaciones=Sum('total_afectaciones'),
        total_minutos=Sum('total_minutos_afectado'),
    )

    desde = timezone.now() - timedelta(days=7)
    eventos_7d = EventoCircuito.objects.filter(
        fecha_mensaje__gte=desde, tipo='afectacion',
    ).count()

    ultimos_eventos = (
        EventoCircuito.objects
        .select_related('circuito', 'mensaje')
        .filter(tipo__in=['afectacion', 'restablecimiento'])
        .order_by('-fecha_mensaje')[:15]
    )

    top_circuitos = circuitos.order_by('-total_minutos_afectado')[:10]

    afectados_actuales = (
        circuitos
        .filter(afectacion_activa=True, afectacion_inicio_msg__isnull=False)
        .order_by('afectacion_inicio_msg')[:10]
    )

    por_municipio = (
        circuitos
        .exclude(municipio='')
        .values('municipio')
        .annotate(
            total=Count('id'),
            afectados=Count('id', filter=Q(estado='afectado')),
        )
        .order_by('-afectados')[:8]
    )

    return render(request, 'home.html', {
        'modo': 'normal',
        'total': total,
        'afectados': afectados,
        'en_servicio': en_servicio,
        'porcentaje_afectados': round(afectados * 100 / total, 1) if total else 0,
        'total_afectaciones': agg['total_afectaciones'] or 0,
        'total_horas': round((agg['total_minutos'] or 0) / 60, 1),
        'eventos_7d': eventos_7d,
        'ultimos_eventos': ultimos_eventos,
        'top_circuitos': top_circuitos,
        'afectados_actuales': afectados_actuales,
        'por_municipio': por_municipio,
    })


# ═══════════════════════════════════════════════════════════════
# MODO APAGÓN
# ═══════════════════════════════════════════════════════════════
def _home_modo_apagon(request, alerta):
    desde_id = alerta.mensaje_deteccion.telegram_id if alerta.mensaje_deteccion else None
    hasta_id = None

    if alerta.mensaje_fin_oficial:
        hasta_id = alerta.mensaje_fin_oficial.telegram_id

    qs = Mensaje.objects.all()
    if desde_id:
        qs = qs.filter(telegram_id__gte=desde_id)
    if hasta_id:
        # Incluir algunos mensajes posteriores al fin oficial
        qs = qs.filter(telegram_id__lte=hasta_id + 10)
    elif desde_id:
        qs = qs.filter(telegram_id__lte=desde_id + 50)

    mensajes_alerta = qs.order_by('telegram_id')

    reportes_recientes = (
        ReporteUsuario.objects
        .select_related('circuito')
        .filter(alerta=alerta)
        .order_by('-creado_en')[:30]
    )

    desde_reporte = timezone.now() - timedelta(hours=2)
    circuitos_reportados = (
        Circuito.objects
        .filter(estado_comunitario_actualizado_en__gte=desde_reporte)
        .order_by('-estado_comunitario_actualizado_en')[:50]
    )

    todos_circuitos = Circuito.objects.order_by('codigo').values('codigo', 'municipio')

    return render(request, 'home.html', {
        'modo': 'apagon',
        'alerta': alerta,
        'mensajes_alerta': mensajes_alerta,
        'reportes_recientes': reportes_recientes,
        'circuitos_reportados': circuitos_reportados,
        'todos_circuitos': todos_circuitos,
        'total_reportes': alerta.reportes_usuarios,
    })

def acerca_de(request):
    """Página informativa del proyecto: uso, público objetivo, notas."""
    return render(request, "acerca_de.html")