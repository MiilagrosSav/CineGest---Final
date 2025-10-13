from django.urls import path
from . import views

app_name = 'cine'

urlpatterns = [
    # --- URLs de Películas ---
    # Read: Lista de todas las películas
    path('peliculas/', views.PeliculaListView.as_view(), name='pelicula_list'),

    # Create: Formulario para crear una nueva película
    path('peliculas/nueva/', views.PeliculaCreateView.as_view(), name='pelicula_create'),

    # Update: Formulario para editar una película existente
    path('peliculas/<int:pk>/editar/', views.PeliculaUpdateView.as_view(), name='pelicula_update'),

    # Delete: Página de confirmación para eliminar una película
    path('peliculas/<int:pk>/eliminar/', views.PeliculaDeleteView.as_view(), name='pelicula_delete'),

    # --- URLs de Salas ---
    # Read: Lista de todas las salas
    path('salas/', views.SalaListView.as_view(), name='sala_list'),

    # Create: Formulario para crear una nueva sala
    path('salas/nueva/', views.SalaCreateView.as_view(), name='sala_create'),

    # Update: Formulario para editar una sala existente
    path('salas/<int:pk>/editar/', views.SalaUpdateView.as_view(), name='sala_update'),

    # Delete: Página de confirmación para eliminar una sala
    path('salas/<int:pk>/eliminar/', views.SalaDeleteView.as_view(), name='sala_delete'),

    # Redirect por defecto a películas
    path('', views.PeliculaListView.as_view(), name='index'),
]