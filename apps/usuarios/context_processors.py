"""
Context processors para la app usuarios.
Añaden variables globales a todas las plantillas.
"""


def notificaciones_context(request):
    """
    Añade `notif_no_leidas` al contexto de todas las plantillas
    cuando el usuario está autenticado.
    """
    if not request.user.is_authenticated:
        return {'notif_no_leidas': 0}

    try:
        count = request.user.notificaciones.filter(leida=False).count()
    except Exception:
        count = 0

    return {'notif_no_leidas': count}