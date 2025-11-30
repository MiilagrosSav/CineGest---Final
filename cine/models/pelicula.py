from django.db import models
from django.core.exceptions import ValidationError
from datetime import date
from simple_history.models import HistoricalRecords
from cine.models.genero import Genero




class Pelicula(models.Model):
    """
    Modelo para representar una película en el cine.
    """
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
    # Ahora soportamos múltiples géneros por película
    generos = models.ManyToManyField(Genero, related_name='peliculas', blank=True)
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
    
    # Flags de control para promociones
    es_estreno = models.BooleanField(
        default=False,
        help_text="Indica si es un lanzamiento reciente."
    )
    acepta_promociones = models.BooleanField(
        default=True,
        help_text="Master switch: si es False, bloquea cualquier descuento."
    )

    def __str__(self):
        return self.titulo

    def get_genero_display(self):
        """Compatibilidad con plantillas: devuelve géneros como cadena separada por comas."""
        try:
            return ', '.join([g.nombre for g in self.generos.all()])
        except Exception:
            return ''

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

    def get_valoraciones_stats(self):
        """
        Devuelve estadísticas de valoraciones para esta película.
        Returns: dict con 'promedio', 'total', 'estrellas_llenas', 'estrellas_vacias'
        """
        from django.db.models import Avg, Count
        from valoraciones.models import Valoracion
        
        stats = Valoracion.objects.filter(pelicula=self).aggregate(
            promedio=Avg('puntuacion'),
            total=Count('id')
        )
        
        promedio = stats['promedio'] or 0
        total = stats['total'] or 0
        
        # Calcular estrellas para display (truncar al entero, no redondear)
        # Usar int() en lugar de round() para evitar 6 estrellas totales
        estrellas_llenas = int(promedio) if promedio > 0 else 0
        estrellas_vacias = 5 - estrellas_llenas
        
        return {
            'promedio': round(promedio, 1),
            'total': total,
            'estrellas_llenas': estrellas_llenas,
            'estrellas_vacias': estrellas_vacias,
        }

    @property
    def promedio_calificacion(self):
        """
        Retorna el promedio de las valoraciones (puntuacion) asociadas a esta película.
        Devuelve un float redondeado a una cifra (ej: 4.5) o 0 si no hay valoraciones.
        """
        from django.db.models import Avg
        from valoraciones.models import Valoracion

        stats = Valoracion.objects.filter(pelicula=self).aggregate(promedio=Avg('puntuacion'))
        promedio = stats.get('promedio') or 0
        try:
            return round(float(promedio), 1)
        except Exception:
            return 0.0

    # historial de cambios
    history = HistoricalRecords()

    class Meta:
        verbose_name = "Película"
        verbose_name_plural = "Películas"
        ordering = ['-fecha_estreno', 'titulo']
        db_table = "peliculas"  # 🎬 Nombre personalizado de la tabla
