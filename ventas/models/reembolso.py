"""
Modelo Reembolso - Representa reembolsos de ventas
"""

from django.db import models
from django.utils import timezone


class Reembolso(models.Model):
    """Representa un reembolso asociado a una venta"""
    
    id_reembolso = models.AutoField(primary_key=True)
    id_venta = models.ForeignKey(
        'Venta',
        on_delete=models.CASCADE,
        related_name='reembolsos',
        verbose_name='Venta'
    )
    id_pelicula = models.ForeignKey(
        'cine.Pelicula',
        on_delete=models.PROTECT,
        related_name='reembolsos',
        verbose_name='Película',
        help_text='Película relacionada con el reembolso'
    )
    monto_reembolso = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name='Monto del Reembolso'
    )
    fecha_reembolso = models.DateTimeField(
        default=timezone.now,
        verbose_name='Fecha de Reembolso'
    )
    motivo = models.TextField(
        blank=True,
        verbose_name='Motivo',
        help_text='Razón del reembolso'
    )
    
    class Meta:
        db_table = 'Reembolso'
        verbose_name = 'Reembolso'
        verbose_name_plural = 'Reembolsos'
        ordering = ['-fecha_reembolso']
    
    def __str__(self):
        return f"Reembolso #{self.id_reembolso} - Venta #{self.id_venta.id_venta} - ${self.monto_reembolso}"
