"""
Extrae la dirección/cuadrante de un circuito a partir del texto
de un mensaje de la Empresa Eléctrica.

Formato típico:
    👉 OP408:Alrededores del cuadrante desde Vía Blanca hasta...
    👉 A800:\nPanamérica y Mazorra
    👉 D632\n: Alrededores de calles...
    👉 OP318,OP406,OP306: Soterrados Habana Vieja.

Consideraciones:
  - Los mensajes terminan con emojis decorativos (🚨📣, ✅, 📌).
  - Algunos incluyen boilerplate: "📌 Usted puede...", "Manténgase informado..."
  - El parser debe cortar antes de esos adornos.
"""

import re


# Máximo de caracteres entre el código y el ":" para evitar
# saltar a otro circuito cuando el formato es raro.
MAX_CARACTERES_HASTA_COLON = 80


# ── Terminadores del bloque de dirección ──────────────────────
# Al encontrar cualquiera de estos, la dirección se corta.
TERMINADORES = re.compile(
    r'(?:'
    r'👉'                        # siguiente circuito
    r'|📌'                       # separador de boilerplate
    r'|Usted puede'              # boilerplate común
    r'|Manténgase informado'     # boilerplate común
    r'|Si usted presenta'        # boilerplate común
    r'|📣'                       # emoji de cierre
    r'|🚨'                       # emoji de alerta
    r'|✅'                       # emoji de confirmación
    r'|🛑'                       # emoji de stop
    r'|🔴'                       # círculo rojo
    r'|🟢'                       # círculo verde
    r'|⚡'                       # rayo
    r'|🔔'                       # campana
    r'|💡'                       # bombilla
    r'|📉'                       # gráfica descendente
    r'|☑️?'                      # checkbox
    r'|📋'                       # clipboard
    r'|🔧'                       # wrench
    r'|⚠️?'                      # warning
    r')',
    re.IGNORECASE,
)

# Emojis que pueden quedar al final tras el corte. Los limpiamos.
RE_EMOJI_FINAL = re.compile(
    r'[\s🚨📣✅🛑🔴🟢⚡🔔💡📉☑️📋🔧⚠️📌]+$',
    re.IGNORECASE,
)

# Espacios múltiples, saltos de línea y tabs
RE_ESPACIOS = re.compile(r'\s+')


def _limpiar_direccion(raw: str) -> str:
    """Colapsa espacios, quita emojis finales y puntuación suelta."""
    if not raw:
        return ''

    # Colapsar espacios/saltos
    limpio = RE_ESPACIOS.sub(' ', raw).strip()

    # Quitar emojis decorativos al final
    limpio = RE_EMOJI_FINAL.sub('', limpio).strip()

    # Quitar puntuación suelta al inicio/final
    limpio = limpio.strip(' :;,.')
    limpio = limpio.strip()

    # Si quedó muy corto, probablemente era solo basura
    if len(limpio) < 3:
        return ''

    return limpio


def extraer_direccion(texto: str, codigo: str) -> str:
    """
    Extrae la dirección asociada a `codigo` en el texto.
    Devuelve la más larga encontrada, o '' si no hay.
    """
    if not texto or not codigo:
        return ''

    # 👉 [CODIGO] [hasta 80 chars, cualquier cosa] : [dirección] [hasta terminador]
    patron = re.compile(
        rf'👉\s*{re.escape(codigo)}(?![A-Z0-9]).{{0,{MAX_CARACTERES_HASTA_COLON}}}?:\s*(.*?)'
        rf'(?={TERMINADORES.pattern}|$)',
        re.IGNORECASE | re.DOTALL,
    )

    direcciones = []
    for m in patron.finditer(texto):
        limpia = _limpiar_direccion(m.group(1))
        if limpia:
            direcciones.append(limpia)

    if not direcciones:
        return ''

    return max(direcciones, key=len)