from django.shortcuts import render, get_object_or_404
from django.core.serializers.json import DjangoJSONEncoder
from django.contrib.auth.decorators import login_required
from django.db.models import Prefetch

from django.utils import timezone
import folium
import json

import hashlib
from datetime import timedelta

from django.http import JsonResponse
from django.views.decorators.http import require_POST

from folium.features import DivIcon

from .models import Circuito, EventoCircuito, AlertaMasiva, ReporteUsuario, ReporteDiscrepancia
from .services.cuadriculas import obtener_poligono, geojson_a_leaflet






# ═══════════════════════════════════════════════════════════════
# MAPA
# ═══════════════════════════════════════════════════════════════
import branca.element
from branca.element import Figure, MacroElement
from jinja2 import Template as JinjaTemplate
import folium
from folium.features import DivIcon
from django.contrib.auth.decorators import login_required
from django.shortcuts import render


# ── Script que se inyecta dentro del HTML de Folium ────────────
# Detecta cambios de tamaño del div del mapa (rotación, barra de
# direcciones, teclado virtual, etc.) y avisa a Leaflet.
JS_INVALIDATE = """
<script>
(function () {
    function attach() {
        var mapEl = document.querySelector('.folium-map');
        if (!mapEl) { setTimeout(attach, 100); return; }

        // Folium registra el objeto Leaflet en window[mapEl.id]
        var mapObj = window[mapEl.id];
        if (!mapObj) { setTimeout(attach, 100); return; }

        function revalidate() {
            setTimeout(function () { mapObj.invalidateSize(); }, 150);
        }

        window.addEventListener('resize', revalidate);
        window.addEventListener('orientationchange', revalidate);
        document.addEventListener('visibilitychange', revalidate);
        window.addEventListener('load', revalidate);

        if (window.ResizeObserver) {
            new ResizeObserver(revalidate).observe(mapEl);
        }
    }
    attach();
})();
</script>
"""


