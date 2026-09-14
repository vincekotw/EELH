"""
Estrategia híbrida de geocodificación:
  0. Aplicar override manual (coordenadas_manuales).
  1. Buscar reparto/barrio en el diccionario local.
  2. Si no, intentar con Nominatim (opcional).
  3. Si no, devolver sin coordenadas.
"""

import re
import time
import unicodedata

from geopy.geocoders import Nominatim

from apps.circuitos.services.coordenadas_manuales import COORDENADAS_MANUALES
from apps.circuitos.services.repartos_habana import REPARTOS_HABANA


# ── Regex de extracción ──────────────────────────────────────
RE_PARENTESIS = re.compile(r'\(([^)]+)\)')

RE_REPARTO = re.compile(
    r'repartos?[\s:]+([\w\s,áéíóúñÁÉÍÓÚÑ]+?)(?:\.|;|,|\s+(?:Alrededor|Cuadrante|Calle|Avenida|Callejón|Carretera)|$)',
    re.IGNORECASE,
)

RE_LISTA_REPARTOS = re.compile(
    r'repartos?:?\s*([^.\n]+)',
    re.IGNORECASE,
)


# ── Utilidades ────────────────────────────────────────────────
def _normalizar(nombre: str) -> str:
    if not nombre:
        return ''
    limpio = nombre.lower().strip()
    limpio = ''.join(
        c for c in unicodedata.normalize('NFD', limpio)
        if unicodedata.category(c) != 'Mn'
    )
    limpio = re.sub(r'[^\w\s]', ' ', limpio)
    limpio = re.sub(r'\s+', ' ', limpio).strip()
    return limpio


def _extraer_candidatos(direccion: str) -> list[str]:
    if not direccion:
        return []

    candidatos = []

    for m in RE_PARENTESIS.finditer(direccion):
        texto = m.group(1).strip()
        if texto and len(texto) < 60:
            candidatos.append(texto)

    for m in RE_LISTA_REPARTOS.finditer(direccion):
        bloque = m.group(1)
        for parte in re.split(r'\s*,\s*|\s+y\s+', bloque):
            parte = parte.strip(' .')
            if parte and 2 < len(parte) < 60:
                candidatos.append(parte)

    for m in RE_REPARTO.finditer(direccion):
        bloque = m.group(1).strip(' .')
        for parte in re.split(r'\s*,\s*|\s+y\s+', bloque):
            parte = parte.strip()
            if parte and 2 < len(parte) < 60:
                candidatos.append(parte)

    for sep in [' -', ' –', ' —']:
        if sep in direccion:
            parte = direccion.rsplit(sep, 1)[-1].strip()
            if parte and 2 < len(parte) < 60:
                candidatos.append(parte)

    if not candidatos:
        candidatos.append(direccion[:60])

    vistos = set()
    unicos = []
    for c in candidatos:
        n = _normalizar(c)
        if n and n not in vistos:
            vistos.add(n)
            unicos.append(c)

    return unicos


def _buscar_en_diccionario(nombre: str) -> tuple[float, float] | None:
    if not nombre:
        return None
    norm = _normalizar(nombre)
    if not norm or len(norm) < 3:
        return None

    if norm in REPARTOS_HABANA:
        return REPARTOS_HABANA[norm]

    mejor = None
    mejor_len = 0
    for clave, coords in REPARTOS_HABANA.items():
        if clave in norm and len(clave) > mejor_len:
            mejor = coords
            mejor_len = len(clave)

    return mejor


def _intentar_nominatim(direccion: str) -> tuple[float, float] | None:
    geolocator = Nominatim(user_agent="circuitos_habana_eelh")

    simplificada = re.split(r'[.;,]', direccion)[0].strip()
    if len(simplificada) < 10:
        return None

    query = f"{simplificada}, La Habana, Cuba"
    try:
        location = geolocator.geocode(query, timeout=10)
        if location:
            return (location.latitude, location.longitude)
    except Exception:
        pass
    return None


def geocodificar(
    direccion: str,
    codigo: str = '',
    usar_nominatim: bool = False,
) -> tuple:
    """
    Devuelve (lat, lng, metodo).
    metodo ∈ {'manual', 'diccionario', 'nominatim', 'sin_resultado'}.

    Acepta `codigo` para aplicar overrides manuales antes de
    intentar cualquier estrategia automática.
    """
    # ── Estrategia 0: override manual por código ─────────────
    if codigo and codigo in COORDENADAS_MANUALES:
        lat, lng = COORDENADAS_MANUALES[codigo]
        return (lat, lng, 'manual')

    if not direccion:
        return (None, None, 'sin_resultado')

    # ── Estrategia 1: diccionario local ──────────────────────
    for candidato in _extraer_candidatos(direccion):
        coords = _buscar_en_diccionario(candidato)
        if coords:
            return (coords[0], coords[1], 'diccionario')

    # ── Estrategia 2: Nominatim ──────────────────────────────
    if usar_nominatim:
        coords = _intentar_nominatim(direccion)
        if coords:
            return (coords[0], coords[1], 'nominatim')

    return (None, None, 'sin_resultado')