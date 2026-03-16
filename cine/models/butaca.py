from django.db import models
from .sala import Sala


# ----------------------------------------------------------------------------------------------
# ------------------------------ creamos la clase BUTACA -------------------------------------
# -----------------------------------------------------------------------------
class Butaca(models.Model):
    """
    Modelo para representar una butaca individual en una sala de cine.
    Cada butaca tiene una ubicación única (fila y número) dentro de una sala específica.
    """

    # Opciones para el tipo de butaca
    TIPO_CHOICES = [
        ('GENERAL', 'General'),
        ('DISCAPACITADO', 'Discapacitado'),
        ('4D', '4D'),
        ('PASILLO', 'Pasillo'),  # Nueva opción para pasillos
    ]

    sala = models.ForeignKey(
        Sala,
        on_delete=models.CASCADE,
        related_name='butacas',
        help_text="La sala a la que pertenece esta butaca"
    )

    fila = models.CharField(
        max_length=5,
        help_text="Fila de la butaca (ej: A, B, C, AA, BB)"
    )

    numero = models.PositiveIntegerField(
        help_text="Número de asiento en la fila"
    )

    tipo = models.CharField(
        max_length=20,
        choices=TIPO_CHOICES,
        default='GENERAL',
        help_text="Tipo de butaca"
    )
    
    es_pasillo = models.BooleanField(
        default=False,
        help_text="Marca si esta posición es un pasillo (no seleccionable)"
    )

    en_mantenimiento = models.BooleanField(
        default=False,
        verbose_name="En mantenimiento",
        help_text="Indica que la butaca está fuera de servicio temporalmente y no puede ser vendida ni seleccionada."
    )

    fecha_creacion = models.DateTimeField(auto_now_add=True)

    def clean(self):
        from django.core.exceptions import ValidationError
        from django.utils import timezone

        # Si se está marcando como en_mantenimiento en un registro existente
        if self.pk and self.en_mantenimiento:
            try:
                original = Butaca.objects.get(pk=self.pk)
                if not original.en_mantenimiento:
                    # Cambio de disponible → mantenimiento: verificar ventas futuras de ESTA butaca
                    from ventas.models import Entrada
                    tiene_venta_futura = Entrada.objects.filter(
                        id_butaca=self,
                        estado__in=['PENDIENTE', 'RESERVADA', 'VENDIDA'],
                        id_funcion__fecha_hora__gt=timezone.now()
                    ).exists()
                    if tiene_venta_futura:
                        raise ValidationError(
                            'No se puede poner en mantenimiento: esta butaca tiene entradas '
                            'vendidas o reservadas para funciones próximas.'
                        )
            except Butaca.DoesNotExist:
                pass

    def save(self, *args, **kwargs):
        """Normalizar fila a MAYÚSCULAS para consistencia (A=a)"""
        if self.fila:
            self.fila = self.fila.strip().upper()
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"Butaca {self.fila}{self.numero} - Sala {self.sala.numero}"

    class Meta:
        verbose_name = "Butaca"
        verbose_name_plural = "Butacas"
        ordering = ['sala', 'fila', 'numero']
        constraints = [
            models.UniqueConstraint(fields=['sala', 'fila', 'numero'], name='UQ_butaca_sala_fila_numero')
        ]
        indexes = [models.Index(fields=['sala', 'fila', 'numero'], name='IDX_butaca_sala_fila_numero')]