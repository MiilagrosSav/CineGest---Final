"""
Vista para procesar la compra de entradas
"""

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction, IntegrityError
from django.core.exceptions import ValidationError
from django.http import JsonResponse
import logging
import json

from cine.models import Funcion, Butaca
from ventas.models import Venta, Entrada
from accounts.models import Cliente
from ventas.intercambio_service import intercambio_service
from ventas.constants import MotivoIntercambio
from promociones.services import calcular_precio_final

logger = logging.getLogger(__name__)


@login_required
def procesar_compra(request, funcion_id):
    """Vista para procesar la compra de entradas"""
    # Bloquear acceso a empleados
    if hasattr(request.user, 'rol') and request.user.rol == 'empleado':
        messages.warning(request, '⚠️ Los empleados deben usar el módulo de venta presencial.')
        return redirect('ventas:dashboard_presencial')
    
    if request.method != 'POST':
        return redirect('ventas:seleccionar_butacas', funcion_id=funcion_id)
    
    funcion = get_object_or_404(Funcion, id=funcion_id)
    
    # Obtener las butacas seleccionadas del formulario o JSON
    content_type = (request.headers.get('Content-Type') or '').lower()
    is_json_request = content_type.startswith('application/json')
    butacas_ids = []

    if is_json_request:
        raw_body = (request.body or b'').strip()
        if not raw_body:
            return JsonResponse(
                {'error': 'Cuerpo JSON vacío. Envia una lista de butacas.'},
                status=400
            )

        try:
            payload = json.loads(raw_body.decode('utf-8'))
        except Exception:
            return JsonResponse(
                {'error': 'JSON inválido.'},
                status=400
            )

        butacas_ids = payload.get('butacas') or payload.get('butacas_ids') or []
        if not isinstance(butacas_ids, list):
            return JsonResponse(
                {'error': 'El campo butacas debe ser una lista.'},
                status=400
            )
    else:
        butacas_ids = request.POST.getlist('butacas[]')
    
    if not butacas_ids:
        if is_json_request:
            return JsonResponse(
                {'error': 'Debes seleccionar al menos una butaca.'},
                status=400
            )
        messages.error(request, '❌ Debes seleccionar al menos una butaca.')
        return redirect('ventas:seleccionar_butacas', funcion_id=funcion_id)
    
    try:
        from django.utils import timezone
        from datetime import timedelta
        
        with transaction.atomic():
            # PASO 1: VALIDAR TODAS LAS BUTACAS CON LOCK ANTES DE CREAR NADA
            butacas_validadas = []
            entradas_reutilizar = []
            
            for butaca_id in butacas_ids:
                butaca = get_object_or_404(Butaca, id=butaca_id)
                
                # Lock pesimista: bloquear la fila para evitar condiciones de carrera
                entrada_ocupada = Entrada.objects.select_for_update().filter(
                    id_funcion=funcion,
                    id_butaca=butaca,
                    estado__in=['RESERVADA', 'VENDIDA', 'PENDIENTE']
                ).first()
                
                if entrada_ocupada:
                    # Excepción: Si es del mismo usuario y es reciente (< 2 min), permitir reutilizar
                    if entrada_ocupada.reservado_por == request.user:
                        tiempo_transcurrido = timezone.now() - entrada_ocupada.fecha_creacion
                        if tiempo_transcurrido < timedelta(minutes=2):
                            entradas_reutilizar.append((entrada_ocupada, butaca))
                            continue
                    
                    # Butaca ocupada por otro usuario o expirada
                    raise Exception(f'La butaca {butaca.fila}{butaca.numero} ya no está disponible. Por favor, actualiza la página y selecciona otra butaca.')
                
                butacas_validadas.append(butaca)
            
            # PASO 2: Todas las butacas están disponibles, ahora sí crear/reutilizar la venta
            cliente, created = Cliente.objects.get_or_create(
                usuario=request.user,
                defaults={
                    'fecha_nacimiento': None,
                }
            )
            
            # Obtener o crear el método de pago por defecto para ventas online
            from ventas.models import MetodoPago
            from decimal import Decimal
            try:
                metodo_pago = MetodoPago.objects.filter(
                    nombre__icontains='Mercado Pago'
                ).first() or MetodoPago.objects.filter(
                    nombre__icontains='Online'
                ).first()
                
                if not metodo_pago:
                    metodo_pago = MetodoPago.objects.create(
                        nombre='Mercado Pago',
                        descripcion='Pago procesado por Mercado Pago'
                    )
            except Exception:
                # Fallback: crear método de pago genérico
                metodo_pago = MetodoPago.objects.create(
                    nombre='Mercado Pago',
                    descripcion='Pago procesado por Mercado Pago'
                )
            
            # Calcular el total preliminar (se recalculará en la pantalla de pago)
            # Por ahora usamos el precio base de la función multiplicado por la cantidad
            total_preliminar = Decimal(str(funcion.precio_base)) * len(butacas_ids)
            _, _, detalle_precio = calcular_precio_final(funcion, len(butacas_ids))
            precio_unitario_entrada = Decimal(str(detalle_precio.get('precio_unitario_final', funcion.precio_base)))
            
            # Vincular cupón de yield/promoción al momento del INSERT (no UPDATE),
            # ya que la DB tiene un trigger que bloquea cambiar cupon_utilizado_id
            # en filas existentes (UPDATE dispara "EL CUPON ES INALTERABLE").
            cupon_yield = None
            promo_token = request.session.get('promo_token')
            print(f"\n[YIELD DEBUG] procesar_compra: promo_token en sesión='{promo_token}'")
            if promo_token:
                try:
                    from promociones.models.cuponGenerado import CuponGenerado
                    cupon_yield = CuponGenerado.objects.filter(token=str(promo_token), usado=True).first()
                    print(f"[YIELD DEBUG]   cupon_yield encontrado: {cupon_yield is not None}"
                          f"{'  token=' + str(cupon_yield.token) + '  politica=' + str(cupon_yield.politica_origen_id) if cupon_yield else ''}")
                except Exception:
                    logger.exception('Error buscando cupón de yield para la sesión')
                    print(f"[YIELD DEBUG]   ERROR buscando cupon")
            else:
                print(f"[YIELD DEBUG]   Sin promo_token en sesión, cupon_yield=None")
            
            provisional_venta_id = request.POST.get('provisional_venta_id')
            venta_provisional = None

            if provisional_venta_id:
                venta_provisional = Venta.objects.select_for_update().filter(
                    id_venta=provisional_venta_id,
                    id_cliente=cliente,
                    estado='PENDIENTE',
                    activo=True,
                ).first()

            # Reusar la venta provisional para mantener una unica venta por flujo.
            # Asi la transicion de estado queda lineal: PENDIENTE -> PENDIENTE_PAGO -> CONFIRMADA.
            if venta_provisional:
                venta = venta_provisional
            else:
                venta = Venta.objects.create(
                    id_cliente=cliente,
                    tipo_venta='ONLINE',
                    estado='PENDIENTE',
                    id_metodo_pago=metodo_pago,
                    total=total_preliminar,
                    cupon_utilizado=cupon_yield,
                )

            # Limpiar referencia de sesión de la venta provisional para esta función.
            request.session.pop(f'reserva_venta_funcion_{funcion.id}', None)
            request.session.modified = True
            
            # PASO 3: Reutilizar entradas del mismo usuario
            for entrada_ocupada, butaca in entradas_reutilizar:
                entrada_ocupada.id_venta = venta
                entrada_ocupada.estado = 'RESERVADA'
                entrada_ocupada.precio_unitario = precio_unitario_entrada
                entrada_ocupada.fecha_creacion = timezone.now()  # Resetear timer
                entrada_ocupada.save()
            
            # PASO 4: Crear nuevas entradas para butacas validadas
            for butaca in butacas_validadas:
                # Eliminar entradas zombie (CANCELADA/EXPIRADA) que bloquearían la butaca.
                # NO se reutilizan porque CANCELADA/EXPIRADA son estados terminales con
                # transición vacía — intentar cambiar su estado lanza ValidationError.
                Entrada.objects.filter(
                    id_funcion=funcion,
                    id_butaca=butaca,
                    estado__in=['CANCELADA', 'EXPIRADA']
                ).delete()

                # Crear nueva entrada limpia
                Entrada.objects.create(
                    id_venta=venta,
                    id_funcion=funcion,
                    id_sala=funcion.sala,
                    id_butaca=butaca,
                    id_pelicula=funcion.pelicula,
                    estado='RESERVADA',
                    reservado_por=request.user,
                    precio_unitario=precio_unitario_entrada,
                )
            
            if not is_json_request:
                messages.success(request, f' Se creó tu reserva con {len(butacas_ids)} entrada(s). ¡Ahora procede al pago!')

            # Redirigir al proceso de pago
            if is_json_request:
                return JsonResponse(
                    {
                        'ok': True,
                        'venta_id': venta.id_venta,
                        'redirect_url': f'/ventas/iniciar-pago/{venta.id_venta}/'
                    }
                )
            return redirect('ventas:iniciar_pago', venta_id=venta.id_venta)
            
    except ValidationError as e:
        error_texto = str(e)

        # Mensajes amigables para colisiones de concurrencia o reglas de inmutabilidad
        if 'id_venta' in error_texto and 'inmutable' in error_texto:
            mensaje = (
                'La butaca que intentaste reservar cambió de estado mientras procesábamos tu compra. '
                'Actualiza la página y selecciona nuevamente las butacas disponibles.'
            )
        elif 'UQ_entrada_funcion_butaca_activa' in error_texto:
            mensaje = (
                'Una o más butacas ya fueron tomadas por otro cliente en este momento. '
                'Actualiza la página y vuelve a intentar con butacas disponibles.'
            )
        else:
            mensaje = 'No se pudo completar la compra por un cambio concurrente en las butacas seleccionadas. Intenta nuevamente.'

        logger.warning('Error de validación en compra concurrente (funcion=%s, user=%s): %s', funcion_id, request.user.id, error_texto)
        if is_json_request:
            return JsonResponse({'error': mensaje}, status=409)
        messages.error(request, f'❌ {mensaje}')
        return redirect('ventas:seleccionar_butacas', funcion_id=funcion_id)

    except IntegrityError as e:
        # Colisión de unicidad típica cuando dos usuarios confirman la misma butaca en paralelo
        logger.warning('IntegrityError en compra concurrente (funcion=%s, user=%s): %s', funcion_id, request.user.id, str(e))
        mensaje = (
            'Una o más butacas fueron reservadas por otro cliente al mismo tiempo. '
            'Actualiza la página y elige otras butacas.'
        )
        if is_json_request:
            return JsonResponse({'error': mensaje}, status=409)
        messages.error(request, f'❌ {mensaje}')
        return redirect('ventas:seleccionar_butacas', funcion_id=funcion_id)

    except Exception as e:
        if is_json_request:
            return JsonResponse(
                {'error': f'Error al procesar la compra: {str(e)}'},
                status=400
            )
        messages.error(request, f'❌ Error al procesar la compra: {str(e)}')
        return redirect('ventas:seleccionar_butacas', funcion_id=funcion_id)


