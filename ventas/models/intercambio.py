"""
Modelo Intercambio - Registro de auditoría de intercambios de entradas
"""

from django.db import models
from django.utils import timezone
from ventas.models.venta import Venta
from cine.models import Funcion


class Intercambio(models.Model):
    """
    Registro de auditoría para cada intercambio de entradas realizado.
    
    Permite:
    - Trazabilidad completa de cambios
    - Enforcement de límites (max_cambios_por_compra)
    - Reportes y análisis de patrones
    - Auditoría para soporte al cliente
    """
    
    MOTIVO_CHOICES = [
        ('HORARIO', 'Cambio de horario'),
        ('FECHA', 'Cambio de fecha'),
        ('PELICULA', 'Cambio de película'),
        ('DISPONIBILIDAD', 'Disponibilidad de asientos'),
        ('OTRO', 'Otro motivo'),
    ]
    
    ESTADO_CHOICES = [
        ('COMPLETADO', 'Completado'),
        ('FALLIDO', 'Fallido'),
        ('REVERTIDO', 'Revertido'),
    ]
    
    id_intercambio = models.AutoField(primary_key=True)
    
    # Relaciones
    venta = models.ForeignKey(
        Venta,
        on_delete=models.PROTECT,
        related_name='intercambios',
        verbose_name='Venta'
    )
    funcion_origen = models.ForeignKey(
        Funcion,
        on_delete=models.PROTECT,
        related_name='intercambios_origen',
        verbose_name='Función Original'
    )
    funcion_destino = models.ForeignKey(
        Funcion,
        on_delete=models.PROTECT,
        related_name='intercambios_destino',
        verbose_name='Nueva Función'
    )
    
    # Metadatos
    fecha_intercambio = models.DateTimeField(
        default=timezone.now,
        verbose_name='Fecha del Intercambio'
    )
    motivo = models.CharField(
        max_length=20,
        choices=MOTIVO_CHOICES,
        default='OTRO',
        verbose_name='Motivo del Intercambio'
    )
    estado = models.CharField(
        max_length=20,
        choices=ESTADO_CHOICES,
        default='COMPLETADO',
        verbose_name='Estado'
    )
    
    # Información adicional
    cantidad_entradas = models.IntegerField(
        verbose_name='Cantidad de Entradas Intercambiadas',
        help_text='Número de entradas que se intercambiaron'
    )
    penalidad_aplicada = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0.00,
        verbose_name='Penalidad Aplicada',
        help_text='Monto de penalidad cobrado (si aplica)'
    )
    notas = models.TextField(
        blank=True,
        null=True,
        verbose_name='Notas',
        help_text='Información adicional sobre el intercambio'
    )
    
    # Auditoría
    usuario_email = models.EmailField(
        verbose_name='Email del Usuario',
        help_text='Email del cliente que realizó el intercambio'
    )
    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True,
        verbose_name='Dirección IP'
    )
    user_agent = models.TextField(
        blank=True,
        null=True,
        verbose_name='User Agent'
    )
    
    class Meta:
        db_table = 'ventas_intercambio'
        verbose_name = 'Intercambio de Entrada'
        verbose_name_plural = 'Intercambios de Entradas'
        ordering = ['-fecha_intercambio']
        indexes = [
            models.Index(fields=['venta', 'fecha_intercambio']),
            models.Index(fields=['estado']),
            models.Index(fields=['funcion_origen']),
            models.Index(fields=['funcion_destino']),
        ]
    
    def __str__(self):
        return f"Intercambio #{self.id_intercambio} - Venta #{self.venta.id_venta} ({self.fecha_intercambio.strftime('%d/%m/%Y %H:%M')})"
    
    @property
    def dias_anticipacion_origen(self):
        """Calcula cuántos días de anticipación tenía respecto a la función original"""
        if self.funcion_origen and self.fecha_intercambio:
            delta = self.funcion_origen.fecha_hora - self.fecha_intercambio
            return delta.days
        return None
    
    @staticmethod
    def contar_intercambios_venta(venta):
        """
        Cuenta cuántos intercambios exitosos ha realizado una venta.
        
        Args:
            venta (Venta): La venta a consultar
            
        Returns:
            int: Número de intercambios completados
        """
        return Intercambio.objects.filter(
            venta=venta,
            estado='COMPLETADO'
        ).count()
    
    @staticmethod
    def puede_intercambiar(venta, politica):
        """
        Verifica si una venta puede realizar más intercambios según la política.
        
        Args:
            venta (Venta): La venta a verificar
            politica (PoliticaReembolso): La política activa
            
        Returns:
            tuple: (bool, str) - (puede_intercambiar, mensaje_error)
        """
        if not politica or not politica.permitir_intercambio:
            return (False, 'Los intercambios están deshabilitados.')
        
        if politica.max_cambios_por_compra > 0:
            count = Intercambio.contar_intercambios_venta(venta)
            if count >= politica.max_cambios_por_compra:
                return (False, f'Has alcanzado el límite máximo de {politica.max_cambios_por_compra} intercambio(s) para esta compra.')
        
        return (True, '')
