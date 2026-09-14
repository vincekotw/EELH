"""
Filtros de template para formatear duraciones.
"""

from django import template

register = template.Library()


@register.filter
def format_duracion(minutos):
    """
    Convierte minutos (int) a formato legible:
        0     → "—"
        45    → "45 min"
        60    → "1h"
        125   → "2h 5m"
        1440  → "24h"
        2386  → "39h 46m"
    """
    if minutos is None or minutos == '':
        return '—'

    try:
        minutos = int(minutos)
    except (ValueError, TypeError):
        return '—'

    if minutos <= 0:
        return '—'

    if minutos < 60:
        return f'{minutos} min'

    horas = minutos // 60
    resto = minutos % 60

    if resto == 0:
        return f'{horas}h'

    return f'{horas}h {resto}m'


@register.filter
def format_duracion_corta(minutos):
    """
    Versión compacta sin espacios: 2h5m, 39h46m.
    Útil para tablas donde el espacio es limitado.
    """
    if minutos is None or minutos == '':
        return '—'

    try:
        minutos = int(minutos)
    except (ValueError, TypeError):
        return '—'

    if minutos <= 0:
        return '—'

    if minutos < 60:
        return f'{minutos}min'

    horas = minutos // 60
    resto = minutos % 60

    if resto == 0:
        return f'{horas}h'

    return f'{horas}h{resto}m'