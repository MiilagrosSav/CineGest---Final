"""
Modelo CajaSesion - Representa la apertura/cierre de caja de un turno de boletería.
"""

from django.db import models
from django.conf import settings
from django.db.models import Sum
from decimal import Decimal
from simple_history.models import HistoricalRecords


class CajaSesion(models.Model):
    ESTADO_CHOICES = [
        ('ABIERTA', 'Abierta'),
        ('CERRADA', 'Cerrada'),
    ]

    empleado = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='sesiones_caja',
        verbose_name='Empleado',
    )
    fondo_inicial = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0'),
        verbose_name='Fondo Inicial (efectivo)',
        help_text='Efectivo disponible al abrir la caja',
    )
    fecha_apertura = models.DateTimeField(auto_now_add=True, verbose_name='Fecha de Apertura')
    fecha_cierre = models.DateTimeField(null=True, blank=True, verbose_name='Fecha de Cierre')
    estado = models.CharField(
        max_length=10,
        choices=ESTADO_CHOICES,
        default='ABIERTA',
        verbose_name='Estado',
    )
    observaciones = models.TextField(blank=True, verbose_name='Observaciones al cierre')

    # Snapshot guardado al cerrar (evita recalcular el histórico)
    total_efectivo_cerrado = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
        verbose_name='Total Efectivo (cierre)',
    )
    total_qr_cerrado = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
        verbose_name='Total QR (cierre)',
    )
    total_ventas_cerrado = models.IntegerField(
        null=True, blank=True,
        verbose_name='Cantidad Ventas (cierre)',
    )

    # Arqueo de cierre
    monto_esperado = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
        verbose_name='Monto Esperado en Caja',
        help_text='Fondo inicial + efectivo cobrado (calculado por el sistema).',
    )
    monto_real_declarado = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
        verbose_name='Efectivo Físico Contado',
        help_text='Lo que el empleado contó en la caja al cerrar.',
    )
    diferencia = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
        verbose_name='Diferencia (Real − Esperado)',
        help_text='Positivo = sobrante, Negativo = faltante.',
    )

    history = HistoricalRecords()

    class Meta:
        db_table = 'CajaSesion'
        verbose_name = 'Sesión de Caja'
        verbose_name_plural = 'Sesiones de Caja'
        ordering = ['-fecha_apertura']

    def __str__(self):
        nombre = self.empleado.get_full_name() or self.empleado.username
        return f"Caja #{self.pk} – {nombre} ({self.get_estado_display()})"

    # ------------------------------------------------------------------
    # Helpers internos
    # ------------------------------------------------------------------

    def _ventas_sesion_qs(self):
        """Queryset de ventas PRESENCIALES CONFIRMADAS de este empleado en esta sesión."""
        from ventas.models.venta import Venta
        try:
            empleado_profile = self.empleado.empleado  # User → Empleado reverse accessor
        except Exception:
            return Venta.objects.none()
        qs = Venta.objects.filter(
            id_empleado=empleado_profile,
            tipo_venta='PRESENCIAL',
            estado='CONFIRMADA',
            fecha_compra__gte=self.fecha_apertura,
        )
        if self.fecha_cierre:
            qs = qs.filter(fecha_compra__lte=self.fecha_cierre)
        return qs

    def get_ventas_sesion(self):
        """Ventas de la sesión con datos de método de pago, para la vista de cierre."""
        return self._ventas_sesion_qs().select_related('id_metodo_pago').order_by('-fecha_compra')

    def get_totales(self):
        """
        Devuelve un dict con totales de la sesión.
        Si la caja está CERRADA, usa el snapshot guardado (más rápido).
        """
        if self.estado == 'CERRADA' and self.total_efectivo_cerrado is not None:
            efectivo = self.total_efectivo_cerrado
            return {
                'fondo_inicial': self.fondo_inicial,
                'efectivo': efectivo,
                'qr': self.total_qr_cerrado or Decimal('0'),
                'ventas': self.total_ventas_cerrado or 0,
                'total_caja': self.fondo_inicial + efectivo,
                'monto_esperado': self.monto_esperado or (self.fondo_inicial + efectivo),
                'monto_real_declarado': self.monto_real_declarado,
                'diferencia': self.diferencia,
            }

        qs = self._ventas_sesion_qs()
        efectivo = (
            qs.filter(id_metodo_pago__nombre='Efectivo')
              .aggregate(t=Sum('total'))['t'] or Decimal('0')
        )
        qr = (
            qs.filter(id_metodo_pago__nombre='Mercado Pago')
              .aggregate(t=Sum('total'))['t'] or Decimal('0')
        )
        return {
            'fondo_inicial': self.fondo_inicial,
            'efectivo': efectivo,
            'qr': qr,
            'ventas': qs.count(),
            'total_caja': self.fondo_inicial + efectivo,
            'monto_esperado': self.fondo_inicial + efectivo,
            'monto_real_declarado': None,
            'diferencia': None,
        }
