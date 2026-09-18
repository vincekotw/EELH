"""
Importa un fixture JSON en bloques para evitar timeouts con Neon.
"""
import json
import os

from django.core.management import call_command


ARCHIVO = 'backup.json'
BLOQUE = 1000


def importar():
    with open(ARCHIVO, encoding='utf-8') as f:
        data = json.load(f)

    total = len(data)
    print(f'Total de objetos: {total}')
    print(f'Bloques de {BLOQUE}')

    for i in range(0, total, BLOQUE):
        chunk = data[i:i + BLOQUE]
        chunk_file = f'_chunk_{i // BLOQUE}.json'

        with open(chunk_file, 'w', encoding='utf-8') as f:
            json.dump(chunk, f, ensure_ascii=False, indent=2)

        print(f'  Bloque {i // BLOQUE + 1} ({len(chunk)} obj)...', end=' ')

        try:
            call_command('loaddata', chunk_file, verbosity=0)
            print('✅')
        except Exception as e:
            print(f'❌ {e}')
            raise
        finally:
            os.remove(chunk_file)

    print(f'\n✅ {total} objetos importados')


importar()