"""
Modelo Venta - Representa una compra/venta completa
"""

from django.db import models
from django.utils import timezone
from accounts.models import Cliente, Empleado


class Venta(models.Model):
    """Representa una venta/compra de entradas"""
    
    ESTADO_CHOICES = [
        ('PENDIENTE', 'Pendiente'),
        ('PENDIENTE_PAGO', 'Pendiente de Pago'),
        ('CONFIRMADA', 'Confirmada'),
        ('CANCELADA', 'Cancelada'),
    ]
    
    TIPO_VENTA_CHOICES = [
        ('ONLINE', 'Online'),
        ('PRESENCIAL', 'Presencial'),
    ]
    
    id_venta = models.AutoField(primary_key=True)
    id_cliente = models.ForeignKey(
        Cliente, 
        on_delete=models.PROTECT,
        related_name='ventas',
        verbose_name='Cliente'
    )
    id_empleado = models.ForeignKey(
        Empleado,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='ventas_procesadas',
        verbose_name='Empleado',
        help_text='Empleado que procesó la venta (solo para ventas presenciales)'
    )
    fecha_compra = models.DateTimeField(
        default=timezone.now,
        verbose_name='Fecha de Compra'
    )
    tipo_venta = models.CharField(
        max_length=20,
        choices=TIPO_VENTA_CHOICES,
        default='ONLINE',
        verbose_name='Tipo de Venta'
    )
    estado = models.CharField(
        max_length=20,
        choices=ESTADO_CHOICES,
        default='PENDIENTE',
        verbose_name='Estado'
    )
    
    class Meta:
        db_table = 'Venta'
        verbose_name = 'Venta'
        verbose_name_plural = 'Ventas'
        ordering = ['-fecha_compra']
    
    def __str__(self):
        return f"Venta #{self.id_venta} - {self.id_cliente.usuario.get_full_name() or self.id_cliente.usuario.username}"
    
    def calcular_total(self):
        """Calcular el total de la venta sumando el precio de todas las entradas"""
        total = sum(entrada.id_funcion.precio_base for entrada in self.entradas.all())
        return total
    
    def cantidad_entradas(self):
        """Retorna la cantidad de entradas de esta venta"""
        return self.entradas.count()
