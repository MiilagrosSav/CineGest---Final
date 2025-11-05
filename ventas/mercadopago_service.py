"""
Servicio para integración con Mercado Pago
Maneja la creación de preferencias de pago y procesamiento de pagos
"""

import mercadopago
from django.conf import settings
from django.urls import reverse


class MercadoPagoService:
    """Servicio para manejar operaciones de Mercado Pago"""
    
    def __init__(self):
        """Inicializar SDK de Mercado Pago con el access token"""
        self.sdk = mercadopago.SDK(settings.MERCADOPAGO_ACCESS_TOKEN)
    
    def crear_preferencia_pago(self, venta, request):
        """
        Crear una preferencia de pago en Mercado Pago
        
        Args:
            venta: Objeto Venta con los datos de la compra
            request: Request de Django para generar URLs absolutas
            
        Returns:
            dict: Respuesta de Mercado Pago con la preferencia creada
        """
        # URLs de retorno (debes crear estas vistas después)
        success_url = request.build_absolute_uri(reverse('ventas:pago_exitoso'))
        failure_url = request.build_absolute_uri(reverse('ventas:pago_fallido'))
        pending_url = request.build_absolute_uri(reverse('ventas:pago_pendiente'))
        
        # Calcular el monto total de la venta
        total = venta.calcular_total()  # Deberás implementar este método en el modelo Venta
        
        # Crear los items de la preferencia
        items = []
        for entrada in venta.entradas.all():
            items.append({
                "title": f"Entrada - {entrada.id_funcion.pelicula.titulo}",
                "description": f"Sala {entrada.id_sala.numero} - Butaca {entrada.id_butaca.fila}{entrada.id_butaca.numero}",
                "quantity": 1,
                "unit_price": float(entrada.id_funcion.precio_base),
                "currency_id": "ARS"  # Cambiar según tu país
            })
        
        # Datos de la preferencia
        preference_data = {
            "items": items,
            "payer": {
                "name": venta.id_cliente.usuario.first_name,
                "surname": venta.id_cliente.usuario.last_name,
                "email": venta.id_cliente.usuario.email,
            },
            "back_urls": {
                "success": success_url,
                "failure": failure_url,
                "pending": pending_url
            },
            "auto_return": "approved",  # Retorno automático cuando se aprueba el pago
            "external_reference": str(venta.id_venta),  # ID de tu venta para identificarla
            "notification_url": request.build_absolute_uri(reverse('ventas:webhook_mercadopago')),  # Para notificaciones IPN
            "statement_descriptor": "CINEGEST",  # Nombre que aparece en el resumen de tarjeta
        }
        
        # Crear la preferencia en Mercado Pago
        preference_response = self.sdk.preference().create(preference_data)
        
        return preference_response
    
    def obtener_pago(self, payment_id):
        """
        Obtener información de un pago específico
        
        Args:
            payment_id: ID del pago en Mercado Pago
            
        Returns:
            dict: Información del pago
        """
        payment_info = self.sdk.payment().get(payment_id)
        return payment_info
    
    def procesar_notificacion_webhook(self, data):
        """
        Procesar notificación IPN (Instant Payment Notification) de Mercado Pago
        
        Args:
            data: Datos recibidos del webhook
            
        Returns:
            dict: Información del pago procesado
        """
        # Mercado Pago envía el ID del pago en el parámetro 'data.id'
        if data.get('type') == 'payment':
            payment_id = data.get('data', {}).get('id')
            
            if payment_id:
                # Obtener información completa del pago
                payment_info = self.obtener_pago(payment_id)
                return payment_info
        
        return None
