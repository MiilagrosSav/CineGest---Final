"""
Vistas para el procesamiento de pagos con Mercado Pago
"""

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.http import JsonResponse, HttpResponse
from django.contrib import messages
from django.conf import settings
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal
import json

from ventas.models import Venta, Pago, MetodoPago
from ventas.mercadopago_service import MercadoPagoService
from core.services import notificacion_service
from cine.models.configuracion_cine import ConfiguracionCine

from promociones.services import calcular_precio_final


@login_required
def iniciar_pago(request, venta_id):
    """
    Iniciar el proceso de pago con Mercado Pago
    Muestra página con botón oficial de MP
    """
    print("\n" + "="*80)
    print("💳 ACCESO A INICIAR_PAGO")
    print(f"   Venta ID: {venta_id}")
    print(f"   Método HTTP: {request.method}")
    print(f"   URL completa: {request.get_full_path()}")
    print(f"   Referer: {request.META.get('HTTP_REFERER', 'Sin referer')}")
    print("="*80 + "\n")
    
    from decimal import Decimal
    from django.conf import settings
    from ventas.models import Venta
    from ventas.mercadopago_service import MercadoPagoService
    from promociones.models.promocion import Promocion
    from promociones.services import calcular_precio_final
    
    # 1. Obtener la venta
    venta = get_object_or_404(Venta, id_venta=venta_id, id_cliente__usuario=request.user)
    
    # ✅ VALIDACIÓN DE EXPIRACIÓN: Verificar si la venta ha expirado
    from datetime import timedelta
    from django.utils import timezone
    
    tiempo_expiracion_minutos = ConfiguracionCine.load().reserva_tiempo_espera
    tiempo_corte = timezone.now() - timedelta(minutes=tiempo_expiracion_minutos)
    
    if venta.estado in ['PENDIENTE', 'PENDIENTE_PAGO'] and venta.fecha_compra < tiempo_corte:
        # La venta ha expirado - expirarla automáticamente
        venta.estado = 'EXPIRADA'
        venta.activo = False
        venta.save(update_fields=['estado', 'activo'])
        
        # Liberar las butacas
        from ventas.models import Entrada
        Entrada.objects.filter(
            id_venta=venta,
            estado__in=['PENDIENTE', 'RESERVADA']
        ).update(estado='EXPIRADA')
        
        messages.error(
            request, 
            '⏰ Tu sesión de reserva ha expirado. Por favor, selecciona tus asientos nuevamente.'
        )
        return redirect('cine:cartelera')
    
    # Verificar estado — aceptamos PENDIENTE_PAGO para permitir reintentos tras fallo
    if venta.estado not in ['PENDIENTE', 'PENDIENTE_PAGO']:
        messages.error(request, '❌ Esta venta ya no está disponible para pago.')
        return redirect('ventas:mis_ventas')
    
    # 2. Recuperar datos para el cálculo
    cantidad = venta.entradas.count()
    # Asumimos que todas las entradas son de la misma función
    if cantidad > 0:
        funcion = venta.entradas.first().id_funcion
    else:
        # Caso borde: venta sin entradas
        messages.error(request, '❌ La venta no tiene entradas.')
        return redirect('ventas:mis_ventas')

    # 3. Recuperar la PROMOCIÓN (Prioridad: guardada en venta > guardada en sesión)
    promo_obj = None

    print(f"\n[YIELD DEBUG] iniciar_pago venta={venta.id_venta}")
    print(f"[YIELD DEBUG]   cupon_utilizado_id={venta.cupon_utilizado_id}")
    print(f"[YIELD DEBUG]   session promo_activa_id={request.session.get('promo_activa_id')}")
    print(f"[YIELD DEBUG]   session promo_token='{request.session.get('promo_token')}'")

    # A) ¿Ya está guardada en la venta vía cupón? (aplica en reintento de pago)
    if getattr(venta, 'cupon_utilizado', None):
        try:
            promo_obj = venta.cupon_utilizado.politica_origen.promocion_a_otorgar
            print(f"[YIELD DEBUG]   Path A OK: promo='{promo_obj.codigo if promo_obj else None}'")
        except Exception as e:
            print(f"[YIELD DEBUG]   Path A ERROR: {e}")
            promo_obj = None
    else:
        print(f"[YIELD DEBUG]   Path A: venta sin cupon_utilizado")

    # B) Fallback: ¿Está en la sesión? (primera visita con cupón de yield o código)
    if promo_obj is None:
        promo_id_sess = request.session.get('promo_activa_id')
        if promo_id_sess:
            try:
                promo_obj = Promocion.objects.filter(pk=promo_id_sess).first()
                print(f"[YIELD DEBUG]   Path B OK: promo='{promo_obj.codigo if promo_obj else None}'")
            except Exception as e:
                print(f"[YIELD DEBUG]   Path B ERROR: {e}")
                promo_obj = None
        else:
            print(f"[YIELD DEBUG]   Path B: sin promo_activa_id en sesión")

    print(f"[YIELD DEBUG]   => promo_obj final: '{promo_obj.codigo if promo_obj else 'NINGUNA'}'")

    # 4. RE-CALCULAR PRECIOS (Usando el servicio corregido que sabe hacer 2x1)
    # Le pasamos 'promocion_especifica' para forzar que use el cupón si existe.
    total_calculado, promo_aplicada, detalle = calcular_precio_final(
        funcion, 
        cantidad, 
        promocion_especifica=promo_obj 
    )
    
    # Extraer valores del detalle calculado
    original_total = detalle['total_original']
    ahorro = detalle['ahorro']
    discounted_total = total_calculado

    # 5. Crear el servicio de Mercado Pago y la Preferencia
    try:
        mp_service = MercadoPagoService()
        # Pasar el total ya calculado (con descuento) para que MP cobre exactamente
        # lo mismo que se muestra en pantalla, sin re-calcular internamente.
        preference_response = mp_service.crear_preferencia_pago(venta, request, total_override=total_calculado)
        
        if preference_response.get('status') == 201:
            preference_id = preference_response['response']['id']
            init_point = preference_response['response']['init_point']
            
            # Limpiar sesión SOLO si se creó la preferencia correctamente
            request.session.pop('promo_activa_id', None)
            request.session.pop('promo_token', None)
            request.session.modified = True
            
            # Preparar variables visuales para el template
            tipo_promo_str = str(promo_aplicada.tipo_descuento).upper() if promo_aplicada else None
            
            # Calculamos unidades pagadas para el texto "Pagás X de Y"
            unidades_pagadas_2x1 = None
            if tipo_promo_str == '2X1':
                unidades_pagadas_2x1 = int((cantidad // 2) + (cantidad % 2))

            from django.urls import reverse
            venta_expiracion = venta.fecha_compra + timedelta(minutes=tiempo_expiracion_minutos)

            # Guardar init_point en sesión para usarla desde el redirect view
            # Evita que el navegador navegue directamente al CDN de MP (causa 403 de CloudFront)
            request.session[f'mp_init_point_{venta.id_venta}'] = init_point
            request.session.modified = True

            context = {
                'venta': venta,
                'mercadopago_public_key': settings.MERCADOPAGO_PUBLIC_KEY,
                'preference_id': preference_id,
                'init_point': init_point,
                
                # Variables numéricas
                'original_total': original_total,
                'discounted_total': discounted_total,
                'ahorro': ahorro,
                
                # Variables de texto formateadas (Display)
                'original_total_display': f"{original_total:.2f}",
                'discounted_total_display': f"{discounted_total:.2f}",
                'ahorro_display': f"{ahorro:.2f}",
                
                # Banderas lógicas
                'tiene_descuento': ahorro > 0,
                'applied_promo_nombre': promo_aplicada.nombre if promo_aplicada else None,
                'applied_promo_tipo': tipo_promo_str,
                'unidades_pagadas_2x1': unidades_pagadas_2x1,

                # Para el countdown y bloqueo JS
                'venta_expiracion_iso': venta_expiracion.isoformat(),
                'tiempo_reserva_segundos': tiempo_expiracion_minutos * 60,
                'marcar_pago_url': reverse('ventas:marcar_pago_iniciado', args=[venta.id_venta]),
                'ir_a_mp_url': reverse('ventas:ir_a_mercadopago', args=[venta.id_venta]),
            }
            
            return render(request, 'ventas/iniciar_pago.html', context)
            
        else:
            # Error de MP
            error_msg = preference_response.get('response', {}).get('message', 'Error desconocido')
            messages.error(request, f'❌ Error al conectar con Mercado Pago: {error_msg}')
            return redirect('ventas:mis_ventas')

    except Exception as e:
        import traceback
        traceback.print_exc()
        messages.error(request, f'❌ Ocurrió un error al procesar: {str(e)}')
        return redirect('ventas:mis_ventas')


@login_required
def pago_exitoso(request):
    """Vista cuando el pago fue exitoso"""
    # Debug: imprimir todos los parámetros recibidos
    print("=" * 50)
    print("PAGO EXITOSO - Parámetros recibidos:")
    print("GET params:", dict(request.GET))
    print("=" * 50)
    
    # Mercado Pago envía estos parámetros en la URL
    payment_id = request.GET.get('payment_id') or request.GET.get('collection_id')
    status = request.GET.get('status') or request.GET.get('collection_status')
    
    # Priorizar venta_id que pasamos nosotros en la URL
    venta_id = request.GET.get('venta_id')
    external_reference = request.GET.get('external_reference') or request.GET.get('preference_id') or venta_id
    
    print(f"🔍 Buscando venta: venta_id={venta_id}, external_reference={external_reference}")
    
    # Si no hay referencia, buscar la última venta pendiente del usuario
    if not external_reference:
        print("⚠️ No se recibió external_reference, buscando última venta pendiente del usuario...")
        try:
            venta = Venta.objects.filter(
                id_cliente__usuario=request.user,
                estado='PENDIENTE'
            ).latest('fecha_compra')
            external_reference = venta.id_venta
            print(f"✅ Encontrada venta pendiente: #{venta.id_venta}")
        except Venta.DoesNotExist:
            print("❌ No se encontró ninguna venta pendiente")
            messages.warning(request, '⚠️ No se pudo identificar la venta. Verifica tu historial de compras.')
            return redirect('ventas:mis_ventas')
    
    if external_reference:
        try:
            venta = Venta.objects.get(id_venta=external_reference)
            print(f"📦 Procesando venta #{venta.id_venta} - Estado actual: {venta.estado}")
            
            # ✅ VALIDACIÓN DE EXPIRACIÓN: Verificar si la venta ha expirado antes de procesar
            from datetime import timedelta
            tiempo_expiracion_minutos = ConfiguracionCine.load().reserva_tiempo_espera
            tiempo_corte = timezone.now() - timedelta(minutes=tiempo_expiracion_minutos)
            
            if venta.estado == 'PENDIENTE' and venta.fecha_compra < tiempo_corte:
                # La venta ha expirado - marcarla como expirada
                print(f"⏰ Venta #{venta.id_venta} ha expirado (>{tiempo_expiracion_minutos} minutos)")
                venta.estado = 'EXPIRADA'
                venta.activo = False
                venta.save(update_fields=['estado', 'activo'])
                
                # Liberar las butacas
                from ventas.models import Entrada
                Entrada.objects.filter(
                    id_venta=venta,
                    estado__in=['PENDIENTE', 'RESERVADA']
                ).update(estado='EXPIRADA')
                
                messages.error(
                    request, 
                    '⏰ Tu sesión de reserva ha expirado. Por favor, selecciona tus asientos nuevamente.'
                )
                return redirect('cine:cartelera')
            
            # ✅ VERIFICAR SI LA VENTA YA ESTÁ CONFIRMADA (por webhook o visita anterior)
            if venta.estado == 'CONFIRMADA':
                print(f"✅ Venta #{venta.id_venta} ya está confirmada. Mostrando pantalla de éxito.")
                # Obtener el pago existente
                pago = venta.pago if hasattr(venta, 'pago') else None
                
                context = {
                    'venta': venta,
                    'pago': pago,
                    'payment_id': payment_id or (pago.nro_transaccion if pago else f'MP-{venta.id_venta}'),
                    'ya_confirmada': True  # Flag para el template
                }
                
                messages.success(request, '¡Tu compra ya fue confirmada exitosamente!')
                return render(request, 'ventas/pago_exitoso_simple.html', context)
            
            # VERIFICAR SI LA VENTA YA FUE CONFIRMADA POR INTERCAMBIO
            if hasattr(venta, 'pago') and venta.pago and venta.pago.id_metodo_pago.nombre == 'Intercambio':
                print(f"⚠️ Venta #{venta.id_venta} ya fue confirmada por intercambio.")
                
                context = {
                    'venta': venta,
                    'pago': venta.pago,
                    'payment_id': venta.pago.nro_transaccion,
                    'es_intercambio': True
                }
                
                messages.info(request, '✅ Tu compra fue confirmada mediante intercambio.')
                return render(request, 'ventas/pago_exitoso_simple.html', context)
            
            # Solo procesar el pago si la venta está pendiente
            if venta.estado not in ['PENDIENTE', 'PENDIENTE_PAGO']:
                print(f"ℹ️ Venta #{venta.id_venta} en estado {venta.estado}.")
                # Aunque no sea CONFIRMADA ni PENDIENTE, mostrar el template de éxito
                pago = venta.pago if hasattr(venta, 'pago') else None
                
                context = {
                    'venta': venta,
                    'pago': pago,
                    'payment_id': payment_id or (pago.nro_transaccion if pago else f'MP-{venta.id_venta}'),
                }
                
                messages.info(request, f'Tu venta está en estado: {venta.get_estado_display()}')
                return render(request, 'ventas/pago_exitoso_simple.html', context)
            
            # Calcular el total con descuentos ANTES de cambiar el estado a CONFIRMADA.
            # calcular_total() tiene una optimización que retorna venta.total si el estado
            # ya es CONFIRMADA, lo que devolvería el total preliminar sin descuento.
            total_real = venta.calcular_total()

            # Actualizar el estado de la venta
            venta.estado = 'CONFIRMADA'
            
            # Buscar dinámicamente el MetodoPago (solo si no tiene uno ya asignado)
            if not venta.id_metodo_pago:
                try:
                    metodo_pago = MetodoPago.objects.filter(
                        nombre__icontains='Mercado Pago'
                    ).first() or MetodoPago.objects.filter(
                        nombre__icontains='Online'
                    ).first()
                    
                    if not metodo_pago:
                        raise MetodoPago.DoesNotExist
                        
                except (MetodoPago.DoesNotExist, AttributeError):
                    print("❌ ERROR: MetodoPago 'Mercado Pago' no existe en la BD")
                    print("   Creando MetodoPago como fallback...")
                    metodo_pago = MetodoPago.objects.create(
                        nombre='Mercado Pago',
                        descripcion='Pago procesado por Mercado Pago'
                    )
                
                venta.estado = 'CONFIRMADA'
                venta.id_metodo_pago = metodo_pago
                venta.save(update_fields=['estado', 'id_metodo_pago'])
            else:
                # Ya tiene método de pago asignado, solo actualizar estado
                metodo_pago = venta.id_metodo_pago
                venta.estado = 'CONFIRMADA'
                venta.save(update_fields=['estado'])
            
            print(f"✅ Venta actualizada a CONFIRMADA con método de pago: {venta.id_metodo_pago.nombre}")
            
            pago, created = Pago.objects.get_or_create(
                id_venta=venta,
                defaults={
                    'monto': total_real,
                    'estado': 'COMPLETADO',
                    'nro_transaccion': payment_id or f'MP-{venta.id_venta}',
                    'id_metodo_pago': metodo_pago
                }
            )
            
            if not created:
                pago.estado = 'COMPLETADO'
                pago.nro_transaccion = payment_id or f'MP-{venta.id_venta}'
                pago.id_metodo_pago = metodo_pago
                pago.save()
            
            print(f"💳 Pago registrado: {pago.nro_transaccion}")
            
            # Actualizar el estado de las entradas (usando .save() para disparar validaciones)
            entradas = venta.entradas.all()
            precio_unitario_final = Decimal(str(total_real))
            if entradas.count() > 0:
                precio_unitario_final = (Decimal(str(total_real)) / entradas.count()).quantize(Decimal('0.01'))
            entradas_actualizadas = 0
            for entrada in entradas:
                entrada.estado = 'VENDIDA'
                if not entrada.precio_unitario or Decimal(str(entrada.precio_unitario)) <= 0:
                    entrada.precio_unitario = precio_unitario_final
                    entrada.save(update_fields=['estado', 'precio_unitario'])
                else:
                    entrada.save(update_fields=['estado'])
                entradas_actualizadas += 1
            print(f"🎟️ {entradas_actualizadas} entradas actualizadas a VENDIDA")
            
            messages.success(request, ' ¡Pago procesado exitosamente! Tu compra ha sido confirmada.')
            
            # Enviar email de confirmación (incluir QR por entrada)
            # Si falla el email, no se rompe el flujo de pago
            try:
                notificacion_service.enviar_confirmacion_compra(venta, request)
                print("📧 Email de confirmación enviado")
            except Exception as e:
                print(f"⚠️ Error enviando email de confirmación: {e}")
                # No mostramos mensaje al usuario porque el pago ya fue exitoso

            # Persistir uso del cupón referenciado en la venta (si existe). Preferimos
            # usar `venta.cupon_utilizado` (persistido por MercadoPagoService) para
            # soportar confirmaciones vía webhook.
            try:
                if getattr(venta, 'cupon_utilizado', None):
                    cupon = venta.cupon_utilizado
                    if cupon and not cupon.usado:
                        cupon.usado = True
                        cupon.save()
                else:
                    # Fallback: si aún no estaba persistido en la venta, intentar desde sesión
                    promo_token = request.session.get('promo_token')
                    if promo_token:
                        from promociones.models.cuponGenerado import CuponGenerado
                        cupon = CuponGenerado.objects.filter(token=str(promo_token)).first()
                        if cupon and not cupon.usado:
                            cupon.usado = True
                            cupon.save()
            except Exception as e:
                print(f"Error marcando cupón como usado: {e}")

            # Limpiar posibles promociones activas en sesión (ya se consumieron)
            try:
                if request.session.get('promo_activa_id'):
                    request.session.pop('promo_activa_id', None)
                if request.session.get('promo_token'):
                    request.session.pop('promo_token', None)
                request.session.modified = True
                request.session.save()
            except Exception:
                pass

            context = {
                'venta': venta,
                'pago': pago,
                'payment_id': payment_id or f'MP-{venta.id_venta}',
            }

            return render(request, 'ventas/pago_exitoso_simple.html', context)
            
        except Venta.DoesNotExist:
            print(f"❌ No se encontró la venta con ID: {external_reference}")
            messages.error(request, '❌ No se encontró la venta.')
    
    print("⚠️ Redirigiendo a mis_ventas (no se procesó el pago)")
    return redirect('ventas:mis_ventas')


@login_required
@require_POST
def marcar_pago_iniciado(request, venta_id):
    """
    AJAX endpoint: transiciona la venta de PENDIENTE → PENDIENTE_PAGO
    cuando el usuario hace click en el botón de Mercado Pago.
    Esto impide que otra sesión inicie un segundo pago para la misma reserva.
    """
    venta = get_object_or_404(Venta, id_venta=venta_id, id_cliente__usuario=request.user)
    if venta.estado == 'PENDIENTE':
        # Update atómico: solo cambia si sigue siendo PENDIENTE
        updated = Venta.objects.filter(pk=venta.pk, estado='PENDIENTE').update(estado='PENDIENTE_PAGO')
        if updated:
            return JsonResponse({'status': 'ok'})
        # Otra request ganó la carrera — probablemente ya es PENDIENTE_PAGO
        return JsonResponse({'status': 'ok', 'ya_marcada': True})
    if venta.estado == 'PENDIENTE_PAGO':
        return JsonResponse({'status': 'ok', 'ya_marcada': True})
    return JsonResponse({'status': 'error', 'message': 'Venta no disponible para pago.'}, status=400)


@login_required
def ir_a_mercadopago(request, venta_id):
    """
    Redirect intermediario server-side hacia Mercado Pago.
    Evita el 403 de CloudFront que ocurre cuando el navegador navega directamente
    a init_point (headers Referer/Sec-Fetch-Site bloqueados por el WAF de MP).
    Usa el init_point guardado en sesión por iniciar_pago.
    """
    from django.http import HttpResponseRedirect

    venta = get_object_or_404(Venta, id_venta=venta_id, id_cliente__usuario=request.user)

    if venta.estado not in ['PENDIENTE', 'PENDIENTE_PAGO']:
        messages.error(request, '❌ Esta venta ya no está disponible para pago.')
        return redirect('ventas:mis_ventas')

    session_key = f'mp_init_point_{venta_id}'
    init_point = request.session.get(session_key)

    if not init_point:
        # Sesión expirada o acceso directo sin haber pasado por iniciar_pago
        messages.warning(request, '⚠️ Tu sesión de pago expiró. Por favor intentá nuevamente.')
        return redirect('ventas:iniciar_pago', venta_id=venta_id)

    # Un solo uso: eliminar de sesión para evitar reutilizar el mismo link
    del request.session[session_key]
    request.session.modified = True

    return HttpResponseRedirect(init_point)


@login_required
def pago_fallido(request):
    """Vista cuando el pago falló"""
    external_reference = request.GET.get('external_reference')
    
    if external_reference:
        try:
            venta = Venta.objects.get(id_venta=external_reference)
            
            messages.error(request, '❌ El pago no pudo ser procesado. Intenta nuevamente.')
            
            context = {
                'venta': venta,
            }
            
            return render(request, 'ventas/pago_fallido.html', context)
            
        except Venta.DoesNotExist:
            pass
    
    return redirect('ventas:mis_ventas')


@login_required
def pago_pendiente(request):
    """Vista cuando el pago está pendiente"""
    external_reference = request.GET.get('external_reference')
    
    if external_reference:
        try:
            venta = Venta.objects.get(id_venta=external_reference)
            
            # Actualizar el estado de la venta a pendiente de pago
            venta.estado = 'PENDIENTE_PAGO'
            venta.save()
            
            messages.info(request, '⏳ Tu pago está pendiente de confirmación.')
            
            context = {
                'venta': venta,
            }
            
            return render(request, 'ventas/pago_pendiente.html', context)
            
        except Venta.DoesNotExist:
            pass
    
    return redirect('ventas:mis_ventas')


@csrf_exempt
@require_POST
def webhook_mercadopago(request):
    """
    Webhook para recibir notificaciones IPN de Mercado Pago
    Esta vista procesa las notificaciones automáticas de cambios de estado de pago
    """
    try:
        # Leer los datos del webhook
        data = json.loads(request.body)
        
        # Procesar la notificación
        mp_service = MercadoPagoService()
        payment_info = mp_service.procesar_notificacion_webhook(data)
        
        if payment_info and payment_info['status'] == 200:
            payment_data = payment_info['response']
            
            # Obtener el ID de la venta desde external_reference
            external_reference = payment_data.get('external_reference')
            payment_status = payment_data.get('status')
            payment_id = payment_data.get('id')
            
            if external_reference:
                venta = Venta.objects.get(id_venta=external_reference)
                
                # Actualizar según el estado del pago
                if payment_status == 'approved':
                    # ✅ Verificar si ya está confirmada para evitar procesamiento duplicado
                    if venta.estado == 'CONFIRMADA':
                        print(f"ℹ️ Webhook: Venta #{venta.id_venta} ya está confirmada. Ignorando.")
                        return HttpResponse(status=200)
                    
                    # Buscar dinámicamente el MetodoPago
                    try:
                        metodo_pago = MetodoPago.objects.filter(
                            nombre__icontains='Mercado Pago'
                        ).first() or MetodoPago.objects.filter(
                            nombre__icontains='Online'
                        ).first()
                        
                        if not metodo_pago:
                            raise MetodoPago.DoesNotExist
                            
                    except (MetodoPago.DoesNotExist, AttributeError):
                        print("❌ ERROR: MetodoPago 'Mercado Pago' no existe en la BD")
                        print("   Creando MetodoPago como fallback...")
                        metodo_pago = MetodoPago.objects.create(
                            nombre='Mercado Pago',
                            descripcion='Pago procesado por Mercado Pago'
                        )
                    
                    # Calcular el total con descuentos ANTES de confirmar (misma razón
                    # que en pago_exitoso: calcular_total() short-circuits para CONFIRMADA).
                    total_real = venta.calcular_total()

                    venta.estado = 'CONFIRMADA'
                    venta.id_metodo_pago = metodo_pago
                    venta.save(update_fields=['estado', 'id_metodo_pago'])

                    # Si la venta tiene un cupón referenciado, marcarlo como usado.
                    try:
                        if getattr(venta, 'cupon_utilizado', None):
                            cupon = venta.cupon_utilizado
                            if cupon and not cupon.usado:
                                cupon.usado = True
                                cupon.save()
                    except Exception as e:
                        print(f"Error marcando cupon de venta como usado (webhook): {e}")
                    
                    # Actualizar el pago
                    
                    pago, created = Pago.objects.get_or_create(
                        id_venta=venta,
                        defaults={
                            'monto': total_real,
                            'estado': 'COMPLETADO',
                            'nro_transaccion': str(payment_id),
                            'id_metodo_pago': metodo_pago
                        }
                    )
                    
                    if not created:
                        pago.estado = 'COMPLETADO'
                        pago.nro_transaccion = str(payment_id)
                        pago.id_metodo_pago = metodo_pago
                        pago.save()
                    
                    # Actualizar entradas (usando .save() para disparar validaciones)
                    entradas = venta.entradas.all()
                    precio_unitario_final = Decimal(str(total_real))
                    if entradas.count() > 0:
                        precio_unitario_final = (Decimal(str(total_real)) / entradas.count()).quantize(Decimal('0.01'))
                    for entrada in entradas:
                        entrada.estado = 'VENDIDA'
                        if not entrada.precio_unitario or Decimal(str(entrada.precio_unitario)) <= 0:
                            entrada.precio_unitario = precio_unitario_final
                            entrada.save(update_fields=['estado', 'precio_unitario'])
                        else:
                            entrada.save(update_fields=['estado'])
                    
                    # Enviar email de confirmación desde webhook (no hay request)
                    # Si falla el email, no se rompe el webhook
                    try:
                        notificacion_service.enviar_confirmacion_compra(venta, None)
                        print("📧 Email de confirmación enviado desde webhook")
                    except Exception as e:
                        print(f"⚠️ Error enviando email desde webhook: {e}")
                        # No lanzar excepción para no romper el webhook
                    
                elif payment_status == 'pending':
                    venta.estado = 'PENDIENTE_PAGO'
                    venta.save(update_fields=['estado'])
                    
                elif payment_status in ['rejected', 'cancelled']:
                    venta.estado = 'CANCELADA'
                    venta.save(update_fields=['estado'])
        
        return HttpResponse(status=200)
        
    except Exception as e:
        # Log del error (puedes usar logging de Django)
        print(f"Error en webhook: {str(e)}")
        return HttpResponse(status=500)
