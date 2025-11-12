"""
Modelo Entrada - Representa cada entrada/butaca vendida
"""

from django.db import models


class Entrada(models.Model):
    """Representa una entrada individual (una butaca para una función)"""
    
    ESTADO_CHOICES = [
        ('RESERVADA', 'Reservada'),
        ('VENDIDA', 'Vendida'),
        ('USADA', 'Usada'),
        ('CANCELADA', 'Cancelada'),
    ]
    
    id_entrada = models.AutoField(primary_key=True)
    id_venta = models.ForeignKey(
        'Venta',
        on_delete=models.CASCADE,
        related_name='entradas',
        verbose_name='Venta'
    )
    id_funcion = models.ForeignKey(
        'cine.Funcion',
        on_delete=models.PROTECT,
        related_name='entradas',
        verbose_name='Función'
    )
    id_sala = models.ForeignKey(
        'cine.Sala',
        on_delete=models.PROTECT,
        related_name='entradas',
        verbose_name='Sala'
    )
    id_butaca = models.ForeignKey(
        'cine.Butaca',
        on_delete=models.PROTECT,
        related_name='entradas',
        verbose_name='Butaca'
    )
    id_pelicula = models.ForeignKey(
        'cine.Pelicula',
        on_delete=models.PROTECT,
        related_name='entradas',
        verbose_name='Película'
    )
    estado = models.CharField(
        max_length=20,
        choices=ESTADO_CHOICES,
        default='RESERVADA',
        verbose_name='Estado'
    )
    
    class Meta:
        db_table = 'Entrada'
        verbose_name = 'Entrada'
        verbose_name_plural = 'Entradas'
        ordering = ['id_funcion', 'id_butaca']
        # Evitar que se venda la misma butaca dos veces para la misma función
        unique_together = [['id_funcion', 'id_butaca']]
    
    def __str__(self):
        return f"Entrada #{self.id_entrada} - {self.id_pelicula.titulo} - Butaca {self.id_butaca.fila}{self.id_butaca.numero}"
