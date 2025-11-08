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


@login_required
def iniciar_pago(request, venta_id):
    """
    Iniciar el proceso de pago con Mercado Pago
    Redirige directamente al checkout de Mercado Pago
    """
    # Obtener la venta
    venta = get_object_or_404(Venta, id_venta=venta_id, id_cliente__usuario=request.user)
    
    # Verificar que la venta esté en estado pendiente
    if venta.estado != 'PENDIENTE':
        messages.error(request, '❌ Esta venta ya no está disponible para pago.')
        return redirect('ventas:mis_ventas')
    
    # Crear el servicio de Mercado Pago
    mp_service = MercadoPagoService()
    
    try:
        # Crear la preferencia de pago
        preference_response = mp_service.crear_preferencia_pago(venta, request)
        
        if preference_response.get('status') == 201:
            # Preferencia creada exitosamente - redirigir directamente a Mercado Pago
            init_point = preference_response['response']['init_point']
            print(f"✅ Redirigiendo a Mercado Pago: {init_point}")
            return redirect(init_point)
        else:
            # Error al crear la preferencia
            error_msg = preference_response.get('response', {}).get('message', 'Error desconocido')
            print("Error en preferencia:", error_msg)
            messages.error(request, f'❌ Error al procesar el pago: {error_msg}')
            return redirect('ventas:mis_ventas')
            
    except Exception as e:
        print("Excepción al crear preferencia:", str(e))
        import traceback
        traceback.print_exc()
        messages.error(request, f'❌ Error al procesar el pago: {str(e)}')
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
            
            # Actualizar el estado de la venta
            venta.estado = 'CONFIRMADA'
            venta.save()
            print(f"✅ Venta actualizada a CONFIRMADA")
            
            # Crear o actualizar el registro de pago
            metodo_pago, _ = MetodoPago.objects.get_or_create(
                nombre='Mercado Pago',
                defaults={'descripcion': 'Pago procesado por Mercado Pago'}
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
                pago.save()
            
            print(f"💳 Pago registrado: {pago.nro_transaccion}")
            
            # Actualizar el estado de las entradas
            entradas_actualizadas = venta.entradas.all().update(estado='VENDIDA')
            print(f"🎟️ {entradas_actualizadas} entradas actualizadas a VENDIDA")
            
            messages.success(request, '✅ ¡Pago procesado exitosamente! Tu compra ha sido confirmada.')
            
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
                    
                    # Actualizar el pago
                    metodo_pago, _ = MetodoPago.objects.get_or_create(
                        nombre='Mercado Pago',
                        defaults={'descripcion': 'Pago procesado por Mercado Pago'}
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
                        pago.save()
                    
                    # Actualizar entradas
                    venta.entradas.all().update(estado='VENDIDA')
                    
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
