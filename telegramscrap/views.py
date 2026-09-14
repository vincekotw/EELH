from django.shortcuts import render
from datetime import timedelta
from django.utils import timezone
from django.db.models import Count, Sum, Q
from apps.circuitos.models import Circuito, EventoCircuito


def home(request):
    """
    Página de inicio con KPIs, últimas afectaciones y top circuitos.
    """
    circuitos = Circuito.objects.all()
    total = circuitos.count()
    afectados = circuitos.filter(estado='afectado').count()
    en_servicio = circuitos.filter(estado='en_servicio').count()

    # ── KPIs globales ────────────────────────────────────────
    agg = circuitos.aggregate(
        total_afectaciones=Sum('total_afectaciones'),
        total_minutos=Sum('total_minutos_afectado'),
    )
    total_afectaciones = agg['total_afectaciones'] or 0
    total_minutos = agg['total_minutos'] or 0

    # ── Últimos 7 días de actividad ──────────────────────────
    desde = timezone.now() - timedelta(days=7)
    eventos_7d = EventoCircuito.objects.filter(
        fecha_mensaje__gte=desde,
        tipo='afectacion',
    ).count()

    # ── Últimos eventos con mensaje ───────────────────────────
    ultimos_eventos = (
        EventoCircuito.objects
        .select_related('circuito', 'mensaje')
        .filter(tipo__in=['afectacion', 'restablecimiento'])
        .order_by('-fecha_mensaje')[:15]
    )

    # ── Top 10 circuitos más castigados ──────────────────────
    top_circuitos = circuitos.order_by('-total_minutos_afectado')[:10]

    # ── Top 10 afectados actualmente (más tiempo llevan sin luz) ─
    afectados_actuales = (
        circuitos
        .filter(afectacion_activa=True, afectacion_inicio_msg__isnull=False)
        .order_by('afectacion_inicio_msg')[:10]
    )

    # ── Circuitos por municipio (top 8) ──────────────────────
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

    context = {
        'total': total,
        'afectados': afectados,
        'en_servicio': en_servicio,
        'porcentaje_afectados': round(afectados * 100 / total, 1) if total else 0,
        'total_afectaciones': total_afectaciones,
        'total_horas': round(total_minutos / 60, 1),
        'eventos_7d': eventos_7d,
        'ultimos_eventos': ultimos_eventos,
        'top_circuitos': top_circuitos,
        'afectados_actuales': afectados_actuales,
        'por_municipio': por_municipio,
    }
    return render(request, 'home.html', context)