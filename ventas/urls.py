"""
URLs para la app ventas
"""

from django.urls import path
from ventas.views import pagos, ventas, butacas, compra, reembolsos, canje
from ventas import views as views_root
from ventas.views import presencial

app_name = 'ventas'

urlpatterns = [
    # URLs de ventas
    path('mis-ventas/', ventas.mis_ventas, name='mis_ventas'),
    path('detalle/<int:venta_id>/', ventas.detalle_venta, name='detalle_venta'),
    
    # URLs de compra
    path('seleccionar-butacas/<int:funcion_id>/', butacas.seleccionar_butacas, name='seleccionar_butacas'),
    path('seleccionar-butacas/intercambio/<int:venta_id>/<int:funcion_id>/', butacas.seleccionar_butacas_intercambio, name='seleccionar_butacas_intercambio'),
    path('confirmar/<int:funcion_id>/', compra.confirmar_compra, name='confirmar_compra'),
    path('api/verificar-butacas/<int:funcion_id>/', butacas.verificar_butacas_ocupadas, name='verificar_butacas_ocupadas'),
    path('procesar/<int:funcion_id>/', compra.procesar_compra, name='procesar_compra'),
    path('procesar-intercambio/<int:venta_id>/<int:funcion_id>/', compra.procesar_intercambio, name='procesar_intercambio'),
    
    # URLs de pagos
    path('pago/iniciar/<int:venta_id>/', pagos.iniciar_pago, name='iniciar_pago'),
    path('pago/exitoso/', pagos.pago_exitoso, name='pago_exitoso'),
    path('pago/fallido/', pagos.pago_fallido, name='pago_fallido'),
    path('pago/pendiente/', pagos.pago_pendiente, name='pago_pendiente'),
    path('webhook/mercadopago/', pagos.webhook_mercadopago, name='webhook_mercadopago'),
    path('compra/<int:venta_id>/intercambiar/', reembolsos.intercambiar_entrada_view, name='intercambiar_entrada'),
    # Presencial / Boletería
    path('presencial/', presencial.dashboard_presencial, name='dashboard_presencial'),
    path('presencial/seleccionar/<int:funcion_id>/', presencial.seleccionar_butacas_presencial, name='seleccionar_butacas_presencial'),
    path('presencial/confirmar/<int:funcion_id>/', presencial.confirmar_venta_presencial, name='confirmar_venta_presencial'),
    path('presencial/procesar/', presencial.procesar_venta_presencial, name='procesar_venta_presencial'),
    path('presencial/ticket/<int:venta_id>/', presencial.ticket_exitoso, name='ticket_exitoso'),
    path('presencial/horarios/', presencial.ver_horarios, name='ver_horarios'),
    path('presencial/buscar-cliente/', presencial.buscar_cliente, name='buscar_cliente'),
    
    # Canje de entradas online
    path('canje/', canje.canje_rapido_view, name='canje_rapido'),
    path('canje/buscar/', canje.buscar_venta_para_impresion, name='buscar_venta_canje'),
    path('canje/marcar-impreso/', canje.marcar_como_impreso, name='marcar_como_impreso'),
    path('canje/ticket/<int:venta_id>/', canje.ticket_canje_view, name='ticket_canje'),
]
