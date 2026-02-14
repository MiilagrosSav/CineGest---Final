
from django.db import models
from django.core.exceptions import ValidationError
from django.utils import timezone
from cine.models.pelicula import Pelicula
from cine.models.sala import Sala
from simple_history.models import HistoricalRecords
from django.core.validators import MinValueValidator
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
        validators=[MinValueValidator(0)],
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

    # Estado de la función
    ESTADO_CHOICES = [
        ('ACTIVA', 'Activa'),
        ('PREVENTA', 'Preventa'),
        ('AGOTADA', 'Agotada'),
        ('INACTIVA', 'Inactiva'),
    ]
    estado = models.CharField(
        max_length=20,
        choices=ESTADO_CHOICES,
        default='ACTIVA',
        help_text='Estado actual de la función'
    )

    def __str__(self):
        formatos = self.get_formatos_destacados()
        return f"{self.pelicula.titulo} [{formatos}] - Sala {self.sala.numero} - {self.fecha_hora.strftime('%d/%m/%Y %H:%M')}"
    
    def clean(self):
        """
        BÚNKER DE INTEGRIDAD - Cine El Artesano
        Centraliza todas las validaciones de negocio e integridad de datos.
        """
        super().clean()
        ahora = timezone.now()

        # 1. VALIDACIÓN DE PRECIO (Cero tolerancia a números negativos)
        if self.precio_base is not None and self.precio_base < 0:
            raise ValidationError({'precio_base': "El precio no puede ser un número negativo."})

        # 2. VALIDACIONES PARA EDICIÓN (Cuando el registro ya existe en la BD)
        if self.pk:
            try:
                original = Funcion.objects.get(pk=self.pk)

                # A. INMUTABILIDAD DE AUDITORÍA: La fecha de creación no se toca
                if self.fecha_creacion != original.fecha_creacion:
                    raise ValidationError({'fecha_creacion': "La fecha de creación es inmutable por seguridad del sistema."})

                # B. BLOQUEO POR VENTAS: Protección de contrato con el cliente
                # Verificamos entradas en estados: RESERVADA, VENDIDA, ENTREGADA, USADA
                tiene_ventas = self.entradas.filter(
                    estado__in=['RESERVADA', 'VENDIDA', 'ENTREGADA', 'USADA']
                ).exists()

                if tiene_ventas:
                    errores = {}
                    if original.pelicula_id != self.pelicula_id:
                        errores['pelicula'] = "No se puede cambiar la película con entradas vendidas."
                    if original.sala_id != self.sala_id:
                        errores['sala'] = "No se puede cambiar la sala con entradas vendidas."
                    if original.fecha_hora != self.fecha_hora:
                        errores['fecha_hora'] = "No se puede cambiar el horario con entradas vendidas."
                    if original.precio_base != self.precio_base:
                        errores['precio_base'] = "El precio base es inmutable si ya hay ventas."
                    
                    if errores:
                        raise ValidationError(errores)
            except Funcion.DoesNotExist:
                pass

        # 3. VALIDACIÓN TEMPORAL (No permitir funciones en el pasado)
        if self.fecha_hora:
            # Si es nueva o si cambiaron la fecha en una edición
            if not self.pk or (self.pk and original.fecha_hora != self.fecha_hora):
                if self.fecha_hora < ahora:
                    raise ValidationError({'fecha_hora': 'La fecha y hora de la función no puede ser en el pasado.'})

        # 4. SANEAMIENTO DE ESTADOS (Evita inyección de valores no permitidos o basura)
        if self.estado_promocion not in dict(self.ESTADO_PROMOCION_CHOICES):
            raise ValidationError({'estado_promocion': f"El valor '{self.estado_promocion}' no es un estado de promoción válido."})
        
        if self.estado not in dict(self.ESTADO_CHOICES):
            raise ValidationError({'estado': f"El valor '{self.estado}' no es un estado de función válido."})

        # 5. INTEGRIDAD FÍSICA Y SOLAPAMIENTO
        # Validar que la sala esté operativa
        if self.sala and not self.sala.activa:
            raise ValidationError({'sala': 'No se pueden programar funciones en salas que figuran como inactivas.'})

        # 6. VALIDACIÓN DE HORARIOS DE ATENCIÓN (Respeta horarios del cine y excepciones)
        if self.pelicula and self.fecha_hora:
            from datetime import timedelta
            from cine.models import ConfiguracionCine
            
            config = ConfiguracionCine.load()
            
            # Calcular hora de inicio y fin de la función (incluye limpieza)
            duracion_total = self.pelicula.duracion + config.minutos_limpieza
            fecha_hora_fin = self.fecha_hora + timedelta(minutes=duracion_total)
            
            # Validar que el rango completo esté dentro de un horario de atención
            es_valido, mensaje_error = config.validar_rango_horario(
                self.fecha_hora, 
                fecha_hora_fin
            )
            
            if not es_valido:
                raise ValidationError({'fecha_hora': mensaje_error})

        # 7. VALIDACIÓN DE SOLAPAMIENTO EN SALA (Evita conflictos físicos)
        if self.sala and self.pelicula and self.fecha_hora:
            from datetime import timedelta
            duracion_total = timedelta(minutes=self.pelicula.duracion + 30)
            fin_funcion = self.fecha_hora + duracion_total

            funciones_solapadas = Funcion.objects.filter(
                sala=self.sala,
                fecha_hora__lt=fin_funcion,
            ).exclude(pk=self.pk if self.pk else None)

            for f in funciones_solapadas:
                duracion_otra = timedelta(minutes=f.pelicula.duracion + 30)
                fin_otra = f.fecha_hora + duracion_otra
                if f.fecha_hora < fin_funcion and self.fecha_hora < fin_otra:
                    raise ValidationError({
                        'fecha_hora': f'Conflicto de horario: La sala ya está ocupada por "{f.pelicula.titulo}" ({f.fecha_hora.strftime("%H:%M")}).'
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

    def get_valoraciones_stats(self):
        """Retorna estadísticas de valoraciones de esta función"""
        from valoraciones.models import Valoracion
        valoraciones = Valoracion.objects.filter(funcion=self)
        
        total = valoraciones.count()
        if total > 0:
            promedio = sum(v.puntuacion for v in valoraciones) / total
            estrellas_llenas = int(promedio)  # Truncar, no redondear
            estrellas_vacias = 5 - estrellas_llenas
        else:
            promedio = 0
            estrellas_llenas = 0
            estrellas_vacias = 5
        
        return {
            'promedio': round(promedio, 1),
            'total': total,
            'estrellas_llenas': estrellas_llenas,
            'estrellas_vacias': estrellas_vacias,
        }

    # historial de cambios
    history = HistoricalRecords()

    class Meta:
        verbose_name = "Función"
        verbose_name_plural = "Funciones"
        ordering = ['fecha_hora', 'sala__numero']
        db_table = "funciones"  # 🎭 Nombre personalizado de la tabla
        
        # Índices para mejorar el rendimiento de las consultas
        indexes = [
            models.Index(fields=['fecha_hora', 'sala'], name='IDX_funcion_fecha_sala'),
            models.Index(fields=['pelicula', 'fecha_hora'], name='IDX_funcion_pelicula_fecha'),
        ]