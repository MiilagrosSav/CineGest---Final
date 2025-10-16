from django.db import models
#----------------------------------------------------------------------------------------------
#--------------------------------creamos la clase PELICULA---------------------------------------------------------------------------------------------------
#-----------------------------------------------------------------------------
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
#----------------------------------------------------------------------------------------------
#--------------------------------creamos la clase SALA---------------------------------------------------------------------------------------------------
#-----------------------------------------------------------------------------
class Sala(models.Model):
    """
    Modelo para representar una sala de cine.
    Cada sala tiene una capacidad específica y puede proyectar películas.
    """
    # Opciones para el tipo de sala
    TIPO_CHOICES = [
        ('NORMAL', 'Sala Normal'),
        ('VIP', 'Sala VIP'),
        ('IMAX', 'Sala IMAX'),
        ('4DX', 'Sala 4DX'),
        ('DOLBY_ATMOS', 'Dolby Atmos'),
    ]

    numero = models.PositiveIntegerField(
        unique=True,
        help_text="Número único de la sala (ej: 1, 2, 3...)"
    )
    
    nombre = models.CharField(
        max_length=100,
        help_text="Nombre descriptivo de la sala (ej: 'Sala Premium A')"
    )
    
    capacidad = models.PositiveIntegerField(
        help_text="Número total de asientos en la sala"
    )
    
    tipo = models.CharField(
        max_length=20,
        choices=TIPO_CHOICES,
        default='NORMAL',
        help_text="Tipo de sala y experiencia que ofrece"
    )
    
    activa = models.BooleanField(
        default=True,
        help_text="Indica si la sala está disponible para proyecciones"
    )
    
    precio_base = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        help_text="Precio base de entrada para esta sala"
    )
    
    observaciones = models.TextField(
        blank=True,
        null=True,
        help_text="Notas adicionales sobre la sala (equipamiento, mantenimiento, etc.)"
    )
    
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Sala {self.numero} - {self.nombre}"
    
    def get_tipo_display_icon(self):
        """Retorna un icono para el tipo de sala"""
        icons = {
            'NORMAL': '🎬',
            'VIP': '👑',
            'IMAX': '📽️',
            '4DX': '🎢',
            'DOLBY_ATMOS': '🔊'
        }
        return icons.get(self.tipo, '🎬')
    
    def get_status_display(self):
        """Retorna el estado de la sala con icono"""
        return "🟢 Activa" if self.activa else "🔴 Inactiva"

    class Meta:
        verbose_name = "Sala"
        verbose_name_plural = "Salas"
        ordering = ['numero']