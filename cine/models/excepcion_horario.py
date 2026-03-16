from django.db import models
from django.core.exceptions import ValidationError
from simple_history.models import HistoricalRecords


class ExcepcionHorario(models.Model):
    """
    Excepciones a los horarios regulares para fechas específicas.
    Modelo simplificado: UN solo rango horario por excepción.
    
    Casos de uso:
    - Días cerrados (cerrado=True): Feriados, mantenimiento, eventos
    - Días con horario modificado (cerrado=False): Un solo rango horario
    
    Ejemplos:
    - 25/12/2024: cerrado=True, descripcion="Navidad"
    - 24/12/2024: cerrado=False, hora_apertura=10:00, hora_cierre=18:00, descripcion="Nochebuena"
    
    Prioridad: Las excepciones tienen prioridad sobre los horarios regulares.
    Si existe una excepción para una fecha, se ignoran los HorarioAtencion del día.
    """
    
    configuracion_cine = models.ForeignKey(
        'ConfiguracionCine',
        on_delete=models.CASCADE,
        related_name='excepciones_horarios',
        verbose_name='Configuración del Cine'
    )
    
    fecha = models.DateField(
        verbose_name='Fecha de Inicio',
        help_text='Fecha de inicio de la excepción (ej: 25/12/2024). Si no se especifica fecha_fin, aplica solo a este día.'
    )
    
    fecha_fin = models.DateField(
        null=True,
        blank=True,
        verbose_name='Fecha de Fin (Opcional)',
        help_text='Si se especifica, la excepción aplica desde "fecha" hasta "fecha_fin" (rango inclusivo)'
    )
    
    cerrado = models.BooleanField(
        default=False,
        verbose_name='Cine Cerrado',
        help_text='Marcar si el cine está completamente cerrado este día'
    )
    
    hora_apertura = models.TimeField(
        null=True,
        blank=True,
        verbose_name='Hora de Apertura',
        help_text='Hora de apertura (solo si cerrado=False)'
    )
    
    hora_cierre = models.TimeField(
        null=True,
        blank=True,
        verbose_name='Hora de Cierre',
        help_text='Hora de cierre (solo si cerrado=False)'
    )
    
    descripcion = models.CharField(
        max_length=200,
        blank=True,
        default='',
        verbose_name='Descripción',
        help_text='Motivo de la excepción (ej: "Navidad", "Mantenimiento")'
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
        db_table = 'excepciones_horarios'
        verbose_name = 'Excepción de Horario'
        verbose_name_plural = 'Excepciones de Horarios'
        ordering = ['fecha']
        
        # Una configuración solo puede tener UNA excepción por fecha
        constraints = [
            models.UniqueConstraint(
                fields=['configuracion_cine', 'fecha'],
                name='unique_excepcion_por_fecha'
            )
        ]
        
        indexes = [
            models.Index(
                fields=['configuracion_cine', 'fecha'],
                name='idx_excepcion_config_fecha'
            ),
            models.Index(
                fields=['fecha', 'cerrado'],
                name='idx_excepcion_fecha_cerrado'
            ),
        ]
    
    def clean(self):
        """
        Validaciones de coherencia:
        
        1. Si fecha_fin está especificado → fecha_fin >= fecha
        2. Si cerrado=True → hora_apertura y hora_cierre deben ser NULL
        3. Si cerrado=False → hora_apertura y hora_cierre son OBLIGATORIOS
        4. hora_cierre > hora_apertura (cuando aplique)
        5. Verificar solapamientos de rangos con otras excepciones
        6. CRÍTICO: Si cerrado=True → NO puede haber ventas confirmadas para esas fechas
        """
        super().clean()
        
        # 1. Validar coherencia de rango de fechas
        if self.fecha_fin and self.fecha_fin < self.fecha:
            raise ValidationError({
                'fecha_fin': 'La fecha de fin debe ser igual o posterior a la fecha de inicio.'
            })
        
        # 2. Validar solapamientos de rangos
        # Solo verificar si tenemos una fecha (nueva excepción o edición)
        if self.fecha:
            # Rango de esta excepción
            fecha_inicio = self.fecha
            fecha_final = self.fecha_fin if self.fecha_fin else self.fecha
            
            # Obtener configuración_cine para la consulta
            # Si no está asignada aún (creación), usar el singleton
            if self.configuracion_cine_id:
                config_id = self.configuracion_cine_id
            else:
                from .configuracion_cine import ConfiguracionCine
                config_id = ConfiguracionCine.load().id
            
            # Buscar excepciones existentes que solapen con este rango
            # Excluir la instancia actual si estamos editando
            excepciones_existentes = ExcepcionHorario.objects.filter(
                configuracion_cine_id=config_id
            )
            
            if self.pk:  # Si es edición, excluir esta misma excepción
                excepciones_existentes = excepciones_existentes.exclude(pk=self.pk)
            
            for excepcion in excepciones_existentes:
                # Rango de la excepción existente
                exc_inicio = excepcion.fecha
                exc_final = excepcion.fecha_fin if excepcion.fecha_fin else excepcion.fecha
                
                # Verificar solapamiento: dos rangos [A1,A2] y [B1,B2] se solapan si:
                # A1 <= B2 AND A2 >= B1
                if fecha_inicio <= exc_final and fecha_final >= exc_inicio:
                    # Hay solapamiento
                    if excepcion.fecha_fin:
                        rango_str = f"{excepcion.fecha.strftime('%d/%m/%Y')} al {excepcion.fecha_fin.strftime('%d/%m/%Y')}"
                    else:
                        rango_str = excepcion.fecha.strftime('%d/%m/%Y')
                    
                    raise ValidationError({
                        'fecha': f'Este rango se solapa con una excepción existente: {rango_str}. '
                                f'No puede haber excepciones solapadas para las mismas fechas.'
                    })
        
        # 3. Si está cerrado, NO debe tener horarios
        if self.cerrado:
            # Si está cerrado, NO debe tener horarios
            if self.hora_apertura is not None or self.hora_cierre is not None:
                raise ValidationError({
                    'cerrado': 'Si el cine está cerrado, no debe especificar horarios de apertura/cierre. '
                              'Deje esos campos vacíos.'
                })
        else:
            # Si NO está cerrado, DEBE tener ambos horarios
            errores = {}
            
            if self.hora_apertura is None:
                errores['hora_apertura'] = 'Este campo es obligatorio cuando el cine NO está cerrado.'
            
            if self.hora_cierre is None:
                errores['hora_cierre'] = 'Este campo es obligatorio cuando el cine NO está cerrado.'
            
            if errores:
                raise ValidationError(errores)
            
            # Validar coherencia de horarios
            if self.hora_apertura and self.hora_cierre:
                if self.hora_cierre <= self.hora_apertura:
                    raise ValidationError({
                        'hora_cierre': 'La hora de cierre debe ser posterior a la hora de apertura.'
                    })
        
        # 6. VALIDACIÓN CRÍTICA: No permitir cerrar o modificar si hay ventas confirmadas para la fecha
        if self.fecha:
            from ventas.models import Venta
            
            # Determinar rango de fechas a verificar
            fecha_inicio = self.fecha
            fecha_final = self.fecha_fin if self.fecha_fin else self.fecha
            
            # Buscar ventas confirmadas para funciones en ese rango de fechas
            # Estados que implican compromiso: CONFIRMADA, PENDIENTE_PAGO, PENDIENTE
            ventas_comprometidas = Venta.objects.filter(
                entradas__id_funcion__fecha_hora__date__gte=fecha_inicio,
                entradas__id_funcion__fecha_hora__date__lte=fecha_final,
                estado__in=['CONFIRMADA', 'PENDIENTE_PAGO', 'PENDIENTE']
            ).distinct()
            
            if ventas_comprometidas.exists():
                # Contar cuántas ventas y entradas
                total_ventas = ventas_comprometidas.count()
                total_entradas = 0
                
                for venta in ventas_comprometidas:
                    total_entradas += venta.entradas.filter(
                        id_funcion__fecha_hora__date__gte=fecha_inicio,
                        id_funcion__fecha_hora__date__lte=fecha_final
                    ).count()
                
                # Formatear mensaje según si es rango o día único
                if fecha_final != fecha_inicio:
                    fecha_str = f"del {fecha_inicio.strftime('%d/%m/%Y')} al {fecha_final.strftime('%d/%m/%Y')}"
                else:
                    fecha_str = f"el día {fecha_inicio.strftime('%d/%m/%Y')}"
                
                # Pluralización correcta
                entrada_plural = "s" if total_entradas != 1 else ""
                vendida_plural = "s" if total_entradas != 1 else ""
                venta_plural = "s" if total_ventas != 1 else ""
                
                raise ValidationError({
                    'cerrado': (
                        f'No es posible cerrar el cine {fecha_str}: '
                        f'Existen {total_entradas} entrada{entrada_plural} ya vendida{vendida_plural} '
                        f'({total_ventas} venta{venta_plural}). '
                        f'Debe cancelar las funciones y gestionar las devoluciones antes de proceder.'
                    )
                })
    
    def save(self, *args, **kwargs):
        """Ejecuta validaciones antes de guardar y aplica baja lógica a funciones si corresponde"""
        self.full_clean()
        
        # Si se está cerrando el cine y pasó las validaciones (no hay ventas)
        # marcar todas las funciones de ese día como inactivas
        if self.cerrado and self.fecha:
            from cine.models.funcion import Funcion
            
            # Determinar rango de fechas
            fecha_inicio = self.fecha
            fecha_final = self.fecha_fin if self.fecha_fin else self.fecha
            
            # Buscar funciones activas en ese rango
            funciones_a_desactivar = Funcion.objects.filter(
                fecha_hora__date__gte=fecha_inicio,
                fecha_hora__date__lte=fecha_final,
                activo=True
            )
            
            # Aplicar baja lógica a todas las funciones del rango
            for funcion in funciones_a_desactivar:
                funcion.soft_delete()
        
        super().save(*args, **kwargs)
    
    def __str__(self):
        """
        Representación en string mostrando rango cuando aplique.
        """
        # Determinar si es rango o fecha única
        if self.fecha_fin:
            rango = f"{self.fecha.strftime('%d/%m/%Y')} al {self.fecha_fin.strftime('%d/%m/%Y')}"
        else:
            rango = self.fecha.strftime('%d/%m/%Y')
        
        # Construir mensaje según tipo de excepción
        if self.cerrado:
            return f"{rango} - CERRADO ({self.descripcion or 'Sin motivo'})"
        else:
            if self.hora_apertura and self.hora_cierre:
                return (f"{rango} - "
                       f"{self.hora_apertura.strftime('%H:%M')} a {self.hora_cierre.strftime('%H:%M')} "
                       f"({self.descripcion or 'Horario modificado'})")
            else:
                return f"{rango} - Horario Modificado"
    
    def aplica_a_fecha(self, fecha):
        """
        Verifica si esta excepción aplica a una fecha dada.
        
        Args:
            fecha (date): Fecha a verificar
            
        Returns:
            bool: True si la excepción aplica, False en caso contrario
            
        Ejemplos:
            >>> # Excepción de un solo día (25/12/2024)
            >>> excepcion.aplica_a_fecha(date(2024, 12, 25))  # True
            >>> excepcion.aplica_a_fecha(date(2024, 12, 26))  # False
            
            >>> # Excepción de rango (01/01/2025 al 15/01/2025)
            >>> excepcion.aplica_a_fecha(date(2025, 1, 5))    # True (dentro del rango)
            >>> excepcion.aplica_a_fecha(date(2025, 1, 20))   # False (fuera del rango)
        """
        if self.fecha_fin:
            # Verificar si está dentro del rango (inclusivo)
            return self.fecha <= fecha <= self.fecha_fin
        else:
            # Verificar si es la fecha exacta
            return self.fecha == fecha
