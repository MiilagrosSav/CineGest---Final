"""
URLs para la app ventas
"""

from django.urls import path
from ventas.views import pagos, ventas, butacas, compra, reembolsos
from ventas import views as views_root

app_name = 'ventas'

urlpatterns = [
    # URLs de ventas
    path('mis-ventas/', ventas.mis_ventas, name='mis_ventas'),
    path('detalle/<int:venta_id>/', ventas.detalle_venta, name='detalle_venta'),
    
    # URLs de compra
    path('seleccionar-butacas/<int:funcion_id>/', butacas.seleccionar_butacas, name='seleccionar_butacas'),
    path('seleccionar-butacas/intercambio/<int:venta_id>/<int:funcion_id>/', butacas.seleccionar_butacas_intercambio, name='seleccionar_butacas_intercambio'),
    path('confirmar/<int:funcion_id>/', compra.confirmar_compra, name='confirmar_compra'),
    path('procesar/<int:funcion_id>/', compra.procesar_compra, name='procesar_compra'),
    path('procesar-intercambio/<int:venta_id>/<int:funcion_id>/', compra.procesar_intercambio, name='procesar_intercambio'),
    
    # URLs de pagos
    path('pago/iniciar/<int:venta_id>/', pagos.iniciar_pago, name='iniciar_pago'),
    path('pago/exitoso/', pagos.pago_exitoso, name='pago_exitoso'),
    path('pago/fallido/', pagos.pago_fallido, name='pago_fallido'),
    path('pago/pendiente/', pagos.pago_pendiente, name='pago_pendiente'),
    path('webhook/mercadopago/', pagos.webhook_mercadopago, name='webhook_mercadopago'),
    path('compra/<int:venta_id>/intercambiar/', reembolsos.intercambiar_entrada_view, name='intercambiar_entrada'),
]
