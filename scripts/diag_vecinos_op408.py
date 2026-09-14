from math import radians, sin, cos, sqrt, atan2
from apps.circuitos.models import Circuito


def distancia_km(lat1, lng1, lat2, lng2):
    """Distancia aproximada en km entre dos puntos (Haversine)."""
    R = 6371
    dlat = radians(lat2 - lat1)
    dlng = radians(lng2 - lng1)
    a = sin(dlat/2)**2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlng/2)**2
    return R * 2 * atan2(sqrt(a), sqrt(1-a))


# ── Centro del polígono de OP408 ──────────────────────────────
geo = Circuito.objects.get(codigo='OP408').geometria_geojson
coords = geo['features'][0]['geometry']['coordinates'][0]
lats = [c[1] for c in coords]
lngs = [c[0] for c in coords]
lat_centro = sum(lats) / len(lats)
lng_centro = sum(lngs) / len(lngs)

print(f'Centro OP408: lat={lat_centro:.6f}, lng={lng_centro:.6f}')
print()

# ── Buscar circuitos cerca (radio 2 km) ───────────────────────
print('Circuitos a menos de 2 km de OP408:')
cercanos = []
for c in Circuito.objects.exclude(codigo='OP408'):
    if c.latitud is None or c.longitud is None:
        continue
    d = distancia_km(lat_centro, lng_centro, float(c.latitud), float(c.longitud))
    if d <= 2.0:
        cercanos.append((d, c))

cercanos.sort(key=lambda x: x[0])

for d, c in cercanos:
    tiene_geo = '📐' if c.geometria_geojson else '⬜'
    print(f'  {tiene_geo} {c.codigo:8s}  {d:.3f} km  '
          f'({c.latitud}, {c.longitud})  estado={c.estado}')

print(f'\nTotal vecinos: {len(cercanos)}')