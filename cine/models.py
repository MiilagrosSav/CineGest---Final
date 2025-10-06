from django.db import models

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

    titulo = models.CharField(max_length=200, help_text="El título de la película.")
    sinopsis = models.TextField(help_text="Una breve descripción de la trama.")
    director = models.CharField(max_length=100, help_text="El director de la película.")
    genero = models.CharField(max_length=50, choices=GENERO_CHOICES, help_text="El género principal.")
    duracion = models.PositiveIntegerField(help_text="La duración en minutos.")
    fecha_estreno = models.DateField(help_text="La fecha de estreno en cines.")
    
    # Campo para la imagen de portada
    imagen_portada = models.ImageField(
        upload_to='portadas_peliculas/', 
        blank=True, 
        null=True, 
        help_text="La imagen de portada o póster de la película."
    )

    def __str__(self):
        return self.titulo

    class Meta:
        verbose_name = "Película"
        verbose_name_plural = "Películas"
        ordering = ['-fecha_estreno', 'titulo']