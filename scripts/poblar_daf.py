# scripts/poblar_daf.py
from apps.telegram_base.models import Mensaje
from apps.circuitos.models import CircuitoDAF
from apps.circuitos.services.parser_daf import (
    es_mensaje_daf, extraer_rango_daf, extraer_circuitos_daf,
    procesar_mensaje_daf,
)

# Limpiar
CircuitoDAF.objects.all().delete()
print('CircuitoDAF limpiado')

# Procesar todos los mensajes DAF
procesados = 0
for m in Mensaje.objects.order_by('fecha', 'telegram_id'):
    if es_mensaje_daf(m.texto):
        procesar_mensaje_daf(m)
        procesados += 1
        print(f'  Procesado msg={m.telegram_id} ({m.fecha.date()})')

print(f'\nMensajes DAF procesados: {procesados}')
print(f'Registros CircuitoDAF activos: {CircuitoDAF.objects.filter(activo=True).count()}')

# Verificar el mensaje 81752
m = Mensaje.objects.get(telegram_id=81752)
rango = extraer_rango_daf(m.texto)
circuitos = extraer_circuitos_daf(m.texto)
print(f'\nVerificación msg=81752:')
print(f'  Rango: {rango}')
print(f'  Circuitos: {circuitos}')