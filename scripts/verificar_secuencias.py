"""
Verifica que las secuencias de PostgreSQL en Neon están correctas.
"""

from django.db import connection

from apps.telegram_base.models import Mensaje
from apps.circuitos.models import Circuito, EventoCircuito


def verificar():
    print('═' * 55)
    print('  VERIFICACIÓN DE SECUENCIAS')
    print('═' * 55)
    print()

    # ── Mensajes ─────────────────────────────────────────────
    total = Mensaje.objects.count()
    ultimo = Mensaje.objects.order_by('-id').first()

    print(f'📨 Mensajes:')
    print(f'   Total:              {total}')
    if ultimo:
        print(f'   Último id:          {ultimo.id}')
        print(f'   Último telegram_id: {ultimo.telegram_id}')

    with connection.cursor() as c:
        c.execute("SELECT last_value FROM telegram_base_mensaje_id_seq")
        next_id = c.fetchone()[0]
        print(f'   Secuencia apunta a: {next_id}')

    # ── Circuitos ────────────────────────────────────────────
    total_c = Circuito.objects.count()
    ultimo_c = Circuito.objects.order_by('-id').first()

    print()
    print(f'⚡ Circuitos:')
    print(f'   Total:              {total_c}')
    if ultimo_c:
        print(f'   Último id:          {ultimo_c.id}')
        print(f'   Último código:      {ultimo_c.codigo}')

    with connection.cursor() as c:
        c.execute("SELECT last_value FROM circuitos_circuito_id_seq")
        next_id = c.fetchone()[0]
        print(f'   Secuencia apunta a: {next_id}')

    # ── Eventos ──────────────────────────────────────────────
    total_e = EventoCircuito.objects.count()
    print()
    print(f'📅 Eventos: {total_e}')

    # ── Diagnóstico ──────────────────────────────────────────
    print()
    print('═' * 55)
    print('  DIAGNÓSTICO')
    print('═' * 55)

    if ultimo and next_id != ultimo.id:
        print('✅ Las secuencias parecen correctas')
    else:
        print('⚠️  Revisar: la secuencia podría estar desincronizada')


verificar()