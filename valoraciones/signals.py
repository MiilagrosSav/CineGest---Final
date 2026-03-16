from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.utils import timezone
from ventas.models.entrada import Entrada
from valoraciones.models import NotificacionValoracion, Valoracion
import logging

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Entrada)
def crear_notificacion_valoracion(sender, instance, created, **kwargs):
    """
    Signal desactivado: La creación de notificaciones se maneja
    exclusivamente en el context_processor para asegurar que solo
    se generen DESPUÉS de que la función termine.
    
    El context_processor verifica funciones terminadas cada vez que
    un cliente autenticado hace un request, creando notificaciones
    solo para funciones que ya finalizaron.
    """
    # Signal desactivado intencionalmente
    # Las notificaciones se crean en context_processors.py
    pass


# ---------------------------------------------------------------------------
# Signal: actualizar estadísticas de la Película al crear/eliminar valoración
# ---------------------------------------------------------------------------
# ¿Por qué es necesario?
#   La cartelera calcula el promedio de la película con una consulta Avg() en cada
#   request. Esto es correcto, pero si el tráfico crece, conviene cachear el
#   resultado en un campo `promedio_cache` del modelo Pelicula para leer con un
#   simple SELECT en lugar de un GROUP BY.
#
# Para activar el caché:
#   1. Agregar en cine/models/pelicula.py:
#        promedio_cache = models.FloatField(default=0.0, editable=False)
#        total_valoraciones_cache = models.PositiveIntegerField(default=0, editable=False)
#   2. Crear y aplicar la migración correspondiente.
#   3. Descomentar las tres líneas marcadas con "(CACHÉ)" más abajo.

def _recalcular_promedio_pelicula(pelicula):
    """Recalcula y opcionalmente persiste el promedio de una película."""
    from django.db.models import Avg, Count
    stats = Valoracion.objects.filter(pelicula=pelicula).aggregate(
        promedio=Avg('puntuacion'),
        total=Count('id')
    )
    promedio = round(stats['promedio'] or 0.0, 2)
    total = stats['total'] or 0

    logger.info(
        "[signal] Promedio actualizado — película='%s' (id=%s) | promedio=%.2f | total=%s",
        pelicula.titulo, pelicula.pk, promedio, total
    )

    # (CACHÉ) Descomentar si se agrega promedio_cache al modelo Pelicula:
    # pelicula.promedio_cache = promedio
    # pelicula.total_valoraciones_cache = total
    # pelicula.save(update_fields=['promedio_cache', 'total_valoraciones_cache'])


@receiver(post_save, sender=Valoracion)
def valoracion_post_save(sender, instance, created, **kwargs):
    """Recalcula el promedio de la película cada vez que se guarda una valoración."""
    accion = "creada" if created else "modificada"
    logger.debug(
        "[signal] Valoración %s — cliente=%s funcion_id=%s puntuacion=%s",
        accion, instance.cliente_id, instance.funcion_id, instance.puntuacion
    )
    _recalcular_promedio_pelicula(instance.pelicula)


@receiver(post_delete, sender=Valoracion)
def valoracion_post_delete(sender, instance, **kwargs):
    """Recalcula el promedio de la película cada vez que se elimina una valoración."""
    logger.debug(
        "[signal] Valoración eliminada — cliente=%s funcion_id=%s",
        instance.cliente_id, instance.funcion_id
    )
    _recalcular_promedio_pelicula(instance.pelicula)

