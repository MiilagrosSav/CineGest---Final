from django.db import models
from core.mixins import SoftDeleteMixin
from django.utils import timezone
from decimal import Decimal, ROUND_HALF_UP
from simple_history.models import HistoricalRecords


class PoliticaReembolso(SoftDeleteMixin, models.Model):
    """Política que regula los intercambios (antes: políticas de reembolso).

    Esta política se consulta desde la vista de intercambio y puede impedir
    o condicionar los cambios (por ejemplo, límite de días antes de la función).
    """
    nombre = models.CharField(max_length=140, default='Política de Intercambio')
    activo = models.BooleanField(default=True, help_text='Si está activa, esta política permite intercambios con las condiciones definidas')
    permitir_intercambio = models.BooleanField(
        default=True,
        help_text='Habilita o bloquea globalmente la posibilidad de realizar intercambios bajo esta política.'
    )
    dias_antes_minimo = models.IntegerField(default=1, help_text='Número mínimo de días antes de la función para permitir intercambio')
    max_cambios_por_compra = models.IntegerField(default=1, help_text='Máximo de intercambios permitidos por compra (0 = ilimitado)')
    ofrecer_promos_vinculo = models.BooleanField(
        default=False,
        help_text='Si está activo, al elegir la nueva función se consideran promociones de vínculo específico.'
    )
    permitir_reintercambio = models.BooleanField(
        default=False,
        help_text='Permite realizar un nuevo intercambio sobre una compra que ya tuvo intercambio previo.'
    )
    permitir_con_cupon_promocion = models.BooleanField(
        default=False,
        help_text='Permite intercambiar compras realizadas con cupón o cualquier tipo de promoción.'
    )
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Política de Reembolso/Intercambio'
        verbose_name_plural = 'Políticas de Reembolso/Intercambio'

    def save(self, *args, **kwargs):
        """Normalizar nombre de la política a Title Case"""
        if self.nombre:
            self.nombre = self.nombre.strip().title()
        super().save(*args, **kwargs)
    
    def __str__(self):
        return self.nombre

    def _obtener_funcion_origen(self, venta):
        entradas_activas = venta.entradas.exclude(estado__in=['CANCELADA', 'EXPIRADA']).select_related('id_funcion')
        primera = entradas_activas.first()
        return primera.id_funcion if primera else None

    def _venta_tiene_cupon_o_promocion(self, venta, funcion_origen):
        if venta.cupon_utilizado:
            return True

        # Si la venta ya fue intercambiada y no tiene cupón asociado,
        # no inferimos promo por diferencia de montos porque el origen real
        # pudo cambiar durante el intercambio.
        try:
            if venta.intercambios.filter(estado='COMPLETADO').exists():
                return False
        except Exception:
            pass

        if not funcion_origen:
            return False

        try:
            entradas_activas = venta.entradas.exclude(estado__in=['CANCELADA', 'EXPIRADA'])
            cantidad_entradas = entradas_activas.count()
            if cantidad_entradas <= 0:
                return False

            total_base = (Decimal(funcion_origen.precio_base) * Decimal(cantidad_entradas)).quantize(
                Decimal('0.01'),
                rounding=ROUND_HALF_UP,
            )

            monto_pagado = None
            if getattr(venta, 'pago', None) and venta.pago and venta.pago.monto is not None:
                monto_pagado = Decimal(venta.pago.monto)
            elif venta.total is not None:
                monto_pagado = Decimal(venta.total)

            if monto_pagado is None:
                return False

            monto_pagado = monto_pagado.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            return monto_pagado < total_base
        except Exception:
            return False

    def _calcular_total_destino_con_politica(self, funcion_destino, cantidad_entradas):
        from promociones.services import calcular_precio_final, obtener_mejor_promocion_global

        cantidad = int(cantidad_entradas)
        if cantidad <= 0:
            return Decimal('0.00')

        if self.ofrecer_promos_vinculo:
            total, _, _ = calcular_precio_final(funcion_destino, cantidad)
            return Decimal(total).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

        promo_global = obtener_mejor_promocion_global(funcion_destino)
        if promo_global:
            total, _, _ = calcular_precio_final(
                funcion_destino,
                cantidad,
                promocion_especifica=promo_global,
            )
            return Decimal(total).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

        total_base = Decimal(funcion_destino.precio_base) * Decimal(cantidad)
        return total_base.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

    def _obtener_total_origen_referencia(self, venta, funcion_origen, entradas_activas):
        """Obtiene el total de referencia para comparar precios en intercambio.

        Prioriza datos financieros válidos (> 0). Si no existen, usa los datos de
        entradas activas o el precio base de la función de origen como fallback.
        """
        cantidad_entradas = entradas_activas.count()

        try:
            total_venta = Decimal(venta.total) if venta.total is not None else None
            if total_venta is not None and total_venta > 0:
                return total_venta.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        except Exception:
            pass

        try:
            pago = getattr(venta, 'pago', None)
            if pago and pago.monto is not None:
                monto_pago = Decimal(pago.monto)
                if monto_pago > 0:
                    return monto_pago.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        except Exception:
            pass

        try:
            precios = [
                Decimal(e.precio_unitario)
                for e in entradas_activas
                if getattr(e, 'precio_unitario', None) is not None and Decimal(e.precio_unitario) > 0
            ]
            if precios:
                return sum(precios, Decimal('0.00')).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        except Exception:
            pass

        return self._calcular_total_destino_con_politica(funcion_origen, cantidad_entradas)

    def validar_intercambio(self, venta, funcion_destino):
        """Valida reglas de negocio avanzadas para intercambios."""
        if not self.activo:
            return (False, 'No hay una política de intercambio activa en este momento.')
        if not self.permitir_intercambio:
            return (False, 'La política activa no permite intercambios en este momento.')

        entradas_activas = venta.entradas.exclude(estado__in=['CANCELADA', 'EXPIRADA']).select_related('id_funcion')
        if not entradas_activas.exists():
            return (False, 'La compra no tiene entradas activas para intercambiar.')

        if funcion_destino is None:
            return (False, 'Debes seleccionar una función destino válida para el intercambio.')

        funcion_origen = entradas_activas.first().id_funcion
        ahora = timezone.now()

        # Si la función original ya empezó o pasó, no se puede intercambiar.
        if funcion_origen.fecha_hora <= ahora:
            return (False, 'La función original ya comenzó o finalizó. No se puede realizar el intercambio.')

        # Regla temporal por día calendario (no por horas exactas)
        fecha_origen_local = timezone.localtime(funcion_origen.fecha_hora)
        ahora_local = timezone.localtime(ahora)
        dias_restantes = (fecha_origen_local.date() - ahora_local.date()).days
        dias_minimos = int(self.dias_antes_minimo)
        if dias_minimos > 0 and dias_restantes < dias_minimos:
            return (False, f'Los intercambios sólo están permitidos con al menos {self.dias_antes_minimo} día(s) de anticipación.')

        if funcion_destino.fecha_hora <= ahora:
            return (False, 'La función seleccionada ya pasó o está en curso.')

        # Regla de precio unitario exacto: la butaca de destino debe costar lo mismo.
        precio_origen = Decimal(funcion_origen.precio_base).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        precio_destino = Decimal(funcion_destino.precio_base).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        if precio_destino != precio_origen:
            return (
                False,
                f'La función destino debe tener el mismo precio por entrada. Origen: ${precio_origen}, destino: ${precio_destino}.'
            )

        # Regla de retorno/reintercambio
        from ventas.models import Intercambio
        intercambios_completados = Intercambio.contar_intercambios_venta(venta)
        if not self.permitir_reintercambio and intercambios_completados > 0:
            return (False, 'Esta compra ya tuvo un intercambio y la política no permite reintercambio.')

        # Límite de intercambios por entrada (aplicado a nivel compra)
        if self.max_cambios_por_compra > 0 and intercambios_completados >= self.max_cambios_por_compra:
            return (False, f'Has alcanzado el límite máximo de {self.max_cambios_por_compra} intercambio(s) por entrada para esta compra.')

        # Regla cupón/promoción
        if not self.permitir_con_cupon_promocion:
            if self._venta_tiene_cupon_o_promocion(venta, funcion_origen):
                return (False, 'Las compras con cupón o promoción no son elegibles para intercambio según la política activa.')

        cantidad_entradas = entradas_activas.count()
        total_origen = self._obtener_total_origen_referencia(venta, funcion_origen, entradas_activas)
        total_destino = self._calcular_total_destino_con_politica(funcion_destino, cantidad_entradas)

        # Regla crítica: intercambio sin diferencia, precio exactamente igual
        if total_destino != total_origen:
            return (
                False,
                f'El intercambio debe mantener exactamente el mismo precio. Origen: ${total_origen}, destino: ${total_destino}.'
            )

        return (True, '')

    def permite_intercambio_para_venta(self, venta):
        """Validación rápida si la política permite intercambio para la venta dada.

        Verifica que la política esté activa y el requisito de días
        antes de la función. Puede extenderse para validar número de cambios.
        """
        funcion_origen = self._obtener_funcion_origen(venta)
        if not funcion_origen:
            return (False, 'La compra no tiene entradas asociadas.')

        if not self.activo:
            return (False, 'No hay una política de intercambio activa en este momento.')
        if not self.permitir_intercambio:
            return (False, 'La política activa no permite intercambios en este momento.')

        ahora = timezone.now()

        if funcion_origen.fecha_hora <= ahora:
            return (False, 'La función original ya comenzó o finalizó. No se puede realizar el intercambio.')

        fecha_origen_local = timezone.localtime(funcion_origen.fecha_hora)
        ahora_local = timezone.localtime(ahora)
        dias_restantes = (fecha_origen_local.date() - ahora_local.date()).days
        dias_minimos = int(self.dias_antes_minimo)
        if dias_minimos > 0 and dias_restantes < dias_minimos:
            return (False, f'Los intercambios sólo están permitidos con al menos {self.dias_antes_minimo} día(s) de anticipación.')

        from ventas.models import Intercambio
        intercambios_completados = Intercambio.contar_intercambios_venta(venta)
        if not self.permitir_reintercambio and intercambios_completados > 0:
            return (False, 'Esta compra ya tuvo un intercambio y la política no permite reintercambio.')

        if self.max_cambios_por_compra > 0 and intercambios_completados >= self.max_cambios_por_compra:
            return (False, f'Has alcanzado el límite máximo de {self.max_cambios_por_compra} intercambio(s) por entrada para esta compra.')

        if not self.permitir_con_cupon_promocion:
            if self._venta_tiene_cupon_o_promocion(venta, funcion_origen):
                return (False, 'Las compras con cupón o promoción no son elegibles para intercambio según la política activa.')

        # Importante: en este punto NO se valida precio, porque aún no hay función destino elegida.
        return (True, '')

    # Historial para auditoría detallada de cambios de política.
    # Nota: permitir_intercambio existe en tabla principal legacy, pero no en la tabla histórica.
    history = HistoricalRecords(excluded_fields=['permitir_intercambio'])
