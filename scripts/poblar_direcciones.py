from apps.circuitos.models import Circuito
from apps.circuitos.services.parser_direccion import extraer_direccion


actualizados = 0
sin_direccion = []

for circuito in Circuito.objects.all():
    candidatos = set()

    # Recorrer TODOS los eventos del circuito (no solo el último)
    # porque queremos quedarnos con la dirección más detallada.
    eventos = circuito.eventos.select_related('mensaje').all()
    for evento in eventos:
        direccion = extraer_direccion(evento.mensaje.texto, circuito.codigo)
        if direccion:
            candidatos.add(direccion)

    if candidatos:
        mejor = max(candidatos, key=len)
        if circuito.direccion != mejor:
            circuito.direccion = mejor
            circuito.save(update_fields=['direccion'])
            actualizados += 1
    else:
        sin_direccion.append(circuito.codigo)

print(f'Circuitos actualizados: {actualizados}')
print(f'Circuitos sin dirección: {len(sin_direccion)}')
if sin_direccion:
    print('Sin dirección:', ', '.join(sin_direccion[:30]))