from django.db.models.signals import post_save
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
