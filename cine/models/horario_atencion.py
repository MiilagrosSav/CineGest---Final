from django.db import models
from django.core.exceptions import ValidationError
from simple_history.models import HistoricalRecords


class HorarioAtencion(models.Model):
    """
    Horarios de apertura y cierre por día de la semana.
    Permite múltiples rangos por día (ej: Lunes 10-14 y 17-23).
    
    Cada registro representa un rango horario para un día específico.
    Se valida que no haya solapamientos en el mismo día.
    """
    
    DIA_SEMANA_CHOICES = [
        (0, 'Lunes'),
        (1, 'Martes'),
        (2, 'Miércoles'),
        (3, 'Jueves'),
        (4, 'Viernes'),
        (5, 'Sábado'),
        (6, 'Domingo'),
    ]
    
    configuracion_cine = models.ForeignKey(
        'ConfiguracionCine',
        on_delete=models.CASCADE,
        related_name='horarios_atencion',
        verbose_name='Configuración del Cine'
    )
    
    dia_semana = models.PositiveSmallIntegerField(
        choices=DIA_SEMANA_CHOICES,
        verbose_name='Día de la Semana',
        help_text='0=Lunes, 6=Domingo'
    )
    
    hora_apertura = models.TimeField(
        verbose_name='Hora de Apertura',
        help_text='Hora de inicio del rango'
    )
    
    hora_cierre = models.TimeField(
        verbose_name='Hora de Cierre',
        help_text='Hora de fin del rango'
    )
    
    activo = models.BooleanField(
        default=True,
        verbose_name='Activo',
        help_text='Desmarcar para deshabilitar temporalmente este horario sin eliminarlo'
    )
    
    orden = models.PositiveSmallIntegerField(
        default=0,
        verbose_name='Orden',
        help_text='Orden de visualización para múltiples rangos del mismo día (0, 1, 2...)'
    )
    
    # Auditoría
    fecha_creacion = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Fecha de Creación'
    )
    
    fecha_actualizacion = models.DateTimeField(
        auto_now=True,
        verbose_name='Fecha de Actualización'
    )
    
    # Historial de cambios
    history = HistoricalRecords()
    
    class Meta:
        db_table = 'horarios_atencion'
        verbose_name = 'Horario de Atención'
        verbose_name_plural = 'Horarios de Atención'
        ordering = ['dia_semana', 'orden', 'hora_apertura']
        
        indexes = [
            models.Index(
                fields=['dia_semana', 'activo'],
                name='idx_horario_dia_activo'
            ),
            models.Index(
                fields=['configuracion_cine', 'dia_semana'],
                name='idx_horario_config_dia'
            ),
        ]
        
        # CONSTRAINT: Evita rangos incoherentes a nivel DB
        constraints = [
            models.CheckConstraint(
                check=models.Q(hora_cierre__gt=models.F('hora_apertura')),
                name='check_hora_cierre_mayor_apertura'
            )
        ]
    
    def clean(self):
        """
        Validación de coherencia y NO SOLAPAMIENTO para el mismo día.
        
        Solapamiento: Dos rangos [A1, A2) y [B1, B2) se solapan si:
        A1 < B2 AND B1 < A2
        
        Nota: Un rango que termina a las 14:00 y otro que empieza a las 14:00
        NO se solapan (límites exactos permitidos).
        """
        super().clean()
        
        # 1. Validar coherencia básica
        if self.hora_apertura and self.hora_cierre:
            if self.hora_cierre <= self.hora_apertura:
                raise ValidationError({
                    'hora_cierre': 'La hora de cierre debe ser posterior a la hora de apertura.'
                })
        
        # 2. Validar solapamientos con otros rangos del MISMO DÍA
        if self.configuracion_cine_id and self.dia_semana is not None:
            # Excluir el registro actual si estamos editando (self.pk existe)
            otros_horarios = HorarioAtencion.objects.filter(
                configuracion_cine=self.configuracion_cine,
                dia_semana=self.dia_semana,
                activo=True
            )
            
            # Si estamos editando, excluir este registro de la validación
            if self.pk:
                otros_horarios = otros_horarios.exclude(pk=self.pk)
            
            for otro in otros_horarios:
                # Detectar solapamiento: [A1, A2) se solapa con [B1, B2) si:
                # A1 < B2 AND B1 < A2
                # 
                # Usamos < estricto para permitir límites exactos
                # Ejemplo: 10:00-14:00 y 14:00-18:00 son VÁLIDOS (no se solapan)
                if self.hora_apertura < otro.hora_cierre and otro.hora_apertura < self.hora_cierre:
                    dia_nombre = dict(self.DIA_SEMANA_CHOICES)[self.dia_semana]
                    raise ValidationError({
                        'hora_apertura': f'Este rango se solapa con otro horario del {dia_nombre}: '
                                        f'{otro.hora_apertura.strftime("%H:%M")} - {otro.hora_cierre.strftime("%H:%M")}. '
                                        f'Los rangos no deben solaparse.'
                    })
    
    def save(self, *args, **kwargs):
        """Ejecuta validaciones antes de guardar"""
        self.full_clean()
        super().save(*args, **kwargs)
    
    def __str__(self):
        dia = dict(self.DIA_SEMANA_CHOICES)[self.dia_semana]
        estado = "" if self.activo else " (inactivo)"
        return f"{dia}: {self.hora_apertura.strftime('%H:%M')} - {self.hora_cierre.strftime('%H:%M')}{estado}"
