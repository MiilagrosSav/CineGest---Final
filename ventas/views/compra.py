"""
Vista para procesar la compra de entradas
"""

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction
from cine.models import Funcion, Butaca
from ventas.models import Venta, Entrada
from accounts.models import Cliente
from django.shortcuts import get_object_or_404


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
                    'direccion': '',  # Valores opcionales para Cliente
                    'fecha_nacimiento': None,
                }
            )
            
            # Crear la venta
            venta = Venta.objects.create(
                id_cliente=cliente,
                tipo_venta='ONLINE',
                estado='PENDIENTE'
            )
            
            # Verificar que las butacas estén disponibles y crear las entradas
            for butaca_id in butacas_ids:
                butaca = get_object_or_404(Butaca, id=butaca_id)
                
                # Verificar que la butaca no esté ocupada
                entrada_existente = Entrada.objects.filter(
                    id_funcion=funcion,
                    id_butaca=butaca,
                    estado__in=['RESERVADA', 'VENDIDA']
                ).exists()
                
                if entrada_existente:
                    raise Exception(f'La butaca {butaca.fila}{butaca.numero} ya está ocupada.')
                
                # Crear la entrada
                Entrada.objects.create(
                    id_venta=venta,
                    id_funcion=funcion,
                    id_sala=funcion.sala,
                    id_butaca=butaca,
                    id_pelicula=funcion.pelicula,
                    estado='RESERVADA'
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
    
    # Calcular el total
    total = len(butacas_ids) * funcion.precio_base
    
    context = {
        'funcion': funcion,
        'butacas': butacas,
        'cantidad': len(butacas_ids),
        'precio_unitario': funcion.precio_base,
        'total': total,
        'butacas_ids': butacas_ids,
    }
    
    return render(request, 'ventas/confirmar_compra.html', context)


@login_required
def procesar_intercambio(request, venta_id, funcion_id):
    """Procesar el intercambio: asignar nuevas butacas a la venta existente y cancelar las antiguas.

    Este flujo no realiza cobros; crea las nuevas entradas en estado 'RESERVADA' y marca
    las entradas antiguas como 'CANCELADA'. Usa locking para evitar race-conditions.
    """
    if request.method != 'POST':
        return redirect('ventas:seleccionar_butacas_intercambio', venta_id=venta_id, funcion_id=funcion_id)

    funcion = get_object_or_404(Funcion, id=funcion_id)
    venta = get_object_or_404(Venta, id_venta=venta_id, id_cliente__usuario=request.user)

    butacas_ids = request.POST.getlist('butacas[]')
    cantidad_necesaria = venta.entradas.count()

    if not butacas_ids:
        messages.error(request, '❌ Debes seleccionar al menos una butaca para el intercambio.')
        return redirect('ventas:seleccionar_butacas_intercambio', venta_id=venta_id, funcion_id=funcion_id)

    if len(butacas_ids) != cantidad_necesaria:
        messages.error(request, f'❌ Debes seleccionar exactamente {cantidad_necesaria} butaca(s) para este intercambio.')
        return redirect('ventas:seleccionar_butacas_intercambio', venta_id=venta_id, funcion_id=funcion_id)

    try:
        with transaction.atomic():
            # Lock the selected butacas to avoid race conditions
            butacas_qs = Butaca.objects.select_for_update().filter(id__in=butacas_ids, sala=funcion.sala)
            butacas = list(butacas_qs)

            if len(butacas) != len(butacas_ids):
                raise Exception('Algunas butacas seleccionadas no existen en la sala.')

            # Asegurarse de que ninguna butaca esté ocupada en la función destino
            ocupadas = Entrada.objects.select_for_update().filter(
                id_funcion=funcion,
                id_butaca_id__in=butacas_ids,
                estado__in=['RESERVADA', 'VENDIDA', 'USADA']
            ).exists()

            if ocupadas:
                raise Exception('Alguna de las butacas seleccionadas ya está ocupada en la nueva función.')

            # Marcar entradas antiguas como canceladas (lock sobre las entradas de la venta)
            venta.entradas.select_for_update().update(estado='CANCELADA')

            # Crear nuevas entradas para la venta con las butacas seleccionadas
            for butaca in butacas:
                Entrada.objects.create(
                    id_venta=venta,
                    id_funcion=funcion,
                    id_sala=funcion.sala,
                    id_butaca=butaca,
                    id_pelicula=funcion.pelicula,
                    estado='RESERVADA'
                )

        messages.success(request, '✅ Intercambio realizado con éxito.')
        return redirect('ventas:detalle_venta', venta_id=venta.id_venta)

    except Exception as e:
        messages.error(request, f'❌ No se pudo completar el intercambio: {str(e)}')
        return redirect('ventas:seleccionar_butacas_intercambio', venta_id=venta_id, funcion_id=funcion_id)
