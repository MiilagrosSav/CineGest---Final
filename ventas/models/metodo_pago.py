"""
Modelo MetodoPago - Representa los métodos de pago disponibles
"""

from django.db import models


class MetodoPago(models.Model):
    """Representa un método de pago (Mercado Pago, Efectivo, Tarjeta, etc.)"""
    
    id_metodo_pago = models.AutoField(primary_key=True)
    nombre = models.CharField(
        max_length=50,
        verbose_name='Nombre'
    )
    descripcion = models.TextField(
        blank=True,
        verbose_name='Descripción'
    )
    
    class Meta:
        db_table = 'Metodo_pago'
        verbose_name = 'Método de Pago'
        verbose_name_plural = 'Métodos de Pago'
        ordering = ['nombre']
        constraints = [
            models.UniqueConstraint(fields=['nombre'], name='UQ_metodo_pago_nombre')
        ]
    
    def __str__(self):
        return self.nombre
