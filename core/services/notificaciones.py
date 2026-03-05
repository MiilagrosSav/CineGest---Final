"""
Servicio centralizado de notificaciones por email
"""

import logging
import io
import base64
from typing import Optional
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.conf import settings
from django.utils.html import strip_tags

# Importaciones para QR
try:
    import qrcode
    from qrcode.image.pure import PyPNGImage
    QRCODE_AVAILABLE = True
except ImportError:
    QRCODE_AVAILABLE = False
    

logger = logging.getLogger(__name__)


class NotificacionService:
    """
    Servicio para envío de notificaciones por email
    """
    
    def __init__(self):
        self.from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@cinegest.com')
    
    def _get_configuracion_cine(self):
        """Obtener configuración del cine (singleton)"""
        try:
            from cine.models import ConfiguracionCine
            return ConfiguracionCine.obtener_configuracion()
        except Exception as e:
            logger.warning(f"No se pudo obtener configuración del cine: {e}")
            return None
    
    def _get_site_name(self, request=None):
        """Obtener nombre del sitio para URLs absolutas"""
        try:
            if request:
                return request.build_absolute_uri('/').rstrip('/')
            # Fallback simple sin usar Site framework
            return getattr(settings, 'SITE_URL', 'http://localhost:8000')
        except Exception:
            return 'http://localhost:8000'
    
    def _generar_qr_base64(self, data: str) -> Optional[str]:
        """
        Generar código QR y devolverlo como base64 data URI
        
        Args:
            data: Texto a codificar en el QR
            
        Returns:
            String con data URI (data:image/png;base64,...) o None si falla
        """
        if not QRCODE_AVAILABLE:
            logger.warning("qrcode library no está disponible")
            return None
        
        try:
            # Crear QR code
            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_L,
                box_size=10,
                border=4,
            )
            qr.add_data(data)
            qr.make(fit=True)
            
            # Generar imagen
            img = qr.make_image(fill_color="black", back_color="white")
            
            # Convertir a base64
            buffer = io.BytesIO()
            img.save(buffer, format='PNG')
            img_base64 = base64.b64encode(buffer.getvalue()).decode()
            
            return f"data:image/png;base64,{img_base64}"
        except Exception as e:
            logger.error(f"Error generando QR code: {e}")
            return None
    
    def enviar_bienvenida(self, usuario) -> bool:
        """
        Enviar email de bienvenida a nuevo usuario
        
        Args:
            usuario: Instancia de Usuario
            
        Returns:
            True si se envió correctamente, False si falló
        """
        try:
            configuracion_cine = self._get_configuracion_cine()
            
            # Preparar contexto
            context = {
                'usuario': usuario,
                'nombre_completo': usuario.get_full_name() or usuario.username,
                'configuracion_cine': configuracion_cine,
                'site_name': configuracion_cine.nombre if configuracion_cine else 'CineGest',
            }
            
            # Renderizar templates
            html_content = render_to_string('core/emails/bienvenida.html', context)
            text_content = render_to_string('core/emails/bienvenida.txt', context)
            
            # Crear email
            subject = f"¡Bienvenido a {context['site_name']}!"
            email = EmailMultiAlternatives(
                subject=subject,
                body=text_content,
                from_email=self.from_email,
                to=[usuario.email]
            )
            email.attach_alternative(html_content, "text/html")
            
            # Enviar
            email.send(fail_silently=False)
            logger.info(f"Email de bienvenida enviado a {usuario.email}")
            return True
            
        except Exception as e:
            logger.error(f"Error enviando email de bienvenida a {usuario.email}: {e}")
            return False
    
    def enviar_confirmacion_compra(self, venta, request=None) -> bool:
        """
        Enviar email de confirmación de compra
        
        Args:
            venta: Instancia de Venta
            request: HttpRequest (opcional, para URLs absolutas)
            
        Returns:
            True si se envió correctamente, False si falló
        """
        try:
            configuracion_cine = self._get_configuracion_cine()
            usuario = venta.id_cliente.usuario
            
            # Obtener datos de la venta
            entradas = venta.entradas.select_related(
                'id_funcion__pelicula',
                'id_funcion__id_sala',
                'id_butaca'
            ).all()
            
            primera_entrada = entradas.first() if entradas else None
            cantidad = entradas.count()
            
            # Generar QR para la venta (código de compra)
            qr_data = f"VENTA:{venta.codigo_compra}"
            qr_src = self._generar_qr_base64(qr_data)
            
            # Generar QR individual para cada entrada
            entradas_con_qr = []
            for entrada in entradas:
                entrada_qr = self._generar_qr_base64(f"ENTRADA:{entrada.codigo_entrada}")
                entradas_con_qr.append({
                    'entrada': entrada,
                    'qr_src': entrada_qr
                })
            
            # Información de promociones/descuentos
            promocion_aplicada = None
            descuento_info = None
            
            # Si la venta tiene cupón aplicado, obtener info de promoción
            if hasattr(venta, 'cupon_utilizado') and venta.cupon_utilizado:
                cupon = venta.cupon_utilizado
                if hasattr(cupon, 'id_promocion'):
                    promocion_aplicada = cupon.id_promocion
                    # Calcular info de descuento
                    subtotal = venta.monto_total  # Simplificado
                    descuento_info = {
                        'subtotal': subtotal,
                        'descuento': 0,  # Calcular según tipo de promoción
                        'total_final': venta.monto_total
                    }
            
            # Preparar contexto
            context = {
                'usuario': usuario,
                'venta': venta,
                'primera_entrada': primera_entrada,
                'cantidad': cantidad,
                'entradas': entradas_con_qr,
                'qr_src': qr_src,
                'promocion_aplicada': promocion_aplicada,
                'descuento_info': descuento_info,
                'configuracion_cine': configuracion_cine,
                'site_name': self._get_site_name(request),
            }
            
            # Renderizar templates
            html_content = render_to_string('core/emails/confirmacion_compra.html', context)
            text_content = render_to_string('core/emails/confirmacion_compra.txt', context)
            
            # Crear email
            nombre_cine = configuracion_cine.nombre if configuracion_cine else 'CineGest'
            subject = f"Confirmación de Compra #{venta.id_venta} - {nombre_cine}"
            email = EmailMultiAlternatives(
                subject=subject,
                body=text_content,
                from_email=self.from_email,
                to=[usuario.email]
            )
            email.attach_alternative(html_content, "text/html")
            
            # Enviar
            email.send(fail_silently=False)
            logger.info(f"Email de confirmación de compra enviado a {usuario.email} para venta #{venta.id_venta}")
            return True
            
        except Exception as e:
            logger.error(f"Error enviando email de confirmación de compra para venta #{venta.id_venta}: {e}")
            return False
    
    def enviar_confirmacion_intercambio(
        self, 
        venta, 
        intercambio, 
        funcion_origen, 
        funcion_destino, 
        request=None
    ) -> bool:
        """
        Enviar email de confirmación de intercambio
        
        Args:
            venta: Instancia de Venta
            intercambio: Instancia de Intercambio
            funcion_origen: Función original
            funcion_destino: Nueva función
            request: HttpRequest (opcional)
            
        Returns:
            True si se envió correctamente, False si falló
        """
        try:
            configuracion_cine = self._get_configuracion_cine()
            usuario = venta.id_cliente.usuario
            
            # Obtener entradas del intercambio
            entradas_intercambiadas = intercambio.entradas.select_related(
                'id_funcion__pelicula',
                'id_funcion__id_sala',
                'id_butaca'
            ).all()
            
            # Generar QR para nuevas entradas
            entradas_con_qr = []
            for entrada in entradas_intercambiadas:
                entrada_qr = self._generar_qr_base64(f"ENTRADA:{entrada.codigo_entrada}")
                entradas_con_qr.append({
                    'entrada': entrada,
                    'qr_src': entrada_qr
                })
            
            # Preparar contexto
            context = {
                'usuario': usuario,
                'venta': venta,
                'intercambio': intercambio,
                'funcion_origen': funcion_origen,
                'funcion_destino': funcion_destino,
                'entradas': entradas_con_qr,
                'cantidad': entradas_intercambiadas.count(),
                'configuracion_cine': configuracion_cine,
                'site_name': self._get_site_name(request),
            }
            
            # Renderizar templates
            html_content = render_to_string('core/emails/confirmacion_intercambio.html', context)
            text_content = render_to_string('core/emails/confirmacion_intercambio.txt', context)
            
            # Crear email
            nombre_cine = configuracion_cine.nombre if configuracion_cine else 'CineGest'
            subject = f"Confirmación de Intercambio #{intercambio.id_intercambio} - {nombre_cine}"
            email = EmailMultiAlternatives(
                subject=subject,
                body=text_content,
                from_email=self.from_email,
                to=[usuario.email]
            )
            email.attach_alternative(html_content, "text/html")
            
            # Enviar
            email.send(fail_silently=False)
            logger.info(f"Email de confirmación de intercambio enviado a {usuario.email} para intercambio #{intercambio.id_intercambio}")
            return True
            
        except Exception as e:
            logger.error(f"Error enviando email de confirmación de intercambio #{intercambio.id_intercambio}: {e}")
            return False
    
    def enviar_oferta_promocion(
        self, 
        cliente, 
        promocion, 
        cupon, 
        link, 
        funcion=None
    ) -> bool:
        """
        Enviar email con oferta de promoción/cupón
        
        Args:
            cliente: Instancia de Cliente
            promocion: Instancia de Promocion
            cupon: Instancia de Cupon
            link: URL para canjear el cupón
            funcion: Función relacionada (opcional)
            
        Returns:
            True si se envió correctamente, False si falló
        """
        try:
            configuracion_cine = self._get_configuracion_cine()
            usuario = cliente.usuario
            
            # Preparar contexto
            context = {
                'usuario': usuario,
                'cliente': cliente,
                'promocion': promocion,
                'cupon': cupon,
                'link': link,
                'funcion': funcion,
                'configuracion_cine': configuracion_cine,
                'site_name': configuracion_cine.nombre if configuracion_cine else 'CineGest',
            }
            
            # Renderizar templates
            html_content = render_to_string('core/emails/promocion_oferta.html', context)
            text_content = render_to_string('core/emails/promocion_oferta.txt', context)
            
            # Crear email
            nombre_cine = configuracion_cine.nombre if configuracion_cine else 'CineGest'
            subject = f"🎁 ¡Tenés una oferta especial de {nombre_cine}!"
            email = EmailMultiAlternatives(
                subject=subject,
                body=text_content,
                from_email=self.from_email,
                to=[usuario.email]
            )
            email.attach_alternative(html_content, "text/html")
            
            # Enviar
            email.send(fail_silently=False)
            logger.info(f"Email de oferta de promoción enviado a {usuario.email} - Cupón: {cupon.token}")
            return True
            
        except Exception as e:
            logger.error(f"Error enviando email de oferta de promoción a {usuario.email}: {e}")
            return False


# Singleton del servicio
notificacion_service = NotificacionService()
