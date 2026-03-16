"""
Vistas AJAX para integración con TMDB (The Movie Database).
Proporciona endpoints para búsqueda y obtención de datos de películas.
"""
import logging
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
from cine.services.tmdb_service import tmdb_service
from cine.mixins import AdminRequiredMixin
from django.views import View
from django.utils.decorators import method_decorator
from cine.models import Clasificacion, Director

logger = logging.getLogger(__name__)


# Mapeo de clasificaciones: nombre -> (edad_minima, descripción)
CLASIFICACIONES_DEFAULT = {
    'ATP': (0, 'Apta para todo público'),
    '+13': (13, 'Mayores de 13 años'),
    'SAM 13': (13, 'Solo apta para mayores de 13 años'),
    '+16': (16, 'Mayores de 16 años'),
    'SAM 16': (16, 'Solo apta para mayores de 16 años'),
    '+18': (18, 'Mayores de 18 años'),
    'SAM 18': (18, 'Solo apta para mayores de 18 años'),
    'C': (18, 'Condicionada - Solo mayores de 18 años'),
}


@login_required
@require_http_methods(["GET"])
def tmdb_search_movies(request):
    """
    Busca películas en TMDB por título.
    
    Endpoint: GET /cine/api/tmdb/search/
    Parámetros:
        - q: Término de búsqueda (título de la película)
        - page: Número de página (opcional, por defecto 1)
    
    Retorna:
        JSON con lista de películas encontradas
    """
    query = request.GET.get('q', '').strip()
    page = request.GET.get('page', 1)
    
    if not query:
        return JsonResponse({
            'success': False,
            'error': 'Debes proporcionar un término de búsqueda'
        }, status=400)
    
    try:
        page = int(page)
    except ValueError:
        page = 1
    
    # Realizar búsqueda en TMDB
    results = tmdb_service.search_movies(query, page)
    
    return JsonResponse({
        'success': True,
        'query': query,
        'total_results': len(results),
        'results': results
    })


@login_required
@require_http_methods(["GET"])
def tmdb_get_movie_details(request, movie_id):
    """
    Obtiene los detalles completos de una película desde TMDB.
    
    Endpoint: GET /cine/api/tmdb/movie/<movie_id>/
    
    Retorna:
        JSON con detalles completos de la película (título, sinopsis, duración, director, etc.)
    """
    try:
        movie_id = int(movie_id)
    except (ValueError, TypeError):
        return JsonResponse({
            'success': False,
            'error': 'ID de película inválido'
        }, status=400)
    
    # Obtener datos completos (detalles + créditos)
    movie_data = tmdb_service.get_complete_movie_data(movie_id)
    
    if not movie_data:
        return JsonResponse({
            'success': False,
            'error': 'No se pudo obtener información de la película'
        }, status=404)
    
    # Construir URL del póster si existe
    if movie_data.get('poster_path'):
        movie_data['poster_url'] = tmdb_service.get_poster_url(movie_data['poster_path'])
    else:
        movie_data['poster_url'] = None
    
    return JsonResponse({
        'success': True,
        'movie': movie_data
    })


