from django.db import models


class Formato(models.Model):
    """Modelo para los formatos de proyección disponibles"""
    
    CATEGORIA_CHOICES = [
        ('VISUAL', 'Visual (2D/3D)'),
        ('EXPERIENCIA', 'Experiencia (4DX, D-BOX, 4D)'),
        ('PANTALLA', 'Pantalla (IMAX, ScreenX, Standard)'),
        ('AUDIO', 'Audio (Dolby Atmos, DTS, etc)'),
        ('OTRO', 'Otro'),
    ]
    
    nombre = models.CharField(
        max_length=50,
        help_text="Nombre del formato (ej: 2D, 3D, IMAX, 4DX)"
    )
    descripcion = models.TextField(
        blank=True,
        help_text="Descripción del formato de proyección"
    )
    categoria = models.CharField(
        max_length=20,
        choices=CATEGORIA_CHOICES,
        default='VISUAL',
        help_text="Categoría del formato para facilitar filtrado"
    )
    
    class Meta:
        db_table = 'formato'
        verbose_name = 'Formato de Proyección'
        verbose_name_plural = 'Formatos de Proyección'
        ordering = ['nombre']
        constraints = [
            models.UniqueConstraint(fields=['nombre'], name='UQ_formato_nombre')
        ]
    
    def __str__(self):
        return self.nombre
