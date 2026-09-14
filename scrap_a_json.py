#!/usr/bin/env python
"""
Scraper histórico que guarda TODO en JSONL, sin tocar la BD.

Uso:
    python scrap_a_json.py --test
    python scrap_a_json.py --cantidad 17000
    python scrap_a_json.py --desde 81270 --hasta 60000
    python scrap_a_json.py --reset

Salida:
    scrap_historico.jsonl         (una línea por mensaje)
    scrap_historico_state.json    (checkpoint para reanudar)
    scrap_historico.log           (log completo)
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
# Configuración
# ══════════════════════════════════════════════════════════════
BASE_DIR = Path(__file__).resolve().parent
OUTPUT_FILE = BASE_DIR / 'scrap_historico.jsonl'
STATE_FILE = BASE_DIR / 'scrap_historico_state.json'
LOG_FILE = BASE_DIR / 'scrap_historico.log'


# ══════════════════════════════════════════════════════════════
# Bootstrap Django (para leer TELEGRAM_* de settings)
# ══════════════════════════════════════════════════════════════
def setup_django():
    sys.path.insert(0, str(BASE_DIR))
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'telegramscrap.settings')
    import django
    django.setup()


# ══════════════════════════════════════════════════════════════
# Logging
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
# Checkpoint
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


# ══════════════════════════════════════════════════════════════
# Núcleo
# ══════════════════════════════════════════════════════════════
def ejecutar(args, log: Log):
    from django.conf import settings
    from apps.telegram_base.services import scraper

    canal = settings.TELEGRAM_CANAL_USERNAME
    timeout = settings.TELEGRAM_TIMEOUT

    # ── Determinar rango ──────────────────────────────────────
    desde = args.desde
    hasta = args.hasta
    cantidad = args.cantidad

    # ── Checkpoint ────────────────────────────────────────────
    state = {} if args.reset else cargar_state()

    if state and state.get('ultimo_id') and not args.reset:
        desde = state['ultimo_id']
        # Si el usuario pasó --hasta explícito, respetarlo.
        # Si no, recalcular con --cantidad desde el nuevo desde.
        if args.hasta is not None:
            hasta = args.hasta
        else:
            hasta = max(1, desde - cantidad)
        log.info(f'📌 Reanudando desde checkpoint: ID {desde}')
        log.info(f'   Nuevo hasta: {hasta} (recalculado)')
    else:
        if desde is None:
            log.error('Debes especificar --desde (no tengo BD para inferirlo).')
            return 1
        if hasta is None:
            hasta = max(1, desde - cantidad)

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

    if hasta >= desde:
        log.error(f'Rango inválido: desde={desde} debe ser > hasta={hasta}.')
        return 1

    total_ids = desde - hasta

    log.info('=' * 60)
    log.info('  SCRAPE → JSONL')
    log.info('=' * 60)
    log.info(f'  Canal:            @{canal}')
    log.info(f'  Desde:            {desde} (exclusivo)')
    log.info(f'  Hasta:            {hasta} (inclusivo)')
    log.info(f'  IDs a recorrer:   {total_ids}')
    log.info(f'  Pausa:            {args.pausa}s')
    log.info(f'  Output:           {OUTPUT_FILE.name}')
    log.info('=' * 60)

    # ── Abrir output en modo append ───────────────────────────
    output_fp = open(OUTPUT_FILE, 'a', encoding='utf-8')

    # ── Ctrl+C ────────────────────────────────────────────────
    detener = {'flag': False}

    def sigint_handler(signum, frame):
        log.warn('\n⛔ Ctrl+C detectado, cerrando ordenadamente...')
        detener['flag'] = True

    signal.signal(signal.SIGINT, sigint_handler)

    # ── Estado acumulado ──────────────────────────────────────
    nuevos = state.get('nuevos', 0)
    vacios = state.get('vacios', 0)
    errores = state.get('errores', 0)
    inicio_sesion = time.time()
    ultimo_guardado = None
    escrito = 0  # mensajes escritos en esta sesión

    try:
        for msg_id in range(desde - 1, hasta - 1, -1):
            if detener['flag']:
                break

            # ── Extraer ───────────────────────────────────────
            try:
                data = scraper.extraer_mensaje(canal, msg_id, timeout)
            except Exception as e:
                errores += 1
                log.error(f'Error extrayendo {msg_id}: {e}')
                time.sleep(args.pausa)
                continue

            if data is None:
                vacios += 1
            else:
                # ── Enriquecer con clasificación ──────────────
                data['tipo_evento'] = scraper.clasificar_evento(data['texto'])
                data['es_afectacion'] = (data['tipo_evento'] == 'afectacion')
                data['circuitos_mencionados'] = scraper.extrar_circuitos(data['texto']) \
                    if hasattr(scraper, 'extrar_circuitos') \
                    else scraper.extraer_circuitos(data['texto'])

                # ── Escribir a JSONL ──────────────────────────
                linea = json.dumps(data, ensure_ascii=False)
                output_fp.write(linea + '\n')
                output_fp.flush()

                nuevos += 1
                escrito += 1
                ultimo_guardado = data['telegram_id']

                # Limitar si --limite
                if args.limite and escrito >= args.limite:
                    log.warn(f'⏸️  Límite de {args.limite} mensajes alcanzado.')
                    break

            # ── Progreso + checkpoint cada 25 IDs ────────────
            recorridos = desde - msg_id
            if recorridos % 25 == 0:
                elapsed = time.time() - inicio_sesion
                velocidad = recorridos / elapsed if elapsed > 0 else 0
                remaining = msg_id - hasta
                eta_seg = remaining / velocidad if velocidad > 0 else 0

                log.info(
                    f'[{recorridos:>6} ids] '
                    f'escritos={escrito:<5} vacios={vacios:<5} '
                    f'vel={velocidad:.2f} ids/s '
                    f'ETA={eta_seg/60:.0f} min'
                )

                state['ultimo_id'] = msg_id
                state['nuevos'] = nuevos
                state['vacios'] = vacios
                state['errores'] = errores
                guardar_state(state)

            time.sleep(args.pausa)

    except Exception as e:
        log.error(f'Excepción inesperada: {e}')
        log.error(traceback.format_exc())
    finally:
        output_fp.close()

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
    log.info('  RESUMEN')
    log.info('=' * 60)
    log.info(f'  Mensajes escritos:    {escrito}')
    log.info(f'  Mensajes totales:     {nuevos}')
    log.info(f'  IDs vacíos:           {vacios}')
    log.info(f'  Errores:              {errores}')
    log.info(f'  Duración:             {elapsed/60:.1f} min')
    log.info(f'  Último guardado:      {ultimo_guardado}')
    log.info(f'  Próximo reanudar en:  {state["ultimo_id"]}')
    log.info(f'  Archivo:              {OUTPUT_FILE}')
    log.info('=' * 60)

    if detener['flag']:
        log.info('Para reanudar, ejecuta el mismo comando.')

    return 0


# ══════════════════════════════════════════════════════════════
# CLI
# ══════════════════════════════════════════════════════════════
def main():
    parser = argparse.ArgumentParser(description='Scraper histórico → JSONL')
    parser.add_argument('--desde', type=int, default=None,
                        help='ID superior (exclusivo).')
    parser.add_argument('--hasta', type=int, default=None,
                        help='ID inferior (inclusivo).')
    parser.add_argument('--cantidad', type=int, default=17000,
                        help='Cuántos IDs recorrer hacia atrás (default: 17000).')
    parser.add_argument('--pausa', type=float, default=1.0,
                        help='Segundos entre peticiones (default: 1.0).')
    parser.add_argument('--limite', type=int, default=None,
                        help='Detenerse tras N mensajes nuevos.')
    parser.add_argument('--test', action='store_true',
                        help='Atajo: --cantidad 50 --limite 30 --pausa 0.7')
    parser.add_argument('--reset', action='store_true',
                        help='Ignorar checkpoint y empezar de cero.')

    args = parser.parse_args()

    if args.test:
        args.cantidad = 50
        args.limite = 30
        args.pausa = 0.7

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