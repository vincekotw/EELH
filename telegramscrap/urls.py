
from django.contrib import admin
from django.urls import path, include
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('admin/', admin.site.urls),
    path('circuitos/', include('apps.circuitos.urls', namespace='circuitos')),
    path('usuarios/', include('apps.usuarios.urls')),
    path('metricas/', include('apps.metricas.urls')),
]
