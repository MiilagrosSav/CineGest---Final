"""
Modelo Venta - Representa una compra/venta completa
"""

from django.db import models
from django.utils import timezone
from decimal import Decimal, ROUND_HALF_UP
from accounts.models import Cliente, Empleado
from simple_history.models import HistoricalRecords
from promociones.services import calcular_precio_final


class Venta(models.Model):
    """Representa una venta/compra de entradas"""
    
    ESTADO_CHOICES = [
        ('PENDIENTE', 'Pendiente'),
        ('PENDIENTE_PAGO', 'Pendiente de Pago'),
        ('CONFIRMADA', 'Confirmada'),
        ('CANCELADA', 'Cancelada'),
    ]
    
    TIPO_VENTA_CHOICES = [
        ('ONLINE', 'Online'),
        ('PRESENCIAL', 'Presencial'),
    ]
    
    id_venta = models.AutoField(primary_key=True)
    id_cliente = models.ForeignKey(
        Cliente, 
        on_delete=models.PROTECT,
        related_name='ventas',
        verbose_name='Cliente'
    )
    id_empleado = models.ForeignKey(
        Empleado,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='ventas_procesadas',
        verbose_name='Empleado',
        help_text='Empleado que procesó la venta (solo para ventas presenciales)'
    )
    cupon_utilizado = models.ForeignKey(
        'promociones.CuponGenerado',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='ventas_usadas',
        verbose_name='Cupón Utilizado',
        help_text='Referencias al cupón usado para esta venta (si aplica)'
    )
    fecha_compra = models.DateTimeField(
        default=timezone.now,
        verbose_name='Fecha de Compra'
    )
    tipo_venta = models.CharField(
        max_length=20,
        choices=TIPO_VENTA_CHOICES,
        default='ONLINE',
        verbose_name='Tipo de Venta'
    )
    estado = models.CharField(
        max_length=20,
        choices=ESTADO_CHOICES,
        default='PENDIENTE',
        verbose_name='Estado'
    )
    id_metodo_pago = models.ForeignKey(
        'ventas.MetodoPago',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='ventas',
        verbose_name='Método de Pago',
        help_text='Método de pago utilizado para la venta'
    )
    codigo_compra = models.CharField(
        max_length=20,
        default='',
        blank=True,
        verbose_name='Código de Compra',
        help_text='Código único para canje de entradas (generado automáticamente)'
    )
    total = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name='Total',
        help_text='Total de la venta calculado y persistido para precisión financiera'
    )
    
    class Meta:
        db_table = 'Venta'
        verbose_name = 'Venta'
        verbose_name_plural = 'Ventas'
        ordering = ['-fecha_compra']
        # NOTA: El constraint de unicidad para codigo_compra se maneja
        # mediante un índice parcial en la migración (solo valores no vacíos)
        # ✅ OPTIMIZACIÓN: Índices para mejorar rendimiento de reportes y dashboards
        indexes = [
            models.Index(fields=['estado', 'fecha_compra'], name='idx_venta_estado_fecha'),
            models.Index(fields=['id_cliente', '-fecha_compra'], name='idx_venta_cliente_fecha'),
            models.Index(fields=['tipo_venta', 'estado'], name='idx_venta_tipo_estado'),
        ]
    
    def save(self, *args, **kwargs):
        """Generar código de compra automáticamente si no existe y calcular total"""
        # 1. Generar código de compra para ventas online
        if not self.codigo_compra and self.tipo_venta == 'ONLINE':
            import random
            import string
            # Generar código único: CG-XXXX-XXXX
            while True:
                parte1 = ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))
                parte2 = ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))
                codigo = f"CG-{parte1}-{parte2}"
                # Verificar que no exista
                if not Venta.objects.filter(codigo_compra=codigo).exists():
                    self.codigo_compra = codigo
                    break
        
        # 2. Calcular y guardar total si es una venta confirmada y tiene entradas
        if self.estado == 'CONFIRMADA' and self.pk:
            # Solo calcular si ya existe en DB (tiene entradas asociadas)
            try:
                total_calculado = self.calcular_total()
                if total_calculado:
                    self.total = total_calculado
            except Exception:
                pass  # Si falla el cálculo, mantener el valor actual
        
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"Venta #{self.id_venta} - {self.id_cliente.usuario.get_full_name() or self.id_cliente.usuario.username}"
    
    def calcular_total(self, request=None, include_detalle: bool = False):
        """
        Calcula el total delegando la lógica al servicio centralizado de promociones.
        Garantiza que Mercado Pago cobre EXACTAMENTE lo mismo que se muestra en pantalla.
        
        Si la venta ya tiene un total persistido, lo retorna directamente para evitar
        discrepancias en reportes financieros.
        """
        # ✅ OPTIMIZACIÓN: Si ya hay un total guardado y es confirmada, usarlo
        if self.total is not None and self.estado == 'CONFIRMADA' and not include_detalle:
            return self.total
        
        # 1. Preparar datos básicos
        entradas = self.entradas.all()
        if not entradas.exists():
            return Decimal('0.00')
            
        cantidad = entradas.count()
        funcion = entradas.first().id_funcion # Asumimos homogeneidad
        
        # 2. Determinar la promoción a usar
        promo_obj = None
        
        # Prioridad A: Cupón ya guardado en la venta (Persistencia)
        if self.cupon_utilizado:
            # CAMBIO AQUÍ: Accedemos a través de la política de origen
            # Usamos getattr para evitar errores si el cupón es muy viejo
            politica = getattr(self.cupon_utilizado, 'politica_origen', None)
            if politica:
                promo_obj = politica.promocion_a_otorgar
            else:
                # Fallback por si acaso tienes cupones viejos con estructura directa
                promo_obj = getattr(self.cupon_utilizado, 'promocion', None)
        
        # Prioridad B: Cupón en sesión (si pasaron el request)
        elif request and request.session.get('promo_activa_id'):
            try:
                from promociones.models.promocion import Promocion
                promo_obj = Promocion.objects.get(pk=request.session['promo_activa_id'])
            except Exception:
                pass

        # 3. LLAMAR AL SERVICIO ÚNICO (La fuente de la verdad)
        total_final, promo_aplicada, detalle = calcular_precio_final(
            funcion,
            cantidad,
            promocion_especifica=promo_obj
        )
        
        # 4. Retorno según lo que pida el llamador
        if include_detalle:
            return total_final, promo_aplicada, detalle
            
        return total_final
    
    def cantidad_entradas(self):
        """Retorna la cantidad de entradas de esta venta"""
        return self.entradas.count()
    
    def get_metodo_pago_normalizado(self):
        """
        Retorna el nombre del método de pago normalizado.
        
        Returns:
            str: Nombre del método de pago ('Efectivo', 'Mercado Pago', 'Tarjeta')
        """
        # Prioridad 1: Si existe un método de pago asignado directamente
        if self.id_metodo_pago:
            return self.id_metodo_pago.nombre
        
        # Prioridad 2: Si existe un registro de Pago con método asignado
        if hasattr(self, 'pago') and self.pago and self.pago.id_metodo_pago:
            return self.pago.id_metodo_pago.nombre
        
        # Fallback: Si no hay información disponible
        return 'No especificado'

    # historial de cambios
    history = HistoricalRecords()
