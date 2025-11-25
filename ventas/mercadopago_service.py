"""
Servicio para integración con Mercado Pago
Maneja la creación de preferencias de pago y procesamiento de pagos
"""

import mercadopago
from django.conf import settings
from django.urls import reverse
from promociones.models.cuponGenerado import CuponGenerado


class MercadoPagoService:
    """Servicio para manejar operaciones de Mercado Pago"""
    
    def __init__(self):
        """Inicializar SDK de Mercado Pago con el access token"""
        access_token = settings.MERCADOPAGO_ACCESS_TOKEN
        if not access_token or access_token == settings.MERCADOPAGO_ACCESS_TOKEN:
            print("⚠️ ADVERTENCIA: Usando credenciales de prueba de Mercado Pago")
            print("⚠️ Para producción, configura MERCADOPAGO_ACCESS_TOKEN en las variables de entorno")
        self.sdk = mercadopago.SDK(access_token)
    
    def crear_preferencia_pago(self, venta, request):
        """
        Crear una preferencia de pago en Mercado Pago
        
        Args:
            venta: Objeto Venta con los datos de la compra
            request: Request de Django para generar URLs absolutas
            
        Returns:
            dict: Respuesta de Mercado Pago con la preferencia creada
        """
        # Calcular el monto total de la venta (pasamos request para aplicar posible promoción en sesión)
        # Antes de crear la preferencia, si existe `promo_token` en sesión, asociar el cupón a la venta
        total = venta.calcular_total(request)
        try:
            promo_token = None
            if request is not None:
                promo_token = request.session.get('promo_token')
            if promo_token:
                cupon = CuponGenerado.objects.filter(token=str(promo_token)).first()
                if cupon:
                    venta.cupon_utilizado = cupon
                    venta.save()
        except Exception:
            # No queremos bloquear la creación de la preferencia si hay un problema con el cupón
            pass
        
        # Crear los items de la preferencia usando el total calculado con promociones
        # En lugar de listar cada entrada individual, crear un solo item con el total
        cantidad_entradas = venta.entradas.count()
        primera_entrada = venta.entradas.first()
        
        items = [{
            "title": f"Entradas - {primera_entrada.id_funcion.pelicula.titulo}" if primera_entrada else "Entradas de Cine",
            "description": f"{cantidad_entradas} entrada(s) para {primera_entrada.id_funcion.pelicula.titulo}" if primera_entrada else f"{cantidad_entradas} entrada(s)",
            "quantity": 1,
            "unit_price": float(total),
            "currency_id": "ARS"
        }]
        
        # URLs de retorno - construir manualmente para asegurar que funcionen
        # Forzar HTTPS para ngrok (Mercado Pago requiere HTTPS)
        host = request.get_host()
        scheme = "https" if "ngrok" in host else request.scheme
        base_url = f"{scheme}://{host}"
        # Agregar external_reference en la URL como parámetro para asegurar que llegue
        success_url = f"{base_url}{reverse('ventas:pago_exitoso')}?venta_id={venta.id_venta}"
        failure_url = f"{base_url}{reverse('ventas:pago_fallido')}?venta_id={venta.id_venta}"
        pending_url = f"{base_url}{reverse('ventas:pago_pendiente')}?venta_id={venta.id_venta}"
        
        # Datos de la preferencia
        preference_data = {
            "items": items,
            "payer": {
                "name": venta.id_cliente.usuario.first_name or "Cliente",
                "surname": venta.id_cliente.usuario.last_name or "CineGest",
                "email": venta.id_cliente.usuario.email,
            },
            "back_urls": {
                "success": success_url,
                "failure": failure_url,
                "pending": pending_url
            },
            "auto_return": "approved",  # Redirigir automáticamente después del pago exitoso
            "external_reference": str(venta.id_venta),  # ID de tu venta para identificarla
            "statement_descriptor": "CINEGEST",  # Nombre que aparece en el resumen de tarjeta
            "binary_mode": True,  # Solo estados: aprobado o rechazado (no pendiente)
            
            # Habilitar tarjetas de crédito/débito para pruebas
            "payment_methods": {
                "excluded_payment_methods": [],  # No excluir ningún método
                "excluded_payment_types": [],    # No excluir ningún tipo
                "installments": 12,              # Hasta 12 cuotas
            }
        }
        
        print(f"📦 Creando preferencia para venta #{venta.id_venta} - Total: ${total}")
        print(f"🔗 Back URLs configuradas:")
        print(f"   ✅ Success: {success_url}")
        print(f"   ❌ Failure: {failure_url}")
        print(f"   ⏳ Pending: {pending_url}")
        
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
