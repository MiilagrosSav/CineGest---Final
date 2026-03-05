"""
Utilidades para el sistema híbrido de almacenamiento de imágenes.
Permite usar Cloudinary como principal y almacenamiento local como respaldo.
"""
import io
import logging
import requests
from PIL import Image
from django.core.files.uploadedfile import InMemoryUploadedFile
from django.conf import settings
import cloudinary
import cloudinary.uploader

logger = logging.getLogger(__name__)

# Configuración de optimización de imágenes
IMAGE_OPTIMIZATION_CONFIG = {
    'max_width': 1280,
    'max_height': 720,
    'quality': 80,
    'format': 'JPEG'
}


def verificar_conexion_cloudinary():
    """
    Verifica si hay conexión con Cloudinary.
    
    Returns:
        bool: True si hay conexión, False en caso contrario
    """
    try:
        # Intentar obtener información de la configuración de Cloudinary
        cloudinary.api.ping()
        return True
    except Exception as e:
        logger.warning(f"No se pudo conectar con Cloudinary: {e}")
        return False


def optimizar_imagen(imagen, max_width=None, max_height=None, quality=None):
    """
    Optimiza una imagen reduciendo su tamaño y calidad según la configuración.
    
    Args:
        imagen: Archivo de imagen (InMemoryUploadedFile o similar)
        max_width: Ancho máximo (por defecto usa IMAGE_OPTIMIZATION_CONFIG)
        max_height: Alto máximo (por defecto usa IMAGE_OPTIMIZATION_CONFIG)
        quality: Calidad JPEG 0-100 (por defecto usa IMAGE_OPTIMIZATION_CONFIG)
    
    Returns:
        InMemoryUploadedFile: Imagen optimizada lista para guardar
    """
    if max_width is None:
        max_width = IMAGE_OPTIMIZATION_CONFIG['max_width']
    if max_height is None:
        max_height = IMAGE_OPTIMIZATION_CONFIG['max_height']
    if quality is None:
        quality = IMAGE_OPTIMIZATION_CONFIG['quality']
    
    try:
        # Abrir la imagen con Pillow
        img = Image.open(imagen)
        
        # Convertir a RGB si es necesario (para JPEG)
        if img.mode in ('RGBA', 'LA', 'P'):
            # Crear un fondo blanco
            background = Image.new('RGB', img.size, (255, 255, 255))
            if img.mode == 'P':
                img = img.convert('RGBA')
            background.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
            img = background
        elif img.mode != 'RGB':
            img = img.convert('RGB')
        
        # Calcular el nuevo tamaño manteniendo la proporción
        img.thumbnail((max_width, max_height), Image.Resampling.LANCZOS)
        
        # Guardar en un buffer de memoria
        output = io.BytesIO()
        img.save(output, format='JPEG', quality=quality, optimize=True)
        output.seek(0)
        
        # Crear un nuevo InMemoryUploadedFile
        nombre_original = getattr(imagen, 'name', 'imagen.jpg')
        nombre_base = nombre_original.rsplit('.', 1)[0]
        nombre_optimizado = f"{nombre_base}_optimizada.jpg"
        
        imagen_optimizada = InMemoryUploadedFile(
            output,
            'ImageField',
            nombre_optimizado,
            'image/jpeg',
            output.getbuffer().nbytes,
            None
        )
        
        return imagen_optimizada
        
    except Exception as e:
        logger.error(f"Error al optimizar imagen: {e}")
        # En caso de error, devolver la imagen original
        return imagen


def subir_a_cloudinary(imagen, folder='cinegest'):
    """
    Sube una imagen a Cloudinary.
    
    Args:
        imagen: Archivo de imagen
        folder: Carpeta en Cloudinary donde guardar la imagen
    
    Returns:
        dict: Respuesta de Cloudinary con la URL y otros datos, o None si falla
    """
    if not verificar_conexion_cloudinary():
        logger.warning("No se puede subir a Cloudinary: sin conexión")
        return None
    
    try:
        # Subir a Cloudinary
        resultado = cloudinary.uploader.upload(
            imagen,
            folder=folder,
            resource_type='image',
            overwrite=True,
            invalidate=True
        )
        
        logger.info(f"Imagen subida exitosamente a Cloudinary: {resultado.get('secure_url')}")
        return resultado
        
    except Exception as e:
        logger.error(f"Error al subir imagen a Cloudinary: {e}")
        return None


def obtener_url_cloudinary(public_id):
    """
    Obtiene la URL segura de una imagen en Cloudinary.
    
    Args:
        public_id: ID público de la imagen en Cloudinary
    
    Returns:
        str: URL de la imagen o None si no se puede obtener
    """
    if not public_id:
        return None
    
    try:
        from cloudinary import CloudinaryImage
        url = CloudinaryImage(public_id).build_url(secure=True)
        return url
    except Exception as e:
        logger.error(f"Error al obtener URL de Cloudinary: {e}")
        return None


def procesar_imagen_hibrida(imagen, folder='cinegest', campo_local=None, instancia_modelo=None):
    """
    Procesa una imagen para el sistema híbrido:
    1. Optimiza la imagen
    2. Intenta subir a Cloudinary
    3. Guarda copia local optimizada
    
    Args:
        imagen: Archivo de imagen a procesar
        folder: Carpeta en Cloudinary
        campo_local: Campo del modelo donde guardar la imagen local
        instancia_modelo: Instancia del modelo (para guardar imagen local)
    
    Returns:
        dict: {
            'cloudinary_url': URL de Cloudinary o None,
            'cloudinary_public_id': Public ID de Cloudinary o None,
            'imagen_local': Imagen optimizada para guardar localmente,
            'success': True si al menos una operación tuvo éxito
        }
    """
    resultado = {
        'cloudinary_url': None,
        'cloudinary_public_id': None,
        'imagen_local': None,
        'success': False
    }
    
    try:
        # 1. Optimizar imagen
        imagen_optimizada = optimizar_imagen(imagen)
        resultado['imagen_local'] = imagen_optimizada
        
        # 2. Intentar subir a Cloudinary
        respuesta_cloudinary = subir_a_cloudinary(imagen, folder=folder)
        
        if respuesta_cloudinary:
            resultado['cloudinary_url'] = respuesta_cloudinary.get('secure_url')
            resultado['cloudinary_public_id'] = respuesta_cloudinary.get('public_id')
            resultado['success'] = True
            logger.info("Imagen procesada con Cloudinary y local")
        else:
            logger.warning("Imagen procesada solo localmente (Cloudinary no disponible)")
            resultado['success'] = True  # Éxito con solo local
        
        return resultado
        
    except Exception as e:
        logger.error(f"Error al procesar imagen híbrida: {e}")
        return resultado
