from collections import Counter
from apps.telegram_base.models import Mensaje
from django.db.models import Count

print('Distribución por tipo de evento:')
for row in Mensaje.objects.values('tipo_evento').annotate(n=Count('id')).order_by('-n'):
    print(f"  {row['tipo_evento']:20s} {row['n']}")

print('\nMuestra de mensajes en "otro":')
for m in Mensaje.objects.filter(tipo_evento='otro')[:15]:
    print(f'  [{m.telegram_id}] {m.texto[:100]}...')

# Verificar IDs específicos que estaban mal
print('\nVerificación de casos específicos:')
for tid in [81272, 81500, 81843, 81789, 81780, 81496, 81841]:
    try:
        m = Mensaje.objects.get(telegram_id=tid)
        print(f'  [{tid}] {m.tipo_evento} - {m.texto[:70]}...')
    except Mensaje.DoesNotExist:
        print(f'  [{tid}] no está en BD')