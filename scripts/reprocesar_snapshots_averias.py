"""
Recorre TODOS los mensajes de 'Averías existentes' en orden
cronológico y aplica la lógica de snapshots.

Útil para corregir estados tras implementar el detector.
"""
from apps.telegram_base.models import Mensaje
from apps.circuitos.models import SnapshotAverias
from apps.circuitos.services.detector_averia import (
    es_mensaje_averias,
    procesar_snapshot_averias,
)


# ── Reset previo (opcional pero recomendado) ──────────────────
n_snapshots = SnapshotAverias.objects.all().delete()
print(f'Snapshots previos borrados: {n_snapshots}')
print()

# ── Filtrar mensajes de averías ───────────────────────────────
print('Buscando mensajes de averías...')
mensajes = []
for m in Mensaje.objects.order_by('fecha', 'telegram_id').iterator():
    if es_mensaje_averias(m.texto):
        mensajes.append(m)

print(f'Encontrados: {len(mensajes)} mensajes de "Averías existentes"')
print()

if not mensajes:
    print('Nada que procesar.')
    raise SystemExit

# ── Mostrar rango ─────────────────────────────────────────────
print(f'Rango: {mensajes[0].telegram_id} → {mensajes[-1].telegram_id}')
print(f'Fechas: {mensajes[0].fecha} → {mensajes[-1].fecha}')
print()

# ── Procesar en orden ─────────────────────────────────────────
restablecidos_total = 0
for i, m in enumerate(mensajes, 1):
    antes = SnapshotAverias.objects.count()
    procesar_snapshot_averias(m)
    despues = SnapshotAverias.objects.count()

    if i % 5 == 0 or i == len(mensajes):
        print(f'  [{i}/{len(mensajes)}] snapshot {m.telegram_id} '
              f'({len(m.circuitos_mencionados or [])} circuitos)')

print()
print('=' * 55)
print(f'Snapshots creados: {SnapshotAverias.objects.count()}')