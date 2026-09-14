from django.contrib import admin
from .models import EstadoScraper, Mensaje, ScrapeRun


@admin.register(EstadoScraper)
class EstadoScraperAdmin(admin.ModelAdmin):
    list_display = ('ultimo_id_escaneado', 'ultimo_scrape')

    def has_add_permission(self, request):
        # Solo permitir una fila
        return not EstadoScraper.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Mensaje)
class MensajeAdmin(admin.ModelAdmin):
    list_display = ('telegram_id', 'fecha', 'tipo_evento', 'es_afectacion', 'tipo_media')
    list_filter = ('tipo_evento', 'es_afectacion', 'tipo_media')   # ← nuevo filtro
    search_fields = ('texto', 'telegram_id')
    date_hierarchy = 'fecha'
    readonly_fields = ('creado_en', 'actualizado_en')


@admin.register(ScrapeRun)
class ScrapeRunAdmin(admin.ModelAdmin):
    list_display = ('iniciado_en', 'estado', 'mensajes_nuevos', 'mensajes_actualizados', 'ids_vacios')
    list_filter = ('estado',)
    readonly_fields = ('iniciado_en', 'terminado_en')

# Register your models here.
