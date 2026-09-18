"""
Importa el backup a Neon de forma robusta:
  - Bloques pequeños (200 objetos).
  - Orden de dependencias (auth → usuarios → circuitos → telegram).
  - Progreso en tiempo real con flush.
"""

import json
import os
import sys
import time

from django.core.management import call_command


ARCHIVO = 'backup.json'
BLOQUE = 200


# Orden de importación: primero lo que no tiene FKs, luego lo demás
ORDEN_MODELOS = [
    # Django core
    'auth.user',
    'auth.group',
    'auth.permission',

    # Apps propias sin FKs externas
    'telegram_base.estadoscraper',
    'telegram_base.mensaje',
    'telegram_base.scraperun',

    'circuitos.circuito',
    'circuitos.eventocircuito',
    'circuitos.alertamasiva',
    'circuitos.snapshotaverias',
    'circuitos.circuitodaf',

    'usuarios.profile',
    'usuarios.circuitousuario',
    'usuarios.notificacion',
    'usuarios.navegacionlog',
]


def log(msg):
    """Print con flush inmediato."""
    print(msg, flush=True)
    sys.stdout.flush()


def importar():
    if not os.path.exists(ARCHIVO):
        log(f'❌ No existe {ARCHIVO}')
        return

    log(f'Leyendo {ARCHIVO}...')
    with open(ARCHIVO, encoding='utf-8') as f:
        data = json.load(f)

    log(f'Total objetos: {len(data)}')

    # ── Agrupar por modelo ───────────────────────────────────
    por_modelo = {}
    for obj in data:
        modelo = obj['model']
        por_modelo.setdefault(modelo, []).append(obj)

    log(f'Modelos únicos: {len(por_modelo)}')
    log('')

    # ── Ordenar según ORDEN_MODELOS ──────────────────────────
    ordenados = []
    procesados = set()

    # Primero los que están en la lista, en el orden definido
    for modelo in ORDEN_MODELOS:
        if modelo in por_modelo:
            ordenados.append(modelo)
            procesados.add(modelo)

    # Luego los que sobren (por si acaso)
    for modelo in sorted(por_modelo.keys()):
        if modelo not in procesados:
            ordenados.append(modelo)

    total_importados = 0
    errores = []

    for modelo in ordenados:
        objetos = por_modelo[modelo]
        log(f'═══ {modelo}: {len(objetos)} objetos ═══')

        for i in range(0, len(objetos), BLOQUE):
            chunk = objetos[i:i + BLOQUE]
            chunk_file = f'_chunk_{modelo.replace(".", "_")}_{i}.json'

            with open(chunk_file, 'w', encoding='utf-8') as f:
                json.dump(chunk, f, ensure_ascii=False)

            num = i // BLOQUE + 1
            total_bloques = (len(objetos) + BLOQUE - 1) // BLOQUE
            log(f'  Bloque {num}/{total_bloques} ({len(chunk)} obj)...')
            sys.stdout.flush()

            try:
                t0 = time.time()
                call_command('loaddata', chunk_file, verbosity=0)
                elapsed = time.time() - t0
                log(f'    ✅ OK en {elapsed:.1f}s')
                total_importados += len(chunk)
            except Exception as e:
                msg = f'{modelo} bloque {num}: {e}'
                log(f'    ❌ {msg}')
                errores.append(msg)
            finally:
                if os.path.exists(chunk_file):
                    os.remove(chunk_file)

        log('')

    # ── Resumen ──────────────────────────────────────────────
    log('═' * 55)
    log('  RESUMEN')
    log('═' * 55)
    log(f'  Importados:  {total_importados}')
    log(f'  Errores:     {len(errores)}')
    if errores:
        log('')
        log('Errores:')
        for e in errores[:10]:
            log(f'  - {e}')


importar()