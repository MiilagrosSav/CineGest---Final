from django.db import models
from django.core.exceptions import ValidationError
from datetime import date



class Pelicula(models.Model):
    """
    Modelo para representar una película en el cine.
    """
    # Opciones para el campo 'genero'
    GENERO_CHOICES = [
        ('ACCION', 'Acción'),
        ('AVENTURA', 'Aventura'),
        ('COMEDIA', 'Comedia'),
        ('DRAMA', 'Drama'),
        ('CIENCIA_FICCION', 'Ciencia Ficción'),
        ('TERROR', 'Terror'),
        ('FANTASIA', 'Fantasía'),
        ('MUSICAL', 'Musical'),
        ('ANIMACION', 'Animación'),
    ]
    
    # Opciones para clasificación
    CLASIFICACION_CHOICES = [
        ('ATP', 'Apta para todo público'),
        ('+13', 'Mayores de 13 años'),
        ('+16', 'Mayores de 16 años'),
        ('+18', 'Mayores de 18 años'),
    ]

    titulo = models.CharField(max_length=200, help_text="El título de la película.")
    sinopsis = models.TextField(help_text="Una breve descripción de la trama.")
    director = models.CharField(max_length=100, help_text="El director de la película.")
    genero = models.CharField(max_length=50, choices=GENERO_CHOICES, help_text="El género principal.")
    duracion = models.PositiveIntegerField(help_text="La duración en minutos.")
    fecha_estreno = models.DateField(help_text="La fecha de estreno en cines.")
    
    # Clasificación por edad
    clasificacion = models.CharField(
        max_length=10,
        choices=CLASIFICACION_CHOICES,
        default='ATP',
        help_text="Clasificación por edad de la película."
    )
    
    # Campo para la imagen de portada
    imagen_portada = models.ImageField(
        upload_to='portadas_peliculas/', 
        blank=True, 
        null=True, 
        help_text="La imagen de portada o póster de la película."
    )

    def __str__(self):
        return self.titulo

    def clean(self):
        """
        Validaciones personalizadas del modelo
        """
        super().clean()
        
        # Validar que la fecha de estreno no sea en el pasado
        if self.fecha_estreno and self.fecha_estreno < date.today():
            raise ValidationError({
                'fecha_estreno': 'La fecha de estreno no puede ser anterior a la fecha actual.'
            })
        
        # Validar que la duración sea razonable (entre 30 minutos y 5 horas)
        if self.duracion and (self.duracion < 30 or self.duracion > 300):
            raise ValidationError({
                'duracion': 'La duración debe estar entre 30 y 300 minutos.'
            })

    def save(self, *args, **kwargs):
        """
        Ejecutar validaciones antes de guardar
        """
        self.clean()
        super().save(*args, **kwargs)

    class Meta:
        verbose_name = "Película"
        verbose_name_plural = "Películas"
        ordering = ['-fecha_estreno', 'titulo']
        db_table = "peliculas"  # 🎬 Nombre personalizado de la tabla