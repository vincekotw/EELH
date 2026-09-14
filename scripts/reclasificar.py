from apps.telegram_base.models import Mensaje
from apps.telegram_base.services.scraper import (
    clasificar_evento,
    extraer_circuitos,
)

actualizados = 0
total = Mensaje.objects.count()

for m in Mensaje.objects.all():
    nuevo_tipo = clasificar_evento(m.texto)
    nuevos_circ = extraer_circuitos(m.texto)
    nueva_afect = (nuevo_tipo == 'afectacion')

    if (m.tipo_evento != nuevo_tipo
            or m.es_afectacion != nueva_afect
            or m.circuitos_mencionados != nuevos_circ):
        m.tipo_evento = nuevo_tipo
        m.es_afectacion = nueva_afect
        m.circuitos_mencionados = nuevos_circ
        m.save(update_fields=['tipo_evento', 'es_afectacion', 'circuitos_mencionados'])
        actualizados += 1

print(f'Total mensajes: {total}')
print(f'Actualizados: {actualizados}')