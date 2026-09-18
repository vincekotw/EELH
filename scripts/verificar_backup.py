"""
Verifica que el backup.json sea válido y muestre un resumen.
"""

import json
from collections import Counter


ARCHIVO = 'backup.json'


def verificar():
    print('═' * 55)
    print('  VERIFICACIÓN DE BACKUP.JSON')
    print('═' * 55)
    print()

    try:
        with open(ARCHIVO, encoding='utf-8') as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f'❌ No existe {ARCHIVO}')
        return
    except json.JSONDecodeError as e:
        print(f'❌ JSON inválido: {e}')
        return

    print(f'✅ JSON válido')
    print(f'   Objetos totales:  {len(data)}')

    modelos = Counter(d['model'] for d in data)
    print(f'   Modelos únicos:   {len(modelos)}')
    print()
    print('Top 15 modelos por cantidad:')
    for modelo, n in modelos.most_common(15):
        print(f'   {modelo:45s} {n}')


verificar()