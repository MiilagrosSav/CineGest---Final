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

    # --- URLs del Diseñador de Butacas ---
    path('salas/<int:sala_id>/disenar/', views.disenar_layout_sala, name='disenar_layout_sala'),
    path('salas/<int:sala_id>/api/guardar_layout/', views.api_guardar_layout_sala, name='api_guardar_layout_sala'),

    # --- URLs de Funciones ---
    # Read: Lista de todas las funciones
    path('funciones/', views.FuncionListView.as_view(), name='funcion_list'),

    # Create: Formulario para crear una nueva función
    path('funciones/nueva/', views.FuncionCreateView.as_view(), name='funcion_create'),

    # Update: Formulario para editar una función existente
    path('funciones/<int:pk>/editar/', views.FuncionUpdateView.as_view(), name='funcion_update'),

    # Delete: Página de confirmación para eliminar una función
    path('funciones/<int:pk>/eliminar/', views.FuncionDeleteView.as_view(), name='funcion_delete'),

    # --- Cartelera Pública ---
    path('cartelera/', views.cartelera_view, name='cartelera'),

    # Redirect por defecto a películas
    path('', views.PeliculaListView.as_view(), name='index'),
]