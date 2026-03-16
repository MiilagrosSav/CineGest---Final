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

    # --- URLs de Gestión de Mantenimiento de Butacas ---
    path('salas/<int:sala_id>/mantenimiento/', views.gestionar_mantenimiento_sala, name='gestionar_mantenimiento_sala'),
    path('salas/<int:sala_id>/api/mantenimiento/batch/', views.api_batch_mantenimiento_sala, name='api_batch_mantenimiento_sala'),
    path('salas/<int:sala_id>/api/mantenimiento/<int:butaca_id>/', views.api_toggle_mantenimiento_butaca, name='api_toggle_mantenimiento_butaca'),

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
    path('funciones/precheck-dias/', views.precheck_dias_semana_disponibles, name='precheck_dias_funcion'),
    
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
    
    # --- Gestión de Clasificaciones de Edad ---
    path('configuracion/clasificaciones/', views.gestionar_clasificaciones_view, name='gestionar_clasificaciones'),
    path('configuracion/clasificaciones/crear/', views.crear_clasificacion_view, name='crear_clasificacion'),
    path('configuracion/clasificaciones/<int:pk>/editar/', views.editar_clasificacion_view, name='editar_clasificacion'),
    path('configuracion/clasificaciones/<int:pk>/eliminar/', views.eliminar_clasificacion_view, name='eliminar_clasificacion'),
    path('configuracion/clasificaciones/<int:pk>/activar/', views.activar_clasificacion_view, name='activar_clasificacion'),

    # --- Gestión de Directores ---
    path('configuracion/directores/', views.DirectorListView.as_view(), name='gestionar_directores'),
    path('configuracion/directores/crear/', views.DirectorCreateView.as_view(), name='crear_director'),
    path('configuracion/directores/<int:pk>/editar/', views.DirectorUpdateView.as_view(), name='editar_director'),
    path('configuracion/directores/<int:pk>/eliminar/', views.DirectorDeleteView.as_view(), name='eliminar_director'),

    # AJAX: Crear director desde modal del formulario de película
    path('api/directores/crear/', views.DirectorCrearAjaxView.as_view(), name='director_crear_ajax'),

    # --- API TMDB (The Movie Database) ---
    # AJAX: Buscar películas en TMDB
    path('api/tmdb/search/', views.tmdb_search_movies, name='tmdb_search'),
    # AJAX: Obtener detalles de película desde TMDB
    path('api/tmdb/movie/<int:movie_id>/', views.tmdb_get_movie_details, name='tmdb_movie_details'),
    # AJAX: Importar película completa desde TMDB
    path('api/tmdb/import/<int:movie_id>/', views.TMDBImportMovieView.as_view(), name='tmdb_import_movie'),
    # AJAX: Descargar póster desde TMDB
    path('api/tmdb/download-poster/<int:movie_id>/', views.tmdb_download_poster, name='tmdb_download_poster'),

    # Redirect por defecto a películas
    path('', views.PeliculaListView.as_view(), name='index'),
]
