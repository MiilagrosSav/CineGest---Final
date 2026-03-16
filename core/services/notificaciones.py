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
            return ConfiguracionCine.load()
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
                'id_funcion__sala',
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
                entrada_qr = self._generar_qr_base64(f"ENTRADA:{entrada.id_entrada}")
                entradas_con_qr.append({
                    'entrada': entrada,
                    'qr_src': entrada_qr
                })
            
            # Detectar la promoción aplicada y el total real recalculando con
            # include_detalle=True (bypasea la optimización de estado CONFIRMADA).
            promocion_aplicada = None
            descuento_info = None
            total_real = venta.total  # fallback al total guardado
            es_compra_por_intercambio = venta.intercambios.filter(estado='COMPLETADO').exists()
            try:
                total_calculado, promo_detectada, detalle_email = venta.calcular_total(include_detalle=True)
                total_real = total_calculado
                if (not es_compra_por_intercambio) and promo_detectada and detalle_email.get('ahorro', 0) > 0:
                    promocion_aplicada = promo_detectada
                    descuento_info = {
                        'subtotal': detalle_email['total_original'],
                        'descuento': detalle_email['ahorro'],
                        'total_final': total_calculado,
                    }
            except Exception:
                pass
            
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
                'total_real': total_real,
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
            
            # Obtener las nuevas entradas de la función destino dentro de la venta
            from ventas.models import Entrada
            entradas_intercambiadas = Entrada.objects.filter(
                id_venta=venta,
                id_funcion=funcion_destino,
                estado__in=['VENDIDA', 'ENTREGADA', 'RESERVADA']
            ).select_related(
                'id_funcion__pelicula',
                'id_funcion__sala',
                'id_butaca'
            )
            
            # Generar QR para nuevas entradas
            entradas_con_qr = []
            for entrada in entradas_intercambiadas:
                entrada_qr = self._generar_qr_base64(f"ENTRADA:{entrada.id_entrada}")
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
                'entradas_nuevas': list(entradas_intercambiadas),  # lista plana para mostrar butacas en plantilla
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
    
    def enviar_yield_promocion(
        self,
        cliente,
        funcion,
        promocion,
        cupon,
        cupon_url: str,
    ) -> bool:
        """
        Enviar email de oferta de yield management (baja ocupación de sala).
        Usa las plantillas promocion_yield.html / promocion_yield.txt.
        """
        try:
            configuracion_cine = self._get_configuracion_cine()
            usuario = cliente.usuario

            # Texto del descuento
            tipo = (getattr(promocion, 'tipo_descuento', '') or '').upper()
            valor = getattr(promocion, 'valor_descuento', 0)
            if tipo == 'PORCENTAJE':
                descuento_texto = f'{int(valor)}% de descuento'
            elif tipo == '2X1':
                descuento_texto = '2x1 en entradas'
            elif tipo == 'MONTO_FIJO':
                descuento_texto = f'${int(valor)} de descuento'
            else:
                descuento_texto = 'Descuento especial'

            context = {
                'usuario': usuario,
                'cliente': cliente,
                'funcion': funcion,
                'pelicula': funcion.pelicula,
                'sala': funcion.sala,
                'promocion': promocion,
                'cupon': cupon,
                'cupon_url': cupon_url,
                'descuento_texto': descuento_texto,
                'configuracion_cine': configuracion_cine,
            }

            html_content = render_to_string('core/emails/promocion_yield.html', context)
            text_content = render_to_string('core/emails/promocion_yield.txt', context)

            nombre_cine = configuracion_cine.nombre if configuracion_cine else 'CineGest'
            subject = f'🎬 ¡Oferta especial! {funcion.pelicula.titulo} - {nombre_cine}'
            email = EmailMultiAlternatives(
                subject=subject,
                body=text_content,
                from_email=self.from_email,
                to=[usuario.email]
            )
            email.attach_alternative(html_content, 'text/html')
            email.send(fail_silently=False)
            logger.info(f'Email yield management enviado a {usuario.email} - Cupón: {cupon.token}')
            return True

        except Exception as e:
            logger.error(f'Error enviando email yield management a {cliente.usuario.email}: {e}')
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

    def enviar_comprobante_pago(self, pago, request=None) -> bool:
        """
        Enviar comprobante de pago (recibo financiero) por email
        
        Este es un documento legal/contable que respalda la transacción monetaria,
        distinto al ticket de entrada que es para acceder al cine.
        
        Args:
            pago: Instancia de Pago
            request: HttpRequest (opcional, para URLs absolutas)
            
        Returns:
            True si se envió correctamente, False si falló
        """
        try:
            from ventas.models import Venta
            
            configuracion_cine = self._get_configuracion_cine()
            venta = pago.id_venta
            usuario = venta.id_cliente.usuario
            
            # Obtener datos de la venta para el detalle
            entradas = venta.entradas.select_related(
                'id_funcion__pelicula',
                'id_funcion__sala',
            ).all()
            
            # Detectar la promoción aplicada y el precio efectivo por entrada recalculando
            # con include_detalle=True (bypasea la optimización de estado CONFIRMADA).
            promo_email = None
            precio_unitario_efectivo = None
            try:
                _, promo_email, detalle_email = venta.calcular_total(include_detalle=True)
                precio_unitario_efectivo = detalle_email.get('precio_unitario_final')
            except Exception:
                pass

            # Agrupar entradas por película
            peliculas_agrupadas = {}
            for entrada in entradas:
                pelicula_nombre = entrada.id_funcion.pelicula.titulo
                # Usar precio efectivo con descuento si se detectó promo;
                # si no, usar precio_unitario guardado en la entrada o precio_base como fallback.
                precio_base_entrada = entrada.id_funcion.precio_base
                precio = precio_unitario_efectivo or (entrada.precio_unitario if entrada.precio_unitario else precio_base_entrada)
                if pelicula_nombre not in peliculas_agrupadas:
                    peliculas_agrupadas[pelicula_nombre] = {
                        'pelicula': entrada.id_funcion.pelicula,
                        'cantidad': 0,
                        'precio_unitario': precio,
                    }
                peliculas_agrupadas[pelicula_nombre]['cantidad'] += 1

            # Calcular subtotales
            conceptos = []
            for pelicula_nombre, datos in peliculas_agrupadas.items():
                subtotal = datos['cantidad'] * datos['precio_unitario']
                conceptos.append({
                    'descripcion': f"Entrada(s) - {pelicula_nombre}",
                    'cantidad': datos['cantidad'],
                    'precio_unitario': datos['precio_unitario'],
                    'subtotal': subtotal,
                })

            # Información de descuento si aplica
            descuento_aplicado = None
            if promo_email:
                descuento_aplicado = {
                    'nombre': promo_email.nombre,
                    'tipo': promo_email.tipo_descuento,
                    'porcentaje': str(promo_email.valor_descuento) if promo_email.tipo_descuento == 'PORCENTAJE' else None,
                }
            elif hasattr(venta, 'cupon_utilizado') and venta.cupon_utilizado:
                cupon = venta.cupon_utilizado
                if hasattr(cupon, 'id_promocion') and cupon.id_promocion:
                    descuento_aplicado = {
                        'nombre': cupon.id_promocion.nombre,
                        'tipo': 'PORCENTAJE',
                        'porcentaje': cupon.id_promocion.descuento_porcentaje,
                    }
            
            # Preparar contexto
            context = {
                'usuario': usuario,
                'pago': pago,
                'venta': venta,
                'conceptos': conceptos,
                'descuento_aplicado': descuento_aplicado,
                'configuracion_cine': configuracion_cine,
                'fecha_emision': pago.fecha_pago,
                'metodo_pago': pago.id_metodo_pago.nombre,
                'site_name': self._get_site_name(request),
            }
            
            # Renderizar templates
            html_content = render_to_string('core/emails/comprobante_pago.html', context)
            text_content = render_to_string('core/emails/comprobante_pago.txt', context)
            
            # Crear email
            nombre_cine = configuracion_cine.nombre if configuracion_cine else 'CineGest'
            subject = f"Comprobante de Pago - Orden #{venta.id_venta} - {nombre_cine}"
            email = EmailMultiAlternatives(
                subject=subject,
                body=text_content,
                from_email=self.from_email,
                to=[usuario.email]
            )
            email.attach_alternative(html_content, "text/html")
            
            # Intentar generar y adjuntar PDF (opcional)
            try:
                pdf_content = self._generar_comprobante_pdf(context)
                if pdf_content:
                    email.attach(
                        f'Comprobante_Pago_{venta.id_venta}.pdf',
                        pdf_content,
                        'application/pdf'
                    )
                    logger.info(f"PDF del comprobante adjunto para pago #{pago.id_pago}")
            except Exception as e:
                logger.warning(f"No se pudo generar PDF del comprobante: {e}")
                # Continuar enviando el email sin PDF
            
            # Enviar
            email.send(fail_silently=False)
            logger.info(f"Comprobante de pago enviado a {usuario.email} para pago #{pago.id_pago}")
            return True
            
        except Exception as e:
            logger.error(f"Error enviando comprobante de pago #{pago.id_pago}: {e}")
            return False
    
    def _generar_comprobante_pdf(self, context):
        """
        Generar PDF del comprobante de pago usando WeasyPrint
        
        Args:
            context: Diccionario con datos del comprobante
            
        Returns:
            Bytes del PDF o None si falla
        """
        try:
            from weasyprint import HTML
            import tempfile
            
            # Renderizar HTML del comprobante
            html_content = render_to_string('core/emails/comprobante_pago_pdf.html', context)
            
            # Generar PDF
            pdf_file = HTML(string=html_content).write_pdf()
            
            return pdf_file
            
        except ImportError:
            logger.warning("WeasyPrint no está instalado. No se puede generar PDF.")
            return None
        except Exception as e:
            logger.error(f"Error generando PDF del comprobante: {e}")
            return None

    def enviar_ticket_presencial(self, venta, email_destino: str) -> bool:
        """
        Envía el ticket de una venta presencial a la dirección de correo indicada.
        Reutiliza el template de confirmación de compra pero dirige el mail al
        email capturado por el empleado en caja (no necesariamente el del cliente).
        """
        try:
            configuracion_cine = self._get_configuracion_cine()

            entradas = venta.entradas.select_related(
                'id_funcion__pelicula', 'id_funcion__sala', 'id_butaca'
            ).all()
            primera_entrada = entradas.first()
            cantidad = entradas.count()

            entradas_con_qr = []
            for entrada in entradas:
                qr = self._generar_qr_base64(f"ENTRADA:{entrada.id_entrada}")
                entradas_con_qr.append({'entrada': entrada, 'qr_src': qr})

            qr_src = self._generar_qr_base64(f"VENTA:{venta.codigo_compra}")
            total_real = venta.total or venta.calcular_total()

            context = {
                'usuario': venta.id_cliente.usuario,
                'nombre_comprador': email_destino,
                'venta': venta,
                'primera_entrada': primera_entrada,
                'cantidad': cantidad,
                'entradas': entradas_con_qr,
                'qr_src': qr_src,
                'promocion_aplicada': None,
                'descuento_info': None,
                'total_real': total_real,
                'configuracion_cine': configuracion_cine,
                'site_name': configuracion_cine.nombre if configuracion_cine else 'CineGest',
            }

            html_content = render_to_string('core/emails/confirmacion_compra.html', context)
            text_content = render_to_string('core/emails/confirmacion_compra.txt', context)

            nombre_cine = configuracion_cine.nombre if configuracion_cine else 'CineGest'
            subject = f"Tu entrada para {primera_entrada.id_funcion.pelicula.titulo} - {nombre_cine}"
            email = EmailMultiAlternatives(
                subject=subject,
                body=text_content,
                from_email=self.from_email,
                to=[email_destino],
            )
            email.attach_alternative(html_content, "text/html")
            email.send(fail_silently=False)
            logger.info(f"Ticket presencial venta #{venta.id_venta} enviado a {email_destino}")
            return True
        except Exception as e:
            logger.error(f"Error enviando ticket presencial venta #{venta.id_venta}: {e}")
            return False


# Singleton del servicio
notificacion_service = NotificacionService()
