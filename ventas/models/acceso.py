"""
Modelo para registrar accesos a funciones (validación en puerta)
"""

from django.db import models
from django.conf import settings
from django.utils import timezone
from simple_history.models import HistoricalRecords


class RegistroAcceso(models.Model):
    """
    Registra cada intento de acceso a una función (exitoso o rechazado).
    Permite auditoría completa de validaciones en puerta.
    """
    
    TIPO_VALIDACION_CHOICES = [
        ('QR', 'Escaneo QR'),
        ('MANUAL', 'Búsqueda Manual'),
        ('CODIGO', 'Código de Entrada'),
    ]
    
    RESULTADO_CHOICES = [
        ('PERMITIDO', 'Acceso Permitido'),
        ('RECHAZADO', 'Acceso Rechazado'),
    ]
    
    # Relaciones
    entrada = models.ForeignKey(
        'ventas.Entrada',
        on_delete=models.PROTECT,
        related_name='registros_acceso',
        verbose_name='Entrada Validada',
        null=True,  # Puede ser null si no se encontró la entrada
        blank=True
    )
    
    empleado_validador = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='validaciones_realizadas',
        verbose_name='Empleado que Validó'
    )
    
    # Datos de la validación
    fecha_hora_intento = models.DateTimeField(
        default=timezone.now,
        verbose_name='Fecha y Hora del Intento'
    )
    
    tipo_validacion = models.CharField(
        max_length=10,
        choices=TIPO_VALIDACION_CHOICES,
        default='QR',
        verbose_name='Tipo de Validación'
    )
    
    resultado = models.CharField(
        max_length=10,
        choices=RESULTADO_CHOICES,
        verbose_name='Resultado'
    )
    
    # Datos de búsqueda (para debugging)
    codigo_buscado = models.CharField(
        max_length=200,
        blank=True,
        verbose_name='Código/Texto Buscado'
    )
    
    # Motivo del rechazo
    motivo_rechazo = models.CharField(
        max_length=255,
        blank=True,
        verbose_name='Motivo del Rechazo',
        help_text='Por ejemplo: "Función no comenzó", "Ya usada", "No encontrada"'
    )
    
    # Información adicional de contexto
    ip_origen = models.GenericIPAddressField(
        null=True,
        blank=True,
        verbose_name='IP de Origen'
    )
    
    class Meta:
        db_table = 'RegistroAcceso'
        verbose_name = 'Registro de Acceso'
        verbose_name_plural = 'Registros de Acceso'
        ordering = ['-fecha_hora_intento']
        indexes = [
            models.Index(fields=['entrada', 'fecha_hora_intento'], name='idx_acceso_entrada'),
            models.Index(fields=['resultado', 'fecha_hora_intento'], name='idx_acceso_resultado'),
        ]
    
    def __str__(self):
        if self.entrada:
            return f"Acceso {self.resultado} - Entrada #{self.entrada.id_entrada} - {self.fecha_hora_intento:%d/%m/%Y %H:%M}"
        return f"Acceso {self.resultado} - Búsqueda '{self.codigo_buscado}' - {self.fecha_hora_intento:%d/%m/%Y %H:%M}"
    
    # Historial de cambios
    history = HistoricalRecords()