@login_required
def confirmar_compra(request, funcion_id):
    """Vista para mostrar resumen y confirmar la compra antes del pago"""
    # Bloquear acceso a empleados
    if hasattr(request.user, 'rol') and request.user.rol == 'empleado':
        messages.warning(request, '⚠️ Los empleados deben usar el módulo de venta presencial.')
        return redirect('ventas:dashboard_presencial')
    
    if request.method != 'POST':
        return redirect('ventas:seleccionar_butacas', funcion_id=funcion_id)
    
    funcion = get_object_or_404(Funcion, id=funcion_id)
    butacas_ids = request.POST.getlist('butacas[]')
    
    if not butacas_ids:
        messages.error(request, '❌ Debes seleccionar al menos una butaca.')
        return redirect('ventas:seleccionar_butacas', funcion_id=funcion_id)
    
    # Obtener las butacas seleccionadas
    butacas = Butaca.objects.filter(id__in=butacas_ids)
    
    # -----------------------------------------------------------
    # CORRECCIÓN: Recuperar el cupón de la sesión
    # -----------------------------------------------------------
    from promociones.models.promocion import Promocion
    
    promo_id = request.session.get('promo_activa_id')
    promo_obj = None
    
    if promo_id:
        # Buscamos la promoción real en la base de datos
        promo_obj = Promocion.objects.filter(pk=promo_id).first()

    # -----------------------------------------------------------
    # LLAMADA CORREGIDA: Pasamos 'promocion_especifica'
    # -----------------------------------------------------------
    # Ahora sí la calculadora sabe que tiene que aplicar el 2x1
    total, promo_aplicada, detalle = calcular_precio_final(
        funcion, 
        len(butacas_ids), 
        promocion_especifica=promo_obj  # <--- ¡ESTA ES LA CLAVE!
    )

    precio_unitario_final = detalle.get('precio_unitario_final')
    
    context = {
        'funcion': funcion,
        'butacas': butacas,
        'cantidad': len(butacas_ids),
        'precio_unitario': funcion.precio_base,
        'precio_unitario_final': precio_unitario_final,
        'total': total,
        'promocion_aplicada': promo_aplicada,
        'detalle_promocion': detalle,
        'butacas_ids': butacas_ids,
    }
    
    return render(request, 'ventas/iniciar_pago.html', context)


