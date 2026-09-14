#!/usr/bin/env python
"""
Importa un archivo JSONL a la BD usando update_or_create.
NO actualiza circuitos. Solo inserta/actualiza Mensajes.

Uso:
    python importar_json.py                          # importa scrap_historico.jsonl
    python importar_json.py --archivo otro.jsonl
    python importar_json.py --dry-run                # solo muestra qué haría
    python importar_json.py --rebuild-circuitos      # tras importar, reconstruye circuitos
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent


def setup_django():
    sys.path.insert(0, str(BASE_DIR))
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'telegramscrap.settings')
    import django
    django.setup()


def parsear_fecha(iso: str | None):
    """Convierte string ISO a datetime o None."""
    if not iso:
        return None
    try:
        return datetime.fromisoformat(iso)
    except (ValueError, TypeError):
        return None


def importar(archivo: Path, dry_run: bool = False):
    from apps.telegram_base.models import Mensaje

    if not archivo.exists():
        print(f'❌ No existe: {archivo}')
        return 1

    total_lineas = 0
    nuevos = 0
    actualizados = 0
    errores = 0
    inicio = time.time()

    print('=' * 60)
    print('  IMPORTAR JSONL → BD')
    print('=' * 60)
    print(f'  Archivo:     {archivo}')
    print(f'  Dry-run:     {dry_run}')
    print('=' * 60)

    with open(archivo, encoding='utf-8') as f:
        for num_linea, linea in enumerate(f, 1):
            linea = linea.strip()
            if not linea:
                continue

            total_lineas += 1

            try:
                data = json.loads(linea)
            except json.JSONDecodeError as e:
                errores += 1
                print(f'  ⚠️  Línea {num_linea}: JSON inválido ({e})')
                continue

            # Validaciones mínimas
            telegram_id = data.get('telegram_id')
            if not telegram_id:
                errores += 1
                print(f'  ⚠️  Línea {num_linea}: sin telegram_id')
                continue

            # Preparar defaults
            defaults = {
                'texto': data.get('texto', ''),
                'fecha': parsear_fecha(data.get('fecha')),
                'media_url': data.get('media_url', '') or '',
                'tipo_media': data.get('tipo_media', 'texto') or 'texto',
                'enlace': data.get('enlace', '') or '',
                'tipo_evento': data.get('tipo_evento', 'otro'),
                'es_afectacion': data.get('es_afectacion', False),
                'circuitos_mencionados': data.get('circuitos_mencionados', []),
            }

            if dry_run:
                # Solo contar
                existente = Mensaje.objects.filter(telegram_id=telegram_id).exists()
                if existente:
                    actualizados += 1
                else:
                    nuevos += 1
                continue

            try:
                obj, created = Mensaje.objects.update_or_create(
                    telegram_id=telegram_id,
                    defaults=defaults,
                )
                if created:
                    nuevos += 1
                else:
                    actualizados += 1
            except Exception as e:
                errores += 1
                print(f'  ❌ Error línea {num_linea} (id={telegram_id}): {e}')

            # Progreso cada 500 líneas
            if total_lineas % 500 == 0:
                elapsed = time.time() - inicio
                vel = total_lineas / elapsed if elapsed > 0 else 0
                print(f'  [{total_lineas:>6} líneas] '
                      f'nuevos={nuevos:<5} actualizados={actualizados:<5} '
                      f'errores={errores:<3} '
                      f'vel={vel:.0f} líneas/s')

    elapsed = time.time() - inicio
    print()
    print('=' * 60)
    print('  RESUMEN')
    print('=' * 60)
    print(f'  Líneas procesadas:  {total_lineas}')
    print(f'  Nuevos:             {nuevos}')
    print(f'  Actualizados:       {actualizados}')
    print(f'  Errores:            {errores}')
    print(f'  Duración:           {elapsed:.1f} s')
    print('=' * 60)

    return 0


def main():
    parser = argparse.ArgumentParser(description='Importar JSONL a BD')
    parser.add_argument('--archivo', type=str, default='scrap_historico.jsonl',
                        help='Nombre del archivo JSONL (default: scrap_historico.jsonl)')
    parser.add_argument('--dry-run', action='store_true',
                        help='Solo simula, no escribe en BD.')
    parser.add_argument('--rebuild-circuitos', action='store_true',
                        help='Al terminar, borrar y reconstruir circuitos.')

    args = parser.parse_args()

    try:
        setup_django()
    except Exception as e:
        print(f'❌ Error al configurar Django: {e}')
        return 1

    archivo = Path(args.archivo)
    if not archivo.is_absolute():
        archivo = BASE_DIR / archivo

    rc = importar(archivo, dry_run=args.dry_run)

    # ── Reconstruir circuitos si se pidió ─────────────────────
    if args.rebuild_circuitos and not args.dry_run and rc == 0:
        print()
        print('🔨 Reconstruyendo circuitos...')
        from apps.circuitos.models import Circuito, EventoCircuito
        from apps.telegram_base.models import Mensaje
        from apps.circuitos.services.actualizador import procesar_mensaje

        EventoCircuito.objects.all().delete()
        Circuito.objects.all().delete()
        print('   Reset OK')

        total = Mensaje.objects.count()
        procesados = 0
        for m in Mensaje.objects.order_by('fecha', 'telegram_id').iterator():
            procesar_mensaje(m)
            procesados += 1
            if procesados % 500 == 0:
                print(f'   {procesados}/{total}')

        print(f'   ✅ Circuitos: {Circuito.objects.count()}')
        print(f'   ✅ Eventos:   {EventoCircuito.objects.count()}')

    return rc


if __name__ == '__main__':
    sys.exit(main())