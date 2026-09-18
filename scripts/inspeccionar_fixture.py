"""Muestra el contenido del backup para los modelos con FK a User."""

import json

with open('backup.json', encoding='utf-8') as f:
    data = json.load(f)

MODELOS = {
    'usuarios.profile',
    'usuarios.circuitousuario',
    'usuarios.notificacion',
    'usuarios.navegacionlog',
}

for d in data:
    if d['model'] in MODELOS:
        print(f'─── {d["model"]} (pk={d.get("pk")}) ───')
        print(json.dumps(d['fields'], indent=2, ensure_ascii=False))
        print()