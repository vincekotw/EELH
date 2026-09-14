"""
Restaura geojson, coordenadas manuales y notas desde el backup.
"""
import json
from apps.circuitos.models import Circuito

with open('scripts/_backup_geojson.json', encoding='utf-8') as f:
    backup = json.load(f)

restaurados = 0
no_encontrados = []

for codigo, datos in backup.items():
    try:
        c = Circuito.objects.get(codigo=codigo)
    except Circuito.DoesNotExist:
        no_encontrados.append(codigo)
        continue

    if datos.get('geometria_geojson'):
        c.geometria_geojson = datos['geometria_geojson']
    if datos.get('usar_cuadrado_default') is not None:
        c.usar_cuadrado_default = datos['usar_cuadrado_default']
    if datos.get('latitud') is not None:
        c.latitud = datos['latitud']
    if datos.get('longitud') is not None:
        c.longitud = datos['longitud']
    if datos.get('municipio') is not None:
        c.municipio = datos['municipio']
    if datos.get('notas'):
        c.notas = datos['notas']


    c.save(update_fields=[
        'geometria_geojson', 'usar_cuadrado_default',
        'latitud', 'longitud', 'municipio', 'notas',
    ])
    restaurados += 1

print(f'Restaurados: {restaurados}')
if no_encontrados:
    print(f'No encontrados: {no_encontrados}')