@login_required
def mapa_circuitos(request):
    circuitos = Circuito.objects.exclude(
        latitud__isnull=True
    ).exclude(longitud__isnull=True)

    # ── Mapa base ─────────────────────────────────────────────
    mapa = folium.Map(
        location=[23.1136, -82.3666],
        zoom_start=12,
        tiles=None,
        width="100%",
        height="100%",
    )

    # ── Capas de tiles ────────────────────────────────────────
    folium.TileLayer(
        tiles='https://{s}.tile.openstreetmap.de/{z}/{x}/{y}.png',
        attr='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
        subdomains='abc',
        name='OSM Alemania',
        max_zoom=19,
    ).add_to(mapa)

    folium.TileLayer(
        tiles='https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png',
        attr='Map data: &copy; OSM contributors, SRTM | Style: &copy; OpenTopoMap (CC-BY-SA)',
        subdomains='abc',
        name='OpenTopoMap',
        max_zoom=17,
    ).add_to(mapa)

    # ── Grupos ────────────────────────────────────────────────
    grupo_afectados = folium.FeatureGroup(name='🔴 Afectados', show=True)
    grupo_servicio  = folium.FeatureGroup(name='🟢 En servicio', show=True)
    grupo_etiquetas = folium.FeatureGroup(name='🏷️ Etiquetas', show=True)

    for c in circuitos:
        geojson = obtener_poligono(c)
        if not geojson:
            continue

        puntos = geojson_a_leaflet(geojson)
        if not puntos:
            continue

        if c.estado == 'afectado':
            color_borde, color_relleno, opacidad = '#c62828', '#ef5350', 0.30
            grupo = grupo_afectados
        else:
            color_borde, color_relleno, opacidad = '#2e7d32', '#66bb6a', 0.20
            grupo = grupo_servicio

        direccion_corta = (c.direccion[:100] + '…') if len(c.direccion) > 100 else c.direccion
        popup_html = (
            f'<div style="font-family: sans-serif; font-size: 13px; min-width: 260px;">'
            f'<b style="font-size: 15px;">{c.codigo}</b><br>'
            f'<small style="color: #666;">{direccion_corta}</small><br><br>'
            f'<b>Estado:</b> {c.get_estado_display()}<br>'
            f'<b>Afectaciones:</b> {c.total_afectaciones}<br>'
            f'<b>Min acumulados:</b> {c.total_minutos_afectado}<br><br>'
            f'<a href="/circuitos/c/{c.codigo}/" '
            f'style="color:#1976d2;font-weight:600;text-decoration:none;" '
            f'target="_blank">Ver detalle completo →</a>'
            f'</div>'
        )

        folium.Polygon(
            locations=puntos,
            color=color_borde,
            weight=1.5,
            fill=True,
            fillColor=color_relleno,
            fillOpacity=opacidad,
            popup=folium.Popup(popup_html, max_width=340),
            tooltip=c.codigo,
        ).add_to(grupo)

        folium.Marker(
            location=[float(c.latitud), float(c.longitud)],
            icon=DivIcon(
                html=(
                    f'<div style="font-family: sans-serif; font-size: 10px; '
                    f'font-weight: 700; color: #212121; '
                    f'text-shadow: 1px 1px 0 white, -1px -1px 0 white, '
                    f'1px -1px 0 white, -1px 1px 0 white; '
                    f'text-align: center; white-space: nowrap; '
                    f'pointer-events: none;">{c.codigo}</div>'
                ),
                icon_size=(60, 14),
                icon_anchor=(30, 7),
            ),
        ).add_to(grupo_etiquetas)

    grupo_afectados.add_to(mapa)
    grupo_servicio.add_to(mapa)
    grupo_etiquetas.add_to(mapa)

    folium.LayerControl(collapsed=False).add_to(mapa)

    # ── Leyenda flotante ──────────────────────────────────────
    leyenda_html = '''
    <div style="
        position: fixed; bottom: 30px; left: 30px; z-index: 9999;
        background: white; padding: 10px 14px; border-radius: 6px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.2);
        font-family: sans-serif; font-size: 13px;
    ">
        <b>Estado de circuitos</b><br>
        <span style="display:inline-block;width:14px;height:14px;
              background:#ef5350;border:1px solid #c62828;
              margin-right:6px;vertical-align:middle;"></span> Afectado<br>
        <span style="display:inline-block;width:14px;height:14px;
              background:#66bb6a;border:1px solid #2e7d32;
              margin-right:6px;vertical-align:middle;"></span> En servicio
    </div>
    '''
    mapa.get_root().html.add_child(folium.Element(leyenda_html))

    # ══════════════════════════════════════════════════════════
    # CLAVE: envolver el mapa en un Figure con altura 100%
    # y añadir el script de invalidateSize al HTML final.
    # ══════════════════════════════════════════════════════════
    fig = Figure(width="100%", height="100%")
    fig.add_child(mapa)

    # Añadimos el JS justo antes de </body> del HTML generado
    html = fig.render()
    html = html.replace("</body>", JS_INVALIDATE + "</body>")

    context = {
        "map_html": html,
        "total": circuitos.count(),
    }
    return render(request, "circuitos/mapa.html", context)


