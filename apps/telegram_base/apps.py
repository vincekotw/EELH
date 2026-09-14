import os
import sys

from django.apps import AppConfig


class TelegramBaseConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.telegram_base'
    verbose_name = 'Telegram Base'

    def ready(self):
        # Evitar arrancar durante migraciones, shell, tests, etc.
        if not self._debe_arrancar_scheduler():
            return

        # Evitar arrancar en el proceso reloader de runserver
        # (runserver lanza dos procesos: el padre que vigila y el hijo que sirve)
        if 'runserver' in sys.argv and os.environ.get('RUN_MAIN') != 'true':
            return

        from apps.telegram_base import scheduler
        scheduler.start(run_now=False)

    @staticmethod
    def _debe_arrancar_scheduler() -> bool:
        """
        Solo arrancamos el scheduler cuando el comando lo justifica.
        Evitamos: migrate, makemigrations, shell, test, collectstatic, etc.
        """
        if len(sys.argv) < 2:
            return False

        comando = sys.argv[1]

        # Comandos donde SÍ queremos scheduler
        comandos_validos = {
            'runserver',
            'run_scheduler',   # nuestro comando manual sigue funcionando
        }

        # Comandos donde NUNCA queremos scheduler
        comandos_excluidos = {
            'migrate', 'makemigrations', 'shell', 'test',
            'collectstatic', 'createsuperuser', 'dumpdata',
            'loaddata', 'scrape_telegram',
        }

        if comando in comandos_excluidos:
            return False

        return comando in comandos_validos