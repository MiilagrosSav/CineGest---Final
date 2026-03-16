"""
Servicio para interactuar con The Movie Database (TMDB) API.
Proporciona funciones para buscar películas y obtener detalles completos.
"""
import requests
import logging
from typing import Dict, List, Optional
from django.conf import settings
from PIL import Image
from io import BytesIO
from django.core.files.uploadedfile import InMemoryUploadedFile
import sys

logger = logging.getLogger(__name__)


class TMDBService:
    """Servicio para consultar la API de TMDB"""
    
    def __init__(self):
        self.api_key = settings.TMDB_API_KEY
        self.base_url = settings.TMDB_BASE_URL
        self.image_base_url = settings.TMDB_IMAGE_BASE_URL
        self.poster_size = settings.TMDB_POSTER_SIZE
        
        if not self.api_key:
            logger.warning("TMDB_API_KEY no está configurada en settings.py o .env")
    
    def _make_request(self, endpoint: str, params: dict = None) -> Optional[dict]:
        """
        Realiza una petición a la API de TMDB.
        
        Args:
            endpoint: Endpoint de la API (ej: '/search/movie')
            params: Parámetros adicionales para la consulta
            
        Returns:
            Diccionario con la respuesta JSON o None si hay error
        """
        if not self.api_key:
            logger.error("No se puede realizar la petición sin TMDB_API_KEY")
            return None
        
        url = f"{self.base_url}{endpoint}"
        default_params = {
            'api_key': self.api_key,
            'language': 'es-ES'  # Respuestas en español
        }
        
        if params:
            default_params.update(params)
        
        try:
            response = requests.get(url, params=default_params, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            logger.error(f"Error al consultar TMDB API: {e}")
            return None
    
    def search_movies(self, query: str, page: int = 1) -> List[Dict]:
        """
        Busca películas por título en TMDB.
        
        Args:
            query: Título de la película a buscar
            page: Número de página (por defecto 1)
            
        Returns:
            Lista de diccionarios con información básica de las películas encontradas
        """
        if not query or not query.strip():
            return []
        
        data = self._make_request('/search/movie', {'query': query, 'page': page})
        
        if not data or 'results' not in data:
            return []
        
        # Formatear resultados para devolver solo lo necesario
        results = []
        for movie in data['results'][:10]:  # Limitar a 10 resultados
            results.append({
                'id': movie.get('id'),
                'title': movie.get('title', ''),
                'original_title': movie.get('original_title', ''),
                'release_date': movie.get('release_date', ''),
                'overview': movie.get('overview', '')[:200] + '...' if movie.get('overview') else '',
                'poster_path': movie.get('poster_path'),
                'vote_average': movie.get('vote_average', 0),
                'popularity': movie.get('popularity', 0)
            })
        
        return results
    
    def get_movie_details(self, movie_id: int) -> Optional[Dict]:
        """
        Obtiene los detalles completos de una película.
        
        Args:
            movie_id: ID de la película en TMDB
            
        Returns:
            Diccionario con todos los detalles de la película o None si hay error
        """
        # Incluir videos en la respuesta usando append_to_response
        data = self._make_request(f'/movie/{movie_id}', {'append_to_response': 'videos'})
        
        if not data:
            return None
        
        return {
            'id': data.get('id'),
            'title': data.get('title', ''),
            'original_title': data.get('original_title', ''),
            'sinopsis': data.get('overview', ''),
            'duracion': data.get('runtime', 0),
            'fecha_estreno': data.get('release_date', ''),
            'poster_path': data.get('poster_path'),
            'backdrop_path': data.get('backdrop_path'),
            'genres': [g.get('name') for g in data.get('genres', [])],
            'vote_average': data.get('vote_average', 0),
            'popularity': data.get('popularity', 0),
            'budget': data.get('budget', 0),
            'revenue': data.get('revenue', 0),
            'status': data.get('status', ''),
            'tagline': data.get('tagline', ''),
            'videos': data.get('videos', {})  # Incluir videos en la respuesta
        }
    
    def get_movie_credits(self, movie_id: int) -> Optional[Dict]:
        """
        Obtiene los créditos (director, actores) de una película.
        
        Args:
            movie_id: ID de la película en TMDB
            
        Returns:
            Diccionario con información de director y reparto o None si hay error
        """
        data = self._make_request(f'/movie/{movie_id}/credits')
        
        if not data:
            return None
        
        # Buscar el director en el 'crew'
        director = None
        director_id = None
        crew = data.get('crew', [])
        for person in crew:
            if person.get('job') == 'Director':
                director = person.get('name')
                director_id = person.get('id')
                break
        
        # Obtener actores principales (primeros 5)
        cast = []
        for actor in data.get('cast', [])[:5]:
            cast.append({
                'name': actor.get('name'),
                'character': actor.get('character'),
                'profile_path': actor.get('profile_path')
            })
        
        return {
            'director': director,
            'director_id': director_id,
            'cast': cast
        }

    def get_person_details(self, person_id: int) -> Optional[Dict]:
        """
        Obtiene detalles ampliados de una persona (director) desde TMDB.

        Args:
            person_id: ID de la persona en TMDB

        Returns:
            Diccionario con biografia y fecha de nacimiento o None si falla
        """
        data = self._make_request(f'/person/{person_id}')
        if not data:
            return None

        return {
            'id': data.get('id'),
            'name': data.get('name', ''),
            'biography': data.get('biography', '') or '',
            'birthday': data.get('birthday') or '',
        }
    
    def get_official_trailer(self, movie_id: int) -> Optional[str]:
        """
        Obtiene el ID (key) del trailer oficial de YouTube de una película.
        
        Busca entre los videos de TMDB aquel que cumpla:
        - type='Trailer'
        - site='YouTube'
        - official=True (preferido)
        
        Args:
            movie_id: ID de la película en TMDB
            
        Returns:
            String con la key de YouTube (ej: 'dQw4w9WgXcQ') o None si no se encuentra
        """
        data = self._make_request(f'/movie/{movie_id}/videos')
        
        if not data or 'results' not in data:
            return None
        
        videos = data.get('results', [])
        
        # Prioridad 1: Trailer oficial de YouTube en español
        for video in videos:
            if (video.get('type') == 'Trailer' and 
                video.get('site') == 'YouTube' and 
                video.get('official') is True and
                video.get('iso_639_1') == 'es'):
                return video.get('key')
        
        # Prioridad 2: Trailer oficial de YouTube en cualquier idioma
        for video in videos:
            if (video.get('type') == 'Trailer' and 
                video.get('site') == 'YouTube' and 
                video.get('official') is True):
                return video.get('key')
        
        # Prioridad 3: Cualquier trailer de YouTube (no necesariamente oficial)
        for video in videos:
            if (video.get('type') == 'Trailer' and 
                video.get('site') == 'YouTube'):
                return video.get('key')
        
        # No se encontró ningún trailer
        logger.info(f"No se encontró trailer oficial para película {movie_id}")
        return None
    
    def get_movie_certification(self, movie_id: int) -> Optional[str]:
        """
        Obtiene la clasificación de edad de una película desde TMDB.
        Utiliza el endpoint release_dates con prioridad internacional:
        1. Argentina (AR) - prioridad local
        2. Estados Unidos (US) - estándar internacional
        
        Args:
            movie_id: ID de la película en TMDB
            
        Returns:
            String con la clasificación (ATP, +13, +16, +18) o 'ATP' por defecto
        """
        data = self._make_request(f'/movie/{movie_id}/release_dates')
        
        if not data or 'results' not in data:
            logger.info(f"No se pudo obtener release_dates para película {movie_id}, usando ATP por defecto")
            return 'ATP'
        
        # Mapeo de certificaciones internacionales a nuestras clasificaciones
        CERTIFICATION_MAP = {
            # Argentina (AR) - Sistema INCAA
            'ATP': 'ATP',           # Apta para Todo Público
            'Atp': 'ATP',
            '+13': '+13',           # SAM 13 (Solo para mayores de 13 años)
            'SAM 13': '+13',
            'SAM13': '+13',
            '+16': '+16',           # SAM 16 (Solo para mayores de 16 años)
            'SAM 16': '+16',
            'SAM16': '+16',
            '+18': '+18',           # SAM 18 (Solo para mayores de 18 años)
            'SAM 18': '+18',
            'SAM18': '+18',
            # Estados Unidos (US) - Sistema MPAA
            'G': 'ATP',             # General Audiences (Todo público)
            'PG': 'ATP',            # Parental Guidance (Guía parental)
            'PG-13': '+13',         # Parents Strongly Cautioned (Mayores de 13)
            'R': '+16',             # Restricted (Menores de 17 requieren adulto)
            'NC-17': '+18',         # No One 17 and Under Admitted (Mayores de 18)
        }
        
        results = data.get('results', [])
        
        # Prioridad 1: Buscar certificación de Argentina (AR)
        for country in results:
            if country.get('iso_3166_1') == 'AR':
                release_dates = country.get('release_dates', [])
                for release in release_dates:
                    cert = release.get('certification', '').strip()
                    if cert and cert in CERTIFICATION_MAP:
                        clasificacion = CERTIFICATION_MAP[cert]
                        logger.info(f"Clasificación encontrada (AR): {cert} → {clasificacion}")
                        return clasificacion
                # Si tiene AR pero certificación vacía o no mapeada, seguir a US
                logger.debug(f"País AR encontrado pero sin certificación válida, buscando US")
        
        # Prioridad 2: Buscar certificación de Estados Unidos (US)
        for country in results:
            if country.get('iso_3166_1') == 'US':
                release_dates = country.get('release_dates', [])
                for release in release_dates:
                    cert = release.get('certification', '').strip()
                    if cert and cert in CERTIFICATION_MAP:
                        clasificacion = CERTIFICATION_MAP[cert]
                        logger.info(f"Clasificación encontrada (US): {cert} → {clasificacion}")
                        return clasificacion
        
        # No se encontró clasificación válida en AR ni US
        logger.info(f"No se encontró clasificación en AR/US para película {movie_id}, usando ATP por defecto")
        return 'ATP'
    
    def get_complete_movie_data(self, movie_id: int) -> Optional[Dict]:
        """
        Obtiene todos los datos necesarios de una película (detalles + créditos + trailer).
        
        Args:
            movie_id: ID de la película en TMDB
            
        Returns:
            Diccionario completo con toda la información o None si hay error
        """
        details = self.get_movie_details(movie_id)
        if not details:
            return None
        
        credits = self.get_movie_credits(movie_id)
        
        # Extraer el trailer oficial de YouTube de los videos
        youtube_trailer_key = None
        videos_data = details.get('videos', {})
        if videos_data and 'results' in videos_data:
            videos = videos_data.get('results', [])
            
            # Prioridad 1: Trailer oficial de YouTube en español
            for video in videos:
                if (video.get('type') == 'Trailer' and 
                    video.get('site') == 'YouTube' and 
                    video.get('official') is True and
                    video.get('iso_639_1') == 'es'):
                    youtube_trailer_key = video.get('key')
                    break
            
            # Prioridad 2: Trailer oficial de YouTube en cualquier idioma
            if not youtube_trailer_key:
                for video in videos:
                    if (video.get('type') == 'Trailer' and 
                        video.get('site') == 'YouTube' and 
                        video.get('official') is True):
                        youtube_trailer_key = video.get('key')
                        break
            
            # Prioridad 3: Cualquier trailer de YouTube
            if not youtube_trailer_key:
                for video in videos:
                    if (video.get('type') == 'Trailer' and 
                        video.get('site') == 'YouTube'):
                        youtube_trailer_key = video.get('key')
                        break
        
        # Combinar detalles, créditos y trailer
        complete_data = {**details}
        if credits:
            complete_data['director'] = credits.get('director', 'Desconocido')
            complete_data['director_tmdb_id'] = credits.get('director_id')
        else:
            complete_data['director'] = 'Desconocido'
            complete_data['director_tmdb_id'] = None

        # Si tenemos ID de director, pedir detalle extendido (/person/{id})
        complete_data['director_biografia'] = ''
        complete_data['director_fecha_nacimiento'] = ''
        if complete_data.get('director_tmdb_id'):
            person_data = self.get_person_details(complete_data['director_tmdb_id'])
            if person_data:
                complete_data['director_biografia'] = person_data.get('biography', '')
                complete_data['director_fecha_nacimiento'] = person_data.get('birthday', '')
        
        # Agregar el trailer key
        complete_data['youtube_trailer_key'] = youtube_trailer_key
        
        # Agregar la clasificación de edad
        certification = self.get_movie_certification(movie_id)
        complete_data['clasificacion'] = certification if certification else 'ATP'
        
        return complete_data
    
    def download_poster(self, poster_path: str, max_width: int = 800) -> Optional[InMemoryUploadedFile]:
        """
        Descarga y redimensiona el póster de una película desde TMDB.
        
        Args:
            poster_path: Ruta del póster en TMDB (ej: '/path/to/poster.jpg')
            max_width: Ancho máximo de la imagen redimensionada (por defecto 800px)
            
        Returns:
            InMemoryUploadedFile listo para guardar en Django o None si hay error
        """
        if not poster_path:
            logger.warning("No se proporcionó ruta de póster")
            return None
        
        # Construir URL completa de la imagen
        poster_url = f"{self.image_base_url}/{self.poster_size}{poster_path}"
        
        try:
            # Descargar la imagen
            response = requests.get(poster_url, timeout=15)
            response.raise_for_status()
            
            # Abrir la imagen con Pillow
            img = Image.open(BytesIO(response.content))
            
            # Convertir a RGB si es necesario (para PNGs con transparencia)
            if img.mode in ('RGBA', 'LA', 'P'):
                background = Image.new('RGB', img.size, (255, 255, 255))
                if img.mode == 'P':
                    img = img.convert('RGBA')
                background.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
                img = background
            
            # Redimensionar manteniendo el aspect ratio
            if img.width > max_width:
                ratio = max_width / img.width
                new_height = int(img.height * ratio)
                img = img.resize((max_width, new_height), Image.Resampling.LANCZOS)
            
            # Convertir a archivo en memoria
            output = BytesIO()
            img.save(output, format='JPEG', quality=85, optimize=True)
            output.seek(0)
            
            # Crear InMemoryUploadedFile compatible con Django
            filename = poster_path.split('/')[-1].replace('.jpg', '_tmdb.jpg')
            file = InMemoryUploadedFile(
                output,
                'ImageField',
                filename,
                'image/jpeg',
                output.getbuffer().nbytes,
                None
            )
            
            logger.info(f"Póster descargado y redimensionado: {filename}")
            return file
            
        except Exception as e:
            logger.error(f"Error al descargar/procesar póster: {e}")
            return None
    
    def get_poster_url(self, poster_path: str, size: str = None) -> str:
        """
        Construye la URL completa de un póster.
        
        Args:
            poster_path: Ruta del póster en TMDB
            size: Tamaño del póster (por defecto usa el configurado en settings)
            
        Returns:
            URL completa del póster
        """
        if not poster_path:
            return ''
        
        size = size or self.poster_size
        return f"{self.image_base_url}/{size}{poster_path}"


# Instancia global del servicio
tmdb_service = TMDBService()
