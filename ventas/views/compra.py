"""
Vista para procesar la compra de entradas
"""

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction
import logging

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
    
    if request.method != 'POST':
        return redirect('ventas:seleccionar_butacas', funcion_id=funcion_id)
    
    funcion = get_object_or_404(Funcion, id=funcion_id)
    
    # Obtener las butacas seleccionadas del formulario
    butacas_ids = request.POST.getlist('butacas[]')
    
    if not butacas_ids:
        messages.error(request, '❌ Debes seleccionar al menos una butaca.')
        return redirect('ventas:seleccionar_butacas', funcion_id=funcion_id)
    
    try:
        with transaction.atomic():
            # Obtener o crear el cliente asociado al usuario
            cliente, created = Cliente.objects.get_or_create(
                usuario=request.user,
                defaults={
                    'fecha_nacimiento': None,
                }
            )
            
            # Crear la venta
            venta = Venta.objects.create(
                id_cliente=cliente,
                tipo_venta='ONLINE',
                estado='PENDIENTE'
            )
            
            # Verificar que las butacas estén disponibles y crear/reutilizar las entradas
            for butaca_id in butacas_ids:
                butaca = get_object_or_404(Butaca, id=butaca_id)
                
                # Verificar que la butaca no esté ocupada (RESERVADA o VENDIDA)
                entrada_existente = Entrada.objects.filter(
                    id_funcion=funcion,
                    id_butaca=butaca,
                    estado__in=['RESERVADA', 'VENDIDA']
                ).exists()
                
                if entrada_existente:
                    raise Exception(f'La butaca {butaca.fila}{butaca.numero} ya está ocupada.')
                
                # Buscar entrada CANCELADA que podamos reutilizar
                entrada_cancelada = Entrada.objects.filter(
                    id_funcion=funcion,
                    id_butaca=butaca,
                    estado='CANCELADA'
                ).first()
                
                if entrada_cancelada:
                    # Reutilizar entrada cancelada
                    entrada_cancelada.id_venta = venta
                    entrada_cancelada.estado = 'RESERVADA'
                    entrada_cancelada.reservado_por = request.user
                    entrada_cancelada.save()
                else:
                    # Crear nueva entrada si no hay canceladas
                    Entrada.objects.create(
                        id_venta=venta,
                        id_funcion=funcion,
                        id_sala=funcion.sala,
                        id_butaca=butaca,
                        id_pelicula=funcion.pelicula,
                        estado='RESERVADA',
                        reservado_por=request.user
                    )
            
            messages.success(request, f'✅ Se creó tu reserva con {len(butacas_ids)} entrada(s). ¡Ahora procede al pago!')
            
            # Redirigir al proceso de pago
            return redirect('ventas:iniciar_pago', venta_id=venta.id_venta)
            
    except Exception as e:
        messages.error(request, f'❌ Error al procesar la compra: {str(e)}')
        return redirect('ventas:seleccionar_butacas', funcion_id=funcion_id)
            
    except Exception as e:
        messages.error(request, f'❌ Error al procesar la compra: {str(e)}')
        return redirect('ventas:seleccionar_butacas', funcion_id=funcion_id)


@login_required
def confirmar_compra(request, funcion_id):
    """Vista para mostrar resumen y confirmar la compra antes del pago"""
    
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
        f"Usuario {request.user.username} procesando intercambio: "
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
    exitoso, mensaje, intercambio = intercambio_service.ejecutar_intercambio(
        venta=venta,
        funcion_destino=funcion,
        butacas=butacas,
        motivo=MotivoIntercambio.OTRO,
        request=request
    )

    if exitoso:
        logger.info(f"Intercambio exitoso: venta {venta_id}, intercambio #{intercambio.id_intercambio}")
        messages.success(request, f'✅ {mensaje}')
        return redirect('ventas:detalle_venta', venta_id=venta.id_venta)
    else:
        logger.error(f"Intercambio fallido para venta {venta_id}: {mensaje}")
        messages.error(request, f'❌ {mensaje}')
        return redirect('ventas:seleccionar_butacas_intercambio', venta_id=venta_id, funcion_id=funcion_id)
