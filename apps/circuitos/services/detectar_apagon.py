"""
Detecta eventos de apagón masivo del SEN a partir de los mensajes
del canal. Activa/cierra el modo "apagón" en la home.
"""

import re
from django.utils import timezone

from apps.circuitos.models import AlertaMasiva


# ── Patrones de INICIO ────────────────────────────────────────
RE_INICIO = re.compile(
    r'(desconexi[óo]n\s+del\s+sistema\s+el[ée]ctrico|'
    r'ca[íi]da\s+(parcial|total)?\s*del\s+sen|'
    r'ca[íi]da\s+del\s+sistema\s+el[ée]ctrico)',
    re.IGNORECASE,
)

# ── Patrones de FIN OFICIAL ───────────────────────────────────
RE_FIN = re.compile(
    r'restablecido\s+el\s+sistema\s+el[ée]ctrico|'
    r'restablecimiento\s+total\s+del\s+sen',
    re.IGNORECASE,
)

# ── Patrones de PROGRESO (no cambian estado, solo enriquecen) ──
RE_PROGRESO = re.compile(
    r'tras\s+la\s+desconexi[óo]n\s+parcial\s+del\s+sen|'
    r'recuperaci[óo]n\s+del\s+sistema\s+el[ée]ctrico|'
    r'el\s+sistema\s+est[áa]\s+enlazado|'
    r'sincronizadas\s+al\s+sen|'
    r'en\s+l[íi]nea\s+la\s+unidad',
    re.IGNORECASE,
)

# ── EXCLUSIONES (falsos positivos) ────────────────────────────
RE_EXCLUIR = re.compile(
    r'aver[íi]a\s+secundaria\s+por\s+transformador|'
    r'transferido\s+temporalmente\s+la\s+carga',
    re.IGNORECASE,
)


def _detectar_tipo(texto_lower: str) -> str:
    """Devuelve el tipo de apagón según la zona mencionada."""
    if any(k in texto_lower for k in ['toda la isla', 'nacional', 'todo el pa[íi]s']):
        return 'total'
    if any(k in texto_lower for k in ['occidental', 'occidente']):
        return 'occidente'
    if any(k in texto_lower for k in ['oriental', 'oriente']):
        return 'oriente'
    if any(k in texto_lower for k in ['capital', 'la habana', 'habana']):
        return 'habana'
    return 'parcial'


def _titulo_para(tipo: str) -> str:
    return {
        'total': '🚨 Apagón total del SEN',
        'occidente': '🚨 Apagón en el occidente del país',
        'oriente': '🚨 Apagón en el oriente del país',
        'habana': '🚨 Apagón en La Habana',
        'parcial': '🚨 Apagón parcial del SEN',
    }.get(tipo, '🚨 Apagón del SEN')


# ── Configuración ─────────────────────────────────────────────
# Solo procesar mensajes de las últimas N horas.
# Los más viejos se ignoran para no crear alertas al reprocesar
# históricos (inicializar_circuitos.py, importaciones, etc.).
MAX_HORAS_ANTIGUEDAD = 12


def procesar_alerta_masiva(mensaje) -> None:
    """
    Analiza el mensaje y decide si activa, mantiene o cierra la
    alerta masiva. Se llama desde `procesar_mensaje`.
    """
    if not mensaje or not mensaje.texto:
        return

    # ── 1. Ignorar mensajes históricos ───────────────────────
    if mensaje.fecha:
        horas = (timezone.now() - mensaje.fecha).total_seconds() / 3600
        if horas > MAX_HORAS_ANTIGUEDAD:
            return

    texto_lower = mensaje.texto.lower()

    # ── 2. Excluir falsos positivos ──────────────────────────
    if RE_EXCLUIR.search(texto_lower):
        return

    alerta_activa = AlertaMasiva.objects.filter(activo=True).first()

    # ── 3. INICIO ────────────────────────────────────────────
    if RE_INICIO.search(texto_lower):
        # Anti-duplicados: si ya existe una alerta con este mensaje,
        # no crear otra (aunque esté cerrada)
        if AlertaMasiva.objects.filter(mensaje_deteccion=mensaje).exists():
            return

        # Solo crear si no hay una alerta activa (evita spam)
        if alerta_activa:
            return

        tipo = _detectar_tipo(texto_lower)
        AlertaMasiva.objects.create(
            tipo=tipo,
            titulo=_titulo_para(tipo),
            descripcion=mensaje.texto[:500],
            iniciado_en=mensaje.fecha or timezone.now(),
            mensaje_deteccion=mensaje,
            activo=True,
        )
        logger.info(
            'Alerta masiva iniciada: %s (msg=%s)',
            tipo, mensaje.telegram_id,
        )
        return

    # ── 4. FIN OFICIAL ───────────────────────────────────────
    # Buscar CUALQUIER alerta (activa o no) que esté sin finalizar
    # y cuyo inicio sea anterior a este mensaje.
    if RE_FIN.search(texto_lower):
        alerta_sin_fin = (
            AlertaMasiva.objects
            .filter(finalizado_en__isnull=True)
            .filter(iniciado_en__lt=mensaje.fecha)
            .order_by('-iniciado_en')
            .first()
        )
        if alerta_sin_fin:
            alerta_sin_fin.finalizado_en = mensaje.fecha or timezone.now()
            alerta_sin_fin.mensaje_fin_oficial = mensaje
            alerta_sin_fin.save(update_fields=[
                'finalizado_en', 'mensaje_fin_oficial',
            ])
            logger.info(
                'Alerta masiva finalizada (msg=%s)',
                mensaje.telegram_id,
            )
        return

    # ── 5. VUELTA A NORMALIDAD ───────────────────────────────
    if (
        alerta_activa
        and alerta_activa.finalizado_en
        and mensaje.circuitos_mencionados
        and mensaje.fecha
        and mensaje.fecha >= alerta_activa.finalizado_en
    ):
        alerta_activa.activo = False
        alerta_activa.save(update_fields=['activo'])
        logger.info(
            'Modo apagón desactivado (msg=%s)',
            mensaje.telegram_id,
        )

    # ── 6. Fallback: cerrar alertas >24h sin fin oficial ─────
    if alerta_activa and not alerta_activa.finalizado_en:
        horas = (
            timezone.now() - alerta_activa.iniciado_en
        ).total_seconds() / 3600
        if horas > 24:
            alerta_activa.activo = False
            alerta_activa.finalizado_en = timezone.now()
            alerta_activa.save(update_fields=['activo', 'finalizado_en'])
            logger.warning(
                'Alerta masiva cerrada por timeout: %s',
                alerta_activa.titulo,
            )