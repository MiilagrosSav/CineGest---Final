from django.db import models
from django.conf import settings
from django.utils import timezone


class Reembolso(models.Model):
    """Registro de intentos de reembolso y respuesta del proveedor."""
    venta = models.ForeignKey(
        'Venta', on_delete=models.CASCADE, related_name='reembolsos', verbose_name='Venta'
    )

    pago = models.ForeignKey(
        'Pago', on_delete=models.SET_NULL, null=True, blank=True, related_name='reembolsos', verbose_name='Pago'
    )

    solicitado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, verbose_name='Solicitado por'
    )

    porcentaje = models.PositiveIntegerField(verbose_name='Porcentaje aplicado')

    monto_solicitado = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='Monto solicitado')
    monto_reembolsado = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, verbose_name='Monto reembolsado')

    provider_payment_id = models.CharField(max_length=200, null=True, blank=True, verbose_name='ID de pago en proveedor')
    provider_response = models.JSONField(null=True, blank=True, verbose_name='Respuesta del proveedor')

    ok = models.BooleanField(default=False, verbose_name='OK')
    status_code = models.CharField(max_length=50, null=True, blank=True, verbose_name='Código de estado')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Reembolso'
        verbose_name_plural = 'Reembolsos'
        ordering = ['-created_at']

    def __str__(self):
        return f"Reembolso #{self.pk} - Venta #{getattr(self.venta, 'id_venta', self.venta_id)} - {self.monto_solicitado}"
