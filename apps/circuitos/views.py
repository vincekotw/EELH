from django.shortcuts import render, get_object_or_404
from django.core.serializers.json import DjangoJSONEncoder
from django.db.models import Prefetch

import folium
import json

from folium.features import DivIcon

from .models import Circuito, EventoCircuito
from .services.cuadriculas import obtener_poligono, geojson_a_leaflet


# ═══════════════════════════════════════════════════════════════
# MAPA
# ═══════════════════════════════════════════════════════════════
def mapa_circuitos(request):
    circuitos = Circuito.objects.exclude(
        latitud__isnull=True
    ).exclude(longitud__isnull=True)

    # ── Mapa base ─────────────────────────────────────────────
    mapa = folium.Map(
        location=[23.1136, -82.3666],
        zoom_start=12,
        tiles=None,
    )

    # ══════════════════════════════════════════════════════════
    # Capas de tiles — solo proveedores accesibles desde Cuba
    # ══════════════════════════════════════════════════════════

    # ── Capa 1: OSM Alemania (por defecto) ────────────────────
    folium.TileLayer(
        tiles='https://{s}.tile.openstreetmap.de/{z}/{x}/{y}.png',
        attr='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
        subdomains='abc',
        name='OSM Alemania',
        max_zoom=19,
    ).add_to(mapa)

    # ── Capa 2: OpenTopoMap (relieve) ─────────────────────────
    folium.TileLayer(
        tiles='https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png',
        attr='Map data: &copy; OSM contributors, SRTM | Style: &copy; OpenTopoMap (CC-BY-SA)',
        subdomains='abc',
        name='OpenTopoMap',
        max_zoom=17,
    ).add_to(mapa)

    # ── Grupos de capas por estado ────────────────────────────
    grupo_afectados = folium.FeatureGroup(name='🔴 Afectados', show=True)
    grupo_servicio = folium.FeatureGroup(name='🟢 En servicio', show=True)
    grupo_etiquetas = folium.FeatureGroup(name='🏷️ Etiquetas', show=True)

    for c in circuitos:
        geojson = obtener_poligono(c)
        if not geojson:
            continue

        puntos = geojson_a_leaflet(geojson)
        if not puntos:
            continue

        # ── Colores según estado ─────────────────────────────
        if c.estado == 'afectado':
            color_borde = '#c62828'
            color_relleno = '#ef5350'
            opacidad = 0.30
            grupo = grupo_afectados
        else:
            color_borde = '#2e7d32'
            color_relleno = '#66bb6a'
            opacidad = 0.20
            grupo = grupo_servicio

        # ── Popup con detalles ───────────────────────────────
        direccion_corta = (c.direccion[:100] + '…') if len(c.direccion) > 100 else c.direccion
        popup_html = (
            f'<div style="font-family: sans-serif; font-size: 13px; min-width: 260px;">'
            f'<b style="font-size: 15px;">{c.codigo}</b><br>'
            f'<small style="color: #666;">{direccion_corta}</small><br><br>'
            f'<b>Estado:</b> {c.get_estado_display()}<br>'
            f'<b>Afectaciones:</b> {c.total_afectaciones}<br>'
            f'<b>Min acumulados:</b> {c.total_minutos_afectado}<br><br>'
            f'<a href="/circuitos/c/{c.codigo}/" '
            f'style="color:#1976d2;font-weight:600;text-decoration:none;">'
            f'Ver detalle completo →</a>'
            f'</div>'
        )

        # ── Polígono (cuadrícula) ────────────────────────────
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

        # ── Etiqueta con el código en el centro ──────────────
        folium.Marker(
            location=[float(c.latitud), float(c.longitud)],
            icon=DivIcon(
                html=(
                    f'<div style="'
                    f'font-family: sans-serif; '
                    f'font-size: 10px; '
                    f'font-weight: 700; '
                    f'color: #212121; '
                    f'text-shadow: 1px 1px 0 white, -1px -1px 0 white, '
                    f'1px -1px 0 white, -1px 1px 0 white; '
                    f'text-align: center; '
                    f'white-space: nowrap; '
                    f'pointer-events: none;'
                    f'">{c.codigo}</div>'
                ),
                icon_size=(60, 14),
                icon_anchor=(30, 7),
            ),
        ).add_to(grupo_etiquetas)

    # ── Añadir grupos al mapa ─────────────────────────────────
    grupo_afectados.add_to(mapa)
    grupo_servicio.add_to(mapa)
    grupo_etiquetas.add_to(mapa)

    # ── Control de capas ──────────────────────────────────────
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

    context = {
        'map_html': mapa._repr_html_(),
        'total': circuitos.count(),
    }
    return render(request, 'circuitos/mapa.html', context)


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

    context = {
        'circuito': circuito,
        'mini_mapa_html': mini_mapa._repr_html_() if mini_mapa else None,
        'eventos': eventos,
        'total_afectaciones_eventos': total_afectaciones_eventos,
        'total_restablecimientos': total_restablecimientos,
        'tiene_geojson': circuito.geometria_geojson is not None,
    }
    return render(request, 'circuitos/detalle.html', context)