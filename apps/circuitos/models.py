from django.db import models
from django.utils import timezone


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
         ('reportes_usuarios', 'Consenso de reportes'),
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

        # ── Estado comunitario (reportes anónimos) ────────────────
    estado_comunitario = models.CharField(
        max_length=20,
        choices=[
            ('afectado', 'Afectado (reportes)'),
            ('en_servicio', 'En servicio (reportes)'),
            ('intermitente', 'Intermitente (reportes)'),
            ('sin_reportes', 'Sin reportes'),
        ],
        default='sin_reportes',
        db_index=True,
    )
    estado_comunitario_actualizado_en = models.DateTimeField(null=True, blank=True)
    reportes_usuarios_total = models.PositiveIntegerField(default=0)

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


# ═══════════════════════════════════════════════════════════════
# ALERTA MASIVA (apagón de SEN)
# ═══════════════════════════════════════════════════════════════
class AlertaMasiva(models.Model):
    """Representa un evento de apagón masivo del SEN."""

    TIPO_CHOICES = [
        ('occidente', 'Apagón en occidente'),
        ('oriente', 'Apagón en oriente'),
        ('habana', 'Apagón en La Habana'),
        ('total', 'Apagón total (toda la isla)'),
        ('parcial', 'Apagón parcial'),
    ]

    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES)
    titulo = models.CharField(max_length=255)
    descripcion = models.TextField(blank=True)

    iniciado_en = models.DateTimeField(db_index=True)
    finalizado_en = models.DateTimeField(null=True, blank=True)
    activo = models.BooleanField(
        default=True, db_index=True,
        help_text="True mientras la home muestre el modo apagón.",
    )

    mensaje_deteccion = models.ForeignKey(
        'telegram_base.Mensaje',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='alertas_masivas',
    )
    mensaje_fin_oficial = models.ForeignKey(
        'telegram_base.Mensaje',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='alertas_cerradas',
    )

    reportes_usuarios = models.PositiveIntegerField(default=0)

    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-iniciado_en']
        verbose_name = 'Alerta masiva'
        verbose_name_plural = 'Alertas masivas'

    def __str__(self):
        return f'{self.get_tipo_display()} · {self.iniciado_en:%Y-%m-%d %H:%M}'

    @property
    def duracion_min(self):
        fin = self.finalizado_en or timezone.now()
        return int((fin - self.iniciado_en).total_seconds() / 60)


class ReporteUsuario(models.Model):
    """Reporte anónimo de un usuario sobre el estado de un circuito."""

    ESTADO_CHOICES = [
        ('afectado', 'Sin servicio'),
        ('en_servicio', 'Con servicio'),
        ('intermitente', 'Intermitente'),
    ]

    circuito = models.ForeignKey(
        Circuito, on_delete=models.CASCADE, related_name='reportes_usuarios',
    )
    alerta = models.ForeignKey(
        AlertaMasiva, on_delete=models.CASCADE, related_name='reportes',
        null=True, blank=True,
    )

    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES)
    comentario = models.TextField(blank=True, max_length=300)

    ip_hash = models.CharField(max_length=64, db_index=True)
    user_agent = models.CharField(max_length=255, blank=True)

    creado_en = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-creado_en']
        indexes = [
            models.Index(fields=['circuito', '-creado_en']),
            models.Index(fields=['ip_hash', '-creado_en']),
        ]
        verbose_name = 'Reporte de usuario'
        verbose_name_plural = 'Reportes de usuarios'

    def __str__(self):
        return f'{self.circuito.codigo} → {self.estado}'


class SnapshotAverias(models.Model):
    """Registra los circuitos afectados según un mensaje de 'Averías existentes'."""
    mensaje = models.OneToOneField(
        'telegram_base.Mensaje',
        on_delete=models.CASCADE,
        related_name='snapshot_averias'
    )
    fecha = models.DateTimeField()
    circuitos_afectados = models.JSONField(
        default=list,
        help_text="Lista de códigos de circuito reportados como afectados."
    )
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-fecha']
        verbose_name = 'Snapshot de averías'
        verbose_name_plural = 'Snapshots de averías'

    def __str__(self):
        return f'Snapshot {self.fecha:%Y-%m-%d %H:%M} - {len(self.circuitos_afectados)} circuitos'


class ReporteDiscrepancia(models.Model):
    """
    Un usuario reporta que un circuito oficialmente 'en servicio'
    no tiene luz realmente. Al llegar a un umbral de IPs únicas,
    se cambia el estado del circuito.
    """

    ESTADO_REPORTADO_CHOICES = [
        ('sin_luz', 'Sin luz'),
        ('intermitente', 'Intermitente'),
    ]

    circuito = models.ForeignKey(
        Circuito,
        on_delete=models.CASCADE,
        related_name='reportes_discrepancia',
    )
    estado_reportado = models.CharField(
        max_length=20,
        choices=ESTADO_REPORTADO_CHOICES,
        default='sin_luz',
    )
    comentario = models.TextField(blank=True, max_length=300)

    ip_hash = models.CharField(max_length=64, db_index=True)
    user_agent = models.CharField(max_length=255, blank=True)

    # Marcado a True si este reporte contribuyó al cambio de estado
    cambio_estado = models.BooleanField(default=False)

    creado_en = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-creado_en']
        indexes = [
            models.Index(fields=['circuito', '-creado_en']),
            models.Index(fields=['ip_hash', 'circuito', '-creado_en']),
        ]
        verbose_name = 'Reporte de discrepancia'
        verbose_name_plural = 'Reportes de discrepancia'

    def __str__(self):
        return f'{self.circuito.codigo} → {self.estado_reportado}'


class CircuitoDAF(models.Model):
    """
    Registro de un circuito protegido por Disparo Automático por
    Frecuencia (DAF) durante un período específico.
    Se rellena al procesar mensajes tipo "rotación DAF semanal".
    """
    circuito = models.ForeignKey(
        Circuito,
        on_delete=models.CASCADE,
        related_name='periodos_daf',
    )
    desde = models.DateField(db_index=True)
    hasta = models.DateField(db_index=True)
    mensaje_origen = models.ForeignKey(
        'telegram_base.Mensaje',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='periodos_daf',
    )
    activo = models.BooleanField(default=True, db_index=True)
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Circuito DAF'
        verbose_name_plural = 'Circuitos DAF'
        ordering = ['-desde', 'circuito__codigo']
        indexes = [
            models.Index(fields=['activo', '-desde']),
        ]

    def __str__(self):
        return f'{self.circuito.codigo} DAF {self.desde} → {self.hasta}'