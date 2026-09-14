from apps.circuitos.models import Circuito, EventoCircuito
from django.db.models import Count, Avg, Sum

print('═' * 60)
print('  ESTADO DE CIRCUITOS')
print('═' * 60)

total = Circuito.objects.count()
print(f'\nTotal circuitos: {total}')
print(f'Total eventos:   {EventoCircuito.objects.count()}')

# Distribución por estado
print('\nDistribución por estado:')
for row in Circuito.objects.values('estado').annotate(n=Count('id')).order_by('-n'):
    print(f"  {row['estado']:15s} {row['n']}")

# Ciclos activos
print(f'\nAfectaciones activas:  {Circuito.objects.filter(afectacion_activa=True).count()}')
print(f'Servicios activos:     {Circuito.objects.filter(servicio_activo=True).count()}')

# Top 15 circuitos más castigados
print('\nTop 15 circuitos con más minutos afectados:')
for c in Circuito.objects.filter(total_minutos_afectado__gt=0).order_by('-total_minutos_afectado')[:15]:
    horas = c.total_minutos_afectado / 60
    print(f'  {c.codigo:8s}  {c.total_afectaciones:3d} afectaciones  '
          f'{horas:6.1f}h acumuladas  estado={c.estado}')

# Verificar que hay circuitos con ciclo cerrado
print('\nCircuitos con ciclo de afectación CERRADO:')
cerrados = Circuito.objects.filter(
    afectacion_inicio_msg__isnull=False,
    afectacion_fin_msg__isnull=False,
)
print(f'  Total: {cerrados.count()}')

# Comparar duración por mensaje vs por contenido
print('\nDiferencia de duración (msg - contenido) en minutos:')
diferencia = Circuito.objects.filter(
    afectacion_duracion_msg_min__isnull=False,
    afectacion_duracion_contenido_min__isnull=False,
)
print(f'  Circuitos comparables: {diferencia.count()}')

# Ejemplos concretos
print('\nEjemplos de circuitos con ciclos cerrados:')
for c in Circuito.objects.filter(
    afectacion_duracion_msg_min__isnull=False,
    afectacion_duracion_contenido_min__isnull=False,
)[:5]:
    print(f'  {c.codigo}:')
    print(f'    inicio_msg={c.afectacion_inicio_msg}')
    print(f'    inicio_cont={c.afectacion_inicio_contenido}')
    print(f'    fin_msg={c.afectacion_fin_msg}')
    print(f'    fin_cont={c.afectacion_fin_contenido}')
    print(f'    duración_msg={c.afectacion_duracion_msg_min} min')
    print(f'    duración_cont={c.afectacion_duracion_contenido_min} min')

print('\n' + '═' * 60)