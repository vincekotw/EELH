"""
Genera cuadrículas (polígonos rectangulares) para los circuitos a
partir de su punto central, y las serializa como GeoJSON.
"""

from math import cos, radians


# Tamaño por defecto de la cuadrícula (en kilómetros)
ANCHO_DEFECTO_KM = 1.2
ALTO_DEFECTO_KM = 1.2


def _km_a_grados_lat(km: float) -> float:
    """1 grado de latitud ≈ 111 km (constante en toda la Tierra)."""
    return km / 111.0


def _km_a_grados_lng(km: float, latitud: float) -> float:
    """
    1 grado de longitud depende de la latitud.
    En La Habana (~23°N), 1° lng ≈ 102 km.
    Fórmula general: km / (111 * cos(lat))
    """
    return km / (111.0 * cos(radians(latitud)))


def generar_cuadrado(
    lat: float,
    lng: float,
    ancho_km: float = ANCHO_DEFECTO_KM,
    alto_km: float = ALTO_DEFECTO_KM,
) -> dict:
    """
    Devuelve un GeoJSON Polygon (dict) que representa un rectángulo
    centrado en (lat, lng) con el ancho y alto indicados.

    Estructura GeoJSON estándar:
      {'type': 'Polygon', 'coordinates': [[[lng, lat], ...]]}
    """
    dlat = _km_a_grados_lat(alto_km) / 2
    dlng = _km_a_grados_lng(ancho_km, lat) / 2

    # Cuatro esquinas en sentido antihorario (empezando por SO)
    esquinas = [
        [lng - dlng, lat - dlat],   # SO (suroeste)
        [lng + dlng, lat - dlat],   # SE (sureste)
        [lng + dlng, lat + dlat],   # NE (noreste)
        [lng - dlng, lat + dlat],   # NO (noroeste)
        [lng - dlng, lat - dlat],   # cierre del anillo
    ]

    return {
        'type': 'Polygon',
        'coordinates': [esquinas],
    }


def _extraer_polygon_de_geojson(geo) -> dict | None:
    """
    Normaliza cualquier GeoJSON válido a un dict {'type': 'Polygon', 'coordinates': [...]}.
    Acepta:
      - Polygon directo
      - Feature que contenga Polygon
      - FeatureCollection con al menos un Feature Polygon
      - Lista de [lat, lng] sin estructura
    """
    if not geo:
        return None

    # Caso 1: Polygon directo
    if isinstance(geo, dict) and geo.get('type') == 'Polygon':
        return geo

    # Caso 2: Feature
    if isinstance(geo, dict) and geo.get('type') == 'Feature':
        geometry = geo.get('geometry')
        if isinstance(geometry, dict) and geometry.get('type') == 'Polygon':
            return geometry

    # Caso 3: FeatureCollection
    if isinstance(geo, dict) and geo.get('type') == 'FeatureCollection':
        features = geo.get('features') or []
        for feat in features:
            if not isinstance(feat, dict):
                continue
            geometry = feat.get('geometry')
            if isinstance(geometry, dict) and geometry.get('type') == 'Polygon':
                return geometry

    # Caso 4: Lista plana [[lng, lat], [lng, lat], ...] o [[lat, lng], ...]
    if isinstance(geo, list) and len(geo) >= 3:
        # Detectar orden: si el primer valor está entre -90 y 90, asumimos [lat, lng]
        primero = geo[0]
        if isinstance(primero, list) and len(primero) == 2:
            if -90 <= primero[0] <= 90 and -180 <= primero[1] <= 180:
                # Podría ser [lat, lng]. Convertimos a [lng, lat]
                coords = [[p[1], p[0]] for p in geo]
                # Aseguramos cierre del anillo
                if coords[0] != coords[-1]:
                    coords.append(coords[0])
                return {'type': 'Polygon', 'coordinates': [coords]}

    return None


def obtener_poligono(circuito) -> dict | None:
    """
    Devuelve el polígono del circuito como GeoJSON Polygon normalizado.
    Prioridad:
      1. `geometria_geojson` si existe.
      2. Cuadrado por defecto SOLO si usar_cuadrado_default=True.
      3. None en cualquier otro caso.
    """
    # 1. GeoJSON personalizado
    geo_normalizado = _extraer_polygon_de_geojson(circuito.geometria_geojson)
    if geo_normalizado:
        return geo_normalizado

    # 2. Cuadrado por defecto — solo si está permitido
    if not getattr(circuito, 'usar_cuadrado_default', True):
        return None

    if circuito.latitud is None or circuito.longitud is None:
        return None

    return generar_cuadrado(float(circuito.latitud), float(circuito.longitud))


def geojson_a_leaflet(geojson: dict) -> list[list[float]]:
    """
    Convierte un GeoJSON Polygon a lista [[lat, lng], ...] para Folium.
    """
    if not geojson or geojson.get('type') != 'Polygon':
        return []

    # Puede tener múltiples anillos (exterior + agujeros). Usamos el exterior.
    anillos = geojson.get('coordinates') or []
    if not anillos:
        return []

    exterior = anillos[0]
    # GeoJSON usa [lng, lat] → Leaflet usa [lat, lng]
    return [[punto[1], punto[0]] for punto in exterior]