import django.db.models as models
from core.mixins import SoftDeleteMixin


class Clasificacion(SoftDeleteMixin, models.Model):
    """
    Modelo para representar las clasificaciones por edad de las películas.
    
    Ejemplos: ATP, +13, +16, +18
    """
    nombre = models.CharField(
        max_length=10,
        unique=True,
        help_text="Código de la clasificación (ej: ATP, +13, +16, +18)"
    )
    descripcion = models.CharField(
        max_length=200,
        help_text="Descripción completa de la clasificación"
    )
    
    # Campo para definir la edad mínima (útil para validaciones futuras)
    edad_minima = models.PositiveIntegerField(
        default=0,
        help_text="Edad mínima recomendada (0 para ATP)"
    )

    class Meta:
        verbose_name = 'Clasificación de Edad'
        verbose_name_plural = 'Clasificaciones de Edad'
        ordering = ['edad_minima', 'nombre']
        db_table = 'cine_clasificacion'
        constraints = [
            models.UniqueConstraint(fields=['nombre'], name='UQ_clasificacion_nombre')
        ]

    def __str__(self):
        return f"{self.nombre} - {self.descripcion}"
    
    def save(self, *args, **kwargs):
        """Normalizar nombre a mayúsculas para consistencia"""
        if self.nombre:
            self.nombre = self.nombre.strip().upper()
        super().save(*args, **kwargs)
