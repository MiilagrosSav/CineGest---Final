from django.db import models
from django.conf import settings


class Valoracion(models.Model):
    """Valoración de una película por un cliente asociada a una función concreta."""
    cliente = models.ForeignKey(
        'accounts.Cliente', on_delete=models.CASCADE, related_name='valoraciones'
    )
    pelicula = models.ForeignKey(
        'cine.Pelicula', on_delete=models.CASCADE, related_name='valoraciones'
    )
    funcion = models.ForeignKey(
        'cine.Funcion', on_delete=models.CASCADE, related_name='valoraciones'
    )

    PUNTUACION_CHOICES = [(i, str(i)) for i in range(1, 6)]
    puntuacion = models.IntegerField(choices=PUNTUACION_CHOICES)

    comentario = models.TextField(blank=True, null=True, max_length=500)

    fecha_creacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'valoraciones'
        verbose_name = 'Valoración'
        verbose_name_plural = 'Valoraciones'
        constraints = [
            models.UniqueConstraint(fields=['cliente', 'funcion'], name='unique_cliente_funcion_valoracion')
        ]

    def __str__(self):
        return f"Valoración {self.puntuacion} - {self.cliente} - {self.funcion}"
from django.db import models

# Create your models here.
