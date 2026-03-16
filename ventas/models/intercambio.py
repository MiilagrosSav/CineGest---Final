"""
Modelo Intercambio - Registro de auditoría de intercambios de entradas
"""

from django.db import models
from django.utils import timezone
from ventas.models.venta import Venta
from cine.models import Funcion
from simple_history.models import HistoricalRecords
from django.core.exceptions import ValidationError

class Intercambio(models.Model):
    """
    Registro de auditoría para cada intercambio de entradas realizado.
    
    Permite:
    - Trazabilidad completa de cambios
    - Enforcement de límites (max_cambios_por_compra)
    - Reportes y análisis de patrones
    - Auditoría para soporte al cliente
    """
    
    MOTIVO_CHOICES = [
        ('HORARIO', 'Cambio de horario'),
        ('FECHA', 'Cambio de fecha'),
        ('PELICULA', 'Cambio de película'),
        ('DISPONIBILIDAD', 'Disponibilidad de asientos'),
        ('OTRO', 'Otro motivo'),
    ]
    
    ESTADO_CHOICES = [
        ('COMPLETADO', 'Completado'),
        ('FALLIDO', 'Fallido'),
        ('REVERTIDO', 'Revertido'),
    ]
    
    id_intercambio = models.AutoField(primary_key=True)
    
    # Relaciones
    venta = models.ForeignKey(
        Venta,
        on_delete=models.PROTECT,
        related_name='intercambios',
        verbose_name='Venta'
    )
    funcion_origen = models.ForeignKey(
        Funcion,
        on_delete=models.PROTECT,
        related_name='intercambios_origen',
        verbose_name='Función Original'
    )
    funcion_destino = models.ForeignKey(
        Funcion,
        on_delete=models.PROTECT,
        related_name='intercambios_destino',
        verbose_name='Nueva Función'
    )
    
    # Metadatos
    fecha_intercambio = models.DateTimeField(
        default=timezone.now,
        verbose_name='Fecha del Intercambio'
    )
    motivo = models.CharField(
        max_length=20,
        choices=MOTIVO_CHOICES,
        default='OTRO',
        verbose_name='Motivo del Intercambio'
    )
    estado = models.CharField(
        max_length=20,
        choices=ESTADO_CHOICES,
        default='COMPLETADO',
        verbose_name='Estado'
    )
    
    # Información adicional
    cantidad_entradas = models.IntegerField(
        verbose_name='Cantidad de Entradas Intercambiadas',
        help_text='Número de entradas que se intercambiaron'
    )
    notas = models.TextField(
        blank=True,
        default='',
        verbose_name='Notas',
        help_text='Información adicional sobre el intercambio'
    )
    
    # Auditoría
    usuario_email = models.EmailField(
        verbose_name='Email del Usuario',
        help_text='Email del cliente que realizó el intercambio'
    )
    
    # Nota: IP y User-Agent se capturan automáticamente en HistoricalIntercambio
    # mediante django-simple-history con HistoryRequestMiddleware habilitado
    
    class Meta:
        db_table = 'ventas_intercambio'
        verbose_name = 'Intercambio de Entrada'
        verbose_name_plural = 'Intercambios de Entradas'
        ordering = ['-fecha_intercambio']
        indexes = [
            models.Index(fields=['venta', 'fecha_intercambio'], name='IDX_int_venta_fecha'),
            models.Index(fields=['estado'], name='IDX_int_estado'),
            models.Index(fields=['funcion_origen'], name='IDX_int_func_origen'),
            models.Index(fields=['funcion_destino'], name='IDX_int_func_destino'),
        ]
    
    def __str__(self):
        return f"Intercambio #{self.id_intercambio} - Venta #{self.venta.id_venta} ({self.fecha_intercambio.strftime('%d/%m/%Y %H:%M')})"
    

    def clean(self):
        super().clean()
        
        # 1. Validación de estados para evitar el -1
        if self.motivo not in dict(self.MOTIVO_CHOICES):
            raise ValidationError({'motivo': f"'{self.motivo}' no es un motivo de intercambio válido."})
            
        if self.estado not in dict(self.ESTADO_CHOICES):
            raise ValidationError({'estado': f"'{self.estado}' no es un estado de intercambio válido."})

        # 2. Bloqueo de campos de auditoría en edición
        if self.pk:
            original = Intercambio.objects.get(pk=self.pk)
            errores = {}
            
            # Lista de campos que NO se pueden tocar jamás
            campos_bloqueados = [
                'venta', 'funcion_origen', 'funcion_destino', 
                'fecha_intercambio', 'cantidad_entradas', 
                'usuario_email'
            ]
            
            for campo in campos_bloqueados:
                if getattr(original, campo) != getattr(self, campo):
                    errores[campo] = "Este campo es parte de la auditoría y no puede modificarse."
            
            if errores:
                raise ValidationError(errores)

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)


    @property
    def dias_anticipacion_origen(self):
        """Calcula cuántos días de anticipación tenía respecto a la función original"""
        if self.funcion_origen and self.fecha_intercambio:
            delta = self.funcion_origen.fecha_hora - self.fecha_intercambio
            return delta.days
        return None
    
    @staticmethod
    def contar_intercambios_venta(venta):
        """
        Cuenta cuántos intercambios exitosos ha realizado una venta.
        
        Args:
            venta (Venta): La venta a consultar
            
        Returns:
            int: Número de intercambios completados
        """
        return Intercambio.objects.filter(
            venta=venta,
            estado='COMPLETADO'
        ).count()
    
    @staticmethod
    def puede_intercambiar(venta, politica):
        """
        Verifica si una venta puede realizar más intercambios según la política.
        
        Args:
            venta (Venta): La venta a verificar
            politica (PoliticaReembolso): La política activa
            
        Returns:
            tuple: (bool, str) - (puede_intercambiar, mensaje_error)
        """
        if not politica or not politica.activo:
            return (False, 'No hay una política de intercambio activa en este momento.')

        count = Intercambio.contar_intercambios_venta(venta)

        if not getattr(politica, 'permitir_reintercambio', False) and count > 0:
            return (False, 'Esta compra ya tuvo un intercambio y la política no permite reintercambio.')
        
        if politica.max_cambios_por_compra > 0:
            if count >= politica.max_cambios_por_compra:
                return (False, f'Has alcanzado el límite máximo de {politica.max_cambios_por_compra} intercambio(s) para esta compra.')
        
        return (True, '')
    
    # historial de cambios
    history = HistoricalRecords()
