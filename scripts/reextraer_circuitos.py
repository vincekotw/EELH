from apps.telegram_base.models import Mensaje
from apps.telegram_base.services.scraper import extraer_circuitos

total = Mensaje.objects.count()
cambiados = 0
nuevos_circuitos = set()

for m in Mensaje.objects.all().iterator():
    antes = set(m.circuitos_mencionados or [])
    despues = set(extraer_circuitos(m.texto or ''))

    if antes != despues:
        m.circuitos_mencionados = sorted(despues)
        m.save(update_fields=['circuitos_mencionados'])
        cambiados += 1
        nuevos_circuitos |= (despues - antes)

print(f'Total mensajes:  {total}')
print(f'Actualizados:    {cambiados}')
print(f'Circuitos nuevos detectados: {sorted(nuevos_circuitos)}')