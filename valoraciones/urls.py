from django.urls import path
from . import views

app_name = 'valoraciones'

urlpatterns = [
    path('registrar/', views.registrar_valoracion, name='registrar_valoracion'),
    path('notificaciones/', views.obtener_notificaciones, name='obtener_notificaciones'),
    path('notificaciones/<int:notificacion_id>/leer/', views.marcar_notificacion_leida, name='marcar_leida'),
    path('notificaciones/leer-todas/', views.marcar_todas_leidas, name='marcar_todas_leidas'),
    path('modal/', views.modal_valoracion, name='modal_valoracion'),
    path('pelicula/<int:pelicula_id>/comentarios/', views.comentarios_pelicula, name='comentarios_pelicula'),
    path('pelicula/<int:pelicula_id>/valoraciones/ajax/', views.obtener_valoraciones_pelicula, name='obtener_valoraciones_ajax'),
]