@login_required
def procesar_intercambio(request, venta_id, funcion_id):
    """Procesar el intercambio: asignar nuevas butacas a la venta existente y cancelar las antiguas.

    Este flujo no realiza cobros; crea las nuevas entradas en estado 'RESERVADA' y marca
    las entradas antiguas como 'CANCELADA'. Usa IntercambioService para toda la lógica.
    """
    if request.method != 'POST':
        return redirect('ventas:seleccionar_butacas_intercambio', venta_id=venta_id, funcion_id=funcion_id)

    funcion = get_object_or_404(Funcion, id=funcion_id)
    venta = get_object_or_404(Venta, id_venta=venta_id, id_cliente__usuario=request.user)

    butacas_ids = request.POST.getlist('butacas[]')
    cantidad_necesaria = venta.entradas.count()

    logger.info(
        f"Usuario {request.user.username} procesando: "
        f"venta {venta_id}, función {funcion_id}, {len(butacas_ids)} butacas seleccionadas"
    )

    # Validaciones básicas
    if not butacas_ids:
        messages.error(request, '❌ Debes seleccionar al menos una butaca para el intercambio.')
        return redirect('ventas:seleccionar_butacas_intercambio', venta_id=venta_id, funcion_id=funcion_id)

    if len(butacas_ids) != cantidad_necesaria:
        messages.error(
            request,
            f'❌ Debes seleccionar exactamente {cantidad_necesaria} butaca(s) para este intercambio.'
        )
        return redirect('ventas:seleccionar_butacas_intercambio', venta_id=venta_id, funcion_id=funcion_id)

    # Obtener objetos Butaca
    butacas = list(Butaca.objects.filter(id__in=butacas_ids, sala=funcion.sala, es_pasillo=False))
    
    if len(butacas) != len(butacas_ids):
        messages.error(request, '❌ Algunas butacas seleccionadas no son válidas.')
        return redirect('ventas:seleccionar_butacas_intercambio', venta_id=venta_id, funcion_id=funcion_id)

    # Ejecutar intercambio usando el servicio
    print("\n" + "="*80)
    print("🔄 INICIANDO INTERCAMBIO")
    print(f"   Venta ID: {venta_id}")
    print(f"   Estado ANTES: {venta.estado}")
    print(f"   Tiene pago ANTES: {hasattr(venta, 'pago') and venta.pago is not None}")
    if hasattr(venta, 'pago') and venta.pago:
        print(f"   Método pago ANTES: {venta.pago.id_metodo_pago.nombre}")
    print("="*80 + "\n")
    
    exitoso, mensaje, intercambio = intercambio_service.ejecutar_intercambio(
        venta=venta,
        funcion_destino=funcion,
        butacas=butacas,
        motivo=MotivoIntercambio.OTRO,
        request=request
    )
    
    print("\n" + "="*80)
    print("🔄 INTERCAMBIO COMPLETADO")
    print(f"   Exitoso: {exitoso}")
    print(f"   Mensaje: {mensaje}")
    if exitoso:
        venta.refresh_from_db()
        print(f"   Estado DESPUÉS: {venta.estado}")
        print(f"   Tiene pago DESPUÉS: {hasattr(venta, 'pago') and venta.pago is not None}")
        if hasattr(venta, 'pago') and venta.pago:
            print(f"   Método pago DESPUÉS: {venta.pago.id_metodo_pago.nombre}")
            print(f"   Monto pago DESPUÉS: {venta.pago.monto}")
            print(f"   Estado pago DESPUÉS: {venta.pago.estado}")
        print(f"   Entradas estado: {list(venta.entradas.values_list('estado', flat=True))}")
    print("="*80 + "\n")

    if exitoso:
        logger.info(f"Intercambio exitoso: venta {venta_id}, intercambio #{intercambio.id_intercambio}")
        
        print("✅ REDIRIGIENDO A: intercambio_exitoso")
        
        # IMPORTANTE: Usar redirect() para implementar el patrón Post/Redirect/Get (PRG)
        # Esto previene que al recargar la página se re-ejecute el POST
        messages.success(request, f'¡Intercambio realizado con éxito! Tus entradas han sido actualizadas.')
        return redirect('ventas:intercambio_exitoso', intercambio_id=intercambio.id_intercambio)
    else:
        logger.error(f"Intercambio fallido para venta {venta_id}: {mensaje}")
        messages.error(request, f'❌ {mensaje}')
        return redirect('ventas:seleccionar_butacas_intercambio', venta_id=venta_id, funcion_id=funcion_id)
