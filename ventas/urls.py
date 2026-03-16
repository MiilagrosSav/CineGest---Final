"""
URLs para la app ventas
"""

from django.urls import path
from ventas.views import pagos, ventas, butacas, compra, reembolsos, canje, acceso
from ventas import views as views_root
from ventas.views import presencial

app_name = 'ventas'

urlpatterns = [
    # URLs de ventas
    path('mis-ventas/', ventas.mis_ventas, name='mis_ventas'),
    path('lista/', ventas.lista_ventas, name='lista_ventas'),
    path('detalle/<int:venta_id>/', ventas.detalle_venta, name='detalle_venta'),
    path('comprobante/<int:venta_id>/', ventas.comprobante_pago, name='comprobante_pago'),
    path('confirmacion/<int:venta_id>/', ventas.comprobante_compra, name='comprobante_compra'),
    
    # URLs de compra
    path('seleccionar-butacas/<int:funcion_id>/', butacas.seleccionar_butacas, name='seleccionar_butacas'),
    path('seleccionar-butacas/intercambio/<int:venta_id>/<int:funcion_id>/', butacas.seleccionar_butacas_intercambio, name='seleccionar_butacas_intercambio'),
    path('confirmar/<int:funcion_id>/', compra.confirmar_compra, name='confirmar_compra'),
    path('api/verificar-butacas/<int:funcion_id>/', butacas.verificar_butacas_ocupadas, name='verificar_butacas_ocupadas'),
    path('procesar/<int:funcion_id>/', compra.procesar_compra, name='procesar_compra'),
    path('procesar-intercambio/<int:venta_id>/<int:funcion_id>/', compra.procesar_intercambio, name='procesar_intercambio'),
    
    # URLs de pagos
    path('pago/iniciar/<int:venta_id>/', pagos.iniciar_pago, name='iniciar_pago'),
    path('pago/marcar-iniciado/<int:venta_id>/', pagos.marcar_pago_iniciado, name='marcar_pago_iniciado'),
    path('pago/ir-a-mp/<int:venta_id>/', pagos.ir_a_mercadopago, name='ir_a_mercadopago'),
    path('pago/exitoso/', pagos.pago_exitoso, name='pago_exitoso'),
    path('pago/fallido/', pagos.pago_fallido, name='pago_fallido'),
    path('pago/pendiente/', pagos.pago_pendiente, name='pago_pendiente'),
    path('webhook/mercadopago/', pagos.webhook_mercadopago, name='webhook_mercadopago'),
    path('compra/<int:venta_id>/intercambiar/', reembolsos.intercambiar_entrada_view, name='intercambiar_entrada'),
    path('intercambio/exitoso/<int:intercambio_id>/', reembolsos.intercambio_exitoso_view, name='intercambio_exitoso'),
    # Presencial / Boletería
    path('presencial/', presencial.dashboard_presencial, name='dashboard_presencial'),
    path('presencial/seleccionar/<int:funcion_id>/', presencial.seleccionar_butacas_presencial, name='seleccionar_butacas_presencial'),
    path('presencial/confirmar/<int:funcion_id>/', presencial.confirmar_venta_presencial, name='confirmar_venta_presencial'),
    path('presencial/procesar/', presencial.procesar_venta_presencial, name='procesar_venta_presencial'),
    path('presencial/ticket/<int:venta_id>/', presencial.ticket_exitoso, name='ticket_exitoso'),
    path('presencial/horarios/', presencial.ver_horarios, name='ver_horarios'),
    path('presencial/buscar-cliente/', presencial.buscar_cliente, name='buscar_cliente'),
    path('presencial/caja/abrir/', presencial.apertura_caja, name='apertura_caja'),
    path('presencial/caja/cerrar/', presencial.cierre_caja, name='cierre_caja'),
    path('presencial/caja/turno-finalizado/', presencial.turno_finalizado, name='turno_finalizado'),
    path('presencial/qr/crear-preferencia/', presencial.presencial_crear_preferencia_qr, name='presencial_crear_preferencia_qr'),
    path('presencial/qr/estado/<int:venta_id>/', presencial.presencial_estado_venta, name='presencial_estado_venta'),
    path('presencial/qr/cancelar/<int:venta_id>/', presencial.presencial_cancelar_venta_qr, name='presencial_cancelar_venta_qr'),

    # Canje de entradas online
    path('canje/', canje.canje_rapido_view, name='canje_rapido'),
    path('canje/buscar/', canje.buscar_venta_para_impresion, name='buscar_venta_canje'),
    path('canje/marcar-impreso/', canje.marcar_como_impreso, name='marcar_como_impreso'),
    path('canje/ticket/<int:venta_id>/', canje.ticket_canje_view, name='ticket_canje'),
    
    # Validación de acceso en puerta
    path('acceso/', acceso.validar_acceso_view, name='validar_acceso'),
    path('acceso/buscar/', acceso.buscar_entrada_api, name='buscar_entrada_api'),
    path('acceso/manual/', acceso.validacion_manual_view, name='validacion_manual'),
]
