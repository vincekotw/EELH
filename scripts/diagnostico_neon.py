"""
Diagnóstico del estado actual de la base de datos Neon.
"""

from django.db import connection
from django.conf import settings


def diag():
    # Info de conexión
    db = settings.DATABASES['default']
    print('═' * 60)
    print('  DIAGNÓSTICO DE NEON')
    print('═' * 60)
    print(f'Engine: {db["ENGINE"]}')
    print(f'Host:   {db.get("HOST", "—")}')
    print(f'Name:   {db.get("NAME", "—")}')
    print()

    with connection.cursor() as c:
        # Contar tablas
        c.execute("""
            SELECT COUNT(*)
            FROM information_schema.tables
            WHERE table_schema = 'public'
        """)
        total_tablas = c.fetchone()[0]
        print(f'Tablas en public: {total_tablas}')
        print()

        # Listar tablas de nuestras apps con su conteo
        apps_tablas = [
            ('auth_user', 'Usuarios'),
            ('telegram_base_mensaje', 'Mensajes'),
            ('circuitos_circuito', 'Circuitos'),
            ('circuitos_eventocircuito', 'Eventos'),
            ('usuarios_profile', 'Profiles'),
        ]

        print('Conteo de filas:')
        for tabla, label in apps_tablas:
            try:
                c.execute(f'SELECT COUNT(*) FROM "{tabla}"')
                count = c.fetchone()[0]
                print(f'  {label:15s} ({tabla}): {count}')
            except Exception as e:
                print(f'  {label:15s} ({tabla}): ❌ {e}')


diag()