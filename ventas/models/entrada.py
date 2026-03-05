"""
Modelo Entrada - Representa cada entrada/butaca 
"""

from django.db import models
from django.conf import settings
from simple_history.models import HistoricalRecords
from django.core.exceptions import ValidationError
from django.utils import timezone


class Entrada(models.Model):
    """Representa una entrada individual (una butaca para una función)"""
    
    ESTADO_CHOICES = [
        ('PENDIENTE', 'Pendiente'),
        ('RESERVADA', 'Reservada'),
        ('VENDIDA', 'Vendida'),
        ('ENTREGADA', 'Entregada'),
        ('USADA', 'Usada'),
        ('CANCELADA', 'Cancelada'),
        ('EXPIRADA', 'Expirada'),
    ]
    
    id_entrada = models.AutoField(primary_key=True)
    id_venta = models.ForeignKey(
        'Venta',
        on_delete=models.CASCADE,
        related_name='entradas',
        verbose_name='Venta'
    )
    id_funcion = models.ForeignKey(
        'cine.Funcion',
        on_delete=models.PROTECT,
        related_name='entradas',
        verbose_name='Función'
    )
    id_sala = models.ForeignKey(
        'cine.Sala',
        on_delete=models.PROTECT,
        related_name='entradas',
        verbose_name='Sala'
    )
    id_butaca = models.ForeignKey(
        'cine.Butaca',
        on_delete=models.PROTECT,
        related_name='entradas',
        verbose_name='Butaca'
    )
    id_pelicula = models.ForeignKey(
        'cine.Pelicula',
        on_delete=models.PROTECT,
        related_name='entradas',
        verbose_name='Película'
    )
    estado = models.CharField(
        max_length=20,
        choices=ESTADO_CHOICES,
        default='RESERVADA',
        verbose_name='Estado'
    )
    fecha_creacion = models.DateTimeField(auto_now_add=True, verbose_name='Fecha de creación')
    reservado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,  
        related_name='reservas',
        verbose_name='Reservado por'
    )

    precio_unitario = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=0.00,
        verbose_name='Precio Unitario Real'
    )
    
    class Meta:
        db_table = 'Entrada'
        verbose_name = 'Entrada'
        verbose_name_plural = 'Entradas'
        ordering = ['id_funcion', 'id_butaca']
        constraints = [
            models.UniqueConstraint(fields=['id_funcion', 'id_butaca'], name='UQ_entrada_funcion_butaca')
        ]
        indexes = [
            models.Index(fields=['id_funcion', 'id_butaca', 'estado'], name='idx_lock_butaca'),
        ]
    def clean(self):
        super().clean()
        
        # 1. Saneamiento del campo estado (evita el -1 o basura)
        if self.estado not in dict(self.ESTADO_CHOICES):
            raise ValidationError({'estado': f"El valor '{self.estado}' no es un estado válido."})

        # 2. Inmutabilidad de campos críticos
        if self.pk:
            original = Entrada.objects.get(pk=self.pk)
            errores = {}
            
            # Lista de campos que NO se pueden cambiar jamás
            campos_prohibidos = [
                'id_venta', 'id_funcion', 'id_sala', 
                'id_butaca', 'id_pelicula', 'reservado_por', 'precio_unitario'
            ]
            
            for campo in campos_prohibidos:
                if getattr(original, campo) != getattr(self, campo):
                    errores[campo] = "Este campo es inmutable una vez creada la entrada."
            
            if errores:
                raise ValidationError(errores)

    def save(self, *args, **kwargs):
        # 1. Validación de transición de estados (ANTES de full_clean)
        if self.pk:
            original = Entrada.objects.get(pk=self.pk)
            # FLUJO PERMITIDO: RESERVADA → VENDIDA → ENTREGADA → USADA
            # TAMBIÉN: VENDIDA → USADA (flujo simplificado: imprimir ticket = validar acceso)
            # PROHIBIDO: USADA → RESERVADA, ENTREGADA → VENDIDA, etc.
            estados_validos = {
                'PENDIENTE': ['RESERVADA', 'CANCELADA', 'EXPIRADA'],  # PENDIENTE puede expirar
                'RESERVADA': ['VENDIDA', 'CANCELADA', 'EXPIRADA'],  # RESERVADA puede expirar
                'VENDIDA': ['ENTREGADA', 'USADA', 'CANCELADA'],  # VENDIDA puede ir directo a USADA (canje/presencial) o CANCELADA (función pasada)
                'ENTREGADA': ['USADA', 'CANCELADA'],  # ENTREGADA puede cancelarse si la función pasó
                'USADA': [],  # Estado terminal
                'CANCELADA': [],  # Estado terminal
                'EXPIRADA': [],  # Estado terminal
            }
            if original.estado != self.estado:
                if self.estado not in estados_validos.get(original.estado, []):
                    raise ValidationError(
                        f"Transición de estado inválida: {original.estado} → {self.estado}"
                    )
        
        # 2. Ejecutar todas las validaciones de clean() + validators
        self.full_clean()
        
        # 3. Guardar en BD
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Entrada #{self.id_entrada} - {self.id_pelicula.titulo} - Butaca {self.id_butaca.fila}{self.id_butaca.numero}"

    # historial de cambios
    history = HistoricalRecords()
