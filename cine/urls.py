from django.urls import path
from . import views

app_name = 'cine'

urlpatterns = [
    # Read: Lista de todas las películas
    # Ejemplo: /peliculas/
    path('', views.PeliculaListView.as_view(), name='pelicula_list'),

    # Create: Formulario para crear una nueva película
    # Ejemplo: /peliculas/nueva/
    path('nueva/', views.PeliculaCreateView.as_view(), name='pelicula_create'),

    # Update: Formulario para editar una película existente
    # Ejemplo: /peliculas/5/editar/
    path('<int:pk>/editar/', views.PeliculaUpdateView.as_view(), name='pelicula_update'),

    # Delete: Página de confirmación para eliminar una película
    # Ejemplo: /peliculas/5/eliminar/
    path('<int:pk>/eliminar/', views.PeliculaDeleteView.as_view(), name='pelicula_delete'),
]