
from django.contrib import admin
from django.urls import path, include
from . import views
from apps.telegram_base import views as telegram_views

urlpatterns = [
    path('', views.home, name='home'),
    path('admin/', admin.site.urls),
    path('circuitos/', include('apps.circuitos.urls', namespace='circuitos')),
    path('usuarios/', include('apps.usuarios.urls')),
    path('metricas/', include('apps.metricas.urls')),
    path('telegram/', include('apps.telegram_base.urls')),
    path('api/cron/tick/', telegram_views.cron_tick, name='cron_tick'),
]
