from django.db import models


# ─────────────────────────────────────────────────────────────
# CIRCUITO
# ─────────────────────────────────────────────────────────────
class Circuito(models.Model):
    """Catálogo único de circuitos con su estado y ciclos temporales."""

    ESTADO_CHOICES = [
        ('afectado', 'Afectado'),
        ('en_servicio', 'En servicio'),
        ('desconocido', 'Desconocido'),
    ]

    ORIGEN_CHOICES = [
        ('afectacion', 'Mensaje de afectación'),
        ('restablecimiento', 'Mensaje de restablecimiento'),
        ('inferido', 'Inferido / histórico'),
    ]

    # ── Identificación ────────────────────────────────────────
    codigo = models.CharField(
        max_length=20,
        unique=True,
        help_text="Código tal como aparece en el canal: OP408, A960, 1243",
    )
    codigo_normalizado = models.CharField(
        max_length=20,
        db_index=True,
        help_text="Uppercase sin espacios ni guiones: OP408, A960, 1243",
    )

    # ── Descriptivos ──────────────────────────────────────────
    direccion = models.TextField(
        blank=True,
        help_text="Dirección/cuadrante que provee la empresa en el mensaje.",
    )
    municipio = models.CharField(max_length=100, blank=True, db_index=True)
    subestacion = models.CharField(max_length=100, blank=True, db_index=True)

    # ── Geolocalización (Folium) ──────────────────────────────
    latitud = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True,
        help_text="Latitud del centro del cuadrante.",
    )
    longitud = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True,
        help_text="Longitud del centro del cuadrante.",
    )
    geometria_geojson = models.JSONField(
        null=True, blank=True,
        help_text="Polígono opcional del cuadrante (GeoJSON) para Folium.",
    )
    usar_cuadrado_default = models.BooleanField(
        default=True,
        help_text=(
            'Si True, se dibuja un cuadrado genérico cuando no hay '
            'geometria_geojson. Si False, el circuito solo se dibuja '
            'si tiene un geojson real.'
        ),
    )

    # ── Estado actual ─────────────────────────────────────────
    estado = models.CharField(
        max_length=20, choices=ESTADO_CHOICES, default='desconocido',
        db_index=True,
    )
    estado_actualizado_en = models.DateTimeField(null=True, blank=True)
    estado_origen = models.CharField(
        max_length=20, choices=ORIGEN_CHOICES, blank=True,
    )

    # ── Último ciclo de AFECTACIÓN ────────────────────────────
    afectacion_inicio_msg = models.DateTimeField(null=True, blank=True)
    afectacion_inicio_contenido = models.DateTimeField(null=True, blank=True)
    afectacion_fin_msg = models.DateTimeField(null=True, blank=True)
    afectacion_fin_contenido = models.DateTimeField(null=True, blank=True)
    afectacion_duracion_msg_min = models.PositiveIntegerField(null=True, blank=True)
    afectacion_duracion_contenido_min = models.PositiveIntegerField(null=True, blank=True)
    afectacion_activa = models.BooleanField(
        default=False,
        help_text="True si aún no llegó el mensaje de restablecimiento.",
    )

    # ── Último ciclo de SERVICIO ──────────────────────────────
    servicio_inicio_msg = models.DateTimeField(null=True, blank=True)
    servicio_inicio_contenido = models.DateTimeField(null=True, blank=True)
    servicio_fin_msg = models.DateTimeField(null=True, blank=True)
    servicio_fin_contenido = models.DateTimeField(null=True, blank=True)
    servicio_duracion_msg_min = models.PositiveIntegerField(null=True, blank=True)
    servicio_duracion_contenido_min = models.PositiveIntegerField(null=True, blank=True)
    servicio_activo = models.BooleanField(
        default=False,
        help_text="True si aún no llegó el mensaje de afectación siguiente.",
    )

    # ── Estadísticas históricas ───────────────────────────────
    total_afectaciones = models.PositiveIntegerField(default=0)
    total_minutos_afectado = models.PositiveIntegerField(
        default=0,
        help_text="Suma acumulada de minutos afectado (por mensaje).",
    )
    primera_mencion = models.DateTimeField(null=True, blank=True)
    ultima_mencion = models.DateTimeField(null=True, blank=True)

    # ── Auditoría ─────────────────────────────────────────────
    notas = models.TextField(blank=True)
    activo = models.BooleanField(default=True)
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Circuito'
        verbose_name_plural = 'Circuitos'
        ordering = ['codigo']
        indexes = [
            models.Index(fields=['estado', '-estado_actualizado_en']),
            models.Index(fields=['codigo_normalizado']),
        ]

    def __str__(self):
        return self.codigo


# ─────────────────────────────────────────────────────────────
# EVENTO CIRCUITO  (trazabilidad completa)
# ─────────────────────────────────────────────────────────────
class EventoCircuito(models.Model):
    """
    Un evento atómico: un mensaje mencionó este circuito.
    Permite reconstruir la historia completa y recalcular
    ciclos si cambia la lógica de clasificación.
    """

    TIPO_CHOICES = [
        ('afectacion', 'Afectación'),
        ('restablecimiento', 'Restablecimiento'),
        ('mencion', 'Mención'),
    ]

    circuito = models.ForeignKey(
        Circuito,
        on_delete=models.CASCADE,
        related_name='eventos',
    )
    mensaje = models.ForeignKey(
        'telegram_base.Mensaje',
        on_delete=models.CASCADE,
        related_name='eventos_circuito',
    )
    tipo = models.CharField(
        max_length=20, choices=TIPO_CHOICES, db_index=True,
    )

    # Los dos tiempos del evento
    fecha_mensaje = models.DateTimeField(
        help_text="msg.fecha (UTC del post en Telegram).",
    )
    fecha_contenido = models.DateTimeField(
        null=True, blank=True,
        help_text="Hora mencionada en el texto del mensaje (si existe).",
    )

    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Evento de circuito'
        verbose_name_plural = 'Eventos de circuitos'
        ordering = ['fecha_mensaje']
        constraints = [
            models.UniqueConstraint(
                fields=['circuito', 'mensaje'],
                name='unico_evento_circuito_mensaje',
            ),
        ]
        indexes = [
            models.Index(fields=['circuito', 'fecha_mensaje']),
            models.Index(fields=['circuito', 'tipo', 'fecha_mensaje']),
        ]

    def __str__(self):
        return f'{self.circuito.codigo} · {self.tipo} · {self.fecha_mensaje:%Y-%m-%d %H:%M}'