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
    
    MEDIO_PAGO_CHOICES = [
        ('EFECTIVO', 'Efectivo'),
        ('MERCADOPAGO', 'Mercado Pago'),
        ('TARJETA', 'Tarjeta'),
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
    medio_pago = models.CharField(
        max_length=20,
        choices=MEDIO_PAGO_CHOICES,
        default='',
        blank=True,
        verbose_name='Medio de Pago',
        help_text='Medio de pago utilizado para la venta'
    )
    codigo_compra = models.CharField(
        max_length=20,
        default='',
        blank=True,
        verbose_name='Código de Compra',
        help_text='Código único para canje de entradas (generado automáticamente)'
    )
    
    class Meta:
        db_table = 'Venta'
        verbose_name = 'Venta'
        verbose_name_plural = 'Ventas'
        ordering = ['-fecha_compra']
        # NOTA: El constraint de unicidad para codigo_compra se maneja
        # mediante un índice parcial en la migración (solo valores no vacíos)
    
    def save(self, *args, **kwargs):
        """Generar código de compra automáticamente si no existe"""
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
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"Venta #{self.id_venta} - {self.id_cliente.usuario.get_full_name() or self.id_cliente.usuario.username}"
    
    def calcular_total(self, request=None, include_detalle: bool = False):
        """
        Calcula el total delegando la lógica al servicio centralizado de promociones.
        Garantiza que Mercado Pago cobre EXACTAMENTE lo mismo que se muestra en pantalla.
        """
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
            return total_final, detalle
            
        return total_final
    
    def cantidad_entradas(self):
        """Retorna la cantidad de entradas de esta venta"""
        return self.entradas.count()
    
    def get_metodo_pago_normalizado(self):
        """
        Retorna el nombre del método de pago normalizado.
        Prioriza el método del Pago (FK) sobre el campo medio_pago.
        
        Returns:
            str: Nombre del método de pago normalizado ('Efectivo', 'Mercado Pago', 'Tarjeta')
        """
        # Prioridad 1: Si existe un registro de Pago con método asignado
        if hasattr(self, 'pago') and self.pago and self.pago.id_metodo_pago:
            return self.pago.id_metodo_pago.nombre
        
        # Prioridad 2: Mapear desde el campo medio_pago (legacy)
        if self.medio_pago:
            mapeo = {
                'EFECTIVO': 'Efectivo',
                'MERCADOPAGO': 'Mercado Pago',
                'TARJETA': 'Tarjeta',
            }
            return mapeo.get(self.medio_pago, self.get_medio_pago_display())
        
        # Fallback: Si no hay información disponible
        return 'No especificado'

    # historial de cambios
    history = HistoricalRecords()
