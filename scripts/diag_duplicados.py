from django.db.models import Count
from apps.circuitos.models import Circuito


print('═' * 60)
print('  DIAGNÓSTICO DE DUPLICADOS')
print('═' * 60)

# ── 1. Circuitos con OP408 en el código ──────────────────────
print('\nCircuitos con "OP408" en el código:')
encontrados = Circuito.objects.filter(codigo__icontains='OP408')
if encontrados:
    for c in encontrados:
        print(f'  id={c.id}  codigo={c.codigo!r}  norm={c.codigo_normalizado!r}')
        print(f'    lat={c.latitud}, lng={c.longitud}')
        print(f'    tiene_geojson={c.geometria_geojson is not None}')
        print(f'    estado={c.estado}')
        print(f'    total_afectaciones={c.total_afectaciones}')
        print()
else:
    print('  Ninguno')

# ── 2. Duplicados por codigo_normalizado ─────────────────────
print('\nDuplicados por codigo_normalizado:')
duplicados = (
    Circuito.objects
    .values('codigo_normalizado')
    .annotate(n=Count('id'))
    .filter(n__gt=1)
    .order_by('-n')
)

if duplicados:
    for d in duplicados:
        print(f'  {d["codigo_normalizado"]!r}: {d["n"]} veces')
        for c in Circuito.objects.filter(codigo_normalizado=d['codigo_normalizado']):
            print(f'    - id={c.id}  codigo={c.codigo!r}  geojson={c.geometria_geojson is not None}')
else:
    print('  Ninguno ✅')

# ── 3. Resumen ───────────────────────────────────────────────
print('\n' + '═' * 60)
print('  TOTALES')
print('═' * 60)
print(f'  Circuitos totales: {Circuito.objects.count()}')
print(f'  Con geojson:       {Circuito.objects.exclude(geometria_geojson__isnull=True).count()}')