# ═══════════════════════════════════════════════════════════════
# LISTA
# ═══════════════════════════════════════════════════════════════
def lista_circuitos(request):
    """
    Tabla filtrable de circuitos. Carga todos los datos y deja
    el filtrado/ordenado al navegador vía JavaScript.
    """
    eventos_ordenados = EventoCircuito.objects.select_related(
        'mensaje'
    ).order_by('-fecha_mensaje')

    circuitos = Circuito.objects.prefetch_related(
        Prefetch('eventos', queryset=eventos_ordenados, to_attr='_eventos_ord')
    ).order_by('codigo')

    # ── Construir el payload JSON para el frontend ────────────
    datos = []
    for c in circuitos:
        ultimo_evento = c._eventos_ord[0] if c._eventos_ord else None

        ultimo = None
        if ultimo_evento:
            msg = ultimo_evento.mensaje
            texto = msg.texto or ''
            ultimo = {
                'tipo': ultimo_evento.tipo,
                'fecha': ultimo_evento.fecha_mensaje.isoformat() if ultimo_evento.fecha_mensaje else None,
                'texto': texto,
                'preview': (texto[:180] + '…') if len(texto) > 180 else texto,
                'telegram_id': msg.telegram_id,
                'enlace': msg.enlace,
            }

        datos.append({
            'codigo': c.codigo,
            'estado': c.estado,
            'estado_display': c.get_estado_display(),
            'municipio': c.municipio or '',
            'subestacion': c.subestacion or '',
            'direccion': c.direccion or '',
            'total_afectaciones': c.total_afectaciones,
            'total_minutos_afectado': c.total_minutos_afectado,
            'total_horas_afectado': round(c.total_minutos_afectado / 60, 1),
            'afectacion_activa': c.afectacion_activa,
            'servicio_activo': c.servicio_activo,
            'afectacion_inicio_msg': c.afectacion_inicio_msg.isoformat() if c.afectacion_inicio_msg else None,
            'afectacion_duracion_msg_min': c.afectacion_duracion_msg_min,
            'afectacion_duracion_contenido_min': c.afectacion_duracion_contenido_min,
            'servicio_duracion_msg_min': c.servicio_duracion_msg_min,
            'servicio_duracion_contenido_min': c.servicio_duracion_contenido_min,
            'ultima_mencion': c.ultima_mencion.isoformat() if c.ultima_mencion else None,
            'ultimo_evento': ultimo,
        })

    # ── Municipios únicos para el filtro ──────────────────────
    municipios = sorted(set(
        Circuito.objects.exclude(municipio='')
        .values_list('municipio', flat=True)
        .distinct()
    ))

    context = {
        'total': len(datos),
        'total_afectados': sum(1 for d in datos if d['estado'] == 'afectado'),
        'municipios': municipios,
        'data_json': json.dumps(datos, cls=DjangoJSONEncoder, ensure_ascii=False),
    }
    return render(request, 'circuitos/lista.html', context)


# ═══════════════════════════════════════════════════════════════
# DETALLE
# ═══════════════════════════════════════════════════════════════
def detalle_circuito(request, codigo):
    """
    Página de detalle completa de un circuito:
      - Info general
      - Mapa mini con su geometría
      - Estadísticas
      - Ciclo actual
      - Timeline de eventos
    """
    circuito = get_object_or_404(Circuito, codigo__iexact=codigo)

    # ── Mini-mapa con la geometría del circuito ──────────────
    mini_mapa = None
    if circuito.latitud and circuito.longitud:
        mini_mapa = folium.Map(
            location=[float(circuito.latitud), float(circuito.longitud)],
            zoom_start=15,
            tiles=None,
        )

        # ── Capa 1: OSM Alemania (por defecto) ────────────────
        folium.TileLayer(
            tiles='https://{s}.tile.openstreetmap.de/{z}/{x}/{y}.png',
            attr='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
            subdomains='abc',
            name='OSM Alemania',
            max_zoom=19,
        ).add_to(mini_mapa)

        # ── Capa 2: OpenTopoMap ───────────────────────────────
        folium.TileLayer(
            tiles='https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png',
            attr='Map data: &copy; OSM contributors, SRTM | Style: &copy; OpenTopoMap (CC-BY-SA)',
            subdomains='abc',
            name='OpenTopoMap',
            max_zoom=17,
        ).add_to(mini_mapa)

        # ── Polígono del circuito ─────────────────────────────
        geojson = obtener_poligono(circuito)
        if geojson:
            puntos = geojson_a_leaflet(geojson)
            if puntos:
                color = '#c62828' if circuito.estado == 'afectado' else '#2e7d32'
                relleno = '#ef5350' if circuito.estado == 'afectado' else '#66bb6a'

                folium.Polygon(
                    locations=puntos,
                    color=color,
                    weight=2,
                    fill=True,
                    fillColor=relleno,
                    fillOpacity=0.35,
                    popup=circuito.codigo,
                    tooltip=circuito.codigo,
                ).add_to(mini_mapa)

                # Ajustar zoom a los límites del polígono
                lats = [p[0] for p in puntos]
                lngs = [p[1] for p in puntos]
                mini_mapa.fit_bounds([
                    [min(lats), min(lngs)],
                    [max(lats), max(lngs)],
                ])

        # ── Control de capas (colapsado para no ocupar espacio) ─
        folium.LayerControl(collapsed=True).add_to(mini_mapa)

    # ── Eventos ordenados cronológicamente descendente ────────
    eventos = (
        circuito.eventos
        .select_related('mensaje')
        .order_by('-fecha_mensaje')[:100]
    )

    # ── Estadísticas agregadas de eventos ─────────────────────
    total_afectaciones_eventos = circuito.eventos.filter(tipo='afectacion').count()
    total_restablecimientos = circuito.eventos.filter(tipo='restablecimiento').count()
    hace_12h = timezone.now() - timedelta(hours=12)
    reportes_discrepancia_ips = (
        ReporteDiscrepancia.objects
        .filter(circuito=circuito, creado_en__gte=hace_12h)
        .values('ip_hash')
        .distinct()
        .count()
    )

    context = {
        'circuito': circuito,
        'mini_mapa_html': mini_mapa._repr_html_() if mini_mapa else None,
        'eventos': eventos,
        'total_afectaciones_eventos': total_afectaciones_eventos,
        'total_restablecimientos': total_restablecimientos,
        'tiene_geojson': circuito.geometria_geojson is not None,
        'reportes_discrepancia_ips': reportes_discrepancia_ips,
    }
    return render(request, 'circuitos/detalle.html', context)


import hashlib
from datetime import timedelta
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_protect


def _hash_ip(request) -> str:
    ip = (
        request.META.get('HTTP_X_FORWARDED_FOR', '').split(',')[0].strip()
        or request.META.get('REMOTE_ADDR', '')
    )
    return hashlib.sha256(f'{ip}:eelh_salt_v1'.encode()).hexdigest()[:32]


@require_POST
@csrf_protect
def reportar_estado(request):
    """Recibe un reporte anónimo del estado de un circuito."""
    codigo = (request.POST.get('circuito') or '').strip().upper()
    estado = (request.POST.get('estado') or '').strip()
    comentario = (request.POST.get('comentario') or '').strip()[:300]

    if estado not in ('afectado', 'en_servicio', 'intermitente'):
        return JsonResponse({'error': 'Estado inválido'}, status=400)

    try:
        circuito = Circuito.objects.get(codigo__iexact=codigo)
    except Circuito.DoesNotExist:
        return JsonResponse(
            {'error': f'Circuito "{codigo}" no encontrado'}, status=404,
        )

    ip_hash = _hash_ip(request)

    # ── Rate limiting: 1 reporte por circuito cada 10 min por IP ──
    hace_10min = timezone.now() - timedelta(minutes=10)
    if ReporteUsuario.objects.filter(
        ip_hash=ip_hash, circuito=circuito, creado_en__gte=hace_10min,
    ).exists():
        return JsonResponse(
            {'error': 'Ya reportaste este circuito hace menos de 10 min'},
            status=429,
        )

    # ── Rate limiting global: 1 reporte por IP cada 30 segundos ───
    hace_30s = timezone.now() - timedelta(seconds=30)
    if ReporteUsuario.objects.filter(
        ip_hash=ip_hash, creado_en__gte=hace_30s,
    ).exists():
        return JsonResponse(
            {'error': 'Espera 30 segundos entre reportes'}, status=429,
        )

    alerta = AlertaMasiva.objects.filter(activo=True).first()

    reporte = ReporteUsuario.objects.create(
        circuito=circuito,
        alerta=alerta,
        estado=estado,
        comentario=comentario,
        ip_hash=ip_hash,
        user_agent=request.META.get('HTTP_USER_AGENT', '')[:255],
    )

    # Actualizar estado comunitario del circuito
    circuito.estado_comunitario = estado
    circuito.estado_comunitario_actualizado_en = timezone.now()
    circuito.reportes_usuarios_total += 1
    circuito.save(update_fields=[
        'estado_comunitario',
        'estado_comunitario_actualizado_en',
        'reportes_usuarios_total',
    ])

    if alerta:
        AlertaMasiva.objects.filter(pk=alerta.pk).update(
            reportes_usuarios=alerta.reportes_usuarios + 1,
        )

    return JsonResponse({
        'ok': True,
        'reporte_id': reporte.id,
        'circuito': circuito.codigo,
        'estado': estado,
        'timestamp': timezone.now().isoformat(),
    })


# ── Configuración ────────────────────────────────────────────
UMBRAL_REPORTES_DISCREPANCIA = 5     # IPs únicas necesarias
VENTANA_REPORTES_HORAS = 12          # ventana de conteo
RATE_LIMIT_IP_HORAS = 12             # 1 reporte por IP por circuito cada N h


def _hash_ip_discrepancia(request) -> str:
    ip = (
        request.META.get('HTTP_X_FORWARDED_FOR', '').split(',')[0].strip()
        or request.META.get('REMOTE_ADDR', '')
    )
    return hashlib.sha256(f'{ip}:discrepancia_v1'.encode()).hexdigest()[:32]


@require_POST
def reportar_discrepancia(request, codigo):
    """Recibe un reporte de discrepancia para un circuito específico."""
    from .models import Circuito, ReporteDiscrepancia

    circuito = get_object_or_404(Circuito, codigo__iexact=codigo)

    # ── Verificar estado actual ─────────────────────────────
    if circuito.estado != 'en_servicio':
        return JsonResponse(
            {'error': 'Este circuito ya figura como afectado.'},
            status=400,
        )

    estado_reportado = (request.POST.get('estado') or 'sin_luz').strip()
    if estado_reportado not in ('sin_luz', 'intermitente'):
        estado_reportado = 'sin_luz'

    comentario = (request.POST.get('comentario') or '').strip()[:300]

    ip_hash = _hash_ip_discrepancia(request)

    # ── Rate limiting por IP ────────────────────────────────
    hace_12h = timezone.now() - timedelta(hours=RATE_LIMIT_IP_HORAS)
    if ReporteDiscrepancia.objects.filter(
        circuito=circuito,
        ip_hash=ip_hash,
        creado_en__gte=hace_12h,
    ).exists():
        return JsonResponse(
            {'error': f'Ya reportaste este circuito en las últimas {RATE_LIMIT_IP_HORAS}h'},
            status=429,
        )

    # ── Crear reporte ───────────────────────────────────────
    reporte = ReporteDiscrepancia.objects.create(
        circuito=circuito,
        estado_reportado=estado_reportado,
        comentario=comentario,
        ip_hash=ip_hash,
        user_agent=request.META.get('HTTP_USER_AGENT', '')[:255],
    )

    # ── Contar IPs únicas en la ventana ─────────────────────
    hace_ventana = timezone.now() - timedelta(hours=VENTANA_REPORTES_HORAS)
    ips_unicas = (
        ReporteDiscrepancia.objects
        .filter(circuito=circuito, creado_en__gte=hace_ventana)
        .values('ip_hash')
        .distinct()
        .count()
    )

    cambio = False

    # ── Cambiar estado si se alcanza el umbral ──────────────
    if ips_unicas >= UMBRAL_REPORTES_DISCREPANCIA:
        # Marcar estos reportes como causantes del cambio
        ReporteDiscrepancia.objects.filter(
            circuito=circuito,
            creado_en__gte=hace_ventana,
        ).update(cambio_estado=True)

        # Cerrar ciclo de servicio si estaba abierto
        if circuito.servicio_activo and circuito.servicio_inicio_msg:
            circuito.servicio_fin_msg = timezone.now()
            circuito.servicio_duracion_msg_min = int(
                (timezone.now() - circuito.servicio_inicio_msg).total_seconds() / 60
            )
            circuito.servicio_activo = False

        # Abrir ciclo de afectación SIN mensaje oficial
        if not circuito.afectacion_activa:
            circuito.afectacion_inicio_msg = timezone.now()
            circuito.afectacion_activa = True
            circuito.total_afectaciones += 1

        # Cambiar estado
        circuito.estado = 'afectado'
        circuito.estado_origen = 'reportes_usuarios'
        circuito.estado_actualizado_en = timezone.now()

        circuito.save(update_fields=[
            'estado', 'estado_origen', 'estado_actualizado_en',
            'afectacion_activa', 'afectacion_inicio_msg',
            'servicio_activo', 'servicio_fin_msg', 'servicio_duracion_msg_min',
            'total_afectaciones',
        ])
        cambio = True

    return JsonResponse({
        'ok': True,
        'reporte_id': reporte.id,
        'circuito': circuito.codigo,
        'ips_unicas': ips_unicas,
        'umbral': UMBRAL_REPORTES_DISCREPANCIA,
        'cambio_estado': cambio,
        'estado_actual': circuito.estado,
    })