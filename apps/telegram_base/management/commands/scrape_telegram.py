"""
Comando de gestión: scrape_telegram
Ejecuta el scraping del canal configurado en settings.

Uso:
    python manage.py scrape_telegram
    python manage.py scrape_telegram --full      # re-escanea desde TELEGRAM_ID_INICIAL
    python manage.py scrape_telegram --dry-run   # no escribe en BD
"""

import sys
from datetime import datetime, timezone

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone as dj_timezone

from apps.telegram_base.models import EstadoScraper, Mensaje, ScrapeRun
from apps.circuitos.services.actualizador import procesar_mensaje
from apps.telegram_base.services import scraper


class Command(BaseCommand):
    help = 'Extrae los mensajes nuevos del canal de Telegram configurado.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--full',
            action='store_true',
            help='Ignora el estado guardado y empieza desde TELEGRAM_ID_INICIAL.',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Simula el scraping sin guardar en la base de datos.',
        )

    def handle(self, *args, **options):
        full = options['full']
        dry_run = options['dry_run']

        canal = settings.TELEGRAM_CANAL_USERNAME
        id_inicial = settings.TELEGRAM_ID_INICIAL
        pausa = settings.TELEGRAM_PAUSA
        timeout = settings.TELEGRAM_TIMEOUT

        self.stdout.write(self.style.NOTICE(
            f'▶️  Scraping @{canal}  (full={full}, dry_run={dry_run})'
        ))

        # ── Determinar rango ─────────────────────────────────
        estado = EstadoScraper.get_solo()

        if full or estado.ultimo_id_escaneado == 0:
            id_desde = id_inicial
        else:
            id_desde = estado.ultimo_id_escaneado + 1

        id_hasta = scraper.obtener_ultimo_id(canal, timeout=timeout)
        if id_hasta is None:
            self.stderr.write(self.style.ERROR(
                '❌ No se pudo detectar el último ID del canal.'
            ))
            return

        if id_desde > id_hasta:
            self.stdout.write(self.style.SUCCESS(
                f'✅ Sin mensajes nuevos (último ID escaneado: {estado.ultimo_id_escaneado}).'
            ))
            return

        self.stdout.write(f'   Rango a procesar: {id_desde} → {id_hasta} '
                          f'({id_hasta - id_desde + 1} IDs)')

        # ── Crear registro de la ejecución ───────────────────
        run = ScrapeRun.objects.create(
            iniciado_en=dj_timezone.now(),
            estado='en_curso',
            id_inicio=id_desde,
            id_fin=id_hasta,
        )

        nuevos = 0
        actualizados = 0
        vacios = 0
        ultimo_ok = estado.ultimo_id_escaneado
        contador_checkpoint = 0

        def on_progreso(msg_id: int, encontrado: bool):
            nonlocal contador_checkpoint, ultimo_ok
            contador_checkpoint += 1
            if encontrado:
                ultimo_ok = msg_id
            # Checkpoint cada 25 mensajes (o al final)
            if contador_checkpoint % 25 == 0 and not dry_run:
                EstadoScraper.objects.filter(pk=1).update(
                    ultimo_id_escaneado=ultimo_ok,
                    ultimo_scrape=dj_timezone.now(),
                )

        try:
            for data in scraper.iterar_rango(
                canal, id_desde, id_hasta,
                pausa=pausa, timeout=timeout,
                on_progreso=on_progreso,
            ):
                # Convertir fecha ISO → datetime
                fecha_iso = data.pop('fecha', None)
                if fecha_iso:
                    try:
                        data['fecha'] = datetime.fromisoformat(fecha_iso)
                    except ValueError:
                        data['fecha'] = None
                else:
                    data['fecha'] = None

                if dry_run:
                    self.stdout.write(
                        f'   [dry-run] {data["telegram_id"]} '
                        f'afectacion={data["es_afectacion"]} '
                        f'circuitos={data["circuitos_mencionados"]}'
                    )
                    if data['es_afectacion']:
                        nuevos += 1
                    else:
                        actualizados += 1
                    continue

                
                telegram_id = data.pop('telegram_id')
                mensaje_obj, created = Mensaje.objects.update_or_create(
                    telegram_id=telegram_id,
                    defaults=data,
                )

                # Aplicar el mensaje a los circuitos
                procesar_mensaje(mensaje_obj)
                if created:
                    nuevos += 1
                else:
                    actualizados += 1

        except KeyboardInterrupt:
            self.stderr.write(self.style.WARNING('\n⛔ Interrumpido por el usuario.'))
            run.estado = 'parcial'
        except Exception as e:
            self.stderr.write(self.style.ERROR(f'\n❌ Error: {e}'))
            run.estado = 'error'
            run.mensaje_error = str(e)
        else:
            run.estado = 'ok'
        finally:
            run.terminado_en = dj_timezone.now()
            run.mensajes_nuevos = nuevos
            run.mensajes_actualizados = actualizados
            run.ids_vacios = (id_hasta - id_desde + 1) - (nuevos + actualizados)
            run.save()

            # Actualización final del estado
            if not dry_run:
                EstadoScraper.objects.filter(pk=1).update(
                    ultimo_id_escaneado=id_hasta,
                    ultimo_scrape=dj_timezone.now(),
                )

        self.stdout.write(self.style.SUCCESS(
            f'\n✅ Terminado.  nuevos={nuevos}  actualizados={actualizados}  '
            f'vacios={run.ids_vacios}  estado={run.estado}'
        ))