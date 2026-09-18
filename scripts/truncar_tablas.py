"""
Borra todas las filas de todas las tablas públicas de PostgreSQL.
Útil para empezar limpio antes de un loaddata.
"""

from django.db import connection


def truncar():
    with connection.cursor() as cursor:
        # Obtener todas las tablas públicas
        cursor.execute("""
            SELECT tablename
            FROM pg_tables
            WHERE schemaname = 'public'
        """)
        tablas = [row[0] for row in cursor.fetchall()]

        if not tablas:
            print('No hay tablas')
            return

        print(f'Truncando {len(tablas)} tablas...')

        # TRUNCATE con CASCADE en una sola sentencia (más rápido)
        # Comillas dobles alrededor de cada nombre para respetar case
        lista = ', '.join(f'"{t}"' for t in tablas)

        cursor.execute(f'TRUNCATE TABLE {lista} RESTART IDENTITY CASCADE')
        print(f'✅ {len(tablas)} tablas truncadas')


truncar()