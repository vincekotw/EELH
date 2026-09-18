import requests
from bs4 import BeautifulSoup

def obtener_ultimo_id(canal: str, headers: dict) -> int:
    """Devuelve el ID más alto visible en la vista general del canal."""
    url = f'https://t.me/s/{canal}'
    resp = requests.get(url, headers=headers, timeout=15)
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
    return max(ids)