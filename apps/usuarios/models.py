from django.conf import settings
from django.db import models


User = settings.AUTH_USER_MODEL


# ═══════════════════════════════════════════════════════════════
# PROFILE (extiende User 1-1)
# ═══════════════════════════════════════════════════════════════
class Profile(models.Model):
    """
    Datos adicionales del usuario que no están en el modelo User
    de Django. Se crea automáticamente con signal al registrarse.
    """
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='profile',
    )
    bio = models.TextField(blank=True, max_length=500)

    # Preferencias de notificación
    notif_email = models.BooleanField(default=True)
    notif_push = models.BooleanField(
        default=False,
        help_text='Notificaciones Web Push (requiere permiso del navegador)',
    )
    notif_afectacion = models.BooleanField(
        default=True,
        help_text='Notificar cuando un circuito vinculado se afecte',
    )
    notif_restablecimiento = models.BooleanField(
        default=True,
        help_text='Notificar cuando un circuito vinculado se restablezca',
    )

    # Metadata
    acepta_terminos = models.BooleanField(default=False)
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Perfil'
        verbose_name_plural = 'Perfiles'

    def __str__(self):
        return f'Perfil de {self.user.username}'


# ═══════════════════════════════════════════════════════════════
# CIRCUITOS VINCULADOS
# ═══════════════════════════════════════════════════════════════
class CircuitoUsuario(models.Model):
    """Vinculación N-N entre usuario y circuito."""
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='circuitos_vinculados',
    )
    circuito = models.ForeignKey(
        'circuitos.Circuito',
        on_delete=models.CASCADE,
        related_name='usuarios_vinculados',
    )
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Circuito vinculado'
        verbose_name_plural = 'Circuitos vinculados'
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'circuito'],
                name='unico_usuario_circuito',
            ),
        ]
        ordering = ['circuito__codigo']

    def __str__(self):
        return f'{self.user.username} → {self.circuito.codigo}'


# ═══════════════════════════════════════════════════════════════
# NOTIFICACIONES (in-app)
# ═══════════════════════════════════════════════════════════════
class Notificacion(models.Model):
    """Notificación in-app generada por el scraper al detectar cambios."""

    TIPO_CHOICES = [
        ('afectacion', 'Afectación'),
        ('restablecimiento', 'Restablecimiento'),
        ('sistema', 'Mensaje del sistema'),
    ]

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='notificaciones',
    )
    circuito = models.ForeignKey(
        'circuitos.Circuito',
        on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='notificaciones',
    )
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES)
    titulo = models.CharField(max_length=200)
    mensaje = models.TextField(blank=True)
    enlace = models.CharField(max_length=300, blank=True)

    leida = models.BooleanField(default=False, db_index=True)
    creado_en = models.DateTimeField(auto_now_add=True, db_index=True)

    # Para evitar duplicados si el scraper corre múltiples veces
    dedup_key = models.CharField(
        max_length=120, blank=True, db_index=True,
        help_text='Clave única para deduplicar (ej: user:circuito:msg_id)',
    )

    class Meta:
        verbose_name = 'Notificación'
        verbose_name_plural = 'Notificaciones'
        ordering = ['-creado_en']
        indexes = [
            models.Index(fields=['user', 'leida', '-creado_en']),
        ]

    def __str__(self):
        return f'{self.user.username} → {self.titulo}'


# ═══════════════════════════════════════════════════════════════
# LOG DE NAVEGACIÓN
# ═══════════════════════════════════════════════════════════════
class NavegacionLog(models.Model):
    """
    Registro de cada petición web hecha por un usuario autenticado.
    Anonimizado por IP para cumplir con privacidad.
    """
    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='navegacion',
    )
    path = models.CharField(max_length=300)
    metodo = models.CharField(max_length=10)
    ip_hash = models.CharField(max_length=64, db_index=True, blank=True)
    user_agent = models.CharField(max_length=255, blank=True)
    referrer = models.CharField(max_length=300, blank=True)
    creado_en = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = 'Navegación'
        verbose_name_plural = 'Navegaciones'
        ordering = ['-creado_en']
        indexes = [
            models.Index(fields=['user', '-creado_en']),
            models.Index(fields=['-creado_en']),
        ]

    def __str__(self):
        return f'{self.user.username if self.user else "anon"} → {self.path}'

from django.db.models.signals import post_save
from django.dispatch import receiver


@receiver(post_save, sender=User)
def crear_profile(sender, instance, created, **kwargs):
    """
    Crea el Profile si no existe. Idempotente: usa get_or_create
    para que sea seguro aunque se dispare varias veces.
    """
    Profile.objects.get_or_create(user=instance)