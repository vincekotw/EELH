# apps/circuitos/urls.py
from django.urls import path
from . import views

app_name = 'circuitos'

urlpatterns = [
    path('mapa/', views.mapa_circuitos, name='mapa'),
    path('lista/', views.lista_circuitos, name='lista'),
    path('c/<str:codigo>/', views.detalle_circuito, name='detalle'),
    path('reportar/', views.reportar_estado, name='reportar'),
]