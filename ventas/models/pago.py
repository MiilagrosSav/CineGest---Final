"""
Modelo Pago - Representa el pago de una venta
"""

from django.db import models
from django.core.validators import MinValueValidator
from django.utils import timezone
from simple_history.models import HistoricalRecords
from django.core.exceptions import ValidationError


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
        validators=[MinValueValidator(0)],
        verbose_name='Monto',
        help_text='Monto del pago - debe ser mayor o igual a cero'
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
        # ✅ DBA: Restricciones a nivel de base de datos para blindar integridad
        constraints = [
            models.CheckConstraint(
                check=models.Q(monto__gte=0),
                name='chk_pago_monto_no_negativo',
                violation_error_message='El monto del pago no puede ser negativo'
            ),
        ]
    def clean(self):
        super().clean()
        
        # 1. Bloqueo de estados inválidos (Evita el -1 en la interfaz)
        if self.estado not in dict(self.ESTADO_CHOICES):
            raise ValidationError({'estado': f"El valor '{self.estado}' no es válido."})

        # 2. Inmutabilidad de pagos finalizados
        if self.pk:
            original = Pago.objects.get(pk=self.pk)
            if original.estado in ['COMPLETADO', 'REEMBOLSADO']:
                if any(getattr(original, f) != getattr(self, f) for f in ['monto', 'id_venta', 'id_metodo_pago']):
                    raise ValidationError("Un pago finalizado no puede ser editado.")

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)
    def __str__(self):
        return f"Pago #{self.id_pago} - Venta #{self.id_venta.id_venta} - ${self.monto}"
    
    # historial de cambios
    history = HistoricalRecords()
