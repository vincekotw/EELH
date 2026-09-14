from django.db import models
from django.utils import timezone
from django.conf import settings


# ─────────────────────────────────────────────────────────────
# 1. ESTADO DEL SCRAPER (singleton)
# ─────────────────────────────────────────────────────────────
class EstadoScraper(models.Model):
    """
    Estado global del scraper. Solo existe una fila (pk=1).
    Guarda el último ID procesado para reanudar sin repetir trabajo.
    """

    ultimo_id_escaneado = models.BigIntegerField(
        default=0,
        help_text="ID del último mensaje procesado. El próximo scrape empieza aquí.",
    )
    ultimo_scrape = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'Estado del scraper'
        verbose_name_plural = 'Estado del scraper'

    def save(self, *args, **kwargs):
        # Forzar singleton: siempre pk=1
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def get_solo(cls) -> 'EstadoScraper':
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    def __str__(self):
        return f'Último ID: {self.ultimo_id_escaneado}'


# ─────────────────────────────────────────────────────────────
# 2. MENSAJE
# ─────────────────────────────────────────────────────────────
class Mensaje(models.Model):
    """Un mensaje individual extraído del canal."""

    telegram_id = models.BigIntegerField(
        unique=True,
        help_text="ID numérico del mensaje en Telegram (el de la URL).",
    )

    # Contenido
    texto = models.TextField(blank=True)
    fecha = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Fecha de publicación en UTC (la del atributo datetime).",
    )

    # Media
    media_url = models.URLField(max_length=500, blank=True)
    tipo_media = models.CharField(
        max_length=20,
        choices=[
            ('texto', 'Texto'),
            ('foto', 'Foto'),
            ('video', 'Video'),
            ('documento', 'Documento'),
            ('otro', 'Otro'),
        ],
        default='texto',
    )

    # Enlace directo
    enlace = models.URLField(max_length=300)

    TIPO_EVENTO_CHOICES = [
        ('afectacion', 'Afectación'),
        ('restablecimiento', 'Restablecimiento'),
        ('otro', 'Otro'),
    ]
    tipo_evento = models.CharField(
        max_length=20,
        choices=TIPO_EVENTO_CHOICES,
        default='otro',
        db_index=True,
        help_text="Clasificación del mensaje: afectación, restablecimiento u otro.",
    )

    # Clasificación automática
    es_afectacion = models.BooleanField(
        default=False,
        help_text="True si el texto menciona 'afectó el servicio' o similar.",
    )
    circuitos_mencionados = models.JSONField(
        default=list,
        blank=True,
        help_text="Lista de códigos de circuito detectados (ej: ['OP408', 'P105']).",
    )

    # Auditoría
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Mensaje'
        verbose_name_plural = 'Mensajes'
        ordering = ['-telegram_id']
        indexes = [
            models.Index(fields=['-telegram_id']),
            models.Index(fields=['-fecha']),
            models.Index(fields=['es_afectacion']),
        ]
        indexes = [
        models.Index(fields=['-telegram_id']),
        models.Index(fields=['-fecha']),
        models.Index(fields=['es_afectacion']),
        models.Index(fields=['tipo_evento']),   # ← nuevo
        ]

    def __str__(self):
        preview = (self.texto[:50] + '…') if len(self.texto) > 50 else self.texto
        return f'[{self.telegram_id}] {preview}'


# ─────────────────────────────────────────────────────────────
# 3. LOG DE SCRAPING
# ─────────────────────────────────────────────────────────────
class ScrapeRun(models.Model):
    """Registro de cada ejecución del scraper (auditoría y depuración)."""

    ESTADO_CHOICES = [
        ('ok', 'Completado'),
        ('parcial', 'Parcial'),
        ('error', 'Error'),
        ('en_curso', 'En curso'),
    ]

    iniciado_en = models.DateTimeField(default=timezone.now)
    terminado_en = models.DateTimeField(null=True, blank=True)
    estado = models.CharField(max_length=10, choices=ESTADO_CHOICES, default='en_curso')

    id_inicio = models.BigIntegerField()
    id_fin = models.BigIntegerField(null=True, blank=True)

    mensajes_nuevos = models.IntegerField(default=0)
    mensajes_actualizados = models.IntegerField(default=0)
    ids_vacios = models.IntegerField(default=0)
    mensaje_error = models.TextField(blank=True)

    class Meta:
        verbose_name = 'Ejecución de scraping'
        verbose_name_plural = 'Ejecuciones de scraping'
        ordering = ['-iniciado_en']

    def __str__(self):
        return f'{self.iniciado_en:%Y-%m-%d %H:%M} → {self.estado}'
# Create your models here.
