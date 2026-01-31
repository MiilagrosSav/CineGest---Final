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
import json

from ventas.models import Venta, Pago, MetodoPago
from ventas.mercadopago_service import MercadoPagoService
from core.services import notificacion_service

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
    
    # Verificar estado
    if venta.estado != 'PENDIENTE':
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
    
    # A) ¿Ya está guardada en la venta? (Idealmente sí, por el paso anterior)
    if getattr(venta, 'cupon_utilizado', None):
        promo_obj = venta.cupon_utilizado.promocion
        
    # B) Fallback: ¿Está en la sesión?
    elif request.session.get('promo_activa_id'):
        try:
            promo_obj = Promocion.objects.get(pk=request.session['promo_activa_id'])
        except Promocion.DoesNotExist:
            pass

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
        # IMPORTANTE: Si tu mp_service usa venta.calcular_total() internamente,
        # asegúrate de que venta.calcular_total() también use la lógica nueva.
        # O mejor, pasa el total explícito si tu servicio lo permite.
        preference_response = mp_service.crear_preferencia_pago(venta, request)
        
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
            
            # VERIFICAR SI LA VENTA YA FUE CONFIRMADA POR INTERCAMBIO
            if hasattr(venta, 'pago') and venta.pago and venta.pago.id_metodo_pago.nombre == 'Intercambio':
                print(f"⚠️ Venta #{venta.id_venta} ya fue confirmada por intercambio. Ignorando webhook de Mercado Pago.")
                messages.info(request, '✅ Tu compra ya está confirmada.')
                return redirect('ventas:detalle_venta', venta_id=venta.id_venta)
            
            # Actualizar el estado de la venta
            venta.estado = 'CONFIRMADA'
            venta.save()
            print(f"✅ Venta actualizada a CONFIRMADA")
            
            # Crear o actualizar el registro de pago
            try:
                metodo_pago = MetodoPago.objects.get(nombre='Mercado Pago')
            except MetodoPago.DoesNotExist:
                print("❌ ERROR: MetodoPago 'Mercado Pago' no existe en la BD")
                print("   Ejecutar: python scripts/crear_metodos_pago_completos.py")
                # Crear como fallback
                metodo_pago = MetodoPago.objects.create(
                    nombre='Mercado Pago',
                    descripcion='Pago procesado por Mercado Pago'
                )
            
            pago, created = Pago.objects.get_or_create(
                id_venta=venta,
                defaults={
                    'monto': venta.calcular_total(),
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
            
            # Actualizar el estado de las entradas
            entradas_actualizadas = venta.entradas.all().update(estado='VENDIDA')
            print(f"🎟️ {entradas_actualizadas} entradas actualizadas a VENDIDA")
            
            messages.success(request, '✅ ¡Pago procesado exitosamente! Tu compra ha sido confirmada.')
            
            # Enviar email de confirmación (incluir QR por entrada)
            try:
                notificacion_service.enviar_confirmacion_compra(venta, request)
            except Exception as e:
                print(f"Error enviando email de confirmación: {e}")

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
                    venta.estado = 'CONFIRMADA'
                    venta.save()

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
                    try:
                        metodo_pago = MetodoPago.objects.get(nombre='Mercado Pago')
                    except MetodoPago.DoesNotExist:
                        print("❌ ERROR: MetodoPago 'Mercado Pago' no existe en la BD")
                        print("   Ejecutar: python scripts/crear_metodos_pago_completos.py")
                        # Crear como fallback
                        metodo_pago = MetodoPago.objects.create(
                            nombre='Mercado Pago',
                            descripcion='Pago procesado por Mercado Pago'
                        )
                    
                    pago, created = Pago.objects.get_or_create(
                        id_venta=venta,
                        defaults={
                            'monto': venta.calcular_total(),
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
                    
                    # Actualizar entradas
                    venta.entradas.all().update(estado='VENDIDA')
                    # Enviar email de confirmación desde webhook (no hay request)
                    try:
                        notificacion_service.enviar_confirmacion_compra(venta, None)
                    except Exception as e:
                        print(f"Error enviando email (webhook): {e}")
                    
                elif payment_status == 'pending':
                    venta.estado = 'PENDIENTE_PAGO'
                    venta.save()
                    
                elif payment_status in ['rejected', 'cancelled']:
                    venta.estado = 'CANCELADA'
                    venta.save()
        
        return HttpResponse(status=200)
        
    except Exception as e:
        # Log del error (puedes usar logging de Django)
        print(f"Error en webhook: {str(e)}")
        return HttpResponse(status=500)
