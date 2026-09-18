"""
Exporta la base de datos a backup.json con UTF-8 explícito.
Compatible con Windows (evita el error de charmap con emojis).
"""

import io
import json
import os

from django.core.management import call_command


OUTPUT_FILE = 'backup.json'


def dump():
    print(f'Exportando a {OUTPUT_FILE}...')

    # Capturamos la salida en un buffer con encoding UTF-8
    buffer = io.StringIO()
    call_command(
        'dumpdata',
        '--natural-foreign',
        '--natural-primary',
        '-e', 'contenttypes',
        '-e', 'auth.permission',
        '-e', 'admin.logentry',
        '-e', 'sessions',
        '--indent', '2',
        stdout=buffer,
    )

    content = buffer.getvalue()

    # Validar que el contenido sea JSON parseable
    try:
        data = json.loads(content)
        print(f'  JSON válido con {len(data)} objetos')
    except json.JSONDecodeError as e:
        print(f'  ❌ JSON inválido: {e}')
        raise

    # Escribir en UTF-8 SIN BOM
    with open(OUTPUT_FILE, 'w', encoding='utf-8', newline='\n') as f:
        f.write(content)

    size_mb = os.path.getsize(OUTPUT_FILE) / (1024 * 1024)
    print(f'✅ Backup guardado: {OUTPUT_FILE} ({size_mb:.2f} MB)')


if __name__ == '__main__':
    dump()