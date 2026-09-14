#!/usr/bin/env python
"""
Scraper histórico standalone para Telegram.
Se ejecuta INDEPENDIENTEMENTE del servidor Django.

Uso:
    python scrap_historico.py --cantidad 10000
    python scrap_historico.py --desde 81270 --hasta 71270
    python scrap_historico.py --test                 # solo 50 mensajes
    python scrap_historico.py --reset                # olvida checkpoint

No actualiza circuitos. Solo guarda mensajes en la BD.
Para reconstruir circuitos después, ejecutar los scripts de
inicialización manualmente desde Django.
"""

import argparse
import json
import os
import signal
import sys
import time
import traceback
from datetime import datetime
from pathlib import Path


# ══════════════════════════════════════════════════════════════
# Configuración del proyecto
# ══════════════════════════════════════════════════════════════
BASE_DIR = Path(__file__).resolve().parent
STATE_FILE = BASE_DIR / 'scrap_historico_state.json'
LOG_FILE = BASE_DIR / 'scrap_historico.log'


# ══════════════════════════════════════════════════════════════
# Bootstrap Django (sin manage.py)
# ══════════════════════════════════════════════════════════════
def setup_django():
    """Configura Django para poder usar el ORM en un script standalone."""
    sys.path.insert(0, str(BASE_DIR))
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'telegramscrap.settings')

    import django
    django.setup()


# ══════════════════════════════════════════════════════════════
# Logging simple a archivo + consola
# ══════════════════════════════════════════════════════════════
class Log:
    def __init__(self, path: Path):
        self.path = path
        self.file = open(path, 'a', encoding='utf-8')

    def _write(self, level: str, msg: str):
        ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        line = f'{ts} [{level}] {msg}'
        print(line)
        self.file.write(line + '\n')
        self.file.flush()

    def info(self, msg): self._write('INFO', msg)
    def warn(self, msg): self._write('WARN', msg)
    def error(self, msg): self._write('ERROR', msg)

    def close(self):
        try:
            self.file.close()
        except Exception:
            pass


