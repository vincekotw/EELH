"""
Revierte el estado de un circuito que fue cambiado por reportes de
discrepancia, dejándolo como estaba antes (en servicio).
"""
from apps.circuitos.models import Circuito, ReporteDiscrepancia


# ═══════════════════════════════════════════════════════════════
# CONFIGURACIÓN — Ajusta si quieres revertir todos
# ═══════════════════════════════════════════════════════════════
REVERTIR_TODOS = True   # Si True, revierte TODOS los circuitos
                        # con estado_origen='reportes_usuarios'
                        # Si False, solo el CODIGO_CIRCUITO de abajo
CODIGO_CIRCUITO = None  # Ej: 'C7'
                        # Se ignora si REVERTIR_TODOS=True


# ═══════════════════════════════════════════════════════════════
# 1. Encontrar circuitos a revertir
# ═══════════════════════════════════════════════════════════════
if REVERTIR_TODOS:
    qs = Circuito.objects.filter(estado_origen='reportes_usuarios')
else:
    qs = Circuito.objects.filter(
        estado_origen='reportes_usuarios',
        codigo__iexact=CODIGO_CIRCUITO,
    )

if not qs.exists():
    print('ℹ️  No hay circuitos con estado_origen=reportes_usuarios.')
    print('   Nada que revertir.')
    raise SystemExit

print('═' * 60)
print(f'  REVIRTIENDO {qs.count()} CIRCUITO(S)')
print('═' * 60)
print()

revertidos = 0

for c in qs:
    print(f'▶️  {c.codigo}')
    print(f'    antes: estado={c.estado}  activa={c.afectacion_activa}')

    # ── 1. Cerrar el ciclo de afectación abierto por los reportes ──
    if c.afectacion_activa and c.afectacion_inicio_msg:
        c.afectacion_fin_msg = c.afectacion_inicio_msg
        c.afectacion_duracion_msg_min = 0
        c.afectacion_activa = False

        # Restar la afectación fantasma del contador total
        if c.total_afectaciones > 0:
            c.total_afectaciones -= 1

    # ── 2. Reabrir ciclo de servicio (estaba en servicio antes) ──
    c.servicio_inicio_msg = None
    c.servicio_inicio_contenido = None
    c.servicio_fin_msg = None
    c.servicio_fin_contenido = None
    c.servicio_duracion_msg_min = None
    c.servicio_duracion_contenido_min = None
    c.servicio_activo = False

    # ── 3. Volver el estado a en_servicio ──
    c.estado = 'en_servicio'
    c.estado_origen = 'restablecimiento'   # el último origen válido
    c.estado_actualizado_en = None

    c.save(update_fields=[
        'afectacion_activa', 'afectacion_fin_msg',
        'afectacion_duracion_msg_min', 'total_afectaciones',
        'servicio_inicio_msg', 'servicio_inicio_contenido',
        'servicio_fin_msg', 'servicio_fin_contenido',
        'servicio_duracion_msg_min', 'servicio_duracion_contenido_min',
        'servicio_activo',
        'estado', 'estado_origen', 'estado_actualizado_en',
    ])

    print(f'    después: estado={c.estado}  activa={c.afectacion_activa}')
    print()

    revertidos += 1


# ═══════════════════════════════════════════════════════════════
# 2. Borrar reportes de discrepancia asociados
# ═══════════════════════════════════════════════════════════════
print('═' * 60)
print('  LIMPIANDO REPORTES DE DISCREPANCIA')
print('═' * 60)

# Borrar los reportes de los circuitos revertidos
n_borrados = ReporteDiscrepancia.objects.filter(
    circuito__in=qs,
).delete()

print(f'  Reportes borrados: {n_borrados}')
print()


# ═══════════════════════════════════════════════════════════════
# 3. Resumen final
# ═══════════════════════════════════════════════════════════════
print('═' * 60)
print(f'  ✅ {revertidos} circuito(s) revertido(s)')
print('═' * 60)