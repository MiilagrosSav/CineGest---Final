"""
Signals para el módulo de ventas
"""

import logging
from django.db.models.signals import post_save
from django.dispatch import receiver
from ventas.models import Pago

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Pago)
def enviar_comprobante_pago_automatico(sender, instance, created, **kwargs):
    """
    Enviar comprobante de pago automáticamente cuando el estado es COMPLETADO
    
    Este signal se dispara después de guardar un Pago. Si el pago está en estado
    COMPLETADO, envía automáticamente el comprobante de pago por email.
    
    Args:
        sender: Clase del modelo (Pago)
        instance: Instancia del pago guardado
        created: Boolean que indica si es una nueva instancia
        **kwargs: Argumentos adicionales
    """
    # Solo enviar email si el estado es COMPLETADO
    if instance.estado == 'COMPLETADO':
        try:
            from core.services.notificaciones import notificacion_service
            
            # Verificar que el pago tenga una venta asociada con cliente
            if not instance.id_venta:
                logger.warning(f"Pago #{instance.id_pago} no tiene venta asociada. No se envía comprobante.")
                return
            
            if not instance.id_venta.id_cliente:
                logger.warning(f"Pago #{instance.id_pago} - Venta sin cliente. No se envía comprobante.")
                return
            
            if not instance.id_venta.id_cliente.usuario:
                logger.warning(f"Pago #{instance.id_pago} - Cliente sin usuario. No se envía comprobante.")
                return
            
            if not instance.id_venta.id_cliente.usuario.email:
                logger.warning(f"Pago #{instance.id_pago} - Usuario sin email. No se envía comprobante.")
                return
            
            # Enviar comprobante de pago
            logger.info(f"Enviando comprobante de pago automático para Pago #{instance.id_pago}")
            exito = notificacion_service.enviar_comprobante_pago(instance, request=None)
            
            if exito:
                logger.info(f"✅ Comprobante de pago enviado exitosamente para Pago #{instance.id_pago}")
            else:
                logger.error(f"❌ Error al enviar comprobante de pago para Pago #{instance.id_pago}")
                
        except Exception as e:
            # No queremos que un error en el envío de email rompa el guardado del pago
            logger.error(f"Error crítico enviando comprobante de pago para Pago #{instance.id_pago}: {e}")