@method_decorator(login_required, name='dispatch')
class TMDBImportMovieView(View):
    """
    Vista para importar una película completa desde TMDB.
    Descarga el póster y lo guarda en el sistema local/Cloudinary.
    """
    
    def post(self, request, movie_id):
        """
        Importa datos de película desde TMDB y retorna datos formateados.
        
        POST /cine/api/tmdb/import/<movie_id>/
        
        Retorna:
            JSON con datos de película listos para el formulario Django
        """
        try:
            movie_id = int(movie_id)
        except (ValueError, TypeError):
            return JsonResponse({
                'success': False,
                'error': 'ID de película inválido'
            }, status=400)
        
        # Obtener datos completos
        movie_data = tmdb_service.get_complete_movie_data(movie_id)
        
        if not movie_data:
            return JsonResponse({
                'success': False,
                'error': 'No se pudo obtener información de la película'
            }, status=404)
        
        # Preparar datos formateados para Django
        clasificacion_nombre = movie_data.get('clasificacion', 'ATP')
        
        # Obtener o crear la clasificación automáticamente
        if clasificacion_nombre in CLASIFICACIONES_DEFAULT:
            edad_minima, descripcion = CLASIFICACIONES_DEFAULT[clasificacion_nombre]
        else:
            # Si la clasificación no está en el mapeo, intentar extraer la edad
            # del nombre (ej: "+16" -> 16) o usar valores genéricos
            try:
                edad_extraida = int(''.join(filter(str.isdigit, clasificacion_nombre)))
                edad_minima = edad_extraida
                descripcion = f'Solo apta para mayores de {edad_extraida} años'
            except (ValueError, TypeError):
                edad_minima = 0
                descripcion = f'Clasificación {clasificacion_nombre}'
        
        # Crear o recuperar la clasificación (si ya existe, la recupera; si no, la crea)
        clasificacion, created = Clasificacion.objects.get_or_create(
            nombre=clasificacion_nombre.strip().upper(),
            defaults={
                'edad_minima': edad_minima,
                'descripcion': descripcion,
                'activo': True
            }
        )
        
        if created:
            logger.info(f" Clasificación '{clasificacion_nombre}' creada automáticamente (ID: {clasificacion.pk}, edad: {edad_minima})")
        else:
            logger.info(f"Clasificación '{clasificacion_nombre}' encontrada en BD (ID: {clasificacion.pk})")
        
        clasificacion_id = clasificacion.pk
        clasificacion_nombre = clasificacion.nombre
        
        # Resolver/crear director con datos de TMDB (get_or_create anti-duplicado)
        director_nombre_completo = (movie_data.get('director') or 'Desconocido').strip()
        director_tmdb_id = movie_data.get('director_tmdb_id')
        director_biografia = (movie_data.get('director_biografia') or '').strip()
        director_fecha_nacimiento_str = (movie_data.get('director_fecha_nacimiento') or '').strip()

        if ',' in director_nombre_completo:
            apellido_raw, nombre_raw = [x.strip() for x in director_nombre_completo.split(',', 1)]
            director_nombre = nombre_raw or director_nombre_completo
            director_apellido = apellido_raw
        else:
            partes_nombre = director_nombre_completo.split()
            if len(partes_nombre) >= 2:
                director_nombre = ' '.join(partes_nombre[:-1])
                director_apellido = partes_nombre[-1]
            else:
                director_nombre = director_nombre_completo
                director_apellido = ''

        # Normalizar a title-case para coincidir con lo que Director.save() produce
        director_nombre = ' '.join(director_nombre.strip().split()).title()
        director_apellido = ' '.join(director_apellido.strip().split()).title()

        director_fecha_nacimiento = None
        if director_fecha_nacimiento_str:
            try:
                from datetime import datetime
                director_fecha_nacimiento = datetime.strptime(director_fecha_nacimiento_str, '%Y-%m-%d').date()
            except ValueError:
                director_fecha_nacimiento = None

        director_defaults = {
            'nombre': director_nombre or director_nombre_completo,
            'apellido': director_apellido,
            'fecha_nacimiento': director_fecha_nacimiento,
            'biografia': director_biografia,
        }

        director_created = False
        if director_tmdb_id:
            # 1. ¿Ya existe un director con este tmdb_id?
            director_obj = Director.objects.filter(tmdb_id=director_tmdb_id).first()
            if not director_obj:
                # 2. ¿Existe un director con el mismo nombre creado manualmente (sin tmdb_id)?
                #    Si existe, lo reutilizamos y le asignamos el tmdb_id — evita el duplicado.
                director_obj = Director.objects.filter(
                    nombre__iexact=director_nombre,
                    apellido__iexact=director_apellido,
                    tmdb_id__isnull=True,
                ).first()
                if director_obj:
                    director_obj.tmdb_id = director_tmdb_id
                    director_obj.save(update_fields=['tmdb_id'])
                    logger.info(f'Director manual vinculado a TMDB: {director_obj} (tmdb_id={director_tmdb_id})')
                else:
                    # 3. No existe: crear nuevo
                    director_obj = Director.objects.create(tmdb_id=director_tmdb_id, **director_defaults)
                    director_created = True
        else:
            # Sin tmdb_id: buscar/crear por nombre normalizado (filter+create evita el bug de iexact en get_or_create)
            director_obj = Director.objects.filter(
                nombre__iexact=director_nombre,
                apellido__iexact=director_apellido,
            ).first()
            if not director_obj:
                director_obj = Director.objects.create(
                    nombre=director_nombre,
                    apellido=director_apellido,
                    fecha_nacimiento=director_fecha_nacimiento,
                    biografia=director_biografia,
                )
                director_created = True

        # Enriquecer campos vacíos del director existente con datos de TMDB
        director_cambios = []
        if director_tmdb_id and not director_obj.tmdb_id:
            director_obj.tmdb_id = director_tmdb_id
            director_cambios.append('tmdb_id')
        if director_fecha_nacimiento and not director_obj.fecha_nacimiento:
            director_obj.fecha_nacimiento = director_fecha_nacimiento
            director_cambios.append('fecha_nacimiento')
        if director_biografia and not director_obj.biografia:
            director_obj.biografia = director_biografia
            director_cambios.append('biografia')
        if director_cambios:
            director_obj.save(update_fields=director_cambios)

        if director_created:
            logger.info(
                f'Director creado desde TMDB: {director_obj} '
                f'(tmdb_id={director_obj.tmdb_id or "sin id"})'
            )

        formatted_data = {
            'id': movie_id,
            'titulo': movie_data.get('title', ''),
            'sinopsis': movie_data.get('sinopsis', ''),
            'director': str(director_obj),
            'director_id': director_obj.pk,
            'director_tmdb_id': director_obj.tmdb_id,
            'director_fecha_nacimiento': (
                director_obj.fecha_nacimiento.isoformat() if director_obj.fecha_nacimiento else ''
            ),
            'director_biografia': director_obj.biografia or '',
            'duracion': movie_data.get('duracion', 0),
            'fecha_estreno': movie_data.get('fecha_estreno', ''),
            'generos': movie_data.get('genres', []),
            'poster_path': movie_data.get('poster_path'),
            'youtube_trailer_key': movie_data.get('youtube_trailer_key'),
            'clasificacion': clasificacion_nombre,
            'clasificacion_id': clasificacion_id,  # ID para autocompletar el select
        }
        
        # Construir URL del póster
        if formatted_data['poster_path']:
            formatted_data['poster_url'] = tmdb_service.get_poster_url(formatted_data['poster_path'])
        else:
            formatted_data['poster_url'] = None
        
        # Construir URL del trailer de YouTube si existe
        if formatted_data['youtube_trailer_key']:
            formatted_data['youtube_trailer_url'] = f"https://www.youtube.com/watch?v={formatted_data['youtube_trailer_key']}"
            formatted_data['youtube_embed_url'] = f"https://www.youtube.com/embed/{formatted_data['youtube_trailer_key']}"
        else:
            formatted_data['youtube_trailer_url'] = None
            formatted_data['youtube_embed_url'] = None
        
        logger.info(f"Película importada desde TMDB: {formatted_data['titulo']} (ID: {movie_id})")
        
        return JsonResponse({
            'success': True,
            'movie': formatted_data
        })


@login_required
@require_http_methods(["POST"])
def tmdb_download_poster(request, movie_id):
    """
    Descarga el póster de una película desde TMDB.
    Este endpoint retorna el póster procesado pero no lo guarda automáticamente.
    
    POST /cine/api/tmdb/download-poster/<movie_id>/
    
    Retorna:
        JSON con información sobre la descarga del póster
    """
    try:
        movie_id = int(movie_id)
    except (ValueError, TypeError):
        return JsonResponse({
            'success': False,
            'error': 'ID de película inválido'
        }, status=400)
    
    # Obtener datos básicos para obtener el poster_path
    movie_data = tmdb_service.get_movie_details(movie_id)
    
    if not movie_data or not movie_data.get('poster_path'):
        return JsonResponse({
            'success': False,
            'error': 'Esta película no tiene póster disponible'
        }, status=404)
    
    poster_path = movie_data['poster_path']
    poster_url = tmdb_service.get_poster_url(poster_path)
    
    return JsonResponse({
        'success': True,
        'poster_url': poster_url,
        'poster_path': poster_path,
        'message': 'El póster se descargará automáticamente al guardar la película'
    })
