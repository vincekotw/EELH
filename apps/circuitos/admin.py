from django.contrib import admin
from .models import Circuito, EventoCircuito


@admin.register(Circuito)
class CircuitoAdmin(admin.ModelAdmin):
    list_display = (
        'codigo', 'estado', 'total_afectaciones', 'total_minutos_afectado',
        'afectacion_activa', 'ultima_mencion',
    )
    list_filter = ('estado', 'afectacion_activa', 'servicio_activo', 'municipio')
    search_fields = ('codigo', 'codigo_normalizado', 'direccion', 'municipio')
    readonly_fields = (
        'codigo_normalizado', 'primera_mencion', 'ultima_mencion',
        'total_afectaciones', 'total_minutos_afectado',
        'creado_en', 'actualizado_en',
    )
    fieldsets = (
        ('Identificación', {
            'fields': ('codigo', 'codigo_normalizado', 'direccion', 'municipio', 'subestacion'),
        }),
        ('Geolocalización', {
            'fields': ('latitud', 'longitud', 'geometria_geojson'),
        }),
        ('Estado', {
            'fields': ('estado', 'estado_origen', 'estado_actualizado_en'),
        }),
        ('Último ciclo de afectación', {
            'fields': (
                'afectacion_inicio_msg', 'afectacion_inicio_contenido',
                'afectacion_fin_msg', 'afectacion_fin_contenido',
                'afectacion_duracion_msg_min', 'afectacion_duracion_contenido_min',
                'afectacion_activa',
            ),
        }),
        ('Último ciclo de servicio', {
            'fields': (
                'servicio_inicio_msg', 'servicio_inicio_contenido',
                'servicio_fin_msg', 'servicio_fin_contenido',
                'servicio_duracion_msg_min', 'servicio_duracion_contenido_min',
                'servicio_activo',
            ),
        }),
        ('Histórico', {
            'fields': (
                'primera_mencion', 'ultima_mencion',
                'total_afectaciones', 'total_minutos_afectado',
            ),
        }),
        ('Notas', {'fields': ('notas', 'activo')}),
        ('Auditoría', {'fields': ('creado_en', 'actualizado_en')}),
    )


@admin.register(EventoCircuito)
class EventoCircuitoAdmin(admin.ModelAdmin):
    list_display = ('circuito', 'tipo', 'fecha_mensaje', 'fecha_contenido')
    list_filter = ('tipo',)
    search_fields = ('circuito__codigo',)
    date_hierarchy = 'fecha_mensaje'
    readonly_fields = ('creado_en',)

from .models import AlertaMasiva, ReporteUsuario


@admin.register(AlertaMasiva)
class AlertaMasivaAdmin(admin.ModelAdmin):
    list_display = ('titulo', 'tipo', 'iniciado_en', 'finalizado_en',
                    'activo', 'duracion_min', 'reportes_usuarios')
    list_filter = ('tipo', 'activo')
    search_fields = ('titulo', 'descripcion')
    readonly_fields = ('creado_en', 'actualizado_en', 'duracion_min')
    date_hierarchy = 'iniciado_en'


@admin.register(ReporteUsuario)
class ReporteUsuarioAdmin(admin.ModelAdmin):
    list_display = ('circuito', 'estado', 'creado_en', 'ip_hash_short')
    list_filter = ('estado', 'creado_en')
    search_fields = ('circuito__codigo', 'comentario')
    date_hierarchy = 'creado_en'
    readonly_fields = ('creado_en', 'ip_hash', 'user_agent')

    def ip_hash_short(self, obj):
        return obj.ip_hash[:8]
    ip_hash_short.short_description = 'IP'