import os
import sys

from django.apps import AppConfig
from django.conf import settings


class TelegramBaseConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.telegram_base'
    verbose_name = 'Telegram Base'

    def ready(self):
        # ── 0. Respetar ENABLE_SCHEDULER ─────────────────────
        if not getattr(settings, 'ENABLE_SCHEDULER', True):
            print('[Scheduler] Desactivado por ENABLE_SCHEDULER=False')
            return

        # ── 1. Evitar arrancar durante migraciones, shell, tests ───
        if not self._debe_arrancar_scheduler():
            return

        # ── 2. Evitar arrancar en el proceso reloader de runserver ─
        if 'runserver' in sys.argv and os.environ.get('RUN_MAIN') != 'true':
            return

        # ── 3. Arrancar ───────────────────────────────────────
        from apps.telegram_base import scheduler
        scheduler.start(run_now=False)

    @staticmethod
    def _debe_arrancar_scheduler() -> bool:
        """
        Solo arrancamos el scheduler cuando el comando lo justifica.
        """
        if len(sys.argv) < 2:
            return False

        comando = sys.argv[1]

        comandos_validos = {
            'runserver',
            'run_scheduler',
        }

        comandos_excluidos = {
            'migrate', 'makemigrations', 'shell', 'test',
            'collectstatic', 'createsuperuser', 'dumpdata',
            'loaddata', 'scrape_telegram',
        }

        if comando in comandos_excluidos:
            return False

        return comando in comandos_validos