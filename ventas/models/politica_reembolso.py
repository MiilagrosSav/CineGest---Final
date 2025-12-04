from django.db import models
from django.utils import timezone


class PoliticaReembolso(models.Model):
    """Política que regula los intercambios (antes: políticas de reembolso).

    Esta política se consulta desde la vista de intercambio y puede impedir
    o condicionar los cambios (por ejemplo, límite de días antes, penalidad).
    """
    nombre = models.CharField(max_length=140, default='Política de Intercambio')
    activo = models.BooleanField(default=True, help_text='Si está activa, esta política permite intercambios con las condiciones definidas')
    dias_antes_minimo = models.IntegerField(default=1, help_text='Número mínimo de días antes de la función para permitir intercambio')
    penalidad_percent = models.DecimalField(max_digits=5, decimal_places=2, default=0.00, help_text='Porcentaje de penalidad aplicado al intercambio (si aplica)')
    max_cambios_por_compra = models.IntegerField(default=1, help_text='Máximo de intercambios permitidos por compra (0 = ilimitado)')
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Política de Reembolso/Intercambio'
        verbose_name_plural = 'Políticas de Reembolso/Intercambio'

    def __str__(self):
        return self.nombre

    def permite_intercambio_para_venta(self, venta):
        """Validación rápida si la política permite intercambio para la venta dada.

        Verifica que la política esté activa y el requisito de días
        antes de la función. Puede extenderse para validar número de cambios.
        """
        if not self.activo:
            return (False, 'No hay una política de intercambio activa en este momento.')

        # Obtener la primera entrada asociada para revisar la fecha de la función
        entradas = venta.entradas.all()
        if not entradas.exists():
            return (False, 'La compra no tiene entradas asociadas.')

        primera = entradas[0]
        fecha_funcion = primera.id_funcion.fecha_hora
        ahora = timezone.now()
        # Convertir la política basada en días a horas para comparación precisa
        horas_minimas = int(self.dias_antes_minimo) * 24
        horas_restantes = (fecha_funcion - ahora).total_seconds() / 3600.0

        if horas_restantes < horas_minimas:
            return (False, f'Los intercambios sólo están permitidos con al menos {self.dias_antes_minimo} día(s) de anticipación.')

        return (True, '')
