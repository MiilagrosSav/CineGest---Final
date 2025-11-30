from django.urls import path
from . import views

app_name = 'valoraciones'

urlpatterns = [
    path('registrar/', views.registrar_valoracion, name='registrar_valoracion'),
]
