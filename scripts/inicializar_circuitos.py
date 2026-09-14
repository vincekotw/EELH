from apps.telegram_base.models import Mensaje
from apps.circuitos.models import Circuito
from apps.circuitos.services.actualizador import procesar_mensaje

# Orden cronológico ascendente para reconstruir la historia real
total = Mensaje.objects.count()
procesados = 0

for m in Mensaje.objects.order_by('fecha', 'telegram_id'):
    procesar_mensaje(m)
    procesados += 1
    if procesados % 100 == 0:
        print(f'  {procesados}/{total}')

print(f'Procesados: {procesados}')
print(f'Circuitos creados: {Circuito.objects.count()}')