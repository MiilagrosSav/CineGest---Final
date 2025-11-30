
from django.db import models
from django.core.exceptions import ValidationError
from django.utils import timezone
from cine.models.pelicula import Pelicula
from cine.models.sala import Sala
from simple_history.models import HistoricalRecords
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
    
    # Opciones para el idioma/audio
    IDIOMA_CHOICES = [
        ('DOBLADA', 'Doblada'),
        ('SUBTITULADA', 'Subtitulada'),
        ('NATIVA', 'Idioma Original'),
    ]
    
    pelicula = models.ForeignKey(
        Pelicula,
        on_delete=models.PROTECT,  # Proteger película si tiene funciones
        related_name='funciones',
        help_text="La película que se proyectará en esta función"
    )
    
    sala = models.ForeignKey(
        Sala,
        on_delete=models.PROTECT,  # Proteger sala si tiene funciones
        related_name='funciones',
        help_text="La sala donde se proyectará la función"
    )
    
    fecha_hora = models.DateTimeField(
        help_text="Fecha y hora de inicio de la función"
    )
    
    precio_base = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        help_text="Precio base de la entrada para esta función (puede variar del precio de la sala)"
    )
    
    idioma = models.CharField(
        max_length=20,
        choices=IDIOMA_CHOICES,
        default='DOBLADA',
        help_text="Idioma/audio de la función"
    )
    
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)
    
    # Yield Management: Control de promociones automáticas
    ESTADO_PROMOCION_CHOICES = [
        ('NORMAL', 'Normal'),
        ('OFERTA_ACTIVA', 'Oferta Activa'),
    ]
    estado_promocion = models.CharField(
        max_length=20,
        choices=ESTADO_PROMOCION_CHOICES,
        default='NORMAL',
        help_text='Estado de promoción automática para esta función'
    )
    promocion_aplicada = models.ForeignKey(
        'promociones.Promocion',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='funciones_con_oferta',
        help_text='Promoción automática actualmente vigente para esta función'
    )

    def __str__(self):
        formatos = self.get_formatos_destacados()
        return f"{self.pelicula.titulo} [{formatos}] - Sala {self.sala.numero} - {self.fecha_hora.strftime('%d/%m/%Y %H:%M')}"
    
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
    
    def get_valoraciones_stats(self):
        """
        Devuelve estadísticas de valoraciones específicas para ESTA función.
        Returns: dict con 'promedio', 'total', 'estrellas_llenas', 'estrellas_vacias'
        """
        from django.db.models import Avg, Count
        try:
            from valoraciones.models import Valoracion
            
            stats = Valoracion.objects.filter(funcion=self).aggregate(
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
        except Exception:
            return {
                'promedio': 0,
                'total': 0,
                'estrellas_llenas': 0,
                'estrellas_vacias': 5,
            }
    
    def get_asientos_disponibles(self):
        """Retorna el número de asientos disponibles para esta función"""
        # Por ahora retorna la capacidad total de la sala
        # En el futuro, aquí se restaría el número de entradas vendidas
        return self.sala.capacidad
    
    def get_formatos_display(self):
        """Retorna los formatos de la función como string"""
        formatos = self.formatos_funcion.select_related('formato').all()
        return ', '.join([ff.formato.nombre for ff in formatos])
    
    def get_formatos_dimension(self):
        """Retorna solo los formatos de dimensión (2D/3D) sin audio ni pantalla"""
        formatos = self.formatos_funcion.select_related('formato').all()
        formatos_dimension = []
        
        for ff in formatos:
            nombre = ff.formato.nombre.upper()
            # Solo incluir formatos que sean 2D, 3D, o combinaciones de dimensión
            if '2D' in nombre or '3D' in nombre:
                formatos_dimension.append(ff.formato.nombre)
        
        return ' + '.join(formatos_dimension) if formatos_dimension else ''
    
    def get_formatos_destacados(self):
        """Retorna solo formatos VISUAL (2D/3D) y EXPERIENCIA (4DX, 4D, D-BOX)"""
        formatos = self.formatos_funcion.select_related('formato').all()
        formatos_destacados = []
        
        for ff in formatos:
            # Solo incluir categorías VISUAL y EXPERIENCIA
            if ff.formato.categoria in ['VISUAL', 'EXPERIENCIA']:
                formatos_destacados.append(ff.formato.nombre)
        
        return ' + '.join(formatos_destacados) if formatos_destacados else '—'

    # historial de cambios
    history = HistoricalRecords()

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