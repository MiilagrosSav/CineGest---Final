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
    path('salas/<int:sala_id>/disenar/', views.disenar_layout_sala, name='disenar_distribucion_asientos'),
    path('salas/<int:sala_id>/api/guardar_layout/', views.api_guardar_layout_sala, name='api_guardar_distribucion_asientos'),

    # --- URLs de Funciones ---
    # Read: Lista de todas las funciones
    path('funciones/', views.FuncionListView.as_view(), name='funcion_list'),

    # Create: Formulario para crear una nueva función
    path('funciones/nueva/', views.funcion_create_view, name='funcion_create'),

    # Update: Formulario para editar una función existente
    path('funciones/<int:pk>/editar/', views.FuncionUpdateView.as_view(), name='funcion_update'),

    # Delete: Página de confirmación para eliminar una función
    path('funciones/<int:pk>/eliminar/', views.FuncionDeleteView.as_view(), name='funcion_delete'),

    # AJAX: Calcular horarios disponibles
    path('funciones/calcular-horarios/', views.calcular_horarios_disponibles, name='calcular_horarios'),
    
    # AJAX: Verificar excepciones de horario para una fecha
    path('funciones/verificar-horario-fecha/', views.verificar_horario_fecha, name='verificar_horario_fecha'),

    # --- Cartelera Pública ---
    path('cartelera/', views.cartelera_view, name='cartelera'),
    
    # --- Cartelera de Preventa ---
    path('preventa/', views.preventa_view, name='preventa'),
    
    # --- Compra de Entradas ---
    path('comprar-entrada/<int:funcion_id>/', views.comprar_entrada_view, name='comprar_entrada'),

    # --- Configuración del Cine ---
    path('configuracion/', views.ConfiguracionCineUpdateView.as_view(), name='configuracion'),
    path('configuracion/actualizar/', views.ConfiguracionCineUpdateView.as_view(), name='configuracion_update'),
    
    # --- Gestión de Horarios de Atención ---
    path('configuracion/horarios/', views.gestionar_horarios_view, name='gestionar_horarios'),
    path('configuracion/horarios/dia/<int:dia_semana>/', views.editar_horarios_dia_view, name='editar_horarios_dia'),
    path('configuracion/horarios/copiar/', views.copiar_horarios_dia_view, name='copiar_horarios_dia'),
    path('configuracion/horarios/<int:horario_id>/eliminar/', views.eliminar_horario_view, name='eliminar_horario'),
    
    # --- Gestión de Excepciones de Horarios ---
    # Nota: El listado de excepciones está integrado en gestionar_horarios (vista unificada)
    path('configuracion/excepciones/crear/', views.crear_excepcion_view, name='crear_excepcion'),
    path('configuracion/excepciones/<int:excepcion_id>/editar/', views.editar_excepcion_view, name='editar_excepcion'),
    path('configuracion/excepciones/<int:excepcion_id>/eliminar/', views.eliminar_excepcion_view, name='eliminar_excepcion'),

    # Redirect por defecto a películas
    path('', views.PeliculaListView.as_view(), name='index'),
]