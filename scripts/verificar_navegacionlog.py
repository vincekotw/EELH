"""
Verifica el estado de la secuencia de usuarios_navegacionlog.
"""

from django.db import connection


def verificar():
    print('═' * 55)
    print('  VERIFICACIÓN DE NAVEGACIONLOG')
    print('═' * 55)
    print()

    with connection.cursor() as c:
        # Contar filas
        c.execute('SELECT COUNT(*) FROM usuarios_navegacionlog')
        total = c.fetchone()[0]
        print(f'Filas en usuarios_navegacionlog:  {total}')

        # Ver la secuencia
        c.execute("SELECT last_value FROM usuarios_navegacionlog_id_seq")
        last = c.fetchone()[0]
        print(f'Valor actual de la secuencia:     {last}')

        # Ver el max id actual
        c.execute('SELECT COALESCE(MAX(id), 0) FROM usuarios_navegacionlog')
        max_id = c.fetchone()[0]
        print(f'MAX(id) en la tabla:               {max_id}')
        print()

        # Diagnóstico
        print('═' * 55)
        if last >= max_id:
            print('✅ SECUENCIA OK')
            print(f'   Próximo INSERT usará id={last + 1}')
            print(f'   (por encima del MAX actual = {max_id})')
        else:
            print('❌ SECUENCIA DESINCRONIZADA')
            print(f'   La secuencia apunta a {last} pero el MAX es {max_id}')
            print(f'   Esto causará UniqueViolation en el próximo INSERT')
        print('═' * 55)


verificar()