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

    fecha_creacion = models.DateTimeField(auto_now_add=True)

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