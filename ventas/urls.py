"""
URLs para la app ventas
"""

from django.urls import path
from ventas.views import pagos

app_name = 'ventas'

urlpatterns = [
    # URLs de pagos
    path('pago/iniciar/<int:venta_id>/', pagos.iniciar_pago, name='iniciar_pago'),
    path('pago/exitoso/', pagos.pago_exitoso, name='pago_exitoso'),
    path('pago/fallido/', pagos.pago_fallido, name='pago_fallido'),
    path('pago/pendiente/', pagos.pago_pendiente, name='pago_pendiente'),
    path('webhook/mercadopago/', pagos.webhook_mercadopago, name='webhook_mercadopago'),
]
