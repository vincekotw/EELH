from django.urls import path
from . import views

app_name = 'metricas'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),

    # Endpoints AJAX
    path('api/tendencia/', views.api_tendencia, name='api_tendencia'),
    path('api/activos-hora/', views.api_activos_hora, name='api_activos_hora'),
    path('api/media-diaria/', views.api_media_diaria, name='api_media_diaria'),
    path('api/rotacion/', views.api_rotacion_media, name='api_rotacion'),
    path('api/mayor-rotacion/', views.api_mayor_rotacion, name='api_mayor_rotacion'),
    path('api/sin-rotacion/', views.api_sin_rotacion, name='api_sin_rotacion'),
    path('api/daf/', views.api_daf_semana, name='api_daf'),
    path('api/mas-horas-sin-servicio/', views.api_mas_horas_sin_servicio, name='api_mas_horas_sin_servicio'),
    path('api/mas-horas-servicio/', views.api_mas_horas_servicio, name='api_mas_horas_servicio'),
    path('api/mttr/', views.api_mttr, name='api_mttr'),
    path('api/disponibilidad/', views.api_disponibilidad, name='api_disponibilidad'),
    path('api/heatmap/', views.api_heatmap_hora, name='api_heatmap'),
    path('api/municipios/', views.api_top_municipios, name='api_municipios'),
    path('api/estabilidad/', views.api_estabilidad, name='api_estabilidad'),
    path('api/tiempo-entre/', views.api_tiempo_entre, name='api_tiempo_entre'),
    path('api/prediccion/', views.api_prediccion, name='api_prediccion'),
    path('api/ranking/', views.api_ranking_usuarios, name='api_ranking'),
    path('api/alertas/', views.api_alertas_historicas, name='api_alertas'),
    path('api/cronicos/', views.api_cronicos, name='api_cronicos'),
    path('api/duracion-usuarios/', views.api_duracion_usuarios, name='api_duracion_usuarios'),
    path('api/todo/', views.api_todo, name='api_todo'),
]