# ══════════════════════════════════════════════════════════════
# Checkpoint (estado persistente entre ejecuciones)
# ══════════════════════════════════════════════════════════════
def cargar_state() -> dict:
    if STATE_FILE.exists():
        try:
            with open(STATE_FILE, encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def guardar_state(state: dict):
    with open(STATE_FILE, 'w', encoding='utf-8') as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def limpiar_state():
    if STATE_FILE.exists():
        STATE_FILE.unlink()


# ══════════════════════════════════════════════════════════════
# Núcleo del scraper
# ══════════════════════════════════════════════════════════════
def ejecutar(args, log: Log):
    # ── Imports diferidos (después de setup_django) ───────────
    from django.conf import settings
    from apps.telegram_base.models import Mensaje
    from apps.telegram_base.services import scraper

    canal = settings.TELEGRAM_CANAL_USERNAME
    timeout = settings.TELEGRAM_TIMEOUT

    # ── Determinar rango ──────────────────────────────────────
    desde = args.desde
    hasta = args.hasta
    cantidad = args.cantidad

    if desde is None:
        primero = Mensaje.objects.order_by('telegram_id').first()
        if not primero:
            log.error('No hay mensajes en BD. Ejecuta el scraper normal primero.')
            return 1
        desde = primero.telegram_id

    if hasta is None:
        hasta = max(1, desde - cantidad)

    if hasta >= desde:
        log.error(f'Rango inválido: desde={desde} debe ser mayor que hasta={hasta}.')
        return 1

    # ── Checkpoint: reanudar ──────────────────────────────────
    state = cargar_state()
    if state and not args.reset:
        # Si el rango del state está dentro del rango actual, continuar
        ultimo_id = state.get('ultimo_id')
        if ultimo_id and hasta < ultimo_id < desde:
            log.info(f'📌 Reanudando desde checkpoint: ID {ultimo_id}')
            desde = ultimo_id
            hasta = state.get('hasta', hasta)

    # Si no hay checkpoint, empezar de cero
    if not state or args.reset:
        state = {
            'desde_original': desde,
            'hasta': hasta,
            'ultimo_id': desde,
            'nuevos': 0,
            'vacios': 0,
            'errores': 0,
            'inicio': time.time(),
        }
        guardar_state(state)

    total_ids = desde - hasta
    log.info('=' * 60)
    log.info('  SCRAPE HISTÓRICO — standalone')
    log.info('=' * 60)
    log.info(f'  Canal:            @{canal}')
    log.info(f'  Desde:            {desde} (exclusivo)')
    log.info(f'  Hasta:            {hasta} (inclusivo)')
    log.info(f'  IDs a recorrer:   {total_ids}')
    log.info(f'  Pausa:            {args.pausa}s')
    log.info(f'  Checkpoint:       {STATE_FILE.name}')
    log.info('=' * 60)

    # ── Bucle principal ───────────────────────────────────────
    nuevos = state.get('nuevos', 0)
    vacios = state.get('vacios', 0)
    errores = state.get('errores', 0)
    inicio_sesion = time.time()
    ultimo_guardado = None
    detener = {'flag': False}

    # ── Capturar Ctrl+C ───────────────────────────────────────
    def sigint_handler(signum, frame):
        log.warn('\n⛔ Ctrl+C detectado, cerrando ordenadamente...')
        detener['flag'] = True

    signal.signal(signal.SIGINT, sigint_handler)

    # ── Iterar hacia atrás ────────────────────────────────────
    try:
        for msg_id in range(desde - 1, hasta - 1, -1):
            if detener['flag']:
                break

            # Extraer + clasificar
                        # Extraer + clasificar (usando las funciones existentes)
            try:
                data = scraper.extraer_mensaje(canal, msg_id, timeout)
                if data is not None:
                    data['tipo_evento'] = scraper.clasificar_evento(data['texto'])
                    data['es_afectacion'] = (data['tipo_evento'] == 'afectacion')
                    data['circuitos_mencionados'] = scraper.extraer_circuitos(data['texto'])
            except Exception as e:
                errores += 1
                log.error(f'Error extrayendo {msg_id}: {e}')
                time.sleep(args.pausa)
                continue

            if data is None:
                vacios += 1
            else:
                # Fecha ISO → datetime
                fecha_iso = data.pop('fecha', None)
                if fecha_iso:
                    try:
                        data['fecha'] = datetime.fromisoformat(fecha_iso)
                    except ValueError:
                        data['fecha'] = None
                else:
                    data['fecha'] = None

                # Guardar
                telegram_id = data.pop('telegram_id')
                try:
                    Mensaje.objects.update_or_create(
                        telegram_id=telegram_id,
                        defaults=data,
                    )
                    nuevos += 1
                    ultimo_guardado = telegram_id
                except Exception as e:
                    errores += 1
                    log.error(f'Error guardando {msg_id}: {e}')

            # ── Progreso cada 25 IDs ──────────────────────────
            recorridos = desde - msg_id
            if recorridos % 25 == 0:
                elapsed = time.time() - inicio_sesion
                velocidad = recorridos / elapsed if elapsed > 0 else 0
                remaining = (msg_id - hasta)
                eta_seg = remaining / velocidad if velocidad > 0 else 0
                log.info(
                    f'[{recorridos:>5} ids] '
                    f'nuevos={nuevos:<5} vacios={vacios:<4} '
                    f'vel={velocidad:.2f} ids/s '
                    f'ETA={eta_seg/60:.0f} min'
                )

                # Checkpoint cada 25
                state['ultimo_id'] = msg_id
                state['nuevos'] = nuevos
                state['vacios'] = vacios
                state['errores'] = errores
                guardar_state(state)

            # Límite de prueba
            if args.limite and nuevos >= args.limite:
                log.warn(f'⏸️  Límite de {args.limite} mensajes alcanzado.')
                break

            time.sleep(args.pausa)

    except Exception as e:
        log.error(f'Excepción inesperada: {e}')
        log.error(traceback.format_exc())

    # ── Guardar estado final ──────────────────────────────────
    state['ultimo_id'] = msg_id if 'msg_id' in locals() else hasta
    state['nuevos'] = nuevos
    state['vacios'] = vacios
    state['errores'] = errores
    guardar_state(state)

    # ── Resumen ───────────────────────────────────────────────
    elapsed = time.time() - inicio_sesion
    log.info('')
    log.info('=' * 60)
    log.info('  RESUMEN DE SESIÓN')
    log.info('=' * 60)
    log.info(f'  Mensajes nuevos:      {nuevos}')
    log.info(f'  IDs sin mensaje:      {vacios}')
    log.info(f'  Errores:              {errores}')
    log.info(f'  Duración:             {elapsed/60:.1f} min')
    log.info(f'  Último guardado:      {ultimo_guardado}')
    log.info(f'  Próximo reanudar en:  {state["ultimo_id"]}')
    log.info('=' * 60)

    if detener['flag']:
        log.info('Para reanudar, ejecuta el mismo comando.')
        log.info('Se continuará desde el checkpoint automáticamente.')

    return 0


# ══════════════════════════════════════════════════════════════
# CLI
# ══════════════════════════════════════════════════════════════
def main():
    parser = argparse.ArgumentParser(
        description='Scraper histórico standalone para Telegram.',
    )
    parser.add_argument('--desde', type=int, default=None,
                        help='ID superior (exclusivo). Default: primer ID en BD.')
    parser.add_argument('--hasta', type=int, default=None,
                        help='ID inferior (inclusivo). Default: desde - cantidad.')
    parser.add_argument('--cantidad', type=int, default=10000,
                        help='Cuántos IDs recorrer hacia atrás (default: 10000).')
    parser.add_argument('--pausa', type=float, default=1.0,
                        help='Segundos entre peticiones (default: 1.0).')
    parser.add_argument('--limite', type=int, default=None,
                        help='Detenerse tras N mensajes nuevos (útil para test).')
    parser.add_argument('--test', action='store_true',
                        help='Atajo: --cantidad 50 --limite 30 --pausa 0.7')
    parser.add_argument('--reset', action='store_true',
                        help='Ignorar checkpoint y empezar de cero.')

    args = parser.parse_args()

    # Atajo --test
    if args.test:
        args.cantidad = 50
        args.limite = 30
        args.pausa = 0.7

    # Bootstrap Django
    try:
        setup_django()
    except Exception as e:
        print(f'❌ Error al configurar Django: {e}')
        traceback.print_exc()
        return 1

    log = Log(LOG_FILE)
    try:
        return ejecutar(args, log)
    finally:
        log.close()


if __name__ == '__main__':
    sys.exit(main())