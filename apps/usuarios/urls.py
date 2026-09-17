from django.urls import path
from . import views

app_name = 'usuarios'

urlpatterns = [
    path('registro/', views.registro, name='registro'),
    path('login/', views.CustomLoginView.as_view(), name='login'),
    path('logout/', views.CustomLogoutView.as_view(), name='logout'),
    path('perfil/', views.perfil, name='perfil'),
     # Circuitos vinculados
    path('circuitos/', views.circuitos_disponibles, name='circuitos_disponibles'),
    path('circuitos/vincular/', views.vincular_circuito, name='vincular_circuito'),
    path('circuitos/desvincular/', views.desvincular_circuito, name='desvincular_circuito'),
]