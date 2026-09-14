"""Comando: run_scheduler — Arranca el planificador horario (bloqueante)."""

import time

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Arranca el planificador de scraping (modo bloqueante).'

    def add_arguments(self, parser):
        parser.add_argument(
            '--run-now',
            action='store_true',
            help='Ejecuta un scrape inmediato al arrancar el scheduler.',
        )

    def handle(self, *args, **options):
        from apps.telegram_base import scheduler

        scheduler.start(run_now=options['run_now'])
        self.stdout.write(self.style.SUCCESS(
            '🚀 Scheduler en marcha. Ctrl+C para detener.'
        ))

        # Mantener el proceso vivo
        try:
            while True:
                time.sleep(60)
        except KeyboardInterrupt:
            self.stdout.write('\n👋 Detenido.')