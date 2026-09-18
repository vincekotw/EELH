"""
Resetea las secuencias de PostgreSQL.

Solo procesa tablas que tengan una columna 'id' con secuencia asociada,
ignorando tablas como django_session (que usan otras PKs).
"""

from django.db import connection


def resetear():
    print('═' * 60)
    print('  RESET DE SECUENCIAS v3')
    print('═' * 60)
    print(f'  DB:   {connection.settings_dict["NAME"]}')
    print(f'  Host: {connection.settings_dict.get("HOST", "local")}')
    print()

    # ── Query: solo tablas que tienen columna 'id' ────────────
    query = """
        SELECT
            c.table_name,
            pg_get_serial_sequence(
                quote_ident(c.table_schema) || '.' || quote_ident(c.table_name),
                'id'
            ) AS secuencia
        FROM information_schema.columns c
        WHERE c.table_schema = 'public'
          AND c.column_name = 'id'
        ORDER BY c.table_name
    """

    with connection.cursor() as cursor:
        cursor.execute(query)
        filas = cursor.fetchall()

    print(f'Tablas con columna id: {len(filas)}')
    print()

    exitos = 0
    sin_secuencia = 0
    errores = 0

    with connection.cursor() as cursor:
        for tabla, secuencia in filas:
            if not secuencia:
                sin_secuencia += 1
                continue

            try:
                cursor.execute(f"""
                    SELECT setval(
                        %s,
                        COALESCE((SELECT MAX(id) FROM "{tabla}"), 0) + 1,
                        false
                    )
                """, [secuencia])
                nuevo = cursor.fetchone()[0]
                print(f'  ✅ {tabla:50s} → {nuevo}')
                exitos += 1
            except Exception as e:
                print(f'  ❌ {tabla:50s} → {e}')
                errores += 1

    print()
    print('═' * 60)
    print(f'  Reseteadas:       {exitos}')
    print(f'  Sin secuencia:    {sin_secuencia}')
    print(f'  Errores:          {errores}')
    print('═' * 60)


resetear()