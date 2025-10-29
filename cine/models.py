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



#----------------------------------------------------------------------------------------------
#--------------------------------creamos la clase FUNCION---------------------------------------------------------------------------------------------------
#-----------------------------------------------------------------------------
class Funcion(models.Model):
    """
    Modelo para representar una función (proyección) de una película en una sala.
    Una función es la combinación de una película, una sala y un horario específico.
    """
    
    # Opciones para el formato de proyección
    FORMATO_CHOICES = [
        ('2D', '2D'),
        ('3D', '3D'),
        ('4D', '4D'),
        ('IMAX', 'IMAX'),
        ('2D_3D', '2D + 3D'),  # Función mixta con asientos 2D y 3D
        ('2D_4D', '2D + 4D'),  # Función mixta con asientos 2D y 4D
        ('3D_4D', '3D + 4D'),  # Función mixta con asientos 3D y 4D
    ]
    
    pelicula = models.ForeignKey(
        Pelicula,
        on_delete=models.CASCADE,
        related_name='funciones',
        help_text="La película que se proyectará en esta función"
    )
    
    sala = models.ForeignKey(
        Sala,
        on_delete=models.CASCADE,
        related_name='funciones',
        help_text="La sala donde se proyectará la función"
    )
    
    fecha_hora = models.DateTimeField(
        help_text="Fecha y hora de inicio de la función"
    )
    
    formato_proyeccion = models.CharField(
        max_length=10,
        choices=FORMATO_CHOICES,
        default='2D',
        help_text="Formato en el que se proyectará la película"
    )
    
    precio_base = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        help_text="Precio base de la entrada para esta función (puede variar del precio de la sala)"
    )
    
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.pelicula.titulo} [{self.formato_proyeccion}] - Sala {self.sala.numero} - {self.fecha_hora.strftime('%d/%m/%Y %H:%M')}"
    
    def clean(self):
        """
        Validaciones personalizadas del modelo Funcion
        """
        super().clean()
        
        # Validar que la fecha_hora no sea en el pasado
        if self.fecha_hora and self.fecha_hora < timezone.now():
            raise ValidationError({
                'fecha_hora': 'La fecha y hora de la función no puede ser en el pasado.'
            })
        
        # Validar que no haya solapamiento de funciones en la misma sala
        if self.sala and self.pelicula and self.fecha_hora:
            # Calcular el tiempo de finalización de esta función (duración + 30 min de limpieza)
            from datetime import timedelta
            duracion_total = timedelta(minutes=self.pelicula.duracion + 30)
            fin_funcion = self.fecha_hora + duracion_total
            
            # Buscar funciones que se solapen en la misma sala
            funciones_solapadas = Funcion.objects.filter(
                sala=self.sala,
                fecha_hora__lt=fin_funcion,
            ).exclude(pk=self.pk if self.pk else None)
            
            for funcion in funciones_solapadas:
                duracion_otra = timedelta(minutes=funcion.pelicula.duracion + 30)
                fin_otra = funcion.fecha_hora + duracion_otra
                
                # Si hay solapamiento
                if funcion.fecha_hora < fin_funcion and self.fecha_hora < fin_otra:
                    raise ValidationError({
                        'fecha_hora': f'Esta función se solapa con otra función en la misma sala: '
                                    f'{funcion.pelicula.titulo} a las {funcion.fecha_hora.strftime("%H:%M")}. '
                                    f'Debe haber al menos 30 minutos entre funciones.'
                    })
        
        # Validar que la sala esté activa
        if self.sala and not self.sala.activa:
            raise ValidationError({
                'sala': 'No se pueden programar funciones en salas inactivas.'
            })

    def save(self, *args, **kwargs):
        """
        Ejecutar validaciones antes de guardar
        """
        self.clean()
        super().save(*args, **kwargs)
    
    def get_hora_fin(self):
        """Retorna la hora de finalización estimada de la función"""
        from datetime import timedelta
        if self.pelicula and self.fecha_hora:
            return self.fecha_hora + timedelta(minutes=self.pelicula.duracion)
        return None
    
    def get_asientos_disponibles(self):
        """Retorna el número de asientos disponibles para esta función"""
        # Por ahora retorna la capacidad total de la sala
        # En el futuro, aquí se restaría el número de entradas vendidas
        return self.sala.capacidad

    class Meta:
        verbose_name = "Función"
        verbose_name_plural = "Funciones"
        ordering = ['fecha_hora', 'sala__numero']
        db_table = "funciones"  # 🎭 Nombre personalizado de la tabla
        
        # Índices para mejorar el rendimiento de las consultas
        indexes = [
            models.Index(fields=['fecha_hora', 'sala']),
            models.Index(fields=['pelicula', 'fecha_hora']),
        ]


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
        ('VIP', 'VIP'),
        ('DISCAPACITADO', 'Discapacitado'),
        ('4D', '4D'),
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

    fecha_creacion = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Butaca {self.fila}{self.numero} - Sala {self.sala.numero}"

    class Meta:
        verbose_name = "Butaca"
        verbose_name_plural = "Butacas"
        ordering = ['sala', 'fila', 'numero']
        unique_together = ("sala", "fila", "numero")
        indexes = [models.Index(fields=['sala', 'fila', 'numero'])]