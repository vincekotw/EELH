"""
Crea manualmente la alerta del apagón de agosto para probar
la UI de modo apagón. Útil solo para desarrollo.
"""
from apps.telegram_base.models import Mensaje
from apps.circuitos.models import AlertaMasiva


# Limpiar
AlertaMasiva.objects.all().delete()

# Buscar mensajes del apagón
try:
    msg_ini = Mensaje.objects.get(telegram_id=72224)
    msg_fin = Mensaje.objects.get(telegram_id=72247)
except Mensaje.DoesNotExist as e:
    print(f'❌ Falta mensaje: {e}')
    raise SystemExit

# Crear alerta con activo=True para ver la UI
a = AlertaMasiva.objects.create(
    tipo='occidente',
    titulo='🚨 Apagón en el occidente del país',
    descripcion=msg_ini.texto[:500],
    iniciado_en=msg_ini.fecha,
    finalizado_en=msg_fin.fecha,
    mensaje_deteccion=msg_ini,
    mensaje_fin_oficial=msg_fin,
    activo=True,   # ← Forzado para ver el modo apagón
)

print(f'✅ Alerta creada:')
print(f'   Título:    {a.titulo}')
print(f'   Inicio:    {a.iniciado_en}')
print(f'   Fin:       {a.finalizado_en}')
print(f'   Duración:  {a.duracion_min} min')
print(f'   Activo:    {a.activo}')
print()
print('Refresca http://127.0.0.1:8000/circuitos/')