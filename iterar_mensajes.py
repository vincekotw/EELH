"""
Itera mensaje por mensaje desde un ID inicial hasta el último ID del canal,
guardando cada mensaje en JSON. Usa el modo embed de Telegram para obtener
el HTML renderizado en el servidor.
"""

import json
import os
import re
import time
import requests
from bs4 import BeautifulSoup

# ── Configuración ──────────────────────────────────────────────
CANAL = 'EmpresaElectricaDeLaHabana'
ID_INICIAL = 81270
ID_FINAL = None                # None = detectar automáticamente
ARCHIVO_SALIDA = 'mensajes.json'
ARCHIVO_PROGRESO = 'progreso.txt'
PAUSA = 1.2                    # segundos entre peticiones
TIMEOUT = 15
HEADERS = {
    'User-Agent': (
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
        'AppleWebKit/537.36 (KHTML, like Gecko) '
        'Chrome/124.0.0.0 Safari/537.36'
    ),
    'Accept-Language': 'es-ES,es;q=0.9,en;q=0.8',
}


def obtener_ultimo_id(canal: str) -> int:
    url = f'https://t.me/s/{canal}'
    print(f'🔍 Detectando último ID desde {url}...')
    resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, 'html.parser')
    ids = []
    for post in soup.select('.tgme_widget_message'):
        dp = post.get('data-post', '')
        if '/' in dp:
            try:
                ids.append(int(dp.rsplit('/', 1)[-1]))
            except ValueError:
                pass
    if not ids:
        raise RuntimeError('No se encontraron mensajes en la vista general.')
    ultimo = max(ids)
    print(f'   → Último ID detectado: {ultimo}')
    return ultimo


def extraer_mensaje(canal: str, msg_id: int) -> dict | None:
    url = f'https://t.me/{canal}/{msg_id}?embed=1'
    try:
        resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
    except requests.exceptions.Timeout:
        print(f'   ⏱️  Timeout en {url}')
        return None
    except requests.exceptions.RequestException as e:
        print(f'   ❌ Error de red en {url}: {e}')
        return None

    if resp.status_code != 200:
        return None

    soup = BeautifulSoup(resp.text, 'html.parser')
    post = soup.select_one('.tgme_widget_message')
    if post is None:
        return None

    data_post = post.get('data-post', '')
    if '/' not in data_post:
        return None
    try:
        id_real = int(data_post.rsplit('/', 1)[-1])
    except ValueError:
        return None

    texto_el = post.select_one('.tgme_widget_message_text')
    texto = texto_el.get_text(separator='\n', strip=True) if texto_el else ''

    time_el = post.select_one('time[datetime]')
    fecha = time_el.get('datetime') if time_el else None

    vistas_el = post.select_one('.tgme_widget_message_views')
    vistas = vistas_el.get_text(strip=True) if vistas_el else None

    autor_el = post.select_one('.tgme_widget_message_owner_name')
    autor = autor_el.get_text(strip=True) if autor_el else None

    media_url = None
    foto_wrap = post.select_one('.tgme_widget_message_photo_wrap')
    if foto_wrap and foto_wrap.has_attr('style'):
        m = re.search(r"background-image:url\('([^']+)'\)", foto_wrap['style'])
        if m:
            media_url = m.group(1)

    return {
        'id': id_real,
        'fecha': fecha,
        'texto': texto,
        'vistas': vistas,
        'autor': autor,
        'media_url': media_url,
        'enlace': f'https://t.me/{canal}/{id_real}',
    }


def cargar_progreso() -> int | None:
    if os.path.exists(ARCHIVO_PROGRESO):
        with open(ARCHIVO_PROGRESO, encoding='utf-8') as f:
            txt = f.read().strip()
            if txt.isdigit():
                return int(txt)
    return None


def guardar_progreso(msg_id: int) -> None:
    with open(ARCHIVO_PROGRESO, 'w', encoding='utf-8') as f:
        f.write(str(msg_id))


def main():
    id_final = ID_FINAL if ID_FINAL is not None else obtener_ultimo_id(CANAL)

    ultimo = cargar_progreso()
    inicio = (ultimo + 1) if ultimo and ultimo <= ID_INICIAL else ID_INICIAL
    print(f'▶️  Iterando del ID {inicio} al {id_final}')

    mensajes = []
    if os.path.exists(ARCHIVO_SALIDA):
        try:
            with open(ARCHIVO_SALIDA, encoding='utf-8') as f:
                mensajes = json.load(f)
            print(f'   → Cargados {len(mensajes)} mensajes previos.')
        except json.JSONDecodeError:
            print('   ⚠️  JSON corrupto, empezando de cero.')

    nuevos = 0
    vacios = 0

    for msg_id in range(inicio, id_final + 1):
        print(f'📩 [{msg_id}/{id_final}] ', end='', flush=True)
        msg = extraer_mensaje(CANAL, msg_id)

        if msg is None:
            print('⏭️  sin contenido')
            vacios += 1
            time.sleep(PAUSA)
            continue

        print(f'✅ {msg["fecha"] or "sin fecha"}')
        mensajes.append(msg)
        nuevos += 1

        if nuevos % 50 == 0:
            with open(ARCHIVO_SALIDA, 'w', encoding='utf-8') as f:
                json.dump(mensajes, f, ensure_ascii=False, indent=2)
            guardar_progreso(msg_id)
            print(f'   💾 Progreso guardado ({len(mensajes)} mensajes).')

        time.sleep(PAUSA)

    with open(ARCHIVO_SALIDA, 'w', encoding='utf-8') as f:
        json.dump(mensajes, f, ensure_ascii=False, indent=2)
    guardar_progreso(id_final)

    print(f'\n✅ Terminado.')
    print(f'   Mensajes válidos: {len(mensajes)}')
    print(f'   IDs vacíos/saltados: {vacios}')
    print(f'   Archivo: {ARCHIVO_SALIDA}')


if __name__ == '__main__':
    main()