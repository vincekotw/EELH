"""
Lógica de extracción de mensajes del canal de Telegram.
Sin dependencias de Django: testeable de forma aislada.
"""

import re
import time
import requests
from bs4 import BeautifulSoup


HEADERS = {
    'User-Agent': (
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
        'AppleWebKit/537.36 (KHTML, like Gecko) '
        'Chrome/124.0.0.0 Safari/537.36'
    ),
    'Accept-Language': 'es-ES,es;q=0.9,en;q=0.8',
}

# ── Clasificación ────────────────────────────────────────────
KEYWORDS_AFECTACION = [
    'se afectó',
    'se afecta',
    'afectado el servicio',
    'afectación',
    'afectados',
    'interrupción',
    'interrumpió',
    'sin servicio',
    'déficit de generación',
    'falla en el servicio',
    'avería',
    'averías',
    'salida del servicio',
    'no cuenta con servicio',
    'disparo del circuito',
    'disparo por',
    'disparo automático por frecuencia',
    'daf',
    'trabajos operativos',
    'vía libre de emergencia',
    'vía libre por emergencia',
    'mantenimiento',
    'fusible fundido',
    'cable fallo',
    'poste partido',
    'primario partido',
    'secundario partido',
    'transformador dañado',
]

KEYWORDS_RESTABLECIMIENTO = [
    'restablecido',
    'restablecimiento',
    'restableció',
    'restablece',
    'restablece el servicio',
    'queda restablecido',
    'normalizado',
    'normalizó',
    'normaliza',
    'se normaliza',
    'se restablece',
    'se restableció',
    'servicio recuperado',
    'recuperó el servicio',
    'queda reparada',
    'queda reparado',
    'ha quedado reparada',
    'se reanuda',
    'se reanudó',
    'en línea la unidad',
    'fuera de línea',
]


# Patrón contextual: captura lo que viene tras 👉 (con o sin letras, con o sin guion)
RE_CIRCUITO_CONTEXTO = re.compile(
    r'👉\s*([A-Z]{0,4}-?\d{1,5})\s*:',
    re.IGNORECASE,
)

# Patrón general: solo con letra inicial (para menciones sin emoji)
RE_CIRCUITO_GENERAL = re.compile(r'\b([A-Z]{1,4}-?\d{2,4})\b')


# ── HTTP ─────────────────────────────────────────────────────
def _get(url: str, timeout: int) -> requests.Response | None:
    try:
        r = requests.get(url, headers=HEADERS, timeout=timeout)
        if r.status_code != 200:
            return None
        return r
    except requests.exceptions.RequestException:
        return None


# ── Detección de último ID ───────────────────────────────────
def obtener_ultimo_id(canal: str, timeout: int = 15) -> int | None:
    """Lee la vista general del canal y devuelve el ID más alto visible."""
    url = f'https://t.me/s/{canal}'
    r = _get(url, timeout)
    if r is None:
        return None

    soup = BeautifulSoup(r.text, 'html.parser')
    ids = []
    for post in soup.select('.tgme_widget_message'):
        dp = post.get('data-post', '')
        if '/' in dp:
            try:
                ids.append(int(dp.rsplit('/', 1)[-1]))
            except ValueError:
                pass
    return max(ids) if ids else None


# ── Extracción de un mensaje ─────────────────────────────────
def extraer_mensaje(canal: str, msg_id: int, timeout: int = 15) -> dict | None:
    """
    Descarga un mensaje individual con ?embed=1 y devuelve sus campos.
    Devuelve None si el mensaje no existe o no se pudo parsear.
    """
    url = f'https://t.me/{canal}/{msg_id}?embed=1'
    r = _get(url, timeout)
    if r is None:
        return None

    soup = BeautifulSoup(r.text, 'html.parser')
    post = soup.select_one('.tgme_widget_message')
    if post is None:
        return None

    # Verificar que el ID coincide (Telegram a veces devuelve otro post)
    dp = post.get('data-post', '')
    if '/' not in dp:
        return None
    try:
        id_real = int(dp.rsplit('/', 1)[-1])
    except ValueError:
        return None
    if id_real != msg_id:
        return None

    texto_el = post.select_one('.tgme_widget_message_text')
    texto = texto_el.get_text(separator='\n', strip=True) if texto_el else ''

    time_el = post.select_one('time[datetime]')
    fecha = time_el.get('datetime') if time_el else None

    media_url = ''
    tipo_media = 'texto'
    foto_wrap = post.select_one('.tgme_widget_message_photo_wrap')
    if foto_wrap and foto_wrap.has_attr('style'):
        m = re.search(r"background-image:url\('([^']+)'\)", foto_wrap['style'])
        if m:
            media_url = m.group(1)
            tipo_media = 'foto'
    elif post.select_one('.tgme_widget_message_video_wrap'):
        tipo_media = 'video'
    elif post.select_one('.tgme_widget_message_document_wrap'):
        tipo_media = 'documento'

    return {
        'telegram_id': id_real,
        'texto': texto,
        'fecha': fecha,          # ISO string o None
        'media_url': media_url,
        'tipo_media': tipo_media,
        'enlace': f'https://t.me/{canal}/{id_real}',
    }


# ── Clasificación ────────────────────────────────────────────
def clasificar_evento(texto: str) -> str:
    """Devuelve 'afectacion', 'restablecimiento' u 'otro'."""
    if not texto:
        return 'otro'
    bajo = texto.lower()

    # Prioridad 1: restablecimiento (evita falsos positivos cuando el
    # texto menciona "avería restablecida" o "afectación solucionada")
    if any(k in bajo for k in KEYWORDS_RESTABLECIMIENTO):
        return 'restablecimiento'

    # Prioridad 2: afectación
    if any(k in bajo for k in KEYWORDS_AFECTACION):
        return 'afectacion'

    return 'otro'


def extraer_circuitos(texto: str) -> list[str]:
    if not texto:
        return []

    # 1) Buscar tras 👉 (captura cualquier formato)
    encontrados = RE_CIRCUITO_CONTEXTO.findall(texto)

    # 2) Si no hay, buscar el patrón general (solo con letra inicial)
    if not encontrados:
        encontrados = RE_CIRCUITO_GENERAL.findall(texto)

    # Normalizar
    normalizados = [c.upper().strip() for c in encontrados if c]

    # Deduplicar manteniendo orden
    vistos = set()
    resultado = []
    for c in normalizados:
        if c not in vistos:
            vistos.add(c)
            resultado.append(c)
    return resultado


# ── Iteración completa ───────────────────────────────────────
def iterar_rango(canal, id_inicio, id_fin, pausa=1.2, timeout=15, on_progreso=None):
    for msg_id in range(id_inicio, id_fin + 1):
        data = extraer_mensaje(canal, msg_id, timeout)
        if data is None:
            if on_progreso:
                on_progreso(msg_id, False)
            time.sleep(pausa)
            continue

        # Clasificación
        data['tipo_evento'] = clasificar_evento(data['texto'])
        data['es_afectacion'] = (data['tipo_evento'] == 'afectacion')
        data['circuitos_mencionados'] = extraer_circuitos(data['texto'])

        if on_progreso:
            on_progreso(msg_id, True)

        yield data
        time.sleep(pausa)