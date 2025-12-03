"""
Modelo Pago - Representa el pago de una venta
"""

from django.db import models
from django.utils import timezone
from simple_history.models import HistoricalRecords


class Pago(models.Model):
    """Representa el pago asociado a una venta"""
    
    ESTADO_CHOICES = [
        ('PENDIENTE', 'Pendiente'),
        ('COMPLETADO', 'Completado'),
        ('RECHAZADO', 'Rechazado'),
        ('REEMBOLSADO', 'Reembolsado'),
    ]
    
    id_pago = models.AutoField(primary_key=True)
    id_venta = models.OneToOneField(
        'Venta',
        on_delete=models.CASCADE,
        related_name='pago',
        verbose_name='Venta'
    )
    monto = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name='Monto'
    )
    fecha_pago = models.DateTimeField(
        default=timezone.now,
        verbose_name='Fecha de Pago'
    )
    estado = models.CharField(
        max_length=20,
        choices=ESTADO_CHOICES,
        default='PENDIENTE',
        verbose_name='Estado'
    )
    nro_transaccion = models.CharField(
        max_length=100,
        blank=True,
        default='',
        verbose_name='Número de Transacción',
        help_text='ID de transacción de Mercado Pago u otro procesador'
    )
    id_metodo_pago = models.ForeignKey(
        'MetodoPago',
        on_delete=models.PROTECT,
        related_name='pagos',
        verbose_name='Método de Pago'
    )
    
    class Meta:
        db_table = 'Pago'
        verbose_name = 'Pago'
        verbose_name_plural = 'Pagos'
        ordering = ['-fecha_pago']
    
    def __str__(self):
        return f"Pago #{self.id_pago} - Venta #{self.id_venta.id_venta} - ${self.monto}"
    
    # historial de cambios
    history = HistoricalRecords()
