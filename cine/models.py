from django.db import models
from django.core.exceptions import ValidationError
from django.utils import timezone
from datetime import date
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
        db_table = "salas"  # 🏛️ Nombre personalizado de la tabla
        ordering = ['numero']