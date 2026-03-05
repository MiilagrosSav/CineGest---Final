"""
Managers personalizados para el módulo de ventas
"""

from django.db import models
from django.utils import timezone
from datetime import timedelta


class VentaManager(models.Manager):
    """Manager personalizado para el modelo Venta"""
    
    def limpiar_expiradas(self, tiempo_expiracion_minutos=None):
        """
        Limpia las ventas pendientes que han superado el tiempo de expiración.
        
        Args:
            tiempo_expiracion_minutos (int): Tiempo en minutos antes de que expire una venta pendiente.
                                             Si es None, usa el valor de ConfiguracionCine.reserva_tiempo_espera.
        
        Returns:
            tuple: (cantidad_ventas_expiradas, cantidad_butacas_liberadas)
        
        Comportamiento:
            - Busca todas las ventas con estado='PENDIENTE' cuya fecha_compra sea menor 
              a timezone.now() - timedelta(minutes=tiempo_expiracion_minutos)
            - Cambia el estado de la venta a 'EXPIRADA'
            - Marca la venta como inactiva (activo=False)
            - Libera las butacas asociadas cambiando el estado de las entradas a 'EXPIRADA'
            - NO borra los registros, solo aplica baja lógica
        """
        from ventas.models import Entrada  # Import local para evitar importación circular
        from cine.models import ConfiguracionCine
        
        # Obtener tiempo de expiración de la configuración si no se especifica
        if tiempo_expiracion_minutos is None:
            try:
                config = ConfiguracionCine.objects.first()
                tiempo_expiracion_minutos = config.reserva_tiempo_espera if config else 10
            except Exception:
                tiempo_expiracion_minutos = 10  # Fallback
        
        # Calcular el timestamp de corte (hace X minutos)
        tiempo_corte = timezone.now() - timedelta(minutes=tiempo_expiracion_minutos)
        
        # Buscar ventas pendientes que hayan expirado
        ventas_expiradas = self.filter(
            estado='PENDIENTE',
            fecha_compra__lt=tiempo_corte,
            activo=True  # Solo procesar las que aún están activas
        )
        
        cantidad_ventas = 0
        cantidad_butacas = 0
        
        # Procesar cada venta expirada
        for venta in ventas_expiradas:
            # Actualizar el estado de la venta
            venta.estado = 'EXPIRADA'
            venta.activo = False
            venta.save(update_fields=['estado', 'activo'])
            cantidad_ventas += 1
            
            # Liberar las butacas asociadas (cambiar estado de entradas a EXPIRADA)
            entradas_actualizadas = Entrada.objects.filter(
                id_venta=venta,
                estado__in=['PENDIENTE', 'RESERVADA']  # Solo las que no están confirmadas
            ).update(estado='EXPIRADA')
            
            cantidad_butacas += entradas_actualizadas
        
        return (cantidad_ventas, cantidad_butacas)
    
    def ventas_activas(self):
        """
        Retorna solo las ventas activas (no expiradas ni canceladas lógicamente).
        
        Returns:
            QuerySet: Ventas con activo=True
        """
        return self.filter(activo=True)
    
    def ventas_pendientes_activas(self):
        """
        Retorna ventas pendientes que aún están activas y no han expirado.
        
        Returns:
            QuerySet: Ventas con estado='PENDIENTE' y activo=True
        """
        return self.filter(estado='PENDIENTE', activo=True)
