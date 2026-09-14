"""
Recorre todos los circuitos y les asigna coordenadas usando la
estrategia híbrida (override manual + diccionario + Nominatim).
"""

from apps.circuitos.models import Circuito
from apps.circuitos.services.geocodificador import geocodificar


USAR_NOMINATIM = True


print('═' * 60)
print('  GEOCODIFICACIÓN HÍBRIDA')
print('═' * 60)

total = Circuito.objects.count()
print(f'Total circuitos: {total}\n')

stats = {
    'manual': 0,
    'diccionario': 0,
    'nominatim': 0,
    'sin_resultado': 0,
    'ya_tenia_coords': 0,
}

sin_resultado = []

for circuito in Circuito.objects.order_by('codigo'):
    if circuito.latitud and circuito.longitud:
        stats['ya_tenia_coords'] += 1
        continue

    lat, lng, metodo = geocodificar(
        circuito.direccion,
        codigo=circuito.codigo,
        usar_nominatim=USAR_NOMINATIM,
    )

    if metodo == 'sin_resultado':
        stats['sin_resultado'] += 1
        sin_resultado.append((circuito.codigo, circuito.direccion[:60] or '(sin dirección)'))
        print(f'  ❌ {circuito.codigo:8s}  sin resultado')
        continue

    circuito.latitud = lat
    circuito.longitud = lng
    circuito.save(update_fields=['latitud', 'longitud'])
    stats[metodo] += 1

    icono = {'manual': '🎯', 'diccionario': '📚', 'nominatim': '🌐'}.get(metodo, '?')
    print(f'  {icono} {circuito.codigo:8s}  {lat:.5f}, {lng:.5f}  ({metodo})')

    if metodo == 'nominatim':
        import time
        time.sleep(1)


print()
print('═' * 60)
print('  RESUMEN')
print('═' * 60)
for k, v in stats.items():
    print(f'  {k:20s} {v:3d}')

if sin_resultado:
    print(f'\n  Sin resultado ({len(sin_resultado)}):')
    for codigo, dir_corta in sin_resultado[:30]:
        print(f'    {codigo:8s}  {dir_corta}')