"""
Guarda todos los geojson + flags relacionados en un archivo JSON
para restaurarlos después de un reset.
"""
import json
from apps.circuitos.models import Circuito

backup = {}

for c in Circuito.objects.all():
    if c.geometria_geojson or not c.usar_cuadrado_default:
        backup[c.codigo] = {
            'geometria_geojson': c.geometria_geojson,
            'usar_cuadrado_default': c.usar_cuadrado_default,
            'latitud': float(c.latitud) if c.latitud else None,
            'longitud': float(c.longitud) if c.longitud else None,
            'municipio': c.municipio,
            'notas': c.notas or '',
        }

with open('scripts/_backup_geojson.json', 'w', encoding='utf-8') as f:
    json.dump(backup, f, ensure_ascii=False, indent=2)

print(f'Circuitos con geojson o config personalizada: {len(backup)}')
for codigo in backup:
    tiene_geo = 'con geojson' if backup[codigo]['geometria_geojson'] else 'solo config'
    print(f'  {codigo}: {tiene_geo}')