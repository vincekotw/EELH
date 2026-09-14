from apps.telegram_base.models import Mensaje

CANDIDATOS = [
    81275, 81326, 81356, 81380, 81398, 81469, 81522, 81555,
    81612, 81696, 81712, 81728, 81795, 81845, 81888,
]

for tid in CANDIDATOS:
    try:
        m = Mensaje.objects.get(telegram_id=tid)
    except Mensaje.DoesNotExist:
        print(f'[{tid}] NO EXISTE')
        continue

    bajo = m.texto.lower()
    tiene_rot = 'rotación' in bajo or 'rotacion' in bajo or 'subestación apolo' in bajo
    tiene_serv = 'con servicio' in bajo or 'restablecido' in bajo
    tiene_afect = 'afectados' in bajo or 'afectado' in bajo

    print(f'[{tid}] tipo={m.tipo_evento:18s} '
          f'rot={tiene_rot} serv={tiene_serv} afect={tiene_afect} '
          f'circs={len(m.circuitos_mencionados)}')