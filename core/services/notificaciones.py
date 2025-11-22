"""
Servicio de notificaciones por email.

Centraliza toda la lógica de envío de emails del sistema:
- Bienvenida (registro de usuarios)
- Compras (confirmación de compra)
- Intercambios (confirmación de intercambio)
"""

import logging
import base64
import io
import urllib.parse
from typing import Optional, Dict, Any, List
try:
    import qrcode  # type: ignore
    HAS_QRCODE = True
except Exception:  # pragma: no cover - runtime fallback if package missing
    qrcode = None
    HAS_QRCODE = False
from PIL import Image
from django.core.mail import send_mail, EmailMultiAlternatives
from django.template.loader import render_to_string
from django.conf import settings

logger = logging.getLogger(__name__)


class NotificacionService:
    """
    Servicio centralizado para envío de notificaciones por email.
    """
    
    def __init__(self):
        self.logger = logger
        self.from_email = settings.DEFAULT_FROM_EMAIL
        if not HAS_QRCODE:
            # Inform at service init time to help debugging in dev
            self.logger.warning(
                'La librería "qrcode" no está disponible en el entorno. '
                'Se usará el servicio externo para generar QR como fallback.'
            )
    
    def _enviar_email(
        self,
        asunto: str,
        template_html: str,
        template_txt: str,
        destinatario: str,
        context: Dict[str, Any]
    ) -> bool:
        """
        Método privado para enviar emails con HTML y texto plano.
        
        Args:
            asunto: Asunto del email
            template_html: Path al template HTML
            template_txt: Path al template de texto plano
            destinatario: Email del destinatario
            context: Contexto para renderizar templates
            
        Returns:
            bool: True si se envió correctamente, False en caso contrario
        """
        try:
            # Renderizar templates
            html_content = render_to_string(template_html, context)
            text_content = render_to_string(template_txt, context)
            
            # Crear email con alternativas
            email = EmailMultiAlternatives(
                subject=asunto,
                body=text_content,
                from_email=self.from_email,
                to=[destinatario]
            )
            email.attach_alternative(html_content, "text/html")
            
            # Enviar
            email.send(fail_silently=False)
            
            self.logger.info(f"Email enviado exitosamente a {destinatario}: {asunto}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error enviando email a {destinatario}: {e}", exc_info=True)
            return False
    
    def enviar_bienvenida(self, usuario) -> bool:
        """
        Envía email de bienvenida al registrar un nuevo usuario.
        
        Args:
            usuario: Objeto Usuario (accounts.models.Usuario)
            
        Returns:
            bool: True si se envió correctamente
        """
        context = {
            'usuario': usuario,
            'nombre_completo': usuario.get_full_name() or usuario.username,
            'site_name': 'CineGest',
        }
        
        return self._enviar_email(
            asunto=f'¡Bienvenido a CineGest, {context["nombre_completo"]}!',
            template_html='core/emails/bienvenida.html',
            template_txt='core/emails/bienvenida.txt',
            destinatario=usuario.email,
            context=context
        )
    
    def enviar_confirmacion_compra(self, venta, request=None) -> bool:
        """
        Envía email de confirmación de compra.
        
        Args:
            venta: Objeto Venta (ventas.models.Venta)
            request: Request HTTP (opcional, para construir URLs absolutas)
            
        Returns:
            bool: True si se envió correctamente
        """
        cliente = venta.id_cliente
        usuario = cliente.usuario
        entradas = list(venta.entradas.filter(estado__in=['RESERVADA', 'VENDIDA']))

        # Calcular total
        total = sum(entrada.id_funcion.precio_base for entrada in entradas)

        # Generar QR localmente para cada entrada (usar qrcode + Pillow)
        tickets: List[Dict[str, Optional[str]]] = []
        for entrada in entradas:
            qr_data_value = f"CINEGEST-{entrada.id_entrada}-{venta.id_venta}"
            qr_src = None
            try:
                qr = qrcode.QRCode(box_size=6, border=2)
                qr.add_data(qr_data_value)
                qr.make(fit=True)
                img = qr.make_image(fill_color="black", back_color="white").convert('RGB')
                buf = io.BytesIO()
                img.save(buf, format='PNG')
                buf.seek(0)
                b64 = base64.b64encode(buf.read()).decode('ascii')
                qr_src = f"data:image/png;base64,{b64}"
            except Exception:
                # Fallback a servicio externo si algo falla
                qr_src = f"https://api.qrserver.com/v1/create-qr-code/?size=300x300&data={urllib.parse.quote(qr_data_value)}"

            tickets.append({'entrada': entrada, 'qr_src': qr_src})

        context = {
            'usuario': usuario,
            'venta': venta,
            'entradas': entradas,
            'tickets': tickets,
            'total': total,
            'cantidad': len(entradas),
            'request': request,
        }
        
        return self._enviar_email(
            asunto=f'✅ Confirmación de Compra - Venta #{venta.id_venta}',
            template_html='core/emails/confirmacion_compra.html',
            template_txt='core/emails/confirmacion_compra.txt',
            destinatario=usuario.email,
            context=context
        )
    
    def enviar_confirmacion_intercambio(
        self,
        venta,
        intercambio,
        funcion_origen,
        funcion_destino,
        request=None
    ) -> bool:
        """
        Envía email de confirmación de intercambio.
        
        Args:
            venta: Objeto Venta
            intercambio: Objeto Intercambio
            funcion_origen: Función original (cancelada)
            funcion_destino: Nueva función (confirmada)
            request: Request HTTP (opcional)
            
        Returns:
            bool: True si se envió correctamente
        """
        from ventas.constants import EstadoEntrada
        
        cliente = venta.id_cliente
        usuario = cliente.usuario
        entradas_nuevas = venta.entradas.filter(estado=EstadoEntrada.RESERVADA)
        
        context = {
            'usuario': usuario,
            'venta': venta,
            'intercambio': intercambio,
            'funcion_origen': funcion_origen,
            'funcion_destino': funcion_destino,
            'entradas_nuevas': entradas_nuevas,
            'request': request,
        }
        
        return self._enviar_email(
            asunto=f'✅ Confirmación de Intercambio - Venta #{venta.id_venta}',
            template_html='core/emails/confirmacion_intercambio.html',
            template_txt='core/emails/confirmacion_intercambio.txt',
            destinatario=usuario.email,
            context=context
        )

    def enviar_oferta_promocion(self, cliente, promocion, cupon, link, funcion=None, request=None) -> bool:
        """
        Envía un email de oferta/promoción a un cliente usando las plantillas de `core/emails/promocion_oferta`.
        Args:
            cliente: `accounts.models.Cliente` (tiene relación a `usuario` con email)
            promocion: instancia de `promociones.models.Promocion`
            cupon: instancia de `promociones.models.CuponGenerado`
            link: URL de canje
            funcion: (opcional) función relacionada
            request: (opcional) request HTTP
        """
        usuario = getattr(cliente, 'usuario', None)
        destinatario = usuario.email if usuario else None
        if not destinatario:
            self.logger.warning('Cliente sin email, se omite el envío de oferta')
            return False

        context = {
            'cliente': cliente,
            'usuario': usuario,
            'promocion': promocion,
            'cupon': cupon,
            'link': link,
            'funcion': funcion,
            'site_name': 'CineGest',
            'request': request,
        }

        asunto = f"Oferta limitada: {promocion.nombre} — ¡aprovechá ahora!"

        return self._enviar_email(
            asunto=asunto,
            template_html='core/emails/promocion_oferta.html',
            template_txt='core/emails/promocion_oferta.txt',
            destinatario=destinatario,
            context=context
        )


# Instancia singleton del servicio
notificacion_service = NotificacionService()
