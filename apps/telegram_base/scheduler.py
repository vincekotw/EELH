"""
Scheduler integrado en Django.
Arranca automáticamente con `runserver` y otros comandos de la lista blanca.

Ejecuta cada hora:
  1. scrape_telegram   → trae mensajes nuevos del canal
  2. recalcular_abiertos → actualiza duraciones de ciclos activos
"""

import logging
import os

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from django.conf import settings
from django.core.management import call_command


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
)
logger = logging.getLogger(__name__)


# Guardamos la instancia a nivel de módulo para no arrancar dos veces
_scheduler: BackgroundScheduler | None = None


def job_scrape_telegram():
    """
    Job horario:
      1. Scrapea el canal y guarda mensajes nuevos.
      2. Aplica los mensajes a los circuitos (afectación/restablecimiento).
      3. Recalcula duraciones de ciclos abiertos hasta el momento actual.
    """
    logger.info('▶️  Job programado: scrape_telegram')

    # ── Paso 1: scrape ────────────────────────────────────────
    try:
        call_command('scrape_telegram')
        logger.info('✅ scrape_telegram completado.')
    except Exception:
        logger.exception('❌ Error en scrape_telegram, se aborta el job.')
        return

    # ── Paso 2: recalcular duraciones abiertas ────────────────
    try:
        from apps.circuitos.services.actualizador import recalcular_abiertos
        recalcular_abiertos()
        logger.info('✅ Duraciones de ciclos abiertos actualizadas.')
    except Exception:
        logger.exception('❌ Error en recalcular_abiertos')


def start(run_now: bool = False) -> BackgroundScheduler | None:
    """Arranca el scheduler en segundo plano (no bloquea)."""
    global _scheduler

    if _scheduler is not None:
        logger.info('ℹ️  Scheduler ya estaba arrancado, no se reinicia.')
        return _scheduler

    tz = getattr(settings, 'TIME_ZONE', 'UTC') or 'UTC'

    scheduler = BackgroundScheduler(
        timezone=tz,
        job_defaults={
            'coalesce': True,
            'max_instances': 1,
            'misfire_grace_time': 300,
        },
    )

    scheduler.add_job(
        job_scrape_telegram,
        trigger=CronTrigger(minute=0, timezone=tz),
        id='scrape_telegram_hourly',
        name='Scrape Telegram cada hora',
        replace_existing=True,
    )

    # Arrancar primero...
    scheduler.start()
    _scheduler = scheduler
    logger.info(f'🚀 Scheduler arrancado en segundo plano (TZ={tz}).')

    # ...y luego leer next_run_time (ya está disponible)
    for job in scheduler.get_jobs():
        logger.info(f'📅 Job registrado: {job.name} → próximo: {job.next_run_time}')

    if run_now:
        logger.info('⚡ Ejecutando scrape inicial...')
        job_scrape_telegram()

    return scheduler