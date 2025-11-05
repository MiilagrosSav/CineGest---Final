from django.db import models


class Formato(models.Model):
    """Modelo para los formatos de proyección disponibles"""
    nombre = models.CharField(
        max_length=50,
        unique=True,
        help_text="Nombre del formato (ej: 2D, 3D, IMAX, 4DX)"
    )
    descripcion = models.TextField(
        blank=True,
        help_text="Descripción del formato de proyección"
    )
    
    class Meta:
        db_table = 'formato'
        verbose_name = 'Formato de Proyección'
        verbose_name_plural = 'Formatos de Proyección'
        ordering = ['nombre']
    
    def __str__(self):
        return self.nombre
