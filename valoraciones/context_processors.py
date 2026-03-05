from django.utils import timezone
from django.db.models import Q
from datetime import timedelta
from valoraciones.models import NotificacionValoracion, Valoracion
from valoraciones.services import puede_valorar
from ventas.models.entrada import Entrada
import logging

logger = logging.getLogger(__name__)


def notificaciones_valoracion_context(request):
    """
    Context processor que:
    1. Verifica funciones RECIENTEMENTE terminadas sin valorar y crea notificaciones
    2. Pasa el contador de notificaciones no leídas al template
    
    OPTIMIZACIÓN: Solo verifica funciones terminadas en las últimas 48 horas
    para evitar procesar funciones muy antiguas en cada request.
    """
    context = {'notificaciones_count': 0}
    
    if not request.user.is_authenticated:
        return context
    
    # Solo para clientes
    try:
        cliente = request.user.cliente
    except:
        return context
    
    # Solo si el cliente acepta notificaciones
    if not cliente.acepta_marketing:
        return context
    
    try:
        ahora = timezone.now()
        # Ventana de tiempo: funciones que iniciaron en las últimas 7 días
        # (tiempo razonable para que una función haya terminado)
        hace_7_dias = ahora - timedelta(days=7)
        
        # Obtener entradas del cliente para funciones recientes
        entradas = Entrada.objects.filter(
            id_venta__id_cliente=cliente,
            estado__in=['VENDIDA', 'USADA'],
            # Solo funciones que iniciaron en los últimos 7 días
            id_funcion__fecha_hora__gte=hace_7_dias
        ).select_related('id_funcion', 'id_funcion__pelicula')
        
        for entrada in entradas:
            funcion = entrada.id_funcion
            
            # Usar la misma lógica que valida la valoración
            # para garantizar consistencia total
            if not puede_valorar(cliente, funcion):
                continue
            
            # Verificar que no exista notificación
            if NotificacionValoracion.objects.filter(cliente=cliente, funcion=funcion).exists():
                continue
            
            # Crear notificación SOLO si puede_valorar() = True
            try:
                mensaje = f"¡Cuéntanos qué te pareció {funcion.pelicula.titulo}!"
                url_destino = f"/valoraciones/modal/?funcion_id={funcion.id}"
                
                NotificacionValoracion.objects.create(
                    cliente=cliente,
                    funcion=funcion,
                    mensaje=mensaje,
                    url_destino=url_destino
                )
                logger.info(f"Notificación creada (context_processor): {cliente.usuario.username} - {funcion.pelicula.titulo}")
            except Exception as e:
                logger.exception(f"Error al crear notificación: {e}")
        
        # Contar notificaciones no leídas
        count = NotificacionValoracion.objects.filter(
            cliente=cliente,
            leido=False
        ).count()
        
        context['notificaciones_count'] = count
        
        # LIMPIEZA: Eliminar notificaciones huérfanas (de funciones que ya no se pueden valorar)
        # Esto previene que queden notificaciones inválidas en la base de datos
        try:
            notificaciones_existentes = NotificacionValoracion.objects.filter(
                cliente=cliente,
                leido=False
            ).select_related('funcion', 'funcion__pelicula')
            
            for notif in notificaciones_existentes:
                # Si la notificación es para una función que ya no se puede valorar, eliminarla
                if not puede_valorar(cliente, notif.funcion):
                    # Verificar si es porque ya valoró (entonces solo marcar como leída)
                    if Valoracion.objects.filter(cliente=cliente, funcion=notif.funcion).exists():
                        notif.leido = True
                        notif.save()
                    else:
                        # Si es por otra razón, eliminar la notificación
                        notif.delete()
                        logger.info(f"Notificación inválida eliminada: {cliente.usuario.username} - {notif.funcion.pelicula.titulo}")
        except Exception as e:
            logger.exception(f"Error al limpiar notificaciones: {e}")
        
    except Exception as e:
        logger.exception(f"Error en notificaciones_valoracion_context: {e}")
    
    